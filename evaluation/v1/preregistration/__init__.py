"""AR-2 authority receipts and durable preregistration state."""

from .amendments import AmendmentError, append_amendment, validate_amendment
from .freeze import AccessLog, DurablePreregistrationStore, FreezeError, FreezeState
from .legacy import LegacyReceiptError, verify_legacy_receipt
from .recovery import RecoveryError, recover_projection, verify_recovery_plan, verify_recovery_receipt
from .receipt import (
    ReceiptError,
    VerifiedRealReceipt,
    build_receipt,
    verify_real_receipt,
    verify_real_receipt_capability,
    verify_receipt,
    verify_receipt_object,
    write_receipt,
)

__all__ = [
    "AccessLog",
    "AmendmentError",
    "DurablePreregistrationStore",
    "FreezeError",
    "FreezeState",
    "LegacyReceiptError",
    "ReceiptError",
    "RecoveryError",
    "VerifiedRealReceipt",
    "append_amendment",
    "build_receipt",
    "recover_projection",
    "validate_amendment",
    "verify_legacy_receipt",
    "verify_recovery_receipt",
    "verify_recovery_plan",
    "verify_real_receipt",
    "verify_real_receipt_capability",
    "verify_receipt",
    "verify_receipt_object",
    "write_receipt",
]
