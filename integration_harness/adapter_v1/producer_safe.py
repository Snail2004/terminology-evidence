"""Verified zero-provider parent payload and deterministic subset authorities."""

from __future__ import annotations

import copy
import re
import shutil
import stat
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from integration_harness.errors import IntegrityError, PolicyError, StorageError, ValidationError
from integration_harness.hashing import self_sha256, sha256_bytes, sha256_file
from integration_harness.jsonio import canonical_bytes, dump_json, loads_strict
from integration_harness.paths import ensure_plain_root


PRODUCER_SAFE_ZIP_SHA256 = "8a39dce822dcb6aa228da25a5a10b7df07b6ac60ef68bca3e5466aba49449d73"
PRODUCER_SAFE_MANIFEST_SELF_SHA256 = "194dd421ad7aef9272e90d1dff2ef96c5a8c8bf1ded7faba74283777e279ddc2"
PRODUCER_SAFE_MANIFEST_PHYSICAL_SHA256 = "f76a9a9701ebd813c9835dab6a4847bd8fb69c91f23d4f831c4528abd925b724"
PRODUCER_SAFE_SENSE_IDENTITY_SHA256 = "db2e5298324981c96bb83c5318fc219e2bd0c341273e439a3bae3900fe9a5708"
PRODUCER_SAFE_CANDIDATE_IDENTITY_SHA256 = "ea80716a38d443afa954f110b3a8346f17073f7e76aa6ea6f2fce377490dd77b"
PRODUCER_SAFE_CONTEXT_IDENTITY_SHA256 = "eef660f3eff8dcec277ec607d0b56f16f66cdf55e708bb39cd6118167d7dd9fb"
PRODUCER_SAFE_RELEASE_RECEIPT_SELF_SHA256 = "633816194a3119baa19284648d49ff546c04e4ce7638dfab7bdf9d0074c8c81b"
PRODUCER_SAFE_RELEASE_RECEIPT_PHYSICAL_SHA256 = "de077983f79674d196189f67b209fc8d9250816deaf3ff11b7c43221f84cd362"
PRODUCER_SAFE_PUBLICATION_RECEIPT_SELF_SHA256 = "cf12bda7d8ef5c7575f265f1996aa64441079f955049b33fe71916968d93c88a"
PRODUCER_SAFE_PUBLICATION_RECEIPT_PHYSICAL_SHA256 = "1709b97c37319b2f4af9cbc3f4c602a2357de627eb30839640cb017ad1d1d0a7"

PARENT_AUTHORITY_SCHEMA = "HarnessProducerSafeParentPayloadAuthorityV1"
SUBSET_AUTHORITY_SCHEMA = "HarnessProducerSafeSubsetCohortAuthorityV1"
COHORT_RELEASE_SCHEMA = "HarnessProducerSafeCohortAuthorityReleaseV1"
SCHEMA_VERSION = "1.0.0"
PARENT_STATUS = "PRODUCER_SAFE_PAYLOAD_ACCEPTED_ZERO_PROVIDER"
SUBSET_STATUS = "PRODUCER_SAFE_SUBSET_AUTHORITY_ZERO_PROVIDER"
PUBLICATION_ACCEPTED = "FINAL_GIT_PUBLICATION_RECEIPT_ACCEPTED_ZERO_PROVIDER"
SUPPORTED_COHORT_SIZES = (1, 15)

_MEMBERS = {
    "CHECKSUMS.sha256",
    "README_PRODUCER_SAFE.md",
    "pipeline_contexts_386.jsonl",
    "pipeline_contexts_386.schema.json",
    "pipeline_input_50_150.jsonl",
    "pipeline_input_50_150.schema.json",
    "pipeline_input_50_150_manifest.json",
    "pipeline_input_50_150_release_receipt.json",
}
_HEX = set("0123456789abcdef")


@dataclass(frozen=True)
class ProducerSafeCandidate:
    candidate_id: str
    sense_id: str
    context_ids: tuple[str, ...]
    raw: bytes
    value: dict[str, Any]


@dataclass(frozen=True)
class ProducerSafeContext:
    context_id: str
    sense_id: str
    context_class: str
    raw: bytes
    value: dict[str, Any]


