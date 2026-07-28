from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from terminology_contracts.bindings import seal_frozen_candidate_contract
from terminology_contracts.canonical import calculate_self_sha256

from vietnamese_attestation.v1.config import AttestationConfig
from vietnamese_attestation.v1.cli.replay import main as replay_main
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
from vietnamese_attestation.v1.judging import (
    FallbackJudgeRouter,
    StaticJudgeProvider,
)
from vietnamese_attestation.v1.cli.run import main
from vietnamese_attestation.v1.retrieval import StaticDocumentFetcher
from vietnamese_attestation.v1.retrieval.search import SearchProviderError
from vietnamese_attestation.v1.retrieval.urls import canonicalize_url
from vietnamese_attestation.v1.runtime.engine import AttestationEngine

from .conftest import judge_payload
from .test_engine import _engine, _search_provider


REPO_ROOT = Path(__file__).resolve().parents[3]
SHARED_EXAMPLE = (
    REPO_ROOT
    / "terminology_contracts_v1"
    / "examples"
    / "valid"
    / "v1.1.0"
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


def test_v11_input_binding_tamper_fails_even_with_valid_self_hash() -> None:
    shared = _shared_candidate()
    shared["input_contract_sha256"] = "f" * 64
    shared["integrity"]["self_sha256"] = calculate_self_sha256(shared)

    with pytest.raises(ContractValidationError, match="does not bind"):
        validate_shared_frozen_candidate(shared)


def test_shared_candidate_version_uses_shared_string_limit() -> None:
    shared = _shared_candidate()
    shared["candidate_key"]["candidate_version"] = "v" * 512
    shared = seal_frozen_candidate_contract(shared)

    internal = adapt_shared_frozen_candidate(shared)

    assert internal["candidate_version"] == "v" * 512


def test_internal_package_projects_to_shared_attestation_contract() -> None:
    shared = _shared_candidate()
    internal = _attested_internal_package(shared)

    projected = project_shared_attestation_package(internal, shared)

    validate_shared_attestation_package(projected)
    assert projected["candidate_key"] == shared["candidate_key"]
    assert projected["input_contract_sha256"] == shared[
        "input_contract_sha256"
    ]
    assert projected["input_contract_sha256"] != shared["integrity"][
        "self_sha256"
    ]
    assert projected["local_status"] == "ATTESTED"
    assert len(projected["accepted_evidence_refs"]) == 2
    assert projected["provenance"]["raw_ledger_ref"]["sha256"] == internal[
        "integrity"
    ]["package_sha256"]
    assert projected["provenance"]["run_spec_id"] == internal[
        "provenance"
    ]["run_spec_id"]
    assert projected["provenance"]["execution_config_sha256"] == internal[
        "provenance"
    ]["execution_config_sha256"]
    assert [row["gate_id"] for row in projected["gate_signals"]] == [
        "concept_mismatch",
        "contradiction",
        "judge_disagreement",
        "insufficient_evidence",
        "attestation_unjudgeable",
    ]
    assert not any(row["asserted"] for row in projected["gate_signals"])
    assert projected["final_glossary_decision"] is None


def test_semantic_negative_asserts_concept_mismatch_without_fallback() -> None:
    shared = _shared_candidate()
    primary = _SemanticJudgeProvider(default_relation="DIFFERENT")
    fallback = StaticJudgeProvider(
        route_id="unused_fallback",
        model_id="fixture-model-2",
        payloads_by_evidence_id={"*": _judge_value("SAME")},
    )
    internal = _internal_package(
        shared,
        documents={
            "https://journal.edu.vn/logic": _document("logic formal")
        },
        judges=[primary, fallback],
    )

    projected = project_shared_attestation_package(internal, shared)
    signals = _signals(projected)

    assert projected["local_status"] == "NOT_ATTESTED"
    assert signals["concept_mismatch"]["asserted"] is True
    assert signals["concept_mismatch"]["evidence_refs"]
    assert signals["contradiction"]["asserted"] is False
    assert fallback.calls == []


def test_same_and_different_evidence_asserts_contradiction() -> None:
    shared = _shared_candidate()
    judge = _SemanticJudgeProvider(
        default_relation="SAME", relation_by_marker={"logic formal": "DIFFERENT"}
    )
    internal = _internal_package(
        shared,
        documents={
            "https://hoclieu.gov.vn/ml/inference": _document(
                "model deployment"
            ),
            "https://journal.edu.vn/logic": _document("logic formal"),
        },
        judges=[judge],
    )

    projected = project_shared_attestation_package(internal, shared)
    signals = _signals(projected)

    assert projected["local_status"] == "CONFLICTING_ATTESTATION"
    assert signals["concept_mismatch"]["asserted"] is True
    assert signals["contradiction"]["asserted"] is True
    assert len(signals["contradiction"]["evidence_refs"]) == 2


def test_weak_and_unjudgeable_packages_assert_evidence_gates() -> None:
    shared = _shared_candidate()
    weak = _internal_package(
        shared,
        documents={
            "https://lab.edu.vn/ml/inference": _document("model deployment")
        },
        judges=[_SemanticJudgeProvider(default_relation="SAME")],
    )
    weak_projected = project_shared_attestation_package(weak, shared)
    weak_signals = _signals(weak_projected)
    assert weak_projected["local_status"] == "WEAKLY_ATTESTED"
    assert weak_signals["insufficient_evidence"]["asserted"] is True
    assert weak_signals["insufficient_evidence"]["evidence_refs"]

    unjudgeable = _search_failed_internal_package(shared)
    unjudgeable_projected = project_shared_attestation_package(
        unjudgeable, shared
    )
    unjudgeable_signals = _signals(unjudgeable_projected)
    assert unjudgeable_projected["local_status"] == "ATTESTATION_UNJUDGEABLE"
    assert unjudgeable_signals["insufficient_evidence"]["asserted"] is True
    assert unjudgeable_signals["attestation_unjudgeable"]["asserted"] is True
    assert unjudgeable_signals["attestation_unjudgeable"]["evidence_refs"] == [
        unjudgeable_projected["provenance"]["raw_ledger_ref"]
    ]


def test_projection_rejects_foreign_internal_candidate() -> None:
    shared = _shared_candidate()
    internal = _attested_internal_package(shared)
    foreign = copy.deepcopy(shared)
    foreign["candidate_key"]["candidate_id"] = "foreign-candidate"
    foreign = seal_frozen_candidate_contract(foreign)

    with pytest.raises(ContractValidationError, match="not bound"):
        project_shared_attestation_package(internal, foreign)


def test_shared_gate_signal_tamper_rejects_after_valid_reseal() -> None:
    shared = _shared_candidate()
    projected = project_shared_attestation_package(
        _attested_internal_package(shared), shared
    )
    signal = projected["gate_signals"][0]
    signal["asserted"] = True
    signal["reason_codes"] = ["FORGED_SIGNAL"]
    signal["evidence_refs"] = [projected["accepted_evidence_refs"][0]]
    projected["integrity"]["self_sha256"] = calculate_self_sha256(projected)

    with pytest.raises(ContractValidationError, match="disagrees"):
        validate_shared_attestation_package(projected)


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
    replay_output = tmp_path / "replay.json"
    assert (
        replay_main(
            [
                "--manifest",
                str(execution_root / "run_manifest.json"),
                "--mode",
                "REPLAY_FROM_SEARCH",
                "--output",
                str(replay_output),
            ]
        )
        == 0
    )
    assert json.loads(replay_output.read_text(encoding="utf-8"))[
        "mode"
    ] == "REPLAY_FROM_SEARCH"


def _shared_candidate() -> dict[str, object]:
    return json.loads(SHARED_EXAMPLE.read_text(encoding="utf-8"))


def _attested_internal_package(shared: dict[str, object]) -> dict[str, object]:
    shared_document = _document("model deployment")
    return _internal_package(
        shared,
        documents={
            "https://hoclieu.gov.vn/ml/inference": shared_document,
            "https://mirror.example.com/copied-inference": shared_document,
            "https://lab.edu.vn/guide/inference": _document(
                "independent model deployment"
            ),
        },
        judges=[_SemanticJudgeProvider(default_relation="SAME")],
    )


def _internal_package(
    shared: dict[str, object],
    *,
    documents: dict[str, str],
    judges: list[object],
) -> dict[str, object]:
    internal_candidate = adapt_shared_frozen_candidate(shared)
    urls = list(documents)
    return _engine(
        _search_provider(urls),
        StaticDocumentFetcher(
            {
                canonicalize_url(url): ("text/html", document)
                for url, document in documents.items()
            }
        ),
        judges,
    ).run(internal_candidate)


def _search_failed_internal_package(
    shared: dict[str, object],
) -> dict[str, object]:
    class FailedSearch:
        provider_id = "failed_search"

        def search(self, query, *, count):
            del query, count
            raise SearchProviderError("offline search failure")

    timestamps = iter(
        ["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"]
    )
    return AttestationEngine(
        search_providers=[FailedSearch()],
        document_fetcher=StaticDocumentFetcher({}),
        judge_router=FallbackJudgeRouter(
            [_SemanticJudgeProvider(default_relation="SAME")]
        ),
        config=AttestationConfig(
            search_provider_ids=("failed_search",),
            judge_route_order=("semantic_fixture",),
        ),
        clock=lambda: next(timestamps),
    ).run(adapt_shared_frozen_candidate(shared))


class _SemanticJudgeProvider:
    route_id = "semantic_fixture"
    model_id = "fixture-model"

    def __init__(
        self,
        *,
        default_relation: str,
        relation_by_marker: dict[str, str] | None = None,
    ) -> None:
        self.default_relation = default_relation
        self.relation_by_marker = dict(relation_by_marker or {})
        self.calls: list[str] = []

    def judge(self, request):
        self.calls.append(request.evidence_id)
        relation = self.default_relation
        for marker, marker_relation in self.relation_by_marker.items():
            if marker in request.snippet_original:
                relation = marker_relation
                break
        delegate = StaticJudgeProvider(
            route_id=self.route_id,
            model_id=self.model_id,
            payloads_by_evidence_id={"*": _judge_value(relation)},
        )
        return delegate.judge(request)

    def identity_payload(self) -> dict[str, object]:
        return {
            "component": "SemanticJudgeProvider",
            "route_id": self.route_id,
            "model_id": self.model_id,
            "default_relation": self.default_relation,
            "relation_by_marker": self.relation_by_marker,
        }


def _judge_value(relation: str) -> dict[str, object]:
    payload = judge_payload(relation)
    payload["evidence_span"] = "suy lu\u1eadn"
    return payload


def _document(marker: str) -> str:
    if marker == "logic formal":
        return (
            "<html><title>Logic h\u1ecdc</title><body>Marker fixture logic formal. Trong logic h\u00ecnh th\u1ee9c, "
            "suy lu\u1eadn l\u00e0 ph\u00e9p d\u1eabn xu\u1ea5t m\u1ec7nh \u0111\u1ec1 t\u1eeb ti\u00ean \u0111\u1ec1 "
            "v\u00e0 quy t\u1eafc ch\u1ee9ng minh. B\u00e0i vi\u1ebft so s\u00e1nh kh\u00e1i ni\u1ec7m n\u00e0y "
            "v\u1edbi h\u1ecdc m\u00e1y nh\u01b0ng kh\u00f4ng m\u00f4 t\u1ea3 vi\u1ec7c m\u00f4 h\u00ecnh t\u1ea1o d\u1ef1 \u0111o\u00e1n. "
            "N\u1ed9i dung c\u00f3 c\u00e1c v\u00ed d\u1ee5 v\u1ec1 tam \u0111o\u1ea1n lu\u1eadn, ti\u00ean \u0111\u1ec1 "
            "v\u00e0 k\u1ebft lu\u1eadn trong gi\u00e1o tr\u00ecnh logic.</body></html>"
        )
    if marker == "independent model deployment":
        return (
            "<html><title>V\u1eadn h\u00e0nh m\u00f4 h\u00ecnh</title><body>Khi ph\u1ee5c v\u1ee5 m\u1ed9t "
            "h\u1ec7 th\u1ed1ng d\u1ef1 \u0111o\u00e1n, m\u00f4 h\u00ecnh nh\u1eadn vector \u0111\u1ea7u v\u00e0o m\u1edbi "
            "v\u00e0 th\u1ef1c hi\u1ec7n suy lu\u1eadn \u0111\u1ec3 sinh nh\u00e3n ho\u1eb7c x\u00e1c su\u1ea5t. "
            "Quy tr\u00ecnh v\u1eadn h\u00e0nh theo d\u00f5i \u0111\u1ed9 tr\u1ec5, b\u1ed9 nh\u1edb, phi\u00ean b\u1ea3n "
            "tham s\u1ed1 v\u00e0 ph\u00e2n ph\u1ed1i d\u1eef li\u1ec7u. T\u00e0i li\u1ec7u n\u00e0y d\u00e0nh cho "
            "k\u1ef9 s\u01b0 tri\u1ec3n khai d\u1ecbch v\u1ee5 h\u1ecdc m\u00e1y.</body></html>"
        )
    return (
        "<html><title>Gi\u00e1o tr\u00ecnh</title><body>Trong h\u1ecdc m\u00e1y, "
        "suy lu\u1eadn l\u00e0 qu\u00e1 tr\u00ecnh m\u00f4 h\u00ecnh \u0111\u00e3 hu\u1ea5n luy\u1ec7n "
        "t\u1ea1o d\u1ef1 \u0111o\u00e1n cho d\u1eef li\u1ec7u m\u1edbi. T\u00e0i li\u1ec7u n\u00e0y gi\u1ea3i "
        "th\u00edch c\u00e1ch tham s\u1ed1 x\u1eed l\u00fd \u0111\u1ea7u v\u00e0o trong h\u1ec7 th\u1ed1ng "
        f"th\u1ef1c t\u1ebf v\u00e0 ghi nh\u1eadn marker {marker} cho fixture.</body></html>"
    )


def _signals(package: dict[str, object]) -> dict[str, dict[str, object]]:
    return {row["gate_id"]: row for row in package["gate_signals"]}
