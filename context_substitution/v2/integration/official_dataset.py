from __future__ import annotations

import copy
import hashlib
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from context_substitution.v2.integration.authority import (
    AUTHORITY_COMMIT,
    AUTHORITY_TAG,
    CONTRACT_MANIFEST_SHA256,
    canonical_sha256,
    validate_authority,
    validate_official_contract,
    verify_frozen_candidate_binding,
)
from context_substitution.v2.integration.common import (
    file_sha256,
)
from context_substitution.v2.jsonio import loads_strict


OFFICIAL_MAIN_COMMIT = "7fd046cc6a9b8f78fd122549feaefa4b2ab83821"
OFFICIAL_ZIP_NAME = "d2l_stage_a_pilot_5_senses_official_v1_reviewer_handoff.zip"
OFFICIAL_ZIP_SHA256 = (
    "9b6a9ee1272b6403054b61f5399d4391328d1d2d8a964b1102af0a2656bc2738"
)
OFFICIAL_PIN_SELF_SHA256 = (
    "7ae7c94176e32b419cfac4bb36704d633c550068e34d00b80389ebb20f035b05"
)
OFFICIAL_MANIFEST_SELF_SHA256 = (
    "16bd2b9c7a974bdccfb977384fa1a35381e6e810c110f489f31d1606398ce2f5"
)
PARENT_DATASET_MANIFEST_SHA256 = (
    "258ebe5d907a0a108a1b80a1ec1aad3c6e265ed1a8edbd5701cc128e273122ce"
)
REVIEWED_DATASET_MANIFEST_SHA256 = (
    "e602af02edf1fb877a9541c5e37f939f4f35ded34ac878d773fc83b96ed3fb48"
)
REVIEWED_PRODUCER_COMMIT = "c585308abbdcd64af7d9c428509e441e56090bee"
EXCLUDED_ELEVEN_SENSE_COMMIT = "b03093dd700f6b5ef87b43d97f4cc1852bea7c4c"

OFFICIAL_ADAPTER_RECEIPT_SCHEMA_ID = "D2LOfficial5SenseCAdapterReceiptV1"
OFFICIAL_RUNTIME_RECEIPT_SCHEMA_ID = "D2LOfficial5SenseCRuntimeReceiptV1"
OFFICIAL_RECEIPT_SCHEMA_VERSION = "1.0.0"

_MANIFEST_SCHEMA_ID = "D2LOfficial5SensePilotManifestV1"
_SELECTION_SCHEMA_ID = "D2LIntegrationPilot5SelectionReceiptV1"
_INDEX_SCHEMA_ID = "D2LOfficialPilotCandidateIndexV1"
_CANONICAL_ZIP_PATH = (
    "review_evidence/dataset/d2l-stage-a-official-5-sense-pilot-v1/"
    + OFFICIAL_ZIP_NAME
)
_EXPECTED_SOURCE_TERMS = (
    "null hypothesis",
    "output gate",
    "Jupyter notebook",
    "learning rate",
    "contexts",
)
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class OfficialDatasetPilot:
    zip_path: Path
    zip_sha256: str
    pin_path: Path
    pin_physical_sha256: str
    pin: dict[str, Any]
    manifest: dict[str, Any]
    file_bytes: dict[str, bytes]
    selection_receipt: dict[str, Any]
    candidate_index: dict[str, Any]
    term_senses: tuple[dict[str, Any], ...]
    contexts: tuple[dict[str, Any], ...]
    candidate_instances: tuple[dict[str, Any], ...]
    effective_senses: tuple[dict[str, Any], ...]
    frozen_candidates: tuple[dict[str, Any], ...]
    constraint_packages: tuple[dict[str, Any], ...]


