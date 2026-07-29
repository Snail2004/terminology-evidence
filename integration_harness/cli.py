"""Command-line surface for the System Integration Harness."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Sequence

from .assembler import GlobalCliAdapter
from .authority import resolve_authority
from .faults import FAULTS, inject_fault
from .inventory import inventory_report, load_inventory
from .join import validate_and_join
from .jsonio import dump_json
from .pipeline import execute_run
from .replay import replay_run, verify_checksums


def _common_authority(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--contracts-root", type=Path, required=True)
    parser.add_argument("--authority-receipt", type=Path, required=True)
    parser.add_argument("--action-policy", type=Path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="integration-harness")
    sub = parser.add_subparsers(dest="command", required=True)

    authority = sub.add_parser("authority-verify")
    _common_authority(authority)
    authority.set_defaults(handler=_authority)

    inventory = sub.add_parser("inventory")
    inventory.add_argument("--manifest", type=Path, required=True)
    inventory.add_argument("--output", type=Path)
    inventory.set_defaults(handler=_inventory)

    packages = sub.add_parser("validate-packages")
    packages.add_argument("--manifest", type=Path, required=True)
    packages.add_argument("--contracts-root", type=Path)
    packages.add_argument("--output", type=Path)
    packages.set_defaults(handler=_packages)

    join = sub.add_parser("join")
    join.add_argument("--manifest", type=Path, required=True)
    join.add_argument("--contracts-root", type=Path)
    join.add_argument("--output", type=Path)
    join.set_defaults(handler=_join)

    run = sub.add_parser("run")
    _common_authority(run)
    run.add_argument("--manifest", type=Path, required=True)
    run.add_argument("--mode", choices=["FIXTURE_CONFORMANCE", "REAL_DEVELOPMENT_ZERO_NETWORK"], required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--run-id", required=True)
    run.set_defaults(handler=_run)

    replay = sub.add_parser("replay")
    replay.add_argument("--run-dir", type=Path, required=True)
    replay.add_argument("--repository-root", type=Path)
    replay.add_argument("--contracts-root", type=Path)
    replay.add_argument("--action-policy", type=Path)
    replay.add_argument("--public-cli", action="store_true")
    replay.set_defaults(handler=_replay)

    verify = sub.add_parser("verify-run")
    verify.add_argument("--run-dir", type=Path, required=True)
    verify.set_defaults(handler=lambda args: verify_checksums(args.run_dir))

    fault = sub.add_parser("inject-fault")
    fault.add_argument("--run-dir", type=Path, required=True)
    fault.add_argument("--fault", choices=sorted(FAULTS), required=True)
    fault.add_argument("--output", type=Path, required=True)
    fault.set_defaults(handler=lambda args: {"status": "PASS", "output": str(inject_fault(args.run_dir, args.output, args.fault))})

    release = sub.add_parser("build-release")
    release.add_argument("--repository-root", type=Path, default=Path.cwd())
    release.add_argument("--output-dir", type=Path, required=True)
    release.set_defaults(handler=_release)
    return parser


def _emit(value: Any) -> int:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


def _authority(args: argparse.Namespace) -> dict[str, Any]:
    authority = resolve_authority(args.authority_receipt, args.contracts_root, action_policy_path=args.action_policy)
    return {"status": "PASS", **authority.as_dict()}


def _inventory(args: argparse.Namespace) -> dict[str, Any]:
    value = inventory_report(load_inventory(args.manifest))
    if args.output:
        dump_json(args.output, value)
    return {"status": "PASS", **value}


def _packages(args: argparse.Namespace) -> dict[str, Any]:
    inventory = load_inventory(args.manifest)
    _, report = validate_and_join(inventory, schema_root=args.contracts_root)
    if args.output:
        dump_json(args.output, report)
    return {"status": "PASS", "artifact_count": len(inventory.records), "candidate_count": report["candidate_count"]}


def _join(args: argparse.Namespace) -> dict[str, Any]:
    inventory = load_inventory(args.manifest)
    _, report = validate_and_join(inventory, schema_root=args.contracts_root)
    if args.output:
        dump_json(args.output, report)
    return {"status": "PASS", **report}


def _run(args: argparse.Namespace) -> dict[str, Any]:
    output = execute_run(
        manifest_path=args.manifest,
        authority_receipt=args.authority_receipt,
        contracts_root=args.contracts_root,
        output_dir=args.output,
        run_id=args.run_id,
        mode=args.mode,
        action_policy=args.action_policy,
        repository_root=args.repository_root,
    )
    return {"status": "PASS", "run_dir": str(output)}


def _replay(args: argparse.Namespace) -> dict[str, Any]:
    adapter = None
    if args.public_cli:
        if args.repository_root is None or args.contracts_root is None:
            raise ValueError("--public-cli requires --repository-root and --contracts-root")
        adapter = GlobalCliAdapter(
            repository_root=args.repository_root,
            authority_receipt=args.run_dir / "input" / "authority" / "authority_receipt.json",
            action_policy=args.action_policy,
            contracts_root=args.contracts_root,
        )
    return replay_run(args.run_dir, adapter=adapter)


def _release(args: argparse.Namespace) -> dict[str, Any]:
    root = args.repository_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / "system_integration_harness_v1_rc1.zip"
    excluded = {"__pycache__", ".pytest_cache", ".git"}
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for top in ("integration_harness", "tests/system_integration", "scripts/integration", "docs/integration"):
            source = root / top
            if not source.exists():
                continue
            for path in source.rglob("*"):
                if not path.is_file() or any(part in excluded or path.suffix == ".pyc" for part in path.parts):
                    continue
                archive.write(path, path.relative_to(root).as_posix())
    digest = __import__("hashlib").sha256(zip_path.read_bytes()).hexdigest()
    (zip_path.with_suffix(zip_path.suffix + ".sha256")).write_text(f"{digest}  {zip_path.name}\n", encoding="utf-8", newline="\n")
    manifest = {"schema_id": "SystemIntegrationReleaseManifestV1", "zip": zip_path.name, "zip_sha256": digest}
    dump_json(output_dir / "release_manifest.json", manifest)
    return {"status": "PASS", "zip": str(zip_path), "zip_sha256": digest}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _emit(args.handler(args))
    except Exception as exc:
        print(json.dumps({"status": "ERROR", "error_type": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
