from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

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
    write_checksums,
    write_json,
    write_jsonl,
)
from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.spec import stable_id

from .followup_handoffs import (
    build_high_risk_audit_handoffs,
    build_reaudit_handoffs,
)
from .followup_validation import (
    ReviewFileSpec,
    apply_resolution,
    capture_review_files,
    sanitize_for_blind_review,
    source_payload_sha256,
)


ARTIFACT_NAME = "d2l_dataset_remaining_100_stage_a_followup_intake_v1"
POLICY_ID = "d2l-remaining-100-stage-a-followup-intake-v1.0"
CREATED_AT = "2026-07-30T00:00:00Z"
BASE_AUTHORITY_COMMIT = "67296e5a85a4ab4507fba137b2cdd3f270a1388d"
PACK_AUTHORITIES = {
    "r0_repair": "74282e544c752ed31d295ffc3f088cd582ef1a8e",
    "high_risk": "a9a3f308cbb2be5e5f6f444a274f55b362e3264c",
    "r0_blind": "b5467010fd2e6b453464ab590dbc827ee06a8410",
}
EXPECTED_BATCHES = {
    "r0_repair": ("repair_batch_001", "repair_batch_002"),
    "high_risk": (
        "highrisk_batch_001",
        "highrisk_batch_002",
        "highrisk_batch_003",
    ),
    "r0_blind": tuple(f"blind_batch_{index:03d}" for index in range(1, 6)),
}


