from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from terminology_contracts.integrity import canonical_sha256, seal_self_hash  # noqa: E402
from terminology_contracts.registries import PACKAGE_VERSION  # noqa: E402


def _load(name: str) -> dict:
    return json.loads(
        (ROOT / "examples" / "valid" / "v1.1.0" / name).read_text(
            encoding="utf-8"
        )
    )


def _write(name: str, value: dict) -> None:
    path = ROOT / "examples" / "valid" / "v1.1.0" / name
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    calibration = _load("calibration_artifact.json")
    calibration["feature_contract_version"] = PACKAGE_VERSION
    calibration["verification_status"] = "SEALED"
    names = list(calibration["model"]["feature_names"])
    coefficients = calibration["model"]["parameters"].setdefault("coefficients", {})
    for name in names:
        coefficients.setdefault(name, 0.0)
    calibration = seal_self_hash(calibration)
    _write("calibration_artifact.json", calibration)

    candidate = _load("frozen_candidate_contract.json")
    context = _load("context_evidence_package.json")
    attestation = _load("attestation_evidence_package.json")
    global_input = _load("global_validator_input.json")
    gates = _load("gate_result_set.json")
    decision = _load("global_decision_package.json")
    certificate = _load("terminology_certificate.json")
    tac = _load("tac_occurrence_input.json")

    context_hash = context["integrity"]["self_sha256"]
    attestation_hash = attestation["integrity"]["self_sha256"]
    input_hash = global_input["integrity"]["self_sha256"]
    gate_hash = gates["integrity"]["self_sha256"]
    calibration_hash = calibration["integrity"]["self_sha256"]

    decision["context_evidence_sha256"] = context_hash
    decision["attestation_evidence_sha256"] = attestation_hash
    decision["decision_policy"]["feature_contract_version"] = PACKAGE_VERSION
    decision["decision_policy"]["calibration_artifact_sha256"] = calibration_hash
    decision["run_metadata"].update(
        {
            "binding_status": "COMPLETE",
            "feature_contract_version": PACKAGE_VERSION,
            "started_at": "2026-07-28T11:00:00+00:00",
            "completed_at": "2026-07-28T11:01:00+00:00",
            "input_package_hashes": {
                "global_validator_input_sha256": input_hash,
                "context_evidence_sha256": context_hash,
                "attestation_evidence_sha256": attestation_hash,
            },
        }
    )
    replay_spec = {
        "candidate_key": decision["candidate_key"],
        "input_contract_sha256": decision["input_contract_sha256"],
        "gate_policy_version": decision["gate_results"]["gate_policy_version"],
        "decision_policy": decision["decision_policy"],
    }
    decision["run_metadata"]["replay_spec_sha256"] = canonical_sha256(replay_spec)
    decision = seal_self_hash(decision)
    _write("global_decision_package.json", decision)

    certificate["binding_status"] = "COMPLETE"
    certificate["attestation_evidence_refs"] = [
        {
            "evidence_id": "attestation-demo-001",
            "evidence_type": "ATTESTATION_SOURCE",
            "uri": "artifact://fixtures/attestation_evidence_package.json",
            "sha256": attestation_hash,
        }
    ]
    certificate["input_contract_sha256"] = candidate["input_contract_sha256"]
    certificate["context_evidence_sha256"] = context_hash
    certificate["attestation_evidence_sha256"] = attestation_hash
    certificate["evidence_summary"]["context_evidence_sha256"] = context_hash
    certificate["evidence_summary"]["attestation_evidence_sha256"] = attestation_hash
    certificate["gate_result_sha256"] = gate_hash
    certificate["calibration_artifact_sha256"] = calibration_hash
    certificate["decision_package_sha256"] = decision["integrity"]["self_sha256"]
    certificate["threshold_version"] = "calibration-fixture-v1.1.0"
    certificate = seal_self_hash(certificate)
    _write("terminology_certificate.json", certificate)

    tac["certificate"] = copy.deepcopy(certificate)
    tac = seal_self_hash(tac)
    _write("tac_occurrence_input.json", tac)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
