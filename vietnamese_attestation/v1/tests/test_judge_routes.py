from __future__ import annotations

import json

from .conftest import judge_payload

from vietnamese_attestation.v1.judging import (
    CKeyJudgeProvider,
    FallbackJudgeRouter,
    GeminiOfficialJudgeProvider,
    JudgeRequest,
    JudgeSchemaError,
    JudgeTransportError,
    ShopAiJudgeProvider,
    StaticJudgeProvider,
)


def _request() -> JudgeRequest:
    return JudgeRequest(
        evidence_id="evidence-1",
        definition_en="A trained model produces outputs for new inputs.",
        scope_id="machine_learning",
        candidate_vi="suy luận",
        snippet_original="Suy luận dùng mô hình để tạo dự đoán.",
        snippet_masked="[TERM] dùng mô hình để tạo dự đoán.",
        source_type="academic",
    )


def test_router_falls_back_only_for_transport_or_schema_failures() -> None:
    first = StaticJudgeProvider(
        route_id="shopai",
        model_id="gemini-a",
        payloads_by_evidence_id={
            "*": JudgeTransportError("timeout", "timed out")
        },
    )
    second = StaticJudgeProvider(
        route_id="ckey",
        model_id="gemini-b",
        payloads_by_evidence_id={
            "*": JudgeSchemaError("invalid_json", "invalid JSON")
        },
    )
    third = StaticJudgeProvider(
        route_id="gemini_official",
        model_id="gemini-c",
        payloads_by_evidence_id={"*": judge_payload()},
    )
    result, attempts = FallbackJudgeRouter([first, second, third]).judge(
        _request()
    )
    assert result.route_id == "gemini_official"
    assert [row["outcome"] for row in attempts] == [
        "TRANSPORT_FAILED",
        "SCHEMA_FAILED",
        "ACCEPTED",
    ]


def test_valid_negative_semantic_result_does_not_fallback() -> None:
    first = StaticJudgeProvider(
        route_id="shopai",
        model_id="gemini-a",
        payloads_by_evidence_id={"*": judge_payload("DIFFERENT")},
    )
    second = StaticJudgeProvider(
        route_id="ckey",
        model_id="gemini-b",
        payloads_by_evidence_id={"*": judge_payload()},
    )
    result, attempts = FallbackJudgeRouter([first, second]).judge(_request())
    assert result.payload["concept_relation"] == "DIFFERENT"
    assert len(attempts) == 1
    assert second.calls == []


def test_hallucinated_evidence_span_falls_back_as_schema_failure() -> None:
    invalid = judge_payload()
    invalid["evidence_span"] = "khong co trong snippet"
    first = StaticJudgeProvider(
        route_id="shopai",
        model_id="gemini-a",
        payloads_by_evidence_id={"*": invalid},
    )
    second = StaticJudgeProvider(
        route_id="ckey",
        model_id="gemini-b",
        payloads_by_evidence_id={"*": judge_payload()},
    )
    result, attempts = FallbackJudgeRouter([first, second]).judge(_request())
    assert result.route_id == "ckey"
    assert [row["outcome"] for row in attempts] == [
        "SCHEMA_FAILED",
        "ACCEPTED",
    ]


def test_three_live_route_shapes_are_supported_without_network() -> None:
    captured: list[tuple[str, dict[str, str]]] = []

    def openai_post(url, headers, payload, timeout):
        del payload, timeout
        captured.append((url, dict(headers)))
        return {
            "choices": [
                {"message": {"content": json.dumps(judge_payload())}}
            ],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7},
        }

    def gemini_post(url, headers, payload, timeout):
        del payload, timeout
        captured.append((url, dict(headers)))
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": json.dumps(judge_payload())}]
                    }
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 13,
                "candidatesTokenCount": 5,
            },
        }

    shop = ShopAiJudgeProvider(api_key="secret-shop", json_post=openai_post)
    ckey = CKeyJudgeProvider(
        api_key="secret-ckey",
        base_url="https://ckey.example/v1",
        json_post=openai_post,
    )
    official = GeminiOfficialJudgeProvider(
        api_key="secret-google", json_post=gemini_post
    )
    assert shop.judge(_request()).input_tokens == 11
    assert ckey.judge(_request()).output_tokens == 7
    assert official.judge(_request()).input_tokens == 13
    assert captured[0][0].endswith("/chat/completions")
    assert captured[1][0] == "https://ckey.example/v1/chat/completions"
    assert "secret-google" not in captured[2][0]
    assert captured[2][1]["x-goog-api-key"] == "secret-google"
