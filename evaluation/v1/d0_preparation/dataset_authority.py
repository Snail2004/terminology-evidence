"""Read the exact detached producer-safe Dataset authority without gold."""

from __future__ import annotations

import collections
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..artifacts.authority import canonical_manifest_path
from ..jsonio import loads_strict, sha256_bytes, sha256_value


DATASET_FINAL_SEAL_COMMIT = "8b3a2cfe9e58c83d871ceea751785f113e3b7182"
DATASET_FINAL_SEAL_PARENT = "e2a93b0822949230cb299ab2f15fad522ad6b27a"
DATASET_FINAL_SEAL_TREE = "bfe13d0711492f4e75b2396534c5618f3c380487"
DATASET_SOURCE_COMMIT = "e0b04e6e2731f5cb0bed394579eb91c8dec7ad1f"

FINAL_RECEIPT_PATH = "dataset/pipeline_input_50_150_producer_safe_v1/review_evidence/final_git_publication_seal_v1/producer_safe_final_git_publication_receipt_v1.json"
PRODUCER_ROOT = "dataset/pipeline_input_50_150_producer_safe_v1/release/pipeline_input_50_150_producer_safe_v1"
PRODUCER_MANIFEST_PATH = f"{PRODUCER_ROOT}/pipeline_input_50_150_manifest.json"
PRODUCER_CANDIDATES_PATH = f"{PRODUCER_ROOT}/pipeline_input_50_150.jsonl"
PRODUCER_CONTEXTS_PATH = f"{PRODUCER_ROOT}/pipeline_contexts_386.jsonl"
PRODUCER_ZIP_PATH = "dataset/pipeline_input_50_150_producer_safe_v1/release/pipeline_input_50_150_producer_safe_v1.zip"
SPLIT_MANIFEST_PATH = "dataset/d2l_dataset_50_senses_fast_track_stage_a_v1/release/d2l_dataset_50_senses_150_candidates_stage_b_review_v1/split_manifest_30_10_10.json"

FINAL_RECEIPT_PHYSICAL_SHA256 = "02922aff35f807a83cced6f6c69ec8fd349d61e6e5b666c2142e517bb2ecc737"
FINAL_RECEIPT_DECLARED_SHA256 = "99c81fb7ae31d9356b00d74d6ca3359b9883ef07c08e37cba93ee54f92a97dcb"
PRODUCER_MANIFEST_PHYSICAL_SHA256 = "f76a9a9701ebd813c9835dab6a4847bd8fb69c91f23d4f831c4528abd925b724"
PRODUCER_MANIFEST_SELF_SHA256 = "194dd421ad7aef9272e90d1dff2ef96c5a8c8bf1ded7faba74283777e279ddc2"
PRODUCER_ZIP_SHA256 = "8a39dce822dcb6aa228da25a5a10b7df07b6ac60ef68bca3e5466aba49449d73"
PRODUCER_CANDIDATE_IDENTITY_SHA256 = "ea80716a38d443afa954f110b3a8346f17073f7e76aa6ea6f2fce377490dd77b"
PRODUCER_CONTEXT_IDENTITY_SHA256 = "eef660f3eff8dcec277ec607d0b56f16f66cdf55e708bb39cd6118167d7dd9fb"
SPLIT_MANIFEST_PHYSICAL_SHA256 = "cec84b39c6bd8d191796efee008a759ee005db03e84ae7d006184542baab58f1"
SPLIT_MANIFEST_SELF_SHA256 = "7b256808dacf446b06bc4f6cdc0ab8f0aa7585a2a4e3a56364cdb3508d17fbdc"

_CANDIDATE_KEYS = {
    "candidate_id", "candidate_version", "candidate_vi", "context_ids",
    "context_set_id", "domain", "part_of_speech", "provenance",
    "record_sha256", "schema_id", "schema_version", "scope_id",
    "sense_definition", "sense_id", "sense_inventory_version", "term_en",
    "term_id",
}
_CONTEXT_KEYS = {
    "block_id", "boundary_only", "chapter_id", "content_sha256",
    "context_class", "context_id", "locator_status", "matched_surface",
    "provenance", "record_sha256", "schema_id", "schema_version",
    "sense_id", "sense_relation", "sentence_id", "source_artifact_sha256",
    "source_text", "synthetic",
}
_FORBIDDEN_PRODUCER_KEYS = {
    "annotation", "candidate_rank", "decision", "expected_result",
    "final_glossary_decision", "gold_label", "reviewer_decision", "winner",
}