def load_official_dataset_pilot(
    zip_path: Path,
    pin_path: Path,
) -> OfficialDatasetPilot:
    """Load the exact five-sense Dataset authority without extracting it."""

    validate_authority()
    source_zip = Path(zip_path).resolve()
    source_pin = Path(pin_path).resolve()
    zip_sha = file_sha256(source_zip)
    if zip_sha != OFFICIAL_ZIP_SHA256:
        raise ValueError("official five-sense ZIP physical SHA mismatch")
    pin_bytes = source_pin.read_bytes()
    pin = loads_strict(pin_bytes, source=source_pin.as_posix(), require_object=True)
    _validate_pin(pin, zip_path=source_zip)
    pin_physical_sha = hashlib.sha256(pin_bytes).hexdigest()

    with zipfile.ZipFile(source_zip) as archive:
        file_bytes = _validated_archive_bytes(archive, pin=pin)
    if EXCLUDED_ELEVEN_SENSE_COMMIT.encode("ascii") in b"".join(file_bytes.values()):
        raise ValueError("excluded eleven-sense lineage appears inside official ZIP")

    manifest = _load_object(file_bytes, "manifest.json")
    _validate_manifest(manifest, file_bytes=file_bytes, pin=pin)
    selection_receipt = _load_object(
        file_bytes, "integration_pilot_5_sense_selection_receipt.json"
    )
    candidate_index = _load_object(file_bytes, "candidate_index_15.json")
    _verify_nested_self_hash(selection_receipt, "selection receipt")
    _verify_nested_self_hash(candidate_index, "candidate index")
    if selection_receipt.get("schema_id") != _SELECTION_SCHEMA_ID:
        raise ValueError("official selection receipt schema mismatch")
    if candidate_index.get("schema_id") != _INDEX_SCHEMA_ID:
        raise ValueError("official candidate index schema mismatch")

    term_senses = tuple(
        _load_jsonl(file_bytes, "materialized_input/term_senses_5.jsonl")
    )
    contexts = tuple(_load_jsonl(file_bytes, "materialized_input/contexts_29.jsonl"))
    candidate_instances = tuple(
        _load_jsonl(file_bytes, "materialized_input/candidate_instances_15.jsonl")
    )
    effective_senses = tuple(
        _load_prefix_objects(file_bytes, "effective_sense_contracts_5/")
    )
    frozen_candidates = tuple(
        _load_prefix_objects(file_bytes, "frozen_candidate_contracts_15/")
    )
    constraint_packages = tuple(
        _load_prefix_objects(file_bytes, "constraint_evidence_packages_15/")
    )
    pilot = OfficialDatasetPilot(
        zip_path=source_zip,
        zip_sha256=zip_sha,
        pin_path=source_pin,
        pin_physical_sha256=pin_physical_sha,
        pin=pin,
        manifest=manifest,
        file_bytes=file_bytes,
        selection_receipt=selection_receipt,
        candidate_index=candidate_index,
        term_senses=term_senses,
        contexts=contexts,
        candidate_instances=candidate_instances,
        effective_senses=effective_senses,
        frozen_candidates=frozen_candidates,
        constraint_packages=constraint_packages,
    )
    _validate_contract_joins(pilot)
    return pilot


def _validated_archive_bytes(
    archive: zipfile.ZipFile,
    *,
    pin: Mapping[str, Any],
) -> dict[str, bytes]:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    if len(names) != len(set(names)):
        raise ValueError("official ZIP contains duplicate paths")
    if len(names) != pin["artifact"]["entry_count"]:
        raise ValueError("official ZIP entry count mismatch")
    result: dict[str, bytes] = {}
    for info in infos:
        _safe_archive_path(info.filename)
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ValueError("official ZIP contains a symlink")
        if info.is_dir() or info.flag_bits & 0x1:
            raise ValueError("official ZIP contains a directory or encrypted entry")
        result[info.filename] = archive.read(info)
    if sum(len(value) for value in result.values()) > 4_000_000:
        raise ValueError("official ZIP expanded size exceeds the sealed pilot bound")
    return result


