"""Exact Main canary authority inputs; these inputs never authorize a run."""

from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ...strict_json import reject_link, strict_json_loads
from ..common import LiveSchemaError, verify_seal
from .e05 import E05ExactIntegrationInputs, validate_e05_protocol_instance


CORPUS_AUTHORITY_PACKAGE_SHA256 = (
    "83a2fddd4f255a8210cdc12ba0c572d04cd68e089089bfe9e94f4240fd298d63"
)
CORPUS_AUTHORIZATION_SELF_SHA256 = (
    "cdfcd233c6e952eceb8c84e39520afbe19bc26ebcad151a12ce358098162336f"
)
CORPUS_AUTHORIZATION_PHYSICAL_SHA256 = (
    "c3480110b40e6d0935102b1d702ea0190ad81b34b9bf96b08976454eaa377085"
)
DRAFT4_FINAL_PACKAGE_SHA256 = (
    "f29c3dd59f30c54f13880164b9ab5d403d332a1de6b74edab6f8b554b4df8bae"
)
DRAFT4_FINAL_AUTHORITY_SELF_SHA256 = (
    "98dbd8322ed92b809a70f28c33adee55ce06856c3a55b13860829b56bc2a27b6"
)
DRAFT4_FINAL_AUTHORITY_PHYSICAL_SHA256 = (
    "c9f0a4cf5185a6df81636750237e068f04054b54577351eaf8e6fb62db627af4"
)
E_AUTHORITY_COMMIT = "b3c1bce9089cc96a38777a16ac9aa7a00ba377bb"
E_AUTHORITY_TREE = "a6dfce179c47b4b3cdd4727238fda14db817ad96"


@dataclass(frozen=True)
class FinalCanaryAuthorityInputs:
    corpus_package_path: Path
    corpus_package_bytes: bytes
    corpus_authorization: Mapping[str, Any]
    corpus_authorization_bytes: bytes
    draft4_package_path: Path
    draft4_package_bytes: bytes
    draft4_authority: Mapping[str, Any]
    draft4_authority_bytes: bytes

    @property
    def live_execution_authorized(self) -> bool:
        return False


def load_final_canary_authority_inputs(
    corpus_authority_package_path: str | Path,
    draft4_final_authority_package_path: str | Path,
) -> FinalCanaryAuthorityInputs:
    corpus_path, corpus_raw = _exact_package(
        corpus_authority_package_path,
        CORPUS_AUTHORITY_PACKAGE_SHA256,
        "corpus-acquisition authority",
    )
    corpus_receipt_raw, corpus_receipt = _pinned_member(
        corpus_raw,
        "main_corpus_acquisition_authorization_v1.json",
        CORPUS_AUTHORIZATION_PHYSICAL_SHA256,
        CORPUS_AUTHORIZATION_SELF_SHA256,
    )
    final_path, final_raw = _exact_package(
        draft4_final_authority_package_path,
        DRAFT4_FINAL_PACKAGE_SHA256,
        "Draft4 final authority",
    )
    final_receipt_raw, final_receipt = _pinned_member(
        final_raw,
        "draft4_final_authority_receipt_v1.json",
        DRAFT4_FINAL_AUTHORITY_PHYSICAL_SHA256,
        DRAFT4_FINAL_AUTHORITY_SELF_SHA256,
    )
    if (
        corpus_receipt.get("schema_id")
        != "MainControlledCorpusAcquisitionAuthorizationV1"
        or corpus_receipt.get("status")
        != "CORPUS_ACQUISITION_AUTHORIZED_PENDING_USER_GO"
        or corpus_receipt.get("corpus_acquisition_authorized") is not True
        or corpus_receipt.get("network_calls_authorized") is not True
        or corpus_receipt.get("provider_calls_authorized") is not False
        or corpus_receipt.get("run_authorized") is not False
        or corpus_receipt.get("user_go_required") is not True
    ):
        raise LiveSchemaError("corpus-acquisition authority boundary mismatch")
    expected_corpus_bindings = {
        "draft4_final_authority_package_sha256": DRAFT4_FINAL_PACKAGE_SHA256,
        "draft4_final_authority_physical_sha256": DRAFT4_FINAL_AUTHORITY_PHYSICAL_SHA256,
        "draft4_final_authority_self_sha256": DRAFT4_FINAL_AUTHORITY_SELF_SHA256,
        "e_commit": E_AUTHORITY_COMMIT,
        "e_tree": E_AUTHORITY_TREE,
    }
    if any(
        corpus_receipt.get("bindings", {}).get(key) != value
        for key, value in expected_corpus_bindings.items()
    ):
        raise LiveSchemaError("corpus-acquisition authority binding mismatch")
    if (
        final_receipt.get("schema_id")
        != "LiveRunProtocolDraft4FinalAuthorityReceiptV1"
        or final_receipt.get("status")
        != "DRAFT4_FINAL_AUTHORITY_SEALED_CANARY_AUTHORIZATION_HOLD"
        or final_receipt.get("authority_state", {}).get("draft4_final_authority")
        is not True
        or final_receipt.get("authority_state", {}).get("run_authorized")
        is not False
    ):
        raise LiveSchemaError("Draft4 final authority boundary mismatch")
    if corpus_receipt.get("candidate_id") != final_receipt.get("candidate_scope", {}).get(
        "candidate_id"
    ) or corpus_receipt.get("phase_id") != final_receipt.get("candidate_scope", {}).get(
        "phase_id"
    ):
        raise LiveSchemaError("canary authority candidate scope mismatch")
    return FinalCanaryAuthorityInputs(
        corpus_package_path=corpus_path,
        corpus_package_bytes=corpus_raw,
        corpus_authorization=corpus_receipt,
        corpus_authorization_bytes=corpus_receipt_raw,
        draft4_package_path=final_path,
        draft4_package_bytes=final_raw,
        draft4_authority=final_receipt,
        draft4_authority_bytes=final_receipt_raw,
    )