@dataclass(frozen=True)
class ProducerSafeParentPayload:
    zip_path: Path
    zip_raw: bytes
    members: Mapping[str, bytes]
    manifest_raw: bytes
    manifest: dict[str, Any]
    receipt_raw: bytes
    receipt: dict[str, Any]
    publication_receipt_path: Path
    publication_receipt_raw: bytes
    publication_receipt: dict[str, Any]
    candidates: tuple[ProducerSafeCandidate, ...]
    contexts: tuple[ProducerSafeContext, ...]

    @property
    def canary_candidate_id(self) -> str:
        first_sense = self.d0_sense_ids[0]
        candidates = sorted(
            item.candidate_id for item in self.candidates if item.sense_id == first_sense
        )
        if len(candidates) != 3:
            raise ValidationError("producer-safe D0 canary sense must have three candidates")
        return candidates[0]

    @property
    def d0_sense_ids(self) -> tuple[str, ...]:
        contexts = {item.context_id: item for item in self.contexts}
        candidates_by_sense: dict[str, list[ProducerSafeCandidate]] = {}
        for candidate in self.candidates:
            candidates_by_sense.setdefault(candidate.sense_id, []).append(candidate)
        eligible = []
        for sense_id, candidates in sorted(candidates_by_sense.items()):
            context_ids = {item for candidate in candidates for item in candidate.context_ids}
            has_contrastive = any(
                contexts[context_id].context_class == "CONTRASTIVE"
                for context_id in context_ids
            )
            if len(candidates) == 3 and has_contrastive:
                eligible.append(sense_id)
        if len(eligible) < 5:
            raise ValidationError("producer-safe parent has fewer than five contrastive D0 senses")
        return tuple(eligible[:5])


def load_producer_safe_parent(
    zip_path: Path,
    *,
    publication_receipt_path: Path | None = None,
) -> ProducerSafeParentPayload:
    """Verify the exact accepted 50/150/386 content payload without gold access."""

    zip_path = ensure_plain_root(zip_path.parent) / zip_path.name
    if not zip_path.is_file():
        raise ValidationError("producer-safe Dataset ZIP is missing")
    zip_raw = zip_path.read_bytes()
    if sha256_bytes(zip_raw) != PRODUCER_SAFE_ZIP_SHA256:
        raise IntegrityError("producer-safe Dataset ZIP authority hash mismatch")
    members = _load_safe_zip(zip_path)
    if set(members) != _MEMBERS:
        raise IntegrityError("producer-safe Dataset ZIP member set mismatch")
    _verify_checksums(members)

    candidate_schema = loads_strict(
        members["pipeline_input_50_150.schema.json"], require_object=True
    )
    context_schema = loads_strict(
        members["pipeline_contexts_386.schema.json"], require_object=True
    )
    Draft202012Validator.check_schema(candidate_schema)
    Draft202012Validator.check_schema(context_schema)
    candidate_validator = Draft202012Validator(candidate_schema)
    context_validator = Draft202012Validator(context_schema)
    candidate_rows = _jsonl(members["pipeline_input_50_150.jsonl"], "candidate")
    context_rows = _jsonl(members["pipeline_contexts_386.jsonl"], "context")
    _validate_rows(candidate_rows, candidate_validator, "candidate")
    _validate_rows(context_rows, context_validator, "context")
    candidates = tuple(
        ProducerSafeCandidate(
            candidate_id=str(value["candidate_id"]),
            sense_id=str(value["sense_id"]),
            context_ids=tuple(str(item) for item in value["context_ids"]),
            raw=canonical_bytes(value) + b"\n",
            value=dict(value),
        )
        for value in candidate_rows
    )
    contexts = tuple(
        ProducerSafeContext(
            context_id=str(value["context_id"]),
            sense_id=str(value["sense_id"]),
            context_class=str(value["context_class"]),
            raw=canonical_bytes(value) + b"\n",
            value=dict(value),
        )
        for value in context_rows
    )
    _verify_joins(candidates, contexts)

    manifest_raw = members["pipeline_input_50_150_manifest.json"]
    receipt_raw = members["pipeline_input_50_150_release_receipt.json"]
    manifest = loads_strict(manifest_raw, require_object=True)
    receipt = loads_strict(receipt_raw, require_object=True)
    _verify_record_hash(manifest, "manifest_sha256", "producer-safe manifest")
    _verify_record_hash(receipt, "receipt_sha256", "producer-safe release receipt")
    if manifest["manifest_sha256"] != PRODUCER_SAFE_MANIFEST_SELF_SHA256:
        raise IntegrityError("producer-safe manifest authority hash mismatch")
    if receipt["receipt_sha256"] != PRODUCER_SAFE_RELEASE_RECEIPT_SELF_SHA256:
        raise IntegrityError("producer-safe release receipt authority hash mismatch")
    if sha256_bytes(manifest_raw) != PRODUCER_SAFE_MANIFEST_PHYSICAL_SHA256:
        raise IntegrityError("producer-safe manifest physical authority hash mismatch")
    if sha256_bytes(receipt_raw) != PRODUCER_SAFE_RELEASE_RECEIPT_PHYSICAL_SHA256:
        raise IntegrityError("producer-safe release receipt physical authority hash mismatch")
    if publication_receipt_path is None:
        publication_receipt_path = zip_path.parent / (
            "pipeline_input_50_150_producer_safe_v1_publication_receipt.json"
        )
    publication_receipt_path = (
        ensure_plain_root(publication_receipt_path.parent) / publication_receipt_path.name
    )
    if not publication_receipt_path.is_file():
        raise ValidationError("producer-safe final publication receipt is missing")
    publication_raw = publication_receipt_path.read_bytes()
    publication = loads_strict(publication_raw, require_object=True)
    _verify_record_hash(publication, "receipt_sha256", "producer-safe publication receipt")
    if publication["receipt_sha256"] != PRODUCER_SAFE_PUBLICATION_RECEIPT_SELF_SHA256:
        raise IntegrityError("producer-safe publication receipt self authority hash mismatch")
    if sha256_bytes(publication_raw) != PRODUCER_SAFE_PUBLICATION_RECEIPT_PHYSICAL_SHA256:
        raise IntegrityError("producer-safe publication receipt physical authority hash mismatch")
    if any(
        publication.get(field) != expected
        for field, expected in (
            ("package_zip_sha256", PRODUCER_SAFE_ZIP_SHA256),
            ("manifest_sha256", PRODUCER_SAFE_MANIFEST_SELF_SHA256),
            ("manifest_physical_sha256", PRODUCER_SAFE_MANIFEST_PHYSICAL_SHA256),
            ("release_receipt_sha256", PRODUCER_SAFE_RELEASE_RECEIPT_SELF_SHA256),
            ("release_receipt_physical_sha256", PRODUCER_SAFE_RELEASE_RECEIPT_PHYSICAL_SHA256),
        )
    ):
        raise IntegrityError("producer-safe publication receipt content binding mismatch")
    _verify_manifest_and_receipt(
        manifest,
        receipt,
        manifest_raw=manifest_raw,
        members=members,
        candidates=candidates,
        contexts=contexts,
    )
    return ProducerSafeParentPayload(
        zip_path=zip_path,
        zip_raw=zip_raw,
        members=members,
        manifest_raw=manifest_raw,
        manifest=manifest,
        receipt_raw=receipt_raw,
        receipt=receipt,
        publication_receipt_path=publication_receipt_path,
        publication_receipt_raw=publication_raw,
        publication_receipt=publication,
        candidates=candidates,
        contexts=contexts,
    )


