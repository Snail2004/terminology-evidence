from __future__ import annotations

from pathlib import Path
import copy
import hashlib
import json

import pytest
from terminology_contracts.bindings import calculate_replay_spec_sha256
from terminology_contracts.integrity import seal_self_hash

from global_validator.v1.audit import replay_run
from global_validator.v1.certificates import verify_persisted_certificate_bundle
from global_validator.v1.config import ExecutionMode, validate_run_config
from global_validator.v1.decision import verify_decision_artifact
from global_validator.v1.engine import run_global_validator
from global_validator.v1.errors import (
    CalibrationError,
    CertificateBindingError,
    DecisionReplayError,
    StorageError,
)
from global_validator.v1.input import assemble_global_input

from .helpers import load_base_input


def test_development_run_is_provisional_certificate_free_and_replayable(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    config = config_factory(output_root=tmp_path, run_id="development-run")
    result = run_global_validator(valid_input_path, config)

    assert result.decision["decision"] == "PROVISIONAL"
    assert result.decision["approval_score"] is None
    assert result.decision["decision_features"] == {}
    assert result.decision["certificate_ref"] is None
    assert result.certificate is None
    assert not (result.run_dir / "output" / "terminology_certificate.json").exists()
    assert replay_run(result.run_dir).matched is True
    assert (
        result.run_dir / "audit" / "authority_verification.json"
    ).read_text(encoding="utf-8").find("CANONICAL_SELF_HASH") >= 0

    with pytest.raises(StorageError, match="already exists"):
        run_global_validator(valid_input_path, config)


def test_contract_example_calibration_requires_explicit_test_mode(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path,
        run_id="blocked-example-calibration",
    )
    with pytest.raises(CalibrationError, match="non-production"):
        run_global_validator(valid_input_path, config)


def test_frozen_production_requires_reviewed_calibration_pin(
    tmp_path: Path, config_factory
) -> None:
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        calibration_path=tmp_path / "reviewed-calibration.json",
    )
    with pytest.raises(CalibrationError, match="expected_calibration_sha256"):
        validate_run_config(config)


def test_copied_example_calibration_remains_non_production(
    valid_input_path: Path,
    calibration_path: Path,
    tmp_path: Path,
    config_factory,
) -> None:
    copied = tmp_path / "copied-calibration.json"
    copied.write_bytes(calibration_path.read_bytes())
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path / "runs",
        run_id="copied-example-calibration",
        calibration_path=copied,
        expected_calibration_sha256=(
            "e8b3b871dda5a17d2f449ed894b23a4b1d5614180fbc59035f92171560926a76"
        ),
    )
    with pytest.raises(CalibrationError, match="non-production"):
        run_global_validator(valid_input_path, config)


def test_calibration_byte_tamper_fails_before_scoring(
    valid_input_path: Path,
    calibration_path: Path,
    tmp_path: Path,
    config_factory,
) -> None:
    payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    payload["model"]["parameters"]["coefficients"]["C_mean"] = 9.0
    tampered = tmp_path / "tampered-calibration.json"
    tampered.write_text(json.dumps(payload), encoding="utf-8")
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path / "runs",
        run_id="tampered-calibration",
        calibration_path=tampered,
        allow_example_calibration=True,
    )
    with pytest.raises(CalibrationError, match="self_sha256 mismatch"):
        run_global_validator(valid_input_path, config)


def test_fixture_mode_rejects_resealed_nonfixture_calibration(
    valid_input_path: Path,
    calibration_path: Path,
    tmp_path: Path,
    config_factory,
) -> None:
    payload = json.loads(calibration_path.read_text(encoding="utf-8"))
    payload["created_at"] = "2026-07-29T00:00:00+00:00"
    altered = tmp_path / "altered-calibration.json"
    altered.write_text(
        json.dumps(seal_self_hash(payload), ensure_ascii=False), encoding="utf-8"
    )
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path / "runs",
        run_id="altered-fixture",
        calibration_path=altered,
        allow_example_calibration=True,
    )
    with pytest.raises(CalibrationError, match="exact contract fixture"):
        run_global_validator(valid_input_path, config)


