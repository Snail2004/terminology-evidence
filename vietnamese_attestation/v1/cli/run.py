from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

from vietnamese_attestation.v1.config import (
    AttestationConfig,
)
from vietnamese_attestation.v1.contracts.shared import (
    SHARED_FROZEN_CANDIDATE_SCHEMA_ID,
    adapt_shared_frozen_candidate,
    project_shared_attestation_package,
)
from vietnamese_attestation.v1.dataset import (
    load_official_frozen_candidate_set,
)
from vietnamese_attestation.v1.judging import (
    CKeyJudgeProvider,
    FallbackJudgeRouter,
    GeminiOfficialJudgeProvider,
    JudgeSchemaError,
    JudgeTransportError,
    ShopAiJudgeProvider,
    StaticJudgeProvider,
)
from vietnamese_attestation.v1.retrieval import (
    BraveSearchProvider,
    DiskFetchCache,
    HttpDocumentFetcher,
    StaticDocumentFetcher,
    StaticSearchProvider,
)
from vietnamese_attestation.v1.retrieval.urls import (
    canonicalize_url,
)
from vietnamese_attestation.v1.runtime.engine import (
    AttestationEngine,
)
from vietnamese_attestation.v1.strict_json import load_strict_json_object


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run Vietnamese Attestation Evidence V1."
    )
    parser.add_argument("--candidate", type=Path)
    parser.add_argument(
        "--development-input",
        action="store_true",
        help="Explicitly permit a loose shared candidate for fixture-only work.",
    )
    parser.add_argument("--dataset-release-manifest", type=Path)
    parser.add_argument("--dataset-release-receipt", type=Path)
    parser.add_argument("--dataset-release-receipt-sha256")
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--official-candidate-id")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--offline-fixture", type=Path)
    parser.add_argument("--cache-root", type=Path)
    parser.add_argument("--run-store-root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    candidate = _input_candidate(args, parser)
    config = (
        AttestationConfig.from_mapping(_object(args.config, "config"))
        if args.config
        else AttestationConfig()
    )
    if args.offline_fixture is not None:
        engine = _offline_engine(
            fixture=_object(args.offline_fixture, "offline fixture"),
            config=config,
            run_store_root=args.run_store_root,
        )
    else:
        if args.cache_root is None:
            parser.error("--cache-root is required for live retrieval")
        if args.run_store_root is None:
            parser.error("--run-store-root is required for live retrieval")
        engine = _live_engine(
            config=config,
            cache_root=args.cache_root,
            run_store_root=args.run_store_root,
        )
    shared_input = (
        candidate.get("schema_id") == SHARED_FROZEN_CANDIDATE_SCHEMA_ID
    )
    internal_candidate = (
        adapt_shared_frozen_candidate(candidate) if shared_input else candidate
    )
    internal_package = engine.run(internal_candidate)
    package = (
        project_shared_attestation_package(internal_package, candidate)
        if shared_input
        else internal_package
    )
    raw_package = (
        json.dumps(
            package,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic_text(args.output, raw_package)
    if args.run_store_root is not None:
        execution_id = internal_package["provenance"][
            "attestation_execution_id"
        ]
        execution_root = (
            args.run_store_root
            / "runs"
            / execution_id
        )
        if shared_input:
            internal_raw = (
                json.dumps(
                    internal_package,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
            _write_atomic_text(execution_root / "package.json", internal_raw)
            _write_atomic_text(
                execution_root / "shared-package.json", raw_package
            )
        else:
            _write_atomic_text(execution_root / "package.json", raw_package)
    return 0


def _offline_engine(
    *,
    fixture: Mapping[str, Any],
    config: AttestationConfig,
    run_store_root: Path | None,
) -> AttestationEngine:
    provider_id = str(fixture.get("search_provider_id", "fixture_search"))
    search = StaticSearchProvider(
        provider_id,
        fixture["search_results_by_query_class"],
    )
    documents = {
        canonicalize_url(url): (
            str(row["content_type"]),
            str(row["text"]),
        )
        for url, row in fixture["documents"].items()
    }
    judge_routes = []
    for raw in fixture["judge_routes"]:
        payloads = {
            str(key): _offline_judge_value(value)
            for key, value in raw["payloads_by_evidence_id"].items()
        }
        judge_routes.append(
            StaticJudgeProvider(
                route_id=str(raw["route_id"]),
                model_id=str(raw["model_id"]),
                payloads_by_evidence_id=payloads,
            )
        )
    offline_config = AttestationConfig(
        retrieval=config.retrieval,
        snippets=config.snippets,
        status=config.status,
        pricing=config.pricing,
        search_provider_ids=(provider_id,),
        judge_route_order=tuple(route.route_id for route in judge_routes),
    )
    return AttestationEngine(
        search_providers=[search],
        document_fetcher=StaticDocumentFetcher(documents),
        judge_router=FallbackJudgeRouter(judge_routes),
        config=offline_config,
        source_overrides=fixture.get("source_overrides", {}),
        clock=_fixed_clock(fixture.get("timestamps")),
        audit_store_root=run_store_root,
    )


def _offline_judge_value(value: Any) -> Any:
    if not isinstance(value, Mapping) or "error" not in value:
        return value
    error = str(value["error"])
    error_type = str(value.get("error_type", "transport"))
    if error_type == "transport":
        return JudgeTransportError("offline_transport_failure", error)
    if error_type == "schema":
        return JudgeSchemaError("offline_schema_failure", error)
    raise ValueError("offline judge error_type must be transport or schema")


def _live_engine(
    *,
    config: AttestationConfig,
    cache_root: Path,
    run_store_root: Path,
) -> AttestationEngine:
    brave_key = _required_env("BRAVE_SEARCH_API_KEY")
    shopai_key = _required_env("SHOPAI_API_KEY")
    ckey_key = _required_env("CKEY_API_KEY")
    ckey_base_url = _required_env("CKEY_BASE_URL")
    gemini_key = _required_env("GEMINI_API_KEY")
    search = BraveSearchProvider(brave_key)
    router = FallbackJudgeRouter(
        [
            ShopAiJudgeProvider(
                api_key=shopai_key,
                model_id=os.environ.get(
                    "SHOPAI_JUDGE_MODEL", "gemini-3.5-flash"
                ),
            ),
            CKeyJudgeProvider(
                api_key=ckey_key,
                base_url=ckey_base_url,
                model_id=os.environ.get(
                    "CKEY_JUDGE_MODEL", "google/gemini-3.5-flash"
                ),
            ),
            GeminiOfficialJudgeProvider(
                api_key=gemini_key,
                model_id=os.environ.get(
                    "GEMINI_JUDGE_MODEL", "gemini-3.5-flash"
                ),
            ),
        ]
    )
    return AttestationEngine(
        search_providers=[search],
        document_fetcher=HttpDocumentFetcher(
            cache=DiskFetchCache(cache_root)
        ),
        judge_router=router,
        config=config,
        audit_store_root=run_store_root,
    )


def _fixed_clock(value: Any):
    timestamps = list(value or ["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z"])
    if len(timestamps) != 2:
        raise ValueError("offline fixture must provide exactly two timestamps")
    iterator = iter(str(item) for item in timestamps)
    return lambda: next(iterator)


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def _input_candidate(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> Mapping[str, Any]:
    official_values = {
        "--dataset-release-manifest": args.dataset_release_manifest,
        "--dataset-release-receipt": args.dataset_release_receipt,
        "--dataset-release-receipt-sha256": (
            args.dataset_release_receipt_sha256
        ),
        "--candidate-root": args.candidate_root,
        "--official-candidate-id": args.official_candidate_id,
    }
    official_requested = any(value is not None for value in official_values.values())
    if args.candidate is not None and official_requested:
        parser.error("--candidate cannot be combined with official Dataset input")
    if args.candidate is None and not official_requested:
        parser.error("provide --candidate or the complete official Dataset input set")
    if official_requested:
        missing = [name for name, value in official_values.items() if value is None]
        if missing:
            parser.error("official Dataset input requires " + ", ".join(missing))
        if args.development_input:
            parser.error("--development-input cannot be used with official Dataset input")
        official = load_official_frozen_candidate_set(
            args.dataset_release_manifest,
            args.dataset_release_receipt,
            args.candidate_root,
            expected_receipt_sha256=args.dataset_release_receipt_sha256,
        )
        matches = [
            candidate
            for candidate in official.candidates
            if candidate["candidate_key"]["candidate_id"]
            == args.official_candidate_id
        ]
        if len(matches) != 1:
            parser.error("official candidate ID is absent or ambiguous")
        return matches[0]

    if args.offline_fixture is None:
        parser.error(
            "a loose candidate is fixture-only; live execution requires an "
            "official Dataset release"
        )
    candidate = _object(args.candidate, "candidate")
    if (
        candidate.get("schema_id") == SHARED_FROZEN_CANDIDATE_SCHEMA_ID
        and candidate.get("binding_status") == "COMPLETE"
        and not args.development_input
    ):
        parser.error(
            "a COMPLETE shared candidate requires an official Dataset release; "
            "use --development-input only for fixture work"
        )
    return candidate


def _object(path: Path | None, label: str) -> Mapping[str, Any]:
    if path is None:
        raise ValueError(f"{label} path is missing")
    try:
        return load_strict_json_object(path)
    except ValueError as exc:
        raise ValueError(f"invalid strict {label} JSON") from exc


def _write_atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(value, encoding="utf-8")
    os.replace(tmp, path)


if __name__ == "__main__":
    raise SystemExit(main())
