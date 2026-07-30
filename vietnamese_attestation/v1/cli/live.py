"""CLI for zero-provider E Live and controlled-corpus tooling."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ..live.fixtures import build_fixture_workspace
from ..live.replay import replay_run
from ..live.snapshot import build_snapshot, inspect_snapshot, verify_snapshot, zip_snapshot
from ..live.common import canonical_bytes, load_object
from ..live.schema_tools import export_schemas


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="e-live", description="E Live zero-provider tooling")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("snapshot-build")
    build.add_argument("--input-dir", required=True, type=Path)
    build.add_argument("--output-dir", required=True, type=Path)
    build.add_argument("--registry", required=True, type=Path)
    build.add_argument("--retrieval-policy", required=True, type=Path)
    build.add_argument("--receipt", required=True, type=Path)
    build.add_argument("--zip", dest="zip_path", type=Path)
    verify = sub.add_parser("snapshot-verify")
    verify.add_argument("snapshot", type=Path)
    inspect = sub.add_parser("snapshot-inspect")
    inspect.add_argument("snapshot", type=Path)
    fixture = sub.add_parser("fixture-build")
    fixture.add_argument("root", type=Path)
    fixture_run = sub.add_parser("fixture-run")
    fixture_run.add_argument("root", type=Path)
    replay = sub.add_parser("replay")
    replay.add_argument("run_root", type=Path)
    schema_export = sub.add_parser("schema-export")
    schema_export.add_argument("output_dir", type=Path)
    args = parser.parse_args(argv)
    if args.command == "snapshot-build":
        manifest = build_snapshot(
            args.input_dir,
            args.output_dir,
            registry=load_object(args.registry),
            retrieval_policy=load_object(args.retrieval_policy),
            acquisition_receipt=load_object(args.receipt),
            acquisition_receipt_source=args.receipt,
        )
        if args.zip_path:
            zip_snapshot(args.output_dir, args.zip_path)
        _print(manifest)
        return 0
    if args.command == "snapshot-verify":
        _print(verify_snapshot(args.snapshot))
        return 0
    if args.command == "snapshot-inspect":
        _print(inspect_snapshot(args.snapshot))
        return 0
    if args.command == "fixture-build":
        workspace = build_fixture_workspace(args.root)
        _print({"status": "FIXTURE_READY", "snapshot_root": str(workspace["snapshot_root"]), "provider_calls": 0, "network_calls": 0})
        return 0
    if args.command == "fixture-run":
        workspace = build_fixture_workspace(args.root)
        result = workspace["service"].create_run(workspace["request"])
        _print({"status": result["status"], "run_id": result["run_id"], "local_status": result.get("local_status"), "provider_calls": 0, "network_calls": 0})
        return 0
    if args.command == "replay":
        _print(replay_run(args.run_root))
        return 0
    if args.command == "schema-export":
        _print(export_schemas(args.output_dir))
        return 0
    raise AssertionError(args.command)


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