def load_future_live_authorization_receipt(
    path: str | Path,
    *,
    inputs: E05ExactIntegrationInputs,
    final_authority: FinalCanaryAuthorityInputs,
    registry_self_sha256: str,
    snapshot_self_sha256: str,
    retrieval_policy_sha256: str,
    query_template_set_sha256: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate a future Main receipt; no receipt is created or embedded here."""

    receipt_path, raw = _regular_file(path, "live authorization receipt")
    del receipt_path
    receipt = _json_object(raw, "live authorization receipt")
    validate_e05_protocol_instance(
        inputs, role="LIVE_AUTHORIZATION_RECEIPT", value=receipt
    )
    if not verify_seal(receipt):
        raise LiveSchemaError("live authorization receipt self hash mismatch")
    draft4 = final_authority.draft4_authority
    if (
        receipt.get("authorization_status") != "RUN_AUTHORIZED"
        or receipt.get("test_only") is not False
        or receipt.get("approval_artifact_self_sha256")
        != DRAFT4_FINAL_AUTHORITY_SELF_SHA256
        or receipt.get("approval_artifact_physical_sha256")
        != DRAFT4_FINAL_AUTHORITY_PHYSICAL_SHA256
        or receipt.get("protocol_commit") != draft4.get("protocol", {}).get("commit")
        or receipt.get("protocol_tree_git_oid")
        != draft4.get("protocol", {}).get("tree")
        or receipt.get("phase_id") != draft4.get("candidate_scope", {}).get("phase_id")
        or receipt.get("issuer_id") != draft4.get("issuer_id")
        or receipt.get("authority_id") != draft4.get("authority_id")
    ):
        raise LiveSchemaError("live authorization receipt final-authority binding mismatch")
    bindings = receipt["bindings"]
    expected = {
        "phase_authorized_candidate_set_self_sha256": inputs.candidate_set["integrity"][
            "self_sha256"
        ],
        "phase_authorized_candidate_set_physical_sha256": inputs.integration_run_spec[
            "candidate_set"
        ]["physical_sha256"],
        "e_registry_sha256": registry_self_sha256,
        "e_corpus_sha256": snapshot_self_sha256,
        "e_retrieval_policy_sha256": retrieval_policy_sha256,
        "query_template_set_sha256": query_template_set_sha256,
    }
    if any(bindings.get(key) != value for key, value in expected.items()):
        raise LiveSchemaError("live authorization receipt E binding mismatch")
    authorities = bindings.get("pre_acquisition_authorities", {})
    if (
        authorities.get("e_release_commit") != E_AUTHORITY_COMMIT
        or authorities.get("e_release_tree_git_oid") != E_AUTHORITY_TREE
        or authorities.get("protocol_authority_self_sha256")
        != DRAFT4_FINAL_AUTHORITY_SELF_SHA256
        or authorities.get("protocol_authority_physical_sha256")
        != DRAFT4_FINAL_AUTHORITY_PHYSICAL_SHA256
    ):
        raise LiveSchemaError("live authorization receipt pre-acquisition binding mismatch")
    current = now or datetime.now(timezone.utc)
    if not _timestamp(receipt["valid_from"]) <= current <= _timestamp(
        receipt["valid_until"]
    ):
        raise LiveSchemaError("live authorization receipt is outside validity")
    return receipt


def _exact_package(path: str | Path, expected: str, label: str) -> tuple[Path, bytes]:
    resolved, raw = _regular_file(path, label)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise LiveSchemaError(f"{label} package physical SHA-256 mismatch")
    return resolved, raw


def _pinned_member(
    package_raw: bytes, name: str, physical: str, self_sha256: str
) -> tuple[bytes, dict[str, Any]]:
    try:
        with zipfile.ZipFile(io.BytesIO(package_raw)) as archive:
            if archive.namelist().count(name) != 1:
                raise LiveSchemaError(f"authority package member mismatch: {name}")
            raw = archive.read(name)
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise LiveSchemaError(f"cannot read authority package member: {name}") from exc
    if hashlib.sha256(raw).hexdigest() != physical:
        raise LiveSchemaError(f"authority member physical SHA-256 mismatch: {name}")
    value = _json_object(raw, name)
    if value.get("integrity", {}).get("self_sha256") != self_sha256 or not verify_seal(
        value
    ):
        raise LiveSchemaError(f"authority member self hash mismatch: {name}")
    return raw, value


def _regular_file(path: str | Path, label: str) -> tuple[Path, bytes]:
    supplied = Path(path).absolute()
    try:
        reject_link(supplied)
        resolved = supplied.resolve(strict=True)
        reject_link(resolved)
        raw = resolved.read_bytes()
    except (OSError, ValueError) as exc:
        raise LiveSchemaError(f"cannot read {label}: {path}") from exc
    if not resolved.is_file():
        raise LiveSchemaError(f"{label} is not a regular file")
    return resolved, raw


def _json_object(raw: bytes, label: str) -> dict[str, Any]:
    try:
        value = strict_json_loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise LiveSchemaError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise LiveSchemaError(f"{label} must be a JSON object")
    return value


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise LiveSchemaError("authorization validity must be a timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LiveSchemaError("authorization validity timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise LiveSchemaError("authorization validity timestamp lacks timezone")
    return parsed.astimezone(timezone.utc)


__all__ = [
    "CORPUS_AUTHORITY_PACKAGE_SHA256",
    "DRAFT4_FINAL_PACKAGE_SHA256",
    "FinalCanaryAuthorityInputs",
    "load_final_canary_authority_inputs",
    "load_future_live_authorization_receipt",
]
