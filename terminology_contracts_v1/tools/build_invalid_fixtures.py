from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
