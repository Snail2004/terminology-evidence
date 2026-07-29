"""Deterministic candidate indexing, exact joins and producer-boundary checks."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import JoinError, PolicyError
from .identity import CandidateIdentity
from .inventory import ArtifactInventory, ArtifactRecord
from .jsonio import load_json
from .packages import ROLE_SCHEMA, validate_package


REQUIRED_ROLES = tuple(ROLE_SCHEMA)
SUPPORT_ROLES = {"collision_index"}


@dataclass(frozen=True)
class PackageValue:
    record: ArtifactRecord
    value: dict[str, Any]
    identity: CandidateIdentity | None


@dataclass(frozen=True)
class JoinedCandidate:
    identity: CandidateIdentity
    packages: dict[str, PackageValue]
    support: dict[str, ArtifactRecord]

    def paths(self) -> dict[str, Path]:
        return {role: item.record.path for role, item in self.packages.items()}

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_key": self.identity.as_dict(),
            "packages": {
                role: {
                    "relative_path": item.record.relative_path,
                    "physical_sha256": item.record.physical_sha256,
                    "self_sha256": item.value["integrity"]["self_sha256"],
                }
                for role, item in sorted(self.packages.items())
            },
            "support": {
                role: {"relative_path": item.relative_path, "physical_sha256": item.physical_sha256}
                for role, item in sorted(self.support.items())
            },
        }


def validate_and_join(
    inventory: ArtifactInventory,
    *,
    schema_root: Path | None = None,
) -> tuple[tuple[JoinedCandidate, ...], dict[str, Any]]:
    grouped: dict[str, dict[str, list[PackageValue]]] = defaultdict(lambda: defaultdict(list))
    support_records: dict[str, list[ArtifactRecord]] = defaultdict(list)
    failures: list[dict[str, Any]] = []
    for record in inventory.records:
        if record.role in SUPPORT_ROLES:
            support_records[record.role].append(record)
            continue
        try:
            value, identity = validate_package(record, schema_root=schema_root)
            candidate_id = (
                str(record.candidate_key.get("candidate_id"))
                if record.role == "effective_sense" and record.candidate_key is not None
                else identity.candidate_id
            )
            grouped[candidate_id][record.role].append(PackageValue(record, value, identity))
        except Exception as exc:
            failures.append({"relative_path": record.relative_path, "error_code": type(exc).__name__, "message": str(exc)})
    if failures:
        raise JoinError({"code": "PACKAGE_VALIDATION_FAILED", "failures": failures})
    joined: list[JoinedCandidate] = []
    for candidate_id in sorted(grouped):
        roles = grouped[candidate_id]
        missing = [role for role in REQUIRED_ROLES if role not in roles]
        extra = [role for role in roles if role not in REQUIRED_ROLES]
        duplicates = [role for role in roles if len(roles[role]) != 1]
        if missing or extra or duplicates:
            raise JoinError({"code": "JOIN_CARDINALITY_FAILED", "candidate_id": candidate_id, "missing": missing, "extra": extra, "duplicates": duplicates})
        values = {role: items[0] for role, items in roles.items()}
        identity = values["frozen_candidate"].identity
        for role, package in values.items():
            if role == "effective_sense":
                value = package.value
                checks = {
                    "source_term": value.get("source_term"),
                    "sense_id": value.get("sense_id"),
                    "scope_id": value.get("scope_id"),
                    "sense_inventory_version": value.get("sense_inventory_version"),
                    "dataset_manifest_sha256": value.get("parent_dataset_manifest_sha256"),
                    "effective_sense_contract_sha256": value.get("integrity", {}).get("self_sha256"),
                }
                expected = identity.as_dict()
                differing = [field for field, observed in checks.items() if observed != expected[field]]
            else:
                if package.identity is None:
                    raise JoinError({"code": "IDENTITY_MISSING", "candidate_id": candidate_id, "role": role})
                differing = [field for field in identity.as_dict() if package.identity.as_dict()[field] != identity.as_dict()[field]]
            if differing:
                raise JoinError({"code": "IDENTITY_MISMATCH", "candidate_id": candidate_id, "role": role, "fields": differing})
        # Dataset owns the frozen candidate and constraint package. C/E remain decision-neutral.
        for role in ("context_evidence", "attestation_evidence"):
            value = values[role].value
            if value.get("final_glossary_decision") is not None:
                raise PolicyError(f"{role} emitted final_glossary_decision")
        support: dict[str, ArtifactRecord] = {}
        collision_hash = values["constraints"].value.get("target_collision", {}).get("collision_index_sha256")
        if collision_hash is not None:
            collision_records = support_records.get("collision_index", [])
            if len(collision_records) != 1:
                raise JoinError({"code": "COLLISION_INDEX_CARDINALITY", "candidate_id": candidate_id, "count": len(collision_records)})
            collision = collision_records[0]
            if collision.physical_sha256 != collision_hash:
                raise JoinError({"code": "COLLISION_INDEX_HASH_MISMATCH", "candidate_id": candidate_id})
            collision_value = load_json(collision.path, require_object=True)
            keys = collision_value.get("candidate_keys")
            expected_key = {key: value for key, value in identity.as_dict().items() if key != "input_contract_sha256"}
            if not isinstance(keys, list) or sum(key == expected_key for key in keys) != 1:
                raise JoinError({"code": "COLLISION_INDEX_CANDIDATE_MISMATCH", "candidate_id": candidate_id})
            support["collision_index"] = collision
        joined.append(JoinedCandidate(identity=identity, packages=dict(values), support=support))
    report = {
        "schema_id": "ExactJoinReportV1",
        "candidate_count": len(joined),
        "joined_count": len(joined),
        "failed_count": len(failures),
        "required_roles": list(REQUIRED_ROLES),
        "candidates": [candidate.as_dict() for candidate in joined],
    }
    return tuple(joined), report
