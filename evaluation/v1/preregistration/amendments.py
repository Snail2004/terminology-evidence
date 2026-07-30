"""AR-2 amendment rules enforced through the durable event writer."""

from __future__ import annotations

import re
from typing import Any, Mapping

from ..artifacts.authority import canonical_manifest_path
from ..constants import AMENDMENT_SCHEMA_ID, SCHEMA_VERSION
from .freeze import (
    EVENT_AMENDMENT,
    EVENT_EXPLORATORY,
    STATE_HIDDEN_TEST,
    DurablePreregistrationStore,
)


class AmendmentError(ValueError):
    """Raised when an amendment would alter frozen or hidden-test authority."""


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FIELDS = {
    "schema_id",
    "schema_version",
    "amendment_id",
    "reason",
    "affected_artifacts",
    "before_hashes",
    "after_hashes",
    "changes_primary_analysis",
    "impact_on_claims",
    "new_preregistration_version",
    "analysis_namespace",
}


def validate_amendment(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _FIELDS:
        raise AmendmentError("amendment shape is invalid")
    if value.get("schema_id") != AMENDMENT_SCHEMA_ID or value.get("schema_version") != SCHEMA_VERSION:
        raise AmendmentError("unsupported amendment schema")
    for field in ("amendment_id", "reason", "impact_on_claims"):
        if not isinstance(value.get(field), str) or not value[field].strip():
            raise AmendmentError(f"amendment {field} is required")
    affected = value.get("affected_artifacts")
    if not isinstance(affected, list) or not affected:
        raise AmendmentError("affected_artifacts must be a nonempty list")
    canonical = [canonical_manifest_path(item) for item in affected]
    if len(set(canonical)) != len(canonical) or canonical != sorted(canonical):
        raise AmendmentError("affected_artifacts must be unique and sorted")
    before = value.get("before_hashes")
    after = value.get("after_hashes")
    if not isinstance(before, Mapping) or not isinstance(after, Mapping) or set(before) != set(canonical) or set(after) != set(canonical):
        raise AmendmentError("before/after hashes must exactly bind affected_artifacts")
    for field, mapping in (("before_hashes", before), ("after_hashes", after)):
        for name, digest in mapping.items():
            if not isinstance(digest, str) or not _SHA256.fullmatch(digest) or set(digest) == {"0"}:
                raise AmendmentError(f"{field}.{name} is invalid")
    if not isinstance(value.get("changes_primary_analysis"), bool):
        raise AmendmentError("changes_primary_analysis must be boolean")
    version = value.get("new_preregistration_version")
    if version is not None and (not isinstance(version, str) or not version.strip()):
        raise AmendmentError("new_preregistration_version is invalid")
    namespace = value.get("analysis_namespace")
    if namespace is not None:
        if not isinstance(namespace, str) or not namespace.startswith("exploratory/"):
            raise AmendmentError("analysis_namespace must use exploratory/ namespace")
        canonical_manifest_path(namespace)
    return dict(value)


def append_amendment(
    store: DurablePreregistrationStore,
    amendment: Mapping[str, Any],
    *,
    actor: str,
    issued_at: str | None = None,
) -> dict[str, Any]:
    checked = validate_amendment(amendment)
    state = store.load()
    if state["status"] == STATE_HIDDEN_TEST:
        if checked["changes_primary_analysis"] is True:
            raise AmendmentError("primary-analysis amendments are forbidden after hidden-test access")
        if checked["analysis_namespace"] is None or checked["new_preregistration_version"] is not None:
            raise AmendmentError("post-test work must be isolated as exploratory and cannot refreeze primary analysis")
        return store._append_event(
            EVENT_EXPLORATORY,
            actor=actor,
            issued_at=issued_at,
            payload={"amendment": checked, "analysis_namespace": checked["analysis_namespace"]},
        )
    if checked["analysis_namespace"] is not None or not checked["new_preregistration_version"]:
        raise AmendmentError("pre-test amendment requires a new preregistration version and no exploratory namespace")
    phase = "PRE_VALIDATION" if state["status"] == "FROZEN_BEFORE_VALIDATION" else "POST_VALIDATION_PRE_TEST"
    return store._append_event(
        EVENT_AMENDMENT,
        actor=actor,
        issued_at=issued_at,
        payload={"amendment": checked, "phase": phase, "new_freeze_required": True},
    )
