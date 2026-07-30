"""Fail-closed external authority loading for E Live."""

from .adapter import (
    EXTERNAL_RECEIPT_ROLES,
    load_authority_bundle,
    make_external_authority_receipt,
    make_trusted_authority_profile,
    validate_loaded_authority_bundle,
    validate_authority_profile,
)
from .e05 import (
    E05_DELIVERY_SHA256,
    E05ExactIntegrationInputs,
    load_e05_exact_integration_inputs,
    validate_e05_protocol_instance,
)
from .production import load_production_authority
from .source_governance import (
    RuntimeRegistryProjection,
    admit_url_before_network,
    fetch_after_path_admission,
    load_runtime_registry_projection,
)

__all__ = [
    "EXTERNAL_RECEIPT_ROLES",
    "E05_DELIVERY_SHA256",
    "E05ExactIntegrationInputs",
    "load_authority_bundle",
    "load_e05_exact_integration_inputs",
    "load_production_authority",
    "RuntimeRegistryProjection",
    "admit_url_before_network",
    "fetch_after_path_admission",
    "load_runtime_registry_projection",
    "make_external_authority_receipt",
    "make_trusted_authority_profile",
    "validate_authority_profile",
    "validate_e05_protocol_instance",
    "validate_loaded_authority_bundle",
]
