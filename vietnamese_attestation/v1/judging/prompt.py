from __future__ import annotations

import hashlib
import json
from typing import Any

from ..contracts.judge import JUDGE_SCHEMA_ID, JUDGE_SCHEMA_VERSION
from .base import JudgeRequest


JUDGE_PROMPT_VERSION = "attestation-judge-v1"
SYSTEM_PROMPT = """\
Bạn là Attestation Judge.
Bạn không chọn thuật ngữ và không quyết định glossary.
Bạn chỉ so sánh định nghĩa của source sense với một snippet tiếng Việt.
Không dùng tần suất hoặc authority làm bằng chứng concept đúng.
Phải đánh giá cả snippet gốc và snippet đã thay candidate bằng [TERM].
Chỉ trả một JSON object đúng schema, không thêm văn bản bên ngoài."""


def build_judge_messages(
    request: JudgeRequest,
) -> tuple[list[dict[str, str]], str]:
    payload = {
        "schema_id": "VietnameseAttestationJudgeRequestV1",
        "schema_version": "1.0.0",
        "definition_en": request.definition_en,
        "scope_id": request.scope_id,
        "candidate_vi": request.candidate_vi,
        "snippet_original": request.snippet_original,
        "snippet_masked": request.snippet_masked,
        "source_type": request.source_type,
        "required_output_schema": judge_json_schema(),
    }
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
        },
    ]
    return messages, prompt_sha256()


def prompt_sha256() -> str:
    payload = {
        "prompt_version": JUDGE_PROMPT_VERSION,
        "system_prompt": SYSTEM_PROMPT,
        "schema": judge_json_schema(),
    }
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def judge_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_id",
            "schema_version",
            "judgeability",
            "concept_relation",
            "domain_match",
            "candidate_role",
            "machine_translation_suspected",
            "evidence_span",
            "reason",
        ],
        "properties": {
            "schema_id": {"const": JUDGE_SCHEMA_ID},
            "schema_version": {"const": JUDGE_SCHEMA_VERSION},
            "judgeability": {
                "enum": [
                    "JUDGEABLE",
                    "INSUFFICIENT_SNIPPET",
                    "INVALID_SNIPPET",
                    "AMBIGUOUS_CONCEPT",
                ]
            },
            "concept_relation": {
                "enum": ["SAME", "RELATED", "DIFFERENT", "UNCERTAIN"]
            },
            "domain_match": {"type": "boolean"},
            "candidate_role": {
                "enum": [
                    "TECHNICAL_TERM",
                    "GENERAL_WORD",
                    "NAME",
                    "QUOTE",
                    "METALANGUAGE",
                    "UNDETERMINED",
                ]
            },
            "machine_translation_suspected": {"type": "boolean"},
            "evidence_span": {"type": "string"},
            "reason": {"type": "string"},
        },
    }


__all__ = [
    "JUDGE_PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "build_judge_messages",
    "judge_json_schema",
    "prompt_sha256",
]
