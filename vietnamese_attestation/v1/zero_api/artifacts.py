"""Artifact, replay, and hash utilities for the zero-API pilot."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..runtime.replay import AuditReplayReader


def verify_replay(manifest_path: Path) -> dict[str, Any]:
    reader = AuditReplayReader(manifest_path)
    reader.verify_all_content()
    modes: dict[str, dict[str, int]] = {}
    for mode in reader.manifest["replay_modes"]:
        replay = reader.replay(mode)
        modes[mode] = {
            name: len(rows) for name, rows in replay["streams"].items()
        }
    return {
        "execution_id": reader.manifest["attestation_execution_id"],
        "run_spec_id": reader.manifest["run_spec_id"],
        "status": "PASS",
        "modes": modes,
    }


def aggregate_attempts(
    root: Path, result_rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for result in result_rows:
        run_root = root / "runs" / str(result["execution_id"])
        for kind, relative in (
            ("SEARCH", "search/requests.jsonl"),
            ("JUDGE", "judge/attempts.jsonl"),
        ):
            path = run_root / relative
            if not path.is_file():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line:
                    continue
                audit_attempt = json.loads(line)
                query_text = audit_attempt.get("query_text")
                request_sha256 = audit_attempt.get("request_sha256")
                if request_sha256 is None:
                    request_sha256 = canonical_sha256(
                        {
                            key: audit_attempt.get(key)
                            for key in (
                                "provider_id",
                                "query_id",
                                "query_class",
                                "query_text",
                                "requested_count",
                            )
                        }
                    )
                response_sha256 = audit_attempt.get("response_sha256")
                response_ref = audit_attempt.get("response_ref")
                if response_sha256 is None and isinstance(
                    response_ref, Mapping
                ):
                    response_sha256 = response_ref.get("artifact_sha256")
                input_tokens = int(audit_attempt.get("input_tokens") or 0)
                output_tokens = int(audit_attempt.get("output_tokens") or 0)
                attempts.append(
                    {
                        "run_id": result["execution_id"],
                        "candidate_id": result["candidate_id"],
                        "execution_id": result["execution_id"],
                        "attempt_kind": kind,
                        "provider_id": audit_attempt.get("provider_id")
                        or audit_attempt.get("route_id"),
                        "model_id": audit_attempt.get("model_id"),
                        "query_hash": (
                            canonical_sha256(query_text)
                            if isinstance(query_text, str)
                            else None
                        ),
                        "request_hash": request_sha256,
                        "response_hash": response_sha256,
                        "status": audit_attempt.get("outcome"),
                        "retry_index": 0,
                        "failure_reason": audit_attempt.get("error_code"),
                        "started_at": result["started_at"],
                        "completed_at": result["completed_at"],
                        "token_usage": {
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": input_tokens + output_tokens,
                        },
                        "latency_ms": 0,
                        "external_api": False,
                        "audit_attempt": audit_attempt,
                    }
                )
    return attempts


def collect_raw_responses(
    root: Path, result_rows: Sequence[Mapping[str, Any]]
) -> int:
    destination = root / "raw_responses"
    count = 0
    for result in result_rows:
        execution_id = str(result["execution_id"])
        run_root = root / "runs" / execution_id
        for namespace in ("search/responses", "judge/responses"):
            source = run_root / namespace
            if not source.is_dir():
                continue
            target = destination / execution_id / namespace
            target.mkdir(parents=True, exist_ok=True)
            for path in sorted(source.iterdir()):
                if not path.is_file() or path.name.endswith(".tmp"):
                    continue
                copied = target / path.name
                shutil.copyfile(path, copied)
                if file_sha256(copied) != path.name.split(".", 1)[0]:
                    raise RuntimeError("raw response hash drift during copy")
                count += 1
    return count


def projection_report(adapter: Mapping[str, Any]) -> dict[str, Any]:
    rows = [
        {
            "candidate_id": row["candidate_id"],
            "status": "BLOCKED_DEVELOPMENT_IDENTITY",
            "reason_codes": [
                "EFFECTIVE_SENSE_CONTRACT_SHA256_UNAVAILABLE",
                "KNOWN_VIETNAMESE_SURFACES_UNAVAILABLE",
                "DOMAIN_ANCHORS_UNAVAILABLE",
            ],
        }
        for row in adapter["candidates"]
    ]
    return {
        "schema_id": "VietnameseAttestationContractProjectionReportV1",
        "schema_version": "1.0.0",
        "authority_schema_id": "AttestationEvidencePackageV1",
        "authority_schema_version": "1.1.0",
        "status": "BLOCKED_DEVELOPMENT_IDENTITY",
        "projected_package_count": 0,
        "blocked_candidate_count": len(rows),
        "candidates": rows,
        "final_glossary_decision": None,
    }


def artifact_manifest(root: Path) -> dict[str, Any]:
    manifest_name = "zero_api_artifact_manifest.json"
    files = [
        {
            "artifact_ref": path.relative_to(root).as_posix(),
            "artifact_sha256": file_sha256(path),
            "byte_count": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
        and path.name != manifest_name
        and not path.name.endswith(".tmp")
    ]
    manifest = {
        "schema_id": "VietnameseAttestationZeroApiArtifactManifestV1",
        "schema_version": "1.0.0",
        "file_count": len(files),
        "files": files,
        "external_provider_call_count": 0,
        "final_glossary_decision": None,
        "integrity": {"self_sha256": "0" * 64},
    }
    manifest["integrity"]["self_sha256"] = self_sha256(manifest)
    return manifest


def write_json(path: Path, value: Any) -> None:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(raw, encoding="utf-8")
    os.replace(tmp, path)


def write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    raw = "".join(
        json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
        for row in rows
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(raw, encoding="utf-8")
    os.replace(tmp, path)


def self_sha256(value: Mapping[str, Any]) -> str:
    payload = json.loads(
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    )
    integrity = payload.get("integrity")
    if not isinstance(integrity, dict):
        raise ValueError("self-hashed artifact requires integrity object")
    integrity.pop("self_sha256", None)
    return canonical_sha256(payload)


def verify_self_sha256(value: Mapping[str, Any]) -> bool:
    integrity = value.get("integrity")
    return (
        isinstance(integrity, Mapping)
        and integrity.get("self_sha256") == self_sha256(value)
    )


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = [
    "aggregate_attempts",
    "artifact_manifest",
    "canonical_sha256",
    "collect_raw_responses",
    "file_sha256",
    "projection_report",
    "self_sha256",
    "verify_replay",
    "verify_self_sha256",
    "write_json",
    "write_jsonl",
]
