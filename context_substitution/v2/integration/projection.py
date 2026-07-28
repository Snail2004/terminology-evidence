from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from context_substitution.v2.contracts.common import REQUIRED_SAME_SENSE_CONTEXT_TYPES
from context_substitution.v2.contracts.run import validate_context_substitution_run
from context_substitution.v2.evidence.provenance import candidate_provider_provenances
from context_substitution.v2.integration.authority import (
    AUTHORITY_COMMIT,
    AUTHORITY_TAG,
    CONTRACT_MANIFEST_SHA256,
    canonical_sha256,
    seal_official_contract,
    validate_authority,
    validate_official_contract,
    verify_frozen_candidate_binding,
)
from context_substitution.v2.integration.common import (
    file_sha256,
    seal_object,
    write_json,
)
from context_substitution.v2.runtime.aggregation import compute_context_result


PACKAGE_SET_SCHEMA_ID = "ContextEvidencePackageSetManifestC1"
PACKAGE_SET_SCHEMA_VERSION = "1.0.0"
PACKAGE_SET_HOLD_STATUS = "GLOBAL_VALIDATOR_NOT_AVAILABLE_HOLD"
COMPONENT_VERSION = "2.2.0"

_GATE_MAP = {
    "concept_mismatch": {
        "SEMANTIC_EQUIVALENCE_LTE_2",
        "DOMAIN_SENSE_FIT_ZERO",
        "CONTEXT_SEMANTIC_MISMATCH",
    },
    "wrong_sense": {"WRONG_SENSE", "CONTEXT_WRONG_SENSE"},
    "contradiction": {"SEMANTIC_CONTRADICTION", "CONTEXT_CONTRADICTION"},
    "judge_disagreement": {"JUDGE_DISAGREEMENT"},
    "insufficient_evidence": {
        "INSUFFICIENT_VALID_SAME_SENSE_CONTEXTS",
        "CONTEXT_EVIDENCE_INSUFFICIENT",
    },
    "missing_contrastive_context": {"MISSING_CONTRASTIVE_CONTEXT"},
    "incomplete_context_type_coverage": {"INCOMPLETE_CONTEXT_TYPE_COVERAGE"},
}
_GATE_ORDER = tuple(_GATE_MAP)


def build_projection_binding_from_ledger(
    *, run_payload: Mapping[str, Any], ledger_path: Path
) -> dict[str, Any]:
    run = validate_context_substitution_run(run_payload)
    path = Path(ledger_path).resolve()
    attempts = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("record_kind") == "PROVIDER_ATTEMPT":
            attempts.append(row)
    if not attempts:
        raise ValueError("provider ledger has no attempt rows")
    run_ids = {row.get("run_id") for row in attempts}
    if len(run_ids) != 1 or not isinstance(next(iter(run_ids)), str):
        raise ValueError("provider ledger must bind exactly one run_id")
    ledger_sha = file_sha256(path)
    return {
        "run_id": next(iter(run_ids)),
        "run_spec_id": "cst-v2.2:" + run["input_sha256"][:24],
        "started_at": min(str(row["started_at"]) for row in attempts),
        "completed_at": max(str(row["completed_at"]) for row in attempts),
        "raw_ledger_ref": {
            "evidence_id": "ledger_" + ledger_sha[:24],
            "evidence_type": "OTHER",
            "uri": f"artifact://ledger/{ledger_sha}/provider_attempts.jsonl",
            "sha256": ledger_sha,
        },
        "authority_tag": AUTHORITY_TAG,
        "authority_commit": AUTHORITY_COMMIT,
        "contract_manifest_sha256": CONTRACT_MANIFEST_SHA256,
    }


def project_context_evidence_packages(
    *,
    run_payload: Mapping[str, Any],
    frozen_candidates: Sequence[Mapping[str, Any]],
    binding: Mapping[str, Any],
) -> list[dict[str, Any]]:
    validate_authority()
    run = validate_context_substitution_run(run_payload)
    normalized_binding = _validate_binding(binding)
    frozen_by_id = _validate_frozen_candidates(run, frozen_candidates)
    packages = [
        _project_candidate(
            run,
            candidate,
            frozen=frozen_by_id[candidate["candidate_id"]],
            binding=normalized_binding,
        )
        for candidate in run["candidates"]
    ]
    return sorted(packages, key=lambda row: row["candidate_key"]["candidate_id"])