def test_frozen_fixture_score_certificate_bundle_and_replay(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path,
        run_id="frozen-fixture-run",
        allow_example_calibration=True,
    )
    result = run_global_validator(valid_input_path, config)

    assert result.decision["decision"] == "AUTO_APPROVED"
    assert result.decision["approval_score"] == pytest.approx(
        0.880481737215655, abs=1e-15
    )
    assert result.certificate is not None
    certificate = result.certificate
    frozen = result.global_input["frozen_candidate_contract"]
    assert certificate["allowed_variants"] == frozen["surfaces"][
        "validated_variants_vi"
    ]
    assert certificate["forbidden_candidates"] == frozen["surfaces"][
        "rejected_variants_vi"
    ]
    assert certificate["validity_context_refs"] == result.global_input[
        "context_evidence"
    ]["support_set"]["positive_support_refs"]
    assert certificate["attestation_evidence_refs"] == result.global_input[
        "attestation_evidence"
    ]["accepted_evidence_refs"]

    report = verify_persisted_certificate_bundle(
        result.run_dir,
        schema_dir=config.schema_dir,
        feature_registry_path=config.feature_registry_path,
    )
    assert report["status"] == "PASS"
    assert replay_run(result.run_dir).matched is True
    verified_decision = verify_decision_artifact(
        result.run_dir / "output" / "global_decision_package.json",
        global_input_path=result.run_dir / "input" / "global_validator_input.json",
        config=config,
    )
    assert verified_decision["integrity"]["self_sha256"] == result.decision[
        "integrity"
    ]["self_sha256"]


def test_frozen_cap_provisional_still_emits_scope_limited_certificate(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    base = load_base_input(valid_input_path)
    context = copy.deepcopy(base["context_evidence"])
    direct_ref = copy.deepcopy(context["support_set"]["positive_support_refs"][0])
    context["contrastive_status"] = "ABSENT"
    context["support_set"]["contrastive_refs"] = []
    context["flags"] = [
        {
            "code": "missing_contrastive_context",
            "severity": "WARNING",
            "message": "Synthetic contract test.",
            "evidence_refs": [direct_ref],
        }
    ]
    signal = next(
        item
        for item in context["gate_signals"]
        if item["gate_id"] == "missing_contrastive_context"
    )
    signal.update(
        {
            "asserted": True,
            "reason_codes": ["MISSING_CONTRASTIVE_CONTEXT"],
            "evidence_refs": [direct_ref],
        }
    )
    context = seal_self_hash(context)
    payload = assemble_global_input(
        effective_sense_contract=base["effective_sense_contract"],
        frozen_candidate_contract=base["frozen_candidate_contract"],
        constraint_evidence=base["constraint_evidence"],
        context_evidence=context,
        attestation_evidence=base["attestation_evidence"],
        assembled_at="2026-07-29T00:00:00+00:00",
        schema_dir=config_factory().schema_dir,
        gate_policy_path=config_factory().gate_policy_path,
        feature_registry_path=config_factory().feature_registry_path,
    )
    input_path = tmp_path / "provisional-input.json"
    input_path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path / "runs",
        run_id="frozen-provisional",
        allow_example_calibration=True,
    )
    result = run_global_validator(input_path, config)
    assert result.decision["decision"] == "PROVISIONAL"
    assert result.certificate is not None
    assert result.certificate["status"] == "PROVISIONAL"
    assert result.certificate["gate_summary"] == ["missing_contrastive_context"]


