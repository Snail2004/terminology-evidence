"""Fail-closed external authority loading for E Live."""

from .adapter import (
    EXTERNAL_RECEIPT_ROLES,
    load_authority_bundle,
    make_external_authority_receipt,
    make_trusted_authority_profile,
    validate_loaded_authority_bundle,
    validate_authority_profile,
)
from .production import load_production_authority

__all__ = [
    "EXTERNAL_RECEIPT_ROLES",
    "load_authority_bundle",
    "load_production_authority",
    "make_external_authority_receipt",
    "make_trusted_authority_profile",
    "validate_authority_profile",
    "validate_loaded_authority_bundle",
]
