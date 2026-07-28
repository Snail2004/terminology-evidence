from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from hardening_common import (
    read_csv,
    read_json,
    read_jsonl,
    sha256_bytes,
    sha256_file,
    sha256_text,
    stable_id,
    validate_file_bindings,
    validate_self_hash,
)


ALLOWED_AUDIT_STATUSES = {
    "PASS_CORPUS_EXTRACTED",
    "FAIL_SYNTHETIC",
    "FAIL_REWRITTEN",
    "FAIL_OFFSET_INVALID",
    "FAIL_SOURCE_HASH_MISMATCH",
    "FAIL_PROVENANCE_INCOMPLETE",
}
ALLOWED_SOURCE_TIERS = {
    "UNIVERSITY_TEXTBOOK",
    "UNIVERSITY_LECTURE",
    "PUBLISHED_TRANSLATED_BOOK",
    "PEER_REVIEWED_PAPER",
    "THESIS_DISSERTATION",
    "OFFICIAL_VENDOR_DOCUMENTATION",
    "GOVERNMENT_OR_STANDARDS_DOCUMENT",
    "OPEN_WEB",
}


def _as_bool(value: Any) -> bool:
    return value is True or str(value).strip().casefold() == "true"


def _validate_checksums(root: Path, errors: list[str]) -> None:
    checksum_path = root / "CHECKSUMS.sha256"
    if not checksum_path.is_file():
        errors.append("Missing CHECKSUMS.sha256")
        return
    expected: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or "  " not in line:
            errors.append("Malformed CHECKSUMS.sha256 line")
            continue
        digest, relative = line.split("  ", 1)
        expected[relative] = digest
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != checksum_path
    }
    if set(expected) != actual_paths:
        errors.append("CHECKSUMS.sha256 file set mismatch")
    for relative, digest in expected.items():
        path = root / relative
        if path.is_file() and sha256_file(path) != digest:
            errors.append(f"Checksum mismatch: {relative}")


def _validate_archive(root: Path, archive_path: Path, errors: list[str]) -> None:
    checksum_path = Path(str(archive_path) + ".sha256")
    if not archive_path.is_file() or not checksum_path.is_file():
        errors.append("Archive or archive checksum is missing")
        return
    declared = checksum_path.read_text(encoding="utf-8").split()[0]
    if declared != sha256_file(archive_path):
        errors.append("Archive SHA256 mismatch")
    expected = {
        f"dataset_methodology_hardening_v1/{path.relative_to(root).as_posix()}": path
        for path in root.rglob("*")
        if path.is_file()
    }
    with zipfile.ZipFile(archive_path) as archive:
        if set(archive.namelist()) != set(expected):
            errors.append("Archive member set mismatch")
            return
        for name, source_path in expected.items():
            if sha256_bytes(archive.read(name)) != sha256_file(source_path):
                errors.append(f"Archive member hash mismatch: {name}")


