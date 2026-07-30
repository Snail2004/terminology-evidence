from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .common import (
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_integrity,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_jsonl,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from .contract_projection_50 import (
        CONTRACT_COMMIT,
        CONTRACT_MANIFEST_SHA256,
        CONTRACT_RECEIPT_PHYSICAL_SHA256,
        CONTRACT_RECEIPT_SELF_SHA256,
        CONTRACT_TAG,
        constraint_evidence_package,
        effective_sense_contract,
        frozen_candidate_contract,
        load_contract_authority,
    )
    from .final50 import (
        FINAL_DATASET_VERSION,
        FINAL_POLICY_ID,
        assign_splits,
        load_d_stage_a_outcomes,
        materialize_selected_records,
        select_exact_50,
    )
    from .validate_fast_track_stage_a import validate_artifact as validate_base
    from .validate_r0_reaudit_result import validate_artifact as validate_r0_result
    from .validate_stage_a_adjudication_result import validate_result as validate_adjudication
    from .validate_stage_a_review_intake import validate_intake
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_integrity,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_jsonl,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from contract_projection_50 import (  # type: ignore
        CONTRACT_COMMIT,
        CONTRACT_MANIFEST_SHA256,
        CONTRACT_RECEIPT_PHYSICAL_SHA256,
        CONTRACT_RECEIPT_SELF_SHA256,
        CONTRACT_TAG,
        constraint_evidence_package,
        effective_sense_contract,
        frozen_candidate_contract,
        load_contract_authority,
    )
    from final50 import (  # type: ignore
        FINAL_DATASET_VERSION,
        FINAL_POLICY_ID,
        assign_splits,
        load_d_stage_a_outcomes,
        materialize_selected_records,
        select_exact_50,
    )
    from validate_fast_track_stage_a import validate_artifact as validate_base  # type: ignore
    from validate_r0_reaudit_result import validate_artifact as validate_r0_result  # type: ignore
    from validate_stage_a_adjudication_result import validate_result as validate_adjudication  # type: ignore
    from validate_stage_a_review_intake import validate_intake  # type: ignore


ARTIFACT_NAME = "d2l_dataset_50_senses_150_candidates_stage_b_review_v1"
STATUS = "READY_FOR_STAGE_B_DUAL_REVIEW"
STAGE_B_POLICY_ID = "d2l-stage-b-50-senses-dual-review-v1.0"
ALLOWED_LABELS = (
    "ACCEPT",
    "CONDITIONAL",
    "REJECT",
    "SPLIT_REQUIRED",
    "HUMAN_UNJUDGEABLE",
)


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _extract_release(zip_path: Path, destination: Path) -> Path:
    with zipfile.ZipFile(zip_path) as archive:
        for info in archive.infolist():
            name = info.filename
            parts = Path(name).parts
            if name.startswith("/") or "\\" in name or ".." in parts:
                raise ValueError(f"unsafe release ZIP path: {name}")
        archive.extractall(destination)
    return destination


def _blank_review() -> dict[str, Any]:
    return {
        "candidate_gold_label": "",
        "allowed_scope": "",
        "validated_variants": [],
        "rejected_variants": [],
        "reason_codes": [],
        "positive_context_refs": [],
        "vietnamese_evidence_refs": [],
        "review_notes": "",
        "review_status": "",
    }


def _context_projection(context: Mapping[str, Any]) -> dict[str, Any]:
    context_id = context.get("context_id", context.get("source_context_id"))
    if not isinstance(context_id, str) or not context_id:
        raise ValueError("review context is missing its source context ID")
    return {
        "context_id": context_id,
        "context_role": context.get("context_role", context.get("context_slot", "")),
        "sense_relation": context.get("sense_relation", "SAME_SENSE"),
        "boundary_only": bool(context.get("synthetic") or context.get("sense_relation") != "SAME_SENSE"),
        "synthetic": bool(context.get("synthetic")),
        "source_text": context["source_text"],
        "matched_surface": context.get("matched_surface"),
        "content_sha256": context["content_sha256"],
        "chapter_id": context.get("chapter_id"),
        "block_id": context.get("block_id"),
        "sentence_id": context.get("sentence_id"),
        "source_artifact_sha256": context.get("source_artifact_sha256"),
    }


def _candidate_case(
    *,
    sense: Mapping[str, Any],
    candidate: Mapping[str, Any],
    contexts: Sequence[Mapping[str, Any]],
    reviewer_slot: str,
    batch_id: str,
) -> dict[str, Any]:
    source_payload = {
        "schema_id": "D2LStageB50CandidateReviewSourceV1",
        "schema_version": "1.0.0",
        "policy_id": STAGE_B_POLICY_ID,
        "batch_id": batch_id,
        "term_id": sense["term_id"],
        "sense_id": sense["sense_id"],
        "source_term": sense["source_term"],
        "definition_en": sense["definition"],
        "part_of_speech": sense["part_of_speech"],
        "scope_id": sense["scope_id"],
        "candidate_id": candidate["candidate_instance_id"],
        "candidate_version": candidate["candidate_version"],
        "candidate_target_vi": candidate["candidate_target_vi"],
        "candidate_instance_sha256": candidate["candidate_instance_sha256"],
        "contexts": [_context_projection(row) for row in contexts],
    }
    return seal_record(
        {
            "schema_id": "D2LStageB50CandidateReviewCaseV1",
            "schema_version": "1.0.0",
            "policy_id": STAGE_B_POLICY_ID,
            "case_id": "stageb50_" + sha256_bytes(
                f"{batch_id}\x1f{sense['sense_id']}\x1f{candidate['candidate_instance_id']}\x1f{reviewer_slot}".encode()
            )[:24],
            "batch_id": batch_id,
            "reviewer_slot": reviewer_slot,
            "source_payload": source_payload,
            "source_payload_sha256": sha256_bytes(canonical_json_bytes(source_payload)),
            "review": _blank_review(),
            "provider_call_count": 0,
            "final_gold_label": None,
            "final_glossary_decision": None,
        },
        "case_sha256",
    )


def _case_sort_key(row: Mapping[str, Any], reviewer_slot: str) -> str:
    return sha256_bytes(f"{reviewer_slot}\x1f{row['candidate_instance_id']}".encode())


def _build_reviewer_payload(
    *,
    sense_by_id: Mapping[str, Mapping[str, Any]],
    candidates_by_sense: Mapping[str, Sequence[Mapping[str, Any]]],
    contexts_by_sense: Mapping[str, Sequence[Mapping[str, Any]]],
    batch_rows: Sequence[Mapping[str, Any]],
    reviewer_slot: str,
    batch_id: str,
) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    for sense in sorted(batch_rows, key=lambda row: row["source_term"].casefold()):
        candidates = sorted(
            candidates_by_sense[sense["sense_id"]],
            key=lambda row: _case_sort_key(row, reviewer_slot),
        )
        for candidate in candidates:
            cases.append(
                _candidate_case(
                    sense=sense,
                    candidate=candidate,
                    contexts=contexts_by_sense[sense["sense_id"]],
                    reviewer_slot=reviewer_slot,
                    batch_id=batch_id,
                )
            )
    source_input = [{"case_id": row["case_id"], "case_sha256": row["case_sha256"]} for row in cases]
    return {
        "schema_id": "D2LStageB50CandidateReviewerInputV1",
        "schema_version": "1.0.0",
        "policy_id": STAGE_B_POLICY_ID,
        "batch_id": batch_id,
        "reviewer_slot": reviewer_slot,
        "case_count": len(cases),
        "sense_count": len(batch_rows),
        "allowed_candidate_gold_labels": list(ALLOWED_LABELS),
        "independence_requirement": "DO_NOT_VIEW_OTHER_REVIEWER_OUTPUTS",
        "return_contract": "RETURN_THIS_JSON_WITH_ONLY_REVIEW_FIELDS_FILLED",
        "cases": cases,
        "source_input_sha256": sha256_bytes(canonical_json_bytes(source_input)),
        "provider_call_count": 0,
        "final_gold_label_count": 0,
        "final_glossary_decision": None,
    }


def _write_reviewer_instructions(path: Path, reviewer_slot: str) -> None:
    path.write_text(
        "# Stage B dual candidate review\n\n"
        f"Review all supplied cases as {reviewer_slot}, independently.\n\n"
        "Use only the supplied English sense, Vietnamese candidate, and D2L source contexts. "
        "Do not infer or record an intended candidate role. Fill only the `review` object. "
        "Choose exactly one candidate_gold_label from ACCEPT, CONDITIONAL, REJECT, "
        "SPLIT_REQUIRED, HUMAN_UNJUDGEABLE. Use positive_context_refs only for supplied "
        "real same-sense contexts. Synthetic/boundary contexts are not positive evidence. "
        "Preserve every source field and hash; do not change case IDs, candidate IDs, or "
        "context text. Set review_status=COMPLETE and return the same JSON structure.\n\n"
        "Do not open or rely on any other reviewer's file. This is a Stage B review only; "
        "do not assign final gold, C/E results, or final glossary decisions.\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    for relative in (
        ".gitattributes",
        "README.md",
        "tools/__init__.py",
        "tools/common.py",
        "tools/spec.py",
        "tools/final50.py",
        "tools/contract_projection_50.py",
        "tools/build_final50_stage_b.py",
        "tools/validate_final50_stage_b.py",
        "tests/test_final50_stage_b.py",
    ):
        source = namespace / relative
        if not source.is_file():
            raise ValueError(f"missing source bundle file: {relative}")
        destination = staging / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def _write_reviewer_handoff(
    staging: Path,
    reviewer_slot: str,
    payloads: Sequence[tuple[str, dict[str, Any]]],
    full_payload: dict[str, Any],
) -> tuple[str, str]:
    handoff_tree = staging / ".handoff" / reviewer_slot
    handoff_tree.mkdir(parents=True)
    write_json(handoff_tree / "reviewer_input_full.json", full_payload)
    for batch_id, payload in payloads:
        write_json(handoff_tree / "batches" / batch_id / "reviewer_input.json", payload)
    _write_reviewer_instructions(handoff_tree / "REVIEW_INSTRUCTIONS.md", reviewer_slot)
    (handoff_tree / "MESSAGE.md").write_text(
        f"Return the completed reviewer_input_full.json as {reviewer_slot}. "
        "Do not return raw prose or alter source fields.\n",
        encoding="utf-8",
        newline="\n",
    )
    handoff_zip = staging / "handoff" / f"{reviewer_slot}.zip"
    build_deterministic_zip(handoff_tree, handoff_zip)
    return f"handoff/{reviewer_slot}.zip", sha256_file(handoff_zip)


def build_final50_stage_b(
    *,
    repo_root: Path,
    base_release_zip: Path,
    intake_release_zip: Path,
    adjudication_release_zip: Path,
    r0_result_release_zip: Path,
    output_root: Path,
    created_at: str,
) -> dict[str, Any]:
    repo_root = repo_root.resolve(strict=True)
    base_release_zip = base_release_zip.resolve(strict=True)
    intake_release_zip = intake_release_zip.resolve(strict=True)
    adjudication_release_zip = adjudication_release_zip.resolve(strict=True)
    r0_result_release_zip = r0_result_release_zip.resolve(strict=True)
    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent))
    source_dir = temporary / "sources"
    source_dir.mkdir()
    base_root = _extract_release(base_release_zip, source_dir / "base")
    intake_root = _extract_release(intake_release_zip, source_dir / "intake")
    adjudication_root = _extract_release(adjudication_release_zip, source_dir / "adjudication")
    r0_root = _extract_release(r0_result_release_zip, source_dir / "r0")
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        source_errors = []
        source_errors.extend(f"base: {e}" for e in validate_base(base_root))
        source_errors.extend(f"intake: {e}" for e in validate_intake(intake_root, canonical_root=base_root))
        source_errors.extend(f"adjudication: {e}" for e in validate_adjudication(adjudication_root, intake_root=intake_root))
        source_errors.extend(f"r0: {e}" for e in validate_r0_result(r0_root))
        if source_errors:
            raise ValueError("source release validation failed: " + "; ".join(source_errors))

        base_manifest = json.loads((base_root / "manifest.json").read_text(encoding="utf-8"))
        intake_manifest = json.loads((intake_root / "manifest.json").read_text(encoding="utf-8"))
        adjudication_manifest = json.loads((adjudication_root / "manifest.json").read_text(encoding="utf-8"))
        r0_manifest = json.loads((r0_root / "manifest.json").read_text(encoding="utf-8"))
        pool = [json.loads(line) for line in (base_root / "master_pool_60.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        candidate_pool = [json.loads(line) for line in (base_root / "candidate_inventory_180.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        contexts_pool = [json.loads(line) for line in (base_root / "contexts_selected.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        selected, excluded, swaps = select_exact_50(pool, contexts_pool)
        assignments, component_report = assign_splits(selected, contexts_pool)
        d_outcomes = load_d_stage_a_outcomes(
            intake_root=intake_root,
            adjudication_root=adjudication_root,
            r0_result_root=r0_root,
        )
        senses, candidates, contexts, bindings = materialize_selected_records(
            selected=selected,
            candidates=candidate_pool,
            contexts=contexts_pool,
            assignments=assignments,
            d_outcomes=d_outcomes,
        )
        split_manifest = seal_integrity(
            {
                "schema_id": "D2LFinal50SplitManifestV1",
                "schema_version": "1.0.0",
                "policy_id": FINAL_POLICY_ID,
                "dataset_version": FINAL_DATASET_VERSION,
                "split_policy": "SENSE_ID_LEAKAGE_COMPONENTS_SENTENCE_OR_BLOCK_V1",
                "split_quotas": {"development": 30, "validation": 10, "test": 10},
                "selected_sense_ids": [row["sense_id"] for row in senses],
                "assignments": dict(sorted(assignments.items())),
                "counts": {
                    split: sum(1 for value in assignments.values() if value == split)
                    for split in ("development", "validation", "test")
                },
                "stratum_counts": {
                    split: dict(
                        sorted(
                            Counter(
                                row["stratum"]
                                for row in selected
                                if assignments[row["sense_id"]] == split
                            ).items()
                        )
                    )
                    for split in ("development", "validation", "test")
                },
                "leakage_components": component_report,
                "provider_call_count": 0,
                "stage_b_gold_autofill_count": 0,
                "final_glossary_decision": None,
            }
        )
        dataset_manifest_sha256 = split_manifest["integrity"]["self_sha256"]
        write_json(staging / "split_manifest_30_10_10.json", split_manifest)
        write_jsonl(staging / "term_senses_50.jsonl", senses)
        write_jsonl(staging / "candidate_instances_150.jsonl", candidates)
        write_jsonl(staging / "contexts_selected_50.jsonl", contexts)
        write_jsonl(staging / "stage_a_review_bindings_50.jsonl", bindings)

        execution_config_sha256 = sha256_bytes(
            canonical_json_bytes(
                {
                    "policy_id": FINAL_POLICY_ID,
                    "contract_authority_manifest_sha256": CONTRACT_MANIFEST_SHA256,
                    "base_manifest_sha256": base_manifest["manifest_sha256"],
                    "split_manifest_sha256": dataset_manifest_sha256,
                    "selected_sense_ids": [row["sense_id"] for row in senses],
                }
            )
        )
        seal_self_hash, seal_frozen, map_candidate_key = load_contract_authority(repo_root)
        effective_contracts: dict[str, dict[str, Any]] = {}
        frozen_contracts: list[dict[str, Any]] = []
        constraint_packages: list[dict[str, Any]] = []
        candidates_by_sense: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for candidate in candidates:
            candidates_by_sense[candidate["sense_id"]].append(candidate)
        bindings_by_sense = {row["sense_id"]: row for row in bindings}
        for sense in senses:
            sense_id = sense["sense_id"]
            source_hashes = {
                "base_dataset_manifest": base_manifest["manifest_sha256"],
                "base_dataset_manifest_physical": sha256_file(base_root / "manifest.json"),
                "review_intake_manifest": intake_manifest["manifest_sha256"],
                "adjudication_manifest": adjudication_manifest["manifest_sha256"],
                "r0_result_manifest": r0_manifest["manifest_sha256"],
                "term_sense": sense["term_sense_sha256"],
                "review_binding": bindings_by_sense[sense_id]["review_binding_sha256"],
            }
            effective = effective_sense_contract(
                sense=sense,
                candidates=candidates_by_sense[sense_id],
                review_binding_sha256=bindings_by_sense[sense_id]["review_binding_sha256"],
                dataset_manifest_sha256=dataset_manifest_sha256,
                created_at=created_at,
                execution_config_sha256=execution_config_sha256,
                source_hashes=source_hashes,
                seal_self_hash=seal_self_hash,
            )
            effective_contracts[sense_id] = effective
            write_json(staging / "effective_sense_contracts_50" / f"{sense_id}.json", effective)
            for candidate in candidates_by_sense[sense_id]:
                candidate_hashes = {**source_hashes, "candidate_instance": candidate["candidate_instance_sha256"]}
                frozen = frozen_candidate_contract(
                    candidate=candidate,
                    sense=sense,
                    sense_candidates=candidates_by_sense[sense_id],
                    effective=effective,
                    dataset_manifest_sha256=dataset_manifest_sha256,
                    created_at=created_at,
                    execution_config_sha256=execution_config_sha256,
                    source_hashes=candidate_hashes,
                    seal_frozen_candidate_contract=seal_frozen,
                    map_candidate_key=map_candidate_key,
                )
                frozen_contracts.append(frozen)
                frozen_path = f"frozen_candidate_contracts_150/{candidate['candidate_instance_id']}.json"
                write_json(staging / frozen_path, frozen)
                constraint = constraint_evidence_package(
                    frozen=frozen,
                    effective=effective,
                    review_binding_path=f"stage_a_review_bindings/{sense_id}.json",
                    review_binding_sha256=bindings_by_sense[sense_id]["review_binding_sha256"],
                    sense=sense,
                    created_at=created_at,
                    execution_config_sha256=execution_config_sha256,
                    source_hashes=candidate_hashes,
                    seal_self_hash=seal_self_hash,
                )
                constraint_packages.append(constraint)
                write_json(
                    staging / f"constraint_evidence_packages_150/{candidate['candidate_instance_id']}.json",
                    constraint,
                )

        candidate_index = []
        for frozen, constraint in zip(
            frozen_contracts, constraint_packages
        ):
            key = frozen["candidate_key"]
            candidate_id = key["candidate_id"]
            sense_id = key["sense_id"]
            candidate_index.append(
                {
                    "candidate_id": candidate_id,
                    "sense_id": sense_id,
                    "source_term": key["source_term"],
                    "candidate_vi": key["candidate_vi"],
                    "candidate_version": key["candidate_version"],
                    "effective_sense_path": f"effective_sense_contracts_50/{sense_id}.json",
                    "effective_sense_sha256": key["effective_sense_contract_sha256"],
                    "frozen_candidate_path": f"frozen_candidate_contracts_150/{candidate_id}.json",
                    "frozen_candidate_sha256": frozen["integrity"]["self_sha256"],
                    "input_contract_sha256": frozen["input_contract_sha256"],
                    "constraint_evidence_path": f"constraint_evidence_packages_150/{candidate_id}.json",
                    "constraint_evidence_sha256": constraint["integrity"]["self_sha256"],
                    "binding_status": "COMPLETE",
                }
            )
        write_json(
            staging / "candidate_index_150.json",
            seal_integrity(
                {
                    "schema_id": "D2LFinal50CandidateIndexV1",
                    "schema_version": "1.0.0",
                    "policy_id": FINAL_POLICY_ID,
                    "candidate_count": 150,
                    "entries": sorted(candidate_index, key=lambda row: row["candidate_id"]),
                    "final_glossary_decision": None,
                }
            ),
        )

        # Build five review batches: the locked official lane first, then 10/10/10/15.
        selected_by_id = {row["sense_id"]: row for row in senses}
        lane_a = [row for row in senses if row["lane"] == "A_OFFICIAL"]
        remainder = [row for row in senses if row["lane"] != "A_OFFICIAL"]
        batch_groups: list[tuple[str, list[dict[str, Any]]]] = [("batch_000", sorted(lane_a, key=lambda row: row["source_term"].casefold()))]
        for index, size in enumerate((10, 10, 10, 15), start=1):
            start = sum((10, 10, 10, 15)[: index - 1])
            batch_groups.append((f"batch_{index:03d}", sorted(remainder, key=lambda row: row["sense_id"])[start : start + size]))
        if sum(len(group) for _, group in batch_groups) != 50:
            raise ValueError("Stage B batch sense count mismatch")
        contexts_by_sense = defaultdict(list)
        for context in contexts:
            contexts_by_sense[context["sense_id"]].append(context)
        candidates_by_sense = defaultdict(list)
        for candidate in candidates:
            candidates_by_sense[candidate["sense_id"]].append(candidate)
        handoff_summary = []
        full_payloads: dict[str, dict[str, Any]] = {}
        for reviewer_slot in ("reviewer_1", "reviewer_2"):
            batch_payloads = []
            all_cases = []
            for batch_id, batch_rows in batch_groups:
                payload = _build_reviewer_payload(
                    sense_by_id=selected_by_id,
                    candidates_by_sense=candidates_by_sense,
                    contexts_by_sense=contexts_by_sense,
                    batch_rows=batch_rows,
                    reviewer_slot=reviewer_slot,
                    batch_id=batch_id,
                )
                batch_payloads.append((batch_id, payload))
                all_cases.extend(payload["cases"])
                write_json(staging / "review_batches" / batch_id / f"{reviewer_slot}_input.json", payload)
            full_source = [{"case_id": row["case_id"], "case_sha256": row["case_sha256"]} for row in all_cases]
            full_payload = {
                "schema_id": "D2LStageB50CandidateReviewerFullInputV1",
                "schema_version": "1.0.0",
                "policy_id": STAGE_B_POLICY_ID,
                "reviewer_slot": reviewer_slot,
                "case_count": len(all_cases),
                "sense_count": 50,
                "batch_count": 5,
                "batches": [batch_id for batch_id, _ in batch_payloads],
                "allowed_candidate_gold_labels": list(ALLOWED_LABELS),
                "independence_requirement": "DO_NOT_VIEW_OTHER_REVIEWER_OUTPUTS",
                "return_contract": "RETURN_THIS_JSON_WITH_ONLY_REVIEW_FIELDS_FILLED",
                "cases": all_cases,
                "source_input_sha256": sha256_bytes(canonical_json_bytes(full_source)),
                "provider_call_count": 0,
                "final_gold_label_count": 0,
                "final_glossary_decision": None,
            }
            full_payloads[reviewer_slot] = full_payload
            write_json(staging / f"{reviewer_slot}_full_input.json", full_payload)
            relative, zip_sha = _write_reviewer_handoff(staging, reviewer_slot, batch_payloads, full_payload)
            handoff_summary.append({"reviewer_slot": reviewer_slot, "case_count": 150, "zip_path": relative, "zip_sha256": zip_sha})
        shutil.rmtree(staging / ".handoff")
        write_json(
            staging / "batch_index.json",
            {
                "schema_id": "D2LStageB50BatchIndexV1",
                "schema_version": "1.0.0",
                "policy_id": STAGE_B_POLICY_ID,
                "batch_count": 5,
                "batches": [
                    {
                        "batch_id": batch_id,
                        "sense_count": len(rows),
                        "candidate_count": len(rows) * 3,
                        "sense_ids": [row["sense_id"] for row in rows],
                    }
                    for batch_id, rows in batch_groups
                ],
            },
        )
        write_jsonl(
            staging / "stage_b_gold_150_template.jsonl",
            [
                {
                    "candidate_id": row["candidate_instance_id"],
                    "sense_id": row["sense_id"],
                    "reviewer_1_label": None,
                    "reviewer_2_label": None,
                    "adjudication_label": None,
                    "final_gold_label": None,
                }
                for row in candidates
            ],
        )
        write_jsonl(
            staging / "stage_b_adjudication_150_template.jsonl",
            [
                {
                    "candidate_id": row["candidate_instance_id"],
                    "sense_id": row["sense_id"],
                    "disagreement": None,
                    "adjudicator_label": None,
                    "adjudication_reason": "",
                }
                for row in candidates
            ],
        )
        write_json(
            staging / "authority_binding.json",
            {
                "schema_id": "D2LTerminologyContractsAuthorityBindingV1",
                "contract_version": "1.1.0",
                "authority_tag": CONTRACT_TAG,
                "authority_commit": CONTRACT_COMMIT,
                "contract_manifest_sha256": CONTRACT_MANIFEST_SHA256,
                "authority_receipt_self_sha256": CONTRACT_RECEIPT_SELF_SHA256,
                "authority_receipt_physical_sha256": CONTRACT_RECEIPT_PHYSICAL_SHA256,
            },
        )
        write_json(
            staging / "selection_report.json",
            seal_integrity(
                {
                    "schema_id": "D2LFinal50SelectionReportV1",
                    "schema_version": "1.0.0",
                    "policy_id": FINAL_POLICY_ID,
                    "selected_count": 50,
                    "pool_count": 60,
                    "excluded_count": 10,
                    "lane_counts": dict(sorted(Counter(row["lane"] for row in senses).items())),
                    "stratum_counts": dict(sorted(Counter(row["stratum"] for row in senses).items())),
                    "excluded_sense_ids": [row["sense_id"] for row in excluded],
                    "excluded_source_terms": [row["source_term"] for row in excluded],
                    "leakage_repair_swaps": swaps,
                    "selection_method": "LOCKED_LANES_STRATA_EVIDENCE_SCORE_THEN_LEAKAGE_COMPONENT_CAP",
                    "stage_b_gold_used": False,
                    "provider_call_count": 0,
                    "final_glossary_decision": None,
                }
            ),
        )
        write_json(
            staging / "dataset_statistics.json",
            seal_integrity(
                {
                    "schema_id": "D2LFinal50DatasetStatisticsV1",
                    "schema_version": "1.0.0",
                    "policy_id": FINAL_POLICY_ID,
                    "sense_count": 50,
                    "candidate_count": 150,
                    "context_count": len(contexts),
                    "candidate_per_sense": dict(sorted(Counter(len(candidates_by_sense[sense["sense_id"]]) for sense in senses).items())),
                    "split_counts": dict(sorted(Counter(assignments.values()).items())),
                    "stratum_counts": dict(sorted(Counter(sense["stratum"] for sense in senses).items())),
                    "stage_b_review_cases_per_reviewer": 150,
                    "stage_b_gold_autofill_count": 0,
                    "provider_call_count": 0,
                    "label_distribution": "PENDING_STAGE_B_REVIEW",
                    "final_glossary_decision": None,
                }
            ),
        )
        write_json(
            staging / "lineage.json",
            seal_integrity(
                {
                    "schema_id": "D2LFinal50DatasetLineageV1",
                    "schema_version": "1.0.0",
                    "policy_id": FINAL_POLICY_ID,
                    "source_base_release_zip_sha256": sha256_file(base_release_zip),
                    "source_intake_release_zip_sha256": sha256_file(intake_release_zip),
                    "source_adjudication_release_zip_sha256": sha256_file(adjudication_release_zip),
                    "source_r0_result_release_zip_sha256": sha256_file(r0_result_release_zip),
                    "contract_authority": {
                        "tag": CONTRACT_TAG,
                        "commit": CONTRACT_COMMIT,
                        "manifest_sha256": CONTRACT_MANIFEST_SHA256,
                    },
                    "selection_manifest_sha256": dataset_manifest_sha256,
                    "provider_call_count": 0,
                    "stage_b_gold_autofill_count": 0,
                    "final_glossary_decision": None,
                }
            ),
        )
        write_json(
            staging / "environment.json",
            {
                "created_at": created_at,
                "network_calls": 0,
                "provider_calls": 0,
                "policy_id": FINAL_POLICY_ID,
                "contract_authority_tag": CONTRACT_TAG,
                "contract_authority_commit": CONTRACT_COMMIT,
            },
        )
        (staging / "RELEASE_REPORT.md").write_text(
            "# D2L Fast-Track Dataset 50 / 150 Stage B handoff\n\n"
            "Status: `READY_FOR_STAGE_B_DUAL_REVIEW`\n\n"
            "This release freezes 50 Stage A-ready senses and 150 candidate cases before "
            "any Stage B result is read. It contains two independent reviewer inputs. "
            "Reviewer outputs, gold labels, C/E evidence, and final glossary decisions are "
            "not included and must remain null until the review and adjudication stages.\n\n"
            "Counts: 50 senses, 150 candidates, 50 EffectiveSenseContractV1, 150 "
            "FrozenCandidateContractV1, 150 ConstraintEvidencePackageV1, five batches, "
            "30/10/10 leakage-safe split, zero provider calls.\n",
            encoding="utf-8",
            newline="\n",
        )
        (staging / "commands.txt").write_text(
            "python -B tools/build_final50_stage_b.py --output-root <OUTPUT_ROOT>\n"
            "python -B tools/validate_final50_stage_b.py --artifact-root <OUTPUT_ROOT> --contracts-root <REPO>/terminology_contracts_v1\n"
            "python -m unittest discover -s tests -p test_final50_stage_b.py\n",
            encoding="utf-8",
            newline="\n",
        )
        _write_source_bundle(staging)
        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LFinal50StageBReviewManifestV1",
            "schema_version": "1.0.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": FINAL_POLICY_ID,
            "stage_b_policy_id": STAGE_B_POLICY_ID,
            "status": STATUS,
            "created_at": created_at,
            "counts": {
                "term_sense": 50,
                "candidate": 150,
                "effective_sense_contract": 50,
                "frozen_candidate_contract": 150,
                "constraint_evidence_package": 150,
                "context": len(contexts),
                "reviewer_case_per_reviewer": 150,
                "reviewer_count": 2,
                "batch": 5,
                "stage_b_gold_autofill": 0,
            },
            "split_counts": dict(sorted(Counter(assignments.values()).items())),
            "contract_authority": {
                "tag": CONTRACT_TAG,
                "commit": CONTRACT_COMMIT,
                "manifest_sha256": CONTRACT_MANIFEST_SHA256,
            },
            "selection_manifest_sha256": dataset_manifest_sha256,
            "provider_call_count": 0,
            "final_gold_label_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        try:
            from .validate_final50_stage_b import validate_artifact
        except ImportError:  # pragma: no cover
            from validate_final50_stage_b import validate_artifact  # type: ignore
        errors = validate_artifact(staging, contracts_root=repo_root / "terminology_contracts_v1")
        if errors:
            raise ValueError("internal final50 validation failed: " + "; ".join(errors))
        zip_name = f"{ARTIFACT_NAME}_reviewer_handoff.zip"
        temporary_zip = temporary / zip_name
        build_deterministic_zip(staging, temporary_zip)
        replace_directory(staging, output_root)
        final_zip = output_root.parent / zip_name
        os.replace(temporary_zip, final_zip)
        zip_sha = sha256_file(final_zip)
        (output_root.parent / f"{zip_name}.sha256").write_text(
            f"{zip_sha} *{zip_name}\n", encoding="ascii", newline="\n"
        )
        return {
            "status": STATUS,
            "artifact_root": str(output_root),
            "manifest_sha256": manifest["manifest_sha256"],
            "reviewer_handoff_zip": str(final_zip),
            "reviewer_handoff_zip_sha256": zip_sha,
            "counts": manifest["counts"],
            "split_counts": manifest["split_counts"],
            "reviewer_handoffs": handoff_summary,
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    namespace = Path(__file__).resolve().parents[1]
    release = namespace / "release"
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument(
        "--base-release-zip",
        type=Path,
        default=release / "d2l_dataset_50_senses_fast_track_stage_a_v1_release.zip",
    )
    parser.add_argument(
        "--intake-release-zip",
        type=Path,
        default=release / "d2l_fast_track_stage_a_review_intake_v1_release.zip",
    )
    parser.add_argument(
        "--adjudication-release-zip",
        type=Path,
        default=release / "d2l_fast_track_stage_a_adjudication_result_v1_release.zip",
    )
    parser.add_argument(
        "--r0-result-release-zip",
        type=Path,
        default=release / "d2l_fast_track_stage_a_r0_reaudit_result_v1_release.zip",
    )
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--created-at", default="2026-07-29T17:00:00Z")
    args = parser.parse_args()
    result = build_final50_stage_b(
        repo_root=args.repo_root,
        base_release_zip=args.base_release_zip,
        intake_release_zip=args.intake_release_zip,
        adjudication_release_zip=args.adjudication_release_zip,
        r0_result_release_zip=args.r0_result_release_zip,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
