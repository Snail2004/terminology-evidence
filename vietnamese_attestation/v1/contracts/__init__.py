"""Versioned contracts for Vietnamese Attestation Evidence V1."""

from .frozen_candidate import (
    FROZEN_CANDIDATE_POLICY_ID,
    FROZEN_CANDIDATE_SCHEMA_ID,
    FROZEN_CANDIDATE_SCHEMA_VERSION,
    seal_frozen_candidate,
    validate_frozen_candidate,
)
from .judge import validate_judge_payload, validate_judge_payload_for_snippet
from .output import (
    PACKAGE_SCHEMA_ID,
    PACKAGE_SCHEMA_VERSION,
    seal_attestation_package,
    validate_attestation_package,
)
from .shared import (
    SHARED_ATTESTATION_PACKAGE_SCHEMA_ID,
    SHARED_FROZEN_CANDIDATE_SCHEMA_ID,
    adapt_shared_frozen_candidate,
    project_shared_attestation_package,
    validate_shared_attestation_package,
    validate_shared_frozen_candidate,
)

__all__ = [
    "FROZEN_CANDIDATE_POLICY_ID",
    "FROZEN_CANDIDATE_SCHEMA_ID",
    "FROZEN_CANDIDATE_SCHEMA_VERSION",
    "PACKAGE_SCHEMA_ID",
    "PACKAGE_SCHEMA_VERSION",
    "SHARED_ATTESTATION_PACKAGE_SCHEMA_ID",
    "SHARED_FROZEN_CANDIDATE_SCHEMA_ID",
    "adapt_shared_frozen_candidate",
    "project_shared_attestation_package",
    "seal_frozen_candidate",
    "seal_attestation_package",
    "validate_frozen_candidate",
    "validate_attestation_package",
    "validate_judge_payload",
    "validate_judge_payload_for_snippet",
    "validate_shared_attestation_package",
    "validate_shared_frozen_candidate",
]
