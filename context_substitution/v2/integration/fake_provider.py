from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from context_substitution.v2.contracts.common import REQUIRED_SAME_SENSE_CONTEXT_TYPES
from context_substitution.v2.providers.base import (
    ContextProviderRoute,
    FailoverStructuredModel,
    ProviderRawResponse,
)
from context_substitution.v2.providers.ledger import ProviderResponseLedger
from context_substitution.v2.runtime.engine import run_d2l_context_substitution
from context_substitution.v2.integration.common import seal_object


FAKE_SUMMARY_SCHEMA_ID = "D2LContextSubstitutionFakeProviderSummaryV1"
FAKE_SUMMARY_SCHEMA_VERSION = "1.0.0"

_SCENARIOS = (
    "pairwise_pass",
    "pairwise_pass",
    "pairwise_pass",
    "minor",
    "fail",
    "invalid_trial_retry",
    "abstain",
    "malformed_failover",
    "judge_disagreement",
    "wrong_sense",
    "pass",
    "minor",
    "fail",
    "pass",
    "pass",
)


def run_fake_provider_pilot(
    input_payload: Mapping[str, Any], *, ledger_root: Path
) -> dict[str, Any]:
    terms = list(input_payload["terms"])
    candidate_ids = sorted(
        target["candidate_target_id"]
        for term in terms
        for target in term["candidate_targets"]
    )
    if len(terms) != 5 or len(candidate_ids) != 15:
        raise ValueError("fake-provider pilot requires exactly 5 senses and 15 candidates")
    scenario_by_candidate = dict(zip(candidate_ids, _SCENARIOS, strict=True))
    term_index = {str(term["term_id"]): index for index, term in enumerate(terms)}
    sender_factory = _FakeSenderFactory(
        scenario_by_candidate=scenario_by_candidate,
        term_index=term_index,
    )
    routes = [
        ContextProviderRoute(
            route_id=route_id,
            model_id=model_id,
            model_family=family,
            independence_group=group,
            sender=sender_factory.sender(route_id),
        )
        for route_id, model_id, family, group in (
            ("shopaikey_gemini", "fake-shopai-pinned-v1", "fake-shopai", "shopai"),
            ("ckey_gemini", "fake-ckey-pinned-v1", "fake-ckey", "ckey"),
            ("gemini_official", "fake-google-pinned-v1", "fake-google", "google"),
        )
    ]
    model = FailoverStructuredModel(
        routes,
        response_ledger=ProviderResponseLedger(Path(ledger_root)),
        audit_run_id="fake-pilot:" + str(input_payload["integrity"]["input_sha256"][:24]),
    )
    run = run_d2l_context_substitution(input_payload, model)
    summary = _summarize(run, scenario_by_candidate=scenario_by_candidate)
    return {"run": run, "summary": summary}


