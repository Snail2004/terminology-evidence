from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from common import seal, sha256_file, validate_self_hash


ALLOWED_REVIEWER_TYPES = {"HUMAN", "AI", "HUMAN_ASSISTED"}


def _valid_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def pending_provenance_template(
    *,
    review_path: Path,
    reviewer_output_ref: str | None = None,
    reviewer_slot: int,
    batch_id: str,
    source_bundle_sha256: str,
    instruction_sha256: str,
) -> dict[str, Any]:
    return seal(
        {
            "schema_id": "D2LCSTReviewerProvenanceV1",
            "status": "PENDING_OWNER_ATTESTATION",
            "batch_id": batch_id,
            "reviewer_slot": reviewer_slot,
            "reviewer_output_ref": reviewer_output_ref or review_path.as_posix(),
            "reviewer_output_sha256": sha256_file(review_path),
            "reviewer_type": None,
            "reviewer_id": None,
            "model_route": None,
            "model_provider": None,
            "model_version": None,
            "prompt_sha256": None,
            "instruction_sha256": instruction_sha256,
            "source_bundle_sha256": source_bundle_sha256,
            "run_id": None,
            "started_at": None,
            "completed_at": None,
            "independence_attestation": None,
            "other_reviewer_outputs_visible": None,
        },
        "provenance_sha256",
    )


def _valid_iso8601(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_provenance_group(
    sidecars: list[dict[str, Any]], review_paths: list[Path]
) -> dict[str, Any]:
    errors: list[str] = []
    pending: list[str] = []
    if len(sidecars) != 3 or len(review_paths) != 3:
        errors.append("exactly three provenance sidecars and review files are required")
    resolved = [path.resolve(strict=True) for path in review_paths]
    if any(
        left.samefile(right)
        for index, left in enumerate(resolved)
        for right in resolved[index + 1 :]
    ):
        errors.append("reviewer outputs must be distinct physical files")
    reviewer_ids: list[str] = []
    for index, (sidecar, review_path) in enumerate(zip(sidecars, review_paths), start=1):
        label = f"reviewer_{index}"
        if not validate_self_hash(sidecar, "provenance_sha256"):
            errors.append(f"{label}: provenance self hash mismatch")
        if sidecar.get("reviewer_output_sha256") != sha256_file(review_path):
            errors.append(f"{label}: reviewer output hash mismatch")
        if sidecar.get("reviewer_slot") != index:
            errors.append(f"{label}: reviewer_slot mismatch")
        for field in ("instruction_sha256", "source_bundle_sha256"):
            if not _valid_sha256(sidecar.get(field)):
                errors.append(f"{label}: {field} must be SHA-256")
        if sidecar.get("status") != "COMPLETE":
            pending.append(f"{label}: provenance status is not COMPLETE")
            continue
        reviewer_type = sidecar.get("reviewer_type")
        reviewer_id = sidecar.get("reviewer_id")
        if reviewer_type not in ALLOWED_REVIEWER_TYPES:
            errors.append(f"{label}: invalid reviewer_type")
        if not isinstance(reviewer_id, str) or not reviewer_id.strip():
            errors.append(f"{label}: reviewer_id is required")
        else:
            reviewer_ids.append(reviewer_id.strip())
        if sidecar.get("independence_attestation") is not True:
            errors.append(f"{label}: independence_attestation must be true")
        if sidecar.get("other_reviewer_outputs_visible") is not False:
            errors.append(f"{label}: other_reviewer_outputs_visible must be false")
        for field in ("started_at", "completed_at"):
            if not _valid_iso8601(sidecar.get(field)):
                errors.append(f"{label}: {field} must be ISO-8601")
        if reviewer_type in {"AI", "HUMAN_ASSISTED"}:
            for field in ("model_provider", "model_version", "prompt_sha256"):
                if not sidecar.get(field):
                    errors.append(f"{label}: {field} is required for {reviewer_type}")
            if sidecar.get("prompt_sha256") and not _valid_sha256(
                sidecar.get("prompt_sha256")
            ):
                errors.append(f"{label}: prompt_sha256 must be SHA-256")
        if not sidecar.get("run_id"):
            errors.append(f"{label}: run_id is required")
    completed = [sidecar for sidecar in sidecars if sidecar.get("status") == "COMPLETE"]
    if completed:
        source_hashes = {sidecar.get("source_bundle_sha256") for sidecar in completed}
        instruction_hashes = {sidecar.get("instruction_sha256") for sidecar in completed}
        if len(source_hashes) != 1:
            errors.append("complete reviewers must bind the same source bundle")
        if len(instruction_hashes) != 1:
            errors.append("complete reviewers must bind the same instruction")
    if len(reviewer_ids) != len(set(reviewer_ids)):
        errors.append("reviewer_id values must be distinct")
    status = "FAIL" if errors else ("BLOCKED" if pending else "PASS")
    return {"status": status, "errors": errors, "pending": pending}
