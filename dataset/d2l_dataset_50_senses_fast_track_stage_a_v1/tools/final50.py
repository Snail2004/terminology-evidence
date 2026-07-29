from __future__ import annotations

import copy
import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

try:
    from .common import canonical_json_bytes, seal_record, sha256_bytes, sha256_file, strict_jsonl
    from .review_result import review_disagreement_fields
except ImportError:  # pragma: no cover - direct script execution
    from common import canonical_json_bytes, seal_record, sha256_bytes, sha256_file, strict_jsonl  # type: ignore
    from review_result import review_disagreement_fields  # type: ignore


FINAL_DATASET_VERSION = "d2l_dataset_50_senses_150_candidates_v1"
FINAL_POLICY_ID = "d2l-dataset-50-senses-150-candidates-stage-b-v1.0"
LANE_QUOTAS = {"A_OFFICIAL": 5, "B_REVIEW_READY": 6, "C_REPAIRED": 4, "D_NEW": 35}
STRATUM_QUOTAS = {"clear": 15, "ambiguous": 20, "collision_or_multi_target": 15}
D_STRATUM_QUOTAS = {"clear": 10, "ambiguous": 12, "collision_or_multi_target": 13}
SPLIT_QUOTAS = {"development": 30, "validation": 10, "test": 10}
C_EXCLUDED_SENSE_ID = "d2lce_2b76c0f26436945cdf880aed"
D_REAUDITED_PRIORITY_IDS = {
    "d2lce_4abd762bcd34d370b4fe6498",
    "d2lce_499fa9391d57e930a19f1b19",
    "d2lce_c01c503b792019c6e3827ac0",
    "d2lce_e014da89e120449f8881dd5b",
}


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def index_rows(rows: Iterable[Mapping[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row.get(field)
        if not isinstance(key, str) or not key or key in result:
            raise ValueError(f"invalid or duplicate {field}: {key!r}")
        result[key] = copy.deepcopy(dict(row))
    return result


def evidence_score(
    sense: Mapping[str, Any], contexts_by_sense: Mapping[str, Sequence[Mapping[str, Any]]]
) -> tuple[int, int, int, int, int, int, str]:
    rows = [
        row
        for row in contexts_by_sense.get(str(sense["sense_id"]), ())
        if row.get("positive_evidence_eligible") and not row.get("synthetic")
    ]
    chapters = {row.get("chapter_id") for row in rows if row.get("chapter_id")}
    blocks = {row.get("block_id") for row in rows if row.get("block_id")}
    roles = {role for row in rows for role in row.get("evidence_roles", [])}
    return (
        int(sense["sense_id"] in D_REAUDITED_PRIORITY_IDS),
        int("POSITIVE_DEFINITION_PROPOSAL" in roles),
        int("POSITIVE_POS_PROPOSAL" in roles),
        len(chapters),
        len(blocks),
        len(rows),
        str(sense["sense_id"]),
    )


def leakage_components(
    selected: Sequence[Mapping[str, Any]], contexts: Sequence[Mapping[str, Any]]
) -> list[list[dict[str, Any]]]:
    selected_by_id = index_rows(selected, "sense_id")
    parent = {sense_id: sense_id for sense_id in selected_by_id}

    def find(value: str) -> str:
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    keyed: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in contexts:
        sense_id = row.get("pool_sense_id")
        if sense_id not in selected_by_id or row.get("synthetic"):
            continue
        for field in ("sentence_id", "block_id"):
            value = row.get(field)
            if isinstance(value, str) and value:
                keyed[(field, value)].add(sense_id)
    for group in keyed.values():
        ordered = sorted(group)
        for other in ordered[1:]:
            union(ordered[0], other)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sense_id, sense in selected_by_id.items():
        grouped[find(sense_id)].append(sense)
    return sorted(
        (sorted(group, key=lambda row: row["sense_id"]) for group in grouped.values()),
        key=lambda group: (-len(group), tuple(row["sense_id"] for row in group)),
    )


def _choose_initial(
    pool: Sequence[Mapping[str, Any]], contexts_by_sense: Mapping[str, Sequence[Mapping[str, Any]]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    selected = [
        copy.deepcopy(dict(row))
        for row in pool
        if row.get("lane") in {"A_OFFICIAL", "B_REVIEW_READY"}
    ]
    selected.extend(
        copy.deepcopy(dict(row))
        for row in pool
        if row.get("lane") == "C_REPAIRED" and row.get("sense_id") != C_EXCLUDED_SENSE_ID
    )
    excluded: list[dict[str, Any]] = [
        copy.deepcopy(dict(row))
        for row in pool
        if row.get("lane") == "C_REPAIRED" and row.get("sense_id") == C_EXCLUDED_SENSE_ID
    ]
    for stratum, quota in D_STRATUM_QUOTAS.items():
        ranked = sorted(
            (row for row in pool if row.get("lane") == "D_NEW" and row.get("stratum") == stratum),
            key=lambda row: evidence_score(row, contexts_by_sense),
            reverse=True,
        )
        selected.extend(copy.deepcopy(dict(row)) for row in ranked[:quota])
        excluded.extend(copy.deepcopy(dict(row)) for row in ranked[quota:])
    return selected, excluded


def _repair_oversized_component(
    selected: list[dict[str, Any]],
    excluded: list[dict[str, Any]],
    contexts: Sequence[Mapping[str, Any]],
    contexts_by_sense: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[dict[str, Any]]:
    swaps: list[dict[str, Any]] = []
    while True:
        components = leakage_components(selected, contexts)
        oversized = next((group for group in components if len(group) > 10), None)
        if oversized is None:
            return swaps
        removable = sorted(
            (row for row in oversized if row.get("lane") == "D_NEW"),
            key=lambda row: evidence_score(row, contexts_by_sense),
        )
        repaired = False
        for outgoing in removable:
            incoming_rows = sorted(
                (
                    row
                    for row in excluded
                    if row.get("lane") == "D_NEW" and row.get("stratum") == outgoing.get("stratum")
                ),
                key=lambda row: evidence_score(row, contexts_by_sense),
                reverse=True,
            )
            for incoming in incoming_rows:
                trial = [row for row in selected if row["sense_id"] != outgoing["sense_id"]]
                trial.append(copy.deepcopy(incoming))
                if max(len(group) for group in leakage_components(trial, contexts)) <= 10:
                    selected[:] = trial
                    excluded[:] = [row for row in excluded if row["sense_id"] != incoming["sense_id"]]
                    excluded.append(copy.deepcopy(outgoing))
                    swaps.append(
                        {
                            "reason": "LEAKAGE_COMPONENT_MAX_10",
                            "outgoing_sense_id": outgoing["sense_id"],
                            "outgoing_source_term": outgoing["source_term"],
                            "incoming_sense_id": incoming["sense_id"],
                            "incoming_source_term": incoming["source_term"],
                            "stratum": outgoing["stratum"],
                        }
                    )
                    repaired = True
                    break
            if repaired:
                break
        if not repaired:
            raise ValueError("cannot reduce leakage component to the 10-sense split cap")


def select_exact_50(
    pool: Sequence[Mapping[str, Any]], contexts: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    contexts_by_sense: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in contexts:
        contexts_by_sense[str(row["pool_sense_id"])].append(row)
    selected, excluded = _choose_initial(pool, contexts_by_sense)
    swaps = _repair_oversized_component(selected, excluded, contexts, contexts_by_sense)
    selected.sort(key=lambda row: row["sense_id"])
    excluded.sort(key=lambda row: row["sense_id"])
    if len(selected) != 50 or len({row["sense_id"] for row in selected}) != 50:
        raise ValueError("exact-50 selection count mismatch")
    if Counter(row["lane"] for row in selected) != Counter(LANE_QUOTAS):
        raise ValueError("exact-50 lane quota mismatch")
    if Counter(row["stratum"] for row in selected) != Counter(STRATUM_QUOTAS):
        raise ValueError("exact-50 stratum quota mismatch")
    return selected, excluded, swaps


def _best_component_subset(
    components: Sequence[Sequence[Mapping[str, Any]]],
    capacity: int,
    target: tuple[int, int, int],
) -> tuple[int, ...]:
    states: dict[tuple[int, int, int], tuple[int, ...]] = {(0, 0, 0): ()}
    for index, component in enumerate(components):
        counts = Counter(row["stratum"] for row in component)
        size = len(component)
        updated = dict(states)
        for (total, clear, ambiguous), chosen in states.items():
            state = (total + size, clear + counts["clear"], ambiguous + counts["ambiguous"])
            if state[0] > capacity:
                continue
            candidate = chosen + (index,)
            if state not in updated or candidate < updated[state]:
                updated[state] = candidate
        states = updated
    candidates = []
    for state, chosen in states.items():
        if state[0] != capacity:
            continue
        collision = state[0] - state[1] - state[2]
        objective = abs(state[1] - target[0]) + abs(state[2] - target[1]) + abs(collision - target[2])
        candidates.append((objective, chosen))
    if not candidates:
        raise ValueError(f"cannot construct leakage-safe split of size {capacity}")
    return min(candidates)[1]


def assign_splits(
    selected: Sequence[Mapping[str, Any]], contexts: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    components = leakage_components(selected, contexts)
    if not components or len(components[0]) > 10:
        raise ValueError("selected set has an oversized leakage component")
    validation_components: list[list[dict[str, Any]]] = [components[0]]
    remaining = list(components[1:])
    validation_remaining = 10 - len(components[0])
    if validation_remaining:
        chosen = _best_component_subset(remaining, validation_remaining, (3, 4, 3))
        validation_components.extend(remaining[index] for index in chosen)
        remaining = [component for index, component in enumerate(remaining) if index not in set(chosen)]
    test_choice = _best_component_subset(remaining, 10, (3, 4, 3))
    test_components = [remaining[index] for index in test_choice]
    test_ids = {row["sense_id"] for group in test_components for row in group}
    validation_ids = {row["sense_id"] for group in validation_components for row in group}
    assignment = {
        row["sense_id"]: (
            "validation"
            if row["sense_id"] in validation_ids
            else "test"
            if row["sense_id"] in test_ids
            else "development"
        )
        for row in selected
    }
    if Counter(assignment.values()) != Counter(SPLIT_QUOTAS):
        raise ValueError("split quota mismatch")
    component_report: list[dict[str, Any]] = []
    for index, group in enumerate(components, start=1):
        splits = {assignment[row["sense_id"]] for row in group}
        if len(splits) != 1:
            raise ValueError("leakage component crosses split boundaries")
        component_report.append(
            {
                "component_id": f"leakage_component_{index:03d}",
                "sense_ids": [row["sense_id"] for row in group],
                "size": len(group),
                "split": next(iter(splits)),
            }
        )
    return assignment, component_report


def _apply_resolution(
    source: Mapping[str, Any], resolution: Mapping[str, Any]
) -> tuple[str, str, str, list[dict[str, Any]]]:
    definition = str(source["proposed_definition_en"])
    part_of_speech = str(source["proposed_part_of_speech"])
    scope = str(source["proposed_scope"])
    if resolution.get("definition_decision") == "REVISE":
        definition = str(resolution["corrected_definition_en"])
    if resolution.get("part_of_speech_decision") == "REVISE":
        part_of_speech = str(resolution["corrected_part_of_speech"])
    if resolution.get("scope_decision") == "REVISE":
        scope = str(resolution["corrected_scope"])
    candidates = copy.deepcopy(list(source["candidates"]))
    indexed = {(row["candidate_id"], row["candidate_slot"]): row for row in candidates}
    for replacement in resolution.get("candidate_replacements", []):
        if not isinstance(replacement, Mapping):
            raise ValueError("candidate replacement must be identity-bound")
        key = (replacement.get("candidate_id"), replacement.get("candidate_slot"))
        target = replacement.get("replacement_target_vi")
        if key not in indexed or not isinstance(target, str) or not target.strip():
            raise ValueError("candidate replacement binding is invalid")
        indexed[key]["candidate_target_vi"] = target
    targets = [_normalized(str(row["candidate_target_vi"])) for row in candidates]
    if len(candidates) != 3 or len(set(targets)) != 3:
        raise ValueError(f"resolved candidate set is not three distinct values: {source.get('sense_id')}")
    return definition, part_of_speech, scope, candidates


def load_d_stage_a_outcomes(
    *, intake_root: Path, adjudication_root: Path, r0_result_root: Path
) -> dict[str, dict[str, Any]]:
    raw_index: dict[tuple[str, str], dict[str, Any]] = {}
    for slot in ("reviewer_1", "reviewer_2"):
        for path in sorted((intake_root / "raw_reviews" / slot).glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            for case in payload["cases"]:
                sense_id = case["source_payload"]["sense_id"]
                raw_index[(slot, sense_id)] = {
                    "case": case,
                    "path": path.relative_to(intake_root).as_posix(),
                    "sha256": sha256_file(path),
                }
    adjudicated = index_rows(strict_jsonl(adjudication_root / "adjudicated_stage_a_24.jsonl"), "sense_id")
    r0_results = index_rows(strict_jsonl(r0_result_root / "r0_reaudit_results_4.jsonl"), "sense_id")
    outcomes: dict[str, dict[str, Any]] = {}
    for (slot, sense_id), entry in raw_index.items():
        if slot != "reviewer_1" or sense_id in adjudicated or sense_id in r0_results:
            continue
        case = entry["case"]
        source = case["source_payload"]
        review = case["review"]
        if review.get("sense_status") != "READY_FOR_CONTRACT_CONSTRUCTION":
            raise ValueError(f"direct Stage A route is not ready: {sense_id}")
        references = [{"reviewer_slot": "reviewer_1", "path": entry["path"], "sha256": entry["sha256"]}]
        if source["risk_class"] == "R3_AMBIGUOUS":
            other = raw_index.get(("reviewer_2", sense_id))
            if other is None or review_disagreement_fields(review, other["case"]["review"]):
                raise ValueError(f"R3 direct route lacks reviewer agreement: {sense_id}")
            references.append(
                {"reviewer_slot": "reviewer_2", "path": other["path"], "sha256": other["sha256"]}
            )
            route = "R3_DUAL_REVIEWER_AGREEMENT"
        else:
            route = "R0_BLIND_AUDIT_ACCEPTED"
        outcomes[sense_id] = {
            "route": route,
            "source_payload": copy.deepcopy(source),
            "resolution": copy.deepcopy(review),
            "review_references": references,
        }
    for sense_id, row in adjudicated.items():
        outcomes[sense_id] = {
            "route": "REVIEWER_3_ADJUDICATED",
            "source_payload": copy.deepcopy(row["source_payload"]),
            "resolution": copy.deepcopy(row["adjudication"]),
            "review_references": [
                {
                    "reviewer_slot": "reviewer_3_adjudicator",
                    "path": "adjudicated_stage_a_24.jsonl",
                    "sha256": row["adjudication_result_sha256"],
                }
            ],
        }
    for sense_id, row in r0_results.items():
        outcomes[sense_id] = {
            "route": "R0_REPAIR_BLIND_REAUDIT_ACCEPTED",
            "source_payload": copy.deepcopy(row["source_payload"]),
            "resolution": copy.deepcopy(row["review"]),
            "review_references": [
                {
                    "reviewer_slot": "r0_blind_reauditor",
                    "path": "r0_reaudit_results_4.jsonl",
                    "sha256": row["result_record_sha256"],
                }
            ],
        }
    if len(outcomes) != 44:
        raise ValueError(f"D-new Stage A outcome closure mismatch: {len(outcomes)}/44")
    return outcomes


def materialize_selected_records(
    *,
    selected: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    contexts: Sequence[Mapping[str, Any]],
    assignments: Mapping[str, str],
    d_outcomes: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    candidates_by_sense: dict[str, list[dict[str, Any]]] = defaultdict(list)
    contexts_by_sense: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        candidates_by_sense[str(row["sense_id"])].append(copy.deepcopy(dict(row)))
    for row in contexts:
        contexts_by_sense[str(row["pool_sense_id"])].append(copy.deepcopy(dict(row)))
    senses_out: list[dict[str, Any]] = []
    candidates_out: list[dict[str, Any]] = []
    contexts_out: list[dict[str, Any]] = []
    bindings_out: list[dict[str, Any]] = []
    for pool_row in sorted(selected, key=lambda row: row["sense_id"]):
        sense_id = str(pool_row["sense_id"])
        source_candidates = candidates_by_sense[sense_id]
        source_contexts = contexts_by_sense[sense_id]
        if pool_row["lane"] == "D_NEW":
            outcome = d_outcomes[sense_id]
            definition, part_of_speech, scope_id, resolved_candidates = _apply_resolution(
                outcome["source_payload"], outcome["resolution"]
            )
            target_by_id = {row["candidate_id"]: row["candidate_target_vi"] for row in resolved_candidates}
            route = outcome["route"]
            references = copy.deepcopy(outcome["review_references"])
            definition_source = (
                "HUMAN_CORRECTED"
                if outcome["resolution"].get("definition_decision") == "REVISE"
                else "MODEL_ACCEPTED"
            )
        else:
            definition = str(pool_row["definition_en"])
            part_of_speech = str(pool_row["part_of_speech"])
            scope_id = str(pool_row.get("scope") or "d2l_selected_campaign_scope_v1")
            target_by_id = {row["candidate_id"]: row["candidate_target_vi"] for row in source_candidates}
            route = str(pool_row["pool_status"])
            definition_source = "MODEL_ACCEPTED"
            references = [
                {
                    "reviewer_slot": "inherited_review_lineage",
                    "path": "master_pool_60.jsonl",
                    "sha256": pool_row["sense_pool_record_sha256"],
                }
            ]
        sense_payload = {
            "schema_id": "D2LFinal50TermSenseV1",
            "schema_version": "1.0.0",
            "policy_id": FINAL_POLICY_ID,
            "dataset_version": FINAL_DATASET_VERSION,
            "term_id": pool_row["term_id"],
            "sense_id": sense_id,
            "source_term": pool_row["source_term"],
            "definition": definition,
            "part_of_speech": part_of_speech,
            "scope_id": scope_id,
            "stratum": pool_row["stratum"],
            "lane": pool_row["lane"],
            "split": assignments[sense_id],
            "stage_a_status": "READY_FOR_CONTRACT_CONSTRUCTION",
            "stage_a_route": route,
            "definition_source": definition_source,
            "provider_call_count": 0,
            "stage_b_gold_label": None,
            "final_glossary_decision": None,
        }
        sense_record = seal_record(sense_payload, "term_sense_sha256")
        senses_out.append(sense_record)
        bindings_out.append(
            seal_record(
                {
                    "schema_id": "D2LFinal50StageAReviewBindingV1",
                    "schema_version": "1.0.0",
                    "policy_id": FINAL_POLICY_ID,
                    "sense_id": sense_id,
                    "lane": pool_row["lane"],
                    "route": route,
                    "source_pool_record_sha256": pool_row["sense_pool_record_sha256"],
                    "review_references": references,
                    "effective_definition_en": definition,
                    "effective_part_of_speech": part_of_speech,
                    "effective_scope_id": scope_id,
                    "effective_candidate_targets_vi": [
                        target_by_id[row["candidate_id"]]
                        for row in sorted(source_candidates, key=lambda item: item["candidate_id"])
                    ],
                    "stage_a_status": "READY_FOR_CONTRACT_CONSTRUCTION",
                    "provider_call_count": 0,
                    "stage_b_gold_label": None,
                    "final_glossary_decision": None,
                },
                "review_binding_sha256",
            )
        )
        for source_candidate in sorted(source_candidates, key=lambda row: row["candidate_id"]):
            target = target_by_id[source_candidate["candidate_id"]]
            changed = target != source_candidate["candidate_target_vi"]
            candidate_version = (
                sha256_bytes(
                    canonical_json_bytes(
                        {
                            "parent": source_candidate["source_candidate_sha256"],
                            "candidate_target_vi": target,
                            "stage_a_route": route,
                        }
                    )
                )
                if changed
                else source_candidate["source_candidate_sha256"]
            )
            candidates_out.append(
                seal_record(
                    {
                        "schema_id": "D2LFinal50CandidateInstanceV1",
                        "schema_version": "1.0.0",
                        "policy_id": FINAL_POLICY_ID,
                        "dataset_version": FINAL_DATASET_VERSION,
                        "candidate_instance_id": source_candidate["candidate_id"],
                        "candidate_slot_id": source_candidate["candidate_slot"],
                        "candidate_version": candidate_version,
                        "candidate_instance_sha256": candidate_version,
                        "candidate_target_vi": target,
                        "sense_id": sense_id,
                        "scope_id": scope_id,
                        "source_candidate_sha256": source_candidate["source_candidate_sha256"],
                        "stage_a_revised": changed,
                        "binding_status": "COMPLETE",
                        "provider_call_count": 0,
                        "final_gold_label": None,
                        "final_glossary_decision": None,
                    },
                    "record_sha256",
                )
            )
        for context in source_contexts:
            context["sense_id"] = sense_id
            context["split"] = assignments[sense_id]
            contexts_out.append(context)
    if len(senses_out) != 50 or len(candidates_out) != 150:
        raise ValueError("materialized final50 count mismatch")
    if any(row.get("synthetic") and row.get("positive_evidence_eligible") for row in contexts_out):
        raise ValueError("synthetic context is marked as positive evidence")
    return senses_out, candidates_out, contexts_out, bindings_out