def _validate_pin(pin: Mapping[str, Any], *, zip_path: Path) -> None:
    expected_keys = {
        "artifact",
        "boundaries",
        "counts",
        "downstream",
        "evidence_labels",
        "integrity",
        "manifest",
        "producer_git",
        "review",
        "schema_id",
        "status",
    }
    if set(pin) != expected_keys:
        raise ValueError("official Dataset pin fields differ")
    _verify_nested_self_hash(pin, "official Dataset pin")
    if pin["integrity"]["self_sha256"] != OFFICIAL_PIN_SELF_SHA256:
        raise ValueError("official Dataset pin self SHA mismatch")
    artifact = pin.get("artifact")
    if not isinstance(artifact, Mapping) or artifact.get("name") != OFFICIAL_ZIP_NAME:
        raise ValueError("official Dataset pin artifact name mismatch")
    expected_artifact = {
        "canonical_path": _CANONICAL_ZIP_PATH,
        "do_not_alter_or_rebuild": True,
        "entry_count": 70,
        "name": OFFICIAL_ZIP_NAME,
        "physical_sha256": OFFICIAL_ZIP_SHA256,
        "size_bytes": 135292,
    }
    if dict(artifact) != expected_artifact or zip_path.stat().st_size != 135292:
        raise ValueError("official Dataset pin artifact binding mismatch")
    if pin.get("schema_id") != "D2LOfficialDatasetInputPinV1" or pin.get(
        "status"
    ) != "CANONICAL_MAIN_PIN_ACCEPTED_FOR_REAL_ZERO_NETWORK_PILOT":
        raise ValueError("official Dataset pin identity mismatch")
    if pin.get("counts") != {
        "constraint_evidence_packages": 15,
        "effective_sense_contracts": 5,
        "frozen_candidate_contracts": 15,
        "stage_b_blocked": 12,
        "stage_b_eligible": 33,
        "stage_b_rows": 45,
    }:
        raise ValueError("official Dataset pin counts mismatch")
    boundaries = pin.get("boundaries", {})
    if (
        boundaries.get("final_glossary_decision") is not None
        or boundaries.get("network_calls") != 0
        or boundaries.get("provider_calls") != 0
    ):
        raise ValueError("official Dataset pin exceeds the zero-provider boundary")
    downstream = pin.get("downstream", {}).get("context_substitution", {})
    if downstream != {
        "expected_official_packages": 15,
        "status": "AUTHORIZED_TO_PRODUCE_ZERO_PROVIDER_EVIDENCE",
    }:
        raise ValueError("official Dataset pin does not authorize C package production")
    producer = pin.get("producer_git", {})
    if producer.get("reviewed_commit") != REVIEWED_PRODUCER_COMMIT or producer.get(
        "unreviewed_later_commit_excluded"
    ) != EXCLUDED_ELEVEN_SENSE_COMMIT:
        raise ValueError("official Dataset producer lineage mismatch")
    manifest = pin.get("manifest", {})
    if manifest.get("self_sha256") != OFFICIAL_MANIFEST_SELF_SHA256:
        raise ValueError("official Dataset manifest pin mismatch")