def test_bundle_tamper_is_rejected(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path,
        run_id="tamper-run",
        allow_example_calibration=True,
    )
    result = run_global_validator(valid_input_path, config)
    decision_path = result.run_dir / "output" / "global_decision_package.json"
    decision_path.write_bytes(decision_path.read_bytes() + b"\n")
    with pytest.raises(CertificateBindingError, match="checksum mismatch"):
        verify_persisted_certificate_bundle(
            result.run_dir,
            schema_dir=config.schema_dir,
            feature_registry_path=config.feature_registry_path,
        )


def test_replay_rejects_maintainer_decision_tamper_reproduction(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    result = run_global_validator(
        valid_input_path,
        config_factory(output_root=tmp_path, run_id="decision-tamper"),
    )
    decision_path = result.run_dir / "output" / "global_decision_package.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["decision"] = "REJECTED"
    _write_json(decision_path, decision)

    with pytest.raises(DecisionReplayError, match="checksum mismatch.*decision"):
        replay_run(result.run_dir)


@pytest.mark.parametrize(
    "relative",
    [
        "output/gate_result_set.json",
        "audit/run_spec.json",
    ],
)
def test_replay_rejects_gate_and_run_spec_byte_tamper(
    relative: str, valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    result = run_global_validator(
        valid_input_path,
        config_factory(
            output_root=tmp_path / relative.replace("/", "-"),
            run_id="bundle-byte-tamper",
        ),
    )
    path = result.run_dir.joinpath(*relative.split("/"))
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(DecisionReplayError, match="checksum mismatch"):
        replay_run(result.run_dir)


def test_replay_rejects_checksum_listing_tamper(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    result = run_global_validator(
        valid_input_path,
        config_factory(output_root=tmp_path, run_id="checksum-tamper"),
    )
    checksums = result.run_dir / "CHECKSUMS.sha256"
    lines = checksums.read_text(encoding="ascii").splitlines()
    lines[0] = ("0" if lines[0][0] != "0" else "1") + lines[0][1:]
    checksums.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")

    with pytest.raises(DecisionReplayError, match="checksum mismatch"):
        replay_run(result.run_dir)


def test_replay_rejects_strict_json_tamper_even_with_refreshed_checksum(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    result = run_global_validator(
        valid_input_path,
        config_factory(output_root=tmp_path, run_id="duplicate-json"),
    )
    spec_path = result.run_dir / "audit" / "run_spec.json"
    spec_path.write_text(
        '{"schema_id":"GlobalValidatorReplaySpecV1",'
        '"schema_id":"Other"}\n',
        encoding="utf-8",
        newline="\n",
    )
    _refresh_checksums(result.run_dir, "audit/run_spec.json")

    with pytest.raises(DecisionReplayError, match="duplicate JSON key"):
        replay_run(result.run_dir)


def test_replay_rejects_rechecksummed_run_spec_binding_drift(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    result = run_global_validator(
        valid_input_path,
        config_factory(output_root=tmp_path, run_id="run-spec-binding"),
    )
    spec_path = result.run_dir / "audit" / "run_spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["global_run_id"] = "tampered-run-id"
    _write_json(spec_path, spec)
    _refresh_checksums(result.run_dir, "audit/run_spec.json")

    with pytest.raises(DecisionReplayError, match="run_metadata.global_run_id"):
        replay_run(result.run_dir)


def test_replay_rejects_authority_byte_tamper_after_checksum_refresh(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    result = run_global_validator(
        valid_input_path,
        config_factory(output_root=tmp_path, run_id="authority-tamper"),
    )
    receipt = result.run_dir / "input" / "authority_receipt.json"
    receipt.write_bytes(receipt.read_bytes() + b" ")
    _refresh_checksums(result.run_dir, "input/authority_receipt.json")

    with pytest.raises(DecisionReplayError, match="physical SHA-256"):
        replay_run(result.run_dir)


@pytest.mark.parametrize(
    "mutation,error",
    [
        ("execution_config", "execution_config_sha256 mismatch"),
        ("timestamps", "run_metadata.started_at mismatch"),
    ],
)
def test_verify_decision_rejects_resealed_config_binding_drift(
    mutation: str,
    error: str,
    valid_input_path: Path,
    tmp_path: Path,
    config_factory,
) -> None:
    config = config_factory(output_root=tmp_path / "runs", run_id="verify-binding")
    result = run_global_validator(valid_input_path, config)
    decision = copy.deepcopy(result.decision)
    if mutation == "execution_config":
        decision["run_metadata"]["execution_config_sha256"] = "f" * 64
    else:
        decision["run_metadata"]["started_at"] = "2026-07-30T00:00:00+00:00"
        decision["run_metadata"]["completed_at"] = "2026-07-29T00:00:00+00:00"
    decision["run_metadata"]["replay_spec_sha256"] = calculate_replay_spec_sha256(
        decision
    )
    decision = seal_self_hash(decision)
    decision_path = tmp_path / f"{mutation}.json"
    _write_json(decision_path, decision)

    with pytest.raises(DecisionReplayError, match=error):
        verify_decision_artifact(
            decision_path,
            global_input_path=valid_input_path,
            config=config,
        )


@pytest.mark.parametrize(
    "foreign_platform_hint",
    [r"C:\work\terminology_evidence", "/var/lib/terminology_evidence"],
)
def test_replay_uses_explicit_portable_authority_root(
    foreign_platform_hint: str,
    valid_input_path: Path,
    tmp_path: Path,
    config_factory,
) -> None:
    config = config_factory(output_root=tmp_path, run_id="portable-authority")
    result = run_global_validator(valid_input_path, config)
    spec_path = result.run_dir / "audit" / "run_spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    assert spec["schema_version"] == "1.1.0"
    spec["repository_root_hint"] = foreign_platform_hint
    _write_json(spec_path, spec)
    _refresh_checksums(result.run_dir, "audit/run_spec.json")

    assert replay_run(
        result.run_dir, authority_root=config.repository_root
    ).matched is True


def test_replay_without_authority_root_rejects_relative_hint(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    config = config_factory(output_root=tmp_path, run_id="relative-hint")
    result = run_global_validator(valid_input_path, config)
    spec_path = result.run_dir / "audit" / "run_spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["repository_root_hint"] = "relative/provenance-only"
    _write_json(spec_path, spec)
    _refresh_checksums(result.run_dir, "audit/run_spec.json")

    with pytest.raises(DecisionReplayError, match="must be absolute"):
        replay_run(result.run_dir)


def test_replay_rejects_resealed_action_policy_authority_drift(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    result = run_global_validator(
        valid_input_path,
        config_factory(output_root=tmp_path, run_id="action-authority-drift"),
    )
    authority_path = (
        result.run_dir / "input" / "gate_action_policy_authority.json"
    )
    authority = json.loads(authority_path.read_text(encoding="utf-8"))
    authority["status"] = "SUPERSEDED"
    authority = seal_self_hash(authority)
    _write_json(authority_path, authority)
    _refresh_checksums(
        result.run_dir, "input/gate_action_policy_authority.json"
    )

    with pytest.raises(
        DecisionReplayError, match="persisted action-policy authority differs"
    ):
        replay_run(result.run_dir)


def test_replay_rejects_rechecksummed_run_spec_authority_drift(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    result = run_global_validator(
        valid_input_path,
        config_factory(output_root=tmp_path, run_id="spec-authority-drift"),
    )
    spec_path = result.run_dir / "audit" / "run_spec.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["contracts_manifest_sha256"] = "f" * 64
    _write_json(spec_path, spec)
    _refresh_checksums(result.run_dir, "audit/run_spec.json")

    with pytest.raises(
        DecisionReplayError, match="contracts_manifest_sha256 authority mismatch"
    ):
        replay_run(result.run_dir)


def test_replay_rejects_resealed_semantic_decision_drift(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    result = run_global_validator(
        valid_input_path,
        config_factory(output_root=tmp_path, run_id="resealed-decision"),
    )
    decision_path = result.run_dir / "output" / "global_decision_package.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["decision"] = "REJECTED"
    decision["decision_reasons"] = ["RESEALED_SEMANTIC_DRIFT"]
    decision = seal_self_hash(decision)
    _write_json(decision_path, decision)

    run_path = result.run_dir / "audit" / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["decision"] = decision["decision"]
    run["decision_package_sha256"] = decision["integrity"]["self_sha256"]
    _write_json(run_path, run)
    _refresh_checksums(
        result.run_dir,
        "audit/run.json",
        "output/global_decision_package.json",
    )

    with pytest.raises(
        DecisionReplayError, match="configured-policy recomputation"
    ):
        replay_run(result.run_dir)


def test_replay_rejects_resealed_gate_drift_against_recomputation(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    result = run_global_validator(
        valid_input_path,
        config_factory(output_root=tmp_path, run_id="resealed-gate"),
    )
    gate_path = result.run_dir / "output" / "gate_result_set.json"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    observation = next(
        item
        for item in gate["observations"]
        if item["gate_id"] == "concept_mismatch"
    )
    assert observation["triggered"] is False
    observation["source_modules"] = list(reversed(observation["source_modules"]))
    gate = seal_self_hash(gate)
    _write_json(gate_path, gate)

    decision_path = result.run_dir / "output" / "global_decision_package.json"
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    decision["gate_results"] = gate
    decision["run_metadata"]["input_package_hashes"]["gate_result_sha256"] = gate[
        "integrity"
    ]["self_sha256"]
    decision["run_metadata"]["replay_spec_sha256"] = calculate_replay_spec_sha256(
        decision
    )
    decision = seal_self_hash(decision)
    _write_json(decision_path, decision)

    run_path = result.run_dir / "audit" / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["decision_package_sha256"] = decision["integrity"]["self_sha256"]
    _write_json(run_path, run)
    _refresh_checksums(
        result.run_dir,
        "audit/run.json",
        "output/gate_result_set.json",
        "output/global_decision_package.json",
    )

    with pytest.raises(DecisionReplayError, match="configured-policy recomputation"):
        replay_run(result.run_dir)


def test_replay_verifies_resealed_certificate_bundle_before_semantic_replay(
    valid_input_path: Path, tmp_path: Path, config_factory
) -> None:
    config = config_factory(
        mode=ExecutionMode.FROZEN_CALIBRATED,
        output_root=tmp_path,
        run_id="certificate-tamper",
        allow_example_calibration=True,
    )
    result = run_global_validator(valid_input_path, config)
    certificate_path = result.run_dir / "output" / "terminology_certificate.json"
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    certificate["allowed_variants"] = ["tampered variant"]
    certificate = seal_self_hash(certificate)
    _write_json(certificate_path, certificate)

    run_path = result.run_dir / "audit" / "run.json"
    run = json.loads(run_path.read_text(encoding="utf-8"))
    run["certificate_sha256"] = certificate["integrity"]["self_sha256"]
    _write_json(run_path, run)
    _refresh_checksums(
        result.run_dir,
        "audit/run.json",
        "output/terminology_certificate.json",
    )

    with pytest.raises(DecisionReplayError, match="certificate bundle verification"):
        replay_run(result.run_dir)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _refresh_checksums(run_dir: Path, *relatives: str) -> None:
    checksums = run_dir / "CHECKSUMS.sha256"
    entries = {}
    for line in checksums.read_text(encoding="ascii").splitlines():
        digest, relative = line.split("  ", 1)
        entries[relative] = digest
    for relative in relatives:
        path = run_dir.joinpath(*relative.split("/"))
        entries[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    checksums.write_text(
        "\n".join(f"{entries[path]}  {path}" for path in sorted(entries)) + "\n",
        encoding="ascii",
        newline="\n",
    )
