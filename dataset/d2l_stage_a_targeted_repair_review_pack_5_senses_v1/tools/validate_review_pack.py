from __future__ import annotations

import argparse
import csv
import json
import re
import zipfile
from collections import Counter
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
        ARTIFACT_NAME,
        CASE_SPECS,
        EXPECTED_BLOCK_IDS,
        EXPECTED_OUTPUT_SENSE_IDS,
        EXPECTED_PARENT_IDS,
        MAIN_DATASET_AUTHORITY_COMMIT,
        MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
        MAIN_DATASET_AUTHORITY_PIN_PHYSICAL_SHA256,
        MAIN_DATASET_AUTHORITY_PIN_SHA256,
        MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        POLICY_ID,
        REJECTED_PARENT_CONTEXTS,
        REVIEW_CSV_FIELDS,
        REVIEW_HUMAN_FIELDS,
        REVIEW_SOURCE_FIELDS,
        REVIEWER_SLOTS,
        SOURCE_DOCUMENT_REF,
        SOURCE_DOCUMENT_SHA256,
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
        ARTIFACT_NAME,
        CASE_SPECS,
        EXPECTED_BLOCK_IDS,
        EXPECTED_OUTPUT_SENSE_IDS,
        EXPECTED_PARENT_IDS,
        MAIN_DATASET_AUTHORITY_COMMIT,
        MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
        MAIN_DATASET_AUTHORITY_PIN_PHYSICAL_SHA256,
        MAIN_DATASET_AUTHORITY_PIN_SHA256,
        MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        POLICY_ID,
        REJECTED_PARENT_CONTEXTS,
        REVIEW_CSV_FIELDS,
        REVIEW_HUMAN_FIELDS,
        REVIEW_SOURCE_FIELDS,
        REVIEWER_SLOTS,
        SOURCE_DOCUMENT_REF,
        SOURCE_DOCUMENT_SHA256,
        STATUS,
    )