class D0DatasetAuthorityError(ValueError):
    """Raised when the detached producer-safe Dataset authority drifts."""


@dataclass(frozen=True)
class D0DatasetSnapshot:
    candidates: tuple[dict[str, Any], ...]
    contexts: tuple[dict[str, Any], ...]
    assignments: dict[str, str]
    proof: dict[str, Any]


def _git(repo: Path, *arguments: str, text: bool = False) -> bytes | str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *arguments],
            check=True,
            capture_output=True,
            text=text,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise D0DatasetAuthorityError(f"git command failed: {' '.join(arguments)}") from exc
    return completed.stdout


def _blob(repo: Path, commit: str, relative: str) -> bytes:
    canonical_manifest_path(relative)
    return bytes(_git(repo, "show", f"{commit}:{relative}"))


def _commit_identity(repo: Path, commit: str) -> tuple[str, str]:
    resolved = str(_git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}", text=True)).strip().lower()
    tree = str(_git(repo, "rev-parse", f"{commit}^{{tree}}", text=True)).strip().lower()
    row = str(_git(repo, "rev-list", "--parents", "-n", "1", commit, text=True)).strip().lower().split()
    if resolved != commit or len(row) != 2 or row[0] != commit:
        raise D0DatasetAuthorityError("Dataset authority commit identity is invalid")
    return tree, row[1]


def _jsonl(data: bytes, field: str) -> list[dict[str, Any]]:
    try:
        text = data.decode("utf-8")
        return [loads_strict(line) for line in text.splitlines() if line]
    except (UnicodeDecodeError, ValueError) as exc:
        raise D0DatasetAuthorityError(f"{field} is not strict UTF-8 JSONL") from exc


def _verify_record(value: Mapping[str, Any], keys: set[str], field: str) -> None:
    if set(value) != keys:
        raise D0DatasetAuthorityError(f"{field} record shape drifted")
    declared = value.get("record_sha256")
    unsigned = dict(value)
    unsigned.pop("record_sha256", None)
    if declared != sha256_value(unsigned):
        raise D0DatasetAuthorityError(f"{field} record self hash mismatch")


def _forbid_producer_metadata(value: Any) -> None:
    if isinstance(value, Mapping):
        forbidden = _FORBIDDEN_PRODUCER_KEYS & set(value)
        if forbidden:
            raise D0DatasetAuthorityError(f"producer-safe payload contains forbidden metadata: {sorted(forbidden)}")
        for item in value.values():
            _forbid_producer_metadata(item)
    elif isinstance(value, list):
        for item in value:
            _forbid_producer_metadata(item)


