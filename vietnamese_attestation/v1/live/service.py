"""Transport-independent E Live API service, restricted to local fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .aggregation import (
    aggregate_candidate,
    build_attestation_package,
    contradictory_evidence_eligible,
    positive_evidence_eligible,
)
from .authority_adapter import validate_loaded_authority_bundle
from .common import (
    LIVE_TOOL_SCHEMA_VERSION,
    LiveSchemaError,
    canonical_bytes,
    canonical_sha256,
    load_object,
    require_exact_keys,
    require_keys,
    require_sha256,
    require_string,
    seal,
    utc_now,
    verify_seal,
)
from .judge import FixtureJudge, judge_request_sha256, make_judge_request, validate_provider_transport_result
from .ledger import EventLedger
from .execution import derive_coverage_from_ledger
from .policies import (
    provider_roles_by_name,
    render_query_plan,
    validate_policy_bundle,
)
from .registry import admit_source, validate_registry
from .replay import replay_run
from .retrieval import (
    FixtureDiscovery,
    FixtureFetcher,
    FixtureTransientFetchError,
    UnknownPhysicalOutcome,
    cluster_global_evidence,
    extract_fetched_evidence,
    extract_snapshot_evidence,
)
from .judge import ProviderAdapter
from .authority_adapter.production import load_production_authority
from .schemas import (
    PREFLIGHT_RESPONSE_SCHEMA_ID,
    compute_run_spec_id,
    validate_preflight_response,
    validate_run_request,
)
from .snapshot import verify_snapshot
from ..strict_json import reject_link

AUTHORIZATION_SCHEMA_ID = "ELocalCanaryAuthorizationReceiptV1"
RUN_SCHEMA_ID = "ELiveRunRecordV1"


class RunBlocked(LiveSchemaError):
    def __init__(self, response: Mapping[str, Any]) -> None:
        self.response = dict(response)
        super().__init__("E Live preflight is BLOCKED")


class ProviderUnknownPhysicalOutcome(LiveSchemaError):
    pass


def make_authorization_receipt(
    *,
    cohort_id: str,
    candidate_ids: Sequence[str],
    registry_self_sha256: str,
    snapshot_manifest_sha256: str,
    policy_hashes: Mapping[str, str],
    receipt_ref: str = "local-fixture/controlled-canary-receipt.json",
) -> dict[str, Any]:
    return seal(
        {
            "schema_id": AUTHORIZATION_SCHEMA_ID,
            "schema_version": LIVE_TOOL_SCHEMA_VERSION,
            "receipt_id": "local-controlled-canary-receipt-v1",
            "receipt_ref": receipt_ref,
            "authorization_status": "CONTROLLED_LOCAL_FIXTURE_ONLY",
            "cohort_id": cohort_id,
            "candidate_ids": sorted(set(candidate_ids)),
            "registry_self_sha256": registry_self_sha256,
            "snapshot_manifest_sha256": snapshot_manifest_sha256,
            "policy_hashes": dict(policy_hashes),
            "provider_calls_allowed": 0,
            "network_calls_allowed": 0,
            "integrity": {},
        }
    )


def validate_authorization_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    require_exact_keys(
        value,
        {
            "schema_id",
            "schema_version",
            "receipt_id",
            "receipt_ref",
            "authorization_status",
            "cohort_id",
            "candidate_ids",
            "registry_self_sha256",
            "snapshot_manifest_sha256",
            "policy_hashes",
            "provider_calls_allowed",
            "network_calls_allowed",
            "integrity",
        },
    )
    if value["schema_id"] != AUTHORIZATION_SCHEMA_ID or value["schema_version"] != LIVE_TOOL_SCHEMA_VERSION:
        raise LiveSchemaError("authorization receipt identity mismatch")
    for key in ("receipt_id", "receipt_ref", "cohort_id"):
        require_string(value[key], path=f"$.{key}")
    candidate_ids = value["candidate_ids"]
    if not isinstance(candidate_ids, list) or not candidate_ids or candidate_ids != sorted(set(candidate_ids)):
        raise LiveSchemaError("authorization candidate_ids must be sorted and unique")
    for index, candidate_id in enumerate(candidate_ids):
        require_string(candidate_id, path=f"$.candidate_ids[{index}]")
    for key in ("registry_self_sha256", "snapshot_manifest_sha256"):
        require_sha256(value[key], path=f"$.{key}")
    policy_hashes = value["policy_hashes"]
    require_exact_keys(
        policy_hashes,
        {
            "retrieval_policy",
            "query_template_set",
            "provider_role_plan",
            "aggregation_policy",
        },
        path="$.policy_hashes",
    )
    for key, digest in policy_hashes.items():
        require_sha256(digest, path=f"$.policy_hashes.{key}")
    if value["authorization_status"] != "CONTROLLED_LOCAL_FIXTURE_ONLY":
        raise LiveSchemaError("authorization receipt is not a local controlled canary receipt")
    if value["provider_calls_allowed"] != 0 or value["network_calls_allowed"] != 0:
        raise LiveSchemaError("zero-provider authorization receipt permits external calls")
    if not verify_seal(value):
        raise LiveSchemaError("authorization receipt self hash mismatch")
    return dict(value)


def make_run_request(
    *,
    run_id: str,
    phase_id: str,
    sense_id: str,
    candidate_id: str,
    term_en: str,
    candidate_vi: str,
    sense_definition: str,
    domain: Mapping[str, Any],
    candidate_variants: Sequence[str],
    authority_refs: Mapping[str, Any],
    budget: Mapping[str, Any],
    policy_hashes: Mapping[str, str],
    query_template_ids: Sequence[str] = ("exact_candidate",),
) -> dict[str, Any]:
    request = {
        "schema_id": "ERunRequestV1",
        "schema_version": LIVE_TOOL_SCHEMA_VERSION,
        "run_id": run_id,
        "run_spec_id": "pending",
        "phase_id": phase_id,
        "sense_id": sense_id,
        "candidate_id": candidate_id,
        "term_en": term_en,
        "candidate_vi": candidate_vi,
        "sense_definition": sense_definition,
        "domain": dict(domain),
        "candidate_variants": list(candidate_variants),
        "query_template_ids": list(query_template_ids),
        "authority_refs": dict(authority_refs),
        "budget": dict(budget),
        "retrieval_policy_sha256": policy_hashes["retrieval_policy"],
        "query_template_set_sha256": policy_hashes["query_template_set"],
        "provider_role_plan_sha256": policy_hashes["provider_role_plan"],
        "aggregation_policy_sha256": policy_hashes["aggregation_policy"],
    }
    request["run_spec_id"] = compute_run_spec_id(request)
    validate_run_request(request)
    return request


class ELiveService:
    """Small internal API implementation; no HTTP client/server is involved."""

    def __init__(
        self,
        *,
        root: str | Path,
        registry: Mapping[str, Any],
        snapshot_root: str | Path,
        policy_bundle: Mapping[str, Mapping[str, Any]],
        authorization_receipt: Mapping[str, Any],
        authorized_cohort_id: str,
        authorized_candidate_ids: Sequence[str],
        credentials_ready: bool = True,
        discovery: FixtureDiscovery | None = None,
        fetcher: FixtureFetcher | None = None,
        judge: FixtureJudge | None = None,
        execution_mode: str = "LOCAL_FIXTURE_ONLY",
        authority_bundle: Mapping[str, Any] | None = None,
        production_authorization_schema: str | Path | None = None,
        production_authority_inputs: Mapping[str, Any] | None = None,
        provider_adapter: ProviderAdapter | None = None,
        clock=utc_now,
    ) -> None:
        self.root = Path(root).absolute()
        reject_link(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry = validate_registry(registry)
        self.snapshot_root = Path(snapshot_root).absolute()
        self.snapshot = verify_snapshot(self.snapshot_root)
        self.policy_bundle = {key: dict(value) for key, value in policy_bundle.items()}
        self.policy_hashes = validate_policy_bundle(self.policy_bundle)
        if execution_mode not in {"LOCAL_FIXTURE_ONLY", "PRODUCTION_AUTHORITY"}:
            raise LiveSchemaError("unsupported E Live execution mode")
        self.execution_mode = execution_mode
        self.authority_bundle = dict(authority_bundle) if authority_bundle is not None else None
        self.production_authority: dict[str, Any] | None = None
        if self.execution_mode == "PRODUCTION_AUTHORITY":
            if authority_bundle is not None or production_authorization_schema is not None:
                raise LiveSchemaError("production authority cannot be supplied as an in-memory bundle or arbitrary schema")
            if production_authority_inputs is None:
                raise LiveSchemaError("production execution requires externally pinned authority inputs")
            self.production_authority = load_production_authority(production_authority_inputs)
            self.authority_bundle = self.production_authority["bundle"]
            self.authorization_receipt = self.production_authority["receipt"]
            if provider_adapter is None:
                raise LiveSchemaError("production execution requires provider adapter")
        else:
            if self.authority_bundle is not None:
                self.authority_bundle = validate_loaded_authority_bundle(self.authority_bundle)
            self.authorization_receipt = validate_authorization_receipt(authorization_receipt)
        if self.authority_bundle is not None and self.authority_bundle.get("execution_mode") != self.execution_mode:
            raise LiveSchemaError("authority bundle execution mode mismatch")
        self.authorized_cohort_id = authorized_cohort_id
        self.authorized_candidate_ids = frozenset(str(item) for item in authorized_candidate_ids)
        self.credentials_ready = bool(credentials_ready)
        self.discovery = discovery
        self.fetcher = fetcher
        self.judge = judge
        self.provider_adapter = provider_adapter
        self.clock = clock
        self.runs: dict[str, dict[str, Any]] = {}

    def preflight(self, request: Mapping[str, Any]) -> dict[str, Any]:
        blockers: list[str] = []
        checks: dict[str, Any] = {}
        try:
            checked = validate_run_request(request)
            checks["request_schema"] = "PASS"
        except Exception as exc:
            checked = dict(request)
            blockers.append("RUN_REQUEST_INVALID")
            checks["request_schema"] = f"FAIL:{type(exc).__name__}"
        if checked.get("run_spec_id") not in {compute_run_spec_id(checked)}:
            blockers.append("RUN_SPEC_ID_MISMATCH")
        candidate_id = str(checked.get("candidate_id", ""))
        if candidate_id not in self.authorized_candidate_ids:
            blockers.append("COHORT_MEMBERSHIP_MISMATCH")
        if checked.get("authority_refs", {}).get("cohort_id") != self.authorized_cohort_id:
            blockers.append("COHORT_ID_MISMATCH")
        authority_refs = checked.get("authority_refs", {})
        candidate_key = authority_refs.get("candidate_key") if isinstance(authority_refs, Mapping) else None
        if not isinstance(candidate_key, Mapping) or (
            candidate_key.get("candidate_id") != candidate_id
            or candidate_key.get("sense_id") != checked.get("sense_id")
            or candidate_key.get("candidate_vi") != checked.get("candidate_vi")
            or candidate_key.get("source_term") != checked.get("term_en")
        ):
            blockers.append("CANDIDATE_KEY_BINDING_MISMATCH")
        try:
            require_sha256(authority_refs.get("input_contract_sha256"), path="$.authority_refs.input_contract_sha256")
        except Exception:
            blockers.append("INPUT_CONTRACT_BINDING_INVALID")
        checks["authorized_cohort"] = "PASS" if not any(item.startswith("COHORT") for item in blockers) else "FAIL"
        receipt = self.authorization_receipt
        if self.execution_mode == "LOCAL_FIXTURE_ONLY":
            if not verify_seal(receipt) or receipt.get("cohort_id") != self.authorized_cohort_id or set(receipt.get("candidate_ids", ())) != set(self.authorized_candidate_ids):
                blockers.append("AUTHORIZATION_RECEIPT_MISMATCH")
        elif receipt.get("authorization_status") != "RUN_AUTHORIZED" or receipt.get("test_only") is not False:
            blockers.append("AUTHORIZATION_RECEIPT_MISMATCH")
        try:
            current_registry = validate_registry(self.registry)
            current_snapshot = verify_snapshot(self.snapshot_root, expected_registry_self_sha256=current_registry["integrity"]["self_sha256"], expected_retrieval_policy_self_sha256=self.policy_hashes["retrieval_policy"])
            checks["registry_snapshot"] = "PASS"
        except Exception as exc:
            current_registry = self.registry
            current_snapshot = self.snapshot
            blockers.append("REGISTRY_OR_SNAPSHOT_INVALID")
            checks["registry_snapshot"] = f"FAIL:{type(exc).__name__}"
        try:
            current_policy_hashes = validate_policy_bundle(self.policy_bundle)
            checks["policy_bundle"] = "PASS"
        except Exception as exc:
            current_policy_hashes = self.policy_hashes
            blockers.append("POLICY_BUNDLE_INVALID")
            checks["policy_bundle"] = f"FAIL:{type(exc).__name__}"
        expected_input_contract = canonical_sha256(candidate_key) if isinstance(candidate_key, Mapping) else None
        exact_request_authority = {
            "registry_self_sha256": current_registry["integrity"]["self_sha256"],
            "snapshot_manifest_sha256": current_snapshot["integrity"]["self_sha256"],
            "input_contract_sha256": expected_input_contract,
        }
        for field, expected_value in exact_request_authority.items():
            if authority_refs.get(field) != expected_value:
                blockers.append(f"REQUEST_{field.upper()}_MISMATCH")
        if self.execution_mode == "LOCAL_FIXTURE_ONLY":
            if receipt.get("registry_self_sha256") != current_registry["integrity"]["self_sha256"] or receipt.get("snapshot_manifest_sha256") != current_snapshot["integrity"]["self_sha256"]:
                blockers.append("AUTHORITY_BINDING_MISMATCH")
            if dict(receipt.get("policy_hashes", {})) != current_policy_hashes:
                blockers.append("AUTHORITY_POLICY_BINDING_MISMATCH")
        else:
            binding = self.production_authority["execution_binding"] if self.production_authority else {}
            exact_production = {
                "cohort_id": self.authorized_cohort_id,
                "candidate_ids": sorted(self.authorized_candidate_ids),
                "run_id": checked.get("run_id"),
                "phase_id": checked.get("phase_id"),
                "run_spec_id": checked.get("run_spec_id"),
                "registry_self_sha256": current_registry["integrity"]["self_sha256"],
                "snapshot_manifest_sha256": current_snapshot["integrity"]["self_sha256"],
                "policy_hashes": current_policy_hashes,
                "provider_role_plan_sha256": current_policy_hashes["provider_role_plan"],
                "budget_sha256": canonical_sha256(checked.get("budget", {})),
            }
            for field, expected_value in exact_production.items():
                if binding.get(field) != expected_value:
                    blockers.append(f"PRODUCTION_{field.upper()}_MISMATCH")
        checks["authorization_receipt"] = "PASS" if "AUTHORIZATION_RECEIPT_MISMATCH" not in blockers else "FAIL"
        checks["authority_adapter"] = "PASS_LOCAL_FIXTURE_ONLY" if self.execution_mode == "LOCAL_FIXTURE_ONLY" else "PASS_RUN_AUTHORIZED"
        expected = {
            "retrieval_policy_sha256": self.policy_hashes.get("retrieval_policy"),
            "query_template_set_sha256": self.policy_hashes.get("query_template_set"),
            "provider_role_plan_sha256": self.policy_hashes.get("provider_role_plan"),
            "aggregation_policy_sha256": self.policy_hashes.get("aggregation_policy"),
        }
        policy_binding_failed = False
        for field, value in expected.items():
            if checked.get(field) != value:
                blockers.append(f"{field.upper()}_MISMATCH")
                policy_binding_failed = True
        checks["policy_bindings"] = "FAIL" if policy_binding_failed else "PASS"
        if not self.credentials_ready:
            blockers.append("CREDENTIAL_READINESS_FAILED")
        checks["credentials_readiness"] = "PASS" if self.credentials_ready else "FAIL"
        checks["provider_calls"] = 0
        checks["network_calls"] = 0
        status = "READY" if not blockers else "BLOCKED"
        response = seal(
            {
                "schema_id": PREFLIGHT_RESPONSE_SCHEMA_ID,
                "schema_version": LIVE_TOOL_SCHEMA_VERSION,
                "status": status,
                "run_id": checked.get("run_id", "unknown"),
                "run_spec_id": checked.get("run_spec_id", "unknown"),
                "provider_calls": 0,
                "blockers": sorted(set(blockers)),
                "checks": checks,
                "integrity": {},
            }
        )
        validate_preflight_response(response)
        return response

    def create_run(self, request: Mapping[str, Any]) -> dict[str, Any]:
        preflight = self.preflight(request)
        if preflight["status"] != "READY":
            raise RunBlocked(preflight)
        checked = validate_run_request(request)
        run_id = checked["run_id"]
        if run_id in self.runs:
            return dict(self.runs[run_id])
        run_root = self.root / "runs" / run_id
        run_root.mkdir(parents=True, exist_ok=False)
        ledger = EventLedger(run_id=run_id, phase_id=checked["phase_id"], clock=self.clock)
        record: dict[str, Any] = {
            "schema_id": RUN_SCHEMA_ID,
            "schema_version": LIVE_TOOL_SCHEMA_VERSION,
            "run_id": run_id,
            "run_spec_id": checked["run_spec_id"],
            "phase_id": checked["phase_id"],
            "status": "RUNNING",
            "provider_calls": 0,
            "network_calls": 0,
            "snapshot_root": str(self.snapshot_root),
            "snapshot_manifest_sha256": self.snapshot["integrity"]["self_sha256"],
            "preflight": preflight,
            "run_root": str(run_root),
            "started_at": self.clock(),
        }
        self.runs[run_id] = record
        try:
            self._execute(checked, record, ledger)
        except Exception as exc:
            if record["status"] == "RUNNING":
                record["status"] = "STOPPED"
            if not ledger.events or ledger.events[-1]["event_kind"] != "STOP_EVENT":
                ledger.append("STOP_EVENT", candidate_replicate_id=checked["candidate_id"], semantic_role="CONTROL", semantic_call_id="exception", transport_attempt_id="exception", failure_disposition=type(exc).__name__, payload={"code": type(exc).__name__, "message": str(exc), "details": {}})
            self._apply_telemetry(record, ledger)
            self._persist_run(record, ledger, package=None)
            raise
        return dict(record)

    def get_run(self, run_id: str) -> dict[str, Any]:
        if run_id not in self.runs:
            path = self.root / "runs" / run_id / "run.json"
            if not path.is_file():
                raise LiveSchemaError("unknown run_id")
            return load_object(path)
        return dict(self.runs[run_id])

    def stop_run(self, run_id: str, *, reason: str = "USER_STOP") -> dict[str, Any]:
        record = self.get_run(run_id)
        if record["status"] in {"COMPLETED", "STOPPED"}:
            return record
        ledger = EventLedger(run_id=run_id, phase_id=record["phase_id"], clock=self.clock)
        events_path = Path(record["run_root"]) / "events.jsonl"
        if events_path.is_file():
            from .common import load_jsonl
            ledger.events = load_jsonl(events_path)
        ledger.append("STOP_EVENT", candidate_replicate_id=record["run_id"], semantic_role="CONTROL", semantic_call_id="stop", transport_attempt_id="stop", failure_disposition=reason, payload={"code": reason, "message": reason, "details": {}})
        record["status"] = "STOPPED"
        self._persist_run(record, ledger, package=None)
        self.runs[run_id] = record
        return dict(record)

    def artifacts(self, run_id: str) -> dict[str, Any]:
        record = self.get_run(run_id)
        root = Path(record["run_root"])
        result = {"run_id": run_id, "status": record["status"], "artifacts": []}
        for name in ("events.jsonl", "evidence_ledger.json", "attestation_package.json", "run.json"):
            path = root / name
            if path.is_file():
                result["artifacts"].append({"artifact_ref": name, "artifact_sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "byte_count": path.stat().st_size})
        return result

    def replay(self, run_id: str) -> dict[str, Any]:
        record = self.get_run(run_id)
        return replay_run(record["run_root"])

    def handle(self, method: str, path: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Minimal internal routing mirror of the documented endpoint paths."""
        payload = payload or {}
        if method == "POST" and path == "/e/v1/preflight":
            return self.preflight(payload)
        if method == "POST" and path == "/e/v1/runs":
            return self.create_run(payload)
        if method == "POST" and path == "/e/v1/replay":
            return self.replay(str(payload["run_id"]))
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:3] == ["e", "v1", "runs"] and method == "GET":
            return self.get_run(parts[3])
        if len(parts) == 5 and parts[:3] == ["e", "v1", "runs"] and parts[4] == "stop" and method == "POST":
            return self.stop_run(parts[3], reason=str(payload.get("reason", "USER_STOP")))
        if len(parts) == 5 and parts[:3] == ["e", "v1", "runs"] and parts[4] == "artifacts" and method == "GET":
            return self.artifacts(parts[3])
        raise LiveSchemaError("unknown E Live endpoint")

    def _execute(self, request: Mapping[str, Any], record: dict[str, Any], ledger: EventLedger) -> None:
        evidence = extract_snapshot_evidence(
            self.snapshot_root,
            candidate_id=request["candidate_id"],
            sense_id=request["sense_id"],
            term_en=request["term_en"],
            candidate_vi=request["candidate_vi"],
            candidate_variants=request["candidate_variants"],
        )
        snapshot_document_count = int(self.snapshot["document_count"])
        coverage_counts: dict[str, Any] = {
            "search_expected": 0,
            "search_success": 0,
            "search_required": False,
            "fetch_expected": 0,
            "fetch_success": 0,
            "fetch_required": False,
            "extraction_expected": snapshot_document_count,
            "extraction_attempted": snapshot_document_count,
            "extraction_success": snapshot_document_count,
            "language_expected": snapshot_document_count,
            "language_attempted": snapshot_document_count,
            "language_success": snapshot_document_count,
            "span_expected": snapshot_document_count,
            "span_attempted": snapshot_document_count,
            "span_success": len(evidence),
            "judge_expected": 0,
            "judge_attempted": 0,
            "judge_success": 0,
        }
        if not evidence and self.discovery is not None:
            query_cap = min(
                int(request["budget"]["max_queries"]),
                int(self.policy_bundle["retrieval_policy"]["max_queries_per_candidate"]),
                int(self.policy_bundle["query_template_set"]["max_queries"]),
            )
            query_plan = render_query_plan(
                self.policy_bundle["query_template_set"],
                selected_template_ids=list(request["query_template_ids"]),
                request=request,
                max_queries=query_cap,
            )
            coverage_counts["search_expected"] = len(query_plan)
            coverage_counts["search_required"] = True
            leads_by_url: dict[str, dict[str, Any]] = {}
            for query in query_plan:
                query_leads = self.discovery.query(
                    query["rendered_query"],
                    candidate_id=request["candidate_id"],
                    max_queries=query_cap,
                )
                coverage_counts["search_success"] += 1
                ledger.append(
                    "E_DISCOVERY_QUERY",
                    candidate_replicate_id=request["candidate_id"],
                    semantic_role="DISCOVERY",
                    semantic_call_id=query["template_id"],
                    transport_attempt_id=query["rendered_query_sha256"],
                    payload={
                        "template_id": query["template_id"],
                        "query_class": query["query_class"],
                        "template_sha256": query["template_sha256"],
                        "rendered_query": query["rendered_query"],
                        "rendered_query_sha256": query["rendered_query_sha256"],
                        "result_count": len(query_leads),
                        "lead_urls": sorted({str(row["url"]) for row in query_leads}),
                        "is_evidence": False,
                    },
                )
                for lead in query_leads:
                    leads_by_url.setdefault(str(lead["url"]), dict(lead))
            fetch_cap = min(
                int(request["budget"]["max_fetches"]),
                int(self.policy_bundle["retrieval_policy"]["max_direct_fetches"]),
            )
            leads = [leads_by_url[url] for url in sorted(leads_by_url)[:fetch_cap]]
            coverage_counts["fetch_expected"] = len(leads)
            coverage_counts["fetch_required"] = True
            for lead in leads:
                if self.fetcher is None:
                    continue
                fetched = None
                max_attempts = min(
                    int(request["budget"]["max_retries"]) + 1,
                    int(self.policy_bundle["retrieval_policy"]["max_fetch_retries"]) + 1,
                )
                for attempt in range(max_attempts):
                    physical_count = sum(
                        1
                        for event in ledger.events
                        if event["event_kind"] in {"E_DIRECT_FETCH_REQUEST", "E_FETCH_RETRY"}
                    )
                    if physical_count >= int(request["budget"]["max_physical_requests"]):
                        ledger.append("STOP_EVENT", candidate_replicate_id=request["candidate_id"], semantic_role="CONTROL", semantic_call_id=lead["candidate_id"], transport_attempt_id=lead["url"], failure_disposition="BUDGET_EXCEEDED", payload={"code": "PHYSICAL_REQUEST_BUDGET_EXHAUSTED", "message": "physical request budget exhausted", "details": {}})
                        record["status"] = "STOPPED"
                        self._persist_run(record, ledger, package=None)
                        return
                    kind = "E_DIRECT_FETCH_REQUEST" if attempt == 0 else "E_FETCH_RETRY"
                    ledger.append(kind, candidate_replicate_id=request["candidate_id"], semantic_role="FETCH", semantic_call_id=lead["candidate_id"], transport_attempt_id=f"{lead['url']}#{attempt}", retry_of=lead["url"] if attempt else None, payload={"url": lead["url"], "retry_index": attempt})
                    try:
                        fetched = self.fetcher.fetch(lead["url"], retry_index=attempt)
                        break
                    except FixtureTransientFetchError:
                        continue
                    except UnknownPhysicalOutcome as exc:
                        ledger.append("STOP_EVENT", candidate_replicate_id=request["candidate_id"], semantic_role="CONTROL", semantic_call_id=lead["candidate_id"], transport_attempt_id=lead["url"], failure_disposition="UNKNOWN_PHYSICAL_OUTCOME", payload={"code": "UNKNOWN_PHYSICAL_OUTCOME", "message": str(exc), "details": {}})
                        record["status"] = "STOPPED"
                        self._persist_run(record, ledger, package=None)
                        return
                if fetched is None:
                    continue
                metadata = self.fetcher.metadata(lead["url"])
                retrieval_policy = self.policy_bundle["retrieval_policy"]
                if len(fetched.redirect_chain) > int(retrieval_policy["max_redirect_hops"]):
                    self._stop_budget(record, ledger, request, "MAX_REDIRECT_HOPS_EXCEEDED", lead["url"])
                    return
                if len(fetched.body) > int(retrieval_policy["max_download_bytes"]):
                    self._stop_budget(record, ledger, request, "MAX_DOWNLOAD_BYTES_EXCEEDED", lead["url"])
                    return
                coverage_counts["fetch_success"] += 1
                source_id = str(metadata.get("source_id", ""))
                admission = admit_source(
                    self.registry,
                    source_id=source_id,
                    canonical_url=lead["url"],
                    final_url=str(metadata.get("final_url", lead["url"])),
                    content_type=fetched.content_type,
                    redirect_chain=fetched.redirect_chain,
                )
                if fetched.redirect_chain:
                    for hop in fetched.redirect_chain:
                        ledger.append("E_REDIRECT_HOP", candidate_replicate_id=request["candidate_id"], semantic_role="FETCH", semantic_call_id=lead["candidate_id"], transport_attempt_id=lead["url"], payload={"url": hop})
                coverage_counts["extraction_expected"] += 1
                coverage_counts["extraction_attempted"] += 1
                try:
                    fetched_rows = extract_fetched_evidence(
                        fetched,
                        source_id=source_id,
                        source_tier=admission["source_tier"],
                        source_type=admission["source_type"],
                        candidate_id=request["candidate_id"],
                        sense_id=request["sense_id"],
                        term_en=request["term_en"],
                        candidate_vi=request["candidate_vi"],
                        candidate_variants=request["candidate_variants"],
                    )
                except LiveSchemaError:
                    continue
                coverage_counts["extraction_success"] += 1
                coverage_counts["language_expected"] += 1
                coverage_counts["language_attempted"] += 1
                coverage_counts["language_success"] += 1
                coverage_counts["span_expected"] += 1
                coverage_counts["span_attempted"] += 1
                coverage_counts["span_success"] += len(fetched_rows)
                raw_document_ref = f"raw_documents/{fetched.content_sha256}.bin"
                raw_document_path = Path(record["run_root"]).joinpath(*raw_document_ref.split("/"))
                raw_document_path.parent.mkdir(parents=True, exist_ok=True)
                raw_document_path.write_bytes(fetched.body)
                for fetched_row in fetched_rows:
                    fetched_row["document_ref"] = raw_document_ref
                evidence.extend(fetched_rows)
        all_evidence, evidence = cluster_global_evidence(evidence)
        accepted_document_count = len({str(row["document_id"]) for row in all_evidence})
        if accepted_document_count > int(self.policy_bundle["retrieval_policy"]["max_accepted_documents"]):
            self._stop_budget(record, ledger, request, "MAX_ACCEPTED_DOCUMENTS_EXCEEDED", "accepted_documents")
            return
        judge_rows: dict[str, dict[str, Any]] = {}
        judge_attempts: list[dict[str, Any]] = []
        role_counts: dict[str, dict[str, int]] = {}
        roles = provider_roles_by_name(self.policy_bundle["provider_role_plan"])
        primary_role = "PRIMARY_ATTESTATION_JUDGE"
        secondary_role = "SECONDARY_ATTESTATION_JUDGE"
        if primary_role not in roles or secondary_role not in roles:
            raise LiveSchemaError("provider role plan must define Primary and Secondary")
        secondary_conditions = set(self.policy_bundle["provider_role_plan"]["secondary_condition"])
        coverage_counts["judge_expected"] = len(evidence)
        if len(evidence) > int(request["budget"]["max_semantic_calls"]):
            record["status"] = "STOPPED"
            ledger.append("STOP_EVENT", candidate_replicate_id=request["candidate_id"], semantic_role="CONTROL", semantic_call_id="budget", transport_attempt_id="budget", failure_disposition="BUDGET_EXCEEDED", payload={"code": "SEMANTIC_CALL_BUDGET_EXHAUSTED", "message": "semantic call budget exhausted", "details": {"required_semantic_calls": len(evidence), "max_semantic_calls": request["budget"]["max_semantic_calls"]}})
            self._persist_run(record, ledger, package=None)
            return
        for row in all_evidence:
            ledger.append("E_SOURCE_DOCUMENT_ACCEPTED", candidate_replicate_id=request["candidate_id"], semantic_role="CORPUS", semantic_call_id=row["evidence_id"], transport_attempt_id=row["document_id"], payload={"document_id": row["document_id"], "source_id": row["source_id"], "content_sha256": row["content_sha256"], "document_ref": row["document_ref"], "snapshot_manifest_sha256": row["snapshot_manifest_sha256"]})
        for row in evidence:
            if self.execution_mode == "LOCAL_FIXTURE_ONLY" and self.judge is None:
                raise LiveSchemaError("fixture Judge is required for a local run")
            try:
                response = self._invoke_judge(
                    request=request,
                    evidence=row,
                    role=primary_role,
                    role_config=roles[primary_role],
                    role_counts=role_counts,
                    judge_attempts=judge_attempts,
                    ledger=ledger,
                )
                if (
                    response["concept_relation"] == "UNCERTAIN"
                    and "PRIMARY_CONCEPT_UNCERTAIN" in secondary_conditions
                ):
                    response = self._invoke_judge(
                        request=request,
                        evidence=row,
                        role=secondary_role,
                        role_config=roles[secondary_role],
                        role_counts=role_counts,
                        judge_attempts=judge_attempts,
                        ledger=ledger,
                    )
            except ProviderUnknownPhysicalOutcome as exc:
                ledger.append("STOP_EVENT", candidate_replicate_id=request["candidate_id"], semantic_role="CONTROL", semantic_call_id=row["evidence_id"], transport_attempt_id=row["evidence_id"], failure_disposition="UNKNOWN_PHYSICAL_OUTCOME", payload={"code": "UNKNOWN_PHYSICAL_OUTCOME", "message": str(exc), "details": {}})
                record["status"] = "STOPPED"
                self._apply_telemetry(record, ledger)
                self._persist_run(record, ledger, package=None)
                return
            except Exception as exc:
                ledger.append("STOP_EVENT", candidate_replicate_id=request["candidate_id"], semantic_role="CONTROL", semantic_call_id=row["evidence_id"], transport_attempt_id=row["evidence_id"], failure_disposition="MALFORMED_E_MODEL_RESPONSE", payload={"code": "MALFORMED_E_MODEL_RESPONSE", "message": str(exc), "details": {}})
                record["status"] = "STOPPED"
                self._apply_telemetry(record, ledger)
                self._persist_run(record, ledger, package=None)
                return
            judge_rows[row["evidence_id"]] = response
        positive_clusters = {
            str(row["duplicate_cluster_id"])
            for row in evidence
            if positive_evidence_eligible(judge_rows[row["evidence_id"]])
        }
        contradictory_clusters = {
            str(row["duplicate_cluster_id"])
            for row in evidence
            if contradictory_evidence_eligible(judge_rows[row["evidence_id"]])
        }
        if positive_clusters and contradictory_clusters and "INDEPENDENT_CLUSTER_CONFLICT" in secondary_conditions:
            for row in evidence:
                if str(row["duplicate_cluster_id"]) not in positive_clusters | contradictory_clusters:
                    continue
                try:
                    judge_rows[row["evidence_id"]] = self._invoke_judge(
                        request=request,
                        evidence=row,
                        role=secondary_role,
                        role_config=roles[secondary_role],
                        role_counts=role_counts,
                        judge_attempts=judge_attempts,
                        ledger=ledger,
                    )
                except ProviderUnknownPhysicalOutcome as exc:
                    ledger.append("STOP_EVENT", candidate_replicate_id=request["candidate_id"], semantic_role="CONTROL", semantic_call_id=row["evidence_id"], transport_attempt_id=row["evidence_id"], failure_disposition="UNKNOWN_PHYSICAL_OUTCOME", payload={"code": "UNKNOWN_PHYSICAL_OUTCOME", "message": str(exc), "details": {}})
                    record["status"] = "STOPPED"
                    self._apply_telemetry(record, ledger)
                    self._persist_run(record, ledger, package=None)
                    return
                except Exception as exc:
                    ledger.append("STOP_EVENT", candidate_replicate_id=request["candidate_id"], semantic_role="CONTROL", semantic_call_id=row["evidence_id"], transport_attempt_id=row["evidence_id"], failure_disposition="MALFORMED_E_MODEL_RESPONSE", payload={"code": "MALFORMED_E_MODEL_RESPONSE", "message": str(exc), "details": {}})
                    record["status"] = "STOPPED"
                    self._apply_telemetry(record, ledger)
                    self._persist_run(record, ledger, package=None)
                    return
        coverage_counts["judge_attempted"] = len(judge_rows)
        coverage_counts["judge_success"] = len(judge_rows)
        coverage = derive_coverage_from_ledger(ledger.events, counts=coverage_counts)
        aggregation = aggregate_candidate(
            evidence,
            judge_rows,
            policy=self.policy_bundle["aggregation_policy"],
            expected_evidence_count=coverage_counts["span_expected"],
            coverage=coverage,
        )
        telemetry = summarize_provider_telemetry(ledger.events)
        evidence_ledger = seal({"schema_id": "EEvidenceLedgerV1", "schema_version": LIVE_TOOL_SCHEMA_VERSION, "run_id": request["run_id"], "run_spec_id": request["run_spec_id"], "all_evidence_rows": all_evidence, "evidence_rows": evidence, "judge_rows": judge_rows, "judge_attempts": judge_attempts, "coverage": coverage, "aggregation": aggregation, **telemetry, "integrity": {}})
        evidence_ledger_path = Path(record["run_root"]) / "evidence_ledger.json"
        evidence_ledger_path.write_bytes(canonical_bytes(evidence_ledger))
        evidence_ledger_sha = hashlib.sha256(evidence_ledger_path.read_bytes()).hexdigest()
        completed_at = self.clock()
        package = build_attestation_package(request=request, aggregation=aggregation, snapshot_manifest_sha256=self.snapshot["integrity"]["self_sha256"], ledger_refs={"artifact_ref": "evidence_ledger.json", "artifact_sha256": evidence_ledger_sha, "event_count": len(ledger.events)}, authority_refs=request["authority_refs"], run_spec_id=request["run_spec_id"], started_at=record["started_at"], completed_at=completed_at, provider_role_plan_sha256=request["provider_role_plan_sha256"], provider_role_plan=self.policy_bundle["provider_role_plan"])
        record["status"] = "COMPLETED"
        record["completed_at"] = completed_at
        record["event_count"] = len(ledger.events)
        record["local_status"] = aggregation["status"]
        record["coverage"] = coverage
        record["package"] = package
        self._apply_telemetry(record, ledger)
        self._persist_run(record, ledger, package=package)

    def _invoke_judge(
        self,
        *,
        request: Mapping[str, Any],
        evidence: Mapping[str, Any],
        role: str,
        role_config: Mapping[str, Any],
        role_counts: dict[str, dict[str, int]],
        judge_attempts: list[dict[str, Any]],
        ledger: EventLedger,
    ) -> dict[str, Any]:
        if role_config["semantic_role"] != role:
            raise LiveSchemaError("provider role identity mismatch")
        if self.execution_mode == "LOCAL_FIXTURE_ONLY" and role_config["mode"] != "ZERO_PROVIDER_FIXTURE":
            raise LiveSchemaError("zero-provider execution refuses the selected provider role")
        if self.execution_mode == "PRODUCTION_AUTHORITY" and role_config["mode"] != "LIVE_PROVIDER":
            raise LiveSchemaError("production execution requires LIVE_PROVIDER role")
        counts = role_counts.setdefault(role, {"semantic": 0, "physical": 0})
        if counts["semantic"] >= int(role_config["max_semantic_calls"]) or counts["physical"] >= int(role_config["max_physical_requests"]):
            raise LiveSchemaError(f"provider role cap exceeded: {role}")
        total_calls = sum(item["semantic"] for item in role_counts.values())
        if total_calls >= int(request["budget"]["max_semantic_calls"]):
            raise LiveSchemaError("global semantic call budget exceeded")
        judge_request = make_judge_request(
            candidate_id=request["candidate_id"],
            sense_id=request["sense_id"],
            evidence_id=evidence["evidence_id"],
            term_en=request["term_en"],
            candidate_vi=request["candidate_vi"],
            sense_definition=request["sense_definition"],
            snippet_original=evidence["snippet_original"],
            snippet_masked=evidence["snippet_masked"],
            source_id=evidence["source_id"],
            source_tier=evidence["source_tier"],
            semantic_role=role,
        )
        if self.execution_mode == "PRODUCTION_AUTHORITY":
            return self._invoke_production_judge(
                request=request, evidence=evidence, role=role, role_config=role_config,
                role_counts=role_counts, judge_attempts=judge_attempts, ledger=ledger,
                judge_request=judge_request,
            )
        counts["semantic"] += 1
        counts["physical"] += 1
        if self.judge is None:
            raise LiveSchemaError("fixture Judge is required")
        response = self.judge.judge(judge_request, role=role)
        response_sha = canonical_sha256(response)
        raw_ref = f"raw_responses/{response_sha}.json"
        raw_path = Path(self.runs[request["run_id"]]["run_root"]).joinpath(*raw_ref.split("/"))
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(canonical_bytes(response))
        provider_request_id = f"fixture-{role.casefold()}-{evidence['evidence_id']}-{counts['physical']}"
        ledger.append_model_request(
            candidate_id=request["candidate_id"],
            sense_id=request["sense_id"],
            semantic_call_id=evidence["evidence_id"],
            provider_request_id=provider_request_id,
            provider_id=str(role_config["provider_id"]),
            model_id=str(role_config["model_id"]),
            route=role,
            prompt_sha256=str(role_config["prompt_sha256"]),
            request_sha256=judge_request_sha256(judge_request),
            response_sha256=response_sha,
            raw_response_locator=raw_ref,
            generation_config=role_config["generation_config"],
            provider_role_plan_sha256=request["provider_role_plan_sha256"],
            usage={"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0, "cost": 0.0, "currency": "USD"},
        )
        judge_attempts.append(
            {
                "evidence_id": evidence["evidence_id"],
                "semantic_role": role,
                "provider_id": role_config["provider_id"],
                "model_id": role_config["model_id"],
                "prompt_sha256": role_config["prompt_sha256"],
                "request_sha256": judge_request_sha256(judge_request),
                "response_sha256": response_sha,
                "raw_response_locator": raw_ref,
            }
        )
        return response

    def _invoke_production_judge(
        self, *, request: Mapping[str, Any], evidence: Mapping[str, Any], role: str,
        role_config: Mapping[str, Any], role_counts: dict[str, dict[str, int]],
        judge_attempts: list[dict[str, Any]], ledger: EventLedger,
        judge_request: Mapping[str, Any],
    ) -> dict[str, Any]:
        if self.provider_adapter is None:
            raise LiveSchemaError("provider adapter is unavailable")
        counts = role_counts[role]
        counts["semantic"] += 1
        request_sha = judge_request_sha256(judge_request)
        max_attempts = int(role_config["max_retries"]) + 1
        for retry_index in range(max_attempts):
            if counts["physical"] >= int(role_config["max_physical_requests"]):
                raise LiveSchemaError(f"provider physical request cap exceeded: {role}")
            if sum(item["physical"] for item in role_counts.values()) >= int(request["budget"]["max_physical_requests"]):
                raise LiveSchemaError("global physical request budget exceeded")
            result = validate_provider_transport_result(
                self.provider_adapter.invoke(judge_request, role_config=role_config),
                request_sha256=request_sha,
            )
            if result["retry_index"] != retry_index:
                raise LiveSchemaError("provider transport retry index mismatch")
            counts["physical"] += result["physical_request_count"]
            response = result["response"]
            raw = response
            raw_ref = f"raw_responses/{result['response_physical_sha256']}.json"
            raw_path = Path(self.runs[request["run_id"]]["run_root"]).joinpath(*raw_ref.split("/"))
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(canonical_bytes(raw))
            usage = {key: result[key] for key in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "cost", "currency")}
            ledger.append_model_request(
                candidate_id=request["candidate_id"], sense_id=request["sense_id"],
                semantic_call_id=evidence["evidence_id"], provider_request_id=result["provider_request_id"],
                provider_id=str(role_config["provider_id"]), model_id=str(role_config["model_id"]), route=role,
                prompt_sha256=str(role_config["prompt_sha256"]), request_sha256=request_sha,
                response_sha256=result["response_canonical_sha256"], response_physical_sha256=result["response_physical_sha256"],
                raw_response_locator=raw_ref, generation_config=role_config["generation_config"],
                provider_role_plan_sha256=request["provider_role_plan_sha256"], retry_index=retry_index,
                outcome=result["outcome"], latency_ms=result["latency_ms"], physical_request_count=result["physical_request_count"],
                started_at=result["started_at"], completed_at=result["completed_at"], usage=usage,
                failure_disposition="NONE" if result["outcome"] == "SUCCESS" else result["outcome"],
            )
            judge_attempts.append({**dict(result), "evidence_id": evidence["evidence_id"], "semantic_role": role,
                                   "provider_id": role_config["provider_id"], "model_id": role_config["model_id"],
                                   "prompt_sha256": role_config["prompt_sha256"], "raw_response_locator": raw_ref})
            if result["outcome"] == "SUCCESS":
                return dict(response)
            if result["outcome"] == "UNKNOWN_PHYSICAL_OUTCOME":
                raise ProviderUnknownPhysicalOutcome(result["provider_request_id"])
            if result["outcome"] == "TERMINAL_FAILURE":
                raise LiveSchemaError("provider terminal failure")
        raise LiveSchemaError("provider retry budget exhausted")

    def _apply_telemetry(self, record: dict[str, Any], ledger: EventLedger) -> None:
        record.update(summarize_provider_telemetry(ledger.events))

    def _stop_budget(
        self,
        record: dict[str, Any],
        ledger: EventLedger,
        request: Mapping[str, Any],
        code: str,
        transport_attempt_id: str,
    ) -> None:
        ledger.append(
            "STOP_EVENT",
            candidate_replicate_id=request["candidate_id"],
            semantic_role="CONTROL",
            semantic_call_id="retrieval_budget",
            transport_attempt_id=transport_attempt_id,
            failure_disposition="BUDGET_EXCEEDED",
            payload={"code": code, "message": code, "details": {}},
        )
        record["status"] = "STOPPED"
        self._persist_run(record, ledger, package=None)

    def _persist_run(self, record: dict[str, Any], ledger: EventLedger, package: Mapping[str, Any] | None) -> None:
        root = Path(record["run_root"])
        root.mkdir(parents=True, exist_ok=True)
        events_path = root / "events.jsonl"
        ledger.write_jsonl(events_path)
        record["events_sha256"] = hashlib.sha256(events_path.read_bytes()).hexdigest()
        if package is not None:
            package_path = root / "attestation_package.json"
            package_path.write_bytes(canonical_bytes(package))
            record["package_sha256"] = hashlib.sha256(package_path.read_bytes()).hexdigest()
        # Keep the run root as an explicit local artifact binding so a fresh
        # process can serve GET/artifacts/replay without reconstructing state.
        run_copy = dict(record)
        (root / "run.json").write_bytes(canonical_bytes(run_copy))
        self.runs[record["run_id"]] = dict(record)