def _validate_manifest(
    manifest: Mapping[str, Any],
    *,
    file_bytes: Mapping[str, bytes],
    pin: Mapping[str, Any],
) -> None:
    _verify_top_level_hash(manifest, "manifest_sha256", "official manifest")
    if manifest.get("manifest_sha256") != OFFICIAL_MANIFEST_SELF_SHA256:
        raise ValueError("official manifest self SHA mismatch")
    if manifest.get("schema_id") != _MANIFEST_SCHEMA_ID or manifest.get(
        "schema_version"
    ) != "1.0.0":
        raise ValueError("official manifest schema mismatch")
    if manifest.get("provider_call_count") != 0 or manifest.get(
        "final_glossary_decision"
    ) is not None:
        raise ValueError("official manifest violates decision neutrality")
    if manifest.get("counts", {}).get("effective_sense_contract") != 5 or manifest.get(
        "counts", {}
    ).get("frozen_candidate_contract") != 15 or manifest.get("counts", {}).get(
        "constraint_evidence_package"
    ) != 15:
        raise ValueError("official manifest contract counts mismatch")
    if manifest.get("source_bindings") != {
        "dataset_v3_manifest_sha256": PARENT_DATASET_MANIFEST_SHA256,
        "parent_p0_manifest_sha256": (
            "32b3bbea775362504ef698cfe65a4a9e27890f761d7067b1c88dad7a9670bb6e"
        ),
        "reviewed_15_manifest_sha256": REVIEWED_DATASET_MANIFEST_SHA256,
    }:
        raise ValueError("official manifest source lineage mismatch")
    if manifest.get("contract_authority") != {
        "commit": AUTHORITY_COMMIT,
        "manifest_sha256": CONTRACT_MANIFEST_SHA256,
        "tag": AUTHORITY_TAG,
    }:
        raise ValueError("official manifest Contracts authority mismatch")
    manifest_bytes = file_bytes["manifest.json"]
    manifest_pin = pin["manifest"]
    if hashlib.sha256(manifest_bytes).hexdigest() != manifest_pin[
        "physical_sha256"
    ]:
        raise ValueError("official manifest physical SHA mismatch")
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise ValueError("official manifest files inventory is missing")
    expected_names = set(files) | {"manifest.json", "CHECKSUMS.sha256"}
    if set(file_bytes) != expected_names:
        raise ValueError("official ZIP inventory differs from manifest")
    for name, metadata in files.items():
        _safe_archive_path(name)
        if not isinstance(metadata, Mapping) or set(metadata) != {
            "sha256",
            "size_bytes",
        }:
            raise ValueError(f"official manifest file metadata differs: {name}")
        payload = file_bytes[name]
        if (
            hashlib.sha256(payload).hexdigest() != metadata["sha256"]
            or len(payload) != metadata["size_bytes"]
        ):
            raise ValueError(f"official manifest file binding mismatch: {name}")
    checksums = _parse_checksums(file_bytes["CHECKSUMS.sha256"])
    if set(checksums) != set(file_bytes) - {"CHECKSUMS.sha256"}:
        raise ValueError("official CHECKSUMS inventory mismatch")
    for name, expected_sha in checksums.items():
        if hashlib.sha256(file_bytes[name]).hexdigest() != expected_sha:
            raise ValueError(f"official CHECKSUMS SHA mismatch: {name}")


