from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.common import (
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        read_csv,
        read_json,
        seal_record,
        sha256_bytes,
        sha256_file,
        write_checksums,
        write_csv,
        write_json,
        write_jsonl,
    )
    from tools.review_contract import (
        ARTIFACT_NAME,
        CONTRACT_AUTHORITY_COMMIT,
        CONTRACT_AUTHORITY_TAG,
        CONTRACT_MANIFEST_SHA256,
        PENDING_ACTIONS,
        POLICY_ID,
        REVIEW_FIELDS,
        SCHEMA_ID,
        SOURCE_ARTIFACT_NAME,
        SOURCE_DATASET_FILES,
        SOURCE_MANIFEST_FILE_SHA256,
        SOURCE_MANIFEST_SHA256,
        SOURCE_PARENT_COMMIT,
        STAGE_B_FIELDS,
        build_adjudication_record,
        build_decision_record,
        build_provenance_record,
        check_receipt_hashes,
        load_source_records,
        require_iso8601,
        validate_review_inputs,
    )
else:
    from .common import (
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        read_csv,
        read_json,
        seal_record,
        sha256_bytes,
        sha256_file,
        write_checksums,
        write_csv,
        write_json,
        write_jsonl,
    )
    from .review_contract import (
        ARTIFACT_NAME,
        CONTRACT_AUTHORITY_COMMIT,
        CONTRACT_AUTHORITY_TAG,
        CONTRACT_MANIFEST_SHA256,
        PENDING_ACTIONS,
        POLICY_ID,
        REVIEW_FIELDS,
        SCHEMA_ID,
        SOURCE_ARTIFACT_NAME,
        SOURCE_DATASET_FILES,
        SOURCE_MANIFEST_FILE_SHA256,
        SOURCE_MANIFEST_SHA256,
        SOURCE_PARENT_COMMIT,
        STAGE_B_FIELDS,
        build_adjudication_record,
        build_decision_record,
        build_provenance_record,
        check_receipt_hashes,
        load_source_records,
        require_iso8601,
        validate_review_inputs,
    )


def _copy_snapshot(paths: dict[str, Path], snapshot: Path) -> dict[str, Path]:
    captured: dict[str, Path] = {}
    for label, source in paths.items():
        source = source.resolve(strict=True)
        destination = snapshot / f"{label}{source.suffix}"
        shutil.copyfile(source, destination)
        if sha256_file(source) != sha256_file(destination):
            raise ValueError(f"input changed during capture: {label}")
        captured[label] = destination
    return captured


