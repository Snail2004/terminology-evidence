from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import (
    read_csv,
    read_json,
    read_jsonl,
    sha256_file,
    validate_self_hash,
)
from evidence import validate_explicit_evidence


EXPECTED_AUTHORITY = {
    "authority_tag": "contracts-v1.1.0",
    "authority_commit": "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed",
    "manifest_sha256": "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b",
}


def _checksum_map(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        result[relative] = digest
    return result


def validate_artifact(artifact_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    manifest = read_json(artifact_root / "manifest.json")
    if not validate_self_hash(manifest, "manifest_sha256"):
        errors.append("manifest self hash mismatch")
    for field, expected in EXPECTED_AUTHORITY.items():
        if manifest.get("authority", {}).get(field) != expected:
            errors.append(f"authority binding mismatch: {field}")
    for relative, binding in manifest.get("files", {}).items():
        path = artifact_root / relative
        if not path.is_file():
            errors.append(f"missing bound file: {relative}")
        elif sha256_file(path) != binding.get("sha256"):
            errors.append(f"bound file hash mismatch: {relative}")

    checksums = _checksum_map(artifact_root / "CHECKSUMS.sha256")
    actual = {
        path.relative_to(artifact_root).as_posix(): sha256_file(path)
        for path in artifact_root.rglob("*")
        if path.is_file() and path != artifact_root / "CHECKSUMS.sha256"
    }
    if checksums != actual:
        errors.append("CHECKSUMS.sha256 does not bind the complete artifact")

    consensus = read_jsonl(artifact_root / "recomputed_consensus_records_v2.jsonl")
    provenance = list((artifact_root / "reviewer_provenance").glob("*/*.json"))
    projections = list((artifact_root / "evidence_validation_sidecars").glob("*/*.jsonl"))
    projection_count = sum(len(read_jsonl(path)) for path in projections)
    blind_cases = read_csv(artifact_root / "blind_audit_pack_development_v1" / "blind_cases.csv")
    blind_headers = set(blind_cases[0]) if blind_cases else set()
    forbidden = {
        "model_definition_en",
        "model_definition_confidence",
        "model_part_of_speech",
        "model_part_of_speech_confidence",
    }
    if len(consensus) != 40:
        errors.append("expected 40 consensus records")
    if len(provenance) != 12:
        errors.append("expected 12 provenance sidecars")
    if projection_count != 120:
        errors.append("expected 120 evidence projections")
    if len(blind_cases) != 13:
        errors.append("expected 13 blind audit senses")
    if any(row.get("split") != "development" for row in blind_cases):
        errors.append("blind audit contains non-development rows")
    if forbidden & blind_headers:
        errors.append("blind audit exposes model fields")
    terms = {row.get("source_term") for row in consensus}
    if not {"Adam", "fully-connected layers", "in place"} <= terms:
        errors.append("required adjudication terms are missing")
    if any(row.get("final_glossary_decision") is not None for row in consensus):
        errors.append("dataset companion must not emit final_glossary_decision")

    report = read_json(artifact_root / "repair_validation_report.json")
    if report.get("structural_status") != "PASS":
        errors.append("repair report structural status is not PASS")
    if report.get("definition_of_done") is not False:
        errors.append("repair report overstates definition of done")
    return {
        "status": "PASS" if not errors else "FAIL",
        "artifact_status": manifest.get("status"),
        "sense_count": len(consensus),
        "provenance_sidecar_count": len(provenance),
        "evidence_projection_count": projection_count,
        "blind_audit_sense_count": len(blind_cases),
        "error_count": len(errors),
        "errors": errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args()
    report = validate_artifact(args.artifact_root.resolve())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