WINDOWS_ABSOLUTE = re.compile(r"(?:^|[\s\"'])[A-Za-z]:[\\/]")
UNC_PATH = re.compile(r"(?:^|[\s\"'])\\\\[^\\\s]+\\")


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _validate_manifest(root: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        manifest = strict_json_object(root / "manifest.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"manifest: {exc}")
        return None
    if manifest.get("schema_id") != "D2LTargetedRepairReviewManifestV1":
        errors.append("manifest schema mismatch")
    if manifest.get("artifact_name") != ARTIFACT_NAME:
        errors.append("manifest artifact name mismatch")
    if manifest.get("policy_id") != POLICY_ID:
        errors.append("manifest policy mismatch")
    if manifest.get("status") != STATUS:
        errors.append("manifest status mismatch")
    if manifest.get("counts") != {
        "candidate": 15,
        "output_sense": 5,
        "parent": 4,
        "review_context": 25,
        "rejected_parent_evidence": 2,
        "reviewer_template": 3,
    }:
        errors.append("manifest counts mismatch")
    if _manifest_self_hash(manifest) != manifest.get("manifest_sha256"):
        errors.append("manifest self hash mismatch")
    expected_files = build_file_inventory(
        root, {"manifest.json", "CHECKSUMS.sha256"}
    )
    if manifest.get("files") != expected_files:
        errors.append("manifest file inventory mismatch")
    for field in (
        "provider_call_count",
        "stage_b_gold_autofill_count",
        "official_contract_count",
    ):
        if manifest.get(field) != 0:
            errors.append(f"manifest {field} must be zero")
    if manifest.get("final_glossary_decision") is not None:
        errors.append("manifest contains a final glossary decision")
    if manifest.get("canonical_main_dataset_authority") != {
        "accepted_zip_sha256": MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        "main_commit": MAIN_DATASET_AUTHORITY_COMMIT,
        "manifest_sha256": MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
        "pin_physical_sha256": MAIN_DATASET_AUTHORITY_PIN_PHYSICAL_SHA256,
        "pin_self_sha256": MAIN_DATASET_AUTHORITY_PIN_SHA256,
        "relationship": "SEPARATE_TARGETED_REPAIR_REVIEW_ARTIFACT",
    }:
        errors.append("canonical Main Dataset authority binding mismatch")
    return manifest


def _validate_checksums(root: Path, errors: list[str]) -> None:
    path = root / "CHECKSUMS.sha256"
    try:
        lines = path.read_text(encoding="ascii").splitlines()
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


def _contains_absolute_path(value: Any) -> bool:
    if isinstance(value, str):
        return bool(WINDOWS_ABSOLUTE.search(value) or UNC_PATH.search(value))
    if isinstance(value, list):
        return any(_contains_absolute_path(item) for item in value)
    if isinstance(value, Mapping):
        return any(_contains_absolute_path(item) for item in value.values())
    return False


def _load_records(root: Path, errors: list[str]) -> dict[str, list[dict[str, Any]]]:
    files = {
        "proposals": "repair_sense_proposals_5.jsonl",
        "candidates": "candidate_proposals_15.jsonl",
        "evidence": "evidence_contexts_25.jsonl",
        "rejected": "rejected_parent_evidence_2.jsonl",
        "pending": "pending_parent_records_4.jsonl",
    }
    loaded: dict[str, list[dict[str, Any]]] = {}
    for key, relative in files.items():
        try:
            loaded[key] = strict_jsonl(root / relative)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{relative}: {exc}")
            loaded[key] = []
    return loaded


def _validate_record_surface(records: Mapping[str, list[dict[str, Any]]], errors: list[str]) -> None:
    expected = {
        "proposals": (5, "sense_proposal_sha256"),
        "candidates": (15, "candidate_proposal_sha256"),
        "evidence": (25, "evidence_record_sha256"),
        "rejected": (2, "rejection_record_sha256"),
        "pending": (4, "pending_record_sha256"),
    }
    for key, (count, hash_field) in expected.items():
        rows = records[key]
        if len(rows) != count:
            errors.append(f"{key} count must be {count}")
        for index, row in enumerate(rows):
            if not verify_record(row, hash_field):
                errors.append(f"{key}[{index}] self hash mismatch")
            if _contains_absolute_path(row):
                errors.append(f"{key}[{index}] contains an absolute path")


def _build_source_document_index(source_document: Path) -> dict[str, dict[str, Any]]:
    if sha256_file(source_document) != SOURCE_DOCUMENT_SHA256:
        raise ValueError("D2L source document hash mismatch")
    document = strict_json_object(source_document)
    index: dict[str, dict[str, Any]] = {}
    chapters = document.get("chapters")
    if not isinstance(chapters, list):
        raise ValueError("D2L source document chapters must be an array")
    for chapter_position, chapter in enumerate(chapters):
        if not isinstance(chapter, Mapping) or not isinstance(chapter.get("blocks"), list):
            raise ValueError("D2L source document chapter shape is invalid")
        for block_position, block in enumerate(chapter["blocks"]):
            if not isinstance(block, Mapping) or not isinstance(block.get("block_id"), str):
                raise ValueError("D2L source document block shape is invalid")
            index[block["block_id"]] = {
                "chapter": chapter,
                "chapter_position": chapter_position,
                "block": block,
                "block_position": block_position,
            }
    return index


def _validate_evidence(
    records: Mapping[str, list[dict[str, Any]]],
    source_document: Path | None,
    errors: list[str],
) -> None:
    evidence = records["evidence"]
    if {row.get("output_sense_id") for row in evidence} != EXPECTED_OUTPUT_SENSE_IDS:
        errors.append("evidence output-sense identities mismatch")
    if {row.get("parent_sense_id") for row in evidence} != EXPECTED_PARENT_IDS:
        errors.append("evidence parent identities mismatch")
    if {row.get("block_id") for row in evidence} != EXPECTED_BLOCK_IDS:
        errors.append("evidence block identities mismatch")
    if Counter(row.get("output_sense_id") for row in evidence) != Counter(
        {sense_id: 5 for sense_id in EXPECTED_OUTPUT_SENSE_IDS}
    ):
        errors.append("each output sense must have exactly five evidence contexts")
    if len({row.get("context_id") for row in evidence}) != 25:
        errors.append("evidence context IDs must be unique")
    for row in evidence:
        if row.get("synthetic") is not False:
            errors.append(f"review evidence is synthetic: {row.get('context_id')}")
        if row.get("source_artifact_ref") != SOURCE_DOCUMENT_REF:
            errors.append(f"source artifact reference mismatch: {row.get('context_id')}")
        if row.get("source_artifact_sha256") != SOURCE_DOCUMENT_SHA256:
            errors.append(f"source artifact hash mismatch: {row.get('context_id')}")
        for text_field, hash_field in (
            ("source_text", "source_text_sha256"),
            ("clean_text", "clean_text_sha256"),
        ):
            text = row.get(text_field)
            if not isinstance(text, str) or not text.strip():
                errors.append(f"empty evidence text: {row.get('context_id')}:{text_field}")
            elif sha256_bytes(text.encode("utf-8")) != row.get(hash_field):
                errors.append(f"evidence text hash mismatch: {row.get('context_id')}:{text_field}")
        if row.get("provider_call_count") != 0 or row.get("final_glossary_decision") is not None:
            errors.append(f"evidence boundary violation: {row.get('context_id')}")

    if source_document is None:
        return
    try:
        source_index = _build_source_document_index(source_document.resolve(strict=True))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"source document: {exc}")
        return
    for row in evidence:
        block = source_index.get(row.get("block_id"))
        if block is None:
            errors.append(f"source block is missing: {row.get('block_id')}")
            continue
        source_block = block["block"]
        source_chapter = block["chapter"]
        checks = {
            "source_text": source_block.get("source_text"),
            "clean_text": source_block.get("clean_text"),
            "block_order_index": source_block.get("order_index"),
            "block_type": source_block.get("block_type"),
            "chapter_id": source_chapter.get("chapter_id"),
            "chapter_order_index": source_chapter.get("order_index"),
            "chapter_position": block["chapter_position"],
            "block_position": block["block_position"],
            "source_json_path": (
                f"$.chapters[{block['chapter_position']}].blocks"
                f"[{block['block_position']}]"
            ),
        }
        for field, expected in checks.items():
            if row.get(field) != expected:
                errors.append(f"source block drift: {row.get('context_id')}:{field}")


def _validate_candidates_and_proposals(
    records: Mapping[str, list[dict[str, Any]]], errors: list[str]
) -> None:
    candidates = records["candidates"]
    proposals = records["proposals"]
    if {row.get("output_sense_id") for row in candidates} != EXPECTED_OUTPUT_SENSE_IDS:
        errors.append("candidate output-sense identities mismatch")
    if Counter(row.get("output_sense_id") for row in candidates) != Counter(
        {sense_id: 3 for sense_id in EXPECTED_OUTPUT_SENSE_IDS}
    ):
        errors.append("each output sense must have exactly three candidates")
    if len({row.get("candidate_id") for row in candidates}) != 15:
        errors.append("candidate IDs must be unique")
    for sense_id in EXPECTED_OUTPUT_SENSE_IDS:
        targets = [
            row.get("candidate_target_vi", "").strip().casefold()
            for row in candidates
            if row.get("output_sense_id") == sense_id
        ]
        if len(targets) != 3 or len(set(targets)) != 3 or any(not row for row in targets):
            errors.append(f"candidate targets must be three distinct values: {sense_id}")
    for row in candidates:
        if row.get("provider_call_count") != 0 or row.get("final_glossary_decision") is not None:
            errors.append(f"candidate boundary violation: {row.get('candidate_id')}")
        if row.get("formation_method") == "REUSE_V3_CANDIDATE":
            if row.get("source_candidate_instance_id") != row.get("candidate_id"):
                errors.append(f"reused candidate identity mismatch: {row.get('candidate_id')}")
            if not row.get("source_candidate_instance_sha256"):
                errors.append(f"reused candidate omits source hash: {row.get('candidate_id')}")
        elif row.get("formation_method") != "DATASET_TARGETED_REPAIR_PROPOSAL":
            errors.append(f"unknown candidate formation method: {row.get('candidate_id')}")

    if len(proposals) != 5:
        return
    if {row.get("output_sense_id") for row in proposals} != EXPECTED_OUTPUT_SENSE_IDS:
        errors.append("proposal output-sense identities mismatch")
    if {row.get("parent_sense_id") for row in proposals} != EXPECTED_PARENT_IDS:
        errors.append("proposal parent identities mismatch")
    if len({row.get("review_case_id") for row in proposals}) != 5:
        errors.append("review case IDs must be unique")
    evidence_by_id = {row.get("context_id"): row for row in records["evidence"]}
    candidates_by_id = {row.get("candidate_id"): row for row in candidates}
    for proposal in proposals:
        sense_id = proposal.get("output_sense_id")
        evidence_ids = proposal.get("evidence_context_ids")
        candidate_ids = proposal.get("candidate_ids")
        if not isinstance(evidence_ids, list) or len(evidence_ids) != 5:
            errors.append(f"proposal evidence count mismatch: {sense_id}")
        elif any(evidence_by_id.get(row, {}).get("output_sense_id") != sense_id for row in evidence_ids):
            errors.append(f"proposal evidence join mismatch: {sense_id}")
        if not isinstance(candidate_ids, list) or len(candidate_ids) != 3:
            errors.append(f"proposal candidate count mismatch: {sense_id}")
        elif any(candidates_by_id.get(row, {}).get("output_sense_id") != sense_id for row in candidate_ids):
            errors.append(f"proposal candidate join mismatch: {sense_id}")
        if proposal.get("status") != "PENDING_HUMAN_REVIEW":
            errors.append(f"proposal is not pending human review: {sense_id}")
        if proposal.get("official_contract_emitted") is not False:
            errors.append(f"proposal claims an official contract: {sense_id}")
        if proposal.get("provider_call_count") != 0 or proposal.get("final_glossary_decision") is not None:
            errors.append(f"proposal boundary violation: {sense_id}")

    spec_by_output = {row["output_sense_id"]: row for row in CASE_SPECS}
    for proposal in proposals:
        spec = spec_by_output.get(proposal.get("output_sense_id"))
        if spec is None:
            continue
        for field in (
            "source_term",
            "parent_sense_id",
            "split_label",
            "proposed_definition_en",
            "proposed_part_of_speech",
            "proposed_scope",
            "repair_action",
            "proposal_basis",
        ):
            if proposal.get(field) != spec[field]:
                errors.append(f"proposal/spec drift: {proposal.get('output_sense_id')}:{field}")


def _expected_review_rows(
    records: Mapping[str, list[dict[str, Any]]]
) -> dict[str, dict[str, str]]:
    evidence_by_id = {row["context_id"]: row for row in records["evidence"]}
    candidate_by_id = {row["candidate_id"]: row for row in records["candidates"]}
    result: dict[str, dict[str, str]] = {}
    for proposal in records["proposals"]:
        contexts = [evidence_by_id[row] for row in proposal["evidence_context_ids"]]
        candidates = [candidate_by_id[row] for row in proposal["candidate_ids"]]
        row = {
            "schema_id": "D2LTargetedRepairHumanReviewRowV1",
            "review_case_id": proposal["review_case_id"],
            "output_sense_id": proposal["output_sense_id"],
            "parent_sense_id": proposal["parent_sense_id"],
            "parent_term_id": proposal["parent_term_id"],
            "source_term": proposal["source_term"],
            "split_label": proposal["split_label"],
            "proposed_definition_en": proposal["proposed_definition_en"],
            "proposed_part_of_speech": proposal["proposed_part_of_speech"],
            "proposed_scope": proposal["proposed_scope"],
            "repair_action": proposal["repair_action"],
            "proposal_basis": proposal["proposal_basis"],
            "context_evidence_ids": "|".join(proposal["evidence_context_ids"]),
            "context_block_ids": "|".join(row["block_id"] for row in contexts),
            "candidate_ids": "|".join(proposal["candidate_ids"]),
            "candidate_targets_vi": "|".join(
                row["candidate_target_vi"] for row in candidates
            ),
        }
        payload = {field: row[field] for field in REVIEW_SOURCE_FIELDS}
        row["source_payload_sha256"] = sha256_bytes(canonical_json_bytes(payload))
        result[row["review_case_id"]] = row
    return result


def _csv_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return next(reader)


def _validate_reviews(
    root: Path, records: Mapping[str, list[dict[str, Any]]], errors: list[str]
) -> None:
    expected = _expected_review_rows(records)
    try:
        cases = read_csv(root / "repair_cases_5.csv")
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        errors.append(f"repair cases: {exc}")
        cases = []
    if len(cases) != 5:
        errors.append("repair case CSV count must be five")
    for row in cases:
        expected_row = expected.get(row.get("review_case_id"))
        if expected_row is None or row != expected_row:
            errors.append(f"repair case source projection mismatch: {row.get('review_case_id')}")

    canonical_template_sources: dict[str, dict[str, str]] | None = None
    for slot in REVIEWER_SLOTS:
        path = root / "reviewer_templates" / f"{slot}.csv"
        try:
            if _csv_headers(path) != list(REVIEW_CSV_FIELDS):
                errors.append(f"review template header mismatch: {slot}")
            rows = read_csv(path)
        except (OSError, UnicodeError, csv.Error, ValueError, StopIteration) as exc:
            errors.append(f"review template {slot}: {exc}")
            continue
        if len(rows) != 5:
            errors.append(f"review template row count must be five: {slot}")
        source_projection: dict[str, dict[str, str]] = {}
        for row in rows:
            case_id = row.get("review_case_id")
            expected_row = expected.get(case_id)
            if expected_row is None:
                errors.append(f"unknown review case: {slot}:{case_id}")
                continue
            actual_source = {
                field: row.get(field, "")
                for field in (*REVIEW_SOURCE_FIELDS, "source_payload_sha256")
            }
            if actual_source != expected_row:
                errors.append(f"review source payload mismatch: {slot}:{case_id}")
            if row.get("reviewer_slot") != slot:
                errors.append(f"reviewer slot mismatch: {slot}:{case_id}")
            for field in REVIEW_HUMAN_FIELDS:
                if row.get(field, "") != "":
                    errors.append(f"review template is prefilled: {slot}:{case_id}:{field}")
            source_projection[case_id] = actual_source
        if canonical_template_sources is None:
            canonical_template_sources = source_projection
        elif source_projection != canonical_template_sources:
            errors.append(f"reviewer source projections differ: {slot}")


def _validate_rejected_and_pending(
    records: Mapping[str, list[dict[str, Any]]], errors: list[str]
) -> None:
    rejected = records["rejected"]
    expected_rejected = {
        (row["parent_sense_id"], row["source_context_id"], row["rejection_reason"])
        for row in REJECTED_PARENT_CONTEXTS
    }
    actual_rejected = {
        (row.get("parent_sense_id"), row.get("source_context_id"), row.get("rejection_reason"))
        for row in rejected
    }
    if actual_rejected != expected_rejected:
        errors.append("rejected-parent evidence ledger mismatch")
    for row in rejected:
        text = row.get("source_text")
        if not isinstance(text, str) or sha256_bytes(text.encode("utf-8")) != row.get(
            "source_text_sha256"
        ):
            errors.append(f"rejected evidence text hash mismatch: {row.get('source_context_id')}")
        if row.get("excluded_from_positive_evidence") is not True:
            errors.append(f"rejected evidence is not excluded: {row.get('source_context_id')}")

    pending = records["pending"]
    if {row.get("sense_id") for row in pending} != EXPECTED_PARENT_IDS:
        errors.append("pending parent ledger mismatch")
    if any(row.get("final_glossary_decision") is not None for row in pending):
        errors.append("pending parent contains a final glossary decision")


def _validate_metadata(root: Path, errors: list[str]) -> None:
    required = {
        "REVIEW_INSTRUCTIONS.md",
        "REVIEW_CASEBOOK.md",
        "RELEASE_REPORT.md",
        "commands.txt",
        "environment.json",
        "junit.xml",
        "lineage.json",
        "acceptance_gate_report.json",
        "source/.gitattributes",
        "source/README.md",
        "source/tools/__init__.py",
        "source/tools/common.py",
        "source/tools/spec.py",
        "source/tools/build_review_pack.py",
        "source/tools/validate_review_pack.py",
        "source/tests/test_review_pack.py",
    }
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    for relative in required - actual:
        errors.append(f"required release file is missing: {relative}")
    try:
        environment = strict_json_object(root / "environment.json")
        lineage = strict_json_object(root / "lineage.json")
        acceptance = strict_json_object(root / "acceptance_gate_report.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"metadata: {exc}")
        return
    if environment.get("network_calls") != 0 or environment.get("provider_calls") != 0:
        errors.append("environment reports network/provider calls")
    if environment.get("source_document_sha256") != SOURCE_DOCUMENT_SHA256:
        errors.append("environment source document hash mismatch")
    for name, payload in (("lineage", lineage), ("acceptance", acceptance)):
        if not verify_integrity(payload):
            errors.append(f"{name} self hash mismatch")
        if payload.get("final_glossary_decision") is not None:
            errors.append(f"{name} contains a final glossary decision")
    if lineage.get("canonical_main_dataset_authority") != {
        "accepted_zip_sha256": MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        "main_commit": MAIN_DATASET_AUTHORITY_COMMIT,
        "manifest_sha256": MAIN_DATASET_AUTHORITY_MANIFEST_SHA256,
        "pin_physical_sha256": MAIN_DATASET_AUTHORITY_PIN_PHYSICAL_SHA256,
        "pin_self_sha256": MAIN_DATASET_AUTHORITY_PIN_SHA256,
        "relationship": "IMMUTABLE_AUTHORITY_NOT_REBUILT_OR_ALTERED",
    }:
        errors.append("lineage canonical authority binding mismatch")
    excluded = lineage.get("parents", {}).get("excluded_local_11_candidate", {})
    if excluded.get("authority_status") != "EXCLUDED_FROM_MAIN_DATASET_AUTHORITY" or excluded.get(
        "use"
    ) != "NON_OVERLAP_GUARD_ONLY":
        errors.append("excluded local 11 candidate authority boundary mismatch")
    if acceptance.get("status") != STATUS:
        errors.append("acceptance status mismatch")
    checks = acceptance.get("checks")
    if not isinstance(checks, Mapping) or not checks or not all(checks.values()):
        errors.append("acceptance contains a failed check")
    if acceptance.get("counts") != {
        "candidate": 15,
        "output_sense": 5,
        "parent": 4,
        "review_context": 25,
        "rejected_parent_evidence": 2,
        "reviewer_template": 3,
    }:
        errors.append("acceptance counts mismatch")


def validate_artifact(root: Path, source_document: Path | None = None) -> list[str]:
    errors: list[str] = []
    root = root.resolve(strict=True)
    _validate_manifest(root, errors)
    _validate_checksums(root, errors)
    records = _load_records(root, errors)
    _validate_record_surface(records, errors)
    _validate_evidence(records, source_document, errors)
    _validate_candidates_and_proposals(records, errors)
    _validate_reviews(root, records, errors)
    _validate_rejected_and_pending(records, errors)
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
    parser.add_argument("--source-document", type=Path)
    parser.add_argument("--zip-path", type=Path)
    args = parser.parse_args()
    errors = validate_artifact(args.artifact_root, args.source_document)
    if args.zip_path is not None:
        errors.extend(
            validate_zip(
                args.zip_path.resolve(strict=True),
                args.artifact_root.resolve(strict=True),
            )
        )
    result = {
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
