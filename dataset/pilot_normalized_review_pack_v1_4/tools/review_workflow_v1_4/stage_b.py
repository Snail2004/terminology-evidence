from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .common import (
    POLICY_ID,
    SCHEMA_VERSION,
    agreement_summary,
    conditional_resolution,
    file_bindings,
    pilot_records,
    read_csv,
    read_json,
    read_jsonl,
    seal,
    sha256_file,
    sha256_object,
    source_payload_hash,
    validate_manifest,
    validate_pilot,
    validate_self_hash,
    write_csv,
    write_json,
    write_text,
)


TABLES = {
    "contrastive": (
        "pilot_contrastive_review.csv",
        "context_id",
        "CONTEXT",
    ),
    "context": ("pilot_context_review.csv", "context_id", "CONTEXT"),
    "candidate": (
        "pilot_candidate_annotation.csv",
        "candidate_instance_id",
        "CANDIDATE",
    ),
}
SIGNATURES = {
    "contrastive": ["contrastive_label", "use_in_sense_boundary_test"],
    "context": ["same_sense_label", "context_type", "context_validity"],
    "candidate": [
        "applicability",
        "semantic_fit_label",
        "candidate_rank",
        "candidate_decision",
        "candidate_relation",
        "relation_to_candidate_instance_id",
    ],
}
OPTIONAL_SIGNATURES = {
    "contrastive": set(),
    "context": {"context_type"},
    "candidate": {"candidate_rank", "relation_to_candidate_instance_id"},
}