def build_parent_authority(parent: ProducerSafeParentPayload) -> dict[str, Any]:
    value = {
        "schema_id": PARENT_AUTHORITY_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "status": PARENT_STATUS,
        "artifact_name": "pipeline_input_50_150_producer_safe_v1",
        "zip_physical_sha256": sha256_bytes(parent.zip_raw),
        "manifest_self_sha256": parent.manifest["manifest_sha256"],
        "manifest_physical_sha256": sha256_bytes(parent.manifest_raw),
        "release_receipt_self_sha256": parent.receipt["receipt_sha256"],
        "release_receipt_physical_sha256": sha256_bytes(parent.receipt_raw),
        "publication_receipt_self_sha256": parent.publication_receipt["receipt_sha256"],
        "publication_receipt_physical_sha256": sha256_bytes(parent.publication_receipt_raw),
        "sense_identity_sha256": parent.manifest["sense_identity_sha256"],
        "candidate_identity_sha256": parent.manifest["candidate_identity_sha256"],
        "context_identity_sha256": parent.manifest["context_identity_sha256"],
        "sense_count": 50,
        "candidate_count": 150,
        "context_count": 386,
        "publication_status": PUBLICATION_ACCEPTED,
        "publication_commit": parent.publication_receipt["publication_git"]["commit"],
        "publication_tree": parent.publication_receipt["publication_git"]["tree"],
        "provider_calls": 0,
        "network_calls": 0,
        "final_glossary_decision": None,
        "integrity": {},
    }
    value["integrity"]["self_sha256"] = self_sha256(value)
    return value


