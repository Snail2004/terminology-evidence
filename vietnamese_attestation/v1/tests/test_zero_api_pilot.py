from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from vietnamese_attestation.v1.runtime.replay import AuditReplayReader
from vietnamese_attestation.v1.zero_api.artifacts import verify_self_sha256
from vietnamese_attestation.v1.zero_api.pilot import (
    SCENARIOS,
    run_zero_api_pilot,
)


def test_real_pilot_runs_all_15_candidates_without_external_api(
    tmp_path: Path,
) -> None:
    summary = _run(tmp_path / "first")

    assert summary["candidate_count"] == 15
    assert summary["scenario_count"] == 15
    assert summary["scenario_coverage"] == list(SCENARIOS)
    assert summary["external_provider_call_count"] == 0
    assert summary["replay_pass_count"] == 15
    assert summary["audit_manifest_count"] == 15
    assert summary["raw_response_count"] > 0
    assert summary["controlled_corpus_status"] == "BLOCKED_EXTERNAL_INPUT"
    assert summary["contract_projection_status"] == (
        "BLOCKED_DEVELOPMENT_IDENTITY"
    )
    assert summary["final_glossary_decision"] is None

    by_scenario = {
        row["scenario"]: row for row in summary["run_results"]
    }
    assert by_scenario["STRONG_POSITIVE"]["local_status"] == "ATTESTED"
    assert by_scenario["DUPLICATE_ECHO"]["local_status"] == "ATTESTED"
    assert "DUPLICATE_ECHO_COLLAPSED" in by_scenario[
        "DUPLICATE_ECHO"
    ]["flags"]
    assert by_scenario["SAME_ORGANIZATION_DIFFERENT_DOCUMENTS"][
        "local_status"
    ] == "WEAKLY_ATTESTED"
    assert by_scenario["RELATED"]["accepted_evidence_count"] == 0
    assert by_scenario["DIFFERENT"]["local_status"] == "NOT_ATTESTED"
    assert by_scenario["UNCERTAIN"]["local_status"] == "NOT_ATTESTED"
    assert by_scenario["JUDGE_UNAVAILABLE"]["local_status"] == (
        "ATTESTATION_UNJUDGEABLE"
    )
    assert by_scenario["SEARCH_FAILURE"]["local_status"] == (
        "ATTESTATION_UNJUDGEABLE"
    )
    assert by_scenario["FETCH_TIMEOUT"]["local_status"] == (
        "ATTESTATION_UNJUDGEABLE"
    )
    assert by_scenario["EXTRACTION_FAILURE"]["local_status"] == (
        "ATTESTATION_UNJUDGEABLE"
    )
    assert by_scenario["NON_VIETNAMESE"]["local_status"] == (
        "ATTESTATION_UNJUDGEABLE"
    )
    assert by_scenario["CANDIDATE_SPAN_ABSENT"]["local_status"] == (
        "NOT_ATTESTED"
    )
    assert "MACHINE_TRANSLATION_SUSPECTED" in by_scenario[
        "MACHINE_TRANSLATION_SUSPECTED"
    ]["flags"]
    assert by_scenario["UNKNOWN_PDF"]["local_status"] == (
        "ATTESTATION_UNJUDGEABLE"
    )
    assert by_scenario["CONFLICTING_ATTESTATION"]["local_status"] == (
        "CONFLICTING_ATTESTATION"
    )
    assert all(
        row["accepted_evidence_count"] > 0
        for row in summary["run_results"]
        if row["local_status"] == "ATTESTED"
    )

    root = tmp_path / "first"
    assert len(list((root / "packages").glob("*.json"))) == 15
    assert len(list((root / "runs").glob("*/run_manifest.json"))) == 15
    assert len(list((root / "raw_responses").rglob("*.json"))) == summary[
        "raw_response_count"
    ]
    manifest = json.loads(
        (root / "zero_api_artifact_manifest.json").read_text(encoding="utf-8")
    )
    stored_summary = json.loads(
        (root / "pilot_zero_api_summary.json").read_text(encoding="utf-8")
    )
    assert verify_self_sha256(stored_summary)
    assert verify_self_sha256(manifest)
    assert stored_summary["integrity"]["self_sha256"] == (
        _authority_self_sha256(stored_summary)
    )
    assert manifest["integrity"]["self_sha256"] == (
        _authority_self_sha256(manifest)
    )
    assert manifest["file_count"] == len(manifest["files"])
    assert manifest["external_provider_call_count"] == 0
    assert manifest["final_glossary_decision"] is None
    for row in manifest["files"]:
        path = root / row["artifact_ref"]
        assert path.is_file()
        assert _sha256(path) == row["artifact_sha256"]
    tampered_summary = copy.deepcopy(stored_summary)
    tampered_summary["candidate_count"] += 1
    assert not verify_self_sha256(tampered_summary)
    attempts = _jsonl(root / "provider_attempts.jsonl")
    assert len(attempts) == summary["fixture_provider_attempt_count"]
    assert attempts and not any(row["external_api"] for row in attempts)
    required_attempt_fields = {
        "run_id",
        "candidate_id",
        "provider_id",
        "model_id",
        "query_hash",
        "request_hash",
        "response_hash",
        "status",
        "retry_index",
        "failure_reason",
        "started_at",
        "completed_at",
        "token_usage",
        "latency_ms",
    }
    assert all(required_attempt_fields <= set(row) for row in attempts)
    for path in sorted((root / "packages").glob("*.json")):
        package = json.loads(path.read_text(encoding="utf-8"))
        assert package["final_glossary_decision"] is None


def test_zero_api_pilot_is_deterministic_and_replay_detects_tamper(
    tmp_path: Path,
) -> None:
    first = _run(tmp_path / "first")
    second = _run(tmp_path / "second")

    assert first["integrity"]["self_sha256"] == second["integrity"][
        "self_sha256"
    ]
    assert [row["package_sha256"] for row in first["run_results"]] == [
        row["package_sha256"] for row in second["run_results"]
    ]

    execution_id = first["run_results"][0]["execution_id"]
    run_root = tmp_path / "first" / "runs" / execution_id
    stream = run_root / "search" / "requests.jsonl"
    stream.write_bytes(stream.read_bytes() + b"{}\n")
    with pytest.raises(ValueError, match="audit stream hash mismatch"):
        AuditReplayReader(run_root / "run_manifest.json").verify_all_content()


def _run(output_root: Path) -> dict[str, object]:
    root = Path(__file__).resolve().parents[3]
    return run_zero_api_pilot(
        source_zip=root / "dataset" / "pilot_dev_only_v1_1.zip",
        parent_v3_zip=(
            root / "dataset" / "d2l_context_support_set_validation_ready_v3.zip"
        ),
        output_root=output_root,
        controlled_registry=(
            root
            / "dataset"
            / "dataset_methodology_hardening_v1"
            / "release"
            / "controlled_vietnamese_source_registry.jsonl"
        ),
    )


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authority_self_sha256(value: dict[str, object]) -> str:
    clone = copy.deepcopy(value)
    integrity = clone.get("integrity")
    assert isinstance(integrity, dict)
    integrity.pop("self_sha256", None)
    raw = json.dumps(
        clone,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
