from __future__ import annotations

from typing import Any

import pytest

from vietnamese_attestation.v1.contracts.frozen_candidate import (
    seal_frozen_candidate,
)
from vietnamese_attestation.v1.contracts.judge import (
    JUDGE_SCHEMA_ID,
    JUDGE_SCHEMA_VERSION,
)


@pytest.fixture
def frozen_candidate() -> dict[str, Any]:
    return seal_frozen_candidate(
        {
            "source_contract_ref": {
                "schema_id": "D2LContextSupportSetFreezeV1",
                "schema_version": "1.0.0",
                "artifact_ref": "fixtures/frozen-candidate-source.json",
                "artifact_sha256": "a" * 64,
            },
            "candidate_id": "term-inference-vi-01",
            "candidate_version": "candidate-v1",
            "term_id": "term-inference",
            "source_term": "inference",
            "candidate_vi": "suy luận",
            "sense_id": "model_execution",
            "scope_id": "machine_learning",
            "sense_contract": {
                "definition_en": (
                    "The process in which a trained model produces outputs "
                    "for new inputs."
                ),
                "definition_review_status": "VERIFIED",
                "definition_provenance": ["d2l-ch03-b015"],
                "sense_inventory_version": "sense-v2",
            },
            "known_surfaces": {
                "canonical": "suy luận",
                "validated_variants": ["quá trình suy luận"],
                "rejected_variants": ["suy diễn logic"],
            },
            "domain_profile": {
                "domain_name": "machine learning",
                "vi_anchors": ["học máy", "mô hình", "dự đoán"],
                "en_anchors": ["machine learning", "model", "prediction"],
            },
            "run_policy": {
                "attestation_policy_version": "attestation-v1.1",
                "query_policy_version": "query-v1",
                "source_policy_version": "source-tier-v2",
                "dedup_policy_version": "dedup-v2",
                "judge_policy_version": "attestation-judge-v1",
            },
        }
    )


def judge_payload(
    relation: str = "SAME",
    *,
    domain_match: bool = True,
    judgeability: str = "JUDGEABLE",
) -> dict[str, Any]:
    return {
        "schema_id": JUDGE_SCHEMA_ID,
        "schema_version": JUDGE_SCHEMA_VERSION,
        "judgeability": judgeability,
        "concept_relation": relation,
        "domain_match": domain_match,
        "candidate_role": (
            "TECHNICAL_TERM" if judgeability == "JUDGEABLE" else "UNDETERMINED"
        ),
        "machine_translation_suspected": False,
        "evidence_span": "suy luận" if judgeability == "JUDGEABLE" else "",
        "reason": "The snippet describes the target model-execution sense.",
    }
