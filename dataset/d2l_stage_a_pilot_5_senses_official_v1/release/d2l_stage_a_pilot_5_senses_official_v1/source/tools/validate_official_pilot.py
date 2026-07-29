from __future__ import annotations

import argparse
import csv
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

try:
    from .common import (
        build_file_inventory,
        canonical_json_bytes,
        read_csv,
        sha256_bytes,
        sha256_file,
        strict_json_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        build_file_inventory,
        canonical_json_bytes,
        read_csv,
        sha256_bytes,
        sha256_file,
        strict_json_file,
        strict_json_object,
        strict_jsonl,
        verify_integrity,
        verify_record,
    )


EXPECTED_SENSE_IDS = {
    "d2lce_11e1c294000ac67785408dcd",
    "d2lce_c6b4477a845e2e0e0e02f088",
    "d2lce_1a91fdded89249a5cd89ec14",
    "d2lce_cc4cb853eff638abcbdf7691",
    "d2lce_382e4bbab285d56a08249753",
}
EXPECTED_TERMS = {
    "null hypothesis",
    "output gate",
    "Jupyter notebook",
    "learning rate",
    "contexts",
}
EXPECTED_ROSTER_IDS = {"diemphuong", "reviewer_2", "snail"}


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _load_contract_validation(contracts_root: Path) -> tuple[Any, Any, Any]:
    package_root = contracts_root / "python"
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    from terminology_contracts.bindings import verify_frozen_candidate_binding  # type: ignore
    from terminology_contracts.canonical import verify_self_sha256  # type: ignore
    from terminology_contracts.validation import validate_instance  # type: ignore

    return validate_instance, verify_self_sha256, verify_frozen_candidate_binding


