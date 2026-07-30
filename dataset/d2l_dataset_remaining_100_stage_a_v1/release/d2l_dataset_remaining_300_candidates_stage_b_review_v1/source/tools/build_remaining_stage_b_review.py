from __future__ import annotations

import argparse
import shutil
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

from dataset.d2l_dataset_50_senses_fast_track_stage_a_v1.tools.common import (
    build_deterministic_zip,
    build_file_inventory,
    canonical_json_bytes,
    replace_directory,
    seal_integrity,
    seal_record,
    sha256_bytes,
    sha256_file,
    strict_json_object,
    strict_jsonl,
    verify_integrity,
    write_checksums,
    write_json,
    write_jsonl,
)


ARTIFACT_NAME = "d2l_dataset_remaining_300_candidates_stage_b_review_v1"
POLICY_ID = "d2l-remaining-300-candidates-stage-b-dual-review-v1.0"
CREATED_AT = "2026-07-30T00:00:00Z"
ALLOWED_LABELS = (
    "ACCEPT",
    "CONDITIONAL",
    "REJECT",
    "SPLIT_REQUIRED",
    "HUMAN_UNJUDGEABLE",
)
REPLACED_SENSE_ID = "d2lce_91002293cea2184b43995f47"
REPLACEMENT_SENSE_ID = "d2lce_bad32719ece6439b4716d093"


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _verify_manifest(
    root: Path, allowed_extras: set[str] | None = None
) -> dict[str, Any]:
    manifest = strict_json_object(root / "manifest.json")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        raise ValueError(f"{root.name}: manifest self-hash mismatch")
    expected = manifest.get("files")
    if not isinstance(expected, dict):
        raise ValueError(f"{root.name}: manifest inventory is not an object")
    actual = build_file_inventory(root, {"manifest.json"})
    ignored = set(allowed_extras or set())
    if "CHECKSUMS.sha256" not in expected:
        ignored.add("CHECKSUMS.sha256")
    if set(expected) - set(actual) or set(actual) - set(expected) - ignored:
        raise ValueError(f"{root.name}: manifest inventory mismatch")
    for relative, metadata in expected.items():
        if (
            not isinstance(metadata, Mapping)
            or metadata.get("sha256") != actual[relative].get("sha256")
        ):
            raise ValueError(f"{root.name}: manifest hash mismatch for {relative}")
    return manifest


def _blank_review() -> dict[str, Any]:
    return {
        "allowed_scope": "",
        "candidate_gold_label": "",
        "positive_context_refs": [],
        "reason_codes": [],
        "rejected_variants": [],
        "review_notes": "",
        "review_status": "",
        "validated_variants": [],
        "vietnamese_evidence_refs": [],
    }


def _context_projection(context: Mapping[str, Any]) -> dict[str, Any]:
    context_id = context.get("context_id")
    if not isinstance(context_id, str) or not context_id:
        raise ValueError("context is missing context_id")
    provenance = context.get("provenance")
    if not isinstance(provenance, Mapping):
        provenance = {}
    relation = str(context.get("sense_relation", "SAME_SENSE"))
    synthetic = bool(
        context.get("synthetic")
        or context_id.startswith("ctxx_")
        or str(context.get("contrastive_review_status", "")).startswith(
            "MODEL_GENERATED"
        )
    )
    return {
        "block_id": context.get("block_id", provenance.get("block_id")),
        "boundary_only": bool(synthetic or relation != "SAME_SENSE"),
        "chapter_id": context.get("chapter_id", provenance.get("chapter_id")),
        "content_sha256": context["content_sha256"],
        "context_id": context_id,
        "context_role": context.get(
            "context_role", context.get("context_slot", "")
        ),
        "matched_surface": context.get("matched_surface"),
        "sense_relation": relation,
        "sentence_id": context.get("sentence_id", provenance.get("sentence_id")),
        "source_artifact_sha256": context.get(
            "source_artifact_sha256",
            provenance.get("source_artifact_sha256"),
        ),
        "source_text": context["source_text"],
        "synthetic": synthetic,
    }


