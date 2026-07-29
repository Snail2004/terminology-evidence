from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from context_substitution.v2.contracts.run import validate_context_substitution_run
from context_substitution.v2.contracts.common import SCHEMA_VERSION
from context_substitution.v2.integration.common import (
    file_sha256,
    object_sha256,
    seal_object,
)
from context_substitution.v2.jsonio import load_jsonl_objects


LEDGER_MANIFEST_SCHEMA_ID = "ContextSubstitutionProviderLedgerManifestV1"
LEDGER_MANIFEST_SCHEMA_VERSION = "1.1.0"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CAPTURE_FIELDS = frozenset(
    {
        "record_kind",
        "raw_response_ref",
        "raw_response_sha256",
        "raw_response_bytes",
    }
)
_ATTEMPT_FIELDS = frozenset(
    {
        "record_kind",
        "run_id",
        "tag",
        "candidate_id",
        "context_id",
        "request_sha256",
        "retry_index",
        "started_at",
        "completed_at",
        "provider_id",
        "status",
        "failure_reason",
        "token_usage",
        "latency",
        "provider_route_id",
        "model_id",
        "model_family",
        "independence_group",
        "role",
        "prompt_version",
        "prompt_sha256",
        "response_sha256",
        "request_id",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
        "cached",
        "latency_ms",
        "accepted",
        "failure_kind",
        "raw_response_ref",
        "raw_response_sha256",
        "raw_response_storage_status",
    }
)
_ROLE_ATTEMPT_FIELDS = frozenset(
    {
        "model_profile",
        "role_equivalence_group",
        "role_plan_sha256",
        "effective_generation_config",
        "escalation_kind",
        "candidate_replicate_index",
        "semantic_role_call_index",
        "provider_request_index",
        "route_attempt_index",
        "transport_retry_index",
        "equivalent_failover_from",
        "provider_status_code",
        "failure_disposition",
        "safe_error_code",
        "budget_units_consumed",
    }
)
_TOKEN_USAGE_FIELDS = frozenset(
    {"input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"}
)


def build_provider_ledger_manifest(
    *, run_payload: Mapping[str, Any], ledger_path: Path
) -> dict[str, Any]:
    run = validate_context_substitution_run(run_payload)
    path = Path(ledger_path).resolve()
    if path.name != "provider_attempts.jsonl" or not path.is_file():
        raise ValueError("provider ledger path must name provider_attempts.jsonl")
    rows = _load_rows(path, role_bound=run["schema_version"] == SCHEMA_VERSION)
    attempts = [row for row in rows if row["record_kind"] == "PROVIDER_ATTEMPT"]
    captures = [row for row in rows if row["record_kind"] == "RAW_RESPONSE_CAPTURED"]
    expected_attempts = list(run["provider_attempts"])
    if len(attempts) != len(expected_attempts):
        raise ValueError(
            "provider ledger attempt count differs from the Context Substitution run"
        )

    run_ids: set[str] = set()
    attempt_identities: list[dict[str, Any]] = []
    for index, (row, expected) in enumerate(zip(attempts, expected_attempts, strict=True)):
        _validate_attempt(row, expected=expected, index=index, ledger_root=path.parent)
        run_ids.add(str(row["run_id"]))
        attempt_identities.append(_attempt_identity(row, expected))
    if len(run_ids) != 1:
        raise ValueError("provider ledger must bind exactly one nonempty run_id")
    ledger_run_id = next(iter(run_ids))
    if ledger_run_id.rsplit(":", 1)[-1] != run["input_sha256"][:24]:
        raise ValueError("provider ledger run_id is not bound to the source input")
    _validate_capture_sequence(rows, ledger_root=path.parent)

    response_set = sorted(
        {
            (str(row["raw_response_ref"]), str(row["raw_response_sha256"]))
            for row in attempts
            if row["raw_response_storage_status"] == "STORED"
        }
    )
    manifest = {
        "schema_id": LEDGER_MANIFEST_SCHEMA_ID,
        "schema_version": LEDGER_MANIFEST_SCHEMA_VERSION,
        "run_id": ledger_run_id,
        "source_run_sha256": run["integrity"]["run_sha256"],
        "source_input_sha256": run["input_sha256"],
        "provider_attempt_count": len(attempts),
        "accepted_attempt_count": sum(bool(row["accepted"]) for row in attempts),
        "rejected_attempt_count": sum(not bool(row["accepted"]) for row in attempts),
        "ledger_event_sequence_sha256": object_sha256(rows),
        "attempt_sequence_sha256": object_sha256(attempt_identities),
        "raw_response_count": len(captures),
        "raw_response_set_sha256": object_sha256(
            [
                {"raw_response_ref": ref, "raw_response_sha256": sha}
                for ref, sha in response_set
            ]
        ),
        "ledger_physical_sha256": file_sha256(path),
        "final_glossary_decision": None,
        "integrity": {},
    }
    return seal_object(manifest, integrity_key="manifest_sha256")


