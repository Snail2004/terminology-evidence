from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class RetrievalConfig:
    max_queries_per_candidate: int = 3
    results_per_query: int = 10
    max_unique_urls: int = 20
    max_fetches: int = 20
    min_fetch_coverage: float = 0.50
    restricted_source_domains: tuple[str, ...] = ()


@dataclass(frozen=True)
class SnippetConfig:
    words_before: int = 60
    words_after: int = 90
    min_words: int = 20
    max_words: int = 300


@dataclass(frozen=True)
class StatusConfig:
    min_same_clusters_for_attested: int = 2
    min_organizations_for_attested: int = 2
    require_tier_a_or_b: bool = True
    machine_translation_suspicion_policy: str = "FLAG_ONLY"


@dataclass(frozen=True)
class PricingConfig:
    policy_version: str = "attestation-cost-v1"
    currency: str = "USD"
    effective_date: str = "UNSPECIFIED"
    search_cost_per_request: tuple[tuple[str, float], ...] = ()
    judge_input_cost_per_million: tuple[tuple[str, float], ...] = ()
    judge_output_cost_per_million: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class AttestationConfig:
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    snippets: SnippetConfig = field(default_factory=SnippetConfig)
    status: StatusConfig = field(default_factory=StatusConfig)
    pricing: PricingConfig = field(default_factory=PricingConfig)
    search_provider_ids: tuple[str, ...] = ("brave",)
    judge_route_order: tuple[str, ...] = (
        "shopai",
        "ckey",
        "gemini_official",
    )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "AttestationConfig":
        retrieval = value.get("retrieval", {})
        snippets = value.get("snippets", {})
        status = value.get("status", {})
        pricing = value.get("pricing", {})
        result = cls(
            retrieval=RetrievalConfig(
                **{
                    **dict(retrieval),
                    "restricted_source_domains": tuple(
                        str(item)
                        for item in retrieval.get(
                            "restricted_source_domains", ()
                        )
                    ),
                }
            ),
            snippets=SnippetConfig(**dict(snippets)),
            status=StatusConfig(**dict(status)),
            pricing=PricingConfig(
                policy_version=str(
                    pricing.get("policy_version", "attestation-cost-v1")
                ),
                currency=str(pricing.get("currency", "USD")),
                effective_date=str(
                    pricing.get("effective_date", "UNSPECIFIED")
                ),
                search_cost_per_request=_price_pairs(
                    pricing.get("search_cost_per_request", {})
                ),
                judge_input_cost_per_million=_price_pairs(
                    pricing.get("judge_input_cost_per_million", {})
                ),
                judge_output_cost_per_million=_price_pairs(
                    pricing.get("judge_output_cost_per_million", {})
                ),
            ),
            search_provider_ids=tuple(
                str(item) for item in value.get("search_provider_ids", ("brave",))
            ),
            judge_route_order=tuple(
                str(item)
                for item in value.get(
                    "judge_route_order",
                    ("shopai", "ckey", "gemini_official"),
                )
            ),
        )
        result.validate()
        return result

    def validate(self) -> None:
        if self.retrieval.max_queries_per_candidate < 1:
            raise ValueError("max_queries_per_candidate must be positive")
        if self.retrieval.results_per_query < 1:
            raise ValueError("results_per_query must be positive")
        if self.retrieval.max_unique_urls < 1:
            raise ValueError("max_unique_urls must be positive")
        if self.retrieval.max_fetches < 1:
            raise ValueError("max_fetches must be positive")
        if not 0 <= self.retrieval.min_fetch_coverage <= 1:
            raise ValueError("min_fetch_coverage must be in [0, 1]")
        for domain in self.retrieval.restricted_source_domains:
            if (
                not domain
                or domain != domain.casefold()
                or any(character in domain for character in "/\\ :")
            ):
                raise ValueError("restricted source domain is not canonical")
        if self.snippets.min_words < 1:
            raise ValueError("min_words must be positive")
        if self.snippets.max_words < self.snippets.min_words:
            raise ValueError("max_words must be >= min_words")
        if self.status.min_same_clusters_for_attested < 1:
            raise ValueError("min_same_clusters_for_attested must be positive")
        if self.status.min_organizations_for_attested < 1:
            raise ValueError("min_organizations_for_attested must be positive")
        if self.status.machine_translation_suspicion_policy not in {
            "FLAG_ONLY",
            "DOWNWEIGHT",
            "EXCLUDE_FROM_STRONG_POSITIVE",
        }:
            raise ValueError(
                "machine_translation_suspicion_policy is unsupported"
            )
        if not self.search_provider_ids:
            raise ValueError("search_provider_ids must not be empty")
        if len(self.search_provider_ids) != len(set(self.search_provider_ids)):
            raise ValueError("search_provider_ids must be unique")
        if not self.judge_route_order:
            raise ValueError("judge_route_order must not be empty")
        if len(self.judge_route_order) != len(set(self.judge_route_order)):
            raise ValueError("judge_route_order must be unique")
        if not self.pricing.policy_version.strip():
            raise ValueError("pricing policy_version must not be empty")
        if not self.pricing.currency.strip():
            raise ValueError("pricing currency must not be empty")
        for _, price in (
            *self.pricing.search_cost_per_request,
            *self.pricing.judge_input_cost_per_million,
            *self.pricing.judge_output_cost_per_million,
        ):
            if price < 0:
                raise ValueError("pricing values must not be negative")

    def identity_payload(self) -> dict[str, Any]:
        return {
            "retrieval": {
                "max_queries_per_candidate": self.retrieval.max_queries_per_candidate,
                "results_per_query": self.retrieval.results_per_query,
                "max_unique_urls": self.retrieval.max_unique_urls,
                "max_fetches": self.retrieval.max_fetches,
                "min_fetch_coverage": self.retrieval.min_fetch_coverage,
                "restricted_source_domains": list(
                    self.retrieval.restricted_source_domains
                ),
            },
            "snippets": {
                "words_before": self.snippets.words_before,
                "words_after": self.snippets.words_after,
                "min_words": self.snippets.min_words,
                "max_words": self.snippets.max_words,
            },
            "status": {
                "min_same_clusters_for_attested": (
                    self.status.min_same_clusters_for_attested
                ),
                "min_organizations_for_attested": (
                    self.status.min_organizations_for_attested
                ),
                "require_tier_a_or_b": self.status.require_tier_a_or_b,
                "machine_translation_suspicion_policy": (
                    self.status.machine_translation_suspicion_policy
                ),
            },
            "pricing": {
                "policy_version": self.pricing.policy_version,
                "currency": self.pricing.currency,
                "effective_date": self.pricing.effective_date,
                "search_cost_per_request": dict(
                    self.pricing.search_cost_per_request
                ),
                "judge_input_cost_per_million": dict(
                    self.pricing.judge_input_cost_per_million
                ),
                "judge_output_cost_per_million": dict(
                    self.pricing.judge_output_cost_per_million
                ),
            },
            "search_provider_ids": list(self.search_provider_ids),
            "judge_route_order": list(self.judge_route_order),
        }


__all__ = [
    "AttestationConfig",
    "PricingConfig",
    "RetrievalConfig",
    "SnippetConfig",
    "StatusConfig",
]


def _price_pairs(value: Any) -> tuple[tuple[str, float], ...]:
    if not isinstance(value, Mapping):
        raise ValueError("pricing table must be an object")
    return tuple(
        sorted((str(key), float(price)) for key, price in value.items())
    )
