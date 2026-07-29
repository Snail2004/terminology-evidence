from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from context_substitution.v2.integration.common import seal_object, write_json
from context_substitution.v2.integration.fake_provider import run_fake_provider_pilot
from context_substitution.v2.integration.official_dataset import (
    load_official_dataset_pilot,
)
from context_substitution.v2.integration.official_dataset_projection import (
    build_official_dataset_inputs,
)
from context_substitution.v2.integration.projection import (
    build_projection_binding_from_ledger,
    write_context_evidence_package_set,
)
from context_substitution.v2.integration.replay import replay_context_run


OFFICIAL_PILOT_REPORT_SCHEMA_ID = "D2LOfficial5SenseCZeroProviderReportV1"
OFFICIAL_PILOT_REPORT_SCHEMA_VERSION = "1.0.0"


def run_official_zero_provider_pilot(
    *,
    dataset_zip: Path,
    dataset_pin: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    """Create exactly 15 C packages without a network/provider call."""

    target = Path(evidence_root).resolve()
    if target.exists() and any(target.iterdir()):
        raise ValueError("official C evidence directory must be empty")
    target.mkdir(parents=True, exist_ok=True)

    pilot = load_official_dataset_pilot(dataset_zip, dataset_pin)
    projected = build_official_dataset_inputs(pilot)
    input_payload = projected["input"]
    shutil.copyfile(pilot.zip_path, target / "official_dataset_source.zip")
    shutil.copyfile(
        pilot.pin_path,
        target / "official_dataset_input_pin_v1.json",
    )
    write_json(target / "pilot_input.json", input_payload)
    write_json(target / "pilot_adapter_receipt.json", projected["adapter_receipt"])
    write_json(target / "pilot_runtime_receipt.json", projected["runtime_receipt"])
    write_json(target / "frozen_candidates.json", projected["frozen_candidates"])

    ledger_root = target / "fake_ledger"
    fake = run_fake_provider_pilot(input_payload, ledger_root=ledger_root)
    run = fake["run"]
    summary = fake["summary"]
    write_json(target / "fake_run.json", run)
    write_json(target / "pilot_zero_api_summary.json", summary)

    replay = replay_context_run(
        input_payload=input_payload,
        original_run=run,
        ledger_root=ledger_root,
    )
    write_json(target / "replay_report.json", replay)

    package_root = target / "context_evidence_packages"
    package_manifest = write_context_evidence_package_set(
        run_payload=run,
        frozen_candidates=projected["frozen_candidates"]["candidates"],
        binding=build_projection_binding_from_ledger(
            run_payload=run,
            ledger_path=ledger_root / "provider_attempts.jsonl",
        ),
        output_directory=package_root,
    )
    candidate_outcomes = [
        {
            "candidate_id": row["candidate_id"],
            "sense_id": row["sense_id"],
            "local_status": row["contextual_evidence"]["status"],
            "asserted_gate_codes": sorted(
                {
                    *row["context_flags"],
                    *(
                        flag
                        for result in row["context_results"]
                        for flag in result["local_hard_flags"]
                    ),
                }
            ),
            "final_glossary_decision": row["final_glossary_decision"],
        }
        for row in sorted(run["candidates"], key=lambda value: value["candidate_id"])
    ]
    if len(candidate_outcomes) != 15 or any(
        row["final_glossary_decision"] is not None for row in candidate_outcomes
    ):
        raise ValueError("official C pilot violates count or decision neutrality")

    report = seal_object(
        {
            "schema_id": OFFICIAL_PILOT_REPORT_SCHEMA_ID,
            "schema_version": OFFICIAL_PILOT_REPORT_SCHEMA_VERSION,
            "status": "PASS",
            "source_zip_sha256": pilot.zip_sha256,
            "source_pin_self_sha256": pilot.pin["integrity"]["self_sha256"],
            "official_manifest_sha256": pilot.manifest["manifest_sha256"],
            "source_input_sha256": input_payload["integrity"]["input_sha256"],
            "source_run_sha256": run["integrity"]["run_sha256"],
            "effective_sense_contract_count": len(pilot.effective_senses),
            "frozen_candidate_contract_count": len(pilot.frozen_candidates),
            "constraint_evidence_package_count": len(pilot.constraint_packages),
            "context_evidence_package_count": package_manifest["package_count"],
            "package_manifest_sha256": package_manifest["integrity"][
                "manifest_sha256"
            ],
            "replay_report_sha256": replay["integrity"]["report_sha256"],
            "local_fake_attempt_count": len(run["provider_attempts"]),
            "accepted_fake_attempt_count": run["usage"]["accepted_count"],
            "rejected_fake_attempt_count": run["usage"]["rejected_count"],
            "candidate_outcomes": candidate_outcomes,
            "candidate_package_failures": [],
            "provider_call_count": 0,
            "network_call_count": 0,
            "final_glossary_decision": None,
            "global_gate_action": None,
            "integrity": {},
        },
        integrity_key="report_sha256",
    )
    write_json(target / "official_pilot_report.json", report)
    return report


__all__ = [
    "OFFICIAL_PILOT_REPORT_SCHEMA_ID",
    "run_official_zero_provider_pilot",
]
