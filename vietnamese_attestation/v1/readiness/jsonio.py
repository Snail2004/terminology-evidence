"""Compatibility exports for the shared strict persisted-data decoder."""

from ..strict_json import (
    canonical_relative_ref,
    load_strict_json,
    load_strict_json_object,
    load_strict_jsonl,
    regular_files,
    reject_link,
    reject_symlink_tree,
    resolve_artifact_file,
    resolve_artifact_root,
    strict_json_loads,
    strict_jsonl_loads,
)

__all__ = [
    "canonical_relative_ref",
    "load_strict_json",
    "load_strict_json_object",
    "load_strict_jsonl",
    "regular_files",
    "reject_link",
    "reject_symlink_tree",
    "resolve_artifact_file",
    "resolve_artifact_root",
    "strict_json_loads",
    "strict_jsonl_loads",
]