def load_d0_dataset_snapshot(repo: Path) -> D0DatasetSnapshot:
    final_tree, final_parent = _commit_identity(repo, DATASET_FINAL_SEAL_COMMIT)
    if final_tree != DATASET_FINAL_SEAL_TREE or final_parent != DATASET_FINAL_SEAL_PARENT:
        raise D0DatasetAuthorityError("Dataset final publication Git identity drifted")
    source_tree, _source_parent = _commit_identity(repo, DATASET_SOURCE_COMMIT)

    receipt_bytes = _blob(repo, DATASET_FINAL_SEAL_COMMIT, FINAL_RECEIPT_PATH)
    if sha256_bytes(receipt_bytes) != FINAL_RECEIPT_PHYSICAL_SHA256:
        raise D0DatasetAuthorityError("Dataset final publication receipt physical hash drifted")
    receipt = loads_strict(receipt_bytes.decode("utf-8"))
    if (
        receipt.get("receipt_sha256") != FINAL_RECEIPT_DECLARED_SHA256
        or receipt.get("status") != "PRODUCER_SAFE_50_150_FINAL_GIT_PUBLICATION_SEAL_READY_FOR_REVIEW"
        or receipt.get("provider_call_count") != 0
        or receipt.get("network_call_count") != 0
        or receipt.get("final_glossary_decision") is not None
        or receipt.get("cardinality") != {
            "candidate_count": 150,
            "candidates_per_sense": 3,
            "context_count": 386,
            "sense_count": 50,
            "senses_with_contrastive_context": 46,
            "senses_without_contrastive_context": 4,
        }
        or receipt.get("package", {}).get("zip_sha256") != PRODUCER_ZIP_SHA256
    ):
        raise D0DatasetAuthorityError("Dataset final publication receipt contract drifted")
    if sha256_bytes(_blob(repo, DATASET_FINAL_SEAL_COMMIT, PRODUCER_ZIP_PATH)) != PRODUCER_ZIP_SHA256:
        raise D0DatasetAuthorityError("Dataset producer-safe ZIP physical hash drifted")

    manifest_bytes = _blob(repo, DATASET_FINAL_SEAL_COMMIT, PRODUCER_MANIFEST_PATH)
    if sha256_bytes(manifest_bytes) != PRODUCER_MANIFEST_PHYSICAL_SHA256:
        raise D0DatasetAuthorityError("Dataset producer-safe manifest physical hash drifted")
    manifest = loads_strict(manifest_bytes.decode("utf-8"))
    unsigned_manifest = dict(manifest)
    declared_manifest = unsigned_manifest.pop("manifest_sha256", None)
    if declared_manifest != PRODUCER_MANIFEST_SELF_SHA256 or sha256_value(unsigned_manifest) != declared_manifest:
        raise D0DatasetAuthorityError("Dataset producer-safe manifest self hash drifted")
    if (
        manifest.get("sense_count") != 50
        or manifest.get("candidate_count") != 150
        or manifest.get("context_count") != 386
        or manifest.get("candidates_per_sense") != 3
        or manifest.get("candidate_identity_sha256") != PRODUCER_CANDIDATE_IDENTITY_SHA256
        or manifest.get("context_identity_sha256") != PRODUCER_CONTEXT_IDENTITY_SHA256
        or manifest.get("provider_call_count") != 0
        or manifest.get("network_call_count") != 0
        or manifest.get("final_glossary_decision") is not None
    ):
        raise D0DatasetAuthorityError("Dataset producer-safe manifest cardinality/identity drifted")

    candidate_bytes = _blob(repo, DATASET_FINAL_SEAL_COMMIT, PRODUCER_CANDIDATES_PATH)
    context_bytes = _blob(repo, DATASET_FINAL_SEAL_COMMIT, PRODUCER_CONTEXTS_PATH)
    if manifest.get("files", {}).get("pipeline_input_50_150.jsonl", {}).get("sha256") != sha256_bytes(candidate_bytes):
        raise D0DatasetAuthorityError("Dataset candidate payload hash drifted")
    if manifest.get("files", {}).get("pipeline_contexts_386.jsonl", {}).get("sha256") != sha256_bytes(context_bytes):
        raise D0DatasetAuthorityError("Dataset context payload hash drifted")
    candidates = _jsonl(candidate_bytes, "Dataset candidates")
    contexts = _jsonl(context_bytes, "Dataset contexts")
    if len(candidates) != 150 or len(contexts) != 386:
        raise D0DatasetAuthorityError("Dataset producer-safe payload cardinality drifted")
    for index, row in enumerate(candidates):
        _verify_record(row, _CANDIDATE_KEYS, f"candidate[{index}]")
        _forbid_producer_metadata(row)
    for index, row in enumerate(contexts):
        _verify_record(row, _CONTEXT_KEYS, f"context[{index}]")
        _forbid_producer_metadata(row)

    candidate_ids = [row["candidate_id"] for row in candidates]
    context_ids = [row["context_id"] for row in contexts]
    if len(set(candidate_ids)) != 150 or len(set(context_ids)) != 386:
        raise D0DatasetAuthorityError("Dataset producer-safe IDs are not unique")
    candidates_by_sense = collections.Counter(row["sense_id"] for row in candidates)
    if set(candidates_by_sense.values()) != {3} or len(candidates_by_sense) != 50:
        raise D0DatasetAuthorityError("Dataset does not contain exactly three candidates per sense")
    contexts_by_id = {row["context_id"]: row for row in contexts}
    for row in candidates:
        if not isinstance(row["context_ids"], list) or not row["context_ids"]:
            raise D0DatasetAuthorityError("candidate context_ids are empty")
        if any(context_id not in contexts_by_id for context_id in row["context_ids"]):
            raise D0DatasetAuthorityError("candidate references an unknown context")

    split_bytes = _blob(repo, DATASET_SOURCE_COMMIT, SPLIT_MANIFEST_PATH)
    if sha256_bytes(split_bytes) != SPLIT_MANIFEST_PHYSICAL_SHA256:
        raise D0DatasetAuthorityError("Dataset split manifest physical hash drifted")
    split = loads_strict(split_bytes.decode("utf-8"))
    unsigned_split = dict(split)
    unsigned_split["integrity"] = {}
    if (
        split.get("integrity") != {"self_sha256": SPLIT_MANIFEST_SELF_SHA256}
        or sha256_value(unsigned_split) != SPLIT_MANIFEST_SELF_SHA256
        or split.get("counts") != {"development": 30, "test": 10, "validation": 10}
        or split.get("provider_call_count") != 0
        or split.get("stage_b_gold_autofill_count") != 0
        or split.get("final_glossary_decision") is not None
    ):
        raise D0DatasetAuthorityError("Dataset split authority drifted")
    assignments = split.get("assignments")
    if not isinstance(assignments, Mapping) or set(assignments) != set(candidates_by_sense):
        raise D0DatasetAuthorityError("Dataset split assignments do not exactly cover producer senses")
    if set(assignments.values()) - {"development", "validation", "test"}:
        raise D0DatasetAuthorityError("Dataset split assignment contains an unknown split")

    proof = {
        "dataset_final_seal_commit": DATASET_FINAL_SEAL_COMMIT,
        "dataset_final_seal_parent": DATASET_FINAL_SEAL_PARENT,
        "dataset_final_seal_tree": DATASET_FINAL_SEAL_TREE,
        "dataset_final_receipt_path": FINAL_RECEIPT_PATH,
        "dataset_final_receipt_physical_sha256": FINAL_RECEIPT_PHYSICAL_SHA256,
        "dataset_final_receipt_declared_sha256": FINAL_RECEIPT_DECLARED_SHA256,
        "producer_manifest_physical_sha256": PRODUCER_MANIFEST_PHYSICAL_SHA256,
        "producer_manifest_self_sha256": PRODUCER_MANIFEST_SELF_SHA256,
        "producer_zip_sha256": PRODUCER_ZIP_SHA256,
        "candidate_identity_sha256": PRODUCER_CANDIDATE_IDENTITY_SHA256,
        "context_identity_sha256": PRODUCER_CONTEXT_IDENTITY_SHA256,
        "split_authority_commit": DATASET_SOURCE_COMMIT,
        "split_authority_tree": source_tree,
        "split_manifest_path": SPLIT_MANIFEST_PATH,
        "split_manifest_physical_sha256": SPLIT_MANIFEST_PHYSICAL_SHA256,
        "split_manifest_self_sha256": SPLIT_MANIFEST_SELF_SHA256,
        "sense_count": 50,
        "candidate_count": 150,
        "context_count": 386,
        "senses_with_contrastive_context": 46,
        "producer_forbidden_metadata_count": 0,
        "gold_label_fields_read": 0,
        "provider_calls": 0,
        "network_calls": 0,
    }
    return D0DatasetSnapshot(
        candidates=tuple(dict(row) for row in candidates),
        contexts=tuple(dict(row) for row in contexts),
        assignments=dict(assignments),
        proof=proof,
    )
