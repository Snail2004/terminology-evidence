from __future__ import annotations

import json
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[3]
COMMON_TOOLS = REPO_ROOT / "dataset" / "d2l_dataset_50_senses_fast_track_stage_a_v1" / "tools"
if str(COMMON_TOOLS) not in sys.path:
    sys.path.insert(0, str(COMMON_TOOLS))

from common import (  # type: ignore  # noqa: E402
    build_file_inventory,
    canonical_json_bytes,
    sha256_bytes,
    sha256_file,
    strict_json_file,
    strict_jsonl,
    verify_record,
)
from build_remaining100_stage_a import (  # type: ignore  # noqa: E402
    ALLOWED_SENSE_STATUS,
    EXCLUDED_PARENT_IDS,
    POLICY_ID,
    RISK_BY_STRATUM,
    STATUS,
    _blank_review,
    _eligible_context,
    _manifest_self_hash,
)


def _error(errors: list[str], message: str) -> None:
    errors.append(message)


def _check_checksums(root: Path, errors: list[str]) -> None:
    checksum_path = root / "CHECKSUMS.sha256"
    if not checksum_path.is_file():
        _error(errors, "CHECKSUMS.sha256 is missing")
        return
    actual: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="ascii").splitlines():
        if " *" not in line:
            _error(errors, "malformed checksum line")
            continue
        digest, relative = line.split(" *", 1)
        if relative in actual:
            _error(errors, f"duplicate checksum path: {relative}")
        actual[relative] = digest
    expected = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(root, {"CHECKSUMS.sha256"}).items()
    }
    if actual != expected:
        _error(errors, "checksum inventory mismatch")


def _load(path: Path, errors: list[str]) -> list[dict[str, Any]]:
    try:
        return strict_jsonl(path)
    except (OSError, UnicodeError, ValueError) as exc:
        _error(errors, f"{path.name}: {exc}")
        return []


def _validate_parent_subset(
    root: Path,
    terms: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    contexts: list[dict[str, Any]],
    errors: list[str],
) -> None:
    snapshot_terms = _load(root / "parent_snapshot_term_senses.jsonl", errors)
    snapshot_candidates = _load(root / "parent_snapshot_candidates.jsonl", errors)
    snapshot_contexts = _load(root / "parent_snapshot_contexts.jsonl", errors)
    if snapshot_terms != terms:
        _error(errors, "term_senses_100 is not byte-equivalent to its parent snapshot")
    if snapshot_candidates != candidates:
        _error(errors, "candidate_instances_300 is not byte-equivalent to its parent snapshot")
    if snapshot_contexts != contexts:
        _error(errors, "contexts_selected_100 is not byte-equivalent to its parent snapshot")
    for row in terms:
        if not verify_record(row, "term_sense_sha256"):
            _error(errors, f"term-sense parent hash mismatch: {row.get('sense_id')}")
    for row in candidates:
        if not verify_record(row, "candidate_instance_sha256"):
            _error(errors, f"candidate parent hash mismatch: {row.get('candidate_instance_id')}")
    for row in contexts:
        if not verify_record(row, "context_sha256"):
            _error(errors, f"context parent hash mismatch: {row.get('context_id')}")