def write_context_evidence_package_set(
    *,
    run_payload: Mapping[str, Any],
    frozen_candidates: Sequence[Mapping[str, Any]],
    binding: Mapping[str, Any],
    output_directory: Path,
) -> dict[str, Any]:
    target = Path(output_directory).resolve()
    if target.exists() and any(target.iterdir()):
        raise ValueError("Context Evidence output directory must be empty")
    target.mkdir(parents=True, exist_ok=True)
    run = validate_context_substitution_run(run_payload)
    packages = project_context_evidence_packages(
        run_payload=run,
        frozen_candidates=frozen_candidates,
        binding=binding,
    )
    entries = []
    package_directory = target / "packages"
    package_directory.mkdir()
    for index, package in enumerate(packages, 1):
        candidate_id = package["candidate_key"]["candidate_id"]
        name = f"{index:03d}_{canonical_sha256(candidate_id)[:16]}.json"
        path = package_directory / name
        write_json(path, package)
        entries.append(
            {
                "candidate_key": package["candidate_key"],
                "input_contract_sha256": package["input_contract_sha256"],
                "path": f"packages/{name}",
                "package_self_sha256": package["integrity"]["self_sha256"],
                "physical_sha256": file_sha256(path),
            }
        )
    manifest = {
        "schema_id": PACKAGE_SET_SCHEMA_ID,
        "schema_version": PACKAGE_SET_SCHEMA_VERSION,
        "status": PACKAGE_SET_HOLD_STATUS,
        "authority_tag": AUTHORITY_TAG,
        "authority_commit": AUTHORITY_COMMIT,
        "contract_manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "source_run_sha256": run["integrity"]["run_sha256"],
        "package_count": len(entries),
        "packages": entries,
        "projection_provider_call_count": 0,
        "source_run_provider_attempt_count": len(run["provider_attempts"]),
        "final_glossary_decision": None,
        "global_gate_action": None,
        "integrity": {},
    }
    manifest = seal_object(manifest, integrity_key="manifest_sha256")
    write_json(target / "manifest.json", manifest)
    return manifest


def _project_candidate(
    run: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    frozen: Mapping[str, Any],
    binding: Mapping[str, Any],
) -> dict[str, Any]:
    if candidate["final_glossary_decision"] is not None:
        raise ValueError("Context Substitution cannot emit a final glossary decision")
    support = _support_set(candidate)
    gate_signals, flags = _gate_signals(candidate, support)
    package = {
        "schema_id": "ContextEvidencePackageV1",
        "schema_version": "1.1.0",
        "candidate_key": frozen["candidate_key"],
        "input_contract_sha256": frozen["input_contract_sha256"],
        "selector_mode": run["execution_policy"]["selector_mode"],
        "review_artifact_sha256": run["execution_policy"]["review_artifact_sha256"],
        "features": _features(candidate),
        "contrastive_status": _contrastive_status(candidate),
        "flags": flags,
        "local_status": candidate["contextual_evidence"]["status"],
        "support_set": support,
        "provenance": _provenance(run, candidate, binding=binding),
        "final_glossary_decision": None,
        "gate_signals": gate_signals,
        "diagnostics": None,
        "integrity": {},
    }
    return validate_official_contract(seal_official_contract(package))


def _validate_binding(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "run_id",
        "run_spec_id",
        "started_at",
        "completed_at",
        "raw_ledger_ref",
        "authority_tag",
        "authority_commit",
        "contract_manifest_sha256",
    }
    if set(value) != required:
        raise ValueError("projection binding fields differ from the sealed contract")
    if value["authority_tag"] != AUTHORITY_TAG:
        raise ValueError("projection authority tag mismatch")
    if value["authority_commit"] != AUTHORITY_COMMIT:
        raise ValueError("projection authority commit mismatch")
    if value["contract_manifest_sha256"] != CONTRACT_MANIFEST_SHA256:
        raise ValueError("projection contract manifest mismatch")
    for key in ("run_id", "run_spec_id", "started_at", "completed_at"):
        if not isinstance(value[key], str) or not value[key]:
            raise ValueError(f"projection binding {key} is required")
    ledger = value["raw_ledger_ref"]
    if not isinstance(ledger, Mapping) or set(ledger) != {
        "evidence_id",
        "evidence_type",
        "uri",
        "sha256",
    }:
        raise ValueError("projection raw ledger reference is invalid")
    return dict(value)


