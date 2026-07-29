from __future__ import annotations


class GlobalValidatorError(ValueError):
    category = "GLOBAL_VALIDATOR_ERROR"


class AuthorityVerificationError(GlobalValidatorError):
    category = "AUTHORITY_ERROR"


class InputValidationError(GlobalValidatorError):
    category = "SCHEMA_ERROR"


class IntegrityValidationError(GlobalValidatorError):
    category = "INTEGRITY_ERROR"


class JoinValidationError(GlobalValidatorError):
    category = "JOIN_ERROR"


class GateProjectionError(GlobalValidatorError):
    category = "GATE_PROJECTION_ERROR"


class GatePolicyError(GlobalValidatorError):
    category = "GATE_POLICY_ERROR"


class FeatureAssemblyError(GlobalValidatorError):
    category = "FEATURE_ASSEMBLY_ERROR"


class CalibrationError(GlobalValidatorError):
    category = "CALIBRATION_ERROR"


class DecisionReplayError(GlobalValidatorError):
    category = "DECISION_REPLAY_ERROR"


class CertificateBindingError(GlobalValidatorError):
    category = "CERTIFICATE_BINDING_ERROR"


class StorageError(GlobalValidatorError):
    category = "IO_ERROR"