def _validate_review_payload(
    payload: Mapping[str, Any],
    expected_batch: str,
    expected_slot: str,
    errors: list[str],
) -> list[dict[str, Any]]:
    cases = payload.get("cases")
    if payload.get("schema_id") != "D2LRemaining100StageAReviewerInputV1":
        _error(errors, f"{expected_batch}/{expected_slot}: schema mismatch")
    if payload.get("batch_id") != expected_batch or payload.get("reviewer_slot") != expected_slot:
        _error(errors, f"{expected_batch}/{expected_slot}: identity mismatch")
    if not isinstance(cases, list):
        _error(errors, f"{expected_batch}/{expected_slot}: cases must be a list")
        return []
    if payload.get("case_count") != len(cases) or payload.get("sense_count") != len(cases):
        _error(errors, f"{expected_batch}/{expected_slot}: case count mismatch")
    source_index = []
    seen: set[str] = set()
    for case in cases:
        if not isinstance(case, Mapping):
            _error(errors, f"{expected_batch}/{expected_slot}: case is not an object")
            continue
        case_id = str(case.get("case_id"))
        if case_id in seen:
            _error(errors, f"{expected_batch}/{expected_slot}: duplicate case {case_id}")
        seen.add(case_id)
        source = case.get("source_payload")
        if not isinstance(source, Mapping):
            _error(errors, f"{expected_batch}/{expected_slot}: missing source payload")
            continue
        source_hash = sha256_bytes(canonical_json_bytes(source))
        if case.get("source_payload_sha256") != source_hash:
            _error(errors, f"{expected_batch}/{expected_slot}: source payload hash mismatch {case_id}")
        if case.get("review") != _blank_review():
            _error(errors, f"{expected_batch}/{expected_slot}: review is prefilled {case_id}")
        if case.get("provider_call_count") != 0 or case.get("stage_b_gold_label") is not None:
            _error(errors, f"{expected_batch}/{expected_slot}: result fields are not blank {case_id}")
        if source.get("policy_id") != POLICY_ID:
            _error(errors, f"{expected_batch}/{expected_slot}: source policy mismatch {case_id}")
        contexts = source.get("evidence_contexts")
        candidates = source.get("candidates")
        if not isinstance(contexts, list) or not contexts:
            _error(errors, f"{expected_batch}/{expected_slot}: no evidence contexts {case_id}")
        if not isinstance(candidates, list) or len(candidates) != 3:
            _error(errors, f"{expected_batch}/{expected_slot}: candidate closure mismatch {case_id}")
        if isinstance(contexts, list):
            for context in contexts:
                if not isinstance(context, Mapping) or not context.get("context_id"):
                    _error(errors, f"{expected_batch}/{expected_slot}: invalid context {case_id}")
        source_index.append({"case_id": case_id, "source_payload_sha256": source_hash})
    expected_index = sha256_bytes(canonical_json_bytes(source_index))
    if payload.get("source_input_sha256") != expected_index:
        _error(errors, f"{expected_batch}/{expected_slot}: source input hash mismatch")
    return [dict(case) for case in cases if isinstance(case, Mapping)]


