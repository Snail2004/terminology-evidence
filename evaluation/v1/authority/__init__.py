"""AR-2 allowed-authority profile and external artifact verification."""

from .verifier import (
    AuthorityProfileError,
    load_allowed_authority_profile,
    profile_path,
    verify_authority_evidence_object,
    verify_external_authorities,
)
from ..artifacts.authority import secure_existing_directory, secure_existing_file

__all__ = [
    "AuthorityProfileError",
    "load_allowed_authority_profile",
    "profile_path",
    "secure_existing_directory",
    "secure_existing_file",
    "verify_authority_evidence_object",
    "verify_external_authorities",
]