def _normalized_candidate(
    candidate: Mapping[str, Any],
    *,
    effective_sense_id: str,
    source_slot_sense_id: str,
) -> dict[str, Any]:
    candidate_id = candidate.get(
        "candidate_instance_id", candidate.get("candidate_id")
    )
    candidate_slot = candidate.get(
        "candidate_slot_id", candidate.get("candidate_slot")
    )
    if not isinstance(candidate_id, str) or not isinstance(candidate_slot, str):
        raise ValueError("candidate identity is incomplete")
    instance_sha = candidate.get("candidate_instance_sha256")
    if not isinstance(instance_sha, str):
        raise ValueError(f"{candidate_id}: missing candidate instance hash")
    target = candidate.get("candidate_target_vi")
    if not isinstance(target, str) or not target.strip():
        raise ValueError(f"{candidate_id}: missing Vietnamese target")
    return {
        "candidate_id": candidate_id,
        "candidate_instance_sha256": instance_sha,
        "candidate_slot": candidate_slot,
        "candidate_target_vi": target,
        "candidate_version": instance_sha,
        "effective_sense_id": effective_sense_id,
        "source_slot_sense_id": source_slot_sense_id,
    }


def _effective_sense(
    *,
    effective_sense_id: str,
    source_slot_sense_id: str,
    source_term: str,
    definition: str,
    part_of_speech: str,
    scope_id: str,
    split: str,
    stratum: str,
    candidate_ids: Sequence[str],
    context_ids: Sequence[str],
    stage_a_authority_sha256: str,
    kind: str,
) -> dict[str, Any]:
    return seal_record(
        {
            "candidate_ids": sorted(candidate_ids),
            "context_ids": sorted(context_ids),
            "definition_en": definition,
            "effective_sense_id": effective_sense_id,
            "kind": kind,
            "part_of_speech": part_of_speech,
            "policy_id": POLICY_ID,
            "schema_id": "D2LRemainingStageBEffectiveSenseV1",
            "schema_version": "1.0",
            "scope_id": scope_id,
            "source_slot_sense_id": source_slot_sense_id,
            "source_term": source_term,
            "split": split,
            "stage_a_authority_sha256": stage_a_authority_sha256,
            "stratum": stratum,
        }
    )


