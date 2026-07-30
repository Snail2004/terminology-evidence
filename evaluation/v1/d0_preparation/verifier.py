"""Fail-closed verification for D0 content and producer-safe cohort bytes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..jsonio import read_json, read_jsonl, sha256_file, sha256_value
from .builder import (
    ADDENDUM_FILE,
    ALL_CONTENT_FILES,
    BASE_FREEZE_RECEIPT_SHA256,
    BASE_FREEZE_RECEIPT_PATH,
    COHORT_FILE,
    CONTENT_MANIFEST_FILE,
    CONTENT_FILES,
    LEDGER_FILE,
    PROTOCOL_FILE,
    REFREEZE_CONTENT_FILE,
    SELECTION_SEED_SHA256,
    SHELLS_FILE,
    D0PreparationError,
    _cohort,
    _select,
    _verify_base_freeze,
)
from .publication import verify_d0_publication
from .dataset_authority import load_d0_dataset_snapshot
from .specification import D0_AMENDMENT_ID, D0_CANDIDATE_COUNT, D0_CANDIDATES_PER_SENSE, D0_COHORT_SIZE, D0_PREPARATION_ID


_FORBIDDEN_PRODUCER_KEYS = {
    "annotation", "candidate_rank", "decision", "expected_result", "gold_label",
    "reviewer_decision", "winner", "split", "split_statistics", "candidate_order",
}


def _without_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["integrity"] = {}
    return result


def _verify_self(value: Mapping[str, Any], field: str) -> str:
    declared = value.get("integrity", {}).get("self_sha256") if isinstance(value.get("integrity"), Mapping) else None
    actual = sha256_value(_without_self_hash(value))
    if declared != actual:
        raise D0PreparationError(f"{field} self hash mismatch")
    return actual


def _walk_forbidden(value: Any, field: str) -> None:
    if isinstance(value, Mapping):
        bad = _FORBIDDEN_PRODUCER_KEYS & set(value)
        if bad:
            raise D0PreparationError(f"producer-safe {field} exposes forbidden keys: {sorted(bad)}")
        for key, child in value.items():
            _walk_forbidden(child, f"{field}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden(child, f"{field}[{index}]")


def _verify_ledger(path: Path, refs: Mapping[str, str]) -> str:
    rows = read_jsonl(path)
    if len(rows) != 2:
        raise D0PreparationError("pre-D0 amendment ledger must contain exactly two events")
    previous = "0" * 64
    for sequence, row in enumerate(rows):
        expected = {
            "schema_id", "schema_version", "sequence_number", "event_type", "issued_at", "actor",
            "previous_event_sha256", "authority_refs", "payload", "event_sha256",
        }
        if set(row) != expected or row["sequence_number"] != sequence or row["previous_event_sha256"] != previous:
            raise D0PreparationError("pre-D0 amendment ledger chain shape is invalid")
        if row["authority_refs"] != dict(refs):
            raise D0PreparationError("pre-D0 amendment ledger authority refs drifted")
        unsigned = dict(row)
        unsigned.pop("event_sha256", None)
        actual = sha256_value(unsigned)
        if row["event_sha256"] != actual:
            raise D0PreparationError("pre-D0 amendment ledger event hash mismatch")
        previous = actual
    if rows[0]["event_type"] != "PRE_D0_AMENDMENT" or rows[1]["event_type"] != "PRE_D0_REFREEZE":
        raise D0PreparationError("pre-D0 amendment/refreeze event order is invalid")
    if rows[0]["payload"].get("changes_primary_analysis") is not False or rows[1]["payload"].get("gold_access_authorized") is not False:
        raise D0PreparationError("pre-D0 ledger changes primary analysis or opens gold")
    return previous


def _verify_cohort(repo: Path, cohort: Mapping[str, Any], selection_authority: Mapping[str, Any]) -> None:
    if cohort.get("schema_id") != "EvaluationD0BlindCohortAuthorityV1" or cohort.get("schema_version") != "1.0.0":
        raise D0PreparationError("unsupported D0 cohort authority")
    if cohort.get("cohort_id") != D0_PREPARATION_ID or cohort.get("selection_policy_id") != "evaluation_d0_blind_hash_rank_v1":
        raise D0PreparationError("D0 cohort identity/policy drifted")
    _walk_forbidden(cohort, "cohort")
    if cohort.get("gold_access_authorized") is not False or cohort.get("provider_calls") != 0 or cohort.get("network_calls") != 0:
        raise D0PreparationError("D0 cohort access boundary is open")
    senses = cohort.get("sense_ids")
    candidates = cohort.get("candidate_ids")
    if not isinstance(senses, list) or senses != sorted(senses) or len(senses) != D0_COHORT_SIZE or len(set(senses)) != D0_COHORT_SIZE:
        raise D0PreparationError("D0 cohort sense cardinality/order is invalid")
    if not isinstance(candidates, list) or candidates != sorted(candidates) or len(candidates) != D0_CANDIDATE_COUNT or len(set(candidates)) != D0_CANDIDATE_COUNT:
        raise D0PreparationError("D0 cohort candidate cardinality/order is invalid")
    phases = cohort.get("phase_membership")
    if not isinstance(phases, Mapping) or set(phases) != {"CANARY", "REMAINDER"} or len(phases["CANARY"]) != 1 or len(phases["REMAINDER"]) != 14:
        raise D0PreparationError("D0 cohort phase membership is invalid")
    if set(phases["CANARY"]) | set(phases["REMAINDER"]) != set(candidates) or set(phases["CANARY"]) & set(phases["REMAINDER"]):
        raise D0PreparationError("D0 cohort phase membership does not cover candidates exactly")
    if cohort.get("candidate_set_sha256") != sha256_value({"candidate_ids": candidates}):
        raise D0PreparationError("D0 candidate-set hash mismatch")
    if cohort.get("selection_authority_sha256") != selection_authority["integrity"]["self_sha256"]:
        raise D0PreparationError("D0 selection authority binding mismatch")
    context_sets = cohort.get("context_sets")
    if not isinstance(context_sets, list) or len(context_sets) != D0_COHORT_SIZE:
        raise D0PreparationError("D0 context-set authority cardinality is invalid")
    for row in context_sets:
        if set(row) != {"context_set_id", "context_set_sha256"}:
            raise D0PreparationError("D0 context-set row shape is invalid")
    if context_sets != selection_authority.get("context_set_hashes"):
        raise D0PreparationError("D0 context-set hashes differ from selection authority")


def verify_d0_content(repo: Path, content_directory: Path) -> dict[str, Any]:
    """Verify deterministic content, Dataset binding and unopened access state."""
    if not content_directory.is_dir():
        raise D0PreparationError("D0 content directory is missing")
    actual = sorted(path.name for path in content_directory.iterdir() if path.is_file())
    allowed_publication = {"pre_d0_refreeze_receipt_v1.json", "manifest.json", "CHECKSUMS.sha256"}
    if set(actual) - set(ALL_CONTENT_FILES) - allowed_publication or not set(ALL_CONTENT_FILES).issubset(actual):
        raise D0PreparationError(f"D0 content file set differs: {actual}")
    manifest = read_json(content_directory / CONTENT_MANIFEST_FILE)
    manifest_self = _verify_self(manifest, "content manifest")
    entries = manifest.get("files")
    expected_entries = []
    for filename in CONTENT_FILES:
        path = content_directory / filename
        expected_entries.append({"path": filename, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    if entries != expected_entries or manifest.get("base_freeze_receipt_sha256") != BASE_FREEZE_RECEIPT_SHA256:
        raise D0PreparationError("D0 content manifest inventory drifted")
    if manifest.get("gold_label_fields_read") != 0 or manifest.get("provider_calls") != 0 or manifest.get("network_calls") != 0:
        raise D0PreparationError("D0 content manifest reports forbidden access")
    base = _verify_base_freeze(repo)
    addendum = read_json(content_directory / ADDENDUM_FILE)
    protocol = read_json(content_directory / PROTOCOL_FILE)
    cohort = read_json(content_directory / COHORT_FILE)
    shells = read_json(content_directory / SHELLS_FILE)
    refreeze = read_json(content_directory / REFREEZE_CONTENT_FILE)
    selection_authority = None
    # The selection authority is deliberately embedded only by hash in the
    # producer-safe cohort; reconstructing it from the sealed Dataset avoids
    # adding another producer-visible file.
    snapshot = load_d0_dataset_snapshot(repo)
    selected_senses, candidates, canary_id = _select(snapshot)
    expected_authority, expected_cohort = _cohort(snapshot, selected_senses, candidates, canary_id)
    selection_authority = expected_authority
    for value, name in ((addendum, "addendum"), (protocol, "protocol"), (cohort, "cohort"), (shells, "shells"), (refreeze, "refreeze content")):
        _verify_self(value, name)
    if addendum.get("base_freeze_receipt_sha256") != base["integrity"]["self_sha256"] or addendum.get("gold_opened") is not False:
        raise D0PreparationError("D0 addendum does not bind unopened base freeze")
    if protocol.get("case_count") != 0 or protocol.get("fabricated_cases") != 0 or protocol.get("gold_access_authorized") is not False:
        raise D0PreparationError("D0 adversarial protocol fabricates or opens cases")
    if shells.get("result_cells_present") != 0 or shells.get("gold_access_authorized") is not False:
        raise D0PreparationError("D0 result shells contain observed results")
    if cohort != expected_cohort:
        raise D0PreparationError("D0 cohort is not the deterministic Dataset-bound selection")
    _verify_cohort(repo, cohort, selection_authority)
    refs = {
        "base_freeze_receipt_sha256": BASE_FREEZE_RECEIPT_SHA256,
        "addendum_sha256": addendum["integrity"]["self_sha256"],
        "protocol_sha256": protocol["integrity"]["self_sha256"],
        "cohort_sha256": cohort["integrity"]["self_sha256"],
        "shells_sha256": shells["integrity"]["self_sha256"],
    }
    ledger_head = _verify_ledger(content_directory / LEDGER_FILE, refs)
    if refreeze.get("amendment_ledger_head_sha256") != ledger_head or refreeze.get("status") != "PRE_D0_ADDENDUM_REFROZEN":
        raise D0PreparationError("D0 refreeze content does not bind amendment ledger")
    if any(refreeze.get(key) != value for key, value in {
        "base_freeze_receipt_sha256": BASE_FREEZE_RECEIPT_SHA256,
        "addendum_sha256": addendum["integrity"]["self_sha256"],
        "protocol_sha256": protocol["integrity"]["self_sha256"],
        "cohort_sha256": cohort["integrity"]["self_sha256"],
        "selection_authority_sha256": selection_authority["integrity"]["self_sha256"],
        "shells_sha256": shells["integrity"]["self_sha256"],
    }.items()):
        raise D0PreparationError("D0 refreeze content hash binding drifted")
    if any(refreeze.get(key) is not False for key in ("gold_access_authorized", "producer_outputs_opened", "validation_opened", "held_out_test_opened")) or refreeze.get("provider_calls") != 0 or refreeze.get("network_calls") != 0:
        raise D0PreparationError("D0 refreeze content opens a restricted resource")
    if manifest.get("preparation_id") != D0_PREPARATION_ID or manifest.get("status") != "CONTENT_READY_NO_GOLD":
        raise D0PreparationError("D0 content manifest identity/status drifted")
    return {
        "status": "PASS",
        "content_manifest_self_sha256": manifest_self,
        "cohort_self_sha256": cohort["integrity"]["self_sha256"],
        "selection_authority_self_sha256": selection_authority["integrity"]["self_sha256"],
        "amendment_ledger_head_sha256": ledger_head,
        "sense_count": D0_COHORT_SIZE,
        "candidate_count": D0_CANDIDATE_COUNT,
        "canary_candidate_id": cohort["phase_membership"]["CANARY"][0],
        "selection_seed_sha256": SELECTION_SEED_SHA256,
        "gold_access": False,
        "provider_calls": 0,
        "network_calls": 0,
    }
