"""Real-pilot orchestration for deterministic zero-network Evidence E."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..contracts.output import validate_attestation_package
from ..dataset.adapter import adapt_dataset_zip
from .artifacts import (
    aggregate_attempts,
    artifact_manifest,
    collect_raw_responses,
    file_sha256,
    projection_report,
    self_sha256,
    verify_replay,
    write_json,
    write_jsonl,
)
from .controlled_registry import inspect_controlled_registry
from .fixtures import (
    SCENARIOS,
    build_internal_candidate,
    build_scenario_engine,
)


ZERO_API_SUMMARY_SCHEMA_ID = "VietnameseAttestationZeroApiPilotSummaryV1"
ZERO_API_SUMMARY_SCHEMA_VERSION = "1.0.0"
ZERO_API_POLICY_ID = "vietnamese_attestation_zero_api_pilot_v1"


def run_zero_api_pilot(
    *,
    source_zip: str | Path,
    parent_v3_zip: str | Path,
    output_root: str | Path,
    controlled_registry: str | Path | None = None,
) -> dict[str, Any]:
    """Run all 15 development candidates without network/provider access."""

    root = Path(output_root).resolve()
    if root.exists() and any(root.iterdir()):
        raise ValueError("zero-API output root must be absent or empty")
    root.mkdir(parents=True, exist_ok=True)
    adapter = adapt_dataset_zip(
        source_zip,
        parent_v3_zip=parent_v3_zip,
    )
    if adapter["mode"] != "DEVELOPMENT_ZERO_API":
        raise ValueError("zero-API pilot requires DEVELOPMENT_ZERO_API input")
    candidates = adapter["candidates"]
    if len(candidates) != len(SCENARIOS):
        raise ValueError("zero-API pilot requires exactly 15 candidates")
    write_json(root / "adapter-package.json", adapter)

    result_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    for index, (raw_candidate, scenario) in enumerate(
        zip(candidates, SCENARIOS, strict=True)
    ):
        candidate = build_internal_candidate(raw_candidate)
        engine = build_scenario_engine(
            candidate=candidate,
            scenario=scenario,
            index=index,
            audit_root=root,
        )
        package = validate_attestation_package(engine.run(candidate))
        if package["final_glossary_decision"] is not None:
            raise RuntimeError("zero-API package emitted a final decision")
        candidate_id = package["candidate_id"]
        package_path = root / "packages" / f"{candidate_id}.json"
        write_json(package_path, package)
        execution_id = package["provenance"]["attestation_execution_id"]
        run_root = root / "runs" / execution_id
        write_json(run_root / "package.json", package)
        replay = verify_replay(run_root / "run_manifest.json")
        replay_rows.append(replay)
        result_rows.append(
            {
                "candidate_id": candidate_id,
                "candidate_version": package["candidate_version"],
                "sense_id": package["sense_id"],
                "scope_id": package["scope_id"],
                "scenario": scenario,
                "local_status": package["attestation_evidence"]["status"],
                "flags": package["attestation_evidence"]["flags"],
                "accepted_evidence_count": len(package["accepted_evidence"]),
                "rejected_evidence_count": len(package["rejected_evidence"]),
                "execution_id": execution_id,
                "started_at": package["provenance"]["started_at"],
                "completed_at": package["provenance"]["completed_at"],
                "package_ref": package_path.relative_to(root).as_posix(),
                "package_sha256": file_sha256(package_path),
                "audit_manifest_sha256": package["audit"]["manifest_sha256"],
                "replay_status": replay["status"],
                "final_glossary_decision": None,
            }
        )

    attempts = aggregate_attempts(root, result_rows)
    write_jsonl(root / "provider_attempts.jsonl", attempts)
    raw_response_count = collect_raw_responses(root, result_rows)
    replay_report = {
        "schema_id": "VietnameseAttestationZeroApiReplayReportV1",
        "schema_version": "1.0.0",
        "run_count": len(replay_rows),
        "all_content_verified": all(
            row["status"] == "PASS" for row in replay_rows
        ),
        "runs": replay_rows,
        "provider_call_count": 0,
    }
    write_json(root / "replay_report.json", replay_report)

    controlled_report = (
        inspect_controlled_registry(controlled_registry)
        if controlled_registry is not None
        else {
            "schema_id": "ControlledVietnameseRegistryInspectionV1",
            "schema_version": "1.0.0",
            "status": "NOT_SUPPLIED",
            "row_count": 0,
            "blockers": ["CONTROLLED_REGISTRY_NOT_SUPPLIED"],
            "retrieval_provider_created": False,
            "provider_call_count": 0,
        }
    )
    write_json(
        root / "controlled_corpus_adapter_report.json",
        controlled_report,
    )
    contract_report = projection_report(adapter)
    write_json(root / "contract_projection_report.json", contract_report)
    write_json(
        root / "provider_canary_report.json",
        {
            "schema_id": "VietnameseAttestationProviderCanaryReportV1",
            "schema_version": "1.0.0",
            "status": "HOLD_NOT_RUN_ZERO_API_PHASE",
            "routes": ["brave", "shopai", "ckey", "gemini_official"],
            "external_provider_call_count": 0,
        },
    )

    status_counts: dict[str, int] = {}
    for row in result_rows:
        status = row["local_status"]
        status_counts[status] = status_counts.get(status, 0) + 1
    summary = {
        "schema_id": ZERO_API_SUMMARY_SCHEMA_ID,
        "schema_version": ZERO_API_SUMMARY_SCHEMA_VERSION,
        "policy_id": ZERO_API_POLICY_ID,
        "mode": adapter["mode"],
        "source_manifest_sha256": adapter["source"]["manifest_sha256"],
        "parent_dataset_manifest_sha256": adapter["source"][
            "parent_dataset_manifest_sha256"
        ],
        "candidate_count": len(result_rows),
        "scenario_count": len(SCENARIOS),
        "scenario_coverage": list(SCENARIOS),
        "status_counts": dict(sorted(status_counts.items())),
        "run_results": result_rows,
        "audit_manifest_count": len(result_rows),
        "replay_pass_count": sum(
            row["status"] == "PASS" for row in replay_rows
        ),
        "fixture_provider_attempt_count": len(attempts),
        "raw_response_count": raw_response_count,
        "external_provider_call_count": 0,
        "contract_projection_status": contract_report["status"],
        "controlled_corpus_status": controlled_report["status"],
        "final_glossary_decision": None,
        "integrity": {"self_sha256": "0" * 64},
    }
    summary["integrity"]["self_sha256"] = self_sha256(summary)
    write_json(root / "pilot_zero_api_summary.json", summary)
    write_json(
        root / "zero_api_artifact_manifest.json",
        artifact_manifest(root),
    )
    return summary


__all__ = [
    "SCENARIOS",
    "ZERO_API_POLICY_ID",
    "ZERO_API_SUMMARY_SCHEMA_ID",
    "ZERO_API_SUMMARY_SCHEMA_VERSION",
    "run_zero_api_pilot",
]
