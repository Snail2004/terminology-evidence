"""Self-verifying System Integration reviewer package inventory."""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from jsonschema import Draft202012Validator

from integration_harness.errors import IntegrityError, StorageError, ValidationError
from integration_harness.hashing import self_sha256, sha256_file
from integration_harness.jsonio import dump_json, loads_strict
from integration_harness.paths import ensure_plain_root


RECEIPT_NAME = "D0_SYSTEM_INTEGRATION_REVIEW_RECEIPT.json"
CHECKSUMS_NAME = "CHECKSUMS.sha256"
RECEIPT_SCHEMA_ID = "SystemIntegrationD0ReviewReceiptV1"
RECEIPT_SCHEMA_VERSION = "1.0.0"
_CHECKSUM_RE = re.compile(r"([0-9a-f]{64})  (.+)")
_TOP_LEVEL_KEYS = {
    "schema_id", "schema_version", "status", "live_status", "base_commit",
    "child_commit", "child_tree", "changed_paths", "gates", "dataset_authority",
    "evaluation_producer_handoff", "main01_dependency", "invariants", "integrity",
}


def seal_review_package(
    root: Path,
    receipt_value: Mapping[str, Any],
    *,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    """Write the self-hashed receipt and a complete non-circular inventory."""

    root = ensure_plain_root(root)
    receipt_path = root / RECEIPT_NAME
    checksums_path = root / CHECKSUMS_NAME
    if receipt_path.exists() or checksums_path.exists():
        raise StorageError("review receipt/checksums already exist")
    receipt = dict(receipt_value)
    receipt["integrity"] = {"self_sha256": "0" * 64}
    receipt["integrity"]["self_sha256"] = self_sha256(receipt)
    _validate_receipt(receipt, schema_path=schema_path)
    dump_json(receipt_path, receipt)
    members = _package_members(root, excluded={CHECKSUMS_NAME})
    lines = [f"{sha256_file(root / name)}  {name}" for name in sorted(members)]
    checksums_path.write_text("\n".join(lines) + "\n", encoding="ascii", newline="\n")
    return verify_review_package(root, schema_path=schema_path)


def verify_review_package(
    root: Path,
    *,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    """Verify receipt canonical identity and every unpacked package member."""

    root = ensure_plain_root(root)
    receipt_path = root / RECEIPT_NAME
    checksums_path = root / CHECKSUMS_NAME
    if not receipt_path.is_file() or not checksums_path.is_file():
        raise IntegrityError("review package receipt or checksums is missing")
    receipt = loads_strict(receipt_path.read_bytes(), require_object=True)
    _validate_receipt(receipt, schema_path=schema_path)
    observed = _read_checksums(checksums_path)
    expected = _package_members(root, excluded={CHECKSUMS_NAME})
    if set(observed) != expected or RECEIPT_NAME not in observed:
        raise IntegrityError("review package checksum inventory is incomplete")
    for relative, claimed in observed.items():
        if sha256_file(root / relative) != claimed:
            raise IntegrityError(f"review package member hash mismatch: {relative}")
    return {
        "status": receipt["status"],
        "receipt_self_sha256": receipt["integrity"]["self_sha256"],
        "receipt_physical_sha256": sha256_file(receipt_path),
        "checksums_physical_sha256": sha256_file(checksums_path),
        "member_count": len(observed),
        "live_status": receipt["live_status"],
    }


def _validate_receipt(
    receipt: Mapping[str, Any],
    *,
    schema_path: Path | None,
) -> None:
    if set(receipt) != _TOP_LEVEL_KEYS:
        raise ValidationError("review receipt top-level contract drift")
    if (
        receipt.get("schema_id") != RECEIPT_SCHEMA_ID
        or receipt.get("schema_version") != RECEIPT_SCHEMA_VERSION
        or receipt.get("status")
        != "SI_EV02_PRODUCER_SAFE_BOUNDARY_READY_FOR_INDEPENDENT_REVIEW"
        or receipt.get("live_status") != "REVIEW_ONLY_DRAFT_INPUT"
    ):
        raise ValidationError("review receipt identity/status drift")
    for field in ("base_commit", "child_commit", "child_tree"):
        value = receipt.get(field)
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}", value):
            raise ValidationError(f"review receipt {field} is invalid")
    paths = receipt.get("changed_paths")
    if (
        not isinstance(paths, list) or not paths or paths != sorted(paths)
        or len(paths) != len(set(paths))
    ):
        raise ValidationError("review receipt changed-path inventory is invalid")
    for path in paths:
        _safe_relative(path)
    for field in (
        "gates", "dataset_authority", "evaluation_producer_handoff",
        "main01_dependency", "invariants", "integrity",
    ):
        if not isinstance(receipt.get(field), Mapping):
            raise ValidationError(f"review receipt {field} must be an object")
    integrity = receipt["integrity"]
    if set(integrity) != {"self_sha256"} or integrity.get("self_sha256") != self_sha256(receipt):
        raise IntegrityError("review receipt canonical self hash mismatch")
    if schema_path is not None:
        schema = loads_strict(schema_path.read_bytes(), require_object=True)
        Draft202012Validator.check_schema(schema)
        errors = sorted(Draft202012Validator(schema).iter_errors(receipt), key=lambda item: list(item.path))
        if errors:
            first = errors[0]
            where = ".".join(str(part) for part in first.path) or "<root>"
            raise ValidationError(f"review receipt schema failure at {where}: {first.message}")


def _read_checksums(path: Path) -> dict[str, str]:
    try:
        text = path.read_text(encoding="ascii")
    except (OSError, UnicodeDecodeError) as exc:
        raise IntegrityError("review package checksums are not ASCII") from exc
    if not text.endswith("\n"):
        raise IntegrityError("review package checksums must end with LF")
    observed: dict[str, str] = {}
    order: list[str] = []
    for line in text.splitlines():
        match = _CHECKSUM_RE.fullmatch(line)
        if match is None:
            raise IntegrityError("review package checksum line is malformed")
        relative = _safe_relative(match.group(2))
        if relative in observed:
            raise IntegrityError("review package checksum path is duplicated")
        observed[relative] = match.group(1)
        order.append(relative)
    if order != sorted(order):
        raise IntegrityError("review package checksum inventory is not sorted")
    return observed


def _package_members(root: Path, *, excluded: set[str]) -> set[str]:
    members: set[str] = set()
    folded: set[str] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise IntegrityError("review package contains a symlink")
        if not path.is_file():
            continue
        relative = _safe_relative(path.relative_to(root).as_posix())
        if relative in excluded:
            continue
        if relative.casefold() in folded:
            raise IntegrityError("review package contains case-confusable paths")
        members.add(relative)
        folded.add(relative.casefold())
    return members


def _safe_relative(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise IntegrityError("unsafe review package path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise IntegrityError("unsafe review package path")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise IntegrityError("unsafe review package path")
    if len(path.parts[0]) >= 2 and path.parts[0][1:2] == ":":
        raise IntegrityError("unsafe review package path")
    return value
