from __future__ import annotations

from conftest import load_v11, reseal_decision, validate_payload


def _development_decision() -> dict:
    package = load_v11("global_decision_package.json")
    package["decision_policy"].update(
        mode="DEVELOPMENT_HEURISTIC",
        calibration_artifact_sha256=None,
        threshold=None,
    )
    package["approval_score"] = None
    package["decision"] = "PROVISIONAL"
    package["decision_reasons"] = ["DEVELOPMENT_ONLY"]
    package["certificate_ref"] = None
    return reseal_decision(package)


def test_development_provisional_without_certificate_is_valid() -> None:
    assert validate_payload(_development_decision(), calibration_path=None) == []


def test_development_cannot_auto_approve() -> None:
    package = _development_decision()
    package["decision"] = "AUTO_APPROVED"
    errors = validate_payload(reseal_decision(package), calibration_path=None)
    assert any("cannot emit AUTO_APPROVED" in error for error in errors)


def test_development_cannot_emit_certificate_reference() -> None:
    package = _development_decision()
    package["certificate_ref"] = {
        "evidence_id": "cert-ref",
        "evidence_type": "DECISION_PACKAGE",
        "uri": "artifact://certificate/ref",
        "sha256": "f" * 64,
    }
    errors = validate_payload(reseal_decision(package), calibration_path=None)
    assert any("cannot emit certificate_ref" in error for error in errors)