class _FakeSenderFactory:
    def __init__(
        self,
        *,
        scenario_by_candidate: Mapping[str, str],
        term_index: Mapping[str, int],
    ) -> None:
        self.scenario_by_candidate = dict(scenario_by_candidate)
        self.term_index = dict(term_index)

    def sender(self, route_id: str):
        def send(
            *,
            system_prompt: str,
            user_payload_json: str,
            response_schema: Mapping[str, Any],
            max_output_tokens: int,
            tag: str,
        ) -> ProviderRawResponse:
            del system_prompt, response_schema, max_output_tokens
            request = json.loads(user_payload_json)
            response = self._response(route_id=route_id, tag=tag, request=request)
            return ProviderRawResponse(
                text=json.dumps(response, ensure_ascii=False, sort_keys=True),
                payload=response,
                request_id=f"fake:{route_id}:{tag}",
                input_tokens=11,
                output_tokens=7,
                reasoning_tokens=0,
                latency_ms=1,
            )

        return send

    def _response(
        self, *, route_id: str, tag: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        if tag.startswith("selector:"):
            return self._selector(request)
        if tag.startswith("trial:"):
            return self._trial(request)
        if tag.startswith("trial-gate:"):
            return self._trial_gate(request, tag=tag)
        if tag.startswith("context-judge:"):
            candidate_id = str(request["candidate"]["candidate_id"])
            if (
                self.scenario_by_candidate[candidate_id] == "malformed_failover"
                and route_id == "shopaikey_gemini"
            ):
                return {"malformed": True}
            return self._judge(request, route_id=route_id)
        if tag.startswith("contrastive:"):
            return {
                "context_id": request["contrastive_context"]["context_id"],
                "candidate_id": request["candidate"]["candidate_id"],
                "tested_sense_id": request["tested_sense_id"],
                "result": "OUT_OF_SCOPE",
                "reason": "deterministic fake contrastive boundary",
            }
        if tag.startswith("pairwise:"):
            return {
                "candidate_a_id": request["candidate_a"]["candidate_id"],
                "candidate_b_id": request["candidate_b"]["candidate_id"],
                "preferred": "TIE",
                "confidence": "MEDIUM",
                "reason": "deterministic fake pairwise tie",
            }
        raise AssertionError(f"unexpected fake-provider tag: {tag}")

    def _selector(self, request: Mapping[str, Any]) -> dict[str, Any]:
        term = request["term"]
        index = self.term_index[str(term["term_id"])]
        annotations = []
        for context_index, context in enumerate(request["contexts"]):
            if context_index < 5:
                relation = "SAME_SENSE"
                context_type = (
                    "definition"
                    if index == 4
                    else REQUIRED_SAME_SENSE_CONTEXT_TYPES[context_index]
                )
            elif index == 3:
                relation = "AMBIGUOUS"
                context_type = "unknown"
            else:
                relation = "CONTRASTIVE"
                context_type = "contrastive"
            annotations.append(
                {
                    "context_id": context["context_id"],
                    "sense_relation": relation,
                    "context_type": context_type,
                    "judgeability": "JUDGEABLE",
                    "reason": "deterministic fake selector classification",
                }
            )
        return {
            "term_id": term["term_id"],
            "sense_id": term["sense_id"],
            "scope_id": term["scope_id"],
            "annotations": annotations,
        }

    @staticmethod
    def _trial(request: Mapping[str, Any]) -> dict[str, Any]:
        candidate = str(request["candidate_translation"])
        return {
            "context_id": request["context_id"],
            "candidate_id": request["candidate_id"],
            "trial_translation": f"Bản thử dùng {candidate} trong ngữ cảnh.",
            "candidate_surface_used": candidate,
            "candidate_usage_confirmed": True,
            "applied_expansion": None,
        }

    def _trial_gate(
        self, request: Mapping[str, Any], *, tag: str
    ) -> dict[str, Any]:
        candidate_id = str(request["candidate"]["candidate_id"])
        scenario = self.scenario_by_candidate[candidate_id]
        attempt = int(tag.rsplit(":", 1)[-1])
        invalid = scenario == "invalid_trial_retry" and attempt == 1
        return {
            "context_id": request["trial"]["context_id"],
            "candidate_id": candidate_id,
            "trial_status": "EXTERNAL_TRANSLATION_ERROR" if invalid else "VALID",
            "candidate_usage_valid": True,
            "external_translation_error": invalid,
            "missing_content": False,
            "added_content": False,
            "reason": "deterministic fake trial gate",
        }

    def _judge(
        self, request: Mapping[str, Any], *, route_id: str
    ) -> dict[str, Any]:
        candidate_id = str(request["candidate"]["candidate_id"])
        scenario = self.scenario_by_candidate[candidate_id]
        surface = str(request["candidate"]["candidate_translation"])
        if scenario == "abstain":
            return {
                "context_id": request["source_context"]["context_id"],
                "candidate_id": candidate_id,
                "judgeability": "INSUFFICIENT_CONTEXT",
                "scores": None,
                "flags": {
                    "semantic_contradiction": False,
                    "wrong_sense": False,
                    "candidate_induced_distortion": False,
                    "translator_external_error": False,
                    "insufficient_context": True,
                },
                "evidence": None,
                "variant_observation": {
                    "surface_used": surface,
                    "requires_expansion": False,
                    "suggested_expansion": None,
                },
                "reason": "deterministic fake abstention",
            }
        if scenario == "judge_disagreement":
            scores = (
                _scores("fail")
                if route_id != "shopaikey_gemini"
                else _scores("threshold")
            )
        elif scenario == "minor":
            scores = _scores("minor")
        elif scenario in {"fail", "wrong_sense"}:
            scores = _scores("fail")
        elif scenario == "pairwise_pass":
            scores = _scores("pairwise")
        else:
            scores = _scores("pass")
        return {
            "context_id": request["source_context"]["context_id"],
            "candidate_id": candidate_id,
            "judgeability": "JUDGEABLE",
            "scores": scores,
            "flags": {
                "semantic_contradiction": False,
                "wrong_sense": scenario == "wrong_sense",
                "candidate_induced_distortion": False,
                "translator_external_error": False,
                "insufficient_context": False,
            },
            "evidence": {
                "source_span": "source",
                "target_span": f"Bản thử dùng {surface} trong ngữ cảnh.",
            },
            "variant_observation": {
                "surface_used": surface,
                "requires_expansion": False,
                "suggested_expansion": None,
            },
            "reason": "deterministic fake contextual judgement",
        }


def _scores(kind: str) -> dict[str, int]:
    return {
        "pass": {
            "semantic_equivalence": 4,
            "domain_sense_fit": 2,
            "collocation_naturalness": 2,
            "grammatical_fit": 1,
            "no_candidate_induced_distortion": 1,
        },
        "pairwise": {
            "semantic_equivalence": 4,
            "domain_sense_fit": 2,
            "collocation_naturalness": 1,
            "grammatical_fit": 1,
            "no_candidate_induced_distortion": 1,
        },
        "threshold": {
            "semantic_equivalence": 3,
            "domain_sense_fit": 2,
            "collocation_naturalness": 1,
            "grammatical_fit": 1,
            "no_candidate_induced_distortion": 1,
        },
        "minor": {
            "semantic_equivalence": 3,
            "domain_sense_fit": 1,
            "collocation_naturalness": 1,
            "grammatical_fit": 1,
            "no_candidate_induced_distortion": 1,
        },
        "fail": {
            "semantic_equivalence": 2,
            "domain_sense_fit": 1,
            "collocation_naturalness": 1,
            "grammatical_fit": 1,
            "no_candidate_induced_distortion": 0,
        },
    }[kind]


def _summarize(
    run: Mapping[str, Any], *, scenario_by_candidate: Mapping[str, str]
) -> dict[str, Any]:
    candidates = list(run["candidates"])
    labels = {
        row["label"]
        for candidate in candidates
        for row in candidate["context_results"]
    }
    flags = {flag for candidate in candidates for flag in candidate["context_flags"]}
    attempts = list(run["provider_attempts"])
    coverage = {
        "trial_valid": any(candidate["context_results"] for candidate in candidates),
        "invalid_trial_then_retry": any(
            len(row["trial_attempts"]) == 2
            for candidate in candidates
            for row in candidate["context_results"]
        ),
        "judge_pass": "PASS" in labels,
        "judge_minor": "MINOR" in labels,
        "judge_fail": "FAIL" in labels,
        "judge_abstain": any(candidate["excluded_contexts"] for candidate in candidates),
        "judge_disagreement": any(candidate["judge_disagreement"] for candidate in candidates),
        "malformed_provider_response": any(
            not row["accepted"] and row["failure_kind"] is not None for row in attempts
        ),
        "provider_failover": any(
            row["accepted"] and row["provider_route_id"] != "shopaikey_gemini"
            for row in attempts
        ),
        "pairwise_tie_break": any(
            row["status"] == "COMPLETED" for row in run["pairwise_observations"]
        ),
        "wrong_sense": any(
            "WRONG_SENSE" in row["local_hard_flags"]
            for candidate in candidates
            for row in candidate["context_results"]
        ),
        "missing_contrastive_context": "MISSING_CONTRASTIVE_CONTEXT" in flags,
        "incomplete_context_type_coverage": "INCOMPLETE_CONTEXT_TYPE_COVERAGE" in flags,
        "insufficient_valid_context": "INSUFFICIENT_VALID_SAME_SENSE_CONTEXTS" in flags,
    }
    missing = sorted(name for name, present in coverage.items() if not present)
    if missing:
        raise ValueError(f"fake-provider scenario coverage is incomplete: {missing}")
    if len(candidates) != 15 or any(
        candidate["final_glossary_decision"] is not None for candidate in candidates
    ):
        raise ValueError("fake-provider run violated candidate count or decision neutrality")
    unsafe = [
        candidate["candidate_id"]
        for candidate in candidates
        if (
            {
                "MISSING_CONTRASTIVE_CONTEXT",
                "INCOMPLETE_CONTEXT_TYPE_COVERAGE",
                "INSUFFICIENT_VALID_SAME_SENSE_CONTEXTS",
            }
            & set(candidate["context_flags"])
            and candidate["recommendation_to_global_validator"]
            == "ELIGIBLE_FOR_COMBINATION"
        )
    ]
    if unsafe:
        raise ValueError(f"evidence-incomplete candidates became eligible: {unsafe}")
    summary = {
        "schema_id": FAKE_SUMMARY_SCHEMA_ID,
        "schema_version": FAKE_SUMMARY_SCHEMA_VERSION,
        "status": "PASS",
        "candidate_count": len(candidates),
        "candidate_scenarios": dict(sorted(scenario_by_candidate.items())),
        "scenario_coverage": coverage,
        "provider_attempt_count": len(attempts),
        "accepted_attempt_count": sum(bool(row["accepted"]) for row in attempts),
        "rejected_attempt_count": sum(not bool(row["accepted"]) for row in attempts),
        "raw_response_storage_complete": all(
            row["raw_response_storage_status"] == "STORED" for row in attempts
        ),
        "source_run_sha256": run["integrity"]["run_sha256"],
        "final_glossary_decision": None,
        "integrity": {},
    }
    return seal_object(summary, integrity_key="summary_sha256")
