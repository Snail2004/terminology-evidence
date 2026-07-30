"""Transport-independent E Live API service, restricted to local fixtures."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .aggregation import aggregate_candidate, build_attestation_package
from .common import (
    LIVE_TOOL_SCHEMA_VERSION,
    LiveSchemaError,
    canonical_bytes,
    canonical_sha256,
    load_object,
    require_keys,
    require_sha256,
    require_string,
    seal,
    utc_now,
    verify_seal,
)
from .judge import FixtureJudge, judge_request_sha256, make_judge_request
from .ledger import EventLedger
from .policies import validate_policy_bundle
from .registry import admit_source, validate_registry
from .replay import replay_run
from .retrieval import (
    FixtureDiscovery,
    FixtureFetcher,
    FixtureTransientFetchError,
    UnknownPhysicalOutcome,
    extract_fetched_evidence,
    extract_snapshot_evidence,
)
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
        self.authorization_receipt = dict(authorization_receipt)
        if self.authorization_receipt.get("schema_id") != AUTHORIZATION_SCHEMA_ID or not verify_seal(self.authorization_receipt):
            raise LiveSchemaError("authorization receipt is invalid")
        if self.authorization_receipt.get("authorization_status") != "CONTROLLED_LOCAL_FIXTURE_ONLY":
            raise LiveSchemaError("authorization receipt is not a local controlled canary receipt")
        if self.authorization_receipt.get("provider_calls_allowed") != 0 or self.authorization_receipt.get("network_calls_allowed") != 0:
            raise LiveSchemaError("zero-provider authorization receipt permits external calls")
        self.authorized_cohort_id = authorized_cohort_id
        self.authorized_candidate_ids = frozenset(str(item) for item in authorized_candidate_ids)
        self.credentials_ready = bool(credentials_ready)
        self.discovery = discovery
        self.fetcher = fetcher
        self.judge = judge
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
        if not verify_seal(receipt) or receipt.get("cohort_id") != self.authorized_cohort_id or set(receipt.get("candidate_ids", ())) != set(self.authorized_candidate_ids):
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
        except Exception as exc:
            current_policy_hashes = self.policy_hashes
            blockers.append("POLICY_BUNDLE_INVALID")
            checks["policy_bundle"] = f"FAIL:{type(exc).__name__}"
        if receipt.get("registry_self_sha256") != current_registry["integrity"]["self_sha256"] or receipt.get("snapshot_manifest_sha256") != current_snapshot["integrity"]["self_sha256"]:
            blockers.append("AUTHORITY_BINDING_MISMATCH")
        if dict(receipt.get("policy_hashes", {})) != current_policy_hashes:
            blockers.append("AUTHORITY_POLICY_BINDING_MISMATCH")
        checks["authorization_receipt"] = "PASS" if "AUTHORIZATION_RECEIPT_MISMATCH" not in blockers else "FAIL"
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
                ledger.append("STOP_EVENT", candidate_replicate_id=checked["candidate_id"], semantic_role="CONTROL", semantic_call_id="exception", transport_attempt_id="exception", failure_disposition=type(exc).__name__, payload={"error": str(exc)})
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
        ledger.append("STOP_EVENT", candidate_replicate_id=record["run_id"], semantic_role="CONTROL", semantic_call_id="stop", transport_attempt_id="stop", failure_disposition=reason, payload={"reason": reason})
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
        if not evidence and self.discovery is not None:
            query_cap = min(
                int(request["budget"]["max_queries"]),
                int(self.policy_bundle["retrieval_policy"]["max_queries_per_candidate"]),
                int(self.policy_bundle["query_template_set"]["max_queries"]),
            )
            leads = self.discovery.query(f'"{request["candidate_vi"]}"', candidate_id=request["candidate_id"], max_queries=query_cap)
            fetch_cap = min(
                int(request["budget"]["max_fetches"]),
                int(self.policy_bundle["retrieval_policy"]["max_direct_fetches"]),
            )
            for lead in leads[:fetch_cap]:
                ledger.append("E_DISCOVERY_QUERY", candidate_replicate_id=request["candidate_id"], semantic_role="DISCOVERY", semantic_call_id=lead["candidate_id"], transport_attempt_id=lead["url"], payload={"lead_url": lead["url"], "is_evidence": False, "query_text": lead["query_text"]})
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
                        ledger.append("STOP_EVENT", candidate_replicate_id=request["candidate_id"], semantic_role="CONTROL", semantic_call_id=lead["candidate_id"], transport_attempt_id=lead["url"], failure_disposition="BUDGET_EXCEEDED", payload={"reason": "physical request budget exhausted"})
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
                        ledger.append("STOP_EVENT", candidate_replicate_id=request["candidate_id"], semantic_role="CONTROL", semantic_call_id=lead["candidate_id"], transport_attempt_id=lead["url"], failure_disposition="UNKNOWN_PHYSICAL_OUTCOME", payload={"error": str(exc)})
                        record["status"] = "STOPPED"
                        self._persist_run(record, ledger, package=None)
                        return
                if fetched is None:
                    continue
                metadata = self.fetcher.metadata(lead["url"])
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
                raw_document_ref = f"raw_documents/{fetched.content_sha256}.bin"
                raw_document_path = Path(record["run_root"]).joinpath(*raw_document_ref.split("/"))
                raw_document_path.parent.mkdir(parents=True, exist_ok=True)
                raw_document_path.write_bytes(fetched.body)
                for fetched_row in fetched_rows:
                    fetched_row["document_ref"] = raw_document_ref
                evidence.extend(fetched_rows)
        if not evidence:
            record["status"] = "STOPPED"
            ledger.append("STOP_EVENT", candidate_replicate_id=request["candidate_id"], semantic_role="CONTROL", semantic_call_id="coverage", transport_attempt_id="coverage", failure_disposition="ATTESTATION_UNJUDGEABLE", payload={"reason": "no frozen corpus evidence"})
            self._persist_run(record, ledger, package=None)
            return
        judge_rows: dict[str, dict[str, Any]] = {}
        if len(evidence) > int(request["budget"]["max_semantic_calls"]):
            record["status"] = "STOPPED"
            ledger.append("STOP_EVENT", candidate_replicate_id=request["candidate_id"], semantic_role="CONTROL", semantic_call_id="budget", transport_attempt_id="budget", failure_disposition="BUDGET_EXCEEDED", payload={"required_semantic_calls": len(evidence), "max_semantic_calls": request["budget"]["max_semantic_calls"]})
            self._persist_run(record, ledger, package=None)
            return
        for row in evidence:
            ledger.append("E_SOURCE_DOCUMENT_ACCEPTED", candidate_replicate_id=request["candidate_id"], semantic_role="CORPUS", semantic_call_id=row["evidence_id"], transport_attempt_id=row["document_id"], payload={"document_id": row["document_id"], "source_id": row["source_id"], "content_sha256": row["content_sha256"], "document_ref": row["document_ref"], "snapshot_manifest_sha256": row["snapshot_manifest_sha256"]})
            if self.judge is None:
                raise LiveSchemaError("fixture Judge is required for a local run")
            judge_request = make_judge_request(candidate_id=request["candidate_id"], sense_id=request["sense_id"], evidence_id=row["evidence_id"], term_en=request["term_en"], candidate_vi=request["candidate_vi"], sense_definition=request["sense_definition"], snippet_original=row["snippet_original"], snippet_masked=row["snippet_masked"], source_id=row["source_id"], source_tier=row["source_tier"])
            try:
                role, response = self.judge.route(judge_request)
            except Exception as exc:
                ledger.append("STOP_EVENT", candidate_replicate_id=request["candidate_id"], semantic_role="CONTROL", semantic_call_id=row["evidence_id"], transport_attempt_id=row["evidence_id"], failure_disposition="MALFORMED_E_MODEL_RESPONSE", payload={"error": str(exc)})
                record["status"] = "STOPPED"
                self._persist_run(record, ledger, package=None)
                return
            judge_rows[row["evidence_id"]] = response
            response_sha = canonical_sha256(response)
            raw_ref = f"raw_responses/{response_sha}.json"
            raw_path = Path(record["run_root"]).joinpath(*raw_ref.split("/"))
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            raw_path.write_bytes(canonical_bytes(response))
            ledger.append_model_request(candidate_id=request["candidate_id"], sense_id=request["sense_id"], semantic_call_id=row["evidence_id"], provider_request_id="fixture-" + row["evidence_id"], provider_id="ZERO_PROVIDER_FIXTURE", model_id="fixture-judge-v1", route=role, prompt_sha256=canonical_sha256(judge_request), request_sha256=judge_request_sha256(judge_request), response_sha256=response_sha, raw_response_locator=raw_ref, usage={"input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0, "cost": 0.0, "currency": "USD"})
        aggregation = aggregate_candidate(evidence, judge_rows, policy=self.policy_bundle["aggregation_policy"], coverage_fraction=1.0)
        evidence_ledger = seal({"schema_id": "EEvidenceLedgerV1", "schema_version": LIVE_TOOL_SCHEMA_VERSION, "run_id": request["run_id"], "run_spec_id": request["run_spec_id"], "evidence_rows": evidence, "judge_rows": judge_rows, "aggregation": aggregation, "provider_calls": 0, "network_calls": 0, "integrity": {}})
        evidence_ledger_path = Path(record["run_root"]) / "evidence_ledger.json"
        evidence_ledger_path.write_bytes(canonical_bytes(evidence_ledger))
        evidence_ledger_sha = hashlib.sha256(evidence_ledger_path.read_bytes()).hexdigest()
        completed_at = self.clock()
        package = build_attestation_package(request=request, aggregation=aggregation, snapshot_manifest_sha256=self.snapshot["integrity"]["self_sha256"], ledger_refs={"artifact_ref": "evidence_ledger.json", "artifact_sha256": evidence_ledger_sha, "event_count": len(ledger.events)}, authority_refs=request["authority_refs"], run_spec_id=request["run_spec_id"], started_at=record["started_at"], completed_at=completed_at, provider_role_plan_sha256=request["provider_role_plan_sha256"])
        record["status"] = "COMPLETED"
        record["completed_at"] = completed_at
        record["event_count"] = len(ledger.events)
        record["local_status"] = aggregation["status"]
        record["package"] = package
        self._persist_run(record, ledger, package=package)

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


__all__ = ["AUTHORIZATION_SCHEMA_ID", "ELiveService", "RUN_SCHEMA_ID", "RunBlocked", "make_authorization_receipt", "make_run_request"]