def _validate_batches(root: Path, terms: list[dict[str, Any]], errors: list[str]) -> None:
    try:
        batch_index = strict_json_file(root / "batch_index.json")
    except (OSError, UnicodeError, ValueError) as exc:
        _error(errors, f"batch_index: {exc}")
        return
    batches = batch_index.get("batches") if isinstance(batch_index, Mapping) else None
    if not isinstance(batches, list) or len(batches) != 10:
        _error(errors, "batch count is not 10")
        return
    all_ids: list[str] = []
    reviewer_1_all: list[dict[str, Any]] = []
    reviewer_2_all: list[dict[str, Any]] = []
    term_by_id = {str(row.get("sense_id")): row for row in terms}
    for batch in batches:
        batch_id = str(batch.get("batch_id"))
        sense_ids = batch.get("sense_ids")
        if not isinstance(sense_ids, list) or len(sense_ids) != 10:
            _error(errors, f"{batch_id}: batch must contain 10 senses")
            continue
        if any(str(sense_id) not in term_by_id for sense_id in sense_ids):
            _error(errors, f"{batch_id}: unknown sense ID")
        all_ids.extend(str(sense_id) for sense_id in sense_ids)
        batch_dir = root / "batches" / batch_id
        try:
            source_rows = strict_json_file(batch_dir / "review_cases.json")
            input_1 = strict_json_file(batch_dir / "reviewer_1_input.json")
            input_2 = strict_json_file(batch_dir / "reviewer_2_input.json")
        except (OSError, UnicodeError, ValueError) as exc:
            _error(errors, f"{batch_id}: {exc}")
            continue
        if not isinstance(source_rows, list) or {str(row.get("sense_id")) for row in source_rows} != set(sense_ids):
            _error(errors, f"{batch_id}: source case sense IDs mismatch")
        cases_1 = _validate_review_payload(input_1, batch_id, "reviewer_1", errors)
        cases_2 = _validate_review_payload(input_2, batch_id, "reviewer_2", errors)
        reviewer_1_all.extend(cases_1)
        reviewer_2_all.extend(cases_2)
        allowed_2 = {
            str(row.get("sense_id"))
            for row in source_rows
            if isinstance(row, Mapping) and row.get("risk_class") in {"R3_AMBIGUOUS", "R4_SPLIT_OR_POS_RISK"}
        }
        actual_2 = {
            str(case.get("source_payload", {}).get("sense_id"))
            for case in cases_2
        }
        if actual_2 != allowed_2:
            _error(errors, f"{batch_id}: reviewer 2 risk routing mismatch")
        for slot, relative, expected_sha in (
            ("reviewer_1", batch.get("reviewer_1_handoff_zip"), batch.get("reviewer_1_handoff_zip_sha256")),
            ("reviewer_2", batch.get("reviewer_2_handoff_zip"), batch.get("reviewer_2_handoff_zip_sha256")),
        ):
            path = root / str(relative)
            if not path.is_file() or sha256_file(path) != expected_sha:
                _error(errors, f"{batch_id}/{slot}: handoff ZIP hash mismatch")
            elif path.suffix == ".zip":
                try:
                    with zipfile.ZipFile(path) as archive:
                        names = set(archive.namelist())
                    if "review_input.json" not in names or "REVIEW_INSTRUCTIONS.md" not in names:
                        _error(errors, f"{batch_id}/{slot}: handoff ZIP is incomplete")
                except zipfile.BadZipFile:
                    _error(errors, f"{batch_id}/{slot}: invalid handoff ZIP")
    if len(all_ids) != 100 or len(set(all_ids)) != 100:
        _error(errors, "batch partition is not an exact 100-sense partition")
    if len(reviewer_1_all) != 100 or len(reviewer_2_all) != 65:
        _error(errors, "reviewer case totals mismatch")
    for slot, expected in (("reviewer_1", 100), ("reviewer_2", 65)):
        try:
            full = strict_json_file(root / f"{slot}_full_input.json")
        except (OSError, UnicodeError, ValueError) as exc:
            _error(errors, f"{slot} full input: {exc}")
            continue
        cases = _validate_review_payload(full, "all_batches", slot, errors)
        if len(cases) != expected:
            _error(errors, f"{slot} full input count mismatch")
        expected_cases = reviewer_1_all if slot == "reviewer_1" else reviewer_2_all
        if [case.get("case_id") for case in cases] != [case.get("case_id") for case in expected_cases]:
            _error(errors, f"{slot} full input differs from batch inputs")