def validate_provider_ledger_manifest(
    value: Mapping[str, Any], *, run_payload: Mapping[str, Any]
) -> dict[str, Any]:
    run = validate_context_substitution_run(run_payload)
    required = {
        "schema_id",
        "schema_version",
        "run_id",
        "source_run_sha256",
        "source_input_sha256",
        "provider_attempt_count",
        "accepted_attempt_count",
        "rejected_attempt_count",
        "ledger_event_sequence_sha256",
        "attempt_sequence_sha256",
        "raw_response_count",
        "raw_response_set_sha256",
        "ledger_physical_sha256",
        "final_glossary_decision",
        "integrity",
    }
    if set(value) != required:
        raise ValueError("provider ledger manifest fields differ from the contract")
    if value["schema_id"] != LEDGER_MANIFEST_SCHEMA_ID or value[
        "schema_version"
    ] != LEDGER_MANIFEST_SCHEMA_VERSION:
        raise ValueError("provider ledger manifest schema mismatch")
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or set(integrity) != {"manifest_sha256"}:
        raise ValueError("provider ledger manifest integrity is invalid")
    identity = dict(value)
    identity["integrity"] = {}
    if integrity["manifest_sha256"] != object_sha256(identity):
        raise ValueError("provider ledger manifest self-hash mismatch")
    if value["source_run_sha256"] != run["integrity"]["run_sha256"]:
        raise ValueError("provider ledger manifest source run mismatch")
    if value["source_input_sha256"] != run["input_sha256"]:
        raise ValueError("provider ledger manifest source input mismatch")
    if value["provider_attempt_count"] != len(run["provider_attempts"]):
        raise ValueError("provider ledger manifest attempt count mismatch")
    accepted = sum(bool(row["accepted"]) for row in run["provider_attempts"])
    rejected = len(run["provider_attempts"]) - accepted
    stored = sum(
        row["raw_response_storage_status"] == "STORED"
        for row in run["provider_attempts"]
    )
    if value["accepted_attempt_count"] != accepted or value[
        "rejected_attempt_count"
    ] != rejected:
        raise ValueError("provider ledger manifest accepted/rejected count mismatch")
    if value["raw_response_count"] != stored:
        raise ValueError("provider ledger manifest raw response count mismatch")
    if value["final_glossary_decision"] is not None:
        raise ValueError("provider ledger manifest cannot contain a final decision")
    for key in (
        "ledger_event_sequence_sha256",
        "attempt_sequence_sha256",
        "raw_response_set_sha256",
        "ledger_physical_sha256",
    ):
        if not isinstance(value[key], str) or not _SHA256.fullmatch(value[key]):
            raise ValueError(f"provider ledger manifest {key} is invalid")
    return dict(value)


def _load_rows(path: Path, *, role_bound: bool) -> list[dict[str, Any]]:
    rows = load_jsonl_objects(path)
    for line_number, row in enumerate(rows, 1):
        kind = row.get("record_kind")
        if kind not in {"RAW_RESPONSE_CAPTURED", "PROVIDER_ATTEMPT"}:
            raise ValueError(f"provider ledger line {line_number} has unknown record_kind")
        expected_fields = (
            _CAPTURE_FIELDS
            if kind == "RAW_RESPONSE_CAPTURED"
            else _ATTEMPT_FIELDS
            | (_ROLE_ATTEMPT_FIELDS if role_bound else frozenset())
        )
        if set(row) != expected_fields:
            missing = sorted(expected_fields - set(row))
            extra = sorted(set(row) - expected_fields)
            details = []
            if missing:
                details.append("missing=" + ",".join(missing))
            if extra:
                details.append("extra=" + ",".join(extra))
            raise ValueError(
                f"provider ledger line {line_number} fields differ from {kind}: "
                + "; ".join(details)
            )
        if kind == "PROVIDER_ATTEMPT":
            usage = row.get("token_usage")
            if not isinstance(usage, Mapping) or set(usage) != _TOKEN_USAGE_FIELDS:
                raise ValueError(
                    f"provider ledger line {line_number} token_usage fields differ from contract"
                )
    if not rows:
        raise ValueError("provider ledger is empty")
    return rows


