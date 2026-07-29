"""Minimal public-protocol fake for exercising subprocess adapter boundaries."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from integration_harness.hashing import self_sha256
from integration_harness.jsonio import dump_json, load_json


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="global-validator")
    sub = root.add_subparsers(dest="command", required=True)
    assemble = sub.add_parser("assemble-input")
    assemble.add_argument("--effective-sense", type=Path, required=True)
    assemble.add_argument("--frozen-candidate", type=Path, required=True)
    assemble.add_argument("--constraints", type=Path, required=True)
    assemble.add_argument("--context-evidence", type=Path, required=True)
    assemble.add_argument("--attestation-evidence", type=Path, required=True)
    assemble.add_argument("--output", type=Path, required=True)
    for name in ("validate-input",):
        command = sub.add_parser(name)
        command.add_argument("--input", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("--input", type=Path, required=True)
    run.add_argument("--output-dir", type=Path, required=True)
    run.add_argument("--run-id", required=True)
    run.add_argument("--mode", required=True)
    replay = sub.add_parser("replay")
    replay.add_argument("--run-dir", type=Path, required=True)
    return root


def main() -> int:
    args, _unknown = parser().parse_known_args()
    if args.command == "assemble-input":
        frozen = load_json(args.frozen_candidate, require_object=True)
        context = load_json(args.context_evidence, require_object=True)
        attestation = load_json(args.attestation_evidence, require_object=True)
        value = {
            "schema_id": "GlobalValidatorInputV1",
            "schema_version": "1.1.0",
            "candidate_key": frozen["candidate_key"],
            "input_contract_sha256": frozen["input_contract_sha256"],
            "effective_sense_contract": load_json(args.effective_sense, require_object=True),
            "frozen_candidate_contract": frozen,
            "constraint_evidence": load_json(args.constraints, require_object=True),
            "context_evidence": context,
            "attestation_evidence": attestation,
            "optional_probes": [],
            "assembly_metadata": {"binding_status": "COMPLETE", "assembler_version": "fixture-public-cli"},
            "integrity": {},
        }
        value["integrity"]["self_sha256"] = self_sha256(value)
        dump_json(args.output, value)
        result = {"status": "PASS", "output": str(args.output), "self_sha256": value["integrity"]["self_sha256"]}
    elif args.command == "validate-input":
        value = load_json(args.input, require_object=True)
        result = {"status": "PASS", "candidate_id": value["candidate_key"]["candidate_id"], "self_sha256": value["integrity"]["self_sha256"]}
    elif args.command == "run":
        value = load_json(args.input, require_object=True)
        output = args.output_dir / args.run_id
        output.mkdir(parents=True, exist_ok=True)
        dump_json(output / "decision.json", {"schema_id": "FakeGlobalDecisionV1", "decision": "PROVISIONAL", "candidate_id": value["candidate_key"]["candidate_id"]})
        result = {"status": "PASS", "decision": "PROVISIONAL", "approval_score": None, "certificate_sha256": None, "run_dir": str(output)}
    else:
        result = {"status": "PASS", "matched": True}
    import json

    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