def build_subset_authority(
    parent: ProducerSafeParentPayload,
    *,
    candidate_count: int,
    parent_authority_binding: Mapping[str, str],
    issuer_id: str,
    authority_id: str,
    run_id: str,
    phase_id: str,
    split_id: str,
) -> dict[str, Any]:
    if candidate_count not in SUPPORTED_COHORT_SIZES:
        raise ValidationError(f"unsupported producer-safe cohort size: {candidate_count}")
    for value, label in (
        (issuer_id, "issuer_id"), (authority_id, "authority_id"),
        (run_id, "run_id"), (phase_id, "phase_id"), (split_id, "split_id"),
    ):
        _string(value, label)
    _require_exact_keys(
        parent_authority_binding,
        {"relative_path", "physical_sha256", "self_sha256"},
        "parent payload authority binding",
    )
    canary = parent.canary_candidate_id
    if candidate_count == 1:
        selected_ids = frozenset({canary})
    else:
        selected_ids = frozenset(
            item.candidate_id
            for item in parent.candidates
            if item.sense_id in set(parent.d0_sense_ids)
        )
    selected = sorted(
        (item for item in parent.candidates if item.candidate_id in selected_ids),
        key=lambda item: item.candidate_id,
    )
    if len(selected) != candidate_count or canary not in selected_ids:
        raise IntegrityError("producer-safe exact subset selection failed")
    contexts_by_id = {item.context_id: item for item in parent.contexts}
    context_ids = sorted({context_id for item in selected for context_id in item.context_ids})
    senses = sorted({item.sense_id for item in selected})
    candidate_bindings = [
        {
            "candidate_id": item.candidate_id,
            "candidate_version": item.value["candidate_version"],
            "sense_id": item.sense_id,
            "context_ids": list(item.context_ids),
            "record_sha256": item.value["record_sha256"],
        }
        for item in selected
    ]
    context_bindings = [
        {
            "context_id": context_id,
            "sense_id": contexts_by_id[context_id].sense_id,
            "context_class": contexts_by_id[context_id].context_class,
            "record_sha256": contexts_by_id[context_id].value["record_sha256"],
        }
        for context_id in context_ids
    ]
    value = {
        "schema_id": SUBSET_AUTHORITY_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "status": SUBSET_STATUS,
        "issuer_id": issuer_id,
        "authority_id": authority_id,
        "run_id": run_id,
        "phase_id": phase_id,
        "split_id": split_id,
        "selection_policy": "D0_FIVE_CONTRASTIVE_SENSES_THREE_CANDIDATES_V1",
        "parent_payload_authority": dict(parent_authority_binding),
        "parent_candidate_count": 150,
        "parent_candidate_identity_sha256": PRODUCER_SAFE_CANDIDATE_IDENTITY_SHA256,
        "candidate_count": candidate_count,
        "candidate_ids": sorted(selected_ids),
        "candidate_set_sha256": _identity_hash(sorted(selected_ids)),
        "candidate_record_set_sha256": sha256_bytes(canonical_bytes(candidate_bindings)),
        "candidate_bindings": candidate_bindings,
        "sense_count": len(senses),
        "sense_ids": senses,
        "sense_set_sha256": _identity_hash(senses),
        "context_count": len(context_ids),
        "context_ids": context_ids,
        "context_set_sha256": _identity_hash(context_ids),
        "context_record_set_sha256": sha256_bytes(canonical_bytes(context_bindings)),
        "context_bindings": context_bindings,
        "canary_candidate_id": canary,
        "canary_requires_contrastive_context": True,
        "publication_status": PUBLICATION_ACCEPTED,
        "provider_calls": 0,
        "network_calls": 0,
        "final_glossary_decision": None,
        "integrity": {},
    }
    value["integrity"]["self_sha256"] = self_sha256(value)
    return value