def generate_stage_b(
    pilot_root: Path,
    sense_contract_root: Path,
    output_root: Path,
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"Output already exists: {output_root}")
    pilot_manifest, pilot_errors = validate_pilot(pilot_root)
    if pilot_errors:
        raise ValueError(f"Pilot validation failed: {pilot_errors}")
    contract_manifest, contract_errors = validate_manifest(
        sense_contract_root,
        expected_schema="D2LReviewedSenseContractV1",
    )
    if contract_errors:
        raise ValueError(f"Sense contract validation failed: {contract_errors}")
    effective = _effective_contract_records(sense_contract_root)
    pilot = pilot_records(pilot_root)
    if set(effective) != set(pilot["TERM_SENSE"]):
        raise ValueError("Effective sense contract does not cover the pilot")

    output_root.mkdir(parents=True)
    rows_by_table = {
        "contrastive": _contrastive_rows(pilot, effective),
        "context": _context_rows(pilot, effective),
        "candidate": _candidate_rows(pilot, effective),
    }
    source_bindings = {
        "schema_id": "D2LCSTStageBSourceBindingsV1_4",
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "source_pilot_manifest_sha256": pilot_manifest["manifest_sha256"],
        "sense_contract_manifest_sha256": contract_manifest["manifest_sha256"],
        "tables": {},
    }
    table_specs = {}
    for table, rows in rows_by_table.items():
        filename, unit_field, record_kind = TABLES[table]
        source_fields = [
            key
            for key in rows[0]
            if not key.startswith(("reviewer_", "adjudicat"))
            and key != "source_payload_sha256"
        ]
        bindings = {}
        for row in rows:
            payload_hash = source_payload_hash(row, source_fields)
            row["source_payload_sha256"] = payload_hash
            unit = row[unit_field]
            bindings[unit] = {
                "source_payload_sha256": payload_hash,
                "source_record_sha256": row["source_record_sha256"],
                "reviewed_sense_contract_sha256": row[
                    "reviewed_sense_contract_sha256"
                ],
            }
        # Keep source hash before human fields in the CSV.
        reordered = []
        for row in rows:
            source = {key: row[key] for key in source_fields}
            human = {
                key: value
                for key, value in row.items()
                if key.startswith(("reviewer_", "adjudicat"))
            }
            reordered.append(
                {
                    **source,
                    "source_payload_sha256": row["source_payload_sha256"],
                    **human,
                }
            )
        rows_by_table[table] = reordered
        write_csv(output_root / filename, list(reordered[0]), reordered)
        table_specs[table] = {
            "filename": filename,
            "unit_field": unit_field,
            "source_record_kind": record_kind,
            "source_fields": source_fields,
            "signature_fields": SIGNATURES[table],
            "optional_signature_fields": sorted(OPTIONAL_SIGNATURES[table]),
        }
        source_bindings["tables"][table] = {
            "unit_field": unit_field,
            "rows": bindings,
        }
    source_bindings["source_bindings_sha256"] = sha256_object(source_bindings)
    write_json(output_root / "source_bindings.json", source_bindings)
    stage_contract = {
        "schema_id": "D2LCSTStageBAnnotationContractV1_4",
        "schema_version": SCHEMA_VERSION,
        "policy_id": POLICY_ID,
        "adjudication_policy": "MAJORITY_2_OF_3_ELSE_ADJUDICATION",
        "group_ranking_policy": "RANK_INDEPENDENT_NON_REJECTED_ONLY",
        "tables": table_specs,
        "label_sets": _label_sets(),
        "source_pilot_manifest_sha256": pilot_manifest["manifest_sha256"],
        "sense_contract_manifest_sha256": contract_manifest["manifest_sha256"],
    }
    stage_contract["contract_sha256"] = sha256_object(stage_contract)
    write_json(output_root / "stage_b_contract.json", stage_contract)
    write_text(
        output_root / "README.md",
        "# D2L CST Stage B annotation pack v1\n\n"
        "These tables were generated only after the effective definition/POS "
        "contract was frozen. Variant and duplicate candidates are not ranked; "
        "they point to a canonical independent candidate.\n",
    )
    mutable = {value[0] for value in TABLES.values()}
    manifest = {
        "schema_id": "D2LCSTStageBAnnotationPackV1",
        "schema_version": "1.0.0",
        "policy_id": POLICY_ID,
        "status": "HUMAN_ANNOTATION_PENDING",
        "source_pilot": {
            "manifest_sha256": pilot_manifest["manifest_sha256"],
            "manifest_file_sha256": sha256_file(pilot_root / "manifest.json"),
        },
        "source_sense_contract": {
            "manifest_sha256": contract_manifest["manifest_sha256"],
            "manifest_file_sha256": sha256_file(
                sense_contract_root / "manifest.json"
            ),
        },
        "row_counts": {table: len(rows) for table, rows in rows_by_table.items()},
        "adjudication_policy": "MAJORITY_2_OF_3_ELSE_ADJUDICATION",
        "group_ranking_policy": "RANK_INDEPENDENT_NON_REJECTED_ONLY",
        "human_review_complete": False,
    }
    manifest["files"] = file_bindings(output_root, mutable=mutable)
    manifest = seal(manifest, "manifest_sha256")
    write_json(output_root / "manifest.json", manifest)
    validation = validate_stage_b(
        output_root,
        pilot_root,
        sense_contract_root,
    )
    if validation["status"] != "PASS":
        raise ValueError(f"Stage B template validation failed: {validation}")
    write_json(output_root / "template_validation_report.json", validation)
    manifest["files"] = file_bindings(output_root, mutable=mutable)
    manifest = seal(manifest, "manifest_sha256")
    write_json(output_root / "manifest.json", manifest)
    return {
        "root": output_root.as_posix(),
        "manifest_sha256": manifest["manifest_sha256"],
        "manifest_file_sha256": sha256_file(output_root / "manifest.json"),
        "row_counts": manifest["row_counts"],
    }


