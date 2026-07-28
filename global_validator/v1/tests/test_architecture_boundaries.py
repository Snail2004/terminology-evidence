from __future__ import annotations

import ast
from pathlib import Path

from terminology_contracts.integrity import verify_self_hash

from global_validator.v1.jsonio import load_json_object


FORBIDDEN_PRODUCER_PREFIXES = (
    "context_substitution",
    "vietnamese_attestation",
)
FORBIDDEN_NETWORK_PREFIXES = (
    "httpx",
    "requests",
    "socket",
    "urllib",
)


def test_runtime_has_no_producer_internal_or_network_imports(
    repository_root: Path,
) -> None:
    runtime_root = repository_root / "global_validator" / "v1"
    excluded = {"tests", "testing", "tools"}
    violations: list[str] = []
    for path in runtime_root.rglob("*.py"):
        if any(part in excluded for part in path.relative_to(runtime_root).parts):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if module.startswith(FORBIDDEN_PRODUCER_PREFIXES):
                    violations.append(f"{path}: producer import {module}")
                if module.startswith(FORBIDDEN_NETWORK_PREFIXES):
                    violations.append(f"{path}: network import {module}")
    assert violations == []


def test_release_reports_are_self_hashed(repository_root: Path) -> None:
    release = repository_root / "global_validator" / "v1" / "release"
    reports = sorted(release.glob("*.json"))
    assert len(reports) >= 7
    for path in reports:
        verify_self_hash(load_json_object(path), path=str(path))