def _validate_manifest(root: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        manifest = strict_json_object(root / "manifest.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"manifest: {exc}")
        return None
    if manifest.get("manifest_sha256") != _manifest_self_hash(manifest):
        errors.append("manifest self hash mismatch")
    if manifest.get("status") != "READY_FOR_REAL_PILOT_REVIEW":
        errors.append("manifest status is not READY_FOR_REAL_PILOT_REVIEW")
    declared = manifest.get("files")
    if not isinstance(declared, Mapping):
        errors.append("manifest files map is missing")
        return manifest
    actual = build_file_inventory(root, {"manifest.json", "CHECKSUMS.sha256"})
    if dict(declared) != actual:
        errors.append("manifest file inventory differs from artifact bytes")
    return manifest


def _validate_checksums(root: Path, errors: list[str]) -> None:
    path = root / "CHECKSUMS.sha256"
    try:
        lines = path.read_text(encoding="ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        errors.append(f"CHECKSUMS: {exc}")
        return
    declared: dict[str, str] = {}
    for line_number, line in enumerate(lines, start=1):
        if " *" not in line:
            errors.append(f"CHECKSUMS:{line_number}: malformed record")
            continue
        digest, relative = line.split(" *", 1)
        if relative in declared:
            errors.append(f"CHECKSUMS duplicate path: {relative}")
        declared[relative] = digest
    expected = {
        relative: metadata["sha256"]
        for relative, metadata in build_file_inventory(
            root, {"CHECKSUMS.sha256"}
        ).items()
    }
    if declared != expected:
        errors.append("CHECKSUMS file set or hashes differ from artifact bytes")
    if list(declared) != sorted(declared):
        errors.append("CHECKSUMS paths are not in canonical POSIX code-point order")


def _validate_json_surface(root: Path, errors: list[str]) -> None:
    for path in sorted(root.rglob("*.json"), key=lambda item: item.relative_to(root).as_posix()):
        try:
            strict_json_file(path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"strict JSON failure {path.relative_to(root).as_posix()}: {exc}")
    for path in sorted(root.rglob("*.jsonl"), key=lambda item: item.relative_to(root).as_posix()):
        try:
            strict_jsonl(path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"strict JSONL failure {path.relative_to(root).as_posix()}: {exc}")


def _validate_roster(root: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        roster = strict_json_object(root / "reviewer_roster_attestation_v1.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"roster: {exc}")
        return None
    if not verify_integrity(roster):
        errors.append("reviewer roster self hash mismatch")
    if roster.get("status") != "ACCEPTED":
        errors.append("reviewer roster is not accepted")
    reviewers = roster.get("reviewers")
    if not isinstance(reviewers, list) or len(reviewers) != 3:
        errors.append("reviewer roster must contain exactly three reviewers")
        return roster
    ids = [row.get("reviewer_id") for row in reviewers if isinstance(row, Mapping)]
    if set(ids) != EXPECTED_ROSTER_IDS or len(ids) != len(set(ids)):
        errors.append("reviewer roster pseudonyms are missing or not distinct")
    if any(row.get("reviewer_type") != "HUMAN" for row in reviewers):
        errors.append("reviewer roster contains a non-human reviewer")
    if roster.get("distinct_person_assertion") is not True:
        errors.append("distinct-person assertion is missing")
    maintainer = roster.get("maintainer_attestation")
    if not isinstance(maintainer, Mapping) or maintainer.get("assertion_basis") != "OWNER_CONFIRMED_IN_PROJECT_TASK":
        errors.append("owner/maintainer attestation is missing")
    return roster


def _validate_blind_and_companion(
    root: Path, roster: Mapping[str, Any] | None, errors: list[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        blind = strict_jsonl(root / "blind_audit_records_3.jsonl")
        companion = strict_jsonl(root / "updated_reviewed_stage_a_companion_15.jsonl")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"blind/companion: {exc}")
        return [], []
    if len(blind) != 3:
        errors.append("blind audit record count must be 3")
    blind_by_id = {}
    for row in blind:
        if not verify_record(row, "blind_audit_record_sha256"):
            errors.append(f"blind record self hash mismatch: {row.get('sense_id')}")
        if row.get("split_decision") != "NO_SPLIT":
            errors.append(f"blind split conflict: {row.get('sense_id')}")
        if row.get("definition_compatibility") not in {"SAME", "COMPATIBLE"}:
            errors.append(f"blind definition conflict: {row.get('sense_id')}")
        if row.get("semantic_binding_status") != "PASS":
            errors.append(f"blind semantic binding failed: {row.get('sense_id')}")
        blind_by_id[row.get("sense_id")] = row
    if len(companion) != 15:
        errors.append("reviewed Stage A companion count must be 15")
    roster_hash = roster.get("integrity", {}).get("self_sha256") if roster else None
    for row in companion:
        if not verify_record(row, "companion_record_sha256"):
            errors.append(f"companion self hash mismatch: {row.get('sense_id')}")
        if row.get("reviewer_roster_attestation_sha256") != roster_hash:
            errors.append(f"companion roster binding mismatch: {row.get('sense_id')}")
        for field in (
            "positive_definition_evidence_ids",
            "positive_pos_evidence_ids",
            "boundary_context_ids",
            "review_provenance_refs",
        ):
            if not isinstance(row.get(field), list) or not row.get(field):
                errors.append(f"companion omits {field}: {row.get('sense_id')}")
        if set(row.get("positive_definition_evidence_ids", [])).intersection(
            row.get("boundary_context_ids", [])
        ):
            errors.append(f"definition/boundary evidence overlap: {row.get('sense_id')}")
        if set(row.get("positive_pos_evidence_ids", [])).intersection(
            row.get("boundary_context_ids", [])
        ):
            errors.append(f"POS/boundary evidence overlap: {row.get('sense_id')}")
        if row.get("risk_class") == "R0_CLEAR":
            blind_ref = row.get("blind_audit_ref")
            blind_row = blind_by_id.get(row.get("sense_id"))
            if not isinstance(blind_ref, Mapping) or blind_row is None:
                errors.append(f"R0 companion lacks blind ref: {row.get('sense_id')}")
            elif blind_ref.get("blind_audit_record_sha256") != blind_row.get(
                "blind_audit_record_sha256"
            ):
                errors.append(f"R0 blind hash binding mismatch: {row.get('sense_id')}")
        expected_eligibility = (
            "ELIGIBLE"
            if row.get("resolution_status") == "READY_FOR_CONTRACT_CONSTRUCTION"
            else "BLOCKED_BY_STAGE_A"
        )
        if row.get("stage_b_eligibility") != expected_eligibility:
            errors.append(f"companion eligibility mismatch: {row.get('sense_id')}")
        if row.get("final_glossary_decision") is not None:
            errors.append(f"companion contains final decision: {row.get('sense_id')}")
    return blind, companion


def _validate_stage_b(
    root: Path, companion: list[Mapping[str, Any]], errors: list[str]
) -> None:
    try:
        rows = read_csv(root / "stage_b_template_45.csv")
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        errors.append(f"Stage B template: {exc}")
        return
    if len(rows) != 45:
        errors.append("Stage B row count must be 45")
    counts = Counter(row.get("stage_b_eligibility") for row in rows)
    if counts != Counter({"ELIGIBLE": 33, "BLOCKED_BY_STAGE_A": 12}):
        errors.append(f"Stage B eligibility must be 33/12, got {dict(counts)}")
    statuses = {row["sense_id"]: row["stage_b_eligibility"] for row in companion}
    for row in rows:
        if row.get("stage_b_eligibility") != statuses.get(row.get("sense_id")):
            errors.append(f"Stage B/companion eligibility mismatch: {row.get('candidate_id')}")
        for field in (
            "candidate_gold_label",
            "allowed_scope",
            "validated_variants",
            "rejected_variants",
            "reason_codes",
            "positive_context_refs",
            "vietnamese_evidence_refs",
            "reviewer_provenance_ref",
            "adjudication_ref",
        ):
            if row.get(field, "") != "":
                errors.append(f"Stage B gold/review field is prefilled: {row.get('candidate_id')}:{field}")
    try:
        report = strict_json_object(root / "stage_b_eligibility_report.json")
        if not verify_integrity(report):
            errors.append("Stage B eligibility report self hash mismatch")
        if report.get("eligibility_counts") != {
            "BLOCKED_BY_STAGE_A": 12,
            "ELIGIBLE": 33,
        }:
            errors.append("Stage B eligibility report count mismatch")
        if report.get("stage_b_gold_autofill_count") != 0:
            errors.append("Stage B report claims gold autofill")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"Stage B eligibility report: {exc}")


def _validate_contracts(root: Path, contracts_root: Path, errors: list[str]) -> None:
    validate_instance, verify_self_sha256, verify_frozen_binding = _load_contract_validation(
        contracts_root
    )
    schema_dir = contracts_root / "schemas" / "v1.1.0"
    effective_paths = sorted((root / "effective_sense_contracts_5").glob("*.json"))
    frozen_paths = sorted((root / "frozen_candidate_contracts_15").glob("*.json"))
    constraint_paths = sorted((root / "constraint_evidence_packages_15").glob("*.json"))
    if (len(effective_paths), len(frozen_paths), len(constraint_paths)) != (5, 15, 15):
        errors.append("official contract file counts must be exactly 5/15/15")
        return
    effective_by_hash: dict[str, dict[str, Any]] = {}
    frozen_by_id: dict[str, dict[str, Any]] = {}
    constraints_by_id: dict[str, dict[str, Any]] = {}
    for path in effective_paths + frozen_paths + constraint_paths:
        try:
            payload = strict_json_object(path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"contract {path.name}: {exc}")
            continue
        contract_errors = validate_instance(payload, schema_dir)
        errors.extend(f"{path.name}: {error}" for error in contract_errors)
        if not verify_self_sha256(payload):
            errors.append(f"{path.name}: authority self hash mismatch")
        schema_id = payload.get("schema_id")
        if schema_id == "EffectiveSenseContractV1":
            effective_by_hash[payload["integrity"]["self_sha256"]] = payload
        elif schema_id == "FrozenCandidateContractV1":
            candidate_id = payload["candidate_key"]["candidate_id"]
            frozen_by_id[candidate_id] = payload
            if payload.get("binding_status") != "COMPLETE" or not verify_frozen_binding(payload):
                errors.append(f"{path.name}: Frozen Candidate is not COMPLETE/bound")
        elif schema_id == "ConstraintEvidencePackageV1":
            candidate_id = payload["candidate_key"]["candidate_id"]
            constraints_by_id[candidate_id] = payload
            if payload.get("binding_status") != "COMPLETE":
                errors.append(f"{path.name}: Constraint package is not COMPLETE")

    if len(effective_by_hash) != 5 or len(frozen_by_id) != 15 or len(constraints_by_id) != 15:
        errors.append("contract identities are not unique")
    materialized_candidates = {
        row["candidate_instance_id"]: row
        for row in strict_jsonl(root / "materialized_input" / "candidate_instances_15.jsonl")
    }
    review_bindings = {
        path.stem: strict_json_object(path)
        for path in (root / "review_bindings_5").glob("*.json")
    }
    if len(review_bindings) != 5:
        errors.append("review binding count must be 5")
    for sense_id, binding in review_bindings.items():
        if not verify_integrity(binding):
            errors.append(f"review binding self hash mismatch: {sense_id}")
        for field in (
            "positive_definition_evidence_ids",
            "positive_pos_evidence_ids",
            "boundary_context_ids",
            "review_provenance_refs",
        ):
            if not binding.get(field):
                errors.append(f"review binding omits {field}: {sense_id}")
    for candidate_id, frozen in frozen_by_id.items():
        constraint = constraints_by_id.get(candidate_id)
        source = materialized_candidates.get(candidate_id)
        key = frozen["candidate_key"]
        effective = effective_by_hash.get(key["effective_sense_contract_sha256"])
        if constraint is None or source is None or effective is None:
            errors.append(f"contract join is incomplete: {candidate_id}")
            continue
        if key.get("candidate_version") != source.get("candidate_instance_sha256"):
            errors.append(f"candidate version drift: {candidate_id}")
        if key.get("candidate_vi") != source.get("candidate_target_vi"):
            errors.append(f"candidate text drift: {candidate_id}")
        if key.get("dataset_manifest_sha256") != "258ebe5d907a0a108a1b80a1ec1aad3c6e265ed1a8edbd5701cc128e273122ce":
            errors.append(f"dataset authority mismatch: {candidate_id}")
        if constraint.get("candidate_key") != key:
            errors.append(f"constraint candidate key mismatch: {candidate_id}")
        if constraint.get("input_contract_sha256") != frozen.get("input_contract_sha256"):
            errors.append(f"constraint input binding mismatch: {candidate_id}")
        if constraint.get("sense_review", {}).get("effective_sense_contract_sha256") != effective.get(
            "integrity", {}
        ).get("self_sha256"):
            errors.append(f"constraint effective-sense binding mismatch: {candidate_id}")
        binding = review_bindings.get(effective["sense_id"])
        binding_hash = binding.get("integrity", {}).get("self_sha256") if binding else None
        if effective.get("review_artifact_sha256") != binding_hash:
            errors.append(f"effective/review binding mismatch: {candidate_id}")
        review_ref = constraint.get("sense_review", {}).get("review_artifact_ref", {})
        if review_ref.get("sha256") != binding_hash:
            errors.append(f"constraint/review binding mismatch: {candidate_id}")
        if constraint.get("target_collision", {}).get("status") != "UNJUDGEABLE":
            errors.append(f"target collision must remain UNJUDGEABLE: {candidate_id}")


def _validate_selection_and_gate(root: Path, errors: list[str]) -> None:
    try:
        selection = strict_json_object(root / "integration_pilot_5_sense_selection_receipt.json")
        gate = strict_json_object(root / "acceptance_gate_report.json")
        index = strict_json_object(root / "candidate_index_15.json")
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        errors.append(f"selection/gate/index: {exc}")
        return
    for name, payload in (("selection", selection), ("gate", gate), ("index", index)):
        if not verify_integrity(payload):
            errors.append(f"{name} self hash mismatch")
    records = selection.get("records", [])
    if {row.get("sense_id") for row in records if isinstance(row, Mapping)} != EXPECTED_SENSE_IDS:
        errors.append("selection receipt sense IDs differ from exact five")
    if {row.get("source_term") for row in records if isinstance(row, Mapping)} != EXPECTED_TERMS:
        errors.append("selection receipt terms differ from exact five")
    if Counter(row.get("selection_group") for row in records) != Counter(
        {"CLEAR_LOW_RISK": 2, "AMBIGUOUS_POLYSEMOUS": 2, "GATE_ADJUDICATION_RISK": 1}
    ):
        errors.append("selection receipt distribution is not 2/2/1")
    if gate.get("status") != "READY_FOR_REAL_PILOT_REVIEW":
        errors.append("acceptance gate status is not ready")
    if not isinstance(gate.get("checks"), Mapping) or not all(gate["checks"].values()):
        errors.append("acceptance gate contains a failed check")
    if gate.get("official_contract_counts") != {
        "ConstraintEvidencePackageV1": 15,
        "EffectiveSenseContractV1": 5,
        "FrozenCandidateContractV1": 15,
    }:
        errors.append("acceptance gate contract counts differ from 5/15/15")
    for payload_name, payload in (("selection", selection), ("gate", gate), ("index", index)):
        if payload.get("final_glossary_decision") is not None:
            errors.append(f"{payload_name} contains a final glossary decision")
    if gate.get("provider_call_count") != 0 or gate.get("stage_b_gold_autofill_count") != 0:
        errors.append("acceptance gate violates zero-provider/zero-gold boundary")
    if index.get("candidate_count") != 15 or len(index.get("entries", [])) != 15:
        errors.append("candidate index count must be 15")


def _validate_lineage_layout(root: Path, errors: list[str]) -> None:
    if (root / "source_dataset").exists():
        errors.append("legacy nested source_dataset layout is forbidden")
    if list((root / "lineage").glob("**/CHECKSUMS.sha256")):
        errors.append("reference-only lineage cannot contain active CHECKSUMS")
    expected = {
        "parent_dataset_v3_reference.json",
        "parent_reviewed_15_reference.json",
        "parent_p0_reference.json",
    }
    actual = {path.name for path in (root / "lineage").glob("*.json")}
    if actual != expected:
        errors.append("reference-only parent receipt set mismatch")
    for path in (root / "lineage").glob("*.json"):
        payload = strict_json_object(path)
        if not verify_integrity(payload):
            errors.append(f"parent reference self hash mismatch: {path.name}")
        if payload.get("reference_only") is not True or payload.get("materialized_package") is not False:
            errors.append(f"parent reference layout ambiguity: {path.name}")
        if payload.get("original_checksums_file_copied") is not False:
            errors.append(f"parent reference claims copied checksum: {path.name}")


def validate_artifact(root: Path, contracts_root: Path) -> list[str]:
    errors: list[str] = []
    root = root.resolve(strict=True)
    contracts_root = contracts_root.resolve(strict=True)
    _validate_manifest(root, errors)
    _validate_checksums(root, errors)
    _validate_json_surface(root, errors)
    roster = _validate_roster(root, errors)
    _, companion = _validate_blind_and_companion(root, roster, errors)
    _validate_stage_b(root, companion, errors)
    _validate_contracts(root, contracts_root, errors)
    _validate_selection_and_gate(root, errors)
    _validate_lineage_layout(root, errors)
    if not (root / "junit.xml").is_file():
        errors.append("junit.xml is missing")
    environment = strict_json_object(root / "environment.json")
    if environment.get("network_calls") != 0 or environment.get("provider_calls") != 0:
        errors.append("environment reports network/provider calls")
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
    parser.add_argument("--contracts-root", type=Path, required=True)
    parser.add_argument("--zip-path", type=Path)
    args = parser.parse_args()
    errors = validate_artifact(args.artifact_root, args.contracts_root)
    if args.zip_path is not None:
        errors.extend(validate_zip(args.zip_path.resolve(strict=True), args.artifact_root.resolve(strict=True)))
    result = {
        "status": "PASS" if not errors else "FAIL",
        "error_count": len(errors),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
