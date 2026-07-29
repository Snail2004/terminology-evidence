from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

try:
    from .build_r0_repair_reaudit import (
        ARTIFACT_NAME,
        POLICY_ID,
        STATUS,
        _build_reaudit_payload,
        _manifest_self_hash,
    )
    from .common import (
        build_file_inventory,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from .r0_repair import R0_REPAIR_SPECS, apply_r0_repair, blank_review
    from .validate_stage_a_adjudication_result import validate_result
except ImportError:  # pragma: no cover - direct script execution
    from build_r0_repair_reaudit import (  # type: ignore
        ARTIFACT_NAME,
        POLICY_ID,
        STATUS,
        _build_reaudit_payload,
        _manifest_self_hash,
    )
    from common import (  # type: ignore
        build_file_inventory,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from r0_repair import R0_REPAIR_SPECS, apply_r0_repair, blank_review  # type: ignore
    from validate_stage_a_adjudication_result import validate_result  # type: ignore


def _validate_manifest(root: Path, errors: list[str]) -> dict[str, Any]:
    try:
        manifest = strict_json_object(root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"manifest: {exc}")
        return {}
    if manifest.get("artifact_name") != ARTIFACT_NAME:
        errors.append("manifest artifact name mismatch")
    if manifest.get("policy_id") != POLICY_ID:
        errors.append("manifest policy mismatch")
    if manifest.get("status") != STATUS:
        errors.append("manifest status mismatch")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        errors.append("manifest self hash mismatch")
    if manifest.get("files") != build_file_inventory(
        root, {"manifest.json", "CHECKSUMS.sha256"}
    ):
        errors.append("manifest file inventory mismatch")
    expected = {
        "repair_case_count": 4,
        "definition_repair_count": 1,
        "candidate_target_repair_count": 4,
        "minimum_ready_r0_acceptances_to_unlock_exact_50": 1,
        "provider_call_count": 0,
        "stage_b_gold_autofill_count": 0,
    }
    for field, value in expected.items():
        if manifest.get(field) != value:
            errors.append(f"manifest count mismatch: {field}")
    if manifest.get("final_glossary_decision") is not None:
        errors.append("manifest contains final glossary decision")
    return manifest


def _validate_checksums(root: Path, errors: list[str]) -> None:
    try:
        lines = (root / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"checksums: {exc}")
        return
    expected = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(root, {"CHECKSUMS.sha256"}).items()
    }
    actual: dict[str, str] = {}
    for line in lines:
        if " *" not in line:
            errors.append("malformed checksum line")
            continue
        digest, relative = line.split(" *", 1)
        if relative in actual:
            errors.append(f"duplicate checksum path: {relative}")
        actual[relative] = digest
    if actual != expected:
        errors.append("checksum inventory mismatch")


def _validate_repairs(
    root: Path, adjudication_root: Path, errors: list[str]
) -> list[dict[str, Any]]:
    try:
        source_queue = strict_jsonl(
            adjudication_root / "pending" / "r0_repair_queue_4.jsonl"
        )
        actual = strict_jsonl(root / "repaired_r0_cases_4.jsonl")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"R0 repair records: {exc}")
        return []
    if len(actual) != 4 or len({row.get("sense_id") for row in actual}) != 4:
        errors.append("R0 repair output must contain four unique senses")
    if {row.get("sense_id") for row in source_queue} != set(R0_REPAIR_SPECS):
        errors.append("canonical R0 queue identity mismatch")
        return actual
    expected = [apply_r0_repair(row, POLICY_ID) for row in source_queue]
    expected.sort(key=lambda row: row["source_term"].casefold())
    if actual != expected:
        errors.append("R0 repaired records differ from deterministic repair policy")
    for row in actual:
        if not verify_record(row, "repair_record_sha256"):
            errors.append(f"R0 repair record self hash mismatch: {row.get('sense_id')}")
        if row.get("repair_status") != "PENDING_BLIND_REAUDIT":
            errors.append(f"R0 repair status mismatch: {row.get('sense_id')}")
        if row.get("provider_call_count") != 0 or row.get(
            "stage_b_gold_label"
        ) is not None or row.get("final_glossary_decision") is not None:
            errors.append(f"R0 repair boundary violation: {row.get('sense_id')}")
    return actual


def _validate_handoff(
    root: Path, repairs: list[Mapping[str, Any]], report: Mapping[str, Any], errors: list[str]
) -> None:
    expected = _build_reaudit_payload(list(repairs))
    try:
        payload = strict_json_object(root / "handoff" / "reviewer_input.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"R0 handoff input: {exc}")
        return
    if payload != expected:
        errors.append("R0 handoff input differs from repaired records")
    if payload.get("case_count") != 4 or payload.get("reviewer_slot") != "r0_blind_reauditor":
        errors.append("R0 handoff identity/count mismatch")
    for case in payload.get("cases", []):
        if "reviewer_1" in case or "repair_operations" in case:
            errors.append(f"R0 handoff leaks prior review: {case.get('sense_id')}")
        if case.get("review") != blank_review():
            errors.append(f"R0 handoff review is prefilled: {case.get('sense_id')}")
        if case.get("provider_call_count") != 0 or case.get(
            "stage_b_gold_label"
        ) is not None or case.get("final_glossary_decision") is not None:
            errors.append(f"R0 handoff boundary violation: {case.get('sense_id')}")
    zip_path = root / str(report.get("handoff_zip"))
    try:
        if sha256_file(zip_path) != report.get("handoff_zip_sha256"):
            errors.append("R0 handoff ZIP hash mismatch")
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)) or set(names) != {
                "CHECKSUMS.sha256",
                "MESSAGE.md",
                "REVIEW_INSTRUCTIONS.md",
                "reviewer_input.json",
            }:
                errors.append("R0 handoff ZIP entries mismatch")
            for name in names:
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or "\\" in name:
                    errors.append(f"unsafe R0 handoff ZIP path: {name}")
            archived_payload = json.loads(archive.read("reviewer_input.json"))
            if archived_payload != expected:
                errors.append("R0 handoff ZIP payload mismatch")
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        errors.append(f"R0 handoff ZIP: {exc}")