def _validate_frozen_candidates(
    run: Mapping[str, Any], values: Sequence[Mapping[str, Any]]
) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for value in values:
        frozen = validate_official_contract(value)
        if frozen["schema_id"] != "FrozenCandidateContractV1":
            raise ValueError("projection input must contain FrozenCandidateContractV1")
        if not verify_frozen_candidate_binding(frozen):
            raise ValueError("Frozen Candidate input_contract_sha256 mismatch")
        candidate_id = frozen["candidate_key"]["candidate_id"]
        if candidate_id in by_id:
            raise ValueError(f"duplicate Frozen Candidate: {candidate_id}")
        by_id[candidate_id] = frozen
    expected = {row["candidate_id"] for row in run["candidates"]}
    if set(by_id) != expected:
        raise ValueError("Frozen Candidate set does not exactly cover the C run")
    for candidate in run["candidates"]:
        _validate_candidate_join(
            candidate,
            by_id[candidate["candidate_id"]],
            execution_policy=run["execution_policy"],
        )
    return by_id


def _validate_candidate_join(
    candidate: Mapping[str, Any],
    frozen: Mapping[str, Any],
    *,
    execution_policy: Mapping[str, Any],
) -> None:
    key = frozen["candidate_key"]
    expected = {
        "candidate_id": candidate["candidate_id"],
        "candidate_version": candidate["candidate_generation"]["candidate_version"],
        "source_term": candidate["source_term"],
        "candidate_vi": candidate["candidate_translation"],
        "sense_id": candidate["sense_id"],
        "scope_id": candidate["scope_id"],
        "sense_inventory_version": candidate["sense_contract"]["sense_inventory_version"],
        "dataset_manifest_sha256": execution_policy["dataset_manifest_sha256"],
    }
    for name, expected_value in expected.items():
        if key[name] != expected_value:
            raise ValueError(f"Frozen Candidate {name} differs from C run")
    sealed_sense = execution_policy["effective_sense_contract_sha256"]
    if sealed_sense is not None and key["effective_sense_contract_sha256"] != sealed_sense:
        raise ValueError("Frozen Candidate effective sense binding differs from C run")


def _features(candidate: Mapping[str, Any]) -> dict[str, Any]:
    evidence = candidate["contextual_evidence"]
    scores = [int(value) for value in evidence["raw_context_scores"]]
    c_min = min(scores) / 10 if scores else 0.0
    c_max = max(scores) / 10 if scores else 0.0
    valid = int(evidence["valid_context_count"])
    invalid = int(evidence["invalid_context_count"])
    total = valid + invalid
    missing = len(candidate["missing_same_sense_context_types"])
    required_total = len(REQUIRED_SAME_SENSE_CONTEXT_TYPES)
    return {
        "C_mean": float(evidence["C"] if evidence["C"] is not None else 0.0),
        "C_min": c_min,
        "C_max": c_max,
        "C_range": c_max - c_min,
        "evidence_coverage": valid / total if total else 0.0,
        "required_context_type_coverage": (required_total - missing) / required_total,
        "judge_agreement": _judge_agreement(candidate["context_results"]),
        "valid_context_count": valid,
        "pass_count": int(evidence["pass_count"]),
        "minor_count": int(evidence["minor_count"]),
        "fail_count": int(evidence["fail_count"]),
    }


def _judge_agreement(rows: Sequence[Mapping[str, Any]]) -> float | None:
    pairs = [row for row in rows if row["secondary_judge"] is not None]
    if not pairs:
        return None
    agreed = 0
    for row in pairs:
        primary = compute_context_result(row["primary_judge"]["output"])[1]
        secondary = compute_context_result(row["secondary_judge"]["output"])[1]
        agreed += primary == secondary
    return agreed / len(pairs)


def _contrastive_status(candidate: Mapping[str, Any]) -> str:
    if not candidate["selected_contrastive_context_ids"]:
        return "ABSENT"
    results = candidate["contrastive_results"]
    if not results:
        return "UNJUDGEABLE"
    if any(row["result"] == "SEPARATE_SENSE_REQUIRED" for row in results):
        return "SENSE_BOUNDARY_DETECTED"
    return "AVAILABLE"


def _support_set(candidate: Mapping[str, Any]) -> dict[str, Any]:
    support = candidate["certificate_support_set"]
    return {
        "positive_support_refs": _refs(
            support.get("positive_support_contexts", ()), evidence_type="CONTEXT"
        ),
        "negative_or_boundary_refs": _refs(
            support.get("negative_or_boundary_contexts", ()), evidence_type="CONTEXT"
        ),
        "contrastive_refs": _refs(
            support.get("contrastive_contexts", ()),
            evidence_type="CONTRASTIVE_CONTEXT",
        ),
    }


