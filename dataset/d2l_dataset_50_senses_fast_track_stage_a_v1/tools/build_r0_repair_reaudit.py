from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

try:
    from .common import (
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_integrity,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from .r0_repair import R0_REPAIR_SPECS, apply_r0_repair, blank_review
    from .spec import CREATED_AT_DEFAULT
    from .validate_stage_a_adjudication_result import validate_result
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_integrity,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from r0_repair import R0_REPAIR_SPECS, apply_r0_repair, blank_review  # type: ignore
    from spec import CREATED_AT_DEFAULT  # type: ignore
    from validate_stage_a_adjudication_result import validate_result  # type: ignore


ARTIFACT_NAME = "d2l_fast_track_stage_a_r0_repair_reaudit_v1"
POLICY_ID = "d2l-fast-track-stage-a-r0-repair-reaudit-v1.0"
STATUS = "READY_FOR_R0_BLIND_REAUDIT"


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _build_reaudit_payload(repairs: list[Mapping[str, Any]]) -> dict[str, Any]:
    cases = []
    for repair in repairs:
        cases.append(
            {
                "schema_id": "D2LFastTrackStageAR0ReauditCaseV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "repair_case_id": repair["repair_case_id"],
                "repair_record_sha256": repair["repair_record_sha256"],
                "sense_id": repair["sense_id"],
                "source_term": repair["source_term"],
                "risk_class": repair["risk_class"],
                "source_payload": repair["repaired_source_payload"],
                "source_payload_sha256": repair["repaired_source_payload_sha256"],
                "review": blank_review(),
                "provider_call_count": 0,
                "stage_b_gold_label": None,
                "final_glossary_decision": None,
            }
        )
    return {
        "schema_id": "D2LFastTrackStageAR0ReauditInputV1",
        "schema_version": "1.0.0",
        "policy_id": POLICY_ID,
        "reviewer_slot": "r0_blind_reauditor",
        "independence_mode": "DOES_NOT_SEE_REVIEWER_1_DECISIONS",
        "return_contract": "RETURN_THIS_JSON_WITH_ONLY_REVIEW_FIELDS_FILLED",
        "case_count": len(cases),
        "cases": cases,
        "source_input_sha256": sha256_bytes(
            canonical_json_bytes(
                [
                    {
                        "repair_case_id": row["repair_case_id"],
                        "repair_record_sha256": row["repair_record_sha256"],
                    }
                    for row in cases
                ]
            )
        ),
    }


def _write_handoff(staging: Path, payload: Mapping[str, Any]) -> tuple[str, str]:
    handoff = staging / ".handoff"
    handoff.mkdir()
    write_json(handoff / "reviewer_input.json", payload)
    (handoff / "MESSAGE.md").write_text(
        "Review the four repaired R0 Stage A cases independently. Read "
        "REVIEW_INSTRUCTIONS.md, fill only each review object, and return the "
        "completed reviewer_input.json file.\n",
        encoding="utf-8",
        newline="\n",
    )
    (handoff / "REVIEW_INSTRUCTIONS.md").write_text(
        "# R0 blind re-audit\n\n"
        "Review each repaired sense from the D2L source contexts. You do not see "
        "the prior reviewer decision. Fill only `review`; preserve every other "
        "field. Use candidate-bound replacement objects if further candidate "
        "changes are required. Set `review_status` to `COMPLETE`. Use "
        "`READY_FOR_CONTRACT_CONSTRUCTION` only when all decisions are resolved. "
        "Do not create Stage B gold or a final glossary decision.\n",
        encoding="utf-8",
        newline="\n",
    )
    write_checksums(handoff, handoff / "CHECKSUMS.sha256")
    relative = "handoff/r0_repair_reaudit_reviewer.zip"
    zip_path = staging / relative
    build_deterministic_zip(handoff, zip_path)
    return relative, sha256_file(zip_path)


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    files = (
        ".gitattributes",
        "README.md",
        "tools/__init__.py",
        "tools/common.py",
        "tools/spec.py",
        "tools/r0_repair.py",
        "tools/build_r0_repair_reaudit.py",
        "tools/validate_r0_repair_reaudit.py",
        "tests/test_r0_repair_reaudit.py",
    )
    for relative in files:
        source = namespace / relative
        if not source.is_file():
            raise ValueError(f"source bundle file is missing: {relative}")
        destination = staging / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def build_r0_repair_reaudit(
    *,
    adjudication_root: Path,
    output_root: Path,
    created_at: str,
) -> dict[str, Any]:
    adjudication_root = adjudication_root.resolve(strict=True)
    validation_errors = validate_result(adjudication_root)
    if validation_errors:
        raise ValueError(
            "canonical adjudication result validation failed: "
            + "; ".join(validation_errors)
        )
    adjudication_manifest = strict_json_object(adjudication_root / "manifest.json")
    queue_path = adjudication_root / "pending" / "r0_repair_queue_4.jsonl"
    queue = strict_jsonl(queue_path)
    if len(queue) != 4 or {row["sense_id"] for row in queue} != set(R0_REPAIR_SPECS):
        raise ValueError("canonical R0 repair queue identity mismatch")
    repairs = [apply_r0_repair(row, POLICY_ID) for row in queue]
    repairs.sort(key=lambda row: row["source_term"].casefold())
    payload = _build_reaudit_payload(repairs)
    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent))
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        write_jsonl(staging / "repaired_r0_cases_4.jsonl", repairs)
        write_json(staging / "handoff" / "reviewer_input.json", payload)
        handoff_relative, handoff_sha = _write_handoff(staging, payload)
        gate = seal_integrity(
            {
                "schema_id": "D2LFastTrackExact50StageAGateV1",
                "schema_version": "1.0.0",
                "artifact_name": ARTIFACT_NAME,
                "policy_id": POLICY_ID,
                "status": "BLOCKED_PENDING_R0_REAUDIT",
                "created_at": created_at,
                "hard_target_strata": {
                    "clear": 15,
                    "ambiguous": 20,
                    "collision_or_multi_target": 15,
                },
                "currently_ready_pool_strata": {
                    "clear": 14,
                    "ambiguous": 23,
                    "collision_or_multi_target": 19,
                },
                "r0_reaudit_case_count": 4,
                "minimum_ready_r0_acceptances_to_unlock_exact_50": 1,
                "projected_clear_count_after_one_acceptance": 15,
                "exact_50_frozen": False,
                "stage_b_150_opened": False,
                "provider_call_count": 0,
                "stage_b_gold_autofill_count": 0,
                "final_glossary_decision": None,
            }
        )
        write_json(staging / "exact_50_gate.json", gate)
        report = seal_integrity(
            {
                "schema_id": "D2LFastTrackStageAR0RepairReauditReportV1",
                "schema_version": "1.0.0",
                "artifact_name": ARTIFACT_NAME,
                "policy_id": POLICY_ID,
                "status": STATUS,
                "created_at": created_at,
                "canonical_adjudication_manifest_sha256": adjudication_manifest[
                    "manifest_sha256"
                ],
                "canonical_adjudication_manifest_physical_sha256": sha256_file(
                    adjudication_root / "manifest.json"
                ),
                "canonical_r0_queue_sha256": sha256_file(queue_path),
                "repair_case_count": 4,
                "definition_repair_count": sum(
                    any(op["operation"] == "REPLACE_DEFINITION" for op in row["repair_operations"])
                    for row in repairs
                ),
                "candidate_target_repair_count": sum(
                    sum(op["operation"] == "REPLACE_CANDIDATE_TARGET" for op in row["repair_operations"])
                    for row in repairs
                ),
                "handoff_zip": handoff_relative,
                "handoff_zip_sha256": handoff_sha,
                "provider_call_count": 0,
                "stage_b_gold_autofill_count": 0,
                "final_glossary_decision": None,
            }
        )
        write_json(staging / "repair_report.json", report)
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L Fast-Track R0 repair and re-audit handoff\n\n"
            "- Four pending R0 senses were repaired exactly from Reviewer 1 instructions.\n"
            "- One definition and four candidate targets changed; IDs and contexts are unchanged.\n"
            "- The handoff hides prior reviewer decisions and contains blank review fields.\n"
            "- At least one accepted re-audit is required to unlock the 15/20/15 exact-50 freeze.\n"
            "- No Stage B gold, provider call, or final glossary decision was created.\n",
            encoding="utf-8",
            newline="\n",
        )
        _write_source_bundle(staging)
        shutil.rmtree(staging / ".handoff")
        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LFastTrackStageAR0RepairReauditManifestV1",
            "schema_version": "1.0.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": POLICY_ID,
            "status": STATUS,
            "created_at": created_at,
            "canonical_adjudication_manifest_sha256": adjudication_manifest[
                "manifest_sha256"
            ],
            "repair_case_count": 4,
            "definition_repair_count": 1,
            "candidate_target_repair_count": 4,
            "minimum_ready_r0_acceptances_to_unlock_exact_50": 1,
            "provider_call_count": 0,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        try:
            from .validate_r0_repair_reaudit import validate_repair_reaudit
        except ImportError:  # pragma: no cover
            from validate_r0_repair_reaudit import validate_repair_reaudit  # type: ignore
        errors = validate_repair_reaudit(staging, adjudication_root=adjudication_root)
        if errors:
            raise ValueError("internal R0 repair validation failed: " + "; ".join(errors))
        zip_name = f"{ARTIFACT_NAME}_release.zip"
        temporary_zip = temporary / zip_name
        build_deterministic_zip(staging, temporary_zip)
        replace_directory(staging, output_root)
        final_zip = output_root.parent / zip_name
        os.replace(temporary_zip, final_zip)
        zip_sha = sha256_file(final_zip)
        (output_root.parent / f"{zip_name}.sha256").write_text(
            f"{zip_sha} *{zip_name}\n", encoding="ascii", newline="\n"
        )
        return {
            "status": STATUS,
            "artifact_root": str(output_root),
            "manifest_sha256": manifest["manifest_sha256"],
            "handoff_zip": str(output_root / handoff_relative),
            "handoff_zip_sha256": handoff_sha,
            "release_zip": str(final_zip),
            "release_zip_sha256": zip_sha,
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    namespace = Path(__file__).resolve().parents[1]
    adjudication_default = namespace / "release" / "d2l_fast_track_stage_a_adjudication_result_v1"
    parser = argparse.ArgumentParser()
    parser.add_argument("--adjudication-root", type=Path, default=adjudication_default)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--created-at", default=CREATED_AT_DEFAULT)
    args = parser.parse_args()
    result = build_r0_repair_reaudit(
        adjudication_root=args.adjudication_root,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
