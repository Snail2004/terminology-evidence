from __future__ import annotations
import argparse
import json
from pathlib import Path

DEFINITION_LABELS = {"ACCEPTED", "CORRECTED", "REJECTED"}
POS_LABELS = {"ACCEPTED", "CORRECTED", "UNCERTAIN", "REJECTED"}
SCHEMA_ID = "D2LCSTParallelReviewRecordV1"
POLICY_ID = "d2l_cst_parallel_three_review_files_v1_1"

def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

def validate(root, output, require_complete=False):
    errors = []
    cases = {row["sense_id"]: row for row in rows(root / "sense_review_cases.jsonl")}
    values = rows(output)
    ids = [str(row.get("sense_id", "")) for row in values]
    if len(ids) != len(set(ids)):
        errors.append("output sense IDs are duplicated")
    if set(ids) != set(cases):
        errors.append("output sense IDs differ from review cases")
    complete = 0
    for index, row in enumerate(values, 1):
        sense_id = str(row.get("sense_id", ""))
        case = cases.get(sense_id)
        if case is None:
            continue
        prefix = f"row {index} ({sense_id})"
        expected = {"schema_id": SCHEMA_ID, "policy_id": POLICY_ID,
                    "term_id": case["term_id"], "sense_id": case["sense_id"],
                    "source_payload_sha256": case["source_payload_sha256"],
                    "case_sha256": case["case_sha256"]}
        for field, value in expected.items():
            if row.get(field) != value:
                errors.append(f"{prefix}: immutable field differs: {field}")
        populated = any(row.get(field) not in ("", [], None) for field in (
            "definition_status", "effective_definition_en", "part_of_speech_status",
            "effective_part_of_speech", "scope_note", "evidence_context_ids",
            "confidence", "rationale", "risk_flags"))
        if not populated and not require_complete:
            continue
        definition_status = row.get("definition_status")
        pos_status = row.get("part_of_speech_status")
        definition = str(row.get("effective_definition_en", ""))
        pos = str(row.get("effective_part_of_speech", ""))
        if definition_status not in DEFINITION_LABELS:
            errors.append(f"{prefix}: invalid definition_status")
        if pos_status not in POS_LABELS:
            errors.append(f"{prefix}: invalid part_of_speech_status")
        if definition_status == "ACCEPTED" and definition != case["model_definition_en"]:
            errors.append(f"{prefix}: accepted definition must equal model definition")
        if definition_status == "CORRECTED" and not definition.strip():
            errors.append(f"{prefix}: corrected definition is blank")
        if definition_status == "REJECTED" and definition:
            errors.append(f"{prefix}: rejected definition must be blank")
        if pos_status == "ACCEPTED" and pos != case["model_part_of_speech"]:
            errors.append(f"{prefix}: accepted POS must equal model POS")
        if pos_status == "CORRECTED" and not pos.strip():
            errors.append(f"{prefix}: corrected POS is blank")
        if pos_status in {"UNCERTAIN", "REJECTED"} and pos:
            errors.append(f"{prefix}: unresolved POS must be blank")
        if not str(row.get("rationale", "")).strip():
            errors.append(f"{prefix}: rationale is blank")
        try:
            confidence = float(row.get("confidence"))
            if not 0 <= confidence <= 1:
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"{prefix}: confidence must be between 0 and 1")
        evidence = row.get("evidence_context_ids")
        allowed = {c["context_id"] for group in case["evidence_contexts"].values() for c in group}
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{prefix}: evidence_context_ids must be a nonempty list")
        elif any(value not in allowed for value in evidence):
            errors.append(f"{prefix}: evidence context is outside the case")
        elif len(evidence) != len(set(evidence)):
            errors.append(f"{prefix}: evidence_context_ids contains duplicates")
        risk = row.get("risk_flags")
        if not isinstance(risk, list) or any(not isinstance(value, str) for value in risk):
            errors.append(f"{prefix}: risk_flags must be a string list")
        if not any(error.startswith(prefix) for error in errors):
            complete += 1
    return {"status": "PASS" if not errors else "FAIL", "row_count": len(values),
            "complete_row_count": complete, "error_count": len(errors), "errors": errors}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pack_root", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    result = validate(args.pack_root, args.output, args.require_complete)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)

if __name__ == "__main__":
    main()
