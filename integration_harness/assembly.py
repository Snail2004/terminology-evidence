"""Assembly orchestration over the public Global CLI adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .assembler import GlobalCliAdapter
from .errors import ExecutionError
from .join import JoinedCandidate
from .jsonio import load_json


def assemble_candidates(
    candidates: tuple[JoinedCandidate, ...],
    adapter: GlobalCliAdapter,
    output_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    assembled: list[dict[str, Any]] = []
    for candidate in candidates:
        output = output_dir / f"{candidate.identity.candidate_id}.json"
        adapter.assemble(candidate, output)
        value = load_json(output, require_object=True)
        if value.get("schema_id") != "GlobalValidatorInputV1":
            raise ExecutionError("Global assembler returned wrong schema")
        assembled.append({
            "candidate_id": candidate.identity.candidate_id,
            "path": output,
            "self_sha256": value.get("integrity", {}).get("self_sha256"),
        })
    return assembled, {
        "schema_id": "AssemblyReportV1",
        "candidate_count": len(assembled),
        "inputs": [
            {"candidate_id": item["candidate_id"], "self_sha256": item["self_sha256"]}
            for item in assembled
        ],
    }