def write_producer_safe_cohort_release(
    zip_path: Path,
    output_root: Path,
    *,
    issuer_id: str,
    authority_id: str,
    run_id: str,
    phase_id: str,
    split_id: str,
    publication_receipt_path: Path | None = None,
    schema_root: Path | None = None,
) -> dict[str, Any]:
    """Write a deterministic parent authority and all six exact subset authorities."""

    parent = load_producer_safe_parent(
        zip_path, publication_receipt_path=publication_receipt_path
    )
    output_root = output_root.absolute()
    if output_root.exists():
        raise StorageError(f"refusing to overwrite producer-safe cohort release: {output_root}")
    parent_root = ensure_plain_root(output_root.parent)
    temp = parent_root / f".{output_root.name}.tmp-{uuid.uuid4().hex}"
    temp.mkdir()
    try:
        parent_authority = build_parent_authority(parent)
        parent_path = temp / "parent_payload_authority.json"
        dump_json(parent_path, parent_authority)
        publication_relative = "source/publication_receipt.json"
        publication_path = temp / publication_relative
        publication_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(parent.publication_receipt_path, publication_path)
        parent_binding = {
            "relative_path": "parent_payload_authority.json",
            "physical_sha256": sha256_file(parent_path),
            "self_sha256": parent_authority["integrity"]["self_sha256"],
        }
        cohort_bindings: list[dict[str, Any]] = []
        for count in SUPPORTED_COHORT_SIZES:
            cohort = build_subset_authority(
                parent,
                candidate_count=count,
                parent_authority_binding=parent_binding,
                issuer_id=issuer_id,
                authority_id=authority_id,
                run_id=run_id,
                phase_id=phase_id,
                split_id=split_id,
            )
            relative = f"cohorts/cohort_{count:03d}.json"
            path = temp / relative
            dump_json(path, cohort)
            cohort_bindings.append(
                {
                    "candidate_count": count,
                    "relative_path": relative,
                    "physical_sha256": sha256_file(path),
                    "self_sha256": cohort["integrity"]["self_sha256"],
                    "candidate_set_sha256": cohort["candidate_set_sha256"],
                }
            )
        manifest = {
            "schema_id": COHORT_RELEASE_SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "status": "PRODUCER_SAFE_EXACT_COHORTS_READY_FOR_REVIEW",
            "parent_payload_authority": parent_binding,
            "publication_receipt": {
                "relative_path": publication_relative,
                "physical_sha256": sha256_file(publication_path),
                "self_sha256": parent.publication_receipt["receipt_sha256"],
            },
            "cohorts": cohort_bindings,
            "supported_candidate_counts": list(SUPPORTED_COHORT_SIZES),
            "canary_candidate_id": parent.canary_candidate_id,
            "publication_status": PUBLICATION_ACCEPTED,
            "provider_calls": 0,
            "network_calls": 0,
            "gold_access": 0,
            "final_glossary_decision": None,
            "integrity": {},
        }
        manifest["integrity"]["self_sha256"] = self_sha256(manifest)
        dump_json(temp / "manifest.json", manifest)
        _write_checksums(temp)
        temp.replace(output_root)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return verify_producer_safe_cohort_release(
        output_root,
        zip_path=zip_path,
        publication_receipt_path=publication_receipt_path,
        schema_root=schema_root,
    )


def verify_producer_safe_cohort_release(
    root: Path,
    *,
    zip_path: Path,
    publication_receipt_path: Path | None = None,
    schema_root: Path | None = None,
) -> dict[str, Any]:
    root = ensure_plain_root(root)
    parent = load_producer_safe_parent(
        zip_path, publication_receipt_path=publication_receipt_path
    )
    manifest = loads_strict((root / "manifest.json").read_bytes(), require_object=True)
    _verify_self_hash(manifest, "producer-safe cohort release manifest")
    if manifest.get("schema_id") != COHORT_RELEASE_SCHEMA:
        raise ValidationError("unsupported producer-safe cohort release")
    parent_authority = loads_strict(
        (root / "parent_payload_authority.json").read_bytes(), require_object=True
    )
    _verify_self_hash(parent_authority, "producer-safe parent authority")
    if schema_root is not None:
        _validate_schema_file(
            parent_authority,
            schema_root / "harness_producer_safe_parent_payload_authority_v1.schema.json",
            "producer-safe parent authority",
        )
        _validate_schema_file(
            manifest,
            schema_root / "harness_producer_safe_cohort_authority_release_v1.schema.json",
            "producer-safe cohort release manifest",
        )
    if parent_authority != build_parent_authority(parent):
        raise IntegrityError("producer-safe parent authority replay mismatch")
    publication = manifest.get("publication_receipt")
    if not isinstance(publication, Mapping):
        raise IntegrityError("producer-safe release publication binding is missing")
    publication_path = root / _safe_member_path(publication.get("relative_path"))
    if (
        not publication_path.is_file()
        or sha256_file(publication_path) != publication.get("physical_sha256")
        or publication.get("self_sha256") != parent.publication_receipt["receipt_sha256"]
    ):
        raise IntegrityError("producer-safe release publication binding drift")
    observed: list[int] = []
    previous_ids: set[str] = set()
    for binding_value in manifest.get("cohorts", []):
        binding = _mapping(binding_value, "producer-safe cohort binding")
        count = binding.get("candidate_count")
        if not isinstance(count, int):
            raise ValidationError("producer-safe cohort count is invalid")
        path = root / _safe_member_path(binding.get("relative_path"))
        if not path.is_file() or sha256_file(path) != binding.get("physical_sha256"):
            raise IntegrityError("producer-safe cohort physical binding mismatch")
        value = loads_strict(path.read_bytes(), require_object=True)
        _verify_self_hash(value, "producer-safe subset authority")
        if schema_root is not None:
            _validate_schema_file(
                value,
                schema_root / "harness_producer_safe_subset_cohort_authority_v1.schema.json",
                "producer-safe subset authority",
            )
        if value["integrity"]["self_sha256"] != binding.get("self_sha256"):
            raise IntegrityError("producer-safe cohort self binding mismatch")
        expected = build_subset_authority(
            parent,
            candidate_count=count,
            parent_authority_binding=manifest["parent_payload_authority"],
            issuer_id=value["issuer_id"],
            authority_id=value["authority_id"],
            run_id=value["run_id"],
            phase_id=value["phase_id"],
            split_id=value["split_id"],
        )
        if value != expected:
            raise IntegrityError("producer-safe subset authority replay mismatch")
        ids = set(value["candidate_ids"])
        if previous_ids and not previous_ids.issubset(ids):
            raise IntegrityError("producer-safe cohort sequence is not nested")
        previous_ids = ids
        observed.append(count)
    if observed != list(SUPPORTED_COHORT_SIZES):
        raise IntegrityError("producer-safe cohort size inventory mismatch")
    _verify_output_checksums(root)
    return {
        "status": manifest["status"],
        "parent_candidate_count": 150,
        "cohort_counts": observed,
        "canary_candidate_id": manifest["canary_candidate_id"],
        "provider_calls": 0,
        "network_calls": 0,
        "gold_access": 0,
        "official_live_authority": "HOLD",
    }


