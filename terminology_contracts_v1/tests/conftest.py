from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ROOT = ROOT / "python"
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from terminology_contracts.bindings import calculate_replay_spec_sha256
from terminology_contracts.integrity import seal_self_hash
from terminology_contracts.validation import validate_instance

SCHEMAS = ROOT / "schemas"
VALID_V10 = ROOT / "examples" / "valid" / "v1.0.0"
VALID_V11 = ROOT / "examples" / "valid" / "v1.1.0"
INVALID_V11 = ROOT / "examples" / "invalid" / "v1.1.0"
MIGRATED_V11 = ROOT / "examples" / "migrated" / "v1.1.0"
MIGRATION_REPORTS = ROOT / "examples" / "migrated" / "reports"
FEATURE_REGISTRY = ROOT / "registries" / "feature_contract_v1.1.0.json"
CALIBRATION = VALID_V11 / "calibration_artifact.json"
GLOBAL_INPUT = VALID_V11 / "global_validator_input.json"
GATE_POLICY = ROOT / "policies" / "gate_policy_v1.0.0.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_v11(name: str) -> dict:
    return load_json(VALID_V11 / name)


def validate_payload(
    payload: dict,
    *,
    calibration_path: Path | None = CALIBRATION,
    global_input_path: Path | None = GLOBAL_INPUT,
    allow_legacy_migration: bool = False,
) -> list[str]:
    return validate_instance(
        payload,
        SCHEMAS,
        calibration_path=calibration_path,
        feature_registry_path=FEATURE_REGISTRY,
        global_input_path=global_input_path,
        gate_policy_path=GATE_POLICY,
        allow_legacy_migration=allow_legacy_migration,
    )


def reseal_decision(payload: dict) -> dict:
    result = copy.deepcopy(payload)
    result["run_metadata"]["input_package_hashes"][
        "gate_result_sha256"
    ] = result["gate_results"]["integrity"]["self_sha256"]
    result["run_metadata"][
        "replay_spec_sha256"
    ] = calculate_replay_spec_sha256(result)
    return seal_self_hash(result)
