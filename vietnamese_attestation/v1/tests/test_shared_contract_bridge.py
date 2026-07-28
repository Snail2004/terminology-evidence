from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from terminology_contracts.canonical import calculate_self_sha256

from vietnamese_attestation.v1.contracts.base import ContractValidationError
from vietnamese_attestation.v1.contracts.output import (
    validate_attestation_package,
)
from vietnamese_attestation.v1.contracts.shared import (
    adapt_shared_frozen_candidate,
    project_shared_attestation_package,
    validate_shared_attestation_package,
    validate_shared_frozen_candidate,
)
from vietnamese_attestation.v1.judging import StaticJudgeProvider
from vietnamese_attestation.v1.cli.run import main
from vietnamese_attestation.v1.retrieval import StaticDocumentFetcher
from vietnamese_attestation.v1.retrieval.urls import canonicalize_url

from .conftest import judge_payload
from .test_engine import _engine, _search_provider


REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_EXAMPLE = (
    REPO_ROOT
    / "terminology_contracts_v1"
    / "examples"
    / "valid"
    / "frozen_candidate_contract.json"
)


def test_shared_frozen_candidate_adapts_without_changing_join_key() -> None:
    shared = _shared_candidate()
    internal = adapt_shared_frozen_candidate(shared)

    assert internal["candidate_id"] == shared["candidate_key"]["candidate_id"]
    assert internal["candidate_vi"] == shared["candidate_key"]["candidate_vi"]
    assert internal["term_id"] == shared["candidate_key"]["candidate_id"]
    assert internal["sense_contract"]["definition_en"] == shared[
        "effective_definition_en"
    ]
    assert internal["known_surfaces"]["validated_variants"] == shared[
        "surfaces"
    ]["validated_variants_vi"]


def test_shared_contract_tamper_fails_before_engine() -> None:
    shared = _shared_candidate()
    shared["candidate_key"]["candidate_vi"] = "biá»ƒu thá»©c kháº£ nghi"

    with pytest.raises(ContractValidationError, match="self_sha256 mismatch"):
        validate_shared_frozen_candidate(shared)


def test_shared_candidate_version_uses_shared_string_limit() -> None:
    shared = _shared_candidate()
    shared["candidate_key"]["candidate_version"] = "v" * 512
    shared["integrity"]["self_sha256"] = calculate_self_sha256(shared)

    internal = adapt_shared_frozen_candidate(shared)

    assert internal["candidate_version"] == "v" * 512


def test_internal_package_projects_to_shared_attestation_contract() -> None:
    shared = _shared_candidate()
    internal = _attested_internal_package(shared)

    projected = project_shared_attestation_package(internal, shared)

    validate_shared_attestation_package(projected)
    assert projected["candidate_key"] == shared["candidate_key"]
    assert projected["input_contract_sha256"] == shared["integrity"][
        "self_sha256"
    ]
    assert projected["local_status"] == "ATTESTED"
    assert len(projected["accepted_evidence_refs"]) == 2
    assert projected["provenance"]["raw_ledger_ref"]["sha256"] == internal[
        "integrity"
    ]["package_sha256"]
    assert projected["final_glossary_decision"] is None


def test_projection_rejects_foreign_internal_candidate() -> None:
    shared = _shared_candidate()
    internal = _attested_internal_package(shared)
    foreign = copy.deepcopy(shared)
    foreign["candidate_key"]["candidate_id"] = "foreign-candidate"
    foreign["integrity"]["self_sha256"] = calculate_self_sha256(foreign)

    with pytest.raises(ContractValidationError, match="not bound"):
        project_shared_attestation_package(internal, foreign)


