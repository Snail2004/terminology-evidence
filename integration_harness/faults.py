"""Controlled test-only mutations of sealed bundles."""

from __future__ import annotations

import shutil
from pathlib import Path

from .errors import ValidationError
from .jsonio import load_json


FAULTS = {
    "missing_package",
    "duplicate_json_key",
    "nan",
    "checksum_drift",
    "identity_mismatch",
    "path_traversal",
}


def inject_fault(source: Path, destination: Path, fault: str) -> Path:
    if fault not in FAULTS:
        raise ValidationError(f"unknown fault: {fault}")
    if destination.exists():
        raise ValidationError(f"fault output already exists: {destination}")
    shutil.copytree(source, destination)
    if fault == "missing_package":
        package = next((destination / "input" / "packages").rglob("*.json"), None)
        if package is None:
            raise ValidationError("no package available for fault")
        package.unlink()
    elif fault == "duplicate_json_key":
        path = destination / "run_spec.json"
        path.write_text('{"schema_id":"SystemIntegrationRunSpecV1","schema_id":"tampered"}\n', encoding="utf-8", newline="\n")
    elif fault == "nan":
        path = destination / "run_spec.json"
        path.write_text('{"value":NaN}\n', encoding="utf-8", newline="\n")
    elif fault == "checksum_drift":
        path = destination / "run_spec.json"
        path.write_text(path.read_text(encoding="utf-8") + "x", encoding="utf-8", newline="\n")
    elif fault == "identity_mismatch":
        path = next((destination / "input" / "packages").rglob("frozen_candidate.json"), None)
        if path is None:
            raise ValidationError("frozen candidate is unavailable")
        value = load_json(path, require_object=True)
        value["candidate_key"]["candidate_id"] = "foreign-candidate"
        path.write_text(__import__("json").dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    elif fault == "path_traversal":
        path = destination / "CHECKSUMS.sha256"
        path.write_text(path.read_text(encoding="utf-8") + "0  ../escape\n", encoding="utf-8", newline="\n")
    return destination
