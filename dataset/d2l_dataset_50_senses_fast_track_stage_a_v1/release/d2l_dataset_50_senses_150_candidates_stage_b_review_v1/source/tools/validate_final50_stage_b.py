from __future__ import annotations

import argparse
import json
import sys
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping

try:
    from .build_final50_stage_b import (
        ALLOWED_LABELS,
        ARTIFACT_NAME,
        STATUS,
        STAGE_B_POLICY_ID,
        _blank_review,
        _manifest_self_hash,
    )
    from .common import (
        build_file_inventory,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from .contract_projection_50 import (
        CONTRACT_COMMIT,
        CONTRACT_MANIFEST_SHA256,
        CONTRACT_TAG,
    )
    from .final50 import FINAL_DATASET_VERSION, FINAL_POLICY_ID, leakage_components
except ImportError:  # pragma: no cover - direct script execution
    from build_final50_stage_b import (  # type: ignore
        ALLOWED_LABELS,
        ARTIFACT_NAME,
        STATUS,
        STAGE_B_POLICY_ID,
        _blank_review,
        _manifest_self_hash,
    )
    from common import (  # type: ignore
        build_file_inventory,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
    from contract_projection_50 import CONTRACT_COMMIT, CONTRACT_MANIFEST_SHA256, CONTRACT_TAG  # type: ignore
    from final50 import FINAL_DATASET_VERSION, FINAL_POLICY_ID, leakage_components  # type: ignore


FORBIDDEN_REVIEW_KEYS = {
    "intended_candidate_role",
    "split",
    "lane",
    "stratum",
    "c_score",
    "e_evidence",
    "global_decision",
    "other_reviewer_label",
}


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _contains_forbidden(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(key in FORBIDDEN_REVIEW_KEYS or _contains_forbidden(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden(item) for item in value)
    return False


def _validate_checksums(root: Path, errors: list[str]) -> None:
    try:
        lines = (root / "CHECKSUMS.sha256").read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"checksums: {exc}")
        return
    actual: dict[str, str] = {}
    for line in lines:
        if " *" not in line:
            errors.append("malformed checksum line")
            continue
        digest, relative = line.split(" *", 1)
        if relative in actual:
            errors.append(f"duplicate checksum path: {relative}")
        actual[relative] = digest
    expected = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(root, {"CHECKSUMS.sha256"}).items()
    }
    if actual != expected:
        errors.append("checksum inventory mismatch")


def _validate_materialized(root: Path, errors: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        senses = strict_jsonl(root / "term_senses_50.jsonl")
        candidates = strict_jsonl(root / "candidate_instances_150.jsonl")
        contexts = strict_jsonl(root / "contexts_selected_50.jsonl")
        bindings = strict_jsonl(root / "stage_a_review_bindings_50.jsonl")
        split = strict_json_object(root / "split_manifest_30_10_10.json")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"materialized data: {exc}")
        return [], [], []
    if len(senses) != 50 or len({row.get("sense_id") for row in senses}) != 50:
        errors.append("term-sense count/uniqueness mismatch")
    if len(candidates) != 150 or len({row.get("candidate_instance_id") for row in candidates}) != 150:
        errors.append("candidate count/uniqueness mismatch")
    if len(bindings) != 50 or len({row.get("sense_id") for row in bindings}) != 50:
        errors.append("Stage A review binding count mismatch")
    if not verify_integrity(split):
        errors.append("split manifest self hash mismatch")
    if split.get("counts") != {"development": 30, "test": 10, "validation": 10}:
        errors.append("split manifest counts mismatch")
    assignments = split.get("assignments")
    if not isinstance(assignments, Mapping) or set(assignments) != {row.get("sense_id") for row in senses}:
        errors.append("split assignment identity mismatch")
        assignments = {}
    if Counter(assignments.values()) != Counter({"development": 30, "validation": 10, "test": 10}):
        errors.append("split assignment quota mismatch")
    sense_by_id = {row.get("sense_id"): row for row in senses}
    candidates_by_sense: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        if not verify_record(row, "record_sha256"):
            errors.append(f"candidate record self hash mismatch: {row.get('candidate_instance_id')}")
        candidates_by_sense[row.get("sense_id")].append(row)
        if row.get("binding_status") != "COMPLETE" or row.get("final_gold_label") is not None:
            errors.append(f"candidate boundary mismatch: {row.get('candidate_instance_id')}")
        if row.get("provider_call_count") != 0 or row.get("final_glossary_decision") is not None:
            errors.append(f"candidate provider/final decision mismatch: {row.get('candidate_instance_id')}")
    for sense_id, sense in sense_by_id.items():
        if not verify_record(sense, "term_sense_sha256"):
            errors.append(f"term-sense self hash mismatch: {sense_id}")
        if sense.get("dataset_version") != FINAL_DATASET_VERSION:
            errors.append(f"term-sense dataset version mismatch: {sense_id}")
        rows = candidates_by_sense.get(sense_id, [])
        targets = [_normalized(str(row.get("candidate_target_vi", ""))) for row in rows]
        if len(rows) != 3 or len(set(targets)) != 3:
            errors.append(f"candidate closure mismatch: {sense_id}")
        if sense.get("split") != assignments.get(sense_id):
            errors.append(f"term-sense split mismatch: {sense_id}")
    if any(row.get("synthetic") and row.get("positive_evidence_eligible") for row in contexts):
        errors.append("synthetic context is positive evidence")
    try:
        components = leakage_components(senses, contexts)
        for component in components:
            component_splits = {assignments[row["sense_id"]] for row in component}
            if len(component_splits) != 1:
                errors.append("sentence/block leakage component crosses splits")
    except (KeyError, ValueError) as exc:
        errors.append(f"leakage validation: {exc}")
    return senses, candidates, contexts


def _validate_contracts(
    root: Path,
    contracts_root: Path,
    senses: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    errors: list[str],
) -> None:
    package_root = contracts_root / "python"
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from terminology_contracts.bindings import verify_frozen_candidate_binding
    from terminology_contracts.canonical import verify_self_sha256
    from terminology_contracts.validation import validate_instance

    schema_dir = contracts_root / "schemas"
    effective_paths = sorted((root / "effective_sense_contracts_50").glob("*.json"))
    frozen_paths = sorted((root / "frozen_candidate_contracts_150").glob("*.json"))
    constraint_paths = sorted((root / "constraint_evidence_packages_150").glob("*.json"))
    if (len(effective_paths), len(frozen_paths), len(constraint_paths)) != (50, 150, 150):
        errors.append("contract directory counts mismatch")
        return
    effective_by_sense: dict[str, dict[str, Any]] = {}
    for path in effective_paths:
        payload = strict_json_object(path)
        effective_by_sense[str(payload.get("sense_id"))] = payload
        errors.extend(f"{path.name}: {error}" for error in validate_instance(payload, schema_dir))
        if not verify_self_sha256(payload):
            errors.append(f"effective sense self hash mismatch: {path.name}")
    frozen_by_id: dict[str, dict[str, Any]] = {}
    for path in frozen_paths:
        payload = strict_json_object(path)
        key = payload.get("candidate_key", {})
        candidate_id = str(key.get("candidate_id")) if isinstance(key, Mapping) else ""
        frozen_by_id[candidate_id] = payload
        errors.extend(f"{path.name}: {error}" for error in validate_instance(payload, schema_dir))
        if not verify_self_sha256(payload) or not verify_frozen_candidate_binding(payload):
            errors.append(f"frozen candidate binding mismatch: {path.name}")
        effective = effective_by_sense.get(str(key.get("sense_id"))) if isinstance(key, Mapping) else None
        if effective is None or key.get("effective_sense_contract_sha256") != effective["integrity"]["self_sha256"]:
            errors.append(f"frozen candidate effective-sense join mismatch: {path.name}")
    for path in constraint_paths:
        payload = strict_json_object(path)
        key = payload.get("candidate_key", {})
        candidate_id = str(key.get("candidate_id")) if isinstance(key, Mapping) else ""
        frozen = frozen_by_id.get(candidate_id)
        errors.extend(f"{path.name}: {error}" for error in validate_instance(payload, schema_dir))
        if not verify_self_sha256(payload):
            errors.append(f"constraint evidence self hash mismatch: {path.name}")
        if frozen is None or payload.get("candidate_key") != frozen.get("candidate_key"):
            errors.append(f"constraint/frozen candidate join mismatch: {path.name}")
        elif payload.get("input_contract_sha256") != frozen.get("input_contract_sha256"):
            errors.append(f"constraint input binding mismatch: {path.name}")
        if payload.get("binding_status") != "COMPLETE":
            errors.append(f"constraint binding is incomplete: {path.name}")


def _validate_reviewer_inputs(root: Path, errors: list[str]) -> None:
    source_by_candidate: dict[str, dict[str, Any]] = {}
    for reviewer_slot in ("reviewer_1", "reviewer_2"):
        try:
            payload = strict_json_object(root / f"{reviewer_slot}_full_input.json")
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append(f"{reviewer_slot}: {exc}")
            continue
        if payload.get("reviewer_slot") != reviewer_slot or payload.get("case_count") != 150:
            errors.append(f"{reviewer_slot}: identity/count mismatch")
        if payload.get("allowed_candidate_gold_labels") != list(ALLOWED_LABELS):
            errors.append(f"{reviewer_slot}: allowed labels mismatch")
        cases = payload.get("cases")
        if not isinstance(cases, list) or len(cases) != 150:
            errors.append(f"{reviewer_slot}: cases mismatch")
            continue
        source_binding = []
        seen: set[Any] = set()
        for case in cases:
            candidate_id = case.get("source_payload", {}).get("candidate_id") if isinstance(case, Mapping) else None
            if candidate_id in seen:
                errors.append(f"{reviewer_slot}: duplicate candidate case")
            seen.add(candidate_id)
            if not verify_record(case, "case_sha256"):
                errors.append(f"{reviewer_slot}: case self hash mismatch: {candidate_id}")
            if case.get("review") != _blank_review():
                errors.append(f"{reviewer_slot}: review is prefilled: {candidate_id}")
            source = case.get("source_payload")
            if not isinstance(source, Mapping) or case.get("source_payload_sha256") != sha256_bytes(
                json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
            ):
                errors.append(f"{reviewer_slot}: source payload hash mismatch: {candidate_id}")
                continue
            if _contains_forbidden(source):
                errors.append(f"{reviewer_slot}: reviewer source leaks hidden fields: {candidate_id}")
            projection = dict(source)
            projection.pop("batch_id", None)
            if reviewer_slot == "reviewer_1":
                source_by_candidate[str(candidate_id)] = projection
            elif source_by_candidate.get(str(candidate_id)) != projection:
                errors.append(f"reviewer source differs across slots: {candidate_id}")
            if case.get("provider_call_count") != 0 or case.get("final_gold_label") is not None:
                errors.append(f"{reviewer_slot}: case boundary violation: {candidate_id}")
            if case.get("final_glossary_decision") is not None:
                errors.append(f"{reviewer_slot}: final decision is not null: {candidate_id}")
            source_binding.append({"case_id": case["case_id"], "case_sha256": case["case_sha256"]})
        if payload.get("source_input_sha256") != sha256_bytes(
            json.dumps(source_binding, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        ):
            errors.append(f"{reviewer_slot}: source input binding mismatch")
        if payload.get("provider_call_count") != 0 or payload.get("final_gold_label_count") != 0:
            errors.append(f"{reviewer_slot}: top-level boundary count mismatch")
        if payload.get("final_glossary_decision") is not None:
            errors.append(f"{reviewer_slot}: top-level final decision is not null")
        zip_path = root / "handoff" / f"{reviewer_slot}.zip"
        try:
            with zipfile.ZipFile(zip_path) as archive:
                names = [info.filename for info in archive.infolist()]
                if len(names) != len(set(names)) or any(
                    name.startswith("/") or "\\" in name or ".." in Path(name).parts for name in names
                ):
                    errors.append(f"{reviewer_slot}: unsafe or duplicate handoff ZIP entry")
        except (OSError, zipfile.BadZipFile) as exc:
            errors.append(f"{reviewer_slot}: handoff ZIP: {exc}")


def validate_artifact(root: Path, *, contracts_root: Path) -> list[str]:
    errors: list[str] = []
    try:
        root = root.resolve(strict=True)
        contracts_root = contracts_root.resolve(strict=True)
        manifest = strict_json_object(root / "manifest.json")
        authority = strict_json_object(root / "authority_binding.json")
        selection = strict_json_object(root / "selection_report.json")
        statistics = strict_json_object(root / "dataset_statistics.json")
        lineage = strict_json_object(root / "lineage.json")
    except (OSError, UnicodeError, ValueError) as exc:
        return [str(exc)]
    if manifest.get("artifact_name") != ARTIFACT_NAME or manifest.get("status") != STATUS:
        errors.append("manifest identity/status mismatch")
    if manifest.get("policy_id") != FINAL_POLICY_ID or manifest.get("stage_b_policy_id") != STAGE_B_POLICY_ID:
        errors.append("manifest policy mismatch")
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        errors.append("manifest self hash mismatch")
    if manifest.get("files") != build_file_inventory(root, {"manifest.json", "CHECKSUMS.sha256"}):
        errors.append("manifest file inventory mismatch")
    expected_counts = {
        "term_sense": 50,
        "candidate": 150,
        "effective_sense_contract": 50,
        "frozen_candidate_contract": 150,
        "constraint_evidence_package": 150,
        "reviewer_case_per_reviewer": 150,
        "reviewer_count": 2,
        "batch": 5,
        "stage_b_gold_autofill": 0,
    }
    counts = manifest.get("counts")
    if not isinstance(counts, Mapping) or any(counts.get(key) != value for key, value in expected_counts.items()):
        errors.append("manifest core counts mismatch")
    if manifest.get("split_counts") != {"development": 30, "test": 10, "validation": 10}:
        errors.append("manifest split counts mismatch")
    if manifest.get("provider_call_count") != 0 or manifest.get("final_gold_label_count") != 0:
        errors.append("manifest boundary counts mismatch")
    if manifest.get("final_glossary_decision") is not None:
        errors.append("manifest final decision must be null")
    if authority.get("authority_tag") != CONTRACT_TAG or authority.get("authority_commit") != CONTRACT_COMMIT:
        errors.append("contract authority tag/commit mismatch")
    if authority.get("contract_manifest_sha256") != CONTRACT_MANIFEST_SHA256:
        errors.append("contract authority manifest mismatch")
    for name, value in (("selection", selection), ("statistics", statistics), ("lineage", lineage)):
        if not verify_integrity(value):
            errors.append(f"{name} report self hash mismatch")
    senses, candidates, _ = _validate_materialized(root, errors)
    _validate_contracts(root, contracts_root, senses, candidates, errors)
    _validate_reviewer_inputs(root, errors)
    try:
        gold = strict_jsonl(root / "stage_b_gold_150_template.jsonl")
        adjudication = strict_jsonl(root / "stage_b_adjudication_150_template.jsonl")
        if len(gold) != 150 or any(row.get("final_gold_label") is not None for row in gold):
            errors.append("Stage B gold template is prefilled or incomplete")
        if len(adjudication) != 150 or any(row.get("adjudicator_label") is not None for row in adjudication):
            errors.append("Stage B adjudication template is prefilled or incomplete")
    except (OSError, UnicodeError, ValueError) as exc:
        errors.append(f"Stage B templates: {exc}")
    _validate_checksums(root, errors)
    return errors


def validate_zip(zip_path: Path, artifact_root: Path) -> list[str]:
    expected = {
        path.relative_to(artifact_root).as_posix(): sha256_file(path)
        for path in artifact_root.rglob("*")
        if path.is_file()
    }
    errors: list[str] = []
    try:
        with zipfile.ZipFile(zip_path) as archive:
            infos = archive.infolist()
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                errors.append("release ZIP contains duplicate entries")
            if any(name.startswith("/") or "\\" in name or ".." in Path(name).parts for name in names):
                errors.append("release ZIP contains an unsafe path")
            actual = {info.filename: sha256_bytes(archive.read(info)) for info in infos}
            if actual != expected:
                errors.append("release ZIP differs from artifact directory")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"release ZIP: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    parser.add_argument("--contracts-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path)
    args = parser.parse_args()
    errors = validate_artifact(args.artifact_root, contracts_root=args.contracts_root)
    if args.zip_path is not None:
        errors.extend(validate_zip(args.zip_path.resolve(strict=True), args.artifact_root.resolve(strict=True)))
    print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
