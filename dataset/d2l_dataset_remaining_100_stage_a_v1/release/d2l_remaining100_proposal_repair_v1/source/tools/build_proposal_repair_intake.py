from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_deterministic_zip,
    build_file_inventory,
    canonical_json_bytes,
    replace_directory,
    seal_integrity,
    seal_record,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    write_checksums,
    write_json,
    write_jsonl,
)

from .proposal_reaudit_handoffs import build_proposal_reaudit_handoffs
from .proposal_repair_validation import (
    ProposalRepairSpec,
    capture_proposal_repairs,
)


ARTIFACT_NAME = "d2l_remaining100_proposal_repair_v1"
POLICY_ID = "d2l-remaining-100-stage-a-proposal-repair-intake-v1.0"
CREATED_AT = "2026-07-30T00:00:00Z"
BASE_AUTHORITY_COMMIT = "02077c41e4007154176e44307dcbf49a32427998"
EXPECTED_ASSIGNMENTS = {
    "high_risk_proposal_repair_reviewer_2": "reviewer_2",
    "high_risk_proposal_repair_reviewer_3": "reviewer_3",
}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _verify_source_manifest(root: Path) -> dict[str, Any]:
    manifest = strict_json_object(root / "manifest.json")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        raise ValueError("proposal-repair source manifest self-hash mismatch")
    actual = {
        relative: metadata
        for relative, metadata in build_file_inventory(
            root, {"CHECKSUMS.sha256", "manifest.json"}
        ).items()
        if relative
        not in {
            "handoff/high_risk_proposal_repair_reviewer_2.json",
            "handoff/high_risk_proposal_repair_reviewer_3.json",
        }
    }
    if manifest.get("files") != actual:
        raise ValueError("proposal-repair source manifest inventory mismatch")
    return manifest


def _repair_specs(
    source_root: Path,
    reviewer_2_responses: Sequence[Path],
    reviewer_3_responses: Sequence[Path],
) -> list[ProposalRepairSpec]:
    supplied = [
        *(('reviewer_2', path) for path in reviewer_2_responses),
        *(('reviewer_3', path) for path in reviewer_3_responses),
    ]
    if len(supplied) != 2:
        raise ValueError("exactly two proposal repair responses are required")
    specs: list[ProposalRepairSpec] = []
    seen: set[str] = set()
    for supplied_role, response_path in supplied:
        response_path = response_path.resolve(strict=True)
        payload = strict_json_object(response_path)
        batch_id = payload.get("batch_id")
        if not isinstance(batch_id, str) or batch_id not in EXPECTED_ASSIGNMENTS:
            raise ValueError(f"unexpected proposal repair batch: {batch_id}")
        if batch_id in seen:
            raise ValueError(f"duplicate proposal repair batch: {batch_id}")
        expected_role = EXPECTED_ASSIGNMENTS[batch_id]
        if supplied_role != expected_role:
            raise ValueError(f"{batch_id}: proposal repair reviewer mismatch")
        specs.append(
            ProposalRepairSpec(
                reviewer_role=supplied_role,
                batch_id=batch_id,
                input_path=(
                    source_root / "repair_batches" / batch_id / "repair_input.json"
                ).resolve(strict=True),
                response_path=response_path,
            )
        )
        seen.add(batch_id)
    if seen != set(EXPECTED_ASSIGNMENTS):
        raise ValueError("proposal repair responses do not match the frozen assignment")
    return sorted(specs, key=lambda spec: spec.batch_id)


def _copy_source_bundle(staging: Path) -> None:
    source_root = staging / "source"
    module_root = Path(__file__).resolve().parent
    project_root = module_root.parent
    for name in (
        "build_proposal_repair_intake.py",
        "followup_validation.py",
        "proposal_reaudit_handoffs.py",
        "proposal_repair_validation.py",
        "validate_proposal_repair_intake.py",
    ):
        destination = source_root / "tools" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(module_root / name, destination)
    destination = source_root / "tests" / "test_proposal_repair_intake.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        project_root / "tests" / "test_proposal_repair_intake.py", destination
    )