def validate_artifact(
    artifact_root: Path,
    *,
    v3_root: Path | None = None,
    selected50_root: Path | None = None,
) -> list[str]:
    root = artifact_root.resolve()
    errors: list[str] = []
    if (root / ".handoff").exists():
        _error(errors, "temporary .handoff staging tree must not be published")
    try:
        manifest = strict_json_file(root / "manifest.json")
    except (OSError, UnicodeError, ValueError) as exc:
        return [f"manifest: {exc}"]
    if manifest.get("artifact_name") != "d2l_dataset_remaining_100_stage_a_v1":
        _error(errors, "manifest artifact name mismatch")
    if manifest.get("policy_id") != POLICY_ID or manifest.get("status") != STATUS:
        _error(errors, "manifest policy/status mismatch")
    if _manifest_self_hash(manifest) != manifest.get("manifest_sha256"):
        _error(errors, "manifest self hash mismatch")
    _check_checksums(root, errors)
    terms = _load(root / "term_senses_100.jsonl", errors)
    candidates = _load(root / "candidate_instances_300.jsonl", errors)
    contexts = _load(root / "contexts_selected_100.jsonl", errors)
    if len(terms) != 100 or len({str(row.get("sense_id")) for row in terms}) != 100:
        _error(errors, "term-sense count/identity mismatch")
    if len(candidates) != 300 or len({str(row.get("candidate_instance_id")) for row in candidates}) != 300:
        _error(errors, "candidate count/identity mismatch")
    if len({str(row.get("context_id")) for row in contexts}) != len(contexts):
        _error(errors, "context IDs are not unique")
    term_ids = {str(row.get("sense_id")) for row in terms}
    candidate_by_sense: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        candidate_by_sense[str(row.get("sense_id"))].append(row)
    for sense_id in term_ids:
        rows = candidate_by_sense.get(sense_id, [])
        if len(rows) != 3 or len({str(row.get("candidate_target_vi")).strip().casefold() for row in rows}) != 3:
            _error(errors, f"candidate closure mismatch: {sense_id}")
    if set(candidate_by_sense) != term_ids:
        _error(errors, "candidate sense IDs do not match terms")
    context_ids_by_sense: dict[str, set[str]] = defaultdict(set)
    for row in contexts:
        sense_id = str(row.get("sense_id"))
        if sense_id not in term_ids or not _eligible_context(row):
            _error(errors, f"invalid selected context: {row.get('context_id')}")
        context_ids_by_sense[sense_id].add(str(row.get("context_id")))
        if row.get("synthetic") and row.get("sense_relation") == "SAME_SENSE":
            _error(errors, f"synthetic same-sense context: {row.get('context_id')}")
    if set(context_ids_by_sense) != term_ids:
        _error(errors, "some sense has no selected context")
    _validate_parent_subset(root, terms, candidates, contexts, errors)
    _validate_batches(root, terms, errors)
    try:
        exclusion = strict_json_file(root / "exclusion_report.json")
        if set(exclusion.get("excluded_parent_ids", [])) != EXCLUDED_PARENT_IDS:
            _error(errors, "exclusion report mismatch")
    except (OSError, UnicodeError, ValueError) as exc:
        _error(errors, f"exclusion report: {exc}")
    if v3_root is not None:
        try:
            parent_manifest = strict_json_file(v3_root / "manifest.json")
            if manifest.get("parent_manifest_sha256") != parent_manifest.get("manifest_sha256"):
                _error(errors, "parent manifest binding mismatch")
            parent_terms = {str(row["sense_id"]): row for row in strict_jsonl(v3_root / "term_senses.jsonl")}
            parent_candidates = {str(row["candidate_instance_id"]): row for row in strict_jsonl(v3_root / "candidate_instances.jsonl")}
            parent_contexts = {str(row["context_id"]): row for row in strict_jsonl(v3_root / "contexts.jsonl")}
            for row in terms:
                if parent_terms.get(str(row["sense_id"])) != row:
                    _error(errors, f"term is not exact V3 subset: {row.get('sense_id')}")
            for row in candidates:
                if parent_candidates.get(str(row["candidate_instance_id"])) != row:
                    _error(errors, f"candidate is not exact V3 subset: {row.get('candidate_instance_id')}")
            for row in contexts:
                if parent_contexts.get(str(row["context_id"])) != row:
                    _error(errors, f"context is not exact V3 subset: {row.get('context_id')}")
        except (OSError, UnicodeError, ValueError, KeyError) as exc:
            _error(errors, f"V3 subset check: {exc}")
    return errors


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--v3-root", type=Path, default=REPO_ROOT / "dataset" / "d2l_context_support_set_validation_ready_v3")
    args = parser.parse_args()
    errors = validate_artifact(args.artifact_root, v3_root=args.v3_root)
    if errors:
        print("\n".join(errors))
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
