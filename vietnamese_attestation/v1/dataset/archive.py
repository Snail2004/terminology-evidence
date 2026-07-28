from __future__ import annotations

import hashlib
import json
import re
import stat
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from .specs import (
    SUPPORTED_BY_ZIP_SHA256,
    DatasetArtifactSpec,
    V3_SPEC,
)


MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
CORE_ROW_FILES = (
    "term_senses.jsonl",
    "candidate_instances.jsonl",
    "contexts.jsonl",
)
SHA256_RE = re.compile(r"[0-9a-f]{64}")


class DatasetAdapterError(ValueError):
    def __init__(self, code: str, path: str, detail: str) -> None:
        super().__init__(f"{code} at {path}: {detail}")
        self.code = code
        self.path = path
        self.detail = detail


@dataclass(frozen=True)
class VerifiedDatasetArchive:
    path: Path
    spec: DatasetArtifactSpec
    zip_sha256: str
    manifest_file_sha256: str
    manifest: dict[str, Any]
    term_senses: tuple[dict[str, Any], ...]
    candidate_instances: tuple[dict[str, Any], ...]
    contexts: tuple[dict[str, Any], ...]
    candidate_slots: tuple[dict[str, Any], ...]
    raw_jsonl_rows: dict[str, tuple[bytes, ...]]