def _verify_manifest_and_receipt(
    manifest: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    manifest_raw: bytes,
    members: Mapping[str, bytes],
    candidates: Sequence[ProducerSafeCandidate],
    contexts: Sequence[ProducerSafeContext],
) -> None:
    if manifest.get("schema_id") != "ProducerSafePipelineInputManifestV1":
        raise ValidationError("producer-safe manifest schema mismatch")
    if receipt.get("schema_id") != "ProducerSafePipelineInputReleaseReceiptV1":
        raise ValidationError("producer-safe receipt schema mismatch")
    for value in (manifest, receipt):
        if value.get("schema_version") != "1.0.0":
            raise ValidationError("producer-safe schema version mismatch")
        if value.get("release_status") != "PRODUCER_SAFE_PIPELINE_INPUT_50_150_READY_FOR_INDEPENDENT_REVIEW":
            raise ValidationError("producer-safe release status mismatch")
        if value.get("provider_call_count") != 0 or value.get("network_call_count") != 0:
            raise PolicyError("producer-safe payload violates zero-provider boundary")
        if value.get("final_glossary_decision") is not None:
            raise PolicyError("producer-safe payload contains a final decision")
        if value.get("member_names") != sorted(_MEMBERS):
            raise IntegrityError("producer-safe declared member inventory mismatch")
    expected_counts = (50, 150, 386)
    if (
        manifest.get("sense_count"), manifest.get("candidate_count"),
        manifest.get("context_count")
    ) != expected_counts:
        raise ValidationError("producer-safe manifest cardinality mismatch")
    if (
        receipt.get("sense_count"), receipt.get("candidate_count"),
        receipt.get("context_count")
    ) != expected_counts:
        raise ValidationError("producer-safe receipt cardinality mismatch")
    if receipt.get("manifest_sha256") != manifest.get("manifest_sha256"):
        raise IntegrityError("producer-safe receipt manifest self binding mismatch")
    if receipt.get("manifest_physical_sha256") != sha256_bytes(manifest_raw):
        raise IntegrityError("producer-safe receipt manifest physical binding mismatch")
    identities = {
        "sense_identity_sha256": _identity_hash(sorted({item.sense_id for item in candidates})),
        "candidate_identity_sha256": _identity_hash(sorted(item.candidate_id for item in candidates)),
        "context_identity_sha256": _identity_hash(sorted(item.context_id for item in contexts)),
    }
    expected_identity = {
        "sense_identity_sha256": PRODUCER_SAFE_SENSE_IDENTITY_SHA256,
        "candidate_identity_sha256": PRODUCER_SAFE_CANDIDATE_IDENTITY_SHA256,
        "context_identity_sha256": PRODUCER_SAFE_CONTEXT_IDENTITY_SHA256,
    }
    if identities != expected_identity:
        raise IntegrityError("producer-safe independently computed identities differ")
    if any(manifest.get(field) != digest for field, digest in identities.items()):
        raise IntegrityError("producer-safe manifest identity binding mismatch")
    files = manifest.get("files")
    if not isinstance(files, Mapping):
        raise ValidationError("producer-safe file inventory is invalid")
    for name, descriptor_value in files.items():
        descriptor = _mapping(descriptor_value, f"producer-safe file {name}")
        raw = members.get(str(name))
        if raw is None:
            raise IntegrityError(f"producer-safe file inventory has foreign member: {name}")
        if descriptor.get("sha256") != sha256_bytes(raw) or descriptor.get("bytes") != len(raw):
            raise IntegrityError(f"producer-safe file inventory mismatch: {name}")


