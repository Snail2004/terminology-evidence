from __future__ import annotations

from pathlib import Path
from typing import Any

from common import read_json, read_jsonl, sha256_file, sha256_object


def load_v3_context_authority(dataset_root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    manifest = read_json(dataset_root / "manifest.json")
    identity = dict(manifest)
    claimed = identity.pop("manifest_sha256", None)
    if claimed != sha256_object(identity):
        raise ValueError("Dataset V3 manifest self hash mismatch")
    contexts_binding = manifest.get("files", {}).get("contexts.jsonl", {})
    if sha256_file(dataset_root / "contexts.jsonl") != contexts_binding.get("sha256"):
        raise ValueError("Dataset V3 contexts hash mismatch")
    rows = read_jsonl(dataset_root / "contexts.jsonl")
    contexts = {str(row["context_id"]): row for row in rows}
    if len(contexts) != len(rows):
        raise ValueError("Dataset V3 context IDs are duplicated")
    for context_id, row in contexts.items():
        identity = dict(row)
        expected = identity.pop("context_sha256", None)
        if expected != sha256_object(identity):
            raise ValueError(f"Dataset V3 context hash mismatch: {context_id}")
    return manifest, contexts


def evidence_role(context: dict[str, Any]) -> str:
    provenance = context.get("provenance") or {}
    source_kind = str(provenance.get("source_kind", ""))
    synthetic = (
        str(context.get("binding_kind", "")) == "SYNTHETIC_BOUNDARY_PROBE"
        or source_kind == "MODEL_GENERATED_SYNTHETIC"
        or str(context.get("context_id", "")).startswith("ctxx_")
    )
    boundary = (
        synthetic
        or context.get("sense_relation") == "CONTRASTIVE"
        or context.get("context_role") == "CONTRASTIVE"
    )
    if boundary:
        return "BOUNDARY_ONLY"
    if (
        context.get("sense_relation") == "SAME_SENSE"
        and context.get("context_role") in {"PRIMARY", "BACKUP"}
        and not synthetic
    ):
        return "POSITIVE_ELIGIBLE"
    return "INELIGIBLE"


def _context_groups(case: dict[str, Any]) -> dict[str, set[str]]:
    return {
        group: {str(context["context_id"]) for context in contexts}
        for group, contexts in case.get("evidence_contexts", {}).items()
    }


def project_legacy_evidence_roles(
    *,
    case: dict[str, Any],
    review_row: dict[str, Any],
    context_authority: dict[str, dict[str, Any]],
    reviewer_slot: int,
) -> dict[str, Any]:
    raw = review_row.get("evidence_context_ids", "")
    cited = [item.strip() for item in str(raw).split(";") if item.strip()]
    groups = _context_groups(case)
    eligible: list[str] = []
    boundary: list[str] = []
    ineligible: list[str] = []
    missing: list[str] = []
    details: list[dict[str, Any]] = []
    for context_id in cited:
        context = context_authority.get(context_id)
        if context is None:
            missing.append(context_id)
            continue
        role = evidence_role(context)
        if role == "POSITIVE_ELIGIBLE":
            eligible.append(context_id)
        elif role == "BOUNDARY_ONLY":
            boundary.append(context_id)
        else:
            ineligible.append(context_id)
        details.append(
            {
                "context_id": context_id,
                "role": role,
                "binding_kind": context.get("binding_kind"),
                "context_role": context.get("context_role"),
                "sense_relation": context.get("sense_relation"),
                "source_groups": sorted(
                    group for group, values in groups.items() if context_id in values
                ),
            }
        )
    proposed_definition = sorted(set(eligible) & groups.get("definition", set()))
    proposed_pos = sorted(set(eligible) & groups.get("part_of_speech", set()))
    blockers = ["LEGACY_EVIDENCE_ROLE_CONFIRMATION_REQUIRED"]
    if boundary:
        blockers.append("BOUNDARY_REFERENCE_IN_LEGACY_UNSEPARATED_FIELD")
    if ineligible or missing:
        blockers.append("INVALID_OR_MISSING_EVIDENCE_REFERENCE")
    if not proposed_definition:
        blockers.append("NO_CONFIRMED_POSITIVE_DEFINITION_EVIDENCE")
    if not proposed_pos:
        blockers.append("NO_CONFIRMED_POSITIVE_POS_EVIDENCE")
    return {
        "schema_id": "D2LCSTLegacyEvidenceRoleProjectionV1",
        "projection_policy_id": "d2l_cst_legacy_evidence_role_projection_v1_2",
        "term_id": case["term_id"],
        "sense_id": case["sense_id"],
        "case_sha256": case["case_sha256"],
        "reviewer_slot": reviewer_slot,
        "projection_status": "PENDING_REVIEWER_ROLE_CONFIRMATION",
        "projection_is_reviewer_intent": False,
        "cited_context_ids": cited,
        "proposed_positive_definition_evidence_ids": proposed_definition,
        "proposed_positive_pos_evidence_ids": proposed_pos,
        "proposed_boundary_context_ids": sorted(boundary),
        "positive_eligible_unallocated_ids": sorted(
            set(eligible) - set(proposed_definition) - set(proposed_pos)
        ),
        "ineligible_context_ids": sorted(ineligible),
        "missing_context_ids": sorted(missing),
        "context_details": details,
        "blocker_codes": sorted(set(blockers)),
    }


def validate_explicit_evidence(
    review: dict[str, Any], context_authority: dict[str, dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    positive_fields = (
        (
            "positive_definition_evidence_ids",
            review.get("definition_status") in {"ACCEPTED", "CORRECTED"},
        ),
        (
            "positive_pos_evidence_ids",
            review.get("part_of_speech_status") in {"ACCEPTED", "CORRECTED"},
        ),
    )
    for field, required in positive_fields:
        values = review.get(field)
        if not isinstance(values, list):
            errors.append(f"{field} must be a list")
            continue
        if required and not values:
            errors.append(f"{field} must be nonempty for a resolved positive decision")
        if len(values) != len(set(values)):
            errors.append(f"{field} contains duplicates")
        for context_id in values:
            context = context_authority.get(str(context_id))
            if context is None:
                errors.append(f"{field} references missing context: {context_id}")
            elif context.get("sense_id") != review.get("sense_id"):
                errors.append(f"{field} references another sense: {context_id}")
            elif context.get("term_id") != review.get("term_id"):
                errors.append(f"{field} references another term: {context_id}")
            elif evidence_role(context) != "POSITIVE_ELIGIBLE":
                errors.append(f"{field} uses non-positive context: {context_id}")
    boundary = review.get("boundary_context_ids")
    if not isinstance(boundary, list):
        errors.append("boundary_context_ids must be a list")
    else:
        if len(boundary) != len(set(boundary)):
            errors.append("boundary_context_ids contains duplicates")
        for context_id in boundary:
            context = context_authority.get(str(context_id))
            if context is None:
                errors.append(f"boundary_context_ids references missing context: {context_id}")
            elif context.get("sense_id") != review.get("sense_id"):
                errors.append(f"boundary_context_ids references another sense: {context_id}")
            elif context.get("term_id") != review.get("term_id"):
                errors.append(f"boundary_context_ids references another term: {context_id}")
            elif evidence_role(context) != "BOUNDARY_ONLY":
                errors.append(f"boundary_context_ids uses positive context: {context_id}")
    if isinstance(boundary, list):
        positive_ids = set(review.get("positive_definition_evidence_ids") or []) | set(
            review.get("positive_pos_evidence_ids") or []
        )
        overlap = positive_ids & set(boundary)
        if overlap:
            errors.append(
                "positive and boundary evidence fields overlap: "
                + ", ".join(sorted(str(value) for value in overlap))
            )
    return errors