def _validate_contract_joins(pilot: OfficialDatasetPilot) -> None:
    if (
        len(pilot.term_senses),
        len(pilot.contexts),
        len(pilot.candidate_instances),
        len(pilot.effective_senses),
        len(pilot.frozen_candidates),
        len(pilot.constraint_packages),
    ) != (5, 29, 15, 5, 15, 15):
        raise ValueError("official pilot materialized cardinality mismatch")

    # These materialized rows retain their parent V3 identity hashes while the
    # official ZIP manifest binds the exact projected bytes.
    for row in pilot.term_senses:
        if not _is_sha256(row.get("term_sense_sha256")):
            raise ValueError("official term sense identity SHA is invalid")
    for row in pilot.contexts:
        if not _is_sha256(row.get("context_sha256")):
            raise ValueError("official context identity SHA is invalid")
        if hashlib.sha256(str(row["source_text"]).encode("utf-8")).hexdigest() != row[
            "content_sha256"
        ]:
            raise ValueError("official context content SHA mismatch")
    for row in pilot.candidate_instances:
        if not _is_sha256(row.get("candidate_instance_sha256")):
            raise ValueError("official candidate identity SHA is invalid")

    for row in (
        *pilot.effective_senses,
        *pilot.frozen_candidates,
        *pilot.constraint_packages,
    ):
        validate_official_contract(row)
        _verify_nested_self_hash(row, str(row.get("schema_id")))
    if not all(verify_frozen_candidate_binding(row) for row in pilot.frozen_candidates):
        raise ValueError("official Frozen Candidate input binding mismatch")

    effective_by_id = _unique_by(
        pilot.effective_senses, lambda row: str(row["sense_id"]), "effective sense"
    )
    frozen_by_id = _unique_by(
        pilot.frozen_candidates,
        lambda row: str(row["candidate_key"]["candidate_id"]),
        "Frozen Candidate",
    )
    constraint_by_id = _unique_by(
        pilot.constraint_packages,
        lambda row: str(row["candidate_key"]["candidate_id"]),
        "Constraint Evidence",
    )
    instance_by_id = _unique_by(
        pilot.candidate_instances,
        lambda row: str(row["candidate_instance_id"]),
        "candidate instance",
    )
    terms_by_sense = _unique_by(
        pilot.term_senses, lambda row: str(row["sense_id"]), "term sense"
    )
    index_entries = pilot.candidate_index.get("entries")
    if not isinstance(index_entries, list) or pilot.candidate_index.get(
        "candidate_count"
    ) != 15:
        raise ValueError("official candidate index count mismatch")
    index_by_id = _unique_by(
        index_entries, lambda row: str(row["candidate_id"]), "candidate index"
    )
    selected_records = pilot.selection_receipt.get("records")
    if not isinstance(selected_records, list) or len(selected_records) != 5:
        raise ValueError("official selection receipt count mismatch")
    selected_ids: list[str] = []
    selected_senses: list[str] = []
    selected_terms: list[str] = []
    for record in selected_records:
        ids = record.get("candidate_ids")
        if not isinstance(ids, list) or len(ids) != 3:
            raise ValueError("official selection receipt candidate count mismatch")
        selected_ids.extend(str(value) for value in ids)
        selected_senses.append(str(record["sense_id"]))
        selected_terms.append(str(record["source_term"]))
    if tuple(selected_terms) != _EXPECTED_SOURCE_TERMS:
        raise ValueError("official selection receipt contains another sense set")
    if len(set(selected_ids)) != 15 or set(selected_ids) != set(frozen_by_id):
        raise ValueError("official selection receipt candidate coverage mismatch")
    if len(set(selected_senses)) != 5 or set(selected_senses) != set(effective_by_id):
        raise ValueError("official selection receipt sense coverage mismatch")
    if set(index_by_id) != set(frozen_by_id) or set(instance_by_id) != set(frozen_by_id):
        raise ValueError("official candidate authority sets do not join exactly")

    contexts_by_sense: dict[str, list[Mapping[str, Any]]] = {}
    for row in pilot.contexts:
        sense_id = str(row["sense_id"])
        contexts_by_sense.setdefault(sense_id, []).append(row)
        if sense_id not in terms_by_sense or row["term_id"] != sense_id:
            raise ValueError("official context has a foreign term/sense")
    if set(contexts_by_sense) != set(effective_by_id):
        raise ValueError("official context sense coverage mismatch")

    files = pilot.manifest["files"]
    for candidate_id in sorted(frozen_by_id):
        frozen = frozen_by_id[candidate_id]
        constraint = constraint_by_id[candidate_id]
        instance = instance_by_id[candidate_id]
        index = index_by_id[candidate_id]
        key = frozen["candidate_key"]
        sense_id = str(key["sense_id"])
        effective = effective_by_id[sense_id]
        if constraint["candidate_key"] != key or constraint[
            "input_contract_sha256"
        ] != frozen["input_contract_sha256"]:
            raise ValueError("Constraint Evidence differs from Frozen Candidate")
        if key["dataset_manifest_sha256"] != PARENT_DATASET_MANIFEST_SHA256:
            raise ValueError("Frozen Candidate Dataset manifest mismatch")
        if key["effective_sense_contract_sha256"] != effective["integrity"][
            "self_sha256"
        ]:
            raise ValueError("Frozen Candidate Effective Sense binding mismatch")
        if (
            key["candidate_version"] != instance["candidate_instance_sha256"]
            or key["candidate_vi"] != instance["candidate_target_vi"]
            or key["scope_id"] != instance["scope_id"]
            or sense_id != instance["sense_id"]
        ):
            raise ValueError("Frozen Candidate differs from materialized candidate")
        expected_index = {
            "binding_status": "COMPLETE",
            "candidate_id": candidate_id,
            "candidate_version": key["candidate_version"],
            "candidate_vi": key["candidate_vi"],
            "constraint_evidence_path": (
                f"constraint_evidence_packages_15/{candidate_id}.json"
            ),
            "constraint_evidence_sha256": constraint["integrity"]["self_sha256"],
            "effective_sense_path": f"effective_sense_contracts_5/{sense_id}.json",
            "effective_sense_sha256": effective["integrity"]["self_sha256"],
            "frozen_candidate_path": f"frozen_candidate_contracts_15/{candidate_id}.json",
            "frozen_candidate_sha256": frozen["integrity"]["self_sha256"],
            "input_contract_sha256": frozen["input_contract_sha256"],
            "sense_id": sense_id,
            "source_term": key["source_term"],
        }
        if index != expected_index:
            raise ValueError("official candidate index binding mismatch")
        for relative in (
            expected_index["constraint_evidence_path"],
            expected_index["effective_sense_path"],
            expected_index["frozen_candidate_path"],
        ):
            if relative not in files:
                raise ValueError("official contract file is missing from manifest")


