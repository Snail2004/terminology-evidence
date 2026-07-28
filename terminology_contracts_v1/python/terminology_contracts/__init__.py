"""Shared terminology validation boundary contracts."""

__version__ = "1.1.0"

from .registries import LEGACY_VERSION, PACKAGE_VERSION
from .bindings import seal_frozen_candidate_contract, verify_frozen_candidate_binding
from .validation import verify_certificate_bundle

__all__ = [
    "LEGACY_VERSION",
    "PACKAGE_VERSION",
    "__version__",
    "seal_frozen_candidate_contract",
    "verify_certificate_bundle",
    "verify_frozen_candidate_binding",
]
