from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "1.4.0"
POLICY_ID = "d2l_cst_three_reviewer_human_review_v1_4"
PILOT_SCHEMA_ID = "D2LCSTDevelopmentOnlyPilotV1_1"
REVIEWER_COUNT = 3
MAJORITY_THRESHOLD = 2


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_object(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: Path, value: Any) -> None:
    _write_atomic(
        path,
        (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    payload = "".join(
        canonical_json(row) + "\n"
        for row in rows
    )
    _write_atomic(path, payload.encode("utf-8"))


def write_text(path: Path, value: str) -> None:
    payload = value if value.endswith("\n") else value + "\n"
    _write_atomic(path, payload.encode("utf-8"))


def write_csv(
    path: Path,
    fieldnames: list[str],
    rows: Iterable[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8-sig",
        newline="",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def validate_self_hash(
    value: dict[str, Any],
    hash_field: str,
    label: str,
    errors: list[str],
) -> None:
    identity = dict(value)
    expected = identity.pop(hash_field, None)
    if expected != sha256_object(identity):
        errors.append(f"{label} self hash mismatch")


def seal(value: dict[str, Any], hash_field: str) -> dict[str, Any]:
    sealed = dict(value)
    sealed.pop(hash_field, None)
    sealed[hash_field] = sha256_object(sealed)
    return sealed


def file_bindings(
    root: Path,
    *,
    mutable: set[str] | None = None,
) -> dict[str, dict[str, Any]]:
    mutable = mutable or set()
    return {
        path.relative_to(root).as_posix(): {
            "ref": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "mutable_after_annotation": path.relative_to(root).as_posix() in mutable,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in {"manifest.json", "annotation_manifest.json"}
    }


def validate_manifest(
    root: Path,
    *,
    expected_schema: str,
    mutable_files_may_differ: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    manifest = read_json(root / "manifest.json")
    if manifest.get("schema_id") != expected_schema:
        errors.append(f"unexpected manifest schema: {manifest.get('schema_id')}")
    validate_self_hash(manifest, "manifest_sha256", "manifest", errors)
    for relative, binding in manifest.get("files", {}).items():
        if mutable_files_may_differ and binding.get("mutable_after_annotation"):
            continue
        path = root / relative
        if not path.is_file() or sha256_file(path) != binding.get("sha256"):
            errors.append(f"file hash mismatch: {relative}")
    return manifest, errors


def validate_pilot(pilot_root: Path) -> tuple[dict[str, Any], list[str]]:
    return validate_manifest(pilot_root, expected_schema=PILOT_SCHEMA_ID)


def pilot_records(pilot_root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    specs = {
        "TERM_SENSE": ("term_senses.jsonl", "sense_id", "term_sense_sha256"),
        "CONTEXT": ("contexts.jsonl", "context_id", "context_sha256"),
        "CANDIDATE": (
            "candidate_instances.jsonl",
            "candidate_instance_id",
            "candidate_instance_sha256",
        ),
    }
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for kind, (filename, id_field, hash_field) in specs.items():
        result[kind] = {}
        for row in read_jsonl(pilot_root / filename):
            identity = dict(row)
            expected = identity.pop(hash_field, None)
            if expected != sha256_object(identity):
                raise ValueError(f"Pilot {kind} row hash mismatch: {row.get(id_field)}")
            result[kind][row[id_field]] = row
    return result


def source_payload_hash(row: dict[str, Any], fields: list[str]) -> str:
    return sha256_object({field: str(row.get(field, "")) for field in fields})


def validate_iso8601(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp requires timezone")
    return parsed


def actor_fields_populated(row: dict[str, str], prefix: str) -> bool:
    if prefix == "adjudicated":
        keys = [key for key in row if key.startswith("adjudicat")]
    else:
        keys = [key for key in row if key.startswith(f"{prefix}_")]
    return any(row.get(key, "") for key in keys)


def reviewer_identity_errors(
    row: dict[str, str],
    *,
    reviewer_count: int = REVIEWER_COUNT,
) -> list[str]:
    errors = []
    reviewers = [
        row.get(f"reviewer_{index}_id", "").strip().casefold()
        for index in range(1, reviewer_count + 1)
    ]
    populated = [value for value in reviewers if value]
    adjudicator = row.get("adjudicator_id", "").strip().casefold()
    if len(populated) != len(set(populated)):
        errors.append("reviewers must be independent")
    if adjudicator and adjudicator in set(populated):
        errors.append("adjudicator must be distinct from all reviewers")
    return errors


def conditional_resolution(
    row: dict[str, str],
    signature_fields: list[str],
    *,
    require_complete: bool,
    optional_signature_fields: set[str] | None = None,
    reviewer_count: int = REVIEWER_COUNT,
    majority_threshold: int = MAJORITY_THRESHOLD,
) -> tuple[str | None, dict[str, str] | None, list[str]]:
    errors: list[str] = []
    optional_signature_fields = optional_signature_fields or set()
    reviewer_prefixes = [
        f"reviewer_{index}" for index in range(1, reviewer_count + 1)
    ]
    for prefix in reviewer_prefixes:
        status = row.get(f"{prefix}_status", "")
        metadata = [
            row.get(f"{prefix}_id", ""),
            row.get(f"{prefix}_reviewed_at", ""),
            row.get(f"{prefix}_notes", ""),
        ]
        decisions = [row.get(f"{prefix}_{field}", "") for field in signature_fields]
        if not status and any(metadata + decisions):
            errors.append(f"{prefix} has data but status is blank")
        if status and status not in {"IN_PROGRESS", "REVIEWED"}:
            errors.append(f"invalid {prefix}_status")
        if status == "REVIEWED":
            if not row.get(f"{prefix}_id") or not row.get(f"{prefix}_reviewed_at"):
                errors.append(f"{prefix} reviewed metadata is incomplete")
            if any(
                not row.get(f"{prefix}_{field}", "")
                for field in signature_fields
                if field not in optional_signature_fields
            ):
                errors.append(f"{prefix} decision signature is incomplete")
            try:
                validate_iso8601(row.get(f"{prefix}_reviewed_at", ""))
            except ValueError:
                errors.append(f"invalid {prefix}_reviewed_at")
        elif row.get(f"{prefix}_reviewed_at"):
            try:
                validate_iso8601(row[f"{prefix}_reviewed_at"])
            except ValueError:
                errors.append(f"invalid {prefix}_reviewed_at")
        if require_complete and status != "REVIEWED":
            errors.append(f"{prefix} is incomplete")

    errors.extend(reviewer_identity_errors(row, reviewer_count=reviewer_count))
    if any(row.get(f"{prefix}_status") != "REVIEWED" for prefix in reviewer_prefixes):
        return None, None, errors

    signatures = [
        {field: row.get(f"{prefix}_{field}", "") for field in signature_fields}
        for prefix in reviewer_prefixes
    ]
    signature_keys = [canonical_json(value) for value in signatures]
    counts = Counter(signature_keys)
    winning_key, winning_count = counts.most_common(1)[0]
    winning_signature = signatures[signature_keys.index(winning_key)]
    if winning_count == reviewer_count:
        if actor_fields_populated(row, "adjudicated"):
            errors.append("adjudication must be blank when reviewers agree")
        return "AGREEMENT", winning_signature, errors
    if winning_count >= majority_threshold:
        if actor_fields_populated(row, "adjudicated"):
            errors.append("adjudication must be blank when reviewer majority exists")
        return "MAJORITY", winning_signature, errors

    status = row.get("adjudication_status", "")
    adjudicated = {field: row.get(f"adjudicated_{field}", "") for field in signature_fields}
    if not status and actor_fields_populated(row, "adjudicated"):
        errors.append("adjudication has data but status is blank")
    if status != "ADJUDICATED":
        if require_complete:
            errors.append("disagreement requires adjudication")
        return "DISAGREEMENT_PENDING", None, errors
    if not row.get("adjudicator_id") or not row.get("adjudicated_at"):
        errors.append("adjudication metadata is incomplete")
    if any(
        not value
        for field, value in adjudicated.items()
        if field not in optional_signature_fields
    ):
        errors.append("adjudicated decision signature is incomplete")
    try:
        adjudicated_at = validate_iso8601(row.get("adjudicated_at", ""))
        reviewer_times = [
            validate_iso8601(row[f"reviewer_{index}_reviewed_at"])
            for index in range(1, reviewer_count + 1)
        ]
        if any(adjudicated_at < value for value in reviewer_times):
            errors.append("adjudication timestamp precedes reviewer timestamp")
    except ValueError:
        errors.append("invalid adjudicated_at")
    return "ADJUDICATED", adjudicated, errors


def agreement_summary(
    rows_by_table: dict[str, list[dict[str, str]]],
    signatures: dict[str, list[str]],
    optional_signatures: dict[str, set[str]] | None = None,
) -> dict[str, Any]:
    optional_signatures = optional_signatures or {}
    tables = {}
    total = {"agreement": 0, "majority": 0, "adjudicated": 0, "pending": 0}
    for table, rows in rows_by_table.items():
        counts = {"agreement": 0, "majority": 0, "adjudicated": 0, "pending": 0}
        for row in rows:
            mode, _, _ = conditional_resolution(
                row,
                signatures[table],
                require_complete=False,
                optional_signature_fields=optional_signatures.get(table, set()),
            )
            if mode == "AGREEMENT":
                counts["agreement"] += 1
            elif mode == "MAJORITY":
                counts["majority"] += 1
            elif mode == "ADJUDICATED":
                counts["adjudicated"] += 1
            else:
                counts["pending"] += 1
        tables[table] = counts
        for key in total:
            total[key] += counts[key]
    return {"tables": tables, "total": total}


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb",
        delete=False,
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)
