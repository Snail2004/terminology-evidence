from __future__ import annotations

from pathlib import Path
from typing import Any

from common import read_json, sha256_file


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REVIEW_SCHEMA_PATH = PACKAGE_ROOT / "stage_a_review_schema_v1_2.json"
CONSENSUS_POLICY_PATH = PACKAGE_ROOT / "stage_a_consensus_policy_v1_2.json"
POLICY_DOCUMENT_PATH = PACKAGE_ROOT / "stage_a_policy_v1_2.md"


def load_review_schema() -> dict[str, Any]:
    return read_json(REVIEW_SCHEMA_PATH)


def load_consensus_policy() -> dict[str, Any]:
    return read_json(CONSENSUS_POLICY_PATH)


def policy_bindings() -> dict[str, dict[str, str]]:
    return {
        "review_schema": {
            "ref": REVIEW_SCHEMA_PATH.name,
            "sha256": sha256_file(REVIEW_SCHEMA_PATH),
        },
        "consensus_policy": {
            "ref": CONSENSUS_POLICY_PATH.name,
            "sha256": sha256_file(CONSENSUS_POLICY_PATH),
        },
        "policy_document": {
            "ref": POLICY_DOCUMENT_PATH.name,
            "sha256": sha256_file(POLICY_DOCUMENT_PATH),
        },
    }
