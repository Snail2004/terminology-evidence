"""Deterministic zero-API integration helpers for Evidence E."""

from .controlled_registry import inspect_controlled_registry
from .pilot import run_zero_api_pilot

__all__ = ["inspect_controlled_registry", "run_zero_api_pilot"]
