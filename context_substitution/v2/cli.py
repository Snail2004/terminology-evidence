from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from context_substitution.v2.contracts.run import (
    context_substitution_to_measurements,
    validate_context_substitution_run,
)
from context_substitution.v2.dataset.reviewed_support import (
    reviewed_support_to_context_substitution_input,
    validate_reviewed_support_bundle,
)
from context_substitution.v2.evaluation.gold import evaluate_gold_cases
from context_substitution.v2.integration.authority import validate_authority
from context_substitution.v2.integration.common import load_json, write_json
from context_substitution.v2.integration.development_fixtures import (
    build_development_frozen_candidate_fixtures,
)
from context_substitution.v2.integration.fake_provider import run_fake_provider_pilot
from context_substitution.v2.integration.pilot import run_zero_api_pilot_smoke
from context_substitution.v2.integration.projection import (
    build_projection_binding_from_ledger,
    write_context_evidence_package_set,
)
from context_substitution.v2.integration.replay import replay_context_run
from context_substitution.v2.integration.release import build_integration_release
from context_substitution.v2.providers.base import FailoverStructuredModel
from context_substitution.v2.providers.google import GoogleRouteSettings
from context_substitution.v2.providers.ledger import ProviderResponseLedger
from context_substitution.v2.runtime.calibration import (
    DEVELOPMENT_HEURISTIC_POLICY,
    frozen_validation_policy,
)
from context_substitution.v2.runtime.engine import run_d2l_context_substitution


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Context Substitution V2.2 standalone integration CLI"
    )
    commands = root.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("reviewed-support-validate")
    _add_source_args(validate, require_split=False)

    adapt = commands.add_parser("reviewed-support-to-runtime")
    _add_source_args(adapt, require_split=True)
    adapt.add_argument("--review-artifact", type=Path)
    adapt.add_argument("--output", type=Path, required=True)
    adapt.add_argument("--receipt", type=Path, required=True)

    run = commands.add_parser("context-run")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--routes", type=Path, required=True)
    run.add_argument("--ledger-root", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--allow-api", action="store_true")
    run.add_argument("--candidate-target-id", action="append")
    run.add_argument(
        "--evaluation-mode",
        choices=("DEVELOPMENT", "FROZEN_TEST_SET"),
        default="DEVELOPMENT",
    )
    run.add_argument("--calibration-artifact", type=Path)
    run.add_argument("--calibration-file-sha256")

    run_validate = commands.add_parser("run-validate")
    run_validate.add_argument("--run", type=Path, required=True)

    projection = commands.add_parser("project-context-evidence")
    projection.add_argument("--run", type=Path, required=True)
    projection.add_argument("--frozen-candidates", type=Path, required=True)
    projection.add_argument("--ledger", type=Path, required=True)
    projection.add_argument("--output-directory", type=Path, required=True)

    development_freeze = commands.add_parser("development-fixture-freeze")
    development_freeze.add_argument("--input", type=Path, required=True)
    development_freeze.add_argument("--run", type=Path, required=True)
    development_freeze.add_argument("--ledger", type=Path, required=True)
    development_freeze.add_argument("--output", type=Path, required=True)

    commands.add_parser("authority-validate")

    gold = commands.add_parser("gold-evaluate")
    gold.add_argument("--cases", type=Path, required=True)
    gold.add_argument("--output", type=Path, required=True)

    pilot = commands.add_parser("pilot-smoke")
    pilot.add_argument("--pilot-directory", type=Path, required=True)
    pilot.add_argument("--pilot-zip", type=Path, required=True)
    pilot.add_argument("--parent-directory", type=Path, required=True)
    pilot.add_argument("--parent-zip", type=Path, required=True)
    pilot.add_argument("--output", type=Path, required=True)

    fake = commands.add_parser("fake-provider-pilot")
    fake.add_argument("--input", type=Path, required=True)
    fake.add_argument("--ledger-root", type=Path, required=True)
    fake.add_argument("--run-output", type=Path, required=True)
    fake.add_argument("--summary-output", type=Path, required=True)

    replay = commands.add_parser("replay-validate")
    replay.add_argument("--input", type=Path, required=True)
    replay.add_argument("--run", type=Path, required=True)
    replay.add_argument("--ledger-root", type=Path, required=True)
    replay.add_argument("--output", type=Path, required=True)

    release = commands.add_parser("integration-release")
    release.add_argument("--evidence-root", type=Path, required=True)
    release.add_argument("--output-directory", type=Path, required=True)

    measurements = commands.add_parser("measurements-project")
    measurements.add_argument("--run", type=Path, required=True)
    measurements.add_argument("--output", type=Path, required=True)
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "reviewed-support-validate":
        result = validate_reviewed_support_bundle(args.source, **_source_kwargs(args))
        _print(result)
        return 0
    if args.command == "reviewed-support-to-runtime":
        result = reviewed_support_to_context_substitution_input(
            args.source,
            source_split=args.source_split,
            review_artifact=args.review_artifact,
            **_source_kwargs(args),
        )
        write_json(args.output, result["input"])
        write_json(args.receipt, result["receipt"])
        _print(
            {
                "input": str(args.output.resolve()),
                "input_sha256": result["input"]["integrity"]["input_sha256"],
                "receipt": str(args.receipt.resolve()),
                "receipt_sha256": result["receipt"]["receipt_sha256"],
            }
        )
        return 0
    if args.command == "context-run":
        if not args.allow_api:
            raise SystemExit("context-run requires explicit --allow-api")
        input_payload = load_json(args.input)
        settings = _route_settings(load_json(args.routes))
        model = FailoverStructuredModel(
            [item.build() for item in settings],
            response_ledger=ProviderResponseLedger(args.ledger_root),
            audit_run_id="api:" + input_payload["integrity"]["input_sha256"][:24],
        )
        if args.evaluation_mode == "FROZEN_TEST_SET":
            if args.calibration_artifact is None:
                raise SystemExit("FROZEN_TEST_SET requires --calibration-artifact")
            policy = frozen_validation_policy(
                calibration_artifact=args.calibration_artifact,
                expected_physical_sha256=args.calibration_file_sha256,
            )
        else:
            if args.calibration_artifact is not None:
                raise SystemExit("development mode cannot claim a calibration artifact")
            policy = DEVELOPMENT_HEURISTIC_POLICY
        result = run_d2l_context_substitution(
            input_payload,
            model,
            candidate_target_ids=args.candidate_target_id,
            threshold_policy=policy,
            evaluation_mode=args.evaluation_mode,
        )
        write_json(args.output, result)
        _print(
            {
                "output": str(args.output.resolve()),
                "run_sha256": result["integrity"]["run_sha256"],
                "usage": result["usage"],
            }
        )
        return 0
    if args.command == "run-validate":
        result = validate_context_substitution_run(load_json(args.run))
        _print(
            {
                "status": "PASS",
                "run_sha256": result["integrity"]["run_sha256"],
                "candidate_count": len(result["candidates"]),
            }
        )
        return 0
    if args.command == "project-context-evidence":
        run_payload = load_json(args.run)
        frozen_set = load_json(args.frozen_candidates)
        result = write_context_evidence_package_set(
            run_payload=run_payload,
            frozen_candidates=_frozen_candidates(frozen_set),
            binding=build_projection_binding_from_ledger(
                run_payload=run_payload,
                ledger_path=args.ledger,
            ),
            output_directory=args.output_directory,
        )
        _print(
            {
                "output_directory": str(args.output_directory.resolve()),
                "package_count": result["package_count"],
                "status": result["status"],
                "manifest_sha256": result["integrity"]["manifest_sha256"],
            }
        )
        return 0
    if args.command == "development-fixture-freeze":
        run_payload = load_json(args.run)
        binding = build_projection_binding_from_ledger(
            run_payload=run_payload,
            ledger_path=args.ledger,
        )
        result = build_development_frozen_candidate_fixtures(
            input_payload=load_json(args.input),
            run_payload=run_payload,
            started_at=binding["started_at"],
            completed_at=binding["completed_at"],
        )
        write_json(args.output, result)
        _print(
            {
                "output": str(args.output.resolve()),
                "status": result["status"],
                "candidate_count": result["candidate_count"],
                "fixture_set_sha256": result["integrity"]["fixture_set_sha256"],
            }
        )
        return 0
    if args.command == "authority-validate":
        _print(validate_authority())
        return 0
    if args.command == "gold-evaluate":
        raw = load_json(args.cases)
        cases = raw["cases"] if isinstance(raw, Mapping) and "cases" in raw else raw
        result = evaluate_gold_cases(cases)
        write_json(args.output, result)
        _print(result)
        return 0
    if args.command == "pilot-smoke":
        result = run_zero_api_pilot_smoke(
            pilot_directory=args.pilot_directory,
            pilot_zip=args.pilot_zip,
            parent_directory=args.parent_directory,
            parent_zip=args.parent_zip,
        )
        write_json(args.output, result)
        _print(result)
        return 0
    if args.command == "fake-provider-pilot":
        result = run_fake_provider_pilot(
            load_json(args.input), ledger_root=args.ledger_root
        )
        write_json(args.run_output, result["run"])
        write_json(args.summary_output, result["summary"])
        _print(result["summary"])
        return 0
    if args.command == "replay-validate":
        result = replay_context_run(
            input_payload=load_json(args.input),
            original_run=load_json(args.run),
            ledger_root=args.ledger_root,
        )
        write_json(args.output, result)
        _print(result)
        return 0
    if args.command == "integration-release":
        result = build_integration_release(
            source_root=Path(__file__).resolve().parents[1],
            evidence_root=args.evidence_root,
            output_directory=args.output_directory,
            commands=_integration_commands(),
            known_gaps=(
                "human-reviewed frozen artifact is not available",
                "API canary was not run",
                "validation/test dataset splits and the full 150-sense API run were not run",
                "Global Validator is not implemented; package set remains on HOLD",
            ),
        )
        _print(result)
        return 0
    if args.command == "measurements-project":
        run = validate_context_substitution_run(load_json(args.run))
        result = context_substitution_to_measurements(run)
        write_json(args.output, result)
        _print({"output": str(args.output.resolve())})
        return 0
    raise AssertionError("unreachable")


def _add_source_args(value: argparse.ArgumentParser, *, require_split: bool) -> None:
    value.add_argument("--source", type=Path, required=True)
    value.add_argument("--parent-v3", type=Path)
    value.add_argument("--expected-zip-sha256")
    value.add_argument("--expected-parent-zip-sha256")
    value.add_argument(
        "--source-split",
        choices=("development", "validation", "test"),
        required=require_split,
    )


def _source_kwargs(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "parent_v3_source": args.parent_v3,
        "expected_zip_sha256": args.expected_zip_sha256,
        "expected_parent_zip_sha256": args.expected_parent_zip_sha256,
    }


def _route_settings(value: Any) -> list[GoogleRouteSettings]:
    if not isinstance(value, Mapping) or set(value) != {"routes"}:
        raise ValueError("routes file must contain exactly one routes list")
    rows = value["routes"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("routes must be a nonempty list")
    result: list[GoogleRouteSettings] = []
    for index, item in enumerate(rows):
        if not isinstance(item, Mapping):
            raise ValueError(f"routes[{index}] must be an object")
        env_name = str(item.get("api_key_env", ""))
        api_key = os.environ.get(env_name, "")
        if not env_name or not api_key:
            raise ValueError(f"routes[{index}] API key environment variable is missing")
        result.append(
            GoogleRouteSettings(
                route_id=str(item["route_id"]),
                model_id=str(item["model_id"]),
                api_key=api_key,
                base_url=None if item.get("base_url") is None else str(item["base_url"]),
                timeout_seconds=int(item.get("timeout_seconds", 120)),
                model_family=None
                if item.get("model_family") is None
                else str(item["model_family"]),
                independence_group=None
                if item.get("independence_group") is None
                else str(item["independence_group"]),
            )
        )
    return result


def _frozen_candidates(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, Mapping) and isinstance(value.get("candidates"), list):
        rows = value["candidates"]
    elif isinstance(value, list):
        rows = value
    else:
        raise ValueError("frozen candidate input must be a list or fixture set")
    if not rows or not all(isinstance(row, Mapping) for row in rows):
        raise ValueError("frozen candidate input must contain candidate objects")
    return list(rows)


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _integration_commands() -> tuple[str, ...]:
    return (
        "python -B -m pytest -q context_substitution/v2/tests --tb=short --junitxml=<evidence>/junit.xml",
        "python -B -m context_substitution.v2 pilot-smoke --pilot-directory <pilot-dir> --pilot-zip <pilot.zip> --parent-directory <v3-dir> --parent-zip <v3.zip> --output <evidence>/pilot_adapter_receipt.json",
        "python -B -m context_substitution.v2 reviewed-support-to-runtime --source <pilot-dir> --parent-v3 <v3-dir> --source-split development --output <evidence>/pilot_input.json --receipt <evidence>/pilot_runtime_receipt.json",
        "python -B -m context_substitution.v2 fake-provider-pilot --input <evidence>/pilot_input.json --ledger-root <evidence>/fake_ledger --run-output <evidence>/fake_run.json --summary-output <evidence>/pilot_zero_api_summary.json",
        "python -B -m context_substitution.v2 replay-validate --input <evidence>/pilot_input.json --run <evidence>/fake_run.json --ledger-root <evidence>/fake_ledger --output <evidence>/replay_report.json",
        "python -B -m context_substitution.v2 development-fixture-freeze --input <evidence>/pilot_input.json --run <evidence>/fake_run.json --ledger <evidence>/fake_ledger/provider_attempts.jsonl --output <evidence>/development_frozen_candidates.json",
        "python -B -m context_substitution.v2 project-context-evidence --run <evidence>/fake_run.json --frozen-candidates <evidence>/development_frozen_candidates.json --ledger <evidence>/fake_ledger/provider_attempts.jsonl --output-directory <evidence>/context_evidence_packages",
    )


if __name__ == "__main__":
    raise SystemExit(main())