def validate_artifact(
    parent_root: Path,
    artifact_root: Path,
    archive_path: Path | None = None,
) -> dict[str, Any]:
    parent_root = parent_root.resolve(strict=True)
    artifact_root = artifact_root.resolve(strict=True)
    errors: list[str] = []
    parent_manifest = read_json(parent_root / "manifest.json")
    manifest = read_json(artifact_root / "manifest.json")
    validation = read_json(artifact_root / "validation_report.json")
    validate_self_hash(parent_manifest, "manifest_sha256", "Parent manifest", errors)
    validate_file_bindings(parent_root, parent_manifest.get("files", {}), "Parent", errors)
    validate_self_hash(
        manifest, "artifact_manifest_sha256", "Artifact manifest", errors
    )
    validate_file_bindings(artifact_root, manifest.get("files", {}), "Artifact", errors)
    actual_bound_files = {
        path.relative_to(artifact_root).as_posix()
        for path in artifact_root.rglob("*")
        if path.is_file()
        and path.relative_to(artifact_root).as_posix()
        not in {"manifest.json", "CHECKSUMS.sha256"}
    }
    if set(manifest.get("files", {})) != actual_bound_files:
        errors.append("Artifact manifest file set mismatch")
    _validate_checksums(artifact_root, errors)
    if manifest.get("parent_dataset_manifest_sha256") != parent_manifest.get(
        "manifest_sha256"
    ):
        errors.append("Parent manifest semantic binding mismatch")
    if manifest.get("parent_dataset_manifest_file_sha256") != sha256_file(
        parent_root / "manifest.json"
    ):
        errors.append("Parent manifest physical binding mismatch")

    contexts = read_jsonl(parent_root / "contexts.jsonl")
    candidates = read_jsonl(parent_root / "candidate_instances.jsonl")
    context_by_id = {row["context_id"]: row for row in contexts}
    candidate_by_id = {row["candidate_instance_id"]: row for row in candidates}
    audit_rows = read_csv(artifact_root / "corpus_origin_audit.csv")
    audit_by_id = {row["context_id"]: row for row in audit_rows}
    if len(audit_rows) != len(contexts) or len(audit_by_id) != len(contexts):
        errors.append("Corpus audit must cover every parent context exactly once")
    source_blocks = read_jsonl(artifact_root / "source_block_registry.jsonl")
    source_block_by_id = {row["block_id"]: row for row in source_blocks}
    for block in source_blocks:
        if sha256_text(block["source_text"]) != block["block_text_sha256"]:
            errors.append(f"Source block hash mismatch: {block['block_id']}")
        if block.get("source_document_sha256") != manifest.get(
            "source_document_sha256"
        ):
            errors.append(f"Source document binding mismatch: {block['block_id']}")
    for context_id, context in context_by_id.items():
        audit = audit_by_id.get(context_id)
        if audit is None:
            continue
        if audit["audit_status"] not in ALLOWED_AUDIT_STATUSES:
            errors.append(f"Unknown audit status: {context_id}")
        if audit["parent_record_sha256"] != context["context_sha256"]:
            errors.append(f"Parent context hash mismatch: {context_id}")
        if audit["audit_status"] == "PASS_CORPUS_EXTRACTED":
            block = source_block_by_id.get(audit["block_id"])
            if audit["origin"] != "CORPUS_EXTRACTED" or block is None:
                errors.append(f"Invalid corpus origin binding: {context_id}")
            elif context["source_text"] not in block["source_text"]:
                errors.append(f"Corpus context is not verbatim: {context_id}")
            if audit["source_hash"] != manifest.get("source_document_sha256"):
                errors.append(f"Corpus source hash mismatch: {context_id}")
        if audit["audit_status"] == "FAIL_SYNTHETIC":
            if audit["origin"] != "SYNTHETIC_CONTROLLED":
                errors.append(f"Synthetic origin mismatch: {context_id}")
            if _as_bool(audit["eligible_for_c_primary_support"]):
                errors.append(f"Synthetic context entered C primary support: {context_id}")

    statistical = read_jsonl(artifact_root / "statistical_units.jsonl")
    occurrence_ids: set[str] = set()
    cluster_splits: dict[str, set[str]] = defaultdict(set)
    for row in statistical:
        candidate = candidate_by_id.get(row["candidate_id"])
        context = context_by_id.get(row["context_id"])
        audit = audit_by_id.get(row["context_id"])
        if candidate is None or context is None or audit is None:
            errors.append(f"Statistical unit has unknown parent: {row['occurrence_id']}")
            continue
        expected_occurrence = stable_id(
            "occurrence",
            row["candidate_id"],
            row["context_id"],
            row["document_id"],
            row["block_id"],
        )
        expected_pairing = stable_id(
            "pairing",
            row["sense_id"],
            row["candidate_slot_id"],
            row["context_id"],
        )
        expected_resampling_group = stable_id("resampling_group", row["sense_id"])
        expected_source_cluster = stable_id(
            "source_block_cluster", row["document_id"], row["block_id"]
        )
        if row["occurrence_id"] != expected_occurrence:
            errors.append(f"Occurrence ID mismatch: {row['occurrence_id']}")
        if row["pairing_id"] != expected_pairing:
            errors.append(f"Pairing ID mismatch: {row['occurrence_id']}")
        if row["resampling_group_id"] != expected_resampling_group:
            errors.append(f"Resampling group mismatch: {row['occurrence_id']}")
        if row["source_block_cluster_id"] != expected_source_cluster:
            errors.append(f"Source block cluster mismatch: {row['occurrence_id']}")
        if row["occurrence_id"] in occurrence_ids:
            errors.append(f"Duplicate occurrence ID: {row['occurrence_id']}")
        occurrence_ids.add(row["occurrence_id"])
        if not _as_bool(audit["eligible_for_c_support"]):
            errors.append(f"Ineligible context in statistical units: {row['context_id']}")
        if row["parent_record_sha256"] != candidate["candidate_instance_sha256"]:
            errors.append(f"Candidate parent hash mismatch: {row['occurrence_id']}")
        if row["parent_context_sha256"] != context["context_sha256"]:
            errors.append(f"Context parent hash mismatch: {row['occurrence_id']}")
        cluster_splits[row["source_block_cluster_id"]].add(row["split"])

    expected_statistical_count = sum(
        sum(
            candidate["sense_id"]
            == context_by_id[audit["context_id"]]["sense_id"]
            for candidate in candidates
        )
        for audit in audit_rows
        if _as_bool(audit["eligible_for_c_support"])
    )
    if len(statistical) != expected_statistical_count:
        errors.append("Statistical unit coverage mismatch")
    leakage = read_jsonl(artifact_root / "source_block_split_leakage.jsonl")
    expected_leakage = {
        cluster for cluster, splits in cluster_splits.items() if len(splits) > 1
    }
    if {row["source_block_cluster_id"] for row in leakage} != expected_leakage:
        errors.append("Source block split leakage audit mismatch")

    registry = read_jsonl(
        artifact_root / "controlled_vietnamese_source_registry.jsonl"
    )
    for row in registry:
        if row.get("source_tier") not in ALLOWED_SOURCE_TIERS:
            errors.append(f"Invalid controlled source tier: {row.get('source_id')}")
        for field in ("organization_id", "document_id", "content_hash", "dedup_group_id"):
            if not row.get(field):
                errors.append(f"Controlled source missing {field}: {row.get('source_id')}")

    adversarial = read_json(artifact_root / "adversarial_manifest.json")
    if adversarial.get("case_count") != len(adversarial.get("cases", [])):
        errors.append("Adversarial case count mismatch")
    tac = read_json(artifact_root / "tac_drift_manifest.json")
    if (
        tac.get("natural_case_count", 0)
        + tac.get("synthetic_controlled_case_count", 0)
        != len(tac.get("cases", []))
    ):
        errors.append("TAC drift case count mismatch")

    downstream = read_jsonl(artifact_root / "downstream_block_selection.jsonl")
    chapters: set[str] = set()
    for row in downstream:
        if row["chapter_id"] in chapters:
            errors.append(f"Duplicate downstream chapter: {row['chapter_id']}")
        chapters.add(row["chapter_id"])
        if not row.get("selected_before_model_run"):
            errors.append(f"Downstream block was not pre-frozen: {row['block_id']}")
        if row.get("experiment_arms") != ["A", "B", "C", "D"]:
            errors.append(f"Downstream arms mismatch: {row['block_id']}")
        block = source_block_by_id.get(row["block_id"])
        if block is None or row["parent_record_sha256"] != block["block_text_sha256"]:
            errors.append(f"Downstream block parent mismatch: {row['block_id']}")

    checks = validation.get("checks", {})
    status_counts = Counter(row["audit_status"] for row in audit_rows)
    if checks.get("audit_status_counts") != dict(sorted(status_counts.items())):
        errors.append("Validation report audit counts mismatch")
    if checks.get("statistical_unit_count") != len(statistical):
        errors.append("Validation report statistical count mismatch")
    if checks.get("cross_split_source_block_cluster_count") != len(leakage):
        errors.append("Validation report leakage count mismatch")
    if checks.get("downstream_selected_block_count") != len(downstream):
        errors.append("Validation report downstream count mismatch")
    if archive_path is not None:
        _validate_archive(artifact_root, archive_path.resolve(strict=False), errors)
    return {
        "status": "FAIL" if errors else validation["status"],
        "structural_integrity": "FAIL" if errors else "PASS",
        "methodology_readiness": validation.get("methodology_readiness"),
        "error_count": len(errors),
        "errors": errors,
        "blocker_count": len(validation.get("blockers", [])),
        "audit_status_counts": dict(sorted(status_counts.items())),
        "statistical_unit_count": len(statistical),
        "source_block_split_leakage_count": len(leakage),
        "controlled_vietnamese_source_count": len(registry),
        "downstream_block_count": len(downstream),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-root", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--archive-path", type=Path)
    args = parser.parse_args()
    result = validate_artifact(args.parent_root, args.artifact_root, args.archive_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