def validate_stage_b(
    stage_b_root: Path,
    pilot_root: Path,
    sense_contract_root: Path,
    *,
    require_complete: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    manifest, manifest_errors = validate_manifest(
        stage_b_root,
        expected_schema="D2LCSTStageBAnnotationPackV1",
        mutable_files_may_differ=True,
    )
    errors.extend(manifest_errors)
    pilot_manifest, pilot_errors = validate_pilot(pilot_root)
    errors.extend(pilot_errors)
    contract_manifest, contract_errors = validate_manifest(
        sense_contract_root,
        expected_schema="D2LReviewedSenseContractV1",
    )
    errors.extend(contract_errors)
    if manifest.get("source_pilot", {}).get("manifest_sha256") != pilot_manifest.get(
        "manifest_sha256"
    ):
        errors.append("Stage B pilot binding mismatch")
    if manifest.get("source_pilot", {}).get("manifest_file_sha256") != sha256_file(
        pilot_root / "manifest.json"
    ):
        errors.append("Stage B pilot physical hash mismatch")
    if manifest.get("source_sense_contract", {}).get(
        "manifest_sha256"
    ) != contract_manifest.get("manifest_sha256"):
        errors.append("Stage B sense contract binding mismatch")
    if manifest.get("source_sense_contract", {}).get(
        "manifest_file_sha256"
    ) != sha256_file(sense_contract_root / "manifest.json"):
        errors.append("Stage B sense contract physical hash mismatch")

    annotation_contract = read_json(stage_b_root / "stage_b_contract.json")
    validate_self_hash(
        annotation_contract,
        "contract_sha256",
        "Stage B contract",
        errors,
    )
    bindings = read_json(stage_b_root / "source_bindings.json")
    validate_self_hash(
        bindings,
        "source_bindings_sha256",
        "Stage B source bindings",
        errors,
    )
    if annotation_contract.get("policy_id") != POLICY_ID or bindings.get(
        "policy_id"
    ) != POLICY_ID:
        errors.append("Stage B policy mismatch")
    if annotation_contract.get("source_pilot_manifest_sha256") != pilot_manifest.get(
        "manifest_sha256"
    ):
        errors.append("Stage B contract pilot hash mismatch")
    if bindings.get("sense_contract_manifest_sha256") != contract_manifest.get(
        "manifest_sha256"
    ):
        errors.append("Stage B binding sense-contract hash mismatch")
    if bindings.get("source_pilot_manifest_sha256") != pilot_manifest.get(
        "manifest_sha256"
    ):
        errors.append("Stage B binding pilot hash mismatch")
    if annotation_contract.get("sense_contract_manifest_sha256") != contract_manifest.get(
        "manifest_sha256"
    ):
        errors.append("Stage B contract sense-contract hash mismatch")

    pilot = pilot_records(pilot_root)
    effective = _effective_contract_records(sense_contract_root)
    rows_by_table = {
        table: read_csv(stage_b_root / filename)
        for table, (filename, _, _) in TABLES.items()
    }
    actual_counts = {table: len(rows) for table, rows in rows_by_table.items()}
    if actual_counts != manifest.get("row_counts"):
        errors.append("Stage B manifest row counts differ")
    context_overlap = {
        row["context_id"] for row in rows_by_table["contrastive"]
    } & {row["context_id"] for row in rows_by_table["context"]}
    if context_overlap:
        errors.append(f"context IDs occur in both tables: {sorted(context_overlap)}")

    resolution_counts = {}
    for table, rows in rows_by_table.items():
        spec = annotation_contract["tables"][table]
        expected = bindings["tables"][table]["rows"]
        units = [row.get(spec["unit_field"], "") for row in rows]
        if len(units) != len(set(units)) or set(units) != set(expected):
            errors.append(f"{table}: annotation units differ from binding")
        counts = Counter()
        for row_number, row in enumerate(rows, start=2):
            unit = row.get(spec["unit_field"], "")
            payload = source_payload_hash(row, spec["source_fields"])
            if row.get("source_payload_sha256") != payload:
                errors.append(f"{table}:{row_number}: source payload was modified")
            expected_row = expected.get(unit, {})
            if row.get("source_payload_sha256") != expected_row.get(
                "source_payload_sha256"
            ):
                errors.append(f"{table}:{row_number}: source binding differs")
            source_record = pilot[spec["source_record_kind"]].get(unit, {})
            source_hash_field = (
                "candidate_instance_sha256"
                if table == "candidate"
                else "context_sha256"
            )
            if row.get("source_record_sha256") != source_record.get(source_hash_field):
                errors.append(f"{table}:{row_number}: pilot record differs")
            sense_contract = effective.get(row.get("sense_id", ""), {})
            if row.get("reviewed_sense_contract_sha256") != sense_contract.get(
                "reviewed_sense_contract_sha256"
            ):
                errors.append(f"{table}:{row_number}: effective sense contract differs")
            if row.get("effective_definition_en") != sense_contract.get(
                "effective_definition_en"
            ) or row.get("effective_part_of_speech") != sense_contract.get(
                "effective_part_of_speech"
            ):
                errors.append(f"{table}:{row_number}: effective sense values differ")

            _validate_stage_b_values(
                table,
                row_number,
                row,
                annotation_contract["label_sets"],
                errors,
            )
            _validate_human_whitespace(table, row_number, row, errors)
            mode, _, row_errors = conditional_resolution(
                row,
                SIGNATURES[table],
                require_complete=require_complete,
                optional_signature_fields=OPTIONAL_SIGNATURES[table],
            )
            errors.extend(f"{table}:{row_number}: {value}" for value in row_errors)
            counts[mode or "PENDING"] += 1
        resolution_counts[table] = dict(counts)

    _validate_partial_candidate_relations(rows_by_table["candidate"], errors)
    if require_complete:
        _validate_effective_candidate_groups(rows_by_table["candidate"], errors)
    return {
        "schema_id": "D2LCSTStageBValidationReportV1_4",
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if not errors else "FAIL",
        "mode": "COMPLETE" if require_complete else "PARTIAL_OR_TEMPLATE",
        "row_counts": actual_counts,
        "resolution_counts": resolution_counts,
        "error_count": len(errors),
        "errors": errors,
    }


def _effective_contract_records(root: Path) -> dict[str, dict[str, Any]]:
    records = {}
    for row in read_jsonl(root / "reviewed_sense_contract.jsonl"):
        identity = dict(row)
        expected = identity.pop("reviewed_sense_contract_sha256", None)
        if expected != sha256_object(identity):
            raise ValueError(f"Reviewed sense contract row hash mismatch: {row.get('sense_id')}")
        records[row["sense_id"]] = row
    return records


def _base_source(
    sense_contract: dict[str, Any],
    source_record_sha256: str,
) -> dict[str, Any]:
    return {
        "workflow_policy_id": POLICY_ID,
        "sense_id": sense_contract["sense_id"],
        "source_term": sense_contract["source_term"],
        "effective_definition_en": sense_contract["effective_definition_en"],
        "effective_part_of_speech": sense_contract["effective_part_of_speech"],
        "reviewed_sense_contract_sha256": sense_contract[
            "reviewed_sense_contract_sha256"
        ],
        "source_record_sha256": source_record_sha256,
    }


def _contrastive_rows(
    pilot: dict[str, dict[str, dict[str, Any]]],
    effective: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for context in pilot["CONTEXT"].values():
        if context.get("context_role") != "CONTRASTIVE":
            continue
        source = {
            **_base_source(
                effective[context["sense_id"]],
                context["context_sha256"],
            ),
            "annotation_unit": "CONTRASTIVE_CONTEXT",
            "term_id": context["term_id"],
            "context_id": context["context_id"],
            "context_source": "CORPUS",
            "source_text": context["source_text"],
            "matched_surface_exact": _exact_surface(context),
            "matched_surface_normalized": _normalized_surface(context),
            "content_sha256": context["content_sha256"],
        }
        rows.append({**source, **_human_fields("contrastive")})
    return sorted(rows, key=lambda row: row["sense_id"])


def _context_rows(
    pilot: dict[str, dict[str, dict[str, Any]]],
    effective: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for context in pilot["CONTEXT"].values():
        if context.get("context_role") not in {"PRIMARY", "BACKUP"}:
            continue
        source = {
            **_base_source(
                effective[context["sense_id"]],
                context["context_sha256"],
            ),
            "annotation_unit": "SAME_SENSE_CONTEXT",
            "term_id": context["term_id"],
            "context_id": context["context_id"],
            "context_role": context["context_role"],
            "context_slot": context["context_slot"],
            "source_text": context["source_text"],
            "matched_surface_exact": _exact_surface(context),
            "matched_surface_normalized": _normalized_surface(context),
            "content_sha256": context["content_sha256"],
            "model_proposed_context_type": context.get("context_type", ""),
        }
        rows.append({**source, **_human_fields("context")})
    return sorted(
        rows,
        key=lambda row: (
            row["sense_id"],
            0 if row["context_role"] == "PRIMARY" else 1,
            row["context_id"],
        ),
    )


def _candidate_rows(
    pilot: dict[str, dict[str, dict[str, Any]]],
    effective: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    for candidate in pilot["CANDIDATE"].values():
        source = {
            **_base_source(
                effective[candidate["sense_id"]],
                candidate["candidate_instance_sha256"],
            ),
            "annotation_unit": "CANDIDATE",
            "term_id": candidate["term_id"],
            "scope_id": candidate["scope_id"],
            "candidate_slot_id": candidate["candidate_slot_id"],
            "candidate_instance_id": candidate["candidate_instance_id"],
            "candidate_target_vi": candidate["candidate_target_vi"],
            "formation_method": candidate["formation_method"],
        }
        rows.append({**source, **_human_fields("candidate")})
    return sorted(rows, key=lambda row: (row["sense_id"], row["candidate_slot_id"]))


def _validate_stage_b_values(
    table: str,
    row_number: int,
    row: dict[str, str],
    labels: dict[str, list[str]],
    errors: list[str],
) -> None:
    for prefix in ("reviewer_1", "reviewer_2", "reviewer_3", "adjudicated"):
        status_field = (
            "adjudication_status" if prefix == "adjudicated" else f"{prefix}_status"
        )
        if not row.get(status_field):
            continue
        for field in SIGNATURES[table]:
            value = row.get(f"{prefix}_{field}", "")
            if not value:
                continue
            label_key = {
                "semantic_fit_label": "semantic_fit_label",
                "use_in_sense_boundary_test": "boolean",
            }.get(field, field)
            if field in {"candidate_rank", "relation_to_candidate_instance_id"}:
                continue
            if value not in labels[label_key]:
                errors.append(f"{table}:{row_number}: invalid {prefix}_{field}")
        if table == "contrastive":
            if row.get(f"{prefix}_contrastive_label") == "INVALID" and row.get(
                f"{prefix}_use_in_sense_boundary_test"
            ) not in {"", "FALSE"}:
                errors.append(f"contrastive:{row_number}: INVALID context cannot enter test")
        elif table == "context":
            same_sense = row.get(f"{prefix}_same_sense_label")
            validity = row.get(f"{prefix}_context_validity")
            context_type = row.get(f"{prefix}_context_type")
            if same_sense == "NOT_SAME_SENSE" or validity == "INVALID":
                if context_type not in {"", "NOT_APPLICABLE"}:
                    errors.append(f"context:{row_number}: invalid context type must be N/A")
            elif same_sense == "SAME_SENSE" and validity in {"VALID", "WEAK"}:
                if row.get(status_field) in {"REVIEWED", "ADJUDICATED"} and context_type not in {
                    "C1",
                    "C2",
                    "C3",
                    "C4",
                    "C5",
                }:
                    errors.append(f"context:{row_number}: valid context requires C1-C5")
        else:
            rank = row.get(f"{prefix}_candidate_rank")
            if rank and (not rank.isdigit() or int(rank) not in {1, 2, 3}):
                errors.append(f"candidate:{row_number}: rank must be 1..3")


def _validate_effective_candidate_groups(
    rows: list[dict[str, str]],
    errors: list[str],
) -> None:
    effective_by_id = {}
    by_sense: dict[str, list[tuple[dict[str, str], dict[str, str]]]] = defaultdict(list)
    for row in rows:
        mode, decision, row_errors = conditional_resolution(
            row,
            SIGNATURES["candidate"],
            require_complete=True,
            optional_signature_fields=OPTIONAL_SIGNATURES["candidate"],
        )
        if row_errors or decision is None:
            continue
        if decision["candidate_relation"] == "UNCERTAIN":
            errors.append(f"candidate:{row['candidate_instance_id']}: unresolved relation")
        effective_by_id[row["candidate_instance_id"]] = decision
        by_sense[row["sense_id"]].append((row, decision))

    for sense_id, items in by_sense.items():
        ranks = []
        for row, decision in items:
            relation = decision["candidate_relation"]
            target = decision["relation_to_candidate_instance_id"]
            rank = decision["candidate_rank"]
            if relation == "INDEPENDENT_ALTERNATIVE":
                if target:
                    errors.append(f"candidate:{row['candidate_instance_id']}: independent candidate has target")
                if decision["candidate_decision"] == "REJECT":
                    if rank:
                        errors.append(f"candidate:{row['candidate_instance_id']}: rejected candidate must not be ranked")
                elif not rank:
                    errors.append(f"candidate:{row['candidate_instance_id']}: independent candidate requires rank")
                elif rank.isdigit() and int(rank) in {1, 2, 3}:
                    ranks.append(int(rank))
            elif relation in {"MORPHOLOGICAL_VARIANT", "DUPLICATE"}:
                if rank:
                    errors.append(f"candidate:{row['candidate_instance_id']}: variant/duplicate rank must be blank")
                target_decision = effective_by_id.get(target)
                if target_decision is None:
                    errors.append(f"candidate:{row['candidate_instance_id']}: relation target is missing")
                elif target_decision["candidate_relation"] != "INDEPENDENT_ALTERNATIVE" or target_decision[
                    "candidate_decision"
                ] == "REJECT":
                    errors.append(f"candidate:{row['candidate_instance_id']}: target is not canonical")
                target_row = next((candidate for candidate in rows if candidate["candidate_instance_id"] == target), None)
                if target_row is not None and target_row["sense_id"] != sense_id:
                    errors.append(f"candidate:{row['candidate_instance_id']}: target belongs to foreign sense")
        if len(ranks) != len(set(ranks)):
            errors.append(f"candidate:{sense_id}: independent ranks are duplicated")
        if ranks and set(ranks) != set(range(1, len(ranks) + 1)):
            errors.append(f"candidate:{sense_id}: independent ranks must be contiguous")


def _validate_partial_candidate_relations(
    rows: list[dict[str, str]],
    errors: list[str],
) -> None:
    by_id = {row["candidate_instance_id"]: row for row in rows}
    for prefix in ("reviewer_1", "reviewer_2", "reviewer_3", "adjudicated"):
        graph = {}
        for row in rows:
            relation = row.get(f"{prefix}_candidate_relation", "")
            target = row.get(f"{prefix}_relation_to_candidate_instance_id", "")
            if relation in {"INDEPENDENT_ALTERNATIVE", "UNCERTAIN"} and target:
                errors.append(
                    f"candidate:{row['candidate_instance_id']}: {relation} must not have target"
                )
            if relation in {"MORPHOLOGICAL_VARIANT", "DUPLICATE"}:
                related = by_id.get(target)
                if related is None:
                    errors.append(
                        f"candidate:{row['candidate_instance_id']}: relation target is missing"
                    )
                elif related["sense_id"] != row["sense_id"]:
                    errors.append(
                        f"candidate:{row['candidate_instance_id']}: relation target is foreign"
                    )
                elif target == row["candidate_instance_id"]:
                    errors.append(
                        f"candidate:{row['candidate_instance_id']}: relation target is self"
                    )
                else:
                    graph[row["candidate_instance_id"]] = target
        for start in graph:
            seen = set()
            node = start
            while node in graph:
                if node in seen:
                    errors.append(f"candidate:{prefix}: relation cycle includes {node}")
                    break
                seen.add(node)
                node = graph[node]


def _validate_human_whitespace(
    table: str,
    row_number: int,
    row: dict[str, str],
    errors: list[str],
) -> None:
    structured_suffixes = (
        "_id",
        "_status",
        "_label",
        "_type",
        "_validity",
        "_rank",
        "_decision",
        "_relation",
        "_reviewed_at",
        "adjudicated_at",
        "_test",
        "_applicability",
        "_candidate_instance_id",
    )
    for key, value in row.items():
        if not key.startswith(("reviewer_", "adjudicat")) or not value:
            continue
        if key.endswith(structured_suffixes) and value != value.strip():
            errors.append(f"{table}:{row_number}: whitespace in {key}")


def _human_fields(table: str) -> dict[str, str]:
    fields = {}
    for prefix in ("reviewer_1", "reviewer_2", "reviewer_3"):
        fields[f"{prefix}_id"] = ""
        fields[f"{prefix}_status"] = ""
        for name in SIGNATURES[table]:
            fields[f"{prefix}_{name}"] = ""
        fields[f"{prefix}_reviewed_at"] = ""
        fields[f"{prefix}_notes"] = ""
    fields["adjudicator_id"] = ""
    fields["adjudication_status"] = ""
    for name in SIGNATURES[table]:
        fields[f"adjudicated_{name}"] = ""
    fields["adjudicated_at"] = ""
    fields["adjudication_notes"] = ""
    return fields


def _label_sets() -> dict[str, list[str]]:
    return {
        "contrastive_label": ["VALID_BOUNDARY", "WEAK_BOUNDARY", "INVALID"],
        "boolean": ["TRUE", "FALSE"],
        "same_sense_label": ["SAME_SENSE", "NOT_SAME_SENSE", "UNCERTAIN"],
        "context_type": ["C1", "C2", "C3", "C4", "C5", "NOT_APPLICABLE"],
        "context_validity": ["VALID", "WEAK", "INVALID"],
        "applicability": ["IN_SCOPE", "OUT_OF_SCOPE", "UNCERTAIN"],
        "semantic_fit_label": ["PASS", "MINOR", "FAIL"],
        "candidate_decision": ["ACCEPT", "CONDITIONAL", "REJECT"],
        "candidate_relation": [
            "INDEPENDENT_ALTERNATIVE",
            "MORPHOLOGICAL_VARIANT",
            "DUPLICATE",
            "UNCERTAIN",
        ],
    }


def _exact_surface(context: dict[str, Any]) -> str:
    return context["source_text"][context["match_start"] : context["match_end"]]


def _normalized_surface(context: dict[str, Any]) -> str:
    return " ".join(_exact_surface(context).casefold().split())