def _validate_rows(
    rows: Sequence[Mapping[str, Any]],
    validator: Draft202012Validator,
    label: str,
) -> None:
    for index, value in enumerate(rows):
        errors = sorted(
            validator.iter_errors(value),
            key=lambda item: tuple(str(part) for part in item.absolute_path),
        )
        if errors:
            first = errors[0]
            raise ValidationError(f"producer-safe {label}[{index}] schema error: {first.message}")
        _verify_record_hash(value, "record_sha256", f"producer-safe {label}[{index}]")


def _verify_joins(
    candidates: Sequence[ProducerSafeCandidate],
    contexts: Sequence[ProducerSafeContext],
) -> None:
    if len(candidates) != 150 or len(contexts) != 386:
        raise ValidationError("producer-safe candidate/context cardinality mismatch")
    if list(candidates) != sorted(candidates, key=lambda item: (item.sense_id, item.candidate_id)):
        raise IntegrityError("producer-safe candidates are not canonically ordered")
    if list(contexts) != sorted(contexts, key=lambda item: (item.sense_id, item.context_id)):
        raise IntegrityError("producer-safe contexts are not canonically ordered")
    if len({item.candidate_id for item in candidates}) != 150:
        raise ValidationError("producer-safe candidate IDs are not unique")
    if len({item.context_id for item in contexts}) != 386:
        raise ValidationError("producer-safe context IDs are not unique")
    context_by_id = {item.context_id: item for item in contexts}
    counts: dict[str, int] = {}
    referenced: set[str] = set()
    for candidate in candidates:
        counts[candidate.sense_id] = counts.get(candidate.sense_id, 0) + 1
        if list(candidate.context_ids) != sorted(candidate.context_ids):
            raise IntegrityError("producer-safe candidate context IDs are not sorted")
        for context_id in candidate.context_ids:
            context = context_by_id.get(context_id)
            if context is None or context.sense_id != candidate.sense_id:
                raise ValidationError("producer-safe candidate/context join mismatch")
            referenced.add(context_id)
        bindings = [
            {"context_id": context_id, "record_sha256": context_by_id[context_id].value["record_sha256"]}
            for context_id in candidate.context_ids
        ]
        expected = sha256_bytes(canonical_bytes(bindings))
        if candidate.value["provenance"]["context_set_sha256"] != expected:
            raise IntegrityError("producer-safe context-set hash mismatch")
    if len(counts) != 50 or set(counts.values()) != {3}:
        raise ValidationError("producer-safe 50/150 sense cardinality mismatch")
    if referenced != set(context_by_id):
        raise ValidationError("producer-safe payload contains unreferenced contexts")


def _load_safe_zip(path: Path) -> dict[str, bytes]:
    result: dict[str, bytes] = {}
    folded: set[str] = set()
    try:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise IntegrityError("producer-safe ZIP CRC verification failed")
            for info in archive.infolist():
                name = _safe_member_path(info.filename)
                mode = (info.external_attr >> 16) & 0xFFFF
                if (
                    name in result or name.casefold() in folded or info.is_dir()
                    or info.flag_bits & 0x1 or stat.S_ISLNK(mode)
                ):
                    raise IntegrityError(f"unsupported producer-safe ZIP member: {name}")
                result[name] = archive.read(info)
                folded.add(name.casefold())
    except (OSError, zipfile.BadZipFile) as exc:
        raise IntegrityError(f"cannot read producer-safe ZIP: {exc}") from exc
    return result