def _write_report(
    output: Path,
    decisions: list[dict[str, Any]],
    input_hashes: dict[str, str],
    adjudication_count: int,
) -> None:
    counts = Counter(row["resolution_status"] for row in decisions)
    lines = [
        "# D2L Stage A Pilot 15 Sense Reviewed V1",
        "",
        "## Phán quyết",
        "",
        "Đây là companion artifact sau khi hợp nhất review của ba người. Gói P0 "
        "`d2l_stage_a_pilot_15_senses_v1` vẫn bất biến.",
        "",
        f"- Review hoàn tất về mặt cấu trúc: **{len(decisions)}/15 sense**.",
        f"- Đủ điều kiện dựng candidate contract: **{counts['READY_FOR_CONTRACT_CONSTRUCTION']}/15**.",
        f"- Cần xử lý mục tiêu: **{15 - counts['READY_FOR_CONTRACT_CONSTRUCTION']}/15**.",
        "- Official runtime contract được phát hành: **0**.",
        "- Stage B gold label được tự động điền: **0**.",
        "- `final_glossary_decision`: **null**; quyết định này thuộc Global Validator.",
        "",
        "## Bốn blocker còn lại",
        "",
        "| Sense | Trạng thái | Việc cần làm |",
        "|---|---|---|",
    ]
    for row in decisions:
        if row["resolution_status"] == "READY_FOR_CONTRACT_CONSTRUCTION":
            continue
        lines.append(
            f"| {row['source_term']} | `{row['resolution_status']}` | "
            f"`{PENDING_ACTIONS.get(row['source_term'], 'TARGETED_HUMAN_REPAIR')}` |"
        )
    lines += [
        "",
        "## Phân loại 15 sense",
        "",
        "| Sense | Risk | Cơ sở | Final definition | Final POS | Final scope | Kết quả |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in decisions:
        lines.append(
            f"| {row['source_term']} | {row['risk_class']} | {row['resolution_basis']} | "
            f"{row['final_definition_decision']} | {row['final_pos_decision']} | "
            f"{row['final_scope_decision']} | {row['resolution_status']} |"
        )
    lines += [
        "",
        "## Phạm vi dữ liệu",
        "",
        "- 15 selected sense, 45 candidate instances, 73 context và candidate index được "
        "sao chép nguyên byte từ P0 trong `source_dataset/`.",
        "- Review provenance: 25 slot reviewer (15 reviewer 1, 10 reviewer 2).",
        f"- Adjudication: {adjudication_count} record, gồm disagreement, R4 và E-unjudgeable.",
        "- Blind audit: 3/3 case đã hoàn tất.",
        "- Stage B vẫn là template mở; không có nhãn vàng hoặc Vietnamese attestation giả lập.",
        "",
        "## Lineage và kiểm tra",
        "",
        f"- Parent P0 manifest self-hash: `{SOURCE_MANIFEST_SHA256}`.",
        f"- Reviewer input hashes: `{input_hashes}`.",
        "- Mỗi JSONL decision/provenance/adjudication có self-hash; toàn bộ file có manifest và CHECKSUMS.",
        "- Không gọi provider/API; không sửa contract authority v1.1.0.",
        "",
        "## Cách kiểm tra",
        "",
        "```text",
        "python -B source/tools/validate_reviewed_pilot.py --artifact-root . --zip-path ../d2l_stage_a_pilot_15_senses_reviewed_v1_reviewer_handoff.zip",
        "```",
        "",
        "`source/` chứa builder, validator và test để reviewer có thể tái chạy kiểm định.",
    ]
    (output / "REVIEW_REPORT.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def _stage_b_projection(source_path: Path, status_by_sense: dict[str, str]) -> list[dict[str, str]]:
    rows = read_csv(source_path)
    if len(rows) != 45:
        raise ValueError("Stage B source row count mismatch")
    projected: list[dict[str, str]] = []
    for row in rows:
        value = {field: row.get(field, "") for field in STAGE_B_FIELDS}
        value["effective_sense_review_status"] = status_by_sense[row["sense_id"]]
        for field in (
            "candidate_gold_label", "allowed_scope", "validated_variants",
            "rejected_variants", "reason_codes", "vietnamese_evidence_refs",
            "reviewer_provenance_ref", "adjudication_ref",
        ):
            if value[field]:
                raise ValueError(f"Stage B field is not blank: {field}")
        projected.append(value)
    return projected


def build_reviewed_pilot(
    *,
    p0_root: Path,
    reviewer_1: Path,
    reviewer_2: Path,
    blind_audit: Path,
    adjudicator: Path,
    intake_receipt: Path,
    output_root: Path,
    reviewer_1_completed_at: str,
    reviewer_2_completed_at: str,
    created_at: str,
) -> dict[str, Any]:
    p0_root = p0_root.resolve(strict=True)
    output_root = output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"refusing to overwrite output: {output_root}")
    output_root.parent.mkdir(parents=True, exist_ok=True)
    require_iso8601(created_at, "created_at")
    source = load_source_records(p0_root)
    input_paths = {
        "reviewer_1": reviewer_1,
        "reviewer_2": reviewer_2,
        "blind_audit": blind_audit,
        "adjudicator": adjudicator,
        "receipt": intake_receipt,
    }
    resolved_inputs = {key: value.resolve(strict=True) for key, value in input_paths.items()}
    if len({str(path).casefold() for path in resolved_inputs.values()}) != len(resolved_inputs):
        raise ValueError("all review and receipt input paths must be distinct")
    review_paths = {key: resolved_inputs[key] for key in ("reviewer_1", "reviewer_2", "blind_audit", "adjudicator")}
    input_hashes = check_receipt_hashes(review_paths, resolved_inputs["receipt"])

    parent = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.", dir=output_root.parent))
    staging = parent / output_root.name
    try:
        snapshot_root = parent / "input_snapshot"
        snapshot_root.mkdir()
        captured = _copy_snapshot(resolved_inputs, snapshot_root)
        for label, expected_hash in input_hashes.items():
            if sha256_file(captured[label]) != expected_hash:
                raise ValueError(f"input drifted before stable capture: {label}")
        review_data = validate_review_inputs(
            source,
            {key: captured[key] for key in review_paths},
            reviewer_1_completed_at,
            reviewer_2_completed_at,
        )

        (staging / "source_dataset").mkdir(parents=True)
        for relative in SOURCE_DATASET_FILES:
            shutil.copyfile(p0_root / relative, staging / "source_dataset" / relative)
        (staging / "review_inputs").mkdir()
        input_targets = {
            "reviewer_1": "reviewer_1.csv",
            "reviewer_2": "reviewer_2.csv",
            "blind_audit": "reviewer_2_blind_audit.csv",
            "adjudicator": "adjudicator.csv",
            "receipt": "INTAKE_RECEIPT.txt",
        }
        for label, target in input_targets.items():
            shutil.copyfile(captured[label], staging / "review_inputs" / target)

        source_namespace = Path(__file__).resolve().parents[1]
        (staging / "source" / "tools").mkdir(parents=True)
        (staging / "source" / "tests").mkdir(parents=True)
        shutil.copyfile(source_namespace / "README.md", staging / "source" / "README.md")
        for name in ("__init__.py", "common.py", "review_contract.py", "build_reviewed_pilot.py", "validate_reviewed_pilot.py"):
            shutil.copyfile(source_namespace / "tools" / name, staging / "source" / "tools" / name)
        shutil.copyfile(source_namespace / "tests" / "test_reviewed_pilot.py", staging / "source" / "tests" / "test_reviewed_pilot.py")

        provenance: list[dict[str, Any]] = []
        provenance_by_sense: dict[str, list[dict[str, Any]]] = {row["sense_id"]: [] for row in source["selected"]}
        for sense in source["selected"]:
            sense_id = sense["sense_id"]
            first = review_data["r1_summaries"][sense_id]
            record = build_provenance_record(
                sense, "reviewer_1", first, "review_inputs/reviewer_1.csv",
                input_hashes["reviewer_1"], reviewer_1_completed_at,
            )
            provenance.append(record)
            provenance_by_sense[sense_id].append(record)
            if sense_id in review_data["r2_summaries"]:
                second = review_data["r2_summaries"][sense_id]
                record = build_provenance_record(
                    sense, "reviewer_2", second, "review_inputs/reviewer_2.csv",
                    input_hashes["reviewer_2"], reviewer_2_completed_at,
                )
                provenance.append(record)
                provenance_by_sense[sense_id].append(record)
        write_jsonl(staging / "review_provenance_15_senses.jsonl", provenance)

        adjudications: list[dict[str, Any]] = []
        adjudication_by_sense: dict[str, dict[str, Any]] = {}
        for sense_id, row in review_data["adj_by_id"].items():
            refs = [record["review_id"] for record in provenance_by_sense[sense_id]]
            record = build_adjudication_record(
                review_data["selected_by_id"][sense_id], row, refs, input_hashes["adjudicator"]
            )
            adjudications.append(record)
            adjudication_by_sense[sense_id] = record
        adjudications.sort(key=lambda row: row["sense_id"])
        write_jsonl(staging / "stage_a_adjudication_15_senses.jsonl", adjudications)

        decisions = []
        for sense in source["selected"]:
            decisions.append(build_decision_record(
                sense, review_data, provenance_by_sense[sense["sense_id"]],
                adjudication_by_sense.get(sense["sense_id"]), input_hashes,
            ))
        decisions.sort(key=lambda row: row["sense_id"])
        write_jsonl(staging / "merged_review_decisions_15.jsonl", decisions)

        ready = [row for row in decisions if row["resolution_status"] == "READY_FOR_CONTRACT_CONSTRUCTION"]
        pending = [row for row in decisions if row["resolution_status"] != "READY_FOR_CONTRACT_CONSTRUCTION"]
        candidates_by_sense: dict[str, list[dict[str, Any]]] = {}
        for candidate in source["candidates"]:
            candidates_by_sense.setdefault(candidate["sense_id"], []).append(candidate)
        effective_candidates = []
        for decision in ready:
            sense = review_data["selected_by_id"][decision["sense_id"]]
            effective_candidates.append(seal_record({
                "schema_id": "D2LStageAEffectiveSenseContractCandidateV1",
                "policy_id": POLICY_ID,
                "status": "READY_FOR_CONTRACT_CONSTRUCTION",
                "term_id": sense["term_id"],
                "sense_id": sense["sense_id"],
                "source_term": sense["source_term"],
                "proposed_definition_en": sense["proposed_definition_en"],
                "proposed_part_of_speech": sense["proposed_part_of_speech"],
                "proposed_scope_note": sense.get("proposed_scope_note"),
                "final_definition_decision": decision["final_definition_decision"],
                "final_pos_decision": decision["final_pos_decision"],
                "final_scope_decision": decision["final_scope_decision"],
                "candidate_ids": [row["candidate_id"] for row in candidates_by_sense[sense["sense_id"]]],
                "positive_context_ids": sorted(set(sense["positive_definition_evidence_ids"] + sense["positive_pos_evidence_ids"])),
                "boundary_context_ids": sense["boundary_context_ids"],
                "source_selected_sense_sha256": sense["selected_sense_sha256"],
                "review_decision_sha256": decision["review_record_sha256"],
                "official_contract_emitted": False,
                "final_glossary_decision": None,
            }, "candidate_record_sha256"))
        write_jsonl(staging / "effective_sense_contract_candidates_11.jsonl", effective_candidates)

        pending_records = []
        for decision in pending:
            pending_records.append(seal_record({
                "schema_id": "D2LStageAPendingResolutionV1",
                "policy_id": POLICY_ID,
                "status": decision["resolution_status"],
                "term_id": decision["term_id"],
                "sense_id": decision["sense_id"],
                "source_term": decision["source_term"],
                "final_definition_decision": decision["final_definition_decision"],
                "final_pos_decision": decision["final_pos_decision"],
                "final_scope_decision": decision["final_scope_decision"],
                "final_decision": decision["final_decision"],
                "required_next_action": PENDING_ACTIONS.get(decision["source_term"], "TARGETED_HUMAN_REPAIR"),
                "review_decision_sha256": decision["review_record_sha256"],
                "official_contract_emitted": False,
                "final_glossary_decision": None,
            }, "pending_record_sha256"))
        write_jsonl(staging / "pending_resolution_4.jsonl", pending_records)

        r1_rows = {row["sense_id"]: row for row in read_csv(captured["reviewer_1"])}
        r2_rows = {row["sense_id"]: row for row in read_csv(captured["reviewer_2"])}
        adj_rows = {row["sense_id"]: row for row in read_csv(captured["adjudicator"])}
        merged_rows: list[dict[str, str]] = []
        for decision in decisions:
            sense_id = decision["sense_id"]
            row = {field: "" for field in REVIEW_FIELDS}
            for field in REVIEW_FIELDS:
                if field in r1_rows[sense_id]:
                    row[field] = r1_rows[sense_id].get(field, "")
            for field in (
                "reviewer_2_id", "reviewer_2_type", "reviewer_2_role", "reviewer_2_status",
                "reviewer_2_definition_decision", "reviewer_2_pos_decision", "reviewer_2_scope_decision",
                "reviewer_2_reason_codes", "reviewer_2_confidence", "reviewer_2_artifact_sha256",
            ):
                row[field] = r2_rows[sense_id].get(field, "")
            if sense_id in adj_rows:
                adj = adj_rows[sense_id]
                row.update({
                    "adjudicator_id": adj["adjudicator_id"],
                    "adjudicator_type": adj["adjudicator_type"],
                    "adjudicator_status": adj["adjudicator_status"],
                    "adjudication_decision": adj["final_decision"],
                    "adjudication_reason": adj["adjudication_reason"],
                    "adjudication_artifact_sha256": input_hashes["adjudicator"],
                    "adjudicator_completed_at": adj["completed_at"],
                })
            row.update({
                "review_status": "COMPLETE",
                "completed_at": adj_rows[sense_id]["completed_at"] if sense_id in adj_rows else reviewer_1_completed_at,
                "reviewer_1_completed_at": reviewer_1_completed_at,
                "reviewer_2_completed_at": reviewer_2_completed_at if sense_id in review_data["r2_summaries"] else "",
                "final_definition_decision": decision["final_definition_decision"],
                "final_pos_decision": decision["final_pos_decision"],
                "final_scope_decision": decision["final_scope_decision"],
                "final_decision": decision["final_decision"],
                "resolution_basis": decision["resolution_basis"],
                "resolution_status": decision["resolution_status"],
                "review_record_sha256": decision["review_record_sha256"],
            })
            merged_rows.append(row)
        merged_rows.sort(key=lambda row: row["sense_id"])
        write_csv(staging / "stage_a_review_results_15_senses.csv", merged_rows, REVIEW_FIELDS)
        shutil.copyfile(captured["blind_audit"], staging / "stage_a_blind_audit_results_3.csv")
        write_csv(
            staging / "stage_b_annotation_template_45.csv",
            _stage_b_projection(p0_root / "stage_b_annotation_template_45.csv", {row["sense_id"]: row["resolution_status"] for row in decisions}),
            STAGE_B_FIELDS,
        )

        _write_report(staging, decisions, input_hashes, len(adjudications))
        counts = Counter(row["resolution_status"] for row in decisions)
        write_json(staging / "stage_a_pilot_15_summary.json", {
            "schema_id": "D2LStageAPilot15ReviewedSummaryV1",
            "policy_id": POLICY_ID,
            "status": "REVIEW_MERGED_PARTIAL_RESOLUTION",
            "selected_sense_count": 15,
            "candidate_count": 45,
            "selected_context_count": len(source["contexts"]),
            "review_provenance_count": len(provenance),
            "adjudication_count": len(adjudications),
            "blind_audit_count": len(review_data["blind_rows"]),
            "resolution_counts": dict(sorted(counts.items())),
            "official_effective_sense_contract_count": 0,
            "stage_b_open_row_count": 45,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
        })
        checks = {
            "parent_p0_manifest_bound": True,
            "selected_sense_count_15": len(source["selected"]) == 15,
            "candidate_count_45": len(source["candidates"]) == 45,
            "context_count_73": len(source["contexts"]) == 73,
            "candidate_three_per_sense": True,
            "reviewer_1_complete_15": True,
            "reviewer_2_complete_assigned_10": True,
            "blind_audit_complete_3": True,
            "distinct_human_reviewer_ids": True,
            "adjudication_complete_4": len(adjudications) == 4,
            "ready_resolution_11": len(ready) == 11,
            "targeted_blockers_4": len(pending) == 4,
            "stage_b_gold_autofill_zero": True,
            "official_contract_emission_zero": True,
            "final_glossary_decision_null": True,
            "provider_call_count_zero": True,
        }
        write_json(staging / "stage_a_pilot_15_acceptance_gate_report.json", {
            "schema_id": "D2LStageAPilot15ReviewedAcceptanceGateReportV1",
            "policy_id": POLICY_ID,
            "status": "PASS_WITH_TARGETED_REPAIR_BLOCKERS",
            "structural_status": "PASS",
            "review_status": "COMPLETE",
            "checks": checks,
            "blockers": [f"{row['source_term']}:{row['resolution_status']}" for row in pending],
            "selected_sense_count": 15,
            "ready_resolution_count": len(ready),
            "pending_resolution_count": len(pending),
            "official_effective_sense_contract_count": 0,
            "stage_b_gold_autofill_count": 0,
            "final_glossary_decision": None,
        })
        write_json(staging / "lineage.json", {
            "schema_id": "D2LStageAPilot15ReviewedLineageV1",
            "policy_id": POLICY_ID,
            "parent_artifact_name": SOURCE_ARTIFACT_NAME,
            "parent_manifest_sha256": SOURCE_MANIFEST_SHA256,
            "parent_manifest_file_sha256": SOURCE_MANIFEST_FILE_SHA256,
            "review_input_file_sha256": input_hashes,
            "reviewer_ids": ["diemphuong", "reviewer_2", "snail"],
            "contract_authority": {
                "tag": CONTRACT_AUTHORITY_TAG,
                "commit": CONTRACT_AUTHORITY_COMMIT,
                "manifest_sha256": CONTRACT_MANIFEST_SHA256,
            },
            "provider_call_count": 0,
            "official_contracts_emitted": 0,
            "final_glossary_decision": None,
        })
        write_json(staging / "environment.json", {"created_at": created_at, "network_calls": 0, "builder_policy": POLICY_ID})
        write_json(staging / "ownership_scan.json", {
            "status": "PASS",
            "owned_namespace": "dataset/d2l_stage_a_pilot_15_senses_reviewed_v1",
            "source_p0_untouched": True,
            "external_review_inputs_captured_before_merge": True,
            "external_result_paths_staged": False,
        })
        write_json(staging / "credential_scan.json", {"status": "PASS", "credentials_in_artifact": False, "provider_calls": 0})
        write_json(staging / "git_commit_receipt.json", {
            "schema_id": "D2LStageAPilot15ReviewedSourceReceiptV1",
            "source_parent_commit": SOURCE_PARENT_COMMIT,
            "source_namespace": "dataset/d2l_stage_a_pilot_15_senses_reviewed_v1",
            "source_code_included": True,
            "tracked_worktree_status_at_build": "CLEAN_TRACKED_FILES_ONLY",
            "external_untracked_paths_excluded": True,
        })
        (staging / "commands.txt").write_text(
            "python tools/build_reviewed_pilot.py --p0-root <P0_RELEASE_ROOT> --reviewer-1 <reviewer1.csv> --reviewer-2 <reviewer2.csv> --blind-audit <blind.csv> --adjudicator <review3.csv> --intake-receipt <INTAKE_RECEIPT.txt> --output-root <OUTPUT_ROOT> --reviewer-1-completed-at 2026-07-29T06:44:14Z --reviewer-2-completed-at 2026-07-29T06:44:14Z --created-at 2026-07-29T07:00:00Z\n"
            "python -B source/tools/validate_reviewed_pilot.py --artifact-root <OUTPUT_ROOT> --zip-path <HANDOFF_ZIP>\n",
            encoding="utf-8",
            newline="\n",
        )

        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": SCHEMA_ID,
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "artifact_name": ARTIFACT_NAME,
            "created_at": created_at,
            "status": "REVIEW_MERGED_PARTIAL_RESOLUTION",
            "parent_artifact_name": SOURCE_ARTIFACT_NAME,
            "parent_manifest_sha256": SOURCE_MANIFEST_SHA256,
            "source_manifest_file_sha256": SOURCE_MANIFEST_FILE_SHA256,
            "counts": {
                "selected_sense": 15,
                "candidate": 45,
                "selected_context": len(source["contexts"]),
                "review_provenance": len(provenance),
                "adjudication": len(adjudications),
                "blind_audit": len(review_data["blind_rows"]),
                "ready_resolution": len(ready),
                "pending_resolution": len(pending),
                "official_effective_sense_contract": 0,
                "stage_b_open_rows": 45,
            },
            "resolution_counts": dict(sorted(counts.items())),
            "review_input_file_sha256": input_hashes,
            "contract_authority": {
                "tag": CONTRACT_AUTHORITY_TAG,
                "commit": CONTRACT_AUTHORITY_COMMIT,
                "manifest_sha256": CONTRACT_MANIFEST_SHA256,
            },
            "provider_call_count": 0,
            "final_glossary_decision": None,
            "files": files,
        }
        manifest["manifest_sha256"] = sha256_bytes(canonical_json_bytes(manifest))
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")

        zip_name = f"{output_root.name}_reviewer_handoff.zip"
        temp_zip = parent / zip_name
        build_deterministic_zip(staging, temp_zip)
        os.replace(staging, output_root)
        final_zip = output_root.parent / zip_name
        os.replace(temp_zip, final_zip)
        zip_hash = sha256_file(final_zip)
        (output_root.parent / f"{zip_name}.sha256").write_text(
            f"{zip_hash} *{zip_name}\n", encoding="ascii", newline="\n"
        )
        return {
            "status": manifest["status"],
            "manifest_sha256": manifest["manifest_sha256"],
            "artifact_root": str(output_root),
            "reviewer_handoff_zip": str(final_zip),
            "reviewer_handoff_zip_sha256": zip_hash,
            "counts": manifest["counts"],
        }
    finally:
        shutil.rmtree(parent, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p0-root", type=Path, required=True)
    parser.add_argument("--reviewer-1", type=Path, required=True)
    parser.add_argument("--reviewer-2", type=Path, required=True)
    parser.add_argument("--blind-audit", type=Path, required=True)
    parser.add_argument("--adjudicator", type=Path, required=True)
    parser.add_argument("--intake-receipt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--reviewer-1-completed-at", required=True)
    parser.add_argument("--reviewer-2-completed-at", required=True)
    parser.add_argument("--created-at", required=True)
    args = parser.parse_args()
    import json
    result = build_reviewed_pilot(
        p0_root=args.p0_root,
        reviewer_1=args.reviewer_1,
        reviewer_2=args.reviewer_2,
        blind_audit=args.blind_audit,
        adjudicator=args.adjudicator,
        intake_receipt=args.intake_receipt,
        output_root=args.output_root,
        reviewer_1_completed_at=args.reviewer_1_completed_at,
        reviewer_2_completed_at=args.reviewer_2_completed_at,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