def _refs(
    rows: Iterable[Mapping[str, Any]], *, evidence_type: str
) -> list[dict[str, str]]:
    result = []
    for row in rows:
        context_id = str(row["context_id"])
        source_sha = row.get("source_sha256") or row["source_provenance"]["source_hash"]
        result.append(
            {
                "evidence_id": context_id,
                "evidence_type": evidence_type,
                "uri": f"artifact://context/{context_id}",
                "sha256": str(source_sha),
            }
        )
    return sorted(result, key=lambda row: row["evidence_id"])


def _gate_signals(
    candidate: Mapping[str, Any], support: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    original_flags = {
        str(flag)
        for flag in candidate["context_flags"]
    } | {
        str(flag)
        for row in candidate["context_results"]
        for flag in row["local_hard_flags"]
    }
    all_refs = _all_evidence_refs(candidate, support)
    signals = []
    flags = []
    for gate_id in _GATE_ORDER:
        reasons = sorted(original_flags & _GATE_MAP[gate_id])
        if gate_id == "missing_contrastive_context" and not candidate[
            "selected_contrastive_context_ids"
        ]:
            reasons = reasons or ["MISSING_CONTRASTIVE_CONTEXT"]
        if gate_id == "incomplete_context_type_coverage" and candidate[
            "missing_same_sense_context_types"
        ]:
            reasons = reasons or ["INCOMPLETE_CONTEXT_TYPE_COVERAGE"]
        asserted = bool(reasons)
        evidence_refs = all_refs if asserted else []
        signals.append(
            {
                "gate_id": gate_id,
                "asserted": asserted,
                "reason_codes": reasons,
                "evidence_refs": evidence_refs,
            }
        )
        if asserted:
            flags.append(
                {
                    "code": gate_id,
                    "severity": _gate_severity(gate_id),
                    "message": ", ".join(reasons),
                    "evidence_refs": evidence_refs,
                }
            )
    return signals, flags


def _all_evidence_refs(
    candidate: Mapping[str, Any], support: Mapping[str, Any]
) -> list[dict[str, str]]:
    values = {
        row["evidence_id"]: row
        for group in support.values()
        for row in group
    }
    for row in candidate["excluded_contexts"]:
        ref = _refs((row,), evidence_type="CONTEXT")[0]
        values[ref["evidence_id"]] = ref
    return [values[key] for key in sorted(values)]


def _gate_severity(gate_id: str) -> str:
    if gate_id in {"concept_mismatch", "wrong_sense", "contradiction"}:
        return "ERROR"
    return "WARNING"


def _provenance(
    run: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    binding: Mapping[str, Any],
) -> dict[str, Any]:
    pairwise = [
        row
        for row in run["pairwise_observations"]
        if candidate["candidate_id"] in {row["candidate_a_id"], row["candidate_b_id"]}
    ]
    rows = list(candidate_provider_provenances(candidate, pairwise))
    model_routes = {
        (
            str(row["provider_route_id"]),
            str(row["model_id"]),
            str(row["model_family"]),
            str(row["independence_group"]),
        )
        for row in rows
    }
    prompt_pairs = sorted(
        {(str(row["role"]), str(row["prompt_sha256"])) for row in rows}
    )
    prompt_hashes = {
        f"{role}:{index:03d}": prompt_sha
        for index, (role, prompt_sha) in enumerate(prompt_pairs, 1)
    }
    source_artifacts = {
        name: str(value["physical_sha256"])
        for name, value in sorted(run["input_source_artifacts"].items())
    }
    source_artifacts["context_substitution_input"] = run["input_sha256"]
    source_artifacts["context_substitution_run"] = run["integrity"]["run_sha256"]
    policy = run["execution_policy"]
    return {
        "run_id": binding["run_id"],
        "started_at": binding["started_at"],
        "completed_at": binding["completed_at"],
        "component_id": "context-substitution",
        "component_version": COMPONENT_VERSION,
        "policy_version": policy["threshold_policy"]["policy_version"],
        "prompt_hashes": prompt_hashes,
        "model_routes": [
            {
                "provider_id": provider_id,
                "model_id": model_id,
                "model_family": model_family,
                "independence_group": independence_group,
            }
            for provider_id, model_id, model_family, independence_group in sorted(
                model_routes
            )
        ],
        "source_artifact_hashes": source_artifacts,
        "raw_ledger_ref": binding["raw_ledger_ref"],
        "notes": "C evidence only; Global Validator unavailable and no global action emitted.",
        "run_spec_id": binding["run_spec_id"],
        "execution_config_sha256": canonical_sha256(policy),
    }