def load_supported_dataset_archive(
    zip_path: str | Path,
) -> VerifiedDatasetArchive:
    path = Path(zip_path).resolve(strict=True)
    if not path.is_file():
        raise DatasetAdapterError(
            "source_not_file", "$source_zip", "source must be a ZIP file"
        )
    zip_sha256 = _sha256_file(path)
    try:
        archive = zipfile.ZipFile(path, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise DatasetAdapterError(
            "invalid_zip", "$source_zip", str(exc)
        ) from exc
    with archive:
        validate_zip_member_names(archive.infolist())
        spec = SUPPORTED_BY_ZIP_SHA256.get(zip_sha256)
        if spec is None:
            raise DatasetAdapterError(
                "unsupported_zip_sha256",
                "$source_zip",
                f"unsupported physical ZIP SHA-256 {zip_sha256}",
            )
        manifest_bytes = _read_entry(archive, "manifest.json")
        manifest_file_sha256 = _sha256_bytes(manifest_bytes)
        if manifest_file_sha256 != spec.manifest_file_sha256:
            raise DatasetAdapterError(
                "manifest_file_hash",
                "$.manifest",
                "manifest file SHA-256 differs from the supported authority",
            )
        manifest = _parse_json_object(manifest_bytes, path="$.manifest")
        _validate_manifest(archive, manifest, spec)
        raw_rows = {
            name: _jsonl_lines(_read_entry(archive, name), path=f"$.{name}")
            for name in CORE_ROW_FILES
        }
        term_senses = tuple(
            _parse_json_object(row, path=f"$.term_senses[{index}]")
            for index, row in enumerate(raw_rows["term_senses.jsonl"])
        )
        candidates = tuple(
            _parse_json_object(row, path=f"$.candidates[{index}]")
            for index, row in enumerate(
                raw_rows["candidate_instances.jsonl"]
            )
        )
        contexts = tuple(
            _parse_json_object(row, path=f"$.contexts[{index}]")
            for index, row in enumerate(raw_rows["contexts.jsonl"])
        )
        slots: tuple[dict[str, Any], ...] = ()
        if spec == V3_SPEC:
            slot_lines = _jsonl_lines(
                _read_entry(archive, "candidate_slots.jsonl"),
                path="$.candidate_slots.jsonl",
            )
            slots = tuple(
                _parse_json_object(row, path=f"$.candidate_slots[{index}]")
                for index, row in enumerate(slot_lines)
            )
            raw_rows["candidate_slots.jsonl"] = slot_lines
        _validate_core_rows(
            spec=spec,
            term_senses=term_senses,
            candidates=candidates,
            contexts=contexts,
            candidate_slots=slots,
        )
    return VerifiedDatasetArchive(
        path=path,
        spec=spec,
        zip_sha256=zip_sha256,
        manifest_file_sha256=manifest_file_sha256,
        manifest=manifest,
        term_senses=term_senses,
        candidate_instances=candidates,
        contexts=contexts,
        candidate_slots=slots,
        raw_jsonl_rows=raw_rows,
    )


def validate_zip_member_names(infos: Sequence[zipfile.ZipInfo]) -> None:
    names: set[str] = set()
    folded: set[str] = set()
    total_size = 0
    for index, info in enumerate(infos):
        name = info.filename
        member_path = f"$.zip_members[{index}]"
        if not isinstance(name, str) or not name:
            raise DatasetAdapterError(
                "unsafe_zip_name", member_path, "empty member name"
            )
        if name != unicodedata.normalize("NFC", name):
            raise DatasetAdapterError(
                "unsafe_zip_name", member_path, "member name is not NFC"
            )
        if "\\" in name or name.startswith(("/", "//")):
            raise DatasetAdapterError(
                "unsafe_zip_name",
                member_path,
                "absolute or backslash ZIP member name",
            )
        if re.match(r"^[A-Za-z]:", name) or any(
            ord(character) < 32 for character in name
        ):
            raise DatasetAdapterError(
                "unsafe_zip_name", member_path, "drive or control character"
            )
        parts = PurePosixPath(name.rstrip("/")).parts
        if not parts or any(part in {"", ".", ".."} for part in parts):
            raise DatasetAdapterError(
                "unsafe_zip_name", member_path, "non-canonical member path"
            )
        canonical = "/".join(parts) + ("/" if info.is_dir() else "")
        if canonical != name:
            raise DatasetAdapterError(
                "unsafe_zip_name", member_path, "non-canonical member name"
            )
        if name in names:
            raise DatasetAdapterError(
                "duplicate_zip_name", member_path, f"duplicate {name!r}"
            )
        folded_name = unicodedata.normalize("NFC", name).casefold()
        if folded_name in folded:
            raise DatasetAdapterError(
                "case_confusable_zip_name",
                member_path,
                f"case-confusable duplicate {name!r}",
            )
        names.add(name)
        folded.add(folded_name)
        if info.flag_bits & 0x1:
            raise DatasetAdapterError(
                "encrypted_zip_member", member_path, name
            )
        unix_mode = (info.external_attr >> 16) & 0xFFFF
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise DatasetAdapterError("zip_symlink", member_path, name)
        if info.file_size > MAX_ENTRY_BYTES:
            raise DatasetAdapterError(
                "zip_entry_too_large", member_path, name
            )
        total_size += info.file_size
        if total_size > MAX_ARCHIVE_BYTES:
            raise DatasetAdapterError(
                "zip_archive_too_large",
                "$.zip_members",
                "uncompressed archive exceeds the closed cap",
            )


def _validate_manifest(
    archive: zipfile.ZipFile,
    manifest: Mapping[str, Any],
    spec: DatasetArtifactSpec,
) -> None:
    _expect_equal(manifest, "schema_id", spec.schema_id, "$.manifest")
    _expect_equal(
        manifest, "schema_version", spec.schema_version, "$.manifest"
    )
    _expect_equal(
        manifest, "manifest_sha256", spec.manifest_sha256, "$.manifest"
    )
    if _sha256_json_without(manifest, "manifest_sha256") != spec.manifest_sha256:
        raise DatasetAdapterError(
            "manifest_self_hash",
            "$.manifest.manifest_sha256",
            "manifest self-hash mismatch",
        )
    files = _require_mapping(manifest.get("files"), "$.manifest.files")
    archive_names = {
        info.filename for info in archive.infolist() if not info.is_dir()
    }
    bound_names = {"manifest.json"}
    for logical_name, raw_binding in files.items():
        if not isinstance(logical_name, str):
            raise DatasetAdapterError(
                "manifest_file_name", "$.manifest.files", "non-string key"
            )
        binding = _require_mapping(
            raw_binding, f"$.manifest.files.{logical_name}"
        )
        if set(binding) != {"ref", "sha256"}:
            raise DatasetAdapterError(
                "manifest_file_binding",
                f"$.manifest.files.{logical_name}",
                "file binding must contain only ref and sha256",
            )
        ref = _require_string(
            binding.get("ref"), f"$.manifest.files.{logical_name}.ref"
        )
        if ref != logical_name:
            raise DatasetAdapterError(
                "manifest_file_binding",
                f"$.manifest.files.{logical_name}.ref",
                "logical name and ref differ",
            )
        expected_sha = _require_sha256(
            binding.get("sha256"),
            f"$.manifest.files.{logical_name}.sha256",
        )
        bound_names.add(ref)
        actual_sha = _sha256_bytes(_read_entry(archive, ref))
        if actual_sha != expected_sha:
            raise DatasetAdapterError(
                "manifest_bound_file_hash",
                f"$.manifest.files.{logical_name}",
                "manifest-bound file SHA-256 mismatch",
            )
    if archive_names != bound_names:
        raise DatasetAdapterError(
            "manifest_file_coverage",
            "$.manifest.files",
            "archive members and manifest bindings differ",
        )


def _validate_core_rows(
    *,
    spec: DatasetArtifactSpec,
    term_senses: Sequence[Mapping[str, Any]],
    candidates: Sequence[Mapping[str, Any]],
    contexts: Sequence[Mapping[str, Any]],
    candidate_slots: Sequence[Mapping[str, Any]],
) -> None:
    if len(term_senses) != spec.term_sense_count:
        _count_error("term_senses", spec.term_sense_count, len(term_senses))
    if len(candidates) != spec.candidate_count:
        _count_error("candidates", spec.candidate_count, len(candidates))
    if len(contexts) != spec.context_count:
        _count_error("contexts", spec.context_count, len(contexts))
    for index, row in enumerate(term_senses):
        _validate_row_identity(
            row,
            path=f"$.term_senses[{index}]",
            schema_id="D2LContextSupportTermSenseV3",
            self_hash_field="term_sense_sha256",
            dataset_version=spec.dataset_version,
        )
    for index, row in enumerate(candidates):
        _validate_row_identity(
            row,
            path=f"$.candidates[{index}]",
            schema_id="D2LContextSupportCandidateInstanceV3",
            self_hash_field="candidate_instance_sha256",
            dataset_version=spec.dataset_version,
        )
    for index, row in enumerate(contexts):
        path = f"$.contexts[{index}]"
        _validate_row_identity(
            row,
            path=path,
            schema_id="D2LContextSupportContextV3",
            self_hash_field="context_sha256",
            dataset_version=spec.dataset_version,
        )
        _validate_context_content(row, path=path)
    senses_by_join = _unique_by_join(term_senses, "term_senses")
    senses_by_context_join = _unique_by_context_join(term_senses)
    sense_ids = _unique_ids(term_senses, "sense_id", "term_senses")
    candidate_ids = _unique_ids(
        candidates, "candidate_instance_id", "candidates"
    )
    context_ids = _unique_ids(contexts, "context_id", "contexts")
    if len(sense_ids) != len(senses_by_join):
        raise DatasetAdapterError(
            "sense_identity_collision",
            "$.term_senses",
            "sense_id and exact join key are not one-to-one",
        )
    candidates_per_sense: Counter[str] = Counter()
    for index, row in enumerate(candidates):
        sense = _join_sense(row, senses_by_join, f"$.candidates[{index}]")
        candidates_per_sense[str(sense["sense_id"])] += 1
    if set(candidates_per_sense.values()) != {3}:
        raise DatasetAdapterError(
            "candidate_cardinality",
            "$.candidates",
            "every sense must have exactly three candidate instances",
        )
    contexts_by_id = {
        str(row["context_id"]): row for row in contexts
    }
    for index, row in enumerate(contexts):
        _join_context_sense(
            row, senses_by_context_join, f"$.contexts[{index}]"
        )
    for index, sense in enumerate(term_senses):
        _validate_sense_context_refs(
            sense,
            contexts_by_id=contexts_by_id,
            path=f"$.term_senses[{index}]",
        )
    role_counts = Counter(str(row.get("context_role")) for row in contexts)
    if dict(sorted(role_counts.items())) != dict(spec.context_role_counts):
        raise DatasetAdapterError(
            "context_role_counts",
            "$.contexts",
            "context role counts differ from the sealed artifact spec",
        )
    split_counts = Counter(str(row.get("split")) for row in term_senses)
    if dict(sorted(split_counts.items())) != dict(spec.split_counts):
        raise DatasetAdapterError(
            "split_counts",
            "$.term_senses",
            "split counts differ from the sealed artifact spec",
        )
    if candidate_slots:
        if len(candidate_slots) != spec.candidate_count:
            _count_error(
                "candidate_slots", spec.candidate_count, len(candidate_slots)
            )
        slots_by_id: dict[str, Mapping[str, Any]] = {}
        for index, row in enumerate(candidate_slots):
            path = f"$.candidate_slots[{index}]"
            _validate_row_identity(
                row,
                path=path,
                schema_id="D2LContextSupportCandidateSlotV3",
                self_hash_field="candidate_slot_sha256",
                dataset_version=spec.dataset_version,
            )
            slot_id = _require_string(row.get("candidate_slot_id"), path)
            if slot_id in slots_by_id:
                raise DatasetAdapterError(
                    "duplicate_id", path, f"duplicate slot {slot_id}"
                )
            slots_by_id[slot_id] = row
        for index, candidate in enumerate(candidates):
            path = f"$.candidates[{index}]"
            slot_id = _require_string(
                candidate.get("candidate_slot_id"),
                f"{path}.candidate_slot_id",
            )
            slot = slots_by_id.get(slot_id)
            if slot is None:
                raise DatasetAdapterError(
                    "broken_candidate_slot_ref", path, slot_id
                )
            for field in (
                "candidate_instance_id",
                "candidate_target_vi",
                "formation_method",
                "term_id",
                "sense_id",
                "scope_id",
                "shared_context_set_id",
            ):
                if candidate.get(field) != slot.get(field):
                    raise DatasetAdapterError(
                        "candidate_slot_mismatch", f"{path}.{field}", field
                    )
    del candidate_ids, context_ids


def _validate_row_identity(
    row: Mapping[str, Any],
    *,
    path: str,
    schema_id: str,
    self_hash_field: str,
    dataset_version: str,
) -> None:
    _expect_equal(row, "schema_id", schema_id, path)
    _expect_equal(row, "schema_version", "3.0.0", path)
    _expect_equal(row, "dataset_version", dataset_version, path)
    expected = _require_sha256(row.get(self_hash_field), f"{path}.{self_hash_field}")
    if _sha256_json_without(row, self_hash_field) != expected:
        raise DatasetAdapterError(
            "row_self_hash", f"{path}.{self_hash_field}", "mismatch"
        )


def _validate_context_content(row: Mapping[str, Any], *, path: str) -> None:
    source_text = _require_string(row.get("source_text"), f"{path}.source_text")
    content_sha = _require_sha256(
        row.get("content_sha256"), f"{path}.content_sha256"
    )
    if _sha256_bytes(source_text.encode("utf-8")) != content_sha:
        raise DatasetAdapterError(
            "context_content_hash", f"{path}.content_sha256", "mismatch"
        )
    start = _require_nonnegative_int(row.get("match_start"), f"{path}.match_start")
    end = _require_nonnegative_int(row.get("match_end"), f"{path}.match_end")
    if start >= end or end > len(source_text):
        raise DatasetAdapterError(
            "context_offset", path, "context-relative offsets are invalid"
        )
    matched = _require_string(row.get("matched_surface"), f"{path}.matched_surface")
    if source_text[start:end].casefold() != matched.casefold():
        raise DatasetAdapterError(
            "context_offset", path, "matched surface differs at offsets"
        )
    provenance = _require_mapping(row.get("provenance"), f"{path}.provenance")
    if "source_start" in provenance:
        source_start = _require_nonnegative_int(
            provenance.get("source_start"), f"{path}.provenance.source_start"
        )
        if row.get("source_match_start_absolute") != source_start + start:
            raise DatasetAdapterError(
                "source_offset", path, "absolute match start mismatch"
            )
        if row.get("source_match_end_absolute") != source_start + end:
            raise DatasetAdapterError(
                "source_offset", path, "absolute match end mismatch"
            )
    elif row.get("source_match_start_absolute") is not None or row.get(
        "source_match_end_absolute"
    ) is not None:
        raise DatasetAdapterError(
            "source_offset", path, "synthetic context has absolute offsets"
        )


def _validate_sense_context_refs(
    sense: Mapping[str, Any],
    *,
    contexts_by_id: Mapping[str, Mapping[str, Any]],
    path: str,
) -> None:
    role_fields = {
        "primary_context_ids": "PRIMARY",
        "backup_context_ids": "BACKUP",
        "contrastive_context_ids": "CONTRASTIVE",
    }
    all_refs: list[str] = []
    for field, role in role_fields.items():
        values = _require_string_list(sense.get(field), f"{path}.{field}")
        all_refs.extend(values)
        for context_id in values:
            context = contexts_by_id.get(context_id)
            if context is None:
                raise DatasetAdapterError(
                    "broken_context_ref", f"{path}.{field}", context_id
                )
            if context.get("context_role") != role:
                raise DatasetAdapterError(
                    "context_role_mismatch", f"{path}.{field}", context_id
                )
            if _context_join_key(context) != _context_join_key(sense):
                raise DatasetAdapterError(
                    "context_join_mismatch", f"{path}.{field}", context_id
                )
    if len(all_refs) != len(set(all_refs)):
        raise DatasetAdapterError(
            "duplicate_context_ref", path, "context role references overlap"
        )


def _unique_by_join(
    rows: Sequence[Mapping[str, Any]], name: str
) -> dict[tuple[str, str, str, str], Mapping[str, Any]]:
    output: dict[tuple[str, str, str, str], Mapping[str, Any]] = {}
    for index, row in enumerate(rows):
        key = _join_key(row)
        if key in output:
            raise DatasetAdapterError(
                "duplicate_join_key", f"$.{name}[{index}]", repr(key)
            )
        output[key] = row
    return output


def _unique_by_context_join(
    rows: Sequence[Mapping[str, Any]],
) -> dict[tuple[str, str, str], Mapping[str, Any]]:
    output: dict[tuple[str, str, str], Mapping[str, Any]] = {}
    for index, row in enumerate(rows):
        key = _context_join_key(row)
        if key in output:
            raise DatasetAdapterError(
                "ambiguous_context_scope",
                f"$.term_senses[{index}]",
                "context join key maps to more than one scope_id",
            )
        output[key] = row
    return output


def _unique_ids(
    rows: Sequence[Mapping[str, Any]], field: str, name: str
) -> set[str]:
    output: set[str] = set()
    for index, row in enumerate(rows):
        value = _require_string(row.get(field), f"$.{name}[{index}].{field}")
        if value in output:
            raise DatasetAdapterError(
                "duplicate_id", f"$.{name}[{index}].{field}", value
            )
        output.add(value)
    return output


def _join_sense(
    row: Mapping[str, Any],
    senses: Mapping[tuple[str, str, str, str], Mapping[str, Any]],
    path: str,
) -> Mapping[str, Any]:
    key = _join_key(row)
    sense = senses.get(key)
    if sense is None:
        raise DatasetAdapterError("broken_sense_join", path, repr(key))
    return sense


def _join_context_sense(
    row: Mapping[str, Any],
    senses: Mapping[tuple[str, str, str], Mapping[str, Any]],
    path: str,
) -> Mapping[str, Any]:
    key = _context_join_key(row)
    sense = senses.get(key)
    if sense is None:
        raise DatasetAdapterError("broken_context_sense_join", path, repr(key))
    return sense


def _join_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return tuple(
        _require_string(row.get(field), f"$.{field}")
        for field in (
            "term_id",
            "sense_id",
            "scope_id",
            "shared_context_set_id",
        )
    )


def _context_join_key(row: Mapping[str, Any]) -> tuple[str, str, str]:
    return tuple(
        _require_string(row.get(field), f"$.{field}")
        for field in ("term_id", "sense_id", "shared_context_set_id")
    )


def _parse_json_object(raw: bytes, *, path: str) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates)
    except (UnicodeDecodeError, json.JSONDecodeError, DatasetAdapterError) as exc:
        if isinstance(exc, DatasetAdapterError):
            raise
        raise DatasetAdapterError("invalid_json", path, str(exc)) from exc
    if not isinstance(value, dict):
        raise DatasetAdapterError("json_type", path, "object required")
    return value


