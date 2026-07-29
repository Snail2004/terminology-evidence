"""Offline CLI for Evaluation registries, reports and authority receipts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..constants import MODE_REAL_AUTHORITY, MODE_SYNTHETIC
from ..fixtures.synthetic import write_synthetic_release
from ..artifacts.loader import load_rows
from ..preregistration.legacy import verify_legacy_receipt
from ..preregistration.receipt import build_receipt, verify_receipt, write_receipt
from ..registries.loader import load_registries, registry_counts, registry_root
from ..release_tools.builder import verify_release
from ..reports.builder import build_evaluation_report


AUTHORITY_ARGUMENTS = {
    "contracts_receipt": "contracts-receipt",
    "contracts_approval_binding": "contracts-approval-binding",
    "contracts_checksums": "contracts-checksums",
    "global_authority_report": "global-authority-report",
    "global_action_policy": "global-action-policy",
    "dataset_manifest": "dataset-manifest",
    "dataset_split_assignments": "dataset-split-assignments",
}


def _path(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _artifact_hashes(values: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--artifact-hash requires NAME=SHA256")
        name, digest = value.split("=", 1)
        if name in result:
            raise ValueError(f"duplicate artifact hash: {name}")
        result[name] = digest
    return result


def _authority_paths(args: argparse.Namespace) -> dict[str, Path] | None:
    values = {name: getattr(args, name) for name in AUTHORITY_ARGUMENTS}
    present = {name for name, value in values.items() if value is not None}
    if not present:
        return None
    if present != set(values):
        raise ValueError("all seven external authority paths are required together")
    return {name: value for name, value in values.items()}


def _add_authority_arguments(parser: argparse.ArgumentParser) -> None:
    for destination, flag in AUTHORITY_ARGUMENTS.items():
        parser.add_argument(f"--{flag}", dest=destination, type=_path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evaluation-v1", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-registries")
    validate.add_argument("--registry-root", type=_path, default=registry_root())
    synthetic = sub.add_parser("build-synthetic")
    synthetic.add_argument("output", type=_path)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("rows", type=_path)
    evaluate.add_argument("output", type=_path)
    evaluate.add_argument("--split", default="development")
    evaluate.add_argument("--seed", type=int, default=20260729)
    evaluate.add_argument("--replicates", type=int, default=200)
    receipt = sub.add_parser("build-receipt")
    receipt.add_argument("output", type=_path)
    receipt.add_argument("--mode", choices=[MODE_REAL_AUTHORITY, MODE_SYNTHETIC], required=True)
    receipt.add_argument("--base-commit", required=True)
    receipt.add_argument("--repo-root", type=_path, required=True)
    receipt.add_argument("--registry-root", type=_path, default=registry_root())
    receipt.add_argument("--artifact-hash", action="append", default=[])
    receipt.add_argument("--synthetic-reason")
    receipt.add_argument("--created-at")
    _add_authority_arguments(receipt)
    verify = sub.add_parser("verify-receipt")
    verify.add_argument("receipt", type=_path)
    verify.add_argument("--repo-root", type=_path)
    verify.add_argument("--registry-root", type=_path, default=registry_root())
    _add_authority_arguments(verify)
    legacy = sub.add_parser("verify-legacy-receipt")
    legacy.add_argument("receipt", type=_path)
    legacy.add_argument("--registry-root", type=_path, default=registry_root())
    release = sub.add_parser("verify-release")
    release.add_argument("release_root", type=_path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-registries":
            result = {"status": "PASS", "counts": registry_counts(load_registries(args.registry_root))}
        elif args.command == "build-synthetic":
            result = write_synthetic_release(args.output)
        elif args.command == "evaluate":
            report = build_evaluation_report(
                load_rows(args.rows),
                args.output,
                split=args.split,
                bootstrap_seed=args.seed,
                bootstrap_replicates=args.replicates,
            )
            result = {"status": "PASS", "semantic_sha256": report["semantic_sha256"]}
        elif args.command == "build-receipt":
            receipt = build_receipt(
                mode=args.mode,
                base_commit=args.base_commit,
                repo_root_path=args.repo_root,
                registry_root_path=args.registry_root,
                artifact_hashes=_artifact_hashes(args.artifact_hash),
                authority_artifact_paths=_authority_paths(args),
                created_at=args.created_at,
                synthetic_reason=args.synthetic_reason,
            )
            write_receipt(args.output, receipt)
            result = {"status": "PASS", "self_sha256": receipt["integrity"]["self_sha256"]}
        elif args.command == "verify-receipt":
            receipt = verify_receipt(
                args.receipt,
                registry_root_path=args.registry_root,
                repo_root_path=args.repo_root,
                authority_artifact_paths=_authority_paths(args),
            )
            result = {"status": "PASS", "self_sha256": receipt["integrity"]["self_sha256"]}
        elif args.command == "verify-legacy-receipt":
            result = verify_legacy_receipt(args.receipt, registry_root_path=args.registry_root)
        elif args.command == "verify-release":
            manifest = verify_release(args.release_root)
            result = {"status": "PASS", "self_sha256": manifest["integrity"]["self_sha256"]}
        else:
            raise ValueError("unsupported command")
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
