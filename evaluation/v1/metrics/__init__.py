"""Deterministic preregistered metric and statistical helpers."""

from .bootstrap import grouped_bootstrap
from .components import summarize_c, summarize_downstream, summarize_e, summarize_gates, summarize_tac
from .core import summarize_global, summarize_labels
from .intervals import wilson_interval
from .paired import mcnemar_exact

__all__ = [
    "grouped_bootstrap",
    "mcnemar_exact",
    "summarize_c",
    "summarize_downstream",
    "summarize_e",
    "summarize_global",
    "summarize_gates",
    "summarize_labels",
    "summarize_tac",
    "wilson_interval",
]
