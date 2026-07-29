"""Typed failures for fail-closed integration operations."""


class HarnessError(Exception):
    """Base class for all expected harness failures."""


class AuthorityError(HarnessError):
    pass


class IntegrityError(HarnessError):
    pass


class DiscoveryError(HarnessError):
    pass


class JoinError(HarnessError):
    pass


class PolicyError(HarnessError):
    pass


class ExecutionError(HarnessError):
    pass


class ReplayError(HarnessError):
    pass


class StorageError(HarnessError):
    pass


class ValidationError(HarnessError):
    pass
