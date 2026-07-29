"""Global Terminology Validator V1.1 public facade."""

from .config import ENGINE_VERSION, ExecutionMode, RunConfig
from .engine import RunResult, run_global_validator

__all__ = [
    "ENGINE_VERSION",
    "ExecutionMode",
    "RunConfig",
    "RunResult",
    "run_global_validator",
]
