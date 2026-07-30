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
        ADJUDICATED_CASES,
        ADJUDICATION_CSV_FIELDS,
        ADJUDICATION_INPUT_SHA256,
        ADJUDICATION_OUTPUT_FIELDS,
        ADJUDICATION_SOURCE_FIELDS,
        ARTIFACT_NAME,
        EXPECTED_CASES,
        MAIN_DATASET_AUTHORITY_COMMIT,
        MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
        MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        POLICY_ID,
        SOURCE_RESULT_ARTIFACT_NAME,
        SOURCE_RESULT_MANIFEST_PHYSICAL_SHA256,
        SOURCE_RESULT_MANIFEST_SHA256,
        SOURCE_RESULT_ZIP_SHA256,
        SOURCE_REVIEW_ARTIFACT_NAME,
        SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
        SOURCE_REVIEW_MANIFEST_SHA256,
        SOURCE_REVIEW_ZIP_SHA256,
        STATUS,
        SUMMARY_CSV_FIELDS,
        stable_id,
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
        ADJUDICATED_CASES,
        ADJUDICATION_CSV_FIELDS,
        ADJUDICATION_INPUT_SHA256,
        ADJUDICATION_OUTPUT_FIELDS,
        ADJUDICATION_SOURCE_FIELDS,
        ARTIFACT_NAME,
        EXPECTED_CASES,
        MAIN_DATASET_AUTHORITY_COMMIT,
        MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
        MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        POLICY_ID,
        SOURCE_RESULT_ARTIFACT_NAME,
        SOURCE_RESULT_MANIFEST_PHYSICAL_SHA256,
        SOURCE_RESULT_MANIFEST_SHA256,
        SOURCE_RESULT_ZIP_SHA256,
        SOURCE_REVIEW_ARTIFACT_NAME,
        SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
        SOURCE_REVIEW_MANIFEST_SHA256,
        SOURCE_REVIEW_ZIP_SHA256,
        STATUS,
        SUMMARY_CSV_FIELDS,
        stable_id,
    )


EXPECTED_COUNTS = {
    "reviewed_sense": 5,
    "reviewed_candidate": 15,
    "review_context": 25,
    "consensus_3_of_3": 3,
    "adjudicated": 2,
    "candidate_replacement": 1,
}
ADAM_DEFINITION = (
    "An adaptive optimization algorithm that updates model parameters using "
    "exponential moving averages of the gradient and its second moment."
)
STATISTICAL_POWER_REPLACEMENT = "độ mạnh của phép kiểm định"


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
    if manifest.get("schema_id") != "D2LTargetedRepairReviewCompleteManifestV1":
        errors.append("manifest schema mismatch")
    if manifest.get("artifact_name") != ARTIFACT_NAME:
        errors.append("manifest artifact mismatch")
    if manifest.get("policy_id") != POLICY_ID or manifest.get("status") != STATUS:
        errors.append("manifest policy/status mismatch")
    if manifest.get("counts") != EXPECTED_COUNTS:
        errors.append("manifest counts mismatch")
    bindings = {
        "source_review_manifest_sha256": SOURCE_REVIEW_MANIFEST_SHA256,
        "source_result_manifest_sha256": SOURCE_RESULT_MANIFEST_SHA256,
        "completed_adjudication_sha256": ADJUDICATION_INPUT_SHA256,
    }
    for field, expected in bindings.items():
        if manifest.get(field) != expected:
            errors.append(f"manifest binding mismatch: {field}")
    for field in (
        "provider_call_count",
        "official_contract_count",
        "stage_b_gold_autofill_count",
    ):
        if manifest.get(field) != 0:
            errors.append(f"manifest {field} must be zero")
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


