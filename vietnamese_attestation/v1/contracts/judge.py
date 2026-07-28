from __future__ import annotations

import unicodedata
from typing import Any, Mapping

from vietnamese_attestation.v1.contracts.base import (
    ContractValidationError,
    require_enum,
    require_exact_keys,
    require_mapping,
    require_string,
)


JUDGE_SCHEMA_ID = "VietnameseAttestationJudgeResultV1"
JUDGE_SCHEMA_VERSION = "1.0.0"
JUDGEABILITY = frozenset(
    {
        "JUDGEABLE",
        "INSUFFICIENT_SNIPPET",
        "INVALID_SNIPPET",
        "AMBIGUOUS_CONCEPT",
    }
)
CONCEPT_RELATIONS = frozenset({"SAME", "RELATED", "DIFFERENT", "UNCERTAIN"})
CANDIDATE_ROLES = frozenset(
    {
        "TECHNICAL_TERM",
        "GENERAL_WORD",
        "NAME",
        "QUOTE",
        "METALANGUAGE",
        "UNDETERMINED",
    }
)


def validate_judge_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    root = require_mapping(payload, path="$")
    require_exact_keys(
        root,
        required={
            "schema_id",
            "schema_version",
            "judgeability",
            "concept_relation",
            "domain_match",
            "candidate_role",
            "machine_translation_suspected",
            "evidence_span",
            "reason",
        },
        path="$",
    )
    if not isinstance(root["domain_match"], bool):
        raise ContractValidationError(
            "type", "$.domain_match", "expected a boolean"
        )
    if not isinstance(root["machine_translation_suspected"], bool):
        raise ContractValidationError(
            "type",
            "$.machine_translation_suspected",
            "expected a boolean",
        )
    normalized = {
        "schema_id": require_enum(
            root["schema_id"], {JUDGE_SCHEMA_ID}, path="$.schema_id"
        ),
        "schema_version": require_enum(
            root["schema_version"],
            {JUDGE_SCHEMA_VERSION},
            path="$.schema_version",
        ),
        "judgeability": require_enum(
            root["judgeability"], JUDGEABILITY, path="$.judgeability"
        ),
        "concept_relation": require_enum(
            root["concept_relation"],
            CONCEPT_RELATIONS,
            path="$.concept_relation",
        ),
        "domain_match": root["domain_match"],
        "candidate_role": require_enum(
            root["candidate_role"],
            CANDIDATE_ROLES,
            path="$.candidate_role",
        ),
        "machine_translation_suspected": root[
            "machine_translation_suspected"
        ],
        "evidence_span": require_string(
            root["evidence_span"],
            path="$.evidence_span",
            allow_empty=True,
            maximum=1000,
        ),
        "reason": require_string(
            root["reason"], path="$.reason", maximum=2000
        ),
    }
    if normalized["judgeability"] != "JUDGEABLE":
        if normalized["concept_relation"] != "UNCERTAIN":
            raise ContractValidationError(
                "judge_relation",
                "$.concept_relation",
                "unjudgeable results must use UNCERTAIN",
            )
    return normalized


def validate_judge_payload_for_snippet(
    payload: Mapping[str, Any],
    *,
    snippet_original: str,
) -> dict[str, Any]:
    normalized = validate_judge_payload(payload)
    evidence_span = unicodedata.normalize(
        "NFC", normalized["evidence_span"]
    )
    snippet = unicodedata.normalize("NFC", snippet_original)
    if normalized["judgeability"] == "JUDGEABLE":
        if not evidence_span:
            raise ContractValidationError(
                "evidence_span",
                "$.evidence_span",
                "judgeable results require a quoted evidence span",
            )
        if evidence_span.casefold() not in snippet.casefold():
            raise ContractValidationError(
                "evidence_span",
                "$.evidence_span",
                "evidence span is not present in the original snippet",
            )
    elif evidence_span:
        raise ContractValidationError(
            "evidence_span",
            "$.evidence_span",
            "unjudgeable results must not fabricate an evidence span",
        )
    return normalized


__all__ = [
    "CANDIDATE_ROLES",
    "CONCEPT_RELATIONS",
    "JUDGE_SCHEMA_ID",
    "JUDGE_SCHEMA_VERSION",
    "JUDGEABILITY",
    "validate_judge_payload",
    "validate_judge_payload_for_snippet",
]
