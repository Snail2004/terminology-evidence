"""Build the append-only pre-D0 addendum and blind producer-safe cohort."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping

from ..jsonio import read_json, sha256_file, sha256_value, write_json, write_jsonl
from .dataset_authority import D0DatasetSnapshot, load_d0_dataset_snapshot
from .specification import (
    D0_AMENDMENT_ID,
    D0_CANDIDATE_COUNT,
    D0_CANDIDATES_PER_SENSE,
    D0_COHORT_SIZE,
    D0_FROZEN_AT,
    D0_PREPARATION_ID,
    D0_SELECTION_POLICY_ID,
    aggregate_distribution,
    adversarial_companion_protocol,
    development_metric_policy,
    non_estimable_natural_metrics,
    result_table_shells,
)


BASE_FREEZE_RECEIPT_SHA256 = "9ecd51676bf3bd758feeb9c330c257629a03f59c8601be10404c30a556762b3a"
BASE_FREEZE_RECEIPT_PATH = "evaluation/v1/authority/analysis_plan_50_150_v1/analysis_plan_freeze_receipt_v1.json"
SELECTION_SEED_SHA256 = "6d83cf9a8f4cae83658778283d961ba2c9206ffac48a109d2d2a382111660c25"
SELECTION_SEED_MATERIAL = {
    "base_freeze_receipt_self_sha256": BASE_FREEZE_RECEIPT_SHA256,
    "dataset_final_seal_commit": "8b3a2cfe9e58c83d871ceea751785f113e3b7182",
    "candidate_identity_sha256": "ea80716a38d443afa954f110b3a8346f17073f7e76aa6ea6f2fce377490dd77b",
    "context_identity_sha256": "eef660f3eff8dcec277ec607d0b56f16f66cdf55e708bb39cd6118167d7dd9fb",
    "split_manifest_physical_sha256": "cec84b39c6bd8d191796efee008a759ee005db03e84ae7d006184542baab58f1",
}

ADDENDUM_FILE = "pre_d0_analysis_plan_addendum_v1.json"
LEDGER_FILE = "pre_d0_amendment_ledger_v1.jsonl"
PROTOCOL_FILE = "adversarial_companion_protocol_v1.json"
COHORT_FILE = "d0_blind_cohort_authority_v1.json"
SHELLS_FILE = "d0_result_table_shells_v1.json"
REFREEZE_CONTENT_FILE = "pre_d0_refreeze_content_v1.json"
CONTENT_MANIFEST_FILE = "content_manifest_v1.json"
CONTENT_FILES = (
    ADDENDUM_FILE,
    LEDGER_FILE,
    PROTOCOL_FILE,
    COHORT_FILE,
    SHELLS_FILE,
    REFREEZE_CONTENT_FILE,
)
ALL_CONTENT_FILES = CONTENT_FILES + (CONTENT_MANIFEST_FILE,)


class D0PreparationError(ValueError):
    """Raised when D0 content cannot be constructed without leaking authority."""


def _without_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["integrity"] = {}
    return result


def _seal(value: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["integrity"] = {"self_sha256": ""}
    result["integrity"]["self_sha256"] = sha256_value(_without_self_hash(result))
    return result


def _event_hash(value: Mapping[str, Any]) -> str:
    unsigned = dict(value)
    unsigned.pop("event_sha256", None)
    return sha256_value(unsigned)


def _verify_base_freeze(repo: Path) -> dict[str, Any]:
    path = repo / BASE_FREEZE_RECEIPT_PATH
    try:
        receipt = read_json(path)
    except (OSError, ValueError) as exc:
        raise D0PreparationError("base analysis-plan freeze receipt is unreadable") from exc
    if receipt.get("integrity", {}).get("self_sha256") != BASE_FREEZE_RECEIPT_SHA256:
        raise D0PreparationError("base analysis-plan freeze receipt self hash drifted")
    if receipt.get("status") != "ANALYSIS_PLAN_FROZEN_FOR_D0" or receipt.get("provider_calls") != 0 or receipt.get("network_calls") != 0:
        raise D0PreparationError("base freeze receipt is not the unopened D0 freeze")
    access = receipt.get("access_state")
    if not isinstance(access, Mapping) or any(access.get(key) not in {False, 0, "0" * 64} for key in ("gold_opened", "validation_opened", "held_out_test_opened", "producer_outputs_opened")):
        raise D0PreparationError("base freeze receipt reports prior restricted access")
    return receipt


def _context_rows(snapshot: D0DatasetSnapshot) -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    for row in snapshot.contexts:
        rows.setdefault(row["sense_id"], []).append(row)
    return rows


def _score(seed: str, namespace: str, value: str) -> str:
    return hashlib.sha256(f"{seed}\0{namespace}\0{value}".encode("utf-8")).hexdigest()


def _select(snapshot: D0DatasetSnapshot) -> tuple[list[str], list[dict[str, Any]], str]:
    contexts = _context_rows(snapshot)
    candidate_by_sense: dict[str, list[dict[str, Any]]] = {}
    for candidate in snapshot.candidates:
        candidate_by_sense.setdefault(candidate["sense_id"], []).append(candidate)
    eligible = sorted(
        sense_id
        for sense_id, candidates in candidate_by_sense.items()
        if snapshot.assignments.get(sense_id) == "development"
        and any(row.get("context_class") == "CONTRASTIVE" for row in contexts.get(sense_id, []))
        and len(candidates) == D0_CANDIDATES_PER_SENSE
    )
    if len(eligible) < D0_COHORT_SIZE:
        raise D0PreparationError("Dataset has fewer than five eligible contrastive development senses")
    selected_senses = [
        sense_id
        for _score_value, sense_id in sorted((_score(SELECTION_SEED_SHA256, "SENSE", sense_id), sense_id) for sense_id in eligible)[:D0_COHORT_SIZE]
    ]
    candidates = sorted(
        (candidate for sense_id in selected_senses for candidate in candidate_by_sense[sense_id]),
        key=lambda row: row["candidate_id"],
    )
    if len(candidates) != D0_CANDIDATE_COUNT or len({row["candidate_id"] for row in candidates}) != D0_CANDIDATE_COUNT:
        raise D0PreparationError("selected cohort cardinality is not exactly fifteen candidates")
    canary = min(candidates, key=lambda row: _score(SELECTION_SEED_SHA256, "CANARY", row["candidate_id"]))
    return selected_senses, candidates, canary["candidate_id"]


def _cohort(snapshot: D0DatasetSnapshot, selected_senses: list[str], candidates: list[dict[str, Any]], canary_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    contexts = _context_rows(snapshot)
    context_sets: list[dict[str, str]] = []
    for sense_id in sorted(selected_senses):
        sense_candidates = [row for row in candidates if row["sense_id"] == sense_id]
        context_set_ids = {row["context_set_id"] for row in sense_candidates}
        if len(context_set_ids) != 1:
            raise D0PreparationError("selected sense has conflicting context-set identities")
        context_set_id = next(iter(context_set_ids))
        context_ids = sorted({context_id for row in sense_candidates for context_id in row["context_ids"]})
        contrastive = [row for row in contexts[sense_id] if row.get("context_class") == "CONTRASTIVE"]
        if len(contrastive) != 1 or contrastive[0]["context_id"] not in context_ids:
            raise D0PreparationError("selected sense does not have exactly one sealed contrastive context")
        context_sets.append(
            {
                "context_set_id": context_set_id,
                "context_set_sha256": sha256_value({"context_ids": context_ids, "context_set_id": context_set_id}),
            }
        )
    candidate_ids = sorted(row["candidate_id"] for row in candidates)
    candidate_set_sha256 = sha256_value({"candidate_ids": candidate_ids})
    selection_authority = _seal(
        {
            "schema_id": "EvaluationD0SelectionAuthorityV1",
            "schema_version": "1.0.0",
            "selection_policy_id": D0_SELECTION_POLICY_ID,
            "seed_sha256": SELECTION_SEED_SHA256,
            "seed_material": dict(SELECTION_SEED_MATERIAL),
            "selected_sense_ids": sorted(selected_senses),
            "candidate_set_sha256": candidate_set_sha256,
            "context_set_hashes": context_sets,
            "dataset_final_seal_commit": snapshot.proof["dataset_final_seal_commit"],
            "split_manifest_physical_sha256": snapshot.proof["split_manifest_physical_sha256"],
            "gold_label_fields_read": 0,
        }
    )
    selection_authority_sha256 = selection_authority["integrity"]["self_sha256"]
    remainder = [candidate_id for candidate_id in candidate_ids if candidate_id != canary_id]
    cohort = _seal(
        {
            "schema_id": "EvaluationD0BlindCohortAuthorityV1",
            "schema_version": "1.0.0",
            "cohort_id": D0_PREPARATION_ID,
            "selection_policy_id": D0_SELECTION_POLICY_ID,
            "selection_authority_sha256": selection_authority_sha256,
            "candidate_set_sha256": candidate_set_sha256,
            "sense_ids": sorted(selected_senses),
            "candidate_ids": candidate_ids,
            "context_sets": context_sets,
            "phase_membership": {"CANARY": [canary_id], "REMAINDER": remainder},
            "gold_access_authorized": False,
            "provider_calls": 0,
            "network_calls": 0,
        }
    )
    return selection_authority, cohort


def _addendum(base_receipt: Mapping[str, Any]) -> dict[str, Any]:
    return _seal(
        {
            "schema_id": "EvaluationPreD0AnalysisPlanAddendumV1",
            "schema_version": "1.0.0",
            "addendum_id": D0_AMENDMENT_ID,
            "preparation_id": D0_PREPARATION_ID,
            "base_freeze_receipt_sha256": BASE_FREEZE_RECEIPT_SHA256,
            "base_plan_id": base_receipt["plan_id"],
            "label_mapping": {
                "positive": ["ACCEPT"],
                "negative": ["REJECT", "SPLIT_REQUIRED"],
                "excluded": ["CONDITIONAL", "HUMAN_UNJUDGEABLE"],
            },
            "aggregate_distribution": aggregate_distribution(),
            "natural_non_estimable_metrics": non_estimable_natural_metrics(),
            "development_metric_policy": development_metric_policy(),
            "adversarial_companion_protocol_id": "evaluation-d0-adversarial-negative-companion-v1",
            "natural_and_adversarial_metrics_separate": True,
            "output_seal_before_gold_access": True,
            "access_order": ["D0", "D1", "V1", "T1"],
            "producer_outputs_opened": False,
            "gold_opened": False,
            "validation_opened": False,
            "held_out_test_opened": False,
            "provider_calls": 0,
            "network_calls": 0,
            "frozen_at": D0_FROZEN_AT,
        }
    )


def _ledger(addendum: Mapping[str, Any], protocol: Mapping[str, Any], cohort: Mapping[str, Any], shells: Mapping[str, Any]) -> list[dict[str, Any]]:
    refs = {
        "base_freeze_receipt_sha256": BASE_FREEZE_RECEIPT_SHA256,
        "addendum_sha256": addendum["integrity"]["self_sha256"],
        "protocol_sha256": protocol["integrity"]["self_sha256"],
        "cohort_sha256": cohort["integrity"]["self_sha256"],
        "shells_sha256": shells["integrity"]["self_sha256"],
    }
    first = {
        "schema_id": "EvaluationPreD0AmendmentEventV1",
        "schema_version": "1.0.0",
        "sequence_number": 0,
        "event_type": "PRE_D0_AMENDMENT",
        "issued_at": D0_FROZEN_AT,
        "actor": "evaluation-maintainer",
        "previous_event_sha256": "0" * 64,
        "authority_refs": refs,
        "payload": {
            "amendment_id": D0_AMENDMENT_ID,
            "changes_primary_analysis": False,
            "new_preregistration_version": "evaluation-analysis-plan-50-senses-150-candidates-pre-d0-v1",
            "gold_access_authorized": False,
        },
        "event_sha256": "",
    }
    first["event_sha256"] = _event_hash(first)
    second = {
        "schema_id": "EvaluationPreD0AmendmentEventV1",
        "schema_version": "1.0.0",
        "sequence_number": 1,
        "event_type": "PRE_D0_REFREEZE",
        "issued_at": D0_FROZEN_AT,
        "actor": "evaluation-maintainer",
        "previous_event_sha256": first["event_sha256"],
        "authority_refs": refs,
        "payload": {
            "amendment_id": D0_AMENDMENT_ID,
            "old_freeze_receipt_sha256": BASE_FREEZE_RECEIPT_SHA256,
            "new_addendum_sha256": addendum["integrity"]["self_sha256"],
            "resume_status": "PRE_D0_ADDENDUM_REFROZEN",
            "gold_access_authorized": False,
            "access_state": {"producer_outputs": False, "gold": False, "validation": False, "held_out_test": False},
        },
        "event_sha256": "",
    }
    second["event_sha256"] = _event_hash(second)
    return [first, second]


def build_d0_content(repo: Path, output_directory: Path, *, snapshot: D0DatasetSnapshot | None = None) -> dict[str, Any]:
    """Build all content files into a new directory, deterministically."""
    if output_directory.exists():
        raise D0PreparationError("D0 content output already exists")
    base_receipt = _verify_base_freeze(repo)
    snapshot = snapshot or load_d0_dataset_snapshot(repo)
    output_directory.mkdir(parents=True)
    addendum = _addendum(base_receipt)
    protocol = _seal(adversarial_companion_protocol())
    shells = _seal(
        {
            "schema_id": "EvaluationD0ResultTableShellsV1",
            "schema_version": "1.0.0",
            "preparation_id": D0_PREPARATION_ID,
            "result_cells_present": 0,
            "gold_access_authorized": False,
            "tables": result_table_shells(),
        }
    )
    selected_senses, candidates, canary_id = _select(snapshot)
    selection_authority, cohort = _cohort(snapshot, selected_senses, candidates, canary_id)
    ledger = _ledger(addendum, protocol, cohort, shells)
    refreeze = _seal(
        {
            "schema_id": "EvaluationPreD0RefreezeContentV1",
            "schema_version": "1.0.0",
            "preparation_id": D0_PREPARATION_ID,
            "status": "PRE_D0_ADDENDUM_REFROZEN",
            "base_freeze_receipt_sha256": BASE_FREEZE_RECEIPT_SHA256,
            "addendum_sha256": addendum["integrity"]["self_sha256"],
            "protocol_sha256": protocol["integrity"]["self_sha256"],
            "cohort_sha256": cohort["integrity"]["self_sha256"],
            "selection_authority_sha256": selection_authority["integrity"]["self_sha256"],
            "shells_sha256": shells["integrity"]["self_sha256"],
            "amendment_ledger_head_sha256": ledger[-1]["event_sha256"],
            "amendment_event_count": len(ledger),
            "gold_access_authorized": False,
            "producer_outputs_opened": False,
            "validation_opened": False,
            "held_out_test_opened": False,
            "provider_calls": 0,
            "network_calls": 0,
            "frozen_at": D0_FROZEN_AT,
        }
    )
    write_json(output_directory / ADDENDUM_FILE, addendum)
    write_jsonl(output_directory / LEDGER_FILE, ledger)
    write_json(output_directory / PROTOCOL_FILE, protocol)
    write_json(output_directory / COHORT_FILE, cohort)
    write_json(output_directory / SHELLS_FILE, shells)
    write_json(output_directory / REFREEZE_CONTENT_FILE, refreeze)
    entries = []
    for filename in CONTENT_FILES:
        path = output_directory / filename
        entries.append({"path": filename, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    manifest = _seal(
        {
            "schema_id": "EvaluationD0ContentManifestV1",
            "schema_version": "1.0.0",
            "preparation_id": D0_PREPARATION_ID,
            "status": "CONTENT_READY_NO_GOLD",
            "files": entries,
            "source_authority": snapshot.proof,
            "base_freeze_receipt_sha256": BASE_FREEZE_RECEIPT_SHA256,
            "gold_label_fields_read": 0,
            "provider_calls": 0,
            "network_calls": 0,
        }
    )
    write_json(output_directory / CONTENT_MANIFEST_FILE, manifest)
    # Ensure no accidental cache/result bytes were created in the authority set.
    actual = sorted(path.name for path in output_directory.iterdir() if path.is_file())
    if actual != sorted(ALL_CONTENT_FILES):
        raise D0PreparationError("D0 content output contains an unexpected file")
    return {
        "status": "PASS",
        "preparation_id": D0_PREPARATION_ID,
        "content_directory": str(output_directory),
        "content_manifest_self_sha256": manifest["integrity"]["self_sha256"],
        "cohort_self_sha256": cohort["integrity"]["self_sha256"],
        "selection_authority_self_sha256": selection_authority["integrity"]["self_sha256"],
        "ledger_head_sha256": ledger[-1]["event_sha256"],
        "sense_count": len(selected_senses),
        "candidate_count": len(candidates),
        "canary_candidate_id": canary_id,
        "gold_access": False,
        "provider_calls": 0,
        "network_calls": 0,
    }