def _validate_source_inputs(
    root: Path, errors: list[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = root / "source_inputs"
    try:
        review_manifest_path = base / "source_review_manifest.json"
        result_manifest_path = base / "source_result_manifest.json"
        if sha256_file(review_manifest_path) != SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256:
            errors.append("copied source review manifest physical hash mismatch")
        if sha256_file(result_manifest_path) != SOURCE_RESULT_MANIFEST_PHYSICAL_SHA256:
            errors.append("copied source result manifest physical hash mismatch")
        review_manifest = strict_json_object(review_manifest_path)
        result_manifest = strict_json_object(result_manifest_path)
        if review_manifest.get("artifact_name") != SOURCE_REVIEW_ARTIFACT_NAME:
            errors.append("copied source review artifact identity mismatch")
        if result_manifest.get("artifact_name") != SOURCE_RESULT_ARTIFACT_NAME:
            errors.append("copied source result artifact identity mismatch")
        if (
            review_manifest.get("manifest_sha256") != SOURCE_REVIEW_MANIFEST_SHA256
            or _manifest_self_hash(review_manifest) != SOURCE_REVIEW_MANIFEST_SHA256
        ):
            errors.append("copied source review manifest self hash mismatch")
        if (
            result_manifest.get("manifest_sha256") != SOURCE_RESULT_MANIFEST_SHA256
            or _manifest_self_hash(result_manifest) != SOURCE_RESULT_MANIFEST_SHA256
        ):
            errors.append("copied source result manifest self hash mismatch")
        for relative, manifest in (
            ("repair_sense_proposals_5.jsonl", review_manifest),
            ("candidate_proposals_15.jsonl", review_manifest),
            ("evidence_contexts_25.jsonl", review_manifest),
            ("repair_cases_5.csv", review_manifest),
            ("consensus_3_of_3_3.jsonl", result_manifest),
            ("adjudication_required_2.jsonl", result_manifest),
        ):
            metadata = manifest.get("files", {}).get(relative)
            if not isinstance(metadata, Mapping) or sha256_file(base / relative) != metadata.get(
                "sha256"
            ):
                errors.append(f"copied source input drift: {relative}")
        proposals = strict_jsonl(base / "repair_sense_proposals_5.jsonl")
        candidates = strict_jsonl(base / "candidate_proposals_15.jsonl")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"source inputs: {exc}")
        return [], []
    return proposals, candidates


def _validate_completed_adjudication(root: Path, errors: list[str]) -> None:
    path = root / "adjudication_template_2_completed.csv"
    try:
        if sha256_file(path) != ADJUDICATION_INPUT_SHA256:
            errors.append("completed adjudication physical hash mismatch")
        if _csv_headers(path) != list(ADJUDICATION_CSV_FIELDS):
            errors.append("completed adjudication header mismatch")
        rows = read_csv(path)
    except (OSError, UnicodeError, csv.Error, ValueError, StopIteration) as exc:
        errors.append(f"completed adjudication: {exc}")
        return
    if len(rows) != 2 or {
        (row.get("source_term"), row.get("split_label")) for row in rows
    } != ADJUDICATED_CASES:
        errors.append("completed adjudication identities mismatch")
    for row in rows:
        payload = {field: row.get(field, "") for field in ADJUDICATION_SOURCE_FIELDS}
        if sha256_bytes(canonical_json_bytes(payload)) != row.get("source_payload_sha256"):
            errors.append(f"adjudication source self hash mismatch: {row.get('source_term')}")
        if row.get("adjudication_status") != "COMPLETE":
            errors.append(f"adjudication is incomplete: {row.get('source_term')}")
        if not row.get("adjudication_notes", "").strip():
            errors.append(f"adjudication notes are missing: {row.get('source_term')}")


def _validate_resolved_records(
    root: Path,
    source_proposals: list[Mapping[str, Any]],
    source_candidates: list[Mapping[str, Any]],
    errors: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        senses = strict_jsonl(root / "reviewed_senses_5.jsonl")
        candidates = strict_jsonl(root / "reviewed_candidates_15.jsonl")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"reviewed records: {exc}")
        return [], []
    if len(senses) != 5 or len({row.get("review_case_id") for row in senses}) != 5:
        errors.append("reviewed sense count/identity mismatch")
    if len(candidates) != 15 or len({row.get("candidate_id") for row in candidates}) != 15:
        errors.append("reviewed candidate count/identity mismatch")
    if {(row.get("source_term"), row.get("split_label")) for row in senses} != EXPECTED_CASES:
        errors.append("reviewed sense case identities mismatch")
    proposal_by_case = {row.get("review_case_id"): row for row in source_proposals}
    source_candidate_by_id = {row.get("candidate_id"): row for row in source_candidates}
    candidates_by_sense: dict[str, list[Mapping[str, Any]]] = {}
    for index, row in enumerate(candidates):
        if not verify_record(row, "reviewed_candidate_sha256"):
            errors.append(f"reviewed candidate self hash mismatch: {index}")
        if row.get("human_review_status") != "COMPLETE":
            errors.append(f"reviewed candidate is incomplete: {row.get('candidate_id')}")
        if row.get("provider_call_count") != 0 or row.get("official_contract_emitted") is not False:
            errors.append(f"reviewed candidate boundary violation: {row.get('candidate_id')}")
        if row.get("final_glossary_decision") is not None:
            errors.append(f"reviewed candidate contains final decision: {row.get('candidate_id')}")
        source = source_candidate_by_id.get(row.get("source_candidate_id"))
        if source is None or row.get("source_candidate_proposal_sha256") != source.get(
            "candidate_proposal_sha256"
        ):
            errors.append(f"reviewed candidate source binding mismatch: {row.get('candidate_id')}")
        candidates_by_sense.setdefault(str(row.get("output_sense_id")), []).append(row)
    replacements = [
        row for row in candidates if row.get("candidate_resolution") == "REPLACED_BY_ADJUDICATION"
    ]
    if len(replacements) != 1:
        errors.append("exactly one candidate replacement is required")
    else:
        replacement = replacements[0]
        expected_id = stable_id(
            "candidate_",
            str(replacement.get("output_sense_id")),
            STATISTICAL_POWER_REPLACEMENT,
            "v1",
        )
        if (
            replacement.get("source_term") != "statistical power"
            or replacement.get("candidate_slot") != "CANDIDATE_2"
            or replacement.get("candidate_target_vi") != STATISTICAL_POWER_REPLACEMENT
            or replacement.get("candidate_id") != expected_id
        ):
            errors.append("statistical power candidate replacement mismatch")
    for index, row in enumerate(senses):
        if not verify_record(row, "reviewed_sense_sha256"):
            errors.append(f"reviewed sense self hash mismatch: {index}")
        proposal = proposal_by_case.get(row.get("review_case_id"))
        if proposal is None:
            errors.append(f"reviewed sense source proposal missing: {row.get('review_case_id')}")
            continue
        for field, source_field in (
            ("output_sense_id", "output_sense_id"),
            ("parent_sense_id", "parent_sense_id"),
            ("source_term", "source_term"),
            ("split", "split"),
            ("split_label", "split_label"),
            ("part_of_speech", "proposed_part_of_speech"),
            ("scope", "proposed_scope"),
            ("evidence_context_ids", "evidence_context_ids"),
        ):
            if row.get(field) != proposal.get(source_field):
                errors.append(f"reviewed sense source projection mismatch: {row.get('review_case_id')}:{field}")
        if row.get("source_sense_proposal_sha256") != proposal.get("sense_proposal_sha256"):
            errors.append(f"reviewed sense source hash mismatch: {row.get('review_case_id')}")
        if row.get("review_status") != "COMPLETE":
            errors.append(f"reviewed sense is incomplete: {row.get('review_case_id')}")
        if row.get("provider_call_count") != 0 or row.get("official_contract_emitted") is not False:
            errors.append(f"reviewed sense boundary violation: {row.get('review_case_id')}")
        if row.get("final_glossary_decision") is not None:
            errors.append(f"reviewed sense contains final decision: {row.get('review_case_id')}")
        linked = sorted(
            candidates_by_sense.get(str(row.get("output_sense_id")), []),
            key=lambda item: str(item.get("candidate_slot")),
        )
        if (
            len(linked) != 3
            or row.get("candidate_ids") != [item.get("candidate_id") for item in linked]
            or row.get("candidate_targets_vi")
            != [item.get("candidate_target_vi") for item in linked]
            or len({str(item.get("candidate_target_vi")).casefold() for item in linked}) != 3
        ):
            errors.append(f"reviewed sense candidate linkage mismatch: {row.get('review_case_id')}")
        if row.get("source_term") == "Adam" and row.get("definition_en") != ADAM_DEFINITION:
            errors.append("Adam adjudicated definition mismatch")
        if row.get("source_term") != "Adam" and row.get("definition_en") != proposal.get(
            "proposed_definition_en"
        ):
            errors.append(f"unexpected definition rewrite: {row.get('review_case_id')}")
    return senses, candidates


def _validate_summary_csv(
    root: Path, senses: list[Mapping[str, Any]], errors: list[str]
) -> None:
    path = root / "review_complete_summary_5.csv"
    try:
        if _csv_headers(path) != list(SUMMARY_CSV_FIELDS):
            errors.append("review summary CSV header mismatch")
        rows = read_csv(path)
    except (OSError, UnicodeError, csv.Error, ValueError, StopIteration) as exc:
        errors.append(f"review summary CSV: {exc}")
        return
    if len(rows) != 5:
        errors.append("review summary CSV row count must be five")
    sense_by_case = {row.get("review_case_id"): row for row in senses}
    for row in rows:
        sense = sense_by_case.get(row.get("review_case_id"))
        if sense is None:
            errors.append(f"review summary CSV has unknown case: {row.get('review_case_id')}")
            continue
        expected = {
            "review_case_id": sense["review_case_id"],
            "output_sense_id": sense["output_sense_id"],
            "source_term": sense["source_term"],
            "split_label": sense["split_label"],
            "definition_en": sense["definition_en"],
            "part_of_speech": sense["part_of_speech"],
            "scope": sense["scope"],
            "candidate_1_vi": sense["candidate_targets_vi"][0],
            "candidate_2_vi": sense["candidate_targets_vi"][1],
            "candidate_3_vi": sense["candidate_targets_vi"][2],
            "resolution_method": sense["resolution_method"],
            "review_status": sense["review_status"],
        }
        if row != expected:
            errors.append(f"review summary CSV projection mismatch: {row.get('review_case_id')}")


def _validate_metadata(root: Path, errors: list[str]) -> None:
    required = {
        "REVIEW_COMPLETE_REPORT.md",
        "commands.txt",
        "environment.json",
        "junit.xml",
        "lineage.json",
        "review_complete_summary.json",
        "source/.gitattributes",
        "source/README.md",
        "source/tools/__init__.py",
        "source/tools/common.py",
        "source/tools/spec.py",
        "source/tools/build_complete_review.py",
        "source/tools/validate_complete_review.py",
        "source/tests/test_complete_review.py",
    }
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    for relative in sorted(required - actual):
        errors.append(f"required release file is missing: {relative}")
    try:
        summary = strict_json_object(root / "review_complete_summary.json")
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
    for field in ("official_contract_count", "stage_b_gold_autofill_count"):
        if summary.get(field) != 0:
            errors.append(f"summary {field} must be zero")
    lineage_bindings = {
        "source_review_artifact": SOURCE_REVIEW_ARTIFACT_NAME,
        "source_review_manifest_sha256": SOURCE_REVIEW_MANIFEST_SHA256,
        "source_review_manifest_physical_sha256": SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256,
        "source_review_zip_sha256": SOURCE_REVIEW_ZIP_SHA256,
        "source_result_artifact": SOURCE_RESULT_ARTIFACT_NAME,
        "source_result_manifest_sha256": SOURCE_RESULT_MANIFEST_SHA256,
        "source_result_manifest_physical_sha256": SOURCE_RESULT_MANIFEST_PHYSICAL_SHA256,
        "source_result_zip_sha256": SOURCE_RESULT_ZIP_SHA256,
        "completed_adjudication_sha256": ADJUDICATION_INPUT_SHA256,
    }
    for field, expected in lineage_bindings.items():
        if lineage.get(field) != expected:
            errors.append(f"lineage binding mismatch: {field}")
    if lineage.get("canonical_main_dataset_authority") != {
        "main_commit": MAIN_DATASET_AUTHORITY_COMMIT,
        "manifest_sha256": MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
        "accepted_zip_sha256": MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        "relationship": "SEPARATE_TARGETED_REPAIR_REVIEW_ARTIFACT",
    }:
        errors.append("lineage canonical authority binding mismatch")
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
    source_proposals, source_candidates = _validate_source_inputs(root, errors)
    _validate_completed_adjudication(root, errors)
    senses, _ = _validate_resolved_records(
        root, source_proposals, source_candidates, errors
    )
    _validate_summary_csv(root, senses, errors)
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
