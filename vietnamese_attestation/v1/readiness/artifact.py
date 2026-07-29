"""Verification of the accepted zero-API milestone artifact."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..runtime.replay import AuditReplayReader
from ..zero_api.artifacts import file_sha256, verify_self_sha256


def verify_zero_api_artifact(root: str | Path) -> dict[str, Any]:
    artifact_root = Path(root).resolve(strict=True)
    summary = _load_object(artifact_root / "pilot_zero_api_summary.json")
    manifest = _load_object(artifact_root / "zero_api_artifact_manifest.json")
    replay = _load_object(artifact_root / "replay_report.json")
    projection = _load_object(artifact_root / "contract_projection_report.json")
    controlled = _load_object(
        artifact_root / "controlled_corpus_adapter_report.json"
    )
    canary = _load_object(artifact_root / "provider_canary_report.json")

    if not verify_self_sha256(summary):
        raise ValueError("zero-API summary canonical self hash mismatch")
    if not verify_self_sha256(manifest):
        raise ValueError("zero-API manifest canonical self hash mismatch")
    if summary.get("candidate_count") != 15:
        raise ValueError("zero-API artifact does not contain 15 candidates")
    if summary.get("replay_pass_count") != 15:
        raise ValueError("zero-API artifact replay count is not 15/15")
    if summary.get("external_provider_call_count") != 0:
        raise ValueError("zero-API artifact records external provider calls")
    if summary.get("final_glossary_decision") is not None:
        raise ValueError("zero-API artifact contains a final glossary decision")
    if projection.get("status") != "BLOCKED_DEVELOPMENT_IDENTITY":
        raise ValueError("development projection HOLD is not preserved")
    if projection.get("projected_package_count") != 0:
        raise ValueError("development identities were projected as authority")
    if controlled.get("status") != "BLOCKED_EXTERNAL_INPUT":
        raise ValueError("controlled registry HOLD is not preserved")
    if controlled.get("retrieval_provider_created") is not False:
        raise ValueError("controlled retrieval provider was created without authority")
    if canary.get("external_provider_call_count") != 0:
        raise ValueError("provider canary report records external calls")
    if replay.get("all_content_verified") is not True:
        raise ValueError("zero-API replay report is not fully verified")

    records = manifest.get("files")
    if not isinstance(records, list) or manifest.get("file_count") != len(records):
        raise ValueError("zero-API manifest file count mismatch")
    listed: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("zero-API manifest record is not an object")
        relative = _safe_relative(record.get("artifact_ref"))
        if relative in listed:
            raise ValueError(f"duplicate zero-API manifest path: {relative}")
        listed.add(relative)
        path = artifact_root / relative
        if not path.is_file():
            raise ValueError(f"zero-API manifest file is missing: {relative}")
        if path.stat().st_size != record.get("byte_count"):
            raise ValueError(f"zero-API manifest size mismatch: {relative}")
        if file_sha256(path) != record.get("artifact_sha256"):
            raise ValueError(f"zero-API manifest hash mismatch: {relative}")
    actual = {
        path.relative_to(artifact_root).as_posix()
        for path in artifact_root.rglob("*")
        if path.is_file()
        and path.name != "zero_api_artifact_manifest.json"
        and not path.name.endswith(".tmp")
    }
    if actual != listed:
        raise ValueError("zero-API artifact file set differs from manifest")

    replay_count = 0
    for path in sorted((artifact_root / "runs").glob("*/run_manifest.json")):
        AuditReplayReader(path).verify_all_content()
        replay_count += 1
    if replay_count != 15:
        raise ValueError("zero-API artifact does not contain 15 replay manifests")

    attempts_path = artifact_root / "provider_attempts.jsonl"
    attempt_count = 0
    for line in attempts_path.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        attempt = json.loads(line)
        if attempt.get("external_api") is not False:
            raise ValueError("zero-API attempt is marked as external")
        attempt_count += 1

    return {
        "schema_id": "VietnameseAttestationZeroApiVerificationReportV1",
        "schema_version": "1.0.0",
        "status": "PASS",
        "artifact_ref": artifact_root.as_posix(),
        "summary_self_sha256": summary["integrity"]["self_sha256"],
        "manifest_self_sha256": manifest["integrity"]["self_sha256"],
        "manifest_file_count": len(records),
        "candidate_count": 15,
        "replay_pass_count": replay_count,
        "fixture_attempt_count": attempt_count,
        "raw_response_count": summary.get("raw_response_count"),
        "shared_projection_status": projection["status"],
        "controlled_registry_status": controlled["status"],
        "provider_canary_status": canary.get("status"),
        "external_provider_call_count": 0,
        "final_glossary_decision": None,
    }


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load zero-API artifact: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"zero-API artifact is not an object: {path}")
    return value


def _safe_relative(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("unsafe zero-API manifest path")
    path = Path(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("unsafe zero-API manifest path")
    return value


__all__ = ["verify_zero_api_artifact"]
