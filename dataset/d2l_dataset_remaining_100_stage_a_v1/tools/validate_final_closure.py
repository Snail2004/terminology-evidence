from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_file_inventory,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    verify_integrity,
    verify_record,
)


TARGET_TERMS = {"attention", "blocks", "inverse", "shape"}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _validate_checksums(root: Path, errors: list[str]) -> None:
    expected: dict[str, str] = {}
    try:
        lines = (root / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(str(exc))
        return
    for line in lines:
        if " *" not in line:
            errors.append("malformed checksum row")
            continue
        digest, relative = line.split(" *", 1)
        if relative in expected:
            errors.append(f"duplicate checksum path: {relative}")
        expected[relative] = digest
    actual = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(
            root, {"CHECKSUMS.sha256"}
        ).items()
    }
    if expected != actual:
        errors.append("checksum inventory does not match artifact files")


def _validate_zero_provider(value: Any, prefix: str, errors: list[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if key == "provider_call_count" and child != 0:
                errors.append(f"nonzero provider call count: {path}")
            if key == "stage_b_gold_autofill_count" and child != 0:
                errors.append(f"nonzero Stage B gold autofill: {path}")
            if key in {"final_glossary_decision", "stage_b_gold_label"} and child is not None:
                errors.append(f"forbidden final/gold value: {path}")
            _validate_zero_provider(child, path, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _validate_zero_provider(child, f"{prefix}[{index}]", errors)


def _captured_cases(
    root: Path, inventory: Mapping[str, Any], errors: list[str]
) -> dict[str, tuple[Mapping[str, Any], str, str]]:
    cases: dict[str, tuple[Mapping[str, Any], str, str]] = {}
    files = inventory.get("files")
    if not isinstance(files, list) or len(files) != 2:
        errors.append("input inventory must contain two files")
        return cases
    roles: set[str] = set()
    for row in files:
        if not isinstance(row, Mapping):
            errors.append("input inventory row must be an object")
            continue
        relative = row.get("captured_relative_path")
        role = row.get("reviewer_role")
        if not isinstance(relative, str) or not isinstance(role, str):
            errors.append("invalid captured input metadata")
            continue
        path = root / "captures" / relative
        if not path.is_file() or sha256_file(path) != row.get("sha256"):
            errors.append(f"captured input hash mismatch: {relative}")
            continue
        roles.add(role)
        payload = strict_json_object(path)
        if payload.get("reviewer_slot") != role:
            errors.append(f"captured reviewer slot mismatch: {relative}")
        for case in payload.get("cases", []):
            if not isinstance(case, Mapping):
                errors.append(f"invalid captured case: {relative}")
                continue
            sense_id = case.get("sense_id")
            if not isinstance(sense_id, str) or sense_id in cases:
                errors.append(f"duplicate or invalid captured sense: {sense_id}")
                continue
            cases[sense_id] = (case, role, str(row["sha256"]))
    if roles != {"reviewer_4", "reviewer_5"}:
        errors.append("captured final re-audit reviewer set mismatch")
    return cases


def validate_artifact(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        manifest = strict_json_object(root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        return [str(exc)]
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        errors.append("manifest self-hash mismatch")
    actual_files = build_file_inventory(
        root, {"CHECKSUMS.sha256", "manifest.json"}
    )
    if manifest.get("files") != actual_files:
        errors.append("manifest file inventory mismatch")
    if manifest.get("file_count") != len(actual_files):
        errors.append("manifest file count mismatch")
    if manifest.get("status") != "REMAINING_100_STAGE_A_99_READY_1_BLOCKED_ZERO_PROVIDER":
        errors.append("manifest status mismatch")
    _validate_checksums(root, errors)

    integrity_files = {
        "authority.json": "D2LRemaining100FinalClosureAuthorityV1",
        "input_inventory.json": "D2LRemaining100FinalReauditInputInventoryV1",
        "switch_resolution_required.json": "D2LRemaining100SwitchResolutionRequirementV1",
        "validation_report.json": "D2LRemaining100FinalClosureReportV1",
    }
    integrity_payloads: dict[str, Mapping[str, Any]] = {}
    for name, schema_id in integrity_files.items():
        try:
            payload = strict_json_object(root / name)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(str(exc))
            continue
        integrity_payloads[name] = payload
        if payload.get("schema_id") != schema_id or not verify_integrity(payload):
            errors.append(f"{name}: integrity/schema mismatch")
    inventory = integrity_payloads.get("input_inventory.json", {})
    captured = _captured_cases(root, inventory, errors)

    try:
        approvals = strict_jsonl(root / "approved_repaired_split_proposals_4.jsonl")
        children = strict_jsonl(root / "approved_child_sense_projections_9.jsonl")
        closure = strict_jsonl(root / "closure_index_100.jsonl")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(str(exc))
        return errors
    for label, rows in {
        "approval": approvals,
        "child": children,
        "closure": closure,
    }.items():
        for row in rows:
            if not verify_record(row):
                errors.append(f"{label} record self-hash mismatch")

    if len(approvals) != 4 or len({row.get("sense_id") for row in approvals}) != 4:
        errors.append("approved proposal count/identity mismatch")
    if {row.get("source_term") for row in approvals} != TARGET_TERMS:
        errors.append("approved proposal term set mismatch")
    approval_by_id = {str(row.get("sense_id")): row for row in approvals}
    expected_children: dict[str, tuple[Mapping[str, Any], Mapping[str, Any]]] = {}
    for approval in approvals:
        sense_id = str(approval.get("sense_id"))
        captured_row = captured.get(sense_id)
        if captured_row is None:
            errors.append(f"{sense_id}: missing captured approval case")
            continue
        case, role, response_sha = captured_row
        if (
            case.get("audit", {}).get("audit_decision") != "APPROVE"
            or case.get("audit", {}).get("invalid_child_sense_ids") != []
            or approval.get("approval_audit") != case.get("audit")
            or approval.get("repaired_proposal") != case.get("repaired_proposal")
            or approval.get("reaudit_result_role") != role
            or approval.get("reaudit_result_sha256") != response_sha
            or approval.get("parent_repair_record_sha256")
            != case.get("parent_repair_record_sha256")
        ):
            errors.append(f"{sense_id}: approval/captured case binding mismatch")
        proposal = approval.get("repaired_proposal")
        child_rows = (
            proposal.get("child_sense_repairs", [])
            if isinstance(proposal, Mapping)
            else []
        )
        child_ids = sorted(
            child.get("temporary_child_sense_id")
            for child in child_rows
            if isinstance(child, Mapping)
        )
        if approval.get("approved_child_sense_ids") != child_ids:
            errors.append(f"{sense_id}: approved child ID binding mismatch")
        for child in child_rows:
            if not isinstance(child, Mapping):
                errors.append(f"{sense_id}: invalid child payload")
                continue
            child_id = child.get("temporary_child_sense_id")
            if not isinstance(child_id, str) or child_id in expected_children:
                errors.append(f"{sense_id}: duplicate or invalid child ID")
                continue
            expected_children[child_id] = (child, approval)

    if len(children) != 9 or len({row.get("temporary_child_sense_id") for row in children}) != 9:
        errors.append("approved child projection count/identity mismatch")
    for row in children:
        child_id = str(row.get("temporary_child_sense_id"))
        expected = expected_children.get(child_id)
        if expected is None:
            errors.append(f"{child_id}: unexpected child projection")
            continue
        child, approval = expected
        if (
            row.get("child_sense_payload") != child
            or row.get("parent_approval_record_sha256") != approval.get("record_sha256")
            or row.get("parent_source_sense_id") != approval.get("sense_id")
            or row.get("source_payload_sha256")
            != approval.get("source_payload_sha256")
            or row.get("stage_a_status") != "APPROVED_SPLIT_CHILD"
        ):
            errors.append(f"{child_id}: child projection binding mismatch")

    if len(closure) != 100 or len({row.get("sense_id") for row in closure}) != 100:
        errors.append("closure count/identity mismatch")
    status_counts = {
        status: sum(row.get("stage_a_status") == status for row in closure)
        for status in {row.get("stage_a_status") for row in closure}
    }
    if status_counts != {"READY": 99, "BLOCKED": 1}:
        errors.append(f"closure status counts mismatch: {status_counts}")
    blocked = [row for row in closure if row.get("stage_a_status") == "BLOCKED"]
    if len(blocked) != 1 or blocked[0].get("source_term") != "switch":
        errors.append("switch must be the sole blocked source sense")
    closure_by_id = {str(row.get("sense_id")): row for row in closure}
    for sense_id, approval in approval_by_id.items():
        row = closure_by_id.get(sense_id)
        if row is None or (
            row.get("stage_a_status") != "READY"
            or row.get("authority_kind")
            != "APPROVED_REPAIRED_SPLIT_PROPOSAL_REAUDIT"
            or row.get("authority_record_sha256") != approval.get("record_sha256")
            or row.get("approved_child_sense_ids")
            != approval.get("approved_child_sense_ids")
        ):
            errors.append(f"{sense_id}: final closure approval binding mismatch")

    report = integrity_payloads.get("validation_report.json", {})
    if (
        report.get("ready_source_sense_count") != 99
        or report.get("blocked_source_sense_count") != 1
        or report.get("approved_repaired_proposal_count") != 4
        or report.get("approved_child_sense_count") != 9
        or report.get("validated_final_reaudit_file_count") != 2
        or report.get("status")
        != "REMAINING_100_STAGE_A_99_READY_1_BLOCKED_ZERO_PROVIDER"
    ):
        errors.append("validation report count/status mismatch")
    switch = integrity_payloads.get("switch_resolution_required.json", {})
    if (
        switch.get("source_term") != "switch"
        or switch.get("stage_a_status") != "BLOCKED"
        or switch.get("status")
        != "REAL_POSITIVE_EVIDENCE_OR_REPLACEMENT_REQUIRED"
        or set(switch.get("forbidden_positive_evidence", []))
        != {"SYNTHETIC_CONTEXT", "BOUNDARY_ONLY_CONTEXT"}
    ):
        errors.append("switch resolution requirement mismatch")

    _validate_zero_provider(manifest, "manifest", errors)
    for name, payload in integrity_payloads.items():
        _validate_zero_provider(payload, name, errors)
    for label, rows in {
        "approvals": approvals,
        "children": children,
        "closure": closure,
    }.items():
        _validate_zero_provider(rows, label, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()
    errors = validate_artifact(args.artifact_root)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
