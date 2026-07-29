from __future__ import annotations

import copy
import os
import shutil
from pathlib import Path

import pytest

from context_substitution.v2.integration.common import (
    load_json,
    seal_object,
    write_json,
)
from context_substitution.v2.integration.official_dataset import (
    EXCLUDED_ELEVEN_SENSE_COMMIT,
    OFFICIAL_MANIFEST_SELF_SHA256,
    OFFICIAL_PIN_SELF_SHA256,
    OFFICIAL_ZIP_SHA256,
    load_official_dataset_pilot,
)
from context_substitution.v2.integration.official_dataset_projection import (
    build_official_dataset_inputs,
    validate_official_adapter_receipt,
    validate_official_runtime_receipt,
)
from context_substitution.v2.integration.official_pilot import (
    run_official_zero_provider_pilot,
)
from context_substitution.v2.integration.release_validation import (
    validate_integration_evidence,
)


def _source_paths() -> tuple[Path, Path, Path]:
    names = (
        "CST_OFFICIAL_5_SENSE_ZIP",
        "CST_OFFICIAL_5_SENSE_PIN",
        "TERMINOLOGY_CONTRACTS_AUTHORITY_RECEIPT",
    )
    values = [os.environ.get(name) for name in names]
    if any(value is None for value in values):
        pytest.skip("official five-sense Dataset/Contracts dependencies are not configured")
    paths = tuple(Path(str(value)).resolve() for value in values)
    if not all(path.is_file() for path in paths):
        pytest.skip("official five-sense Dataset/Contracts dependency is missing")
    return paths  # type: ignore[return-value]


@pytest.fixture(scope="module")
def official_source():
    zip_path, pin_path, _ = _source_paths()
    return load_official_dataset_pilot(zip_path, pin_path)


@pytest.fixture(scope="module")
def official_evidence(tmp_path_factory):
    zip_path, pin_path, receipt_path = _source_paths()
    root = tmp_path_factory.mktemp("official-c-five-sense")
    report = run_official_zero_provider_pilot(
        dataset_zip=zip_path,
        dataset_pin=pin_path,
        evidence_root=root,
    )
    return root, report, receipt_path


def test_official_dataset_exact_contracts_and_runtime_bindings(official_source) -> None:
    pilot = official_source
    assert pilot.zip_sha256 == OFFICIAL_ZIP_SHA256
    assert pilot.pin["integrity"]["self_sha256"] == OFFICIAL_PIN_SELF_SHA256
    assert pilot.manifest["manifest_sha256"] == OFFICIAL_MANIFEST_SELF_SHA256
    assert len(pilot.effective_senses) == 5
    assert len(pilot.frozen_candidates) == 15
    assert len(pilot.constraint_packages) == 15
    assert EXCLUDED_ELEVEN_SENSE_COMMIT.encode("ascii") not in b"".join(
        pilot.file_bytes.values()
    )

    projected = build_official_dataset_inputs(pilot)
    validate_official_adapter_receipt(projected["adapter_receipt"])
    validate_official_runtime_receipt(projected["runtime_receipt"])
    assert len(projected["input"]["terms"]) == 5
    assert sum(
        len(term["candidate_targets"]) for term in projected["input"]["terms"]
    ) == 15
    assert projected["frozen_candidates"]["candidate_count"] == 15
    assert projected["adapter_receipt"]["provider_call_count"] == 0
    assert projected["runtime_receipt"]["network_call_count"] == 0
    assert projected["runtime_receipt"]["final_glossary_decision"] is None
    assert projected["runtime_receipt"]["global_gate_action"] is None


def test_official_zero_provider_pilot_projects_and_replays_15_packages(
    official_evidence,
) -> None:
    root, report, receipt_path = official_evidence
    assert report["status"] == "PASS"
    assert report["context_evidence_package_count"] == 15
    assert report["candidate_package_failures"] == []
    assert report["provider_call_count"] == 0
    assert report["network_call_count"] == 0
    assert report["final_glossary_decision"] is None
    assert report["global_gate_action"] is None
    assert len(report["candidate_outcomes"]) == 15
    assert (root / "official_dataset_source.zip").read_bytes() == Path(
        os.environ["CST_OFFICIAL_5_SENSE_ZIP"]
    ).read_bytes()
    assert (root / "official_dataset_input_pin_v1.json").read_bytes() == Path(
        os.environ["CST_OFFICIAL_5_SENSE_PIN"]
    ).read_bytes()

    validation = validate_integration_evidence(
        evidence_root=root,
        junit_summary={"tests": 1, "failures": 0, "errors": 0, "skipped": 0},
        authority_receipt_path=receipt_path,
    )
    assert validation["status"] == "PASS"
    assert validation["package_count"] == 15
    assert validation["provider_call_count"] == 0
    assert validation["final_glossary_decision"] is None
    assert validation["official_pilot_report_sha256"] == report["integrity"][
        "report_sha256"
    ]


def test_official_loader_rejects_zip_and_excluded_lineage_tamper(
    official_source,
    tmp_path: Path,
) -> None:
    zip_path, pin_path, _ = _source_paths()
    changed_zip = tmp_path / "changed.zip"
    changed_zip.write_bytes(zip_path.read_bytes() + b"x")
    with pytest.raises(ValueError, match="ZIP physical SHA mismatch"):
        load_official_dataset_pilot(changed_zip, pin_path)

    changed_pin = copy.deepcopy(official_source.pin)
    changed_pin["producer_git"]["unreviewed_later_commit_excluded"] = "0" * 64
    changed_pin = seal_object(changed_pin, integrity_key="self_sha256")
    changed_pin_path = tmp_path / "changed_pin.json"
    write_json(changed_pin_path, changed_pin)
    with pytest.raises(ValueError, match="pin self SHA mismatch"):
        load_official_dataset_pilot(zip_path, changed_pin_path)


def test_release_rejects_resealed_candidate_binding_drift(
    official_evidence,
    tmp_path: Path,
) -> None:
    root, _, receipt_path = official_evidence
    changed = tmp_path / "changed-evidence"
    shutil.copytree(root, changed)
    runtime_path = changed / "pilot_runtime_receipt.json"
    runtime = load_json(runtime_path)
    runtime["contract_bindings"][0]["input_contract_sha256"] = "0" * 64
    runtime = seal_object(runtime, integrity_key="receipt_sha256")
    write_json(runtime_path, runtime)
    with pytest.raises(ValueError, match="runtime receipt differs"):
        validate_integration_evidence(
            evidence_root=changed,
            junit_summary={"tests": 1, "failures": 0, "errors": 0, "skipped": 0},
            authority_receipt_path=receipt_path,
        )


def test_release_rejects_global_action_even_when_resealed(
    official_evidence,
    tmp_path: Path,
) -> None:
    root, _, receipt_path = official_evidence
    changed = tmp_path / "global-action-evidence"
    shutil.copytree(root, changed)
    report_path = changed / "official_pilot_report.json"
    report = load_json(report_path)
    report["global_gate_action"] = "ACCEPT"
    report = seal_object(report, integrity_key="report_sha256")
    write_json(report_path, report)
    with pytest.raises(ValueError, match="global_gate_action mismatch"):
        validate_integration_evidence(
            evidence_root=changed,
            junit_summary={"tests": 1, "failures": 0, "errors": 0, "skipped": 0},
            authority_receipt_path=receipt_path,
        )