def _materialize_remaining(
    *,
    v3_root: Path,
    stage_b_50_root: Path,
    remaining100_root: Path,
    replacement_root: Path,
    stage_a_complete_root: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    term_senses = strict_jsonl(v3_root / "term_senses.jsonl")
    candidates = strict_jsonl(v3_root / "candidate_instances.jsonl")
    contexts = strict_jsonl(v3_root / "contexts.jsonl")
    sense_by_id = {row["sense_id"]: row for row in term_senses}
    candidate_by_id = {row["candidate_instance_id"]: row for row in candidates}
    context_by_id = {row["context_id"]: row for row in contexts}
    candidates_by_sense: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        candidates_by_sense[candidate["sense_id"]].append(candidate)

    completed_candidate_rows = strict_jsonl(
        stage_b_50_root / "stage_b_gold_150.jsonl"
    )
    completed_sense_ids = {row["sense_id"] for row in completed_candidate_rows}
    completed_candidate_ids = {
        row["candidate_id"] for row in completed_candidate_rows
    }
    if len(completed_sense_ids) != 50 or len(completed_candidate_ids) != 150:
        raise ValueError("completed Stage B authority must contain 50/150")

    remaining_rows = strict_jsonl(remaining100_root / "closure_index_100.jsonl")
    remaining_by_id = {row["sense_id"]: row for row in remaining_rows}
    if len(remaining_by_id) != 100 or not set(remaining_by_id) <= set(sense_by_id):
        raise ValueError("remaining source-slot authority is invalid")
    remaining_v3_candidate_ids = {
        candidate["candidate_instance_id"]
        for sense_id in remaining_by_id
        for candidate in candidates_by_sense[sense_id]
    }
    if remaining_v3_candidate_ids & completed_candidate_ids:
        raise ValueError("completed and remaining candidate authorities overlap")

    child_rows = strict_jsonl(
        remaining100_root / "approved_child_sense_projections_9.jsonl"
    )
    children_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in child_rows:
        children_by_parent[row["parent_source_sense_id"]].append(row)
    if len(children_by_parent) != 4 or len(child_rows) != 9:
        raise ValueError("split child authority must contain four parents/nine children")

    slot_rows = strict_jsonl(
        stage_a_complete_root / "stage_a_source_slot_index_150.jsonl"
    )
    slot_by_id = {row["source_slot_sense_id"]: row for row in slot_rows}
    if len(slot_by_id) != 150:
        raise ValueError("Stage A completion slot index must contain 150 rows")
    replacement_contract = strict_json_object(
        stage_a_complete_root / "replacement_effective_sense_contract.json"
    )
    replacement_source = strict_json_object(
        replacement_root / "replacement_source.json"
    )
    if replacement_contract["sense_id"] != REPLACEMENT_SENSE_ID:
        raise ValueError("replacement contract identity mismatch")

    output_senses: list[dict[str, Any]] = []
    output_candidates: list[dict[str, Any]] = []
    used_context_ids: set[str] = set()
    used_candidate_ids: set[str] = set()

    for source_slot_id in sorted(remaining_by_id):
        parent = sense_by_id[source_slot_id]
        slot = slot_by_id[source_slot_id]
        if source_slot_id == REPLACED_SENSE_ID:
            replacement_candidates = replacement_contract["candidates"]
            replacement_contexts = replacement_contract["evidence_contexts"]
            normalized = [
                _normalized_candidate(
                    row,
                    effective_sense_id=REPLACEMENT_SENSE_ID,
                    source_slot_sense_id=REPLACED_SENSE_ID,
                )
                for row in replacement_candidates
            ]
            output_candidates.extend(normalized)
            used_candidate_ids.update(row["candidate_id"] for row in normalized)
            used_context_ids.update(row["context_id"] for row in replacement_contexts)
            for row in replacement_contexts:
                context_by_id[row["context_id"]] = dict(row)
            output_senses.append(
                _effective_sense(
                    effective_sense_id=REPLACEMENT_SENSE_ID,
                    source_slot_sense_id=REPLACED_SENSE_ID,
                    source_term=replacement_contract["source_term"],
                    definition=replacement_contract["definition_en"],
                    part_of_speech=replacement_contract["part_of_speech"],
                    scope_id=replacement_contract["scope"],
                    split=parent["split"],
                    stratum=replacement_source["stratum"],
                    candidate_ids=[row["candidate_id"] for row in normalized],
                    context_ids=[row["context_id"] for row in replacement_contexts],
                    stage_a_authority_sha256=replacement_contract["record_sha256"],
                    kind="REPLACEMENT",
                )
            )
            continue

        children = children_by_parent.get(source_slot_id)
        if children:
            parent_candidate_ids = {
                row["candidate_instance_id"]
                for row in candidates_by_sense[source_slot_id]
            }
            assigned_candidate_ids: set[str] = set()
            for child in sorted(
                children, key=lambda row: row["temporary_child_sense_id"]
            ):
                payload = child["child_sense_payload"]
                child_id = child["temporary_child_sense_id"]
                assignments = payload["candidate_assignments"]
                normalized = []
                for assignment in assignments:
                    candidate_id = assignment["candidate_id"]
                    candidate = candidate_by_id.get(candidate_id)
                    if candidate is None:
                        raise ValueError(f"unknown child candidate: {candidate_id}")
                    if (
                        candidate["sense_id"] != source_slot_id
                        or candidate["candidate_slot_id"]
                        != assignment["candidate_slot"]
                    ):
                        raise ValueError(f"child candidate binding mismatch: {candidate_id}")
                    revised_candidate = dict(candidate)
                    revised_candidate["candidate_target_vi"] = assignment["target_vi"]
                    revised_candidate["candidate_instance_sha256"] = sha256_bytes(
                        canonical_json_bytes(
                            {
                                "candidate_id": candidate_id,
                                "candidate_slot": assignment["candidate_slot"],
                                "candidate_target_vi": assignment["target_vi"],
                                "effective_sense_id": child_id,
                                "parent_candidate_instance_sha256": candidate[
                                    "candidate_instance_sha256"
                                ],
                                "stage_a_authority_sha256": child["record_sha256"],
                            }
                        )
                    )
                    normalized_candidate = _normalized_candidate(
                        revised_candidate,
                        effective_sense_id=child_id,
                        source_slot_sense_id=source_slot_id,
                    )
                    normalized_candidate["parent_candidate_instance_sha256"] = (
                        candidate["candidate_instance_sha256"]
                    )
                    normalized_candidate["stage_a_repaired_target"] = (
                        assignment["target_vi"] != candidate["candidate_target_vi"]
                    )
                    normalized.append(normalized_candidate)
                    assigned_candidate_ids.add(candidate_id)
                context_ids = payload["context_ids"]
                if any(context_id not in context_by_id for context_id in context_ids):
                    raise ValueError(f"{child_id}: unknown child context")
                output_candidates.extend(normalized)
                used_candidate_ids.update(row["candidate_id"] for row in normalized)
                used_context_ids.update(context_ids)
                output_senses.append(
                    _effective_sense(
                        effective_sense_id=child_id,
                        source_slot_sense_id=source_slot_id,
                        source_term=parent["source_term"],
                        definition=payload["definition_en"],
                        part_of_speech=payload["part_of_speech"],
                        scope_id=payload["scope"],
                        split=parent["split"],
                        stratum=parent["stratum"],
                        candidate_ids=[row["candidate_id"] for row in normalized],
                        context_ids=context_ids,
                        stage_a_authority_sha256=child["record_sha256"],
                        kind="APPROVED_SPLIT_CHILD",
                    )
                )
            if assigned_candidate_ids != parent_candidate_ids:
                raise ValueError(
                    f"{parent['source_term']}: child candidate partition is incomplete"
                )
            continue

        parent_candidates = candidates_by_sense[source_slot_id]
        if len(parent_candidates) != 3:
            raise ValueError(f"{parent['source_term']}: expected three candidates")
        normalized = [
            _normalized_candidate(
                row,
                effective_sense_id=source_slot_id,
                source_slot_sense_id=source_slot_id,
            )
            for row in parent_candidates
        ]
        context_ids = (
            parent["primary_context_ids"]
            + parent["backup_context_ids"]
            + parent["contrastive_context_ids"]
        )
        if any(context_id not in context_by_id for context_id in context_ids):
            raise ValueError(f"{parent['source_term']}: unknown context")
        output_candidates.extend(normalized)
        used_candidate_ids.update(row["candidate_id"] for row in normalized)
        used_context_ids.update(context_ids)
        output_senses.append(
            _effective_sense(
                effective_sense_id=source_slot_id,
                source_slot_sense_id=source_slot_id,
                source_term=parent["source_term"],
                definition=parent["definition"],
                part_of_speech=parent["part_of_speech"],
                scope_id=parent["scope_id"],
                split=parent["split"],
                stratum=parent["stratum"],
                candidate_ids=[row["candidate_id"] for row in normalized],
                context_ids=context_ids,
                stage_a_authority_sha256=slot["authority_record_sha256"],
                kind="UNSPLIT",
            )
        )

    expected_remaining_v3 = set(remaining_v3_candidate_ids) - {
        row["candidate_instance_id"]
        for row in candidates_by_sense[REPLACED_SENSE_ID]
    }
    replacement_ids = {
        row["candidate_id"] for row in replacement_contract["candidates"]
    }
    if used_candidate_ids != expected_remaining_v3 | replacement_ids:
        raise ValueError("remaining candidate coverage is not exact")
    if len(output_senses) != 105 or len(output_candidates) != 300:
        raise ValueError("remaining Stage B materialization must contain 105/300")
    if len(used_candidate_ids) != 300:
        raise ValueError("candidate IDs are not unique")
    output_contexts = [
        {
            **_context_projection(context_by_id[context_id]),
            "context_projection_sha256": sha256_bytes(
                canonical_json_bytes(_context_projection(context_by_id[context_id]))
            ),
        }
        for context_id in sorted(used_context_ids)
    ]
    return (
        sorted(output_senses, key=lambda row: row["effective_sense_id"]),
        sorted(output_candidates, key=lambda row: row["candidate_id"]),
        output_contexts,
    )


def _pack_batches(
    senses: Sequence[Mapping[str, Any]],
    candidates_by_sense: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[tuple[str, list[Mapping[str, Any]]]]:
    bins: list[list[Mapping[str, Any]]] = [[] for _ in range(10)]
    counts = [0] * 10
    ordered = sorted(
        senses,
        key=lambda row: (
            -len(candidates_by_sense[row["effective_sense_id"]]),
            row["effective_sense_id"],
        ),
    )
    for sense in ordered:
        size = len(candidates_by_sense[sense["effective_sense_id"]])
        target = next(
            (index for index, count in enumerate(counts) if count + size <= 30),
            None,
        )
        if target is None:
            raise ValueError("cannot pack effective senses into ten 30-case batches")
        bins[target].append(sense)
        counts[target] += size
    if counts != [30] * 10:
        raise ValueError(f"Stage B batch candidate counts are not exact: {counts}")
    return [
        (f"batch_{index + 1:03d}", sorted(rows, key=lambda row: row["effective_sense_id"]))
        for index, rows in enumerate(bins)
    ]


def _candidate_case(
    *,
    sense: Mapping[str, Any],
    candidate: Mapping[str, Any],
    contexts: Sequence[Mapping[str, Any]],
    reviewer_slot: str,
    batch_id: str,
) -> dict[str, Any]:
    source_payload = {
        "batch_id": batch_id,
        "candidate_id": candidate["candidate_id"],
        "candidate_instance_sha256": candidate["candidate_instance_sha256"],
        "candidate_target_vi": candidate["candidate_target_vi"],
        "candidate_version": candidate["candidate_version"],
        "contexts": list(contexts),
        "definition_en": sense["definition_en"],
        "effective_sense_id": sense["effective_sense_id"],
        "part_of_speech": sense["part_of_speech"],
        "policy_id": POLICY_ID,
        "schema_id": "D2LRemainingStageBCandidateReviewSourceV1",
        "schema_version": "1.0",
        "scope_id": sense["scope_id"],
        "source_slot_sense_id": sense["source_slot_sense_id"],
        "source_term": sense["source_term"],
    }
    return seal_record(
        {
            "batch_id": batch_id,
            "case_id": "stageb_remaining_"
            + sha256_bytes(
                f"{batch_id}\x1f{candidate['candidate_id']}\x1f{reviewer_slot}".encode(
                    "utf-8"
                )
            )[:24],
            "final_glossary_decision": None,
            "final_gold_label": None,
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "review": _blank_review(),
            "reviewer_slot": reviewer_slot,
            "schema_id": "D2LRemainingStageBCandidateReviewCaseV1",
            "schema_version": "1.0",
            "source_payload": source_payload,
            "source_payload_sha256": sha256_bytes(
                canonical_json_bytes(source_payload)
            ),
        },
        "case_sha256",
    )


def _reviewer_payload(
    *,
    batch_id: str,
    senses: Sequence[Mapping[str, Any]],
    candidates_by_sense: Mapping[str, Sequence[Mapping[str, Any]]],
    contexts_by_id: Mapping[str, Mapping[str, Any]],
    reviewer_slot: str,
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for sense in senses:
        sense_id = sense["effective_sense_id"]
        candidates = sorted(
            candidates_by_sense[sense_id],
            key=lambda row: sha256_bytes(
                f"{reviewer_slot}\x1f{row['candidate_id']}".encode("utf-8")
            ),
        )
        contexts = [contexts_by_id[value] for value in sense["context_ids"]]
        for candidate in candidates:
            cases.append(
                _candidate_case(
                    sense=sense,
                    candidate=candidate,
                    contexts=contexts,
                    reviewer_slot=reviewer_slot,
                    batch_id=batch_id,
                )
            )
    source_binding = [
        {"case_id": row["case_id"], "case_sha256": row["case_sha256"]}
        for row in cases
    ]
    return {
        "allowed_candidate_gold_labels": list(ALLOWED_LABELS),
        "batch_id": batch_id,
        "case_count": len(cases),
        "cases": cases,
        "final_glossary_decision": None,
        "final_gold_label_count": 0,
        "independence_requirement": "DO_NOT_VIEW_OTHER_REVIEWER_OUTPUTS",
        "policy_id": POLICY_ID,
        "provider_call_count": 0,
        "return_contract": "RETURN_THIS_JSON_WITH_ONLY_REVIEW_FIELDS_FILLED",
        "reviewer_slot": reviewer_slot,
        "schema_id": "D2LRemainingStageBCandidateReviewerInputV1",
        "schema_version": "1.0",
        "sense_count": len(senses),
        "source_input_sha256": sha256_bytes(
            canonical_json_bytes(source_binding)
        ),
    }


def _write_instructions(path: Path, reviewer_slot: str) -> None:
    path.write_text(
        "# Stage B independent candidate review\n\n"
        f"Complete all 300 cases as {reviewer_slot}. Work independently and do not "
        "view another reviewer output. Use only the supplied English sense, "
        "Vietnamese candidate, and D2L contexts. Fill only each `review` object. "
        "Choose one candidate_gold_label from ACCEPT, CONDITIONAL, REJECT, "
        "SPLIT_REQUIRED, HUMAN_UNJUDGEABLE. ACCEPT/CONDITIONAL must list the "
        "candidate in validated_variants and cite at least one real SAME_SENSE "
        "context in positive_context_refs. REJECT must list it in rejected_variants. "
        "Synthetic or boundary-only contexts cannot be positive evidence. Provide "
        "reason_codes, nonblank review_notes, and review_status=COMPLETE. Preserve "
        "all source fields and hashes. Do not assign final gold, C/E output, rank, "
        "winner, or final glossary decision. Return reviewer_input_full.json only.\n",
        encoding="utf-8",
        newline="\n",
    )


def _copy_source_bundle(staging: Path) -> None:
    module_root = Path(__file__).resolve().parent
    project_root = module_root.parent
    for name in (
        "build_remaining_stage_b_review.py",
        "validate_remaining_stage_b_review.py",
    ):
        destination = staging / "source" / "tools" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(module_root / name, destination)
    destination = staging / "source" / "tests" / "test_remaining_stage_b_review.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        project_root / "tests" / "test_remaining_stage_b_review.py",
        destination,
    )


def build_remaining_stage_b_review(
    *,
    v3_root: Path,
    stage_b_50_root: Path,
    remaining100_root: Path,
    replacement_root: Path,
    stage_a_complete_root: Path,
    output_root: Path,
    zip_path: Path,
) -> dict[str, Any]:
    roots = {
        "v3": v3_root.resolve(strict=True),
        "stage_b_50": stage_b_50_root.resolve(strict=True),
        "remaining100": remaining100_root.resolve(strict=True),
        "replacement": replacement_root.resolve(strict=True),
        "stage_a_complete": stage_a_complete_root.resolve(strict=True),
    }
    output_root = output_root.resolve()
    zip_path = zip_path.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    manifests = {
        key: _verify_manifest(
            root,
            {
                "handoff/switch_replacement_reviewer_1.json",
                "handoff/switch_replacement_reviewer_2.json",
            }
            if key == "replacement"
            else None,
        )
        for key, root in roots.items()
    }
    completion_authority = strict_json_object(
        roots["stage_a_complete"] / "authority.json"
    )
    if not verify_integrity(completion_authority):
        raise ValueError("Stage A completion authority self-hash mismatch")
    for key in ("stage_b_50", "remaining100", "replacement"):
        expected = completion_authority["manifests"][key]
        if (
            expected["self_sha256"] != manifests[key]["manifest_sha256"]
            or expected["physical_sha256"]
            != sha256_file(roots[key] / "manifest.json")
        ):
            raise ValueError(f"Stage A completion authority drift: {key}")

    senses, candidates, contexts = _materialize_remaining(
        v3_root=roots["v3"],
        stage_b_50_root=roots["stage_b_50"],
        remaining100_root=roots["remaining100"],
        replacement_root=roots["replacement"],
        stage_a_complete_root=roots["stage_a_complete"],
    )
    candidates_by_sense: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        candidates_by_sense[candidate["effective_sense_id"]].append(candidate)
    contexts_by_id = {row["context_id"]: row for row in contexts}
    batches = _pack_batches(senses, candidates_by_sense)

    with tempfile.TemporaryDirectory(
        prefix="remaining-stage-b-review-", dir=output_root.parent
    ) as name:
        staging = Path(name) / ARTIFACT_NAME
        staging.mkdir(parents=True)
        write_jsonl(staging / "effective_senses_105.jsonl", senses)
        write_jsonl(staging / "candidate_instances_300.jsonl", candidates)
        write_jsonl(staging / "contexts_selected.jsonl", contexts)
        write_json(
            staging / "batch_index.json",
            seal_integrity(
                {
                    "batch_count": 10,
                    "batches": [
                        {
                            "batch_id": batch_id,
                            "candidate_count": sum(
                                len(candidates_by_sense[row["effective_sense_id"]])
                                for row in rows
                            ),
                            "effective_sense_count": len(rows),
                            "effective_sense_ids": [
                                row["effective_sense_id"] for row in rows
                            ],
                        }
                        for batch_id, rows in batches
                    ],
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LRemainingStageBBatchIndexV1",
                    "schema_version": "1.0",
                }
            ),
        )
        handoffs = []
        for reviewer_slot in ("reviewer_1", "reviewer_2"):
            handoff_tree = staging / ".handoff" / reviewer_slot
            all_cases: list[dict[str, Any]] = []
            for batch_id, batch_senses in batches:
                payload = _reviewer_payload(
                    batch_id=batch_id,
                    senses=batch_senses,
                    candidates_by_sense=candidates_by_sense,
                    contexts_by_id=contexts_by_id,
                    reviewer_slot=reviewer_slot,
                )
                all_cases.extend(payload["cases"])
                write_json(
                    staging
                    / "review_batches"
                    / batch_id
                    / f"{reviewer_slot}_input.json",
                    payload,
                )
                write_json(
                    handoff_tree / "batches" / batch_id / "reviewer_input.json",
                    payload,
                )
            source_binding = [
                {"case_id": row["case_id"], "case_sha256": row["case_sha256"]}
                for row in all_cases
            ]
            full_payload = {
                "allowed_candidate_gold_labels": list(ALLOWED_LABELS),
                "batch_count": 10,
                "batches": [batch_id for batch_id, _ in batches],
                "case_count": 300,
                "cases": all_cases,
                "effective_sense_count": 105,
                "final_glossary_decision": None,
                "final_gold_label_count": 0,
                "independence_requirement": "DO_NOT_VIEW_OTHER_REVIEWER_OUTPUTS",
                "policy_id": POLICY_ID,
                "provider_call_count": 0,
                "return_contract": "RETURN_THIS_JSON_WITH_ONLY_REVIEW_FIELDS_FILLED",
                "reviewer_slot": reviewer_slot,
                "schema_id": "D2LRemainingStageBCandidateReviewerFullInputV1",
                "schema_version": "1.0",
                "source_input_sha256": sha256_bytes(
                    canonical_json_bytes(source_binding)
                ),
            }
            write_json(staging / f"{reviewer_slot}_full_input.json", full_payload)
            write_json(handoff_tree / "reviewer_input_full.json", full_payload)
            _write_instructions(
                handoff_tree / "REVIEW_INSTRUCTIONS.md", reviewer_slot
            )
            (handoff_tree / "MESSAGE.md").write_text(
                "Complete reviewer_input_full.json and return it as "
                f"{reviewer_slot}.json. Return the file only, without raw prose.\n",
                encoding="utf-8",
                newline="\n",
            )
            handoff_zip = staging / "handoff" / f"{reviewer_slot}.zip"
            build_deterministic_zip(handoff_tree, handoff_zip)
            handoffs.append(
                {
                    "case_count": 300,
                    "path": f"handoff/{reviewer_slot}.zip",
                    "reviewer_slot": reviewer_slot,
                    "sha256": sha256_file(handoff_zip),
                }
            )
        shutil.rmtree(staging / ".handoff")
        write_jsonl(
            staging / "stage_b_gold_300_template.jsonl",
            [
                {
                    "adjudication_label": None,
                    "candidate_id": row["candidate_id"],
                    "effective_sense_id": row["effective_sense_id"],
                    "final_gold_label": None,
                    "reviewer_1_label": None,
                    "reviewer_2_label": None,
                }
                for row in candidates
            ],
        )
        write_json(
            staging / "authority.json",
            seal_integrity(
                {
                    "manifests": {
                        key: {
                            "physical_sha256": sha256_file(root / "manifest.json"),
                            "self_sha256": manifests[key]["manifest_sha256"],
                        }
                        for key, root in roots.items()
                    },
                    "policy_id": POLICY_ID,
                    "schema_id": "D2LRemainingStageBReviewAuthorityV1",
                    "schema_version": "1.0",
                    "stage_a_completion_authority_self_sha256": completion_authority[
                        "integrity"
                    ]["self_sha256"],
                }
            ),
        )
        write_json(
            staging / "release_summary.json",
            seal_integrity(
                {
                    "batch_count": 10,
                    "candidate_count": 300,
                    "effective_sense_count": 105,
                    "final_glossary_decision": None,
                    "handoffs": handoffs,
                    "policy_id": POLICY_ID,
                    "provider_call_count": 0,
                    "reviewer_count": 2,
                    "reviewer_case_count_each": 300,
                    "schema_id": "D2LRemainingStageBReviewSummaryV1",
                    "schema_version": "1.0",
                    "stage_b_gold_autofill_count": 0,
                    "status": "READY_FOR_STAGE_B_DUAL_REVIEW_ZERO_PROVIDER",
                }
            ),
        )
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L remaining Stage B review handoff\n\n"
            "- Effective senses: 105.\n"
            "- Candidate cases: 300.\n"
            "- Reviewers: 2 independent full inputs.\n"
            "- Batches: 10 x 30 candidate cases.\n"
            "- Stage B gold autofill: 0.\n"
            "- Provider calls: 0.\n"
            "- Final glossary decision: null.\n",
            encoding="utf-8",
            newline="\n",
        )
        _copy_source_bundle(staging)
        files = build_file_inventory(
            staging, excluded={"CHECKSUMS.sha256", "manifest.json"}
        )
        manifest = {
            "artifact_name": ARTIFACT_NAME,
            "counts": {
                "batch": 10,
                "candidate": 300,
                "effective_sense": 105,
                "reviewer": 2,
                "reviewer_case_each": 300,
                "stage_b_gold_autofill": 0,
            },
            "created_at": CREATED_AT,
            "file_count": len(files),
            "files": files,
            "final_glossary_decision": None,
            "policy_id": POLICY_ID,
            "provider_call_count": 0,
            "schema_id": "D2LRemainingStageBReviewManifestV1",
            "schema_version": "1.0",
            "status": "READY_FOR_STAGE_B_DUAL_REVIEW_ZERO_PROVIDER",
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        from .validate_remaining_stage_b_review import validate_artifact

        errors = validate_artifact(staging)
        if errors:
            raise ValueError("; ".join(errors))
        replace_directory(staging, output_root)
    build_deterministic_zip(output_root, zip_path)
    return {
        "artifact_root": str(output_root),
        "manifest_sha256": strict_json_object(output_root / "manifest.json")[
            "manifest_sha256"
        ],
        "reviewer_1_zip_sha256": sha256_file(
            output_root / "handoff" / "reviewer_1.zip"
        ),
        "reviewer_2_zip_sha256": sha256_file(
            output_root / "handoff" / "reviewer_2.zip"
        ),
        "status": "READY_FOR_STAGE_B_DUAL_REVIEW_ZERO_PROVIDER",
        "zip_path": str(zip_path),
        "zip_sha256": sha256_file(zip_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v3-root", type=Path, required=True)
    parser.add_argument("--stage-b-50-root", type=Path, required=True)
    parser.add_argument("--remaining100-root", type=Path, required=True)
    parser.add_argument("--replacement-root", type=Path, required=True)
    parser.add_argument("--stage-a-complete-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path, required=True)
    args = parser.parse_args()
    result = build_remaining_stage_b_review(
        v3_root=args.v3_root,
        stage_b_50_root=args.stage_b_50_root,
        remaining100_root=args.remaining100_root,
        replacement_root=args.replacement_root,
        stage_a_complete_root=args.stage_a_complete_root,
        output_root=args.output_root,
        zip_path=args.zip_path,
    )
    print(canonical_json_bytes(result).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
