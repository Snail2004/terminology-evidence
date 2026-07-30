"""Zero-provider replay of a sealed E Live run directory."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from .common import LiveSchemaError, load_jsonl, load_object, verify_seal
from .ledger import verify_event_chain
from .snapshot import verify_snapshot
from ..strict_json import resolve_artifact_file


def replay_run(run_root: str | Path) -> dict[str, Any]:
    root = Path(run_root).absolute()
    run = load_object(root / "run.json")
    events = load_jsonl(root / "events.jsonl")
    verify_event_chain(events, run_id=run.get("run_id"))
    snapshot = verify_snapshot(run["snapshot_root"])
    if snapshot["integrity"]["self_sha256"] != run.get("snapshot_manifest_sha256"):
        raise LiveSchemaError("run snapshot authority binding mismatch")
    for event in events:
        if event["event_kind"] == "E_MODEL_REQUEST":
            raw_path = resolve_artifact_file(root, event["payload"]["raw_response_locator"])
            if hashlib.sha256(raw_path.read_bytes()).hexdigest() != event["payload"]["response_sha256"]:
                raise LiveSchemaError("raw Judge response hash mismatch")
        if event["event_kind"] == "E_SOURCE_DOCUMENT_ACCEPTED":
            ref = event["payload"]["document_ref"]
            base = root if ref.startswith("raw_documents/") else Path(run["snapshot_root"])
            raw_path = resolve_artifact_file(base, ref)
            if hashlib.sha256(raw_path.read_bytes()).hexdigest() != event["payload"]["content_sha256"]:
                raise LiveSchemaError("raw source document hash mismatch")
    package = load_object(root / "attestation_package.json")
    if not verify_seal(package):
        raise LiveSchemaError("sealed attestation package hash mismatch")
    expected_events = str(run.get("events_sha256", ""))
    actual_events = hashlib.sha256((root / "events.jsonl").read_bytes()).hexdigest()
    if expected_events != actual_events:
        raise LiveSchemaError("run event artifact hash mismatch")
    expected_package = str(run.get("package_sha256", ""))
    actual_package = hashlib.sha256((root / "attestation_package.json").read_bytes()).hexdigest()
    if expected_package != actual_package:
        raise LiveSchemaError("run package artifact hash mismatch")
    if int(run.get("provider_calls", -1)) != 0:
        raise LiveSchemaError("replay refuses nonzero provider call run")
    ledger_path = root / "evidence_ledger.json"
    evidence_ledger = load_object(ledger_path)
    if not verify_seal(evidence_ledger):
        raise LiveSchemaError("evidence ledger self hash mismatch")
    expected_ledger_sha = package["provenance"]["raw_ledger_ref"]["sha256"]
    if hashlib.sha256(ledger_path.read_bytes()).hexdigest() != expected_ledger_sha:
        raise LiveSchemaError("evidence ledger package binding mismatch")
    return {
        "status": "REPLAYED_ZERO_PROVIDER",
        "run_id": run["run_id"],
        "run_spec_id": run["run_spec_id"],
        "event_count": len(events),
        "event_sha256": actual_events,
        "package_sha256": actual_package,
        "provider_calls": 0,
        "network_calls": 0,
        "final_glossary_decision": package.get("final_glossary_decision"),
    }


__all__ = ["replay_run"]
