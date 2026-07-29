"""Static scans and versioned findings for the readiness release."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any, Iterable

from ..zero_api.artifacts import self_sha256


def seal(value: dict[str, Any]) -> dict[str, Any]:
    payload = json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))
    payload["integrity"] = {"self_sha256": "0" * 64}
    payload["integrity"]["self_sha256"] = self_sha256(payload)
    return payload


def static_scan(root: Path, paths: Iterable[str]) -> dict[str, Any]:
    failures: list[str] = []
    module_count = 0
    for relative in paths:
        if not relative.endswith(".py"):
            continue
        module_count += 1
        path = root / relative
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        except (OSError, UnicodeError, SyntaxError) as exc:
            failures.append(f"{relative}: {exc}")
    return seal(
        {
            "schema_id": "VietnameseAttestationStaticScanV1",
            "schema_version": "1.0.0",
            "status": "PASS" if not failures else "FAIL",
            "python_module_count": module_count,
            "failures": failures,
        }
    )


def credential_scan(root: Path, paths: Iterable[str]) -> dict[str, Any]:
    patterns = {
        "OPENAI_STYLE_KEY": re.compile(b"s" + rb"k-[A-Za-z0-9_-]{20,}"),
        "GOOGLE_API_KEY": re.compile(b"AI" + rb"za[0-9A-Za-z_-]{30,}"),
        "PRIVATE_KEY": re.compile(
            b"-----BEGIN " + rb"[A-Z ]*PRIVATE KEY-----"
        ),
    }
    findings: list[dict[str, str]] = []
    credential_prefix = "API" + "-Key/"
    for relative in paths:
        if credential_prefix in relative or relative.startswith(credential_prefix):
            findings.append({"path": relative, "kind": "FORBIDDEN_CREDENTIAL_PATH"})
            continue
        raw = (root / relative).read_bytes()
        for kind, pattern in patterns.items():
            if pattern.search(raw):
                findings.append({"path": relative, "kind": kind})
    return seal(
        {
            "schema_id": "VietnameseAttestationCredentialScanV1",
            "schema_version": "1.0.0",
            "status": "PASS" if not findings else "FAIL",
            "finding_count": len(findings),
            "findings": findings,
        }
    )


def findings_report(canonical_main: str) -> dict[str, Any]:
    return {
        "schema_id": "VietnameseAttestationReadinessFindingsV1",
        "schema_version": "1.0.0",
        "status": "HOLD_EXTERNAL_INPUTS",
        "report_version": "1.2.1",
        "canonical_main_at_build": canonical_main,
        "findings": [
            {
                "finding_id": "E-RDY-001",
                "severity": "INFO",
                "status": "RESOLVED",
                "summary": "Zero-API milestone metadata was stale in V1.2 draft",
                "resolution": "Use a1707a8 as integration commit and 66/66 plus 8/8 gates",
            },
            {
                "finding_id": "E-RDY-002",
                "severity": "BLOCKER",
                "status": "HOLD_EXTERNAL",
                "summary": "Official Dataset-owned Frozen Candidates are unavailable",
                "required_to_close": "15 COMPLETE FrozenCandidateContractV1@1.1.0 inputs",
            },
            {
                "finding_id": "E-RDY-003",
                "severity": "BLOCKER",
                "status": "HOLD_EXTERNAL",
                "summary": "Controlled Vietnamese registry is empty",
                "required_to_close": "Non-empty sealed registry plus retrieval content authority",
            },
            {
                "finding_id": "E-RDY-004",
                "severity": "BLOCKER",
                "status": "HOLD_APPROVAL",
                "summary": "Provider compatibility canaries are not authorized",
                "required_to_close": "Explicit maintainer approval and safe secret loading",
            },
            {
                "finding_id": "E-RDY-005",
                "severity": "INFO",
                "status": "RESOLVED",
                "summary": "Global Validator executable is integrated on canonical main",
                "resolution": "E handoff remains blocked only by official E evidence inputs",
            },
            {
                "finding_id": "E-RDY-006",
                "severity": "LOW",
                "status": "RESOLVED",
                "summary": "Initial ZIP ordering followed Windows Path comparison",
                "resolution": "Release members are sorted by canonical POSIX relative path",
            },
        ],
        "provider_call_count": 0,
        "final_glossary_decision": None,
    }


__all__ = ["credential_scan", "findings_report", "seal", "static_scan"]