def _verify_nested_self_hash(
    value: Mapping[str, Any],
    label: str,
    *,
    key: str = "self_sha256",
) -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or set(integrity) != {key}:
        raise ValueError(f"{label} integrity fields differ")
    claimed = integrity.get(key)
    identity = copy.deepcopy(dict(value))
    identity["integrity"].pop(key)
    if not _is_sha256(claimed) or canonical_sha256(identity) != claimed:
        raise ValueError(f"{label} self SHA mismatch")


def _verify_top_level_hash(
    value: Mapping[str, Any], key: str, label: str
) -> None:
    claimed = value.get(key)
    identity = copy.deepcopy(dict(value))
    identity.pop(key, None)
    if not _is_sha256(claimed) or canonical_sha256(identity) != claimed:
        raise ValueError(f"{label} self SHA mismatch")


def _load_object(values: Mapping[str, bytes], name: str) -> dict[str, Any]:
    return loads_strict(values[name], source=name, require_object=True)


def _load_jsonl(values: Mapping[str, bytes], name: str) -> list[dict[str, Any]]:
    try:
        text = values[name].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"{name}: JSONL is not UTF-8") from exc
    rows = []
    for line_number, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        rows.append(
            loads_strict(
                line,
                source=f"{name}:{line_number}",
                require_object=True,
            )
        )
    return rows


def _load_prefix_objects(
    values: Mapping[str, bytes], prefix: str
) -> list[dict[str, Any]]:
    names = sorted(
        name for name in values if name.startswith(prefix) and name.endswith(".json")
    )
    return [_load_object(values, name) for name in names]


def _parse_checksums(payload: bytes) -> dict[str, str]:
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("official CHECKSUMS is not ASCII") from exc
    result: dict[str, str] = {}
    for line_number, line in enumerate(text.splitlines(), 1):
        match = re.fullmatch(r"([0-9a-f]{64}) \*(.+)", line)
        if match is None:
            raise ValueError(f"official CHECKSUMS line {line_number} is malformed")
        digest, name = match.groups()
        _safe_archive_path(name)
        if name in result:
            raise ValueError("official CHECKSUMS contains a duplicate path")
        result[name] = digest
    return result


def _safe_archive_path(value: str) -> PurePosixPath:
    if "\\" in value or ":" in value:
        raise ValueError("official ZIP path is not canonical POSIX")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("official ZIP path is unsafe")
    return path


def _unique_by(
    values: Sequence[Mapping[str, Any]],
    key,
    label: str,
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for value in values:
        identity = key(value)
        if identity in result:
            raise ValueError(f"duplicate {label}: {identity}")
        result[identity] = value
    return result


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and _SHA256_RE.fullmatch(value) is not None


__all__ = [
    "EXCLUDED_ELEVEN_SENSE_COMMIT",
    "OFFICIAL_ADAPTER_RECEIPT_SCHEMA_ID",
    "OFFICIAL_MAIN_COMMIT",
    "OFFICIAL_MANIFEST_SELF_SHA256",
    "OFFICIAL_PIN_SELF_SHA256",
    "OFFICIAL_RUNTIME_RECEIPT_SCHEMA_ID",
    "OFFICIAL_ZIP_SHA256",
    "OfficialDatasetPilot",
    "load_official_dataset_pilot",
]