def _no_duplicates(pairs: Iterable[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise DatasetAdapterError(
                "duplicate_json_key", "$.json", f"duplicate key {key!r}"
            )
        output[key] = value
    return output


def _jsonl_lines(raw: bytes, *, path: str) -> tuple[bytes, ...]:
    lines = tuple(line for line in raw.splitlines() if line.strip())
    if not lines:
        raise DatasetAdapterError("empty_jsonl", path, "no rows")
    return lines


def _read_entry(archive: zipfile.ZipFile, name: str) -> bytes:
    try:
        info = archive.getinfo(name)
    except KeyError as exc:
        raise DatasetAdapterError("missing_zip_member", "$.zip", name) from exc
    if info.is_dir():
        raise DatasetAdapterError("zip_member_type", "$.zip", name)
    with archive.open(info, "r") as handle:
        raw = handle.read(MAX_ENTRY_BYTES + 1)
    if len(raw) > MAX_ENTRY_BYTES:
        raise DatasetAdapterError("zip_entry_too_large", "$.zip", name)
    return raw


def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DatasetAdapterError("type", path, "object required")
    return value


def _require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise DatasetAdapterError("type", path, "non-empty string required")
    return value


def _require_sha256(value: Any, path: str) -> str:
    text = _require_string(value, path)
    if not SHA256_RE.fullmatch(text):
        raise DatasetAdapterError("sha256", path, "lowercase SHA-256 required")
    return text


def _require_nonnegative_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DatasetAdapterError("type", path, "non-negative integer required")
    return value


def _require_string_list(value: Any, path: str) -> list[str]:
    if not isinstance(value, list):
        raise DatasetAdapterError("type", path, "array required")
    output = [
        _require_string(item, f"{path}[{index}]")
        for index, item in enumerate(value)
    ]
    if len(output) != len(set(output)):
        raise DatasetAdapterError("duplicate_array_item", path, "duplicates")
    return output


def _expect_equal(
    row: Mapping[str, Any], field: str, expected: Any, path: str
) -> None:
    if row.get(field) != expected:
        raise DatasetAdapterError(
            "unexpected_value",
            f"{path}.{field}",
            f"expected {expected!r}, got {row.get(field)!r}",
        )


def _count_error(name: str, expected: int, actual: int) -> None:
    raise DatasetAdapterError(
        "row_count", f"$.{name}", f"expected {expected}, got {actual}"
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_json_without(row: Mapping[str, Any], field: str) -> str:
    payload = {key: value for key, value in row.items() if key != field}
    raw = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return _sha256_bytes(raw)


__all__ = [
    "DatasetAdapterError",
    "VerifiedDatasetArchive",
    "load_supported_dataset_archive",
    "validate_zip_member_names",
]