def _validate_attempt(
    row: Mapping[str, Any],
    *,
    expected: Mapping[str, Any],
    index: int,
    ledger_root: Path,
) -> None:
    for key, value in expected.items():
        if row.get(key) != value:
            raise ValueError(f"provider ledger attempt {index} differs at {key}")
    for key in ("run_id", "tag", "started_at", "completed_at"):
        if not isinstance(row.get(key), str) or not row[key]:
            raise ValueError(f"provider ledger attempt {index} lacks {key}")
    role = expected["role"]
    candidate_id = row.get("candidate_id")
    context_id = row.get("context_id")
    if role == "context_selector":
        if candidate_id is not None or context_id is not None:
            raise ValueError(f"provider ledger attempt {index} selector identity mismatch")
    elif role == "pairwise_tiebreaker":
        if not isinstance(candidate_id, str) or not candidate_id or context_id is not None:
            raise ValueError(f"provider ledger attempt {index} pairwise identity mismatch")
    elif (
        not isinstance(candidate_id, str)
        or not candidate_id
        or not isinstance(context_id, str)
        or not context_id
    ):
        raise ValueError(f"provider ledger attempt {index} candidate/context identity mismatch")
    if row.get("provider_id") != expected["provider_route_id"]:
        raise ValueError(f"provider ledger attempt {index} provider_id mismatch")
    if row.get("status") != ("ACCEPTED" if expected["accepted"] else "REJECTED"):
        raise ValueError(f"provider ledger attempt {index} status mismatch")
    if row.get("failure_reason") != expected["failure_kind"]:
        raise ValueError(f"provider ledger attempt {index} failure reason mismatch")
    if row.get("latency") != expected["latency_ms"]:
        raise ValueError(f"provider ledger attempt {index} latency mismatch")
    expected_usage = {
        "input_tokens": expected["input_tokens"],
        "output_tokens": expected["output_tokens"],
        "reasoning_tokens": expected["reasoning_tokens"],
        "total_tokens": expected["total_tokens"],
    }
    if row.get("token_usage") != expected_usage:
        raise ValueError(f"provider ledger attempt {index} token usage mismatch")
    for key in ("prompt_sha256", "request_sha256"):
        if not isinstance(row.get(key), str) or not _SHA256.fullmatch(row[key]):
            raise ValueError(f"provider ledger attempt {index} {key} is invalid")
    if not isinstance(row.get("retry_index"), int) or row["retry_index"] < 0:
        raise ValueError(f"provider ledger attempt {index} retry_index is invalid")
    if expected["raw_response_storage_status"] == "STORED":
        read_content_addressed_response(
            ledger_root,
            str(expected["raw_response_ref"]),
            str(expected["raw_response_sha256"]),
        )


def _attempt_identity(
    row: Mapping[str, Any], expected: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "candidate_id": row["candidate_id"],
        "context_id": row["context_id"],
        "tag": row["tag"],
        "request_sha256": row["request_sha256"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "attempt": dict(expected),
    }


def _validate_capture_sequence(
    rows: Sequence[Mapping[str, Any]], *, ledger_root: Path
) -> None:
    pending: tuple[str, str] | None = None
    capture_count = 0
    for index, row in enumerate(rows):
        if row["record_kind"] == "RAW_RESPONSE_CAPTURED":
            if pending is not None:
                raise ValueError(
                    "provider response capture is not immediately followed by its attempt"
                )
            ref = str(row.get("raw_response_ref"))
            sha = str(row.get("raw_response_sha256"))
            data = read_content_addressed_response(ledger_root, ref, sha)
            if row.get("raw_response_bytes") != len(data):
                raise ValueError("provider response capture byte count mismatch")
            pending = (ref, sha)
            capture_count += 1
            continue
        stored = row.get("raw_response_storage_status") == "STORED"
        if stored:
            expected = (
                str(row.get("raw_response_ref")),
                str(row.get("raw_response_sha256")),
            )
            if pending != expected:
                raise ValueError(
                    f"stored provider attempt {index} lacks its immediately preceding capture"
                )
        elif pending is not None:
            raise ValueError("unbound provider response capture precedes an unstored attempt")
        pending = None
    if pending is not None:
        raise ValueError("provider ledger contains unbound response captures")
    if capture_count != sum(
        row.get("raw_response_storage_status") == "STORED"
        for row in rows
        if row["record_kind"] == "PROVIDER_ATTEMPT"
    ):
        raise ValueError("provider response capture count differs from stored attempts")


def read_content_addressed_response(
    root: Path, ref: str, expected_sha: str
) -> bytes:
    if "\\" in ref or ":" in ref:
        raise ValueError("raw response ref is not canonical POSIX relative form")
    pure = PurePosixPath(ref)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("raw response ref escapes the ledger root")
    if len(pure.parts) != 2 or pure.parts[0] != "provider_responses":
        raise ValueError("raw response ref must be provider_responses/<sha>.txt")
    if pure.suffix != ".txt" or pure.stem != expected_sha or not _SHA256.fullmatch(
        expected_sha
    ):
        raise ValueError("raw response ref is not content-addressed")
    target = root.joinpath(*pure.parts)
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("raw response artifact path contains a symlink")
    if not target.is_file():
        raise ValueError("raw response artifact is missing or symlinked")
    resolved_root = root.resolve()
    resolved = target.resolve()
    if not resolved.is_relative_to(resolved_root):
        raise ValueError("raw response artifact escapes the ledger root")
    data = target.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError("raw response hash mismatch")
    return data
