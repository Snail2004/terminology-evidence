from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from terminology_contracts.bindings import calculate_replay_spec_sha256  # noqa: E402
from terminology_contracts.integrity import seal_self_hash  # noqa: E402


VALID = ROOT / "examples" / "valid" / "v1.1.0"
INVALID = ROOT / "examples" / "invalid" / "v1.1.0"


def _load(name: str) -> dict:
    return json.loads((VALID / name).read_text(encoding="utf-8"))


def _write(name: str, value: dict) -> None:
    INVALID.mkdir(parents=True, exist_ok=True)
    (INVALID / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _reseal_decision(value: dict) -> dict:
    value["run_metadata"][
        "replay_spec_sha256"
    ] = calculate_replay_spec_sha256(value)
    return seal_self_hash(value)


def main() -> int:
    for path in INVALID.glob("*.json"):
        path.unlink()

    context = _load("context_evidence_package.json")
    context["features"]["pass_count"] += 1
    _write("context_bad_counts.json", seal_self_hash(context))

    attestation = _load("attestation_evidence_package.json")
    attestation["accepted_evidence_refs"] = []
    _write("attested_without_evidence.json", seal_self_hash(attestation))

    envelope = _load("global_validator_input.json")
    envelope["context_evidence"]["candidate_key"]["sense_id"] = "wrong-sense"
    envelope["context_evidence"] = seal_self_hash(envelope["context_evidence"])
    envelope["assembly_metadata"]["source_package_hashes"][
        "context_evidence_sha256"
    ] = envelope["context_evidence"]["integrity"]["self_sha256"]
    _write("global_input_mismatched_candidate.json", seal_self_hash(envelope))

    gates = _load("gate_result_set.json")
    gates["observations"][0]["triggered"] = False
    gates["observations"][0]["action"] = "FATAL_REJECT"
    _write("gate_false_with_action.json", seal_self_hash(gates))

    decision = _load("global_decision_package.json")
    decision["decision_policy"]["mode"] = "DEVELOPMENT_HEURISTIC"
    decision["decision_policy"]["calibration_artifact_sha256"] = None
    decision["decision_policy"]["threshold"] = None
    decision["certificate_ref"] = {
        "evidence_id": "forbidden-cert",
        "evidence_type": "DECISION_PACKAGE",
        "uri": "artifact://invalid/certificate",
        "sha256": "a" * 64,
    }
    _write("dev_policy_auto_approved.json", seal_self_hash(decision))

    certificate = _load("terminology_certificate.json")
    certificate["decision_package_sha256"] = "0" * 64
    _write("certificate_missing_decision_binding.json", seal_self_hash(certificate))

    calibration = _load("calibration_artifact.json")
    calibration["development_dataset_sha256"] = "0" * 64
    _write("calibration_zero_dataset_hash.json", seal_self_hash(calibration))

    frozen = _load("frozen_candidate_contract.json")
    frozen["effective_definition_en"] = "Tampered definition with stale binding."
    _write("frozen_stale_input_binding.json", seal_self_hash(frozen))

    envelope = _load("global_validator_input.json")
    envelope.pop("constraint_evidence")
    _write("global_input_missing_constraint.json", seal_self_hash(envelope))

    decision = _load("global_decision_package.json")
    decision["decision_features"] = {}
    _write("decision_empty_features.json", _reseal_decision(decision))

    gates = _load("gate_result_set.json")
    gates["observations"][1]["gate_id"] = gates["observations"][0]["gate_id"]
    _write("gate_duplicate_id.json", seal_self_hash(gates))

    tac = _load("tac_occurrence_input.json")
    tac["source_term_span"]["end"] = len(tac["source_text"]) + 1
    _write("tac_span_out_of_bounds.json", seal_self_hash(tac))

    calibration = _load("calibration_artifact.json")
    calibration["model"] = {
        "model_type": "RULE_SET",
        "feature_names": ["C_mean"],
        "parameters": {"rules": [{"feature": "C_mean"}]},
    }
    _write("calibration_undefined_rule_set.json", seal_self_hash(calibration))

    decision = _load("global_decision_package.json")
    raw = json.dumps(decision, ensure_ascii=False, sort_keys=True).replace(
        str(decision["approval_score"]), "NaN", 1
    )
    (INVALID / "decision_nan_score.json").write_text(
        raw + "\n", encoding="utf-8", newline="\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
