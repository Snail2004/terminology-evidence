"""Strict zero-API adapters for the shared C/E D2L dataset authorities."""

from .adapter import adapt_dataset_zip
from .archive import (
    DatasetAdapterError,
    VerifiedDatasetArchive,
    load_supported_dataset_archive,
    validate_zip_member_names,
)
from .contracts import (
    ADAPTER_POLICY_ID,
    ADAPTER_SCHEMA_ID,
    ADAPTER_SCHEMA_VERSION,
    CANDIDATE_SCHEMA_ID,
    CANDIDATE_SCHEMA_VERSION,
    seal_adapter_candidate,
    seal_adapter_package,
    validate_adapter_candidate,
    validate_adapter_package,
)
from .specs import (
    PILOT_MANIFEST_SHA256,
    PILOT_SCHEMA_ID,
    PILOT_SCHEMA_VERSION,
    PILOT_ZIP_SHA256,
    V3_MANIFEST_SHA256,
    V3_SCHEMA_ID,
    V3_SCHEMA_VERSION,
    V3_ZIP_SHA256,
)

__all__ = [
    "ADAPTER_POLICY_ID",
    "ADAPTER_SCHEMA_ID",
    "ADAPTER_SCHEMA_VERSION",
    "CANDIDATE_SCHEMA_ID",
    "CANDIDATE_SCHEMA_VERSION",
    "DatasetAdapterError",
    "PILOT_MANIFEST_SHA256",
    "PILOT_SCHEMA_ID",
    "PILOT_SCHEMA_VERSION",
    "PILOT_ZIP_SHA256",
    "V3_MANIFEST_SHA256",
    "V3_SCHEMA_ID",
    "V3_SCHEMA_VERSION",
    "V3_ZIP_SHA256",
    "VerifiedDatasetArchive",
    "adapt_dataset_zip",
    "load_supported_dataset_archive",
    "seal_adapter_candidate",
    "seal_adapter_package",
    "validate_adapter_candidate",
    "validate_adapter_package",
    "validate_zip_member_names",
]