def _git_head(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _result_specs(
    *,
    kind: str,
    reviewer_roles: Sequence[str],
    release_root: Path,
    response_paths: Sequence[Path],
) -> list[ReviewFileSpec]:
    if len(reviewer_roles) != len(response_paths):
        raise ValueError(f"{kind}: reviewer role count does not match responses")
    specs: list[ReviewFileSpec] = []
    input_name = "reviewer_input.json" if kind == "r0_blind" else "repair_input.json"
    seen_batches: set[str] = set()
    for reviewer_role, response_path in zip(reviewer_roles, response_paths):
        payload = strict_json_object(response_path.resolve(strict=True))
        batch_id = payload.get("batch_id")
        if not isinstance(batch_id, str) or batch_id in seen_batches:
            raise ValueError(f"{kind}: invalid or duplicate batch ID")
        seen_batches.add(batch_id)
        input_path = release_root / "batches" / batch_id / input_name
        specs.append(
            ReviewFileSpec(
                kind=kind,
                reviewer_role=reviewer_role,
                batch_id=batch_id,
                input_path=input_path.resolve(strict=True),
                response_path=response_path.resolve(strict=True),
            )
        )
    if tuple(sorted(seen_batches)) != tuple(sorted(EXPECTED_BATCHES[kind])):
        raise ValueError(f"{kind}: response batches do not match the frozen index")
    return specs


def _captured_payload(capture_root: Path, inventory: Mapping[str, Any]) -> dict[str, Any]:
    return strict_json_object(capture_root / inventory["captured_relative_path"])


def _repair_record(
    *,
    case: Mapping[str, Any],
    resolution: Mapping[str, Any],
    source_result_sha256: str,
    source_role: str,
) -> dict[str, Any]:
    source = case["source_payload"]
    effective, operations = apply_resolution(source, resolution)
    blind_source = sanitize_for_blind_review(effective)
    sense_id = str(source["sense_id"])
    return seal_record(
        {
            "blind_source_payload": blind_source,
            "blind_source_payload_sha256": source_payload_sha256(blind_source),
            "effective_source_payload": effective,
            "effective_source_payload_sha256": source_payload_sha256(effective),
            "final_glossary_decision": None,
            "parent_source_payload_sha256": case["source_payload_sha256"],
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "reaudit_case_id": stable_id("followup_reaudit_", sense_id),
            "repair_operations": operations,
            "schema_id": "D2LRemaining100FollowupRepairRecordV1",
            "schema_version": "1.0",
            "sense_id": sense_id,
            "source_result_role": source_role,
            "source_result_sha256": source_result_sha256,
            "source_term": source["source_term"],
            "stage_b_gold_label": None,
            "status": "PENDING_DISTINCT_BLIND_REAUDIT",
        },
        "record_sha256",
    )


def _accepted_blind_record(
    case: Mapping[str, Any], source_result_sha256: str, source_role: str
) -> dict[str, Any]:
    source = case["source_payload"]
    sense_id = str(source["sense_id"])
    return seal_record(
        {
            "final_glossary_decision": None,
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "review": case["review"],
            "schema_id": "D2LRemaining100AcceptedBlindAuditRecordV1",
            "schema_version": "1.0",
            "sense_id": sense_id,
            "source_payload": source,
            "source_payload_sha256": case["source_payload_sha256"],
            "source_result_role": source_role,
            "source_result_sha256": source_result_sha256,
            "source_term": source["source_term"],
            "stage_b_gold_label": None,
            "status": "BLIND_AUDIT_ACCEPTED_PENDING_FINAL_DATASET_FREEZE",
        },
        "record_sha256",
    )


def _high_risk_record(
    case: Mapping[str, Any], source_result_sha256: str, source_role: str
) -> dict[str, Any]:
    source = case["source_payload"]
    repair = case["repair"]
    sense_id = str(source["sense_id"])
    proposal: dict[str, Any]
    if repair["resolution_status"] == "REPAIRED":
        effective, operations = apply_resolution(source, repair)
        effective_blind = sanitize_for_blind_review(effective)
        proposal = {
            "effective_source_payload": effective_blind,
            "effective_source_payload_sha256": source_payload_sha256(effective_blind),
            "proposal_type": "REPAIRED_SOURCE",
            "repair_operations": operations,
        }
    elif repair["resolution_status"] == "SPLIT_PROPOSED":
        proposal = {
            "child_sense_repairs": repair["child_sense_repairs"],
            "proposal_type": "SPLIT_PROPOSAL",
        }
    else:
        raise ValueError("blocked high-risk case cannot become an audit proposal")
    blind_source = sanitize_for_blind_review(source)
    return seal_record(
        {
            "audit_case_id": stable_id("highrisk_audit_", sense_id),
            "blind_source_payload": blind_source,
            "blind_source_payload_sha256": source_payload_sha256(blind_source),
            "final_glossary_decision": None,
            "parent_source_payload_sha256": case["source_payload_sha256"],
            "policy_id": POLICY_ID,
            "proposal": proposal,
            "provider_call_count": 0,
            "schema_id": "D2LRemaining100HighRiskProposalRecordV1",
            "schema_version": "1.0",
            "sense_id": sense_id,
            "source_result_role": source_role,
            "source_result_sha256": source_result_sha256,
            "source_term": source["source_term"],
            "stage_b_gold_label": None,
            "status": "PENDING_DISTINCT_HIGH_RISK_PROPOSAL_AUDIT",
        },
        "record_sha256",
    )


def _blocked_record(
    case: Mapping[str, Any], source_result_sha256: str, source_role: str
) -> dict[str, Any]:
    source = case["source_payload"]
    return seal_record(
        {
            "final_glossary_decision": None,
            "parent_source_payload_sha256": case["source_payload_sha256"],
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "reason": case["repair"]["repair_rationale"],
            "schema_id": "D2LRemaining100BlockedFollowupRecordV1",
            "schema_version": "1.0",
            "sense_id": source["sense_id"],
            "source_result_role": source_role,
            "source_result_sha256": source_result_sha256,
            "source_term": source["source_term"],
            "stage_b_gold_label": None,
            "status": "BLOCKED_INSUFFICIENT_POSITIVE_EVIDENCE",
        },
        "record_sha256",
    )


def _copy_source_bundle(staging: Path) -> None:
    source_root = staging / "source"
    module_root = Path(__file__).resolve().parent
    project_root = module_root.parent
    for name in (
        "build_followup_intake.py",
        "followup_handoffs.py",
        "followup_validation.py",
        "validate_followup_intake.py",
    ):
        destination = source_root / "tools" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(module_root / name, destination)
    for name in ("test_followup_intake.py",):
        destination = source_root / "tests" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(project_root / "tests" / name, destination)


def build_followup_intake(
    *,
    r0_release_root: Path,
    r0_responses: Sequence[Path],
    high_risk_release_root: Path,
    high_risk_responses: Sequence[Path],
    blind_release_root: Path,
    blind_responses: Sequence[Path],
    output_root: Path,
    zip_path: Path,
    verify_authority: bool = True,
) -> dict[str, Any]:
    release_roots = {
        "r0_repair": r0_release_root.resolve(strict=True),
        "high_risk": high_risk_release_root.resolve(strict=True),
        "r0_blind": blind_release_root.resolve(strict=True),
    }
    if verify_authority:
        for kind, root in release_roots.items():
            repo_root = root
            while repo_root.parent != repo_root and not (repo_root / ".git").exists():
                repo_root = repo_root.parent
            actual = _git_head(repo_root)
            if actual != PACK_AUTHORITIES[kind]:
                raise ValueError(f"{kind}: authority commit mismatch: {actual}")
    specs = []
    specs.extend(
        _result_specs(
            kind="r0_repair",
            reviewer_roles=("reviewer_1", "reviewer_1"),
            release_root=release_roots["r0_repair"],
            response_paths=r0_responses,
        )
    )
    specs.extend(
        _result_specs(
            kind="high_risk",
            reviewer_roles=("reviewer_2", "reviewer_2", "reviewer_3"),
            release_root=release_roots["high_risk"],
            response_paths=high_risk_responses,
        )
    )
    specs.extend(
        _result_specs(
            kind="r0_blind",
            reviewer_roles=(
                "reviewer_4",
                "reviewer_5",
                "reviewer_4",
                "reviewer_5",
                "reviewer_4",
            ),
            release_root=release_roots["r0_blind"],
            response_paths=blind_responses,
        )
    )
    output_root = output_root.resolve()
    zip_path = zip_path.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{ARTIFACT_NAME}-", dir=output_root.parent
    ) as temp_name:
        staging = Path(temp_name) / ARTIFACT_NAME
        staging.mkdir(parents=True)
        captures_root = staging / "captures"
        inventory = capture_review_files(specs, captures_root)
        inventory_by_key = {
            (row["kind"], row["batch_id"]): row for row in inventory
        }
        r0_reaudit: list[dict[str, Any]] = []
        high_risk_audit: list[dict[str, Any]] = []
        accepted_blind: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for spec in specs:
            row = inventory_by_key[(spec.kind, spec.batch_id)]
            response = _captured_payload(captures_root, row)
            for case in response["cases"]:
                if spec.kind == "r0_repair":
                    r0_reaudit.append(
                        _repair_record(
                            case=case,
                            resolution=case["repair"],
                            source_result_sha256=row["sha256"],
                            source_role=spec.reviewer_role,
                        )
                    )
                elif spec.kind == "high_risk":
                    if case["repair"]["resolution_status"] == "BLOCKED":
                        blocked.append(
                            _blocked_record(case, row["sha256"], spec.reviewer_role)
                        )
                    else:
                        high_risk_audit.append(
                            _high_risk_record(case, row["sha256"], spec.reviewer_role)
                        )
                else:
                    if case["review"]["sense_status"] == "READY_FOR_CONTRACT_CONSTRUCTION":
                        accepted_blind.append(
                            _accepted_blind_record(
                                case, row["sha256"], spec.reviewer_role
                            )
                        )
                    elif case["review"]["sense_status"] == "REVISION_REQUIRED":
                        r0_reaudit.append(
                            _repair_record(
                                case=case,
                                resolution=case["review"],
                                source_result_sha256=row["sha256"],
                                source_role=spec.reviewer_role,
                            )
                        )
                    else:
                        raise ValueError(
                            f"unsupported blind follow-up status: {case['sense_id']}"
                        )
        r0_reaudit.sort(key=lambda row: row["sense_id"])
        high_risk_audit.sort(key=lambda row: row["sense_id"])
        accepted_blind.sort(key=lambda row: row["sense_id"])
        blocked.sort(key=lambda row: row["sense_id"])
        counts = Counter(
            {
                "accepted_blind": len(accepted_blind),
                "blocked": len(blocked),
                "high_risk_audit": len(high_risk_audit),
                "r0_reaudit": len(r0_reaudit),
            }
        )
        if counts != Counter(
            {"accepted_blind": 23, "blocked": 1, "high_risk_audit": 10, "r0_reaudit": 12}
        ):
            raise ValueError(f"follow-up routing mismatch: {dict(counts)}")
        routing_root = staging / "routing"
        write_jsonl(routing_root / "accepted_blind_23.jsonl", accepted_blind)
        write_jsonl(routing_root / "r0_reaudit_pending_12.jsonl", r0_reaudit)
        write_jsonl(
            routing_root / "high_risk_audit_pending_10.jsonl", high_risk_audit
        )
        write_jsonl(routing_root / "blocked_1.jsonl", blocked)
        handoff_root = staging / "handoff"
        handoff_root.mkdir(parents=True)
        reaudit_handoffs = build_reaudit_handoffs(r0_reaudit, handoff_root)
        high_risk_handoffs = build_high_risk_audit_handoffs(
            high_risk_audit, handoff_root
        )
        (handoff_root / "ASSIGNMENT.md").write_bytes(
            "# Follow-up reviewer assignment\n\n"
            "The assignments preserve reviewer independence and balance 11 cases per "
            "reviewer. Do not exchange completed outputs before both reviewers finish.\n\n"
            "## Reviewer 4\n\n"
            "- `followup_reaudit_batch_001.zip` (5 cases)\n"
            "- `followup_reaudit_batch_003.zip` (2 cases)\n"
            "- `high_risk_audit_batch_001.zip` (4 cases)\n\n"
            "Return:\n\n"
            "- `followup_reaudit_batch_001_reviewer_4.json`\n"
            "- `followup_reaudit_batch_003_reviewer_4.json`\n"
            "- `high_risk_audit_batch_001_reviewer_4.json`\n\n"
            "## Reviewer 5\n\n"
            "- `followup_reaudit_batch_002.zip` (5 cases)\n"
            "- `high_risk_audit_batch_002.zip` (4 cases)\n"
            "- `high_risk_audit_batch_003.zip` (2 cases)\n\n"
            "Return:\n\n"
            "- `followup_reaudit_batch_002_reviewer_5.json`\n"
            "- `high_risk_audit_batch_002_reviewer_5.json`\n"
            "- `high_risk_audit_batch_003_reviewer_5.json`\n".encode("utf-8")
        )
        (handoff_root / "REVIEWER_4_MESSAGE.md").write_bytes(
            "Review the three assigned ZIP files independently. Follow each included "
            "REVIEW_INSTRUCTIONS.md exactly, modify only `review` or `audit`, preserve "
            "all source and proposal fields, and return the three JSON files named in "
            "ASSIGNMENT.md. Treat synthetic or boundary-only contexts only as negative "
            "boundaries. Do not add Stage B gold, rank, winner, or final glossary "
            "decisions, and do not inspect Reviewer 5 outputs.\n".encode("utf-8")
        )
        (handoff_root / "REVIEWER_5_MESSAGE.md").write_bytes(
            "Review the three assigned ZIP files independently. Follow each included "
            "REVIEW_INSTRUCTIONS.md exactly, modify only `review` or `audit`, preserve "
            "all source and proposal fields, and return the three JSON files named in "
            "ASSIGNMENT.md. Treat synthetic or boundary-only contexts only as negative "
            "boundaries. Do not add Stage B gold, rank, winner, or final glossary "
            "decisions, and do not inspect Reviewer 4 outputs.\n".encode("utf-8")
        )
        authority = seal_integrity(
            {
                "base_authority_commit": BASE_AUTHORITY_COMMIT,
                "pack_authority_commits": PACK_AUTHORITIES,
                "policy_id": POLICY_ID,
                "schema_id": "D2LRemaining100FollowupAuthorityV1",
                "schema_version": "1.0",
            }
        )
        write_json(staging / "authority.json", authority)
        write_json(
            staging / "input_inventory.json",
            seal_integrity(
                {
                    "file_count": len(inventory),
                    "files": sorted(
                        inventory, key=lambda row: row["captured_relative_path"]
                    ),
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LRemaining100FollowupInputInventoryV1",
                    "schema_version": "1.0",
                }
            ),
        )
        report = seal_integrity(
            {
                "accepted_blind_case_count": len(accepted_blind),
                "blocked_case_count": len(blocked),
                "created_at": CREATED_AT,
                "final_glossary_decision": None,
                "high_risk_audit_case_count": len(high_risk_audit),
                "high_risk_handoffs": high_risk_handoffs,
                "policy_id": POLICY_ID,
                "provider_call_count": 0,
                "r0_reaudit_case_count": len(r0_reaudit),
                "reaudit_handoffs": reaudit_handoffs,
                "schema_id": "D2LRemaining100FollowupIntakeReportV1",
                "schema_version": "1.0",
                "stage_b_gold_autofill_count": 0,
                "status": "FOLLOWUP_REVIEW_PACKS_READY_ZERO_PROVIDER",
                "validated_result_file_count": len(inventory),
                "validated_source_case_count": 46,
            }
        )
        write_json(staging / "validation_report.json", report)
        (staging / "RELEASE_REPORT.md").write_bytes(
            "# D2L remaining-100 follow-up intake\n\n"
            "- Reviewer result files validated and captured: 10/10.\n"
            "- Source cases validated: 46/46.\n"
            "- Blind audit accepted pending final freeze: 23.\n"
            "- Corrected cases pending distinct blind re-audit: 12.\n"
            "- High-risk proposals pending distinct audit: 10.\n"
            "- Insufficient-evidence cases kept blocked: 1 (`switch`).\n"
            "- Provider calls: 0.\n"
            "- Stage B gold autofill: 0.\n"
            "- Final glossary decision: null.\n".encode("utf-8")
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
            "schema_id": "D2LRemaining100FollowupIntakeManifestV1",
            "schema_version": "1.0",
            "status": "FOLLOWUP_REVIEW_PACKS_READY_ZERO_PROVIDER",
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        from .validate_followup_intake import validate_artifact

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
        "status": "FOLLOWUP_REVIEW_PACKS_READY_ZERO_PROVIDER",
        "zip_path": str(zip_path),
        "zip_sha256": sha256_file(zip_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--r0-release-root", type=Path, required=True)
    parser.add_argument("--r0-response", type=Path, action="append", required=True)
    parser.add_argument("--high-risk-release-root", type=Path, required=True)
    parser.add_argument(
        "--high-risk-response", type=Path, action="append", required=True
    )
    parser.add_argument("--blind-release-root", type=Path, required=True)
    parser.add_argument("--blind-response", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path, required=True)
    args = parser.parse_args()
    result = build_followup_intake(
        r0_release_root=args.r0_release_root,
        r0_responses=args.r0_response,
        high_risk_release_root=args.high_risk_release_root,
        high_risk_responses=args.high_risk_response,
        blind_release_root=args.blind_release_root,
        blind_responses=args.blind_response,
        output_root=args.output_root,
        zip_path=args.zip_path,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