def summarize_provider_telemetry(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    model_events = [
        row for row in events
        if row.get("event_kind") == "E_MODEL_REQUEST"
        and not str(row.get("payload", {}).get("provider_request_id", "")).startswith("fixture-")
    ]
    physical_requests = sum(int(row["payload"]["physical_request_count"]) for row in model_events)
    return {
        "provider_calls": physical_requests,
        "network_calls": physical_requests,
        "physical_requests": physical_requests,
        "retry_count": sum(1 for row in model_events if int(row["payload"]["retry_index"]) > 0),
        "input_tokens": sum(int(row["usage"]["input_tokens"]) for row in model_events),
        "output_tokens": sum(int(row["usage"]["output_tokens"]) for row in model_events),
        "reasoning_tokens": sum(int(row["usage"]["reasoning_tokens"]) for row in model_events),
        "total_tokens": sum(int(row["usage"]["total_tokens"]) for row in model_events),
        "total_cost": sum(float(row["usage"]["cost"]) for row in model_events),
        "currency": model_events[0]["usage"]["currency"] if model_events else "USD",
        "latency_total_ms": sum(int(row["payload"]["latency_ms"]) for row in model_events),
        "latency_measurements": [int(row["payload"]["latency_ms"]) for row in model_events],
    }


__all__ = ["AUTHORIZATION_SCHEMA_ID", "ELiveService", "RUN_SCHEMA_ID", "RunBlocked", "make_authorization_receipt", "make_run_request", "summarize_provider_telemetry", "validate_authorization_receipt"]