def _repair_record(
    *,
    case: Mapping[str, Any],
    source_route: Mapping[str, Any],
    result_sha256: str,
    reviewer_role: str,
) -> dict[str, Any]:
    return seal_record(
        {
            "final_glossary_decision": None,
            "parent_high_risk_audit_record_sha256": source_route["record_sha256"],
            "policy_id": POLICY_ID,
            "prior_audit": case["audit"],
            "proposal_repair": case["repair"],
            "provider_call_count": 0,
            "reaudit_reviewer_role": case["audit_result_role"],
            "repair_result_role": reviewer_role,
            "repair_result_sha256": result_sha256,
            "repaired_proposal": case["repair"]["revised_proposal"],
            "schema_id": "D2LRemaining100HighRiskProposalRepairRecordV1",
            "schema_version": "1.0",
            "sense_id": case["sense_id"],
            "source_payload": case["source_payload"],
            "source_payload_sha256": case["source_payload_sha256"],
            "source_term": case["source_term"],
            "stage_b_gold_label": None,
            "status": "PENDING_DISTINCT_PROPOSAL_REAUDIT",
        }
    )


def build_proposal_repair_intake(
    *,
    source_root: Path,
    reviewer_2_responses: Sequence[Path],
    reviewer_3_responses: Sequence[Path],
    output_root: Path,
    zip_path: Path,
) -> dict[str, Any]:
    source_root = source_root.resolve(strict=True)
    source_manifest = _verify_source_manifest(source_root)
    specs = _repair_specs(source_root, reviewer_2_responses, reviewer_3_responses)
    output_root = output_root.resolve()
    zip_path = zip_path.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{ARTIFACT_NAME}-", dir=output_root.parent
    ) as temp_name:
        staging = Path(temp_name) / ARTIFACT_NAME
        staging.mkdir(parents=True)
        captures_root = staging / "captures"
        inventory = capture_proposal_repairs(specs, captures_root)
        inventory_by_batch = {row["batch_id"]: row for row in inventory}
        source_routes = {
            str(row["sense_id"]): row
            for row in strict_jsonl(
                source_root / "routing" / "high_risk_revision_required_4.jsonl"
            )
        }
        records: list[dict[str, Any]] = []
        for spec in specs:
            inventory_row = inventory_by_batch[spec.batch_id]
            payload = strict_json_object(
                captures_root / inventory_row["captured_relative_path"]
            )
            for case in payload["cases"]:
                source_route = source_routes.get(str(case["sense_id"]))
                if source_route is None:
                    raise ValueError(f"{case['sense_id']}: missing revision source route")
                if (
                    source_route["parent_proposal_record_sha256"]
                    != case["proposal_record_sha256"]
                    or source_route["audit"] != case["audit"]
                    or source_route["proposal"] != case["original_proposal"]
                ):
                    raise ValueError(f"{case['sense_id']}: repair authority mismatch")
                if case["source_result_role"] != spec.reviewer_role:
                    raise ValueError(f"{case['sense_id']}: proposal author mismatch")
                records.append(
                    _repair_record(
                        case=case,
                        source_route=source_route,
                        result_sha256=inventory_row["sha256"],
                        reviewer_role=spec.reviewer_role,
                    )
                )
        records.sort(key=lambda row: str(row["sense_id"]))
        if len(records) != 4 or len({row["sense_id"] for row in records}) != 4:
            raise ValueError("proposal repair intake must contain four unique senses")
        if {row["source_term"] for row in records} != {
            "attention",
            "blocks",
            "inverse",
            "shape",
        }:
            raise ValueError("proposal repair term set mismatch")
        if any(
            row["repair_result_role"] == row["reaudit_reviewer_role"]
            for row in records
        ):
            raise ValueError("proposal repair author cannot perform the re-audit")
        write_jsonl(staging / "proposal_repairs_pending_reaudit_4.jsonl", records)
        handoff_root = staging / "handoff"
        handoff_root.mkdir(parents=True)
        handoffs = build_proposal_reaudit_handoffs(records, handoff_root)
        (handoff_root / "ASSIGNMENT.md").write_bytes(
            (
                "# Final repaired-proposal re-audit assignment\n\n"
                "## Reviewer 4\n\n"
                "- `proposal_reaudit_reviewer_4.zip` (1 case: blocks)\n\n"
                "Return `proposal_reaudit_reviewer_4.json`.\n\n"
                "## Reviewer 5\n\n"
                "- `proposal_reaudit_reviewer_5.zip` (3 cases: attention, inverse, shape)\n\n"
                "Return `proposal_reaudit_reviewer_5.json`.\n"
            ).encode("utf-8")
        )
        (handoff_root / "REVIEWER_4_MESSAGE.md").write_bytes(
            "Re-audit the repaired blocks proposal in the assigned ZIP. Follow INSTRUCTIONS.md, edit only audit, preserve all other fields, and return proposal_reaudit_reviewer_4.json only.\n".encode(
                "utf-8"
            )
        )
        (handoff_root / "REVIEWER_5_MESSAGE.md").write_bytes(
            "Re-audit the repaired attention, inverse, and shape proposals in the assigned ZIP. Follow INSTRUCTIONS.md, edit only audit, preserve all other fields, and return proposal_reaudit_reviewer_5.json only.\n".encode(
                "utf-8"
            )
        )
        write_json(
            staging / "authority.json",
            seal_integrity(
                {
                    "base_authority_commit": BASE_AUTHORITY_COMMIT,
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LRemaining100ProposalRepairIntakeAuthorityV1",
                    "schema_version": "1.0",
                    "source_manifest_physical_sha256": sha256_file(
                        source_root / "manifest.json"
                    ),
                    "source_manifest_self_sha256": source_manifest[
                        "manifest_sha256"
                    ],
                }
            ),
        )
        write_json(
            staging / "input_inventory.json",
            seal_integrity(
                {
                    "file_count": len(inventory),
                    "files": sorted(
                        inventory, key=lambda row: row["captured_relative_path"]
                    ),
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LRemaining100ProposalRepairInputInventoryV1",
                    "schema_version": "1.0",
                }
            ),
        )
        write_json(
            staging / "validation_report.json",
            seal_integrity(
                {
                    "blocked_case_count": 1,
                    "created_at": CREATED_AT,
                    "final_glossary_decision": None,
                    "pending_reaudit_case_count": len(records),
                    "policy_id": POLICY_ID,
                    "provider_call_count": 0,
                    "ready_stage_a_source_sense_count": 95,
                    "reaudit_handoffs": handoffs,
                    "schema_id": "D2LRemaining100ProposalRepairIntakeReportV1",
                    "schema_version": "1.0",
                    "stage_b_gold_autofill_count": 0,
                    "status": "PROPOSAL_REPAIRS_VALIDATED_REAUDIT_READY_ZERO_PROVIDER",
                    "validated_result_file_count": len(inventory),
                }
            ),
        )
        (staging / "RELEASE_REPORT.md").write_bytes(
            (
                "# D2L remaining-100 proposal repair intake\n\n"
                "- Reviewer 2/3 repair files validated and captured: 2/2.\n"
                "- Repaired proposals awaiting distinct re-audit: 4.\n"
                "- Reviewer 4: `blocks`.\n"
                "- Reviewer 5: `attention`, `inverse`, `shape`.\n"
                "- Remaining-100 Stage A source senses ready before re-audit: 95/100.\n"
                "- Evidence-blocked source senses: 1 (`switch`).\n"
                "- Provider calls: 0.\n"
                "- Stage B gold autofill: 0.\n"
                "- Final glossary decision: null.\n"
            ).encode("utf-8")
        )
        _copy_source_bundle(staging)
        files = build_file_inventory(
            staging, excluded={"CHECKSUMS.sha256", "manifest.json"}
        )
        manifest = {
            "artifact_name": ARTIFACT_NAME,
            "base_authority_commit": BASE_AUTHORITY_COMMIT,
            "created_at": CREATED_AT,
            "file_count": len(files),
            "files": files,
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "schema_id": "D2LRemaining100ProposalRepairIntakeManifestV1",
            "schema_version": "1.0",
            "status": "PROPOSAL_REPAIRS_VALIDATED_REAUDIT_READY_ZERO_PROVIDER",
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        from .validate_proposal_repair_intake import validate_artifact

        errors = validate_artifact(staging)
        if errors:
            raise ValueError("; ".join(errors))
        replace_directory(staging, output_root)
    build_deterministic_zip(output_root, zip_path)
    return {
        "artifact_root": str(output_root),
        "manifest_sha256": strict_json_object(output_root / "manifest.json")[
            "manifest_sha256"
        ],
        "status": "PROPOSAL_REPAIRS_VALIDATED_REAUDIT_READY_ZERO_PROVIDER",
        "zip_path": str(zip_path),
        "zip_sha256": sha256_file(zip_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--reviewer-2-response", type=Path, action="append", required=True)
    parser.add_argument("--reviewer-3-response", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path, required=True)
    args = parser.parse_args()
    result = build_proposal_repair_intake(
        source_root=args.source_root,
        reviewer_2_responses=args.reviewer_2_response,
        reviewer_3_responses=args.reviewer_3_response,
        output_root=args.output_root,
        zip_path=args.zip_path,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
