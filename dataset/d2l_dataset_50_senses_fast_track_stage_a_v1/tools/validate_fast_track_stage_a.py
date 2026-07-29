from __future__ import annotations

import argparse
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

try:
    from .common import (
        build_file_inventory,
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from .spec import (
        ARTIFACT_NAME,
        LANE_COUNTS,
        MAIN_DATASET_AUTHORITY_COMMIT,
        MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        OFFICIAL_5_MANIFEST_PHYSICAL_SHA256,
        OFFICIAL_5_MANIFEST_SHA256,
        POLICY_ID,
        POOL_STRATUM_COUNTS,
        REPAIRED_5_MANIFEST_PHYSICAL_SHA256,
        REPAIRED_5_MANIFEST_SHA256,
        REVIEWED_15_MANIFEST_PHYSICAL_SHA256,
        REVIEWED_15_MANIFEST_SHA256,
        REVIEW_FIELDS,
        RISK_COUNTS_NEW,
        SOURCE_BATCH_MANIFEST_PHYSICAL_SHA256,
        SOURCE_BATCH_MANIFEST_SHA256,
        SOURCE_DOCUMENT_SHA256,
        STATUS,
        V3_MANIFEST_PHYSICAL_SHA256,
        V3_MANIFEST_SHA256,
    )
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        build_file_inventory,
        canonical_json_bytes,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from spec import (  # type: ignore
        ARTIFACT_NAME,
        LANE_COUNTS,
        MAIN_DATASET_AUTHORITY_COMMIT,
        MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        OFFICIAL_5_MANIFEST_PHYSICAL_SHA256,
        OFFICIAL_5_MANIFEST_SHA256,
        POLICY_ID,
        POOL_STRATUM_COUNTS,
        REPAIRED_5_MANIFEST_PHYSICAL_SHA256,
        REPAIRED_5_MANIFEST_SHA256,
        REVIEWED_15_MANIFEST_PHYSICAL_SHA256,
        REVIEWED_15_MANIFEST_SHA256,
        REVIEW_FIELDS,
        RISK_COUNTS_NEW,
        SOURCE_BATCH_MANIFEST_PHYSICAL_SHA256,
        SOURCE_BATCH_MANIFEST_SHA256,
        SOURCE_DOCUMENT_SHA256,
        STATUS,
        V3_MANIFEST_PHYSICAL_SHA256,
        V3_MANIFEST_SHA256,
    )


EXPECTED_COUNTS = {
    "sense_pool": 60,
    "candidate_pool": 180,
    "selected_context": 468,
    "stage_a_new_sense": 44,
    "stage_a_batch": 9,
}
EXPECTED_WORKLOAD = {
    "existing_senses_not_re_reviewed": 16,
    "new_senses_requiring_stage_a": 44,
    "reviewer_1_cases": 44,
    "reviewer_2_cases": 31,
    "independent_stage_a_review_decisions": 75,
    "blind_audits_r0": 13,
    "mandatory_adjudications_r4": 16,
    "conditional_adjudications_r3_max": 15,
    "stage_b_candidate_reviews_after_final_50": 300,
}
SOURCE_MANIFESTS = {
    "v3_manifest.json": (V3_MANIFEST_PHYSICAL_SHA256, V3_MANIFEST_SHA256),
    "source_batches_manifest.json": (
        SOURCE_BATCH_MANIFEST_PHYSICAL_SHA256,
        SOURCE_BATCH_MANIFEST_SHA256,
    ),
    "official_5_manifest.json": (
        OFFICIAL_5_MANIFEST_PHYSICAL_SHA256,
        OFFICIAL_5_MANIFEST_SHA256,
    ),
    "reviewed_15_manifest.json": (
        REVIEWED_15_MANIFEST_PHYSICAL_SHA256,
        REVIEWED_15_MANIFEST_SHA256,
    ),
    "repaired_5_manifest.json": (
        REPAIRED_5_MANIFEST_PHYSICAL_SHA256,
        REPAIRED_5_MANIFEST_SHA256,
    ),
}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _validate_manifest(root: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        manifest = strict_json_object(root / "manifest.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"manifest: {exc}")
        return None
    if manifest.get("schema_id") != "D2LFastTrackStageAManifestV1":
        errors.append("manifest schema mismatch")
    if manifest.get("artifact_name") != ARTIFACT_NAME:
        errors.append("manifest artifact mismatch")
    if manifest.get("policy_id") != POLICY_ID or manifest.get("status") != STATUS:
        errors.append("manifest policy/status mismatch")
    if manifest.get("counts") != EXPECTED_COUNTS:
        errors.append("manifest counts mismatch")
    if manifest.get("lane_counts") != LANE_COUNTS:
        errors.append("manifest lane counts mismatch")
    if manifest.get("pool_stratum_counts") != POOL_STRATUM_COUNTS:
        errors.append("manifest stratum counts mismatch")
    if manifest.get("new_risk_counts") != RISK_COUNTS_NEW:
        errors.append("manifest risk counts mismatch")
    if manifest.get("workload") != EXPECTED_WORKLOAD:
        errors.append("manifest workload mismatch")
    if manifest.get("v3_manifest_sha256") != V3_MANIFEST_SHA256:
        errors.append("manifest V3 binding mismatch")
    if manifest.get("source_batch_manifest_sha256") != SOURCE_BATCH_MANIFEST_SHA256:
        errors.append("manifest source-batch binding mismatch")
    if manifest.get("provider_call_count") != 0:
        errors.append("manifest provider call count must be zero")
    if manifest.get("stage_b_gold_autofill_count") != 0:
        errors.append("manifest Stage B gold autofill count must be zero")
    if manifest.get("final_glossary_decision") is not None:
        errors.append("manifest contains a final glossary decision")
    if _manifest_self_hash(manifest) != manifest.get("manifest_sha256"):
        errors.append("manifest self hash mismatch")
    if manifest.get("files") != build_file_inventory(
        root, {"manifest.json", "CHECKSUMS.sha256"}
    ):
        errors.append("manifest file inventory mismatch")
    return manifest


def _validate_checksums(root: Path, errors: list[str]) -> None:
    try:
        lines = (root / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"checksums: {exc}")
        return
    actual: dict[str, str] = {}
    for line in lines:
        if " *" not in line:
            errors.append(f"malformed checksum line: {line!r}")
            continue
        digest, relative = line.split(" *", 1)
        if relative in actual:
            errors.append(f"duplicate checksum path: {relative}")
        actual[relative] = digest
    expected = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in root.rglob("*")
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    }
    if actual != dict(sorted(expected.items())):
        errors.append("checksum inventory mismatch")


def _validate_source_manifests(root: Path, errors: list[str]) -> None:
    base = root / "source_manifests"
    for name, (physical, self_hash) in SOURCE_MANIFESTS.items():
        path = base / name
        try:
            if sha256_file(path) != physical:
                errors.append(f"source manifest physical hash mismatch: {name}")
            manifest = strict_json_object(path)
            if (
                manifest.get("manifest_sha256") != self_hash
                or _manifest_self_hash(manifest) != self_hash
            ):
                errors.append(f"source manifest self hash mismatch: {name}")
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"source manifest {name}: {exc}")


def _validate_pool(
    root: Path, errors: list[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        pool = strict_jsonl(root / "master_pool_60.jsonl")
        candidates = strict_jsonl(root / "candidate_inventory_180.jsonl")
        contexts = strict_jsonl(root / "contexts_selected.jsonl")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"pool data: {exc}")
        return [], [], []
    if len(pool) != 60 or len({row.get("sense_id") for row in pool}) != 60:
        errors.append("sense pool must contain 60 unique senses")
    if Counter(row.get("lane") for row in pool) != Counter(LANE_COUNTS):
        errors.append("sense pool lane counts mismatch")
    if Counter(row.get("stratum") for row in pool) != Counter(POOL_STRATUM_COUNTS):
        errors.append("sense pool stratum counts mismatch")
    new_rows = [row for row in pool if row.get("lane") == "D_NEW"]
    if Counter(row.get("risk_class") for row in new_rows) != Counter(RISK_COUNTS_NEW):
        errors.append("new sense risk counts mismatch")
    for index, row in enumerate(pool):
        if not verify_record(row, "sense_pool_record_sha256"):
            errors.append(f"sense pool self hash mismatch: {index}")
        if row.get("provider_call_count") != 0:
            errors.append(f"sense pool provider call count is nonzero: {row.get('sense_id')}")
        if row.get("stage_b_gold_label") is not None or row.get(
            "final_glossary_decision"
        ) is not None:
            errors.append(f"sense pool contains a forbidden label: {row.get('sense_id')}")
        if row.get("target_split_status") != "PENDING_FINAL_50_FREEZE":
            errors.append(f"sense pool prematurely freezes a target split: {row.get('sense_id')}")

    if len(candidates) != 180 or len({row.get("candidate_id") for row in candidates}) != 180:
        errors.append("candidate pool must contain 180 unique candidates")
    candidate_by_sense: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for index, row in enumerate(candidates):
        if not verify_record(row, "candidate_pool_record_sha256"):
            errors.append(f"candidate pool self hash mismatch: {index}")
        candidate_by_sense[str(row.get("sense_id"))].append(row)
        if row.get("intended_candidate_role") is not None:
            errors.append(f"candidate intended role is exposed: {row.get('candidate_id')}")
        if row.get("provider_call_count") != 0 or row.get("final_gold_label") is not None:
            errors.append(f"candidate contains provider/gold data: {row.get('candidate_id')}")
        if row.get("final_glossary_decision") is not None:
            errors.append(f"candidate contains a final decision: {row.get('candidate_id')}")
    for sense in pool:
        rows = sorted(
            candidate_by_sense.get(sense["sense_id"], []),
            key=lambda row: str(row.get("candidate_slot")),
        )
        if (
            len(rows) != 3
            or sense.get("candidate_ids") != [row.get("candidate_id") for row in rows]
            or len(
                {
                    str(row.get("candidate_target_vi")).strip().casefold()
                    for row in rows
                }
            )
            != 3
        ):
            errors.append(f"sense candidate linkage mismatch: {sense.get('sense_id')}")

    if len(contexts) != 468:
        errors.append("selected context count must be 468")
    contexts_by_sense: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for index, row in enumerate(contexts):
        if not verify_record(row, "selected_context_sha256"):
            errors.append(f"selected context self hash mismatch: {index}")
        contexts_by_sense[str(row.get("pool_sense_id"))].append(row)
        text = row.get("source_text")
        if not isinstance(text, str) or sha256_bytes(text.encode("utf-8")) != row.get(
            "content_sha256"
        ):
            errors.append(f"selected context content hash mismatch: {row.get('source_context_id')}")
        if row.get("synthetic") is True and row.get("positive_evidence_eligible") is not False:
            errors.append(f"synthetic context is positive evidence: {row.get('source_context_id')}")
        if row.get("positive_evidence_eligible") is True:
            if row.get("synthetic") is not False or row.get("source_artifact_sha256") != SOURCE_DOCUMENT_SHA256:
                errors.append(f"positive context lacks real-source binding: {row.get('source_context_id')}")
        if row.get("provider_call_count") != 0 or row.get("final_glossary_decision") is not None:
            errors.append(f"selected context boundary violation: {row.get('source_context_id')}")
    for sense in pool:
        actual_ids = sorted(
            row.get("source_context_id") for row in contexts_by_sense.get(sense["sense_id"], [])
        )
        if sorted(sense.get("evidence_context_ids", [])) != actual_ids:
            errors.append(f"sense context linkage mismatch: {sense.get('sense_id')}")
        if sense.get("lane") == "D_NEW":
            positive_primary = [
                row
                for row in contexts_by_sense.get(sense["sense_id"], [])
                if row.get("positive_evidence_eligible") is True
                and "PRIMARY" in row.get("evidence_roles", [])
            ]
            if len(positive_primary) != 5:
                errors.append(f"new sense must have five real primary contexts: {sense.get('sense_id')}")
    return pool, candidates, contexts


def _review_is_blank(review: Any) -> bool:
    if not isinstance(review, Mapping) or set(review) != set(REVIEW_FIELDS):
        return False
    for field in REVIEW_FIELDS:
        value = review[field]
        if field in {
            "invalid_evidence_context_ids",
            "candidate_replacements",
            "proposed_split_labels",
        }:
            if value != []:
                return False
        elif value != "":
            return False
    return True


def _contains_forbidden_reviewer_key(value: Any) -> bool:
    forbidden = {
        "intended_candidate_role",
        "final_gold_label",
        "stage_b_gold_label",
        "final_glossary_decision",
        "c_score",
        "e_evidence",
        "global_decision",
    }
    if isinstance(value, Mapping):
        return any(key in forbidden or _contains_forbidden_reviewer_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_reviewer_key(item) for item in value)
    return False


def _validate_reviewer_input(
    path: Path,
    *,
    batch_id: str,
    reviewer_slot: str,
    expected_sense_ids: set[str],
    errors: list[str],
) -> list[dict[str, Any]]:
    try:
        payload = strict_json_object(path)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"reviewer input {batch_id}/{reviewer_slot}: {exc}")
        return []
    if payload.get("schema_id") != "D2LFastTrackStageAReviewerInputV1":
        errors.append(f"reviewer input schema mismatch: {batch_id}/{reviewer_slot}")
    if payload.get("batch_id") != batch_id or payload.get("reviewer_slot") != reviewer_slot:
        errors.append(f"reviewer input identity mismatch: {batch_id}/{reviewer_slot}")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        errors.append(f"reviewer input cases are invalid: {batch_id}/{reviewer_slot}")
        return []
    actual_ids: set[str] = set()
    source_projection = []
    for index, case in enumerate(cases):
        if not isinstance(case, Mapping) or not isinstance(case.get("source_payload"), Mapping):
            errors.append(f"reviewer case is invalid: {batch_id}/{reviewer_slot}/{index}")
            continue
        source = case["source_payload"]
        sense_id = source.get("sense_id")
        if isinstance(sense_id, str):
            actual_ids.add(sense_id)
        claimed = case.get("source_payload_sha256")
        if claimed != sha256_bytes(canonical_json_bytes(source)):
            errors.append(f"reviewer source payload hash mismatch: {batch_id}/{reviewer_slot}/{sense_id}")
        if not _review_is_blank(case.get("review")):
            errors.append(f"reviewer input is prefilled: {batch_id}/{reviewer_slot}/{sense_id}")
        if _contains_forbidden_reviewer_key(source):
            errors.append(f"reviewer source exposes a forbidden key: {batch_id}/{reviewer_slot}/{sense_id}")
        source_projection.append(
            {"sense_id": sense_id, "source_payload_sha256": claimed}
        )
    if actual_ids != expected_sense_ids:
        errors.append(f"reviewer case identities mismatch: {batch_id}/{reviewer_slot}")
    if payload.get("source_input_sha256") != sha256_bytes(
        canonical_json_bytes(source_projection)
    ):
        errors.append(f"reviewer input source hash mismatch: {batch_id}/{reviewer_slot}")
    return cases


def _validate_handoff_zip(
    zip_path: Path, input_path: Path, errors: list[str]
) -> None:
    try:
        with zipfile.ZipFile(zip_path) as archive:
            names = [info.filename for info in archive.infolist()]
            if set(names) != {
                "CHECKSUMS.sha256",
                "MESSAGE.md",
                "REVIEW_INSTRUCTIONS.md",
                "review_input.json",
            }:
                errors.append(f"reviewer handoff ZIP entries mismatch: {zip_path.name}")
            for info in archive.infolist():
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
                    errors.append(f"unsafe reviewer handoff ZIP path: {info.filename}")
            if sha256_bytes(archive.read("review_input.json")) != sha256_file(input_path):
                errors.append(f"reviewer handoff input differs from batch: {zip_path.name}")
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        errors.append(f"reviewer handoff ZIP {zip_path.name}: {exc}")


def _validate_batches(
    root: Path, pool: list[Mapping[str, Any]], errors: list[str]
) -> None:
    try:
        index = strict_json_object(root / "batch_index.json")
        errors.append("batch index must be a JSON array")
        del index
        return
    except ValueError:
        try:
            raw = json.loads((root / "batch_index.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            errors.append(f"batch index: {exc}")
            return
        if not isinstance(raw, list):
            errors.append("batch index must be a JSON array")
            return
        index_rows = raw
    new_by_id = {row["sense_id"]: row for row in pool if row.get("lane") == "D_NEW"}
    if len(index_rows) != 9 or [row.get("sense_count") for row in index_rows] != [5] * 8 + [4]:
        errors.append("batch index partition mismatch")
    seen: set[str] = set()
    reviewer_1_total = reviewer_2_total = mandatory = conditional = blind = 0
    for sequence, index_row in enumerate(index_rows, start=1):
        batch_id = f"batch_{sequence:03d}"
        if index_row.get("batch_id") != batch_id or index_row.get("sequence") != sequence:
            errors.append(f"batch index ordering mismatch: {batch_id}")
        batch_dir = root / "batches" / batch_id
        try:
            batch_manifest = strict_json_object(batch_dir / "batch_manifest.json")
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"batch manifest {batch_id}: {exc}")
            continue
        if not verify_integrity(batch_manifest):
            errors.append(f"batch manifest self hash mismatch: {batch_id}")
        if batch_manifest.get("integrity", {}).get("self_sha256") != index_row.get(
            "batch_manifest_sha256"
        ):
            errors.append(f"batch index manifest binding mismatch: {batch_id}")
        sense_ids = set(batch_manifest.get("sense_ids", []))
        if seen & sense_ids:
            errors.append(f"sense appears in multiple batches: {batch_id}")
        seen |= sense_ids
        reviewer_1_expected = sense_ids
        reviewer_2_expected = {
            sense_id
            for sense_id in sense_ids
            if new_by_id.get(sense_id, {}).get("risk_class")
            in {"R3_AMBIGUOUS", "R4_SPLIT_OR_POS_RISK"}
        }
        _validate_reviewer_input(
            batch_dir / "reviewer_1_input.json",
            batch_id=batch_id,
            reviewer_slot="reviewer_1",
            expected_sense_ids=reviewer_1_expected,
            errors=errors,
        )
        _validate_reviewer_input(
            batch_dir / "reviewer_2_input.json",
            batch_id=batch_id,
            reviewer_slot="reviewer_2",
            expected_sense_ids=reviewer_2_expected,
            errors=errors,
        )
        if sha256_file(batch_dir / "reviewer_1_input.json") != batch_manifest.get(
            "reviewer_1_input_sha256"
        ):
            errors.append(f"reviewer 1 input hash mismatch: {batch_id}")
        if sha256_file(batch_dir / "reviewer_2_input.json") != batch_manifest.get(
            "reviewer_2_input_sha256"
        ):
            errors.append(f"reviewer 2 input hash mismatch: {batch_id}")
        for slot in ("reviewer_1", "reviewer_2"):
            zip_path = root / batch_manifest[f"{slot}_handoff_zip"]
            if sha256_file(zip_path) != batch_manifest[f"{slot}_handoff_zip_sha256"]:
                errors.append(f"reviewer handoff ZIP hash mismatch: {batch_id}/{slot}")
            _validate_handoff_zip(zip_path, batch_dir / f"{slot}_input.json", errors)
        reviewer_1_total += int(batch_manifest.get("reviewer_1_case_count", -999))
        reviewer_2_total += int(batch_manifest.get("reviewer_2_case_count", -999))
        mandatory += int(batch_manifest.get("mandatory_adjudication_count", -999))
        conditional += int(batch_manifest.get("conditional_adjudication_count", -999))
        blind += int(batch_manifest.get("blind_audit_count", -999))
    if seen != set(new_by_id):
        errors.append("Stage A batches do not cover all 44 new senses exactly once")
    if (reviewer_1_total, reviewer_2_total, mandatory, conditional, blind) != (
        44,
        31,
        16,
        15,
        13,
    ):
        errors.append("Stage A workload totals mismatch")


def _validate_metadata(root: Path, errors: list[str]) -> None:
    required = {
        "RELEASE_REPORT.md",
        "selection_report.json",
        "batch_index.json",
        "lineage.json",
        "environment.json",
        "commands.txt",
        "junit.xml",
        "source/.gitattributes",
        "source/README.md",
        "source/tools/__init__.py",
        "source/tools/common.py",
        "source/tools/spec.py",
        "source/tools/build_fast_track_stage_a.py",
        "source/tools/validate_fast_track_stage_a.py",
        "source/tests/test_fast_track_stage_a.py",
    }
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    }
    for relative in sorted(required - actual):
        errors.append(f"required release file is missing: {relative}")
    try:
        summary = strict_json_object(root / "selection_report.json")
        lineage = strict_json_object(root / "lineage.json")
        environment = strict_json_object(root / "environment.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"metadata: {exc}")
        return
    for name, payload in (("summary", summary), ("lineage", lineage)):
        if not verify_integrity(payload):
            errors.append(f"{name} self hash mismatch")
        if payload.get("provider_call_count") != 0:
            errors.append(f"{name} provider call count must be zero")
        if payload.get("final_glossary_decision") is not None:
            errors.append(f"{name} contains a final glossary decision")
    if summary.get("status") != STATUS or summary.get("counts") != EXPECTED_COUNTS:
        errors.append("selection summary status/counts mismatch")
    if summary.get("workload") != EXPECTED_WORKLOAD:
        errors.append("selection summary workload mismatch")
    expected_lineage = {
        "v3_manifest_sha256": V3_MANIFEST_SHA256,
        "source_batch_manifest_sha256": SOURCE_BATCH_MANIFEST_SHA256,
        "official_5_manifest_sha256": OFFICIAL_5_MANIFEST_SHA256,
        "reviewed_15_manifest_sha256": REVIEWED_15_MANIFEST_SHA256,
        "repaired_5_manifest_sha256": REPAIRED_5_MANIFEST_SHA256,
        "source_document_sha256": SOURCE_DOCUMENT_SHA256,
    }
    for field, expected in expected_lineage.items():
        if lineage.get(field) != expected:
            errors.append(f"lineage binding mismatch: {field}")
    if lineage.get("canonical_main_dataset_authority") != {
        "main_commit": MAIN_DATASET_AUTHORITY_COMMIT,
        "accepted_zip_sha256": MAIN_DATASET_AUTHORITY_ZIP_SHA256,
        "relationship": "LANE_A_IMMUTABLE_SEED_ONLY",
    }:
        errors.append("canonical Main authority binding mismatch")
    if environment.get("network_calls") != 0 or environment.get("provider_calls") != 0:
        errors.append("environment reports network/provider calls")


def validate_artifact(root: Path) -> list[str]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
    except OSError as exc:
        return [f"artifact root: {exc}"]
    _validate_manifest(root, errors)
    _validate_checksums(root, errors)
    _validate_source_manifests(root, errors)
    pool, _, _ = _validate_pool(root, errors)
    _validate_batches(root, pool, errors)
    _validate_metadata(root, errors)
    return errors


def validate_zip(zip_path: Path, artifact_root: Path) -> list[str]:
    errors: list[str] = []
    expected = {
        path.relative_to(artifact_root).as_posix(): sha256_file(path)
        for path in artifact_root.rglob("*")
        if path.is_file()
    }
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                errors.append("ZIP contains duplicate entries")
            for info in infos:
                path = PurePosixPath(info.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in info.filename:
                    errors.append(f"ZIP contains unsafe path: {info.filename}")
                mode = (info.external_attr >> 16) & 0o170000
                if mode == 0o120000:
                    errors.append(f"ZIP contains symlink: {info.filename}")
            actual = {info.filename: sha256_bytes(archive.read(info)) for info in infos}
            if actual != expected:
                errors.append("ZIP entries differ from artifact directory")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"ZIP: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path)
    args = parser.parse_args()
    errors = validate_artifact(args.artifact_root)
    if args.zip_path is not None:
        errors.extend(validate_zip(args.zip_path.resolve(strict=True), args.artifact_root))
    result = {"status": "PASS" if not errors else "FAIL", "errors": errors}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