def _validate_reports(root: Path, errors: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        report = strict_json_object(root / "repair_report.json")
        gate = strict_json_object(root / "exact_50_gate.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"R0 report: {exc}")
        return {}, {}
    for name, value in (("repair report", report), ("exact-50 gate", gate)):
        if not verify_integrity(value):
            errors.append(f"{name} self hash mismatch")
    if report.get("status") != STATUS or report.get("repair_case_count") != 4:
        errors.append("R0 repair report status/count mismatch")
    if report.get("definition_repair_count") != 1 or report.get(
        "candidate_target_repair_count"
    ) != 4:
        errors.append("R0 repair report operation counts mismatch")
    if gate.get("status") != "BLOCKED_PENDING_R0_REAUDIT":
        errors.append("exact-50 gate status mismatch")
    if gate.get("hard_target_strata") != {
        "clear": 15,
        "ambiguous": 20,
        "collision_or_multi_target": 15,
    } or gate.get("currently_ready_pool_strata") != {
        "clear": 14,
        "ambiguous": 23,
        "collision_or_multi_target": 19,
    }:
        errors.append("exact-50 gate stratum counts mismatch")
    if gate.get("minimum_ready_r0_acceptances_to_unlock_exact_50") != 1:
        errors.append("exact-50 gate minimum acceptance mismatch")
    for value in (report, gate):
        if value.get("provider_call_count") != 0 or value.get(
            "stage_b_gold_autofill_count"
        ) != 0 or value.get("final_glossary_decision") is not None:
            errors.append("R0 report boundary violation")
    return report, gate


def validate_repair_reaudit(
    root: Path, *, adjudication_root: Path | None = None
) -> list[str]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        return [f"artifact root: {exc}"]
    if adjudication_root is None:
        namespace = Path(__file__).resolve().parents[1]
        adjudication_root = namespace / "release" / "d2l_fast_track_stage_a_adjudication_result_v1"
    adjudication_root = adjudication_root.resolve(strict=True)
    errors.extend(
        f"canonical adjudication result: {message}"
        for message in validate_result(adjudication_root)
    )
    manifest = _validate_manifest(root, errors)
    _validate_checksums(root, errors)
    try:
        canonical_manifest = strict_json_object(adjudication_root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"canonical adjudication manifest: {exc}")
        return errors
    if manifest.get("canonical_adjudication_manifest_sha256") != canonical_manifest.get(
        "manifest_sha256"
    ):
        errors.append("manifest canonical adjudication binding mismatch")
    repairs = _validate_repairs(root, adjudication_root, errors)
    report, _ = _validate_reports(root, errors)
    if report.get("canonical_adjudication_manifest_sha256") != canonical_manifest.get(
        "manifest_sha256"
    ) or report.get("canonical_adjudication_manifest_physical_sha256") != sha256_file(
        adjudication_root / "manifest.json"
    ):
        errors.append("report canonical adjudication binding mismatch")
    _validate_handoff(root, repairs, report, errors)
    required = {
        "source/.gitattributes",
        "source/README.md",
        "source/tools/common.py",
        "source/tools/spec.py",
        "source/tools/r0_repair.py",
        "source/tools/build_r0_repair_reaudit.py",
        "source/tools/validate_r0_repair_reaudit.py",
        "source/tests/test_r0_repair_reaudit.py",
    }
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    for relative in sorted(required - actual):
        errors.append(f"source bundle file missing: {relative}")
    return errors


def validate_zip(zip_path: Path, artifact_root: Path) -> list[str]:
    expected = {
        path.relative_to(artifact_root).as_posix(): sha256_file(path)
        for path in artifact_root.rglob("*")
        if path.is_file()
    }
    errors: list[str] = []
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                errors.append("release ZIP contains duplicate entries")
            actual = {info.filename: sha256_bytes(archive.read(info)) for info in infos}
            if actual != expected:
                errors.append("release ZIP differs from artifact directory")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"release ZIP: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--adjudication-root", type=Path)
    parser.add_argument("--zip-path", type=Path)
    args = parser.parse_args()
    errors = validate_repair_reaudit(
        args.artifact_root, adjudication_root=args.adjudication_root
    )
    if args.zip_path is not None:
        errors.extend(validate_zip(args.zip_path.resolve(strict=True), args.artifact_root))
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