def test_cli_accepts_shared_input_and_preserves_internal_replay(
    tmp_path: Path,
) -> None:
    shared = _shared_candidate()
    candidate_path = tmp_path / "shared-candidate.json"
    fixture_path = tmp_path / "fixture.json"
    output_path = tmp_path / "shared-attestation.json"
    run_store_root = tmp_path / "run-store"
    candidate_path.write_text(
        json.dumps(shared, ensure_ascii=False), encoding="utf-8"
    )
    fixture_path.write_text(
        json.dumps(
            {
                "search_provider_id": "fixture_search",
                "search_results_by_query_class": {
                    "EXACT_CANDIDATE": [],
                    "CANDIDATE_DOMAIN": [],
                    "CANDIDATE_SOURCE_TERM": [],
                },
                "documents": {},
                "judge_routes": [
                    {
                        "route_id": "fixture_judge",
                        "model_id": "fixture-model",
                        "payloads_by_evidence_id": {"*": judge_payload()},
                    }
                ],
                "timestamps": [
                    "2026-01-01T00:00:00Z",
                    "2026-01-01T00:00:01Z",
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "--candidate",
                str(candidate_path),
                "--offline-fixture",
                str(fixture_path),
                "--output",
                str(output_path),
                "--run-store-root",
                str(run_store_root),
            ]
        )
        == 0
    )

    shared_package = validate_shared_attestation_package(
        json.loads(output_path.read_text(encoding="utf-8"))
    )
    execution_root = (
        run_store_root / "runs" / shared_package["provenance"]["run_id"]
    )
    assert (execution_root / "shared-package.json").read_bytes() == output_path.read_bytes()
    validate_attestation_package(
        json.loads(
            (execution_root / "package.json").read_text(encoding="utf-8")
        )
    )


def _shared_candidate() -> dict[str, object]:
    return json.loads(SHARED_EXAMPLE.read_text(encoding="utf-8"))


def _attested_internal_package(shared: dict[str, object]) -> dict[str, object]:
    internal_candidate = adapt_shared_frozen_candidate(shared)
    candidate_surface = "suy lu\u1eadn"
    urls = [
        "https://hoclieu.gov.vn/ml/inference",
        "https://mirror.example.com/copied-inference",
        "https://lab.edu.vn/guide/inference",
    ]
    shared_document = (
        "<html><title>C\u1ea9m nang</title><body>Trong h\u1ecdc m\u00e1y, "
        f"{candidate_surface} l\u00e0 qu\u00e1 tr\u00ecnh m\u00f4 h\u00ecnh \u0111\u00e3 hu\u1ea5n luy\u1ec7n "
        "t\u1ea1o d\u1ef1 \u0111o\u00e1n cho d\u1eef li\u1ec7u m\u1edbi. N\u1ed9i dung n\u00e0y tr\u00ecnh b\u00e0y "
        "k\u1ef9 thu\u1eadt tri\u1ec3n khai m\u00f4 h\u00ecnh trong h\u1ec7 th\u1ed1ng th\u1ef1c t\u1ebf.</body></html>"
    )
    independent_document = (
        "<html><title>Gi\u00e1o tr\u00ecnh</title><body>M\u1ed9t m\u00f4 h\u00ecnh h\u1ecdc m\u00e1y th\u1ef1c hi\u1ec7n "
        f"{candidate_surface} \u0111\u1ec3 sinh \u0111\u1ea7u ra tr\u00ean m\u1eabu ch\u01b0a t\u1eebng th\u1ea5y. "
        "T\u00e0i li\u1ec7u m\u00f4 t\u1ea3 qu\u00e1 tr\u00ecnh d\u1ef1 \u0111o\u00e1n trong tri\u1ec3n khai v\u00e0 "
        "gi\u1ea3i th\u00edch c\u00e1ch tham s\u1ed1 \u0111\u00e3 hu\u1ea5n luy\u1ec7n x\u1eed l\u00fd d\u1eef li\u1ec7u m\u1edbi.</body></html>"
    )
    documents = {
        canonicalize_url(urls[0]): ("text/html", shared_document),
        canonicalize_url(urls[1]): ("text/html", shared_document),
        canonicalize_url(urls[2]): ("text/html", independent_document),
    }
    accepted_judge = judge_payload()
    accepted_judge["evidence_span"] = candidate_surface
    return _engine(
        _search_provider(urls),
        StaticDocumentFetcher(documents),
        [
            StaticJudgeProvider(
                route_id="fixture_judge",
                model_id="fixture-model",
                payloads_by_evidence_id={"*": accepted_judge},
            )
        ],
    ).run(internal_candidate)
