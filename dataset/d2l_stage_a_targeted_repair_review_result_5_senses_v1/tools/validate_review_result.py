from __future__ import annotations

import argparse
import csv
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

try:
    from .common import (
        build_file_inventory,
        canonical_json_bytes,
        read_csv,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from .spec import (
        ADJUDICATION_CASES,
        ADJUDICATION_CSV_FIELDS,
        ADJUDICATION_OUTPUT_FIELDS,
        ADJUDICATION_SOURCE_FIELDS,
        ARTIFACT_NAME,
        CONSENSUS_CASES,
        DECISION_FIELDS,
        POLICY_ID,
        REVIEW_CSV_FIELDS,
        REVIEW_HUMAN_FIELDS,
        REVIEW_INPUT_SHA256,
        REVIEW_SOURCE_FIELDS,
        REVIEWER_SLOTS,
        SOURCE_REVIEW_ARTIFACT_NAME,
        SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
        SOURCE_REVIEW_MANIFEST_SHA256,
        SOURCE_REVIEW_ZIP_SHA256,
        STATUS,
    )
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        build_file_inventory,
        canonical_json_bytes,
        read_csv,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from spec import (  # type: ignore
        ADJUDICATION_CASES,
        ADJUDICATION_CSV_FIELDS,
        ADJUDICATION_OUTPUT_FIELDS,
        ADJUDICATION_SOURCE_FIELDS,
        ARTIFACT_NAME,
        CONSENSUS_CASES,
        DECISION_FIELDS,
        POLICY_ID,
        REVIEW_CSV_FIELDS,
        REVIEW_HUMAN_FIELDS,
        REVIEW_INPUT_SHA256,
        REVIEW_SOURCE_FIELDS,
        REVIEWER_SLOTS,
        SOURCE_REVIEW_ARTIFACT_NAME,
        SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
        SOURCE_REVIEW_MANIFEST_SHA256,
        SOURCE_REVIEW_ZIP_SHA256,
        STATUS,
    )


EXPECTED_COUNTS = {
    "review_case": 5,
    "review_input": 3,
    "consensus_3_of_3": 3,
    "adjudication_required": 2,
}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _csv_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return next(csv.reader(handle))


def _validate_manifest(root: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        manifest = strict_json_object(root / "manifest.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"manifest: {exc}")
        return None
    if manifest.get("schema_id") != "D2LTargetedRepairReviewResultManifestV1":
        errors.append("manifest schema mismatch")
    if manifest.get("artifact_name") != ARTIFACT_NAME:
        errors.append("manifest artifact mismatch")
    if manifest.get("policy_id") != POLICY_ID:
        errors.append("manifest policy mismatch")
    if manifest.get("status") != STATUS:
        errors.append("manifest status mismatch")
    if manifest.get("counts") != EXPECTED_COUNTS:
        errors.append("manifest counts mismatch")
    if manifest.get("source_review_manifest_sha256") != SOURCE_REVIEW_MANIFEST_SHA256:
        errors.append("manifest source review binding mismatch")
    if manifest.get("review_input_sha256") != REVIEW_INPUT_SHA256:
        errors.append("manifest review input binding mismatch")
    if manifest.get("provider_call_count") != 0:
        errors.append("manifest provider call count must be zero")
    if manifest.get("official_contract_count") != 0:
        errors.append("manifest official contract count must be zero")
    if manifest.get("final_glossary_decision") is not None:
        errors.append("manifest contains a final glossary decision")
    if _manifest_self_hash(manifest) != manifest.get("manifest_sha256"):
        errors.append("manifest self hash mismatch")
    expected_files = build_file_inventory(root, {"manifest.json", "CHECKSUMS.sha256"})
    if manifest.get("files") != expected_files:
        errors.append("manifest file inventory mismatch")
    return manifest


def _validate_checksums(root: Path, errors: list[str]) -> None:
    try:
        lines = (root / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"checksums: {exc}")
        return
    actual: dict[str, str] = {}
    for line in lines:
        if " *" not in line:
            errors.append(f"malformed checksum line: {line!r}")
            continue
        digest, relative = line.split(" *", 1)
        if relative in actual:
            errors.append(f"duplicate checksum path: {relative}")
        actual[relative] = digest
    expected = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in root.rglob("*")
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    }
    if actual != dict(sorted(expected.items())):
        errors.append("checksum inventory mismatch")


def _load_review_inputs(
    root: Path, errors: list[str]
) -> dict[str, dict[str, dict[str, str]]]:
    reviews: dict[str, dict[str, dict[str, str]]] = {}
    canonical_sources: dict[str, dict[str, str]] | None = None
    all_case_ids: set[str] | None = None
    for slot in REVIEWER_SLOTS:
        path = root / "review_inputs" / f"{slot}.csv"
        try:
            if sha256_file(path) != REVIEW_INPUT_SHA256[slot]:
                errors.append(f"review input hash mismatch: {slot}")
            if _csv_headers(path) != list(REVIEW_CSV_FIELDS):
                errors.append(f"review input header mismatch: {slot}")
            rows = read_csv(path)
        except (OSError, UnicodeError, csv.Error, ValueError, StopIteration) as exc:
            errors.append(f"review input {slot}: {exc}")
            continue
        if len(rows) != 5 or len({row.get("review_case_id") for row in rows}) != 5:
            errors.append(f"review input must contain five unique rows: {slot}")
        by_case: dict[str, dict[str, str]] = {}
        source_projection: dict[str, dict[str, str]] = {}
        for row in rows:
            case_id = row.get("review_case_id", "")
            if not case_id:
                errors.append(f"blank review case ID: {slot}")
                continue
            if row.get("reviewer_slot") != slot:
                errors.append(f"reviewer slot mismatch: {slot}:{case_id}")
            if row.get("review_status") != "COMPLETE":
                errors.append(f"review is not complete: {slot}:{case_id}")
            payload = {field: row.get(field, "") for field in REVIEW_SOURCE_FIELDS}
            if sha256_bytes(canonical_json_bytes(payload)) != row.get(
                "source_payload_sha256"
            ):
                errors.append(f"review source payload hash mismatch: {slot}:{case_id}")
            by_case[case_id] = row
            source_projection[case_id] = {
                **payload,
                "source_payload_sha256": row.get("source_payload_sha256", ""),
            }
        reviews[slot] = by_case
        case_ids = set(by_case)
        if all_case_ids is None:
            all_case_ids = case_ids
        elif case_ids != all_case_ids:
            errors.append(f"review case identities differ: {slot}")
        if canonical_sources is None:
            canonical_sources = source_projection
        elif source_projection != canonical_sources:
            errors.append(f"review source projections differ: {slot}")
    return reviews


def _validate_vote(
    vote: Mapping[str, Any],
    slot: str,
    expected: Mapping[str, str],
    errors: list[str],
    label: str,
) -> None:
    if vote.get("reviewer_slot") != slot:
        errors.append(f"{label} reviewer slot mismatch: {slot}")
    if vote.get("review_input_sha256") != REVIEW_INPUT_SHA256[slot]:
        errors.append(f"{label} reviewer hash mismatch: {slot}")
    for field in REVIEW_HUMAN_FIELDS:
        if vote.get(field) != expected.get(field):
            errors.append(f"{label} reviewer vote drift: {slot}:{field}")
    claimed = vote.get("review_vote_sha256")
    payload = dict(vote)
    payload.pop("review_vote_sha256", None)
    if claimed != sha256_bytes(canonical_json_bytes(payload)):
        errors.append(f"{label} reviewer vote hash mismatch: {slot}")


def _validate_result_records(
    root: Path,
    reviews: Mapping[str, Mapping[str, Mapping[str, str]]],
    errors: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        consensus = strict_jsonl(root / "consensus_3_of_3_3.jsonl")
        adjudication = strict_jsonl(root / "adjudication_required_2.jsonl")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"result records: {exc}")
        return [], []
    if len(consensus) != 3:
        errors.append("consensus record count must be three")
    if len(adjudication) != 2:
        errors.append("adjudication record count must be two")
    if {(row.get("source_term"), row.get("split_label")) for row in consensus} != CONSENSUS_CASES:
        errors.append("consensus case identities mismatch")
    if {
        (row.get("source_term"), row.get("split_label")): row.get("issue_type")
        for row in adjudication
    } != ADJUDICATION_CASES:
        errors.append("adjudication case identities mismatch")

    seen_case_ids: set[str] = set()
    for kind, rows, hash_field in (
        ("consensus", consensus, "consensus_record_sha256"),
        ("adjudication", adjudication, "adjudication_record_sha256"),
    ):
        for index, record in enumerate(rows):
            label = f"{kind}[{index}]"
            if not verify_record(record, hash_field):
                errors.append(f"{label} self hash mismatch")
            case_id = record.get("review_case_id")
            if not isinstance(case_id, str) or not case_id:
                errors.append(f"{label} review case ID missing")
                continue
            if case_id in seen_case_ids:
                errors.append(f"duplicate result case: {case_id}")
            seen_case_ids.add(case_id)
            if record.get("policy_id") != POLICY_ID:
                errors.append(f"{label} policy mismatch")
            if record.get("review_input_sha256") != REVIEW_INPUT_SHA256:
                errors.append(f"{label} review input binding mismatch")
            if record.get("provider_call_count") != 0:
                errors.append(f"{label} provider call count must be zero")
            if record.get("official_contract_emitted") is not False:
                errors.append(f"{label} emits an official contract")
            if record.get("final_glossary_decision") is not None:
                errors.append(f"{label} contains a final glossary decision")
            votes = record.get("reviewer_votes")
            if not isinstance(votes, list) or len(votes) != 3:
                errors.append(f"{label} must contain three votes")
                continue
            for slot, vote in zip(REVIEWER_SLOTS, votes):
                expected = reviews.get(slot, {}).get(case_id)
                if not isinstance(vote, Mapping) or expected is None:
                    errors.append(f"{label} reviewer vote cannot be bound: {slot}")
                    continue
                _validate_vote(vote, slot, expected, errors, label)
            if kind == "consensus":
                vectors = {
                    tuple(reviews[slot][case_id][field] for field in DECISION_FIELDS)
                    for slot in REVIEWER_SLOTS
                    if case_id in reviews.get(slot, {})
                }
                if len(vectors) != 1:
                    errors.append(f"{label} does not have exact 3-of-3 agreement")
                expected_decisions = {
                    field: reviews["reviewer_1"][case_id][field]
                    for field in DECISION_FIELDS
                }
                if record.get("consensus_decisions") != expected_decisions:
                    errors.append(f"{label} consensus decision projection mismatch")
                if record.get("consensus_status") != "AGREEMENT_3_OF_3":
                    errors.append(f"{label} consensus status mismatch")
            elif record.get("status") != "ADJUDICATION_REQUIRED":
                errors.append(f"{label} adjudication status mismatch")
    expected_case_ids = set(reviews.get("reviewer_1", {}))
    if seen_case_ids != expected_case_ids:
        errors.append("result records do not cover all five review cases exactly once")
    return consensus, adjudication


def _validate_adjudication_template(
    root: Path,
    adjudication: list[Mapping[str, Any]],
    reviews: Mapping[str, Mapping[str, Mapping[str, str]]],
    errors: list[str],
) -> None:
    path = root / "adjudication_template_2.csv"
    try:
        if _csv_headers(path) != list(ADJUDICATION_CSV_FIELDS):
            errors.append("adjudication template header mismatch")
        rows = read_csv(path)
    except (OSError, UnicodeError, csv.Error, ValueError, StopIteration) as exc:
        errors.append(f"adjudication template: {exc}")
        return
    if len(rows) != 2 or len({row.get("review_case_id") for row in rows}) != 2:
        errors.append("adjudication template must contain two unique rows")
    records = {record.get("review_case_id"): record for record in adjudication}
    for row in rows:
        case_id = row.get("review_case_id", "")
        record = records.get(case_id)
        if record is None:
            errors.append(f"unknown adjudication template case: {case_id}")
            continue
        payload = {field: row.get(field, "") for field in ADJUDICATION_SOURCE_FIELDS}
        if sha256_bytes(canonical_json_bytes(payload)) != row.get("source_payload_sha256"):
            errors.append(f"adjudication source payload hash mismatch: {case_id}")
        if row.get("issue_type") != record.get("issue_type"):
            errors.append(f"adjudication issue mismatch: {case_id}")
        for slot in REVIEWER_SLOTS:
            review = reviews.get(slot, {}).get(case_id)
            if review is None:
                errors.append(f"adjudication review is missing: {slot}:{case_id}")
                continue
            for suffix, source_field in (
                ("definition_decision", "definition_decision"),
                ("corrected_definition_en", "corrected_definition_en"),
                ("candidate_set_decision", "candidate_set_decision"),
                ("review_notes", "review_notes"),
            ):
                if row.get(f"{slot}_{suffix}") != review.get(source_field):
                    errors.append(
                        f"adjudication reviewer projection mismatch: {slot}:{case_id}:{suffix}"
                    )
        for field in ADJUDICATION_OUTPUT_FIELDS:
            if row.get(field, "") != "":
                errors.append(f"adjudication output is prefilled: {case_id}:{field}")


def _validate_metadata(root: Path, errors: list[str]) -> None:
    required = {
        "ADJUDICATION_INSTRUCTIONS.md",
        "REVIEW_RESULT_REPORT.md",
        "commands.txt",
        "environment.json",
        "junit.xml",
        "lineage.json",
        "review_summary.json",
        "source/.gitattributes",
        "source/README.md",
        "source/tools/__init__.py",
        "source/tools/common.py",
        "source/tools/spec.py",
        "source/tools/build_review_result.py",
        "source/tools/validate_review_result.py",
        "source/tests/test_review_result.py",
    }
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    for relative in sorted(required - actual):
        errors.append(f"required release file is missing: {relative}")
    try:
        summary = strict_json_object(root / "review_summary.json")
        lineage = strict_json_object(root / "lineage.json")
        environment = strict_json_object(root / "environment.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"metadata: {exc}")
        return
    for name, payload in (("summary", summary), ("lineage", lineage)):
        if not verify_integrity(payload):
            errors.append(f"{name} self hash mismatch")
        if payload.get("provider_call_count") != 0:
            errors.append(f"{name} provider call count must be zero")
        if payload.get("final_glossary_decision") is not None:
            errors.append(f"{name} contains a final glossary decision")
    if summary.get("status") != STATUS or summary.get("counts") != EXPECTED_COUNTS:
        errors.append("summary status/counts mismatch")
    if summary.get("review_input_sha256") != REVIEW_INPUT_SHA256:
        errors.append("summary review input binding mismatch")
    if summary.get("official_contract_count") != 0:
        errors.append("summary official contract count must be zero")
    expected_lineage = {
        "source_review_artifact": SOURCE_REVIEW_ARTIFACT_NAME,
        "source_review_manifest_sha256": SOURCE_REVIEW_MANIFEST_SHA256,
        "source_review_manifest_physical_sha256": SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
        "source_review_zip_sha256": SOURCE_REVIEW_ZIP_SHA256,
        "review_input_sha256": REVIEW_INPUT_SHA256,
    }
    for field, expected in expected_lineage.items():
        if lineage.get(field) != expected:
            errors.append(f"lineage binding mismatch: {field}")
    if environment.get("network_calls") != 0 or environment.get("provider_calls") != 0:
        errors.append("environment reports network/provider calls")


def validate_artifact(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        return [f"artifact root: {exc}"]
    _validate_manifest(root, errors)
    _validate_checksums(root, errors)
    reviews = _load_review_inputs(root, errors)
    _, adjudication = _validate_result_records(root, reviews, errors)
    _validate_adjudication_template(root, adjudication, reviews, errors)
    _validate_metadata(root, errors)
    return errors


def validate_zip(zip_path: Path, artifact_root: Path) -> list[str]:
    errors: list[str] = []
    expected = {
        path.relative_to(artifact_root).as_posix(): sha256_file(path)
        for path in artifact_root.rglob("*")
        if path.is_file()
    }
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                errors.append("ZIP contains duplicate entries")
            for info in infos:
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
                    errors.append(f"ZIP contains unsafe path: {info.filename}")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    errors.append(f"ZIP contains symlink: {info.filename}")
            actual = {info.filename: sha256_bytes(archive.read(info)) for info in infos}
            if actual != expected:
                errors.append("ZIP entries differ from artifact directory")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"ZIP: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path)
    args = parser.parse_args()
    errors = validate_artifact(args.artifact_root)
    if args.zip_path is not None:
        errors.extend(validate_zip(args.zip_path.resolve(strict=True), args.artifact_root))
    result = {"status": "PASS" if not errors else "FAIL", "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
