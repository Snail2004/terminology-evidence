from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

try:
    from .build_stage_b_official_5 import (
        ALLOWED_LABELS,
        ARTIFACT_NAME,
        OFFICIAL_MANIFEST_SHA256,
        POLICY_ID,
        STATUS,
        _manifest_self_hash,
    )
    from .common import (
        build_file_inventory,
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
except ImportError:  # pragma: no cover - direct script execution
    from build_stage_b_official_5 import (  # type: ignore
        ALLOWED_LABELS,
        ARTIFACT_NAME,
        OFFICIAL_MANIFEST_SHA256,
        POLICY_ID,
        STATUS,
        _manifest_self_hash,
    )
    from common import (  # type: ignore
        build_file_inventory,
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )


FORBIDDEN_KEYS = {
    "candidate_role",
    "intended_candidate_role",
    "final_gold_label",
    "c_score",
    "e_evidence",
    "global_decision",
    "other_reviewer_label",
}


def _walk_keys(value: Any):
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield key
            yield from _walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_keys(item)


def _manifest(root: Path, errors: list[str]) -> dict[str, Any]:
    try:
        manifest = strict_json_object(root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"manifest: {exc}")
        return {}
    if manifest.get("artifact_name") != ARTIFACT_NAME:
        errors.append("artifact name mismatch")
    if manifest.get("policy_id") != POLICY_ID:
        errors.append("policy mismatch")
    if manifest.get("status") != STATUS:
        errors.append("status mismatch")
    if manifest.get("official_manifest_sha256") != OFFICIAL_MANIFEST_SHA256:
        errors.append("official authority manifest mismatch")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        errors.append("manifest self hash mismatch")
    if manifest.get("files") != build_file_inventory(
        root, {"manifest.json", "CHECKSUMS.sha256"}
    ):
        errors.append("manifest inventory mismatch")
    for key, expected in {
        "sense_count": 5,
        "candidate_count": 15,
        "judgments_required": 30,
        "provider_call_count": 0,
        "final_gold_label_count": 0,
    }.items():
        if manifest.get(key) != expected:
            errors.append(f"manifest count mismatch: {key}")
    if manifest.get("final_glossary_decision") is not None:
        errors.append("manifest contains final glossary decision")
    return manifest


def _checksums(root: Path, errors: list[str]) -> None:
    try:
        lines = (root / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"checksums: {exc}")
        return
    actual = {}
    for line in lines:
        if " *" not in line:
            errors.append("malformed checksum line")
            continue
        digest, relative = line.split(" *", 1)
        actual[relative] = digest
    expected = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(
            root, {"CHECKSUMS.sha256"}
        ).items()
    }
    if actual != expected:
        errors.append("checksum inventory mismatch")


def _validate_case(case: Mapping[str, Any], errors: list[str], prefix: str) -> None:
    if not verify_record(case, "case_sha256"):
        errors.append(f"{prefix}: case hash mismatch")
    source = case.get("source_payload")
    if not isinstance(source, Mapping):
        errors.append(f"{prefix}: source payload invalid")
        return
    if set(_walk_keys(source)) & FORBIDDEN_KEYS:
        errors.append(f"{prefix}: forbidden role/evaluation key exposed")
    if case.get("source_payload_sha256") != sha256_bytes(canonical_json_bytes(source)):
        errors.append(f"{prefix}: source payload hash mismatch")
    if not isinstance(source.get("contexts"), list) or not source["contexts"]:
        errors.append(f"{prefix}: contexts missing")
    for context in source.get("contexts", []):
        if not isinstance(context, Mapping):
            errors.append(f"{prefix}: context invalid")
            continue
        if context.get("synthetic") and not context.get("boundary_only"):
            errors.append(f"{prefix}: synthetic context is not boundary-only")
        if context.get("synthetic") and context.get("context_id", "").startswith("ctx_"):
            errors.append(f"{prefix}: synthetic context ID binding mismatch")
    review = case.get("review")
    if not isinstance(review, Mapping):
        errors.append(f"{prefix}: review missing")
        return
    if set(review) != {
        "candidate_gold_label",
        "allowed_scope",
        "validated_variants",
        "rejected_variants",
        "reason_codes",
        "positive_context_refs",
        "vietnamese_evidence_refs",
        "review_notes",
        "review_status",
    }:
        errors.append(f"{prefix}: review schema mismatch")
    if any(review.get(field) not in ("", [], None) for field in review if field != "candidate_gold_label"):
        errors.append(f"{prefix}: review is prefilled")
    if review.get("candidate_gold_label") != "":
        errors.append(f"{prefix}: candidate gold label is prefilled")
    if case.get("provider_call_count") != 0 or case.get("final_gold_label") is not None:
        errors.append(f"{prefix}: case boundary violation")
    if case.get("final_glossary_decision") is not None:
        errors.append(f"{prefix}: case contains final glossary decision")


