"""Stable identifiers and policy constants for Evaluation V1."""

SCHEMA_VERSION = "1.0.0"
PREREGISTRATION_SCHEMA_ID = "EvaluationPreregistrationV1"
RECEIPT_SCHEMA_ID = "EvaluationPreregistrationReceiptV1"
AMENDMENT_SCHEMA_ID = "EvaluationPreregistrationAmendmentV1"
STATUS_DRAFT = "DRAFT"
STATUS_FROZEN = "FROZEN_BEFORE_VALIDATION"
STATUS_VALIDATION_OPEN = "VALIDATION_OPEN"
STATUS_TEST_SEALED = "TEST_SEALED"
STATUS_TEST_OPENED = "TEST_OPENED"
ALLOWED_GOLD_LABELS = (
    "ACCEPT",
    "CONDITIONAL",
    "REJECT",
    "SPLIT_REQUIRED",
    "HUMAN_UNJUDGEABLE",
)
ALLOWED_GLOBAL_STATUSES = (
    "AUTO_APPROVED",
    "PROVISIONAL",
    "HUMAN_REVIEW",
    "REJECTED",
    "SPLIT_REQUIRED",
)
ALLOWED_EXCLUSION_REASONS = (
    "CORRUPT_ARTIFACT",
    "MISSING_REQUIRED_GOLD",
    "INVALID_SCHEMA",
    "UNRESOLVED_SENSE_AUTHORITY",
    "HUMAN_UNJUDGEABLE",
    "PROTOCOL_VIOLATION",
)
PRIMARY_METRIC_IDS = (
    "auto_approved_precision",
    "auto_approved_coverage",
    "false_approval_count",
    "human_review_rate",
    "hard_rejection_accuracy",
)
