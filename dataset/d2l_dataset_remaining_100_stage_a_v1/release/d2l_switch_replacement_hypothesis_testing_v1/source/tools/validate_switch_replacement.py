from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
from typing import Any, Mapping

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_deterministic_zip,
    build_file_inventory,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    verify_integrity,
)


REPLACED_TERM = "switch"
REPLACED_SENSE_ID = "d2lce_91002293cea2184b43995f47"
REPLACEMENT_TERM = "hypothesis testing"
REPLACEMENT_SENSE_ID = "d2lce_bad32719ece6439b4716d093"


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


def _blank_review() -> dict[str, Any]:
    return {
        "candidate_replacements": [],
        "candidate_set_decision": "",
        "corrected_definition_en": "",
        "corrected_part_of_speech": "",
        "corrected_scope": "",
        "definition_decision": "",
        "evidence_decision": "",
        "invalid_evidence_context_ids": [],
        "part_of_speech_decision": "",
        "proposed_split_labels": [],
        "review_notes": "",
        "review_status": "",
        "scope_decision": "",
        "sense_status": "",
    }


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
    if manifest.get("status") != "REPLACEMENT_SELECTED_PENDING_TWO_INDEPENDENT_REVIEWS_ZERO_PROVIDER":
        errors.append("manifest status mismatch")
    _validate_checksums(root, errors)

    expected_integrity = {
        "authority.json": "D2LSwitchReplacementAuthorityV1",
        "current_source_term_inventory_150.json": "D2LCurrentSourceTermInventory150V1",
        "replacement_selection.json": "D2LSwitchReplacementSelectionV1",
        "replacement_source.json": "D2LSwitchReplacementStageASourceV1",
        "source_evidence.json": "D2LSwitchReplacementSourceEvidenceV1",
        "validation_report.json": "D2LSwitchReplacementValidationReportV1",
    }
    payloads: dict[str, Mapping[str, Any]] = {}
    for name, schema_id in expected_integrity.items():
        try:
            payload = strict_json_object(root / name)
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(str(exc))
            continue
        payloads[name] = payload
        if payload.get("schema_id") != schema_id or not verify_integrity(payload):
            errors.append(f"{name}: integrity/schema mismatch")

    inventory = payloads.get("current_source_term_inventory_150.json", {})
    terms = inventory.get("source_terms_casefolded")
    if (
        not isinstance(terms, list)
        or inventory.get("source_term_count") != 150
        or len(terms) != 150
        or len(set(terms)) != 150
        or REPLACED_TERM not in terms
        or REPLACEMENT_TERM in terms
    ):
        errors.append("current source-term inventory/nonduplicate check mismatch")

    selection = payloads.get("replacement_selection.json", {})
    if (
        selection.get("replaced_sense_id") != REPLACED_SENSE_ID
        or selection.get("replaced_source_term") != REPLACED_TERM
        or selection.get("replacement_sense_id") != REPLACEMENT_SENSE_ID
        or selection.get("replacement_source_term") != REPLACEMENT_TERM
        or selection.get("replacement_status")
        != "SELECTED_PENDING_TWO_INDEPENDENT_REVIEWS"
    ):
        errors.append("replacement selection mismatch")

    source = payloads.get("replacement_source.json", {})
    source_payload = dict(source)
    source_payload.pop("integrity", None)
    if (
        source_payload.get("source_term") != REPLACEMENT_TERM
        or source_payload.get("sense_id") != REPLACEMENT_SENSE_ID
        or source_payload.get("term_id") != REPLACEMENT_SENSE_ID
        or source_payload.get("review_requirement")
        != "TWO_INDEPENDENT_STAGE_A_REVIEWS"
    ):
        errors.append("replacement source identity mismatch")
    candidates = source_payload.get("candidates")
    contexts = source_payload.get("evidence_contexts")
    if not isinstance(candidates, list) or len(candidates) != 3:
        errors.append("replacement must contain three candidates")
        candidates = []
    if len({row.get("candidate_id") for row in candidates}) != len(candidates) or len(
        {row.get("candidate_target_vi") for row in candidates}
    ) != len(candidates):
        errors.append("replacement candidates must be unique")
    for row in candidates:
        payload = {
            "candidate_id": row.get("candidate_id"),
            "candidate_slot": row.get("candidate_slot"),
            "candidate_target_vi": row.get("candidate_target_vi"),
        }
        if row.get("candidate_instance_sha256") != sha256_bytes(
            canonical_json_bytes(payload)
        ):
            errors.append("candidate instance hash mismatch")
    if not isinstance(contexts, list) or len(contexts) != 7:
        errors.append("replacement must contain seven review contexts")
        contexts = []
    if sum(row.get("context_role") == "PRIMARY" for row in contexts) != 5:
        errors.append("replacement must contain five primary contexts")
    if sum(row.get("context_role") == "BACKUP" for row in contexts) != 2:
        errors.append("replacement must contain two backup contexts")
    if len({row.get("context_id") for row in contexts}) != len(contexts):
        errors.append("replacement context IDs must be unique")
    for row in contexts:
        payload = dict(row)
        claimed = payload.pop("context_sha256", None)
        if claimed != sha256_bytes(canonical_json_bytes(payload)):
            errors.append("context self-hash mismatch")
        text = row.get("source_text")
        start = row.get("source_match_start_local")
        end = row.get("source_match_end_local")
        if (
            row.get("synthetic") is not False
            or row.get("boundary_only") is not False
            or row.get("positive_evidence_eligible") is not True
            or not isinstance(text, str)
            or not isinstance(start, int)
            or not isinstance(end, int)
            or text[start:end] != row.get("matched_surface")
            or row.get("content_sha256") != sha256_bytes(text.encode("utf-8"))
        ):
            errors.append("context evidence/provenance mismatch")

    try:
        candidate_provenance = strict_jsonl(root / "candidate_provenance_3.jsonl")
        context_provenance = strict_jsonl(root / "context_provenance_7.jsonl")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(str(exc))
        candidate_provenance = []
        context_provenance = []
    if {row.get("candidate_id") for row in candidate_provenance} != {
        row.get("candidate_id") for row in candidates
    } or len(candidate_provenance) != 3:
        errors.append("candidate provenance mismatch")
    if {row.get("context_id") for row in context_provenance} != {
        row.get("context_id") for row in contexts
    } or len(context_provenance) != 7:
        errors.append("context provenance mismatch")

    evidence = payloads.get("source_evidence.json", {})
    glossary_record = evidence.get("glossary_record")
    source_decisions = evidence.get("source_decisions")
    evidence_blocks = evidence.get("evidence_blocks")
    if (
        not isinstance(glossary_record, Mapping)
        or glossary_record.get("record_id") != REPLACEMENT_SENSE_ID
        or glossary_record.get("value", {}).get("canonical_source")
        != REPLACEMENT_TERM
        or not isinstance(source_decisions, list)
        or len(source_decisions) != 3
        or any(row.get("decision") != "admit" for row in source_decisions)
        or not isinstance(evidence_blocks, list)
        or len(evidence_blocks) != 9
    ):
        errors.append("sealed source evidence mismatch")
    block_map = {
        row.get("block_id"): row.get("text")
        for row in evidence_blocks or []
        if isinstance(row, Mapping)
    }
    for row in contexts:
        if block_map.get(row.get("block_id")) != row.get("source_text"):
            errors.append("review context does not match captured source block")

    roles: set[str] = set()
    source_sha = sha256_bytes(canonical_json_bytes(source_payload))
    for role in ("reviewer_1", "reviewer_2"):
        batch = root / "review_batches" / role
        try:
            review_input = strict_json_object(batch / "reviewer_input.json")
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(str(exc))
            continue
        roles.add(str(review_input.get("reviewer_slot")))
        cases = review_input.get("cases")
        if (
            review_input.get("case_count") != 1
            or not isinstance(cases, list)
            or len(cases) != 1
            or review_input.get("source_input_sha256") != source_sha
        ):
            errors.append(f"{role}: review batch count/source mismatch")
            continue
        case = cases[0]
        if (
            case.get("reviewer_slot") != role
            or case.get("source_payload") != source_payload
            or case.get("source_payload_sha256") != source_sha
            or case.get("review") != _blank_review()
        ):
            errors.append(f"{role}: review case binding is invalid")
        handoff_zip = root / "handoff" / f"switch_replacement_{role}.zip"
        with tempfile.TemporaryDirectory(prefix="switch-review-zip-") as name:
            rebuilt = Path(name) / "rebuilt.zip"
            build_deterministic_zip(batch, rebuilt)
            if not handoff_zip.is_file() or sha256_file(handoff_zip) != sha256_file(
                rebuilt
            ):
                errors.append(f"{role}: handoff ZIP mismatch")
    if roles != {"reviewer_1", "reviewer_2"}:
        errors.append("reviewer slots are not distinct")

    report = payloads.get("validation_report.json", {})
    if (
        report.get("candidate_count") != 3
        or report.get("context_count") != 7
        or report.get("primary_context_count") != 5
        or report.get("synthetic_context_count") != 0
        or report.get("reviewer_pack_count") != 2
        or report.get("nonduplicate_against_current_150") is not True
        or report.get("status")
        != "REPLACEMENT_SELECTED_PENDING_TWO_INDEPENDENT_REVIEWS_ZERO_PROVIDER"
    ):
        errors.append("validation report count/status mismatch")

    _validate_zero_provider(manifest, "manifest", errors)
    for name, payload in payloads.items():
        _validate_zero_provider(payload, name, errors)
    for label, value in {
        "candidate_provenance": candidate_provenance,
        "context_provenance": context_provenance,
    }.items():
        _validate_zero_provider(value, label, errors)
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