def _validate_inputs(root: Path, errors: list[str]) -> None:
    payloads = []
    sense_ids: set[str] = set()
    candidate_ids: set[str] = set()
    for slot in ("reviewer_1", "reviewer_2"):
        try:
            payload = strict_json_object(root / f"{slot}_input.json")
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{slot} input: {exc}")
            continue
        payloads.append(payload)
        if payload.get("schema_id") != "D2LStageBOfficialCandidateReviewerInputV1":
            errors.append(f"{slot} input schema mismatch")
        if payload.get("reviewer_slot") != slot or payload.get("case_count") != 15:
            errors.append(f"{slot} input identity/count mismatch")
        cases = payload.get("cases")
        if not isinstance(cases, list) or len(cases) != 15:
            errors.append(f"{slot} case count mismatch")
            continue
        source_projection = []
        for index, case in enumerate(cases):
            _validate_case(case, errors, f"{slot}/case_{index + 1}")
            source = case.get("source_payload", {})
            sense_ids.add(source.get("sense_id"))
            candidate_ids.add(source.get("candidate_id"))
            source_projection.append(
                {"case_id": case.get("case_id"), "case_sha256": case.get("case_sha256")}
            )
        if payload.get("source_input_sha256") != sha256_bytes(
            canonical_json_bytes(source_projection)
        ):
            errors.append(f"{slot} source input hash mismatch")
    if len(payloads) == 2:
        first = {
            case["source_payload"]["candidate_id"]: case["source_payload"]
            for case in payloads[0]["cases"]
        }
        second = {
            case["source_payload"]["candidate_id"]: case["source_payload"]
            for case in payloads[1]["cases"]
        }
        if set(first) != set(second):
            errors.append("reviewer candidate sets differ")
        for candidate_id in first:
            if first[candidate_id] != second[candidate_id]:
                errors.append(f"reviewer source payload differs: {candidate_id}")
    if len(sense_ids) != 5 or len(candidate_ids) != 15:
        errors.append("official input sense/candidate coverage mismatch")


def _validate_handoffs(root: Path, report: Mapping[str, Any], errors: list[str]) -> None:
    handoffs = report.get("handoffs")
    if not isinstance(handoffs, list) or len(handoffs) != 2:
        errors.append("handoff index mismatch")
        return
    for row in handoffs:
        path = root / str(row.get("zip_path"))
        if sha256_file(path) != row.get("zip_sha256"):
            errors.append(f"handoff ZIP hash mismatch: {row.get('reviewer_slot')}")
        try:
            with zipfile.ZipFile(path) as archive:
                names = [info.filename for info in archive.infolist()]
                if set(names) != {
                    "CHECKSUMS.sha256",
                    "MESSAGE.md",
                    "REVIEW_INSTRUCTIONS.md",
                    "review_input.json",
                }:
                    errors.append(f"handoff entries mismatch: {row.get('reviewer_slot')}")
                for info in archive.infolist():
                    relative = PurePosixPath(info.filename)
                    if relative.is_absolute() or ".." in relative.parts or "\\" in info.filename:
                        errors.append(f"unsafe handoff path: {info.filename}")
        except (OSError, zipfile.BadZipFile, KeyError) as exc:
            errors.append(f"handoff ZIP error: {exc}")


def validate_artifact(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        return [str(exc)]
    _manifest(root, errors)
    _checksums(root, errors)
    try:
        report = strict_json_object(root / "RELEASE_REPORT.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"release report: {exc}")
        return errors
    if not verify_integrity(report):
        errors.append("release report self hash mismatch")
    if report.get("status") != STATUS or report.get("sense_count") != 5:
        errors.append("release report status/count mismatch")
    if report.get("candidate_count") != 15 or report.get("judgments_required") != 30:
        errors.append("release report candidate/judgment count mismatch")
    if report.get("provider_call_count") != 0 or report.get("final_gold_label_count") != 0:
        errors.append("release report boundary violation")
    if report.get("final_glossary_decision") is not None:
        errors.append("release report contains final glossary decision")
    _validate_inputs(root, errors)
    _validate_handoffs(root, report, errors)
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
            actual = {info.filename: sha256_bytes(archive.read(info)) for info in archive.infolist()}
            if actual != expected:
                errors.append("release ZIP differs from artifact directory")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"release ZIP: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path)
    args = parser.parse_args()
    errors = validate_artifact(args.artifact_root)
    if args.zip_path is not None:
        errors.extend(validate_zip(args.zip_path.resolve(strict=True), args.artifact_root))
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