def _verify_checksums(members: Mapping[str, bytes]) -> None:
    raw = members["CHECKSUMS.sha256"]
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise IntegrityError("producer-safe checksums are not ASCII") from exc
    if not text.endswith("\n"):
        raise IntegrityError("producer-safe checksums must end with LF")
    observed: dict[str, str] = {}
    order: list[str] = []
    for line in text.splitlines():
        match = re.fullmatch(r"([0-9a-f]{64}) \*(.+)", line)
        if match is None:
            raise IntegrityError("malformed producer-safe checksum line")
        name = _safe_member_path(match.group(2))
        if name in observed:
            raise IntegrityError("duplicate producer-safe checksum member")
        observed[name] = match.group(1)
        order.append(name)
    if order != sorted(order) or set(observed) != set(members) - {"CHECKSUMS.sha256"}:
        raise IntegrityError("producer-safe checksum inventory mismatch")
    for name, digest in observed.items():
        if sha256_bytes(members[name]) != digest:
            raise IntegrityError(f"producer-safe checksum mismatch: {name}")


def _jsonl(raw: bytes, label: str) -> list[dict[str, Any]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise IntegrityError(f"producer-safe {label} JSONL is not UTF-8") from exc
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(text.splitlines(), start=1):
        if not line:
            raise IntegrityError(f"blank producer-safe {label} row: {index}")
        rows.append(loads_strict(line, require_object=True))
    return rows


def _verify_record_hash(value: Mapping[str, Any], field: str, label: str) -> None:
    claimed = value.get(field)
    payload = copy.deepcopy(dict(value))
    payload.pop(field, None)
    if claimed != sha256_bytes(canonical_bytes(payload)):
        raise IntegrityError(f"{label} canonical hash mismatch")


def _verify_self_hash(value: Mapping[str, Any], label: str) -> None:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping) or integrity.get("self_sha256") != self_sha256(value):
        raise IntegrityError(f"{label} self hash mismatch")


def _identity_hash(values: Sequence[str]) -> str:
    return sha256_bytes(canonical_bytes(sorted(values)))


def _safe_member_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise IntegrityError("unsafe producer-safe member path")
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise IntegrityError("unsafe producer-safe member path")
    if any(part in {"", ".", ".."} for part in path.parts):
        raise IntegrityError("unsafe producer-safe member path")
    if len(path.parts[0]) >= 2 and path.parts[0][1:2] == ":":
        raise IntegrityError("drive-qualified producer-safe member path")
    return value


def _write_checksums(root: Path) -> None:
    lines = [
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "CHECKSUMS.sha256"
    ]
    (root / "CHECKSUMS.sha256").write_text(
        "\n".join(lines) + "\n", encoding="ascii", newline="\n"
    )


def _verify_output_checksums(root: Path) -> None:
    path = root / "CHECKSUMS.sha256"
    lines = path.read_text(encoding="ascii").splitlines()
    observed: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if match is None:
            raise IntegrityError("malformed cohort release checksum")
        relative = _safe_member_path(match.group(2))
        observed[relative] = match.group(1)
    expected_paths = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item != path
    }
    if set(observed) != expected_paths:
        raise IntegrityError("cohort release checksum inventory mismatch")
    for relative, digest in observed.items():
        if sha256_file(root / relative) != digest:
            raise IntegrityError(f"cohort release checksum mismatch: {relative}")


def _validate_schema_file(value: Mapping[str, Any], path: Path, label: str) -> None:
    schema = loads_strict(path.read_bytes(), require_object=True)
    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda item: tuple(str(part) for part in item.absolute_path),
    )
    if errors:
        first = errors[0]
        where = ".".join(str(part) for part in first.absolute_path) or "$"
        raise ValidationError(f"{label} schema validation failed at {where}: {first.message}")


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValidationError(f"{label} must be an object")
    return value


def _string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValidationError(f"{label} must be a non-empty string")
    return value


def _require_exact_keys(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    observed = set(value)
    if observed != expected:
        raise ValidationError(
            f"{label} fields mismatch: missing={sorted(expected-observed)}, "
            f"extra={sorted(observed-expected)}"
        )


__all__ = [
    "PARENT_AUTHORITY_SCHEMA",
    "PRODUCER_SAFE_CANDIDATE_IDENTITY_SHA256",
    "PRODUCER_SAFE_CONTEXT_IDENTITY_SHA256",
    "PRODUCER_SAFE_MANIFEST_SELF_SHA256",
    "PRODUCER_SAFE_SENSE_IDENTITY_SHA256",
    "PRODUCER_SAFE_ZIP_SHA256",
    "SUBSET_AUTHORITY_SCHEMA",
    "SUPPORTED_COHORT_SIZES",
    "ProducerSafeParentPayload",
    "build_parent_authority",
    "build_subset_authority",
    "load_producer_safe_parent",
    "verify_producer_safe_cohort_release",
    "write_producer_safe_cohort_release",
]
