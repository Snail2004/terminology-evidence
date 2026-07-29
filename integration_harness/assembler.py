"""Public Global Validator CLI adapter and command boundary."""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from .errors import ExecutionError
from .identity import CandidateIdentity
from .join import JoinedCandidate
from .jsonio import loads_strict


@dataclass
class GlobalCliAdapter:
    """Invoke only the public Global Validator CLI, never its private modules."""

    repository_root: Path
    authority_receipt: Path
    action_policy: Path | None = None
    contracts_root: Path | None = None
    command_prefix: tuple[str, ...] = field(default_factory=tuple)
    python_executable: str = sys.executable

    def __post_init__(self) -> None:
        self.repository_root = self.repository_root.resolve()
        self.authority_receipt = self.authority_receipt.resolve()
        if self.contracts_root is None:
            self.contracts_root = self.repository_root / "terminology_contracts_v1"
        else:
            self.contracts_root = self.contracts_root.resolve()

    def _base_command(self) -> list[str]:
        if self.command_prefix:
            return list(self.command_prefix)
        return [self.python_executable, "-m", "global_validator.v1.cli"]

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        existing = env.get("PYTHONPATH", "")
        roots = [str(self.repository_root), str(self.contracts_root / "python")]
        env["PYTHONPATH"] = os.pathsep.join(roots + ([existing] if existing else []))
        env["SYSTEM_INTEGRATION_NETWORK_POLICY"] = "FORBIDDEN"
        env["NO_PROXY"] = "*"
        return env

    def _call(self, args: Sequence[str]) -> dict[str, Any]:
        command = self._base_command() + list(args)
        completed = subprocess.run(
            command,
            cwd=self.repository_root,
            env=self._env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if completed.returncode != 0:
            raise ExecutionError(
                f"Global CLI failed ({completed.returncode}): {completed.stderr.strip() or completed.stdout.strip()}"
            )
        try:
            result = loads_strict(completed.stdout.encode("utf-8"), require_object=True)
        except Exception as exc:
            raise ExecutionError(f"Global CLI emitted invalid JSON: {exc}") from exc
        if result.get("status") not in {"PASS", "OK"}:
            raise ExecutionError(f"Global CLI returned non-success: {result}")
        return result

    def _authority_args(self) -> list[str]:
        args = [
            "--repository-root", str(self.repository_root),
            "--authority-receipt", str(self.authority_receipt),
        ]
        if self.action_policy is not None:
            args.extend(["--action-policy", str(self.action_policy.resolve())])
        return args

    def assemble(self, candidate: JoinedCandidate, output: Path) -> dict[str, Any]:
        paths = candidate.paths()
        args = ["assemble-input", *self._authority_args()]
        args.extend(["--effective-sense", str(paths["effective_sense"])])
        args.extend(["--frozen-candidate", str(paths["frozen_candidate"])])
        args.extend(["--constraints", str(paths["constraints"])])
        args.extend(["--context-evidence", str(paths["context_evidence"])])
        args.extend(["--attestation-evidence", str(paths["attestation_evidence"])])
        args.extend(["--assembled-at", "1970-01-01T00:00:00+00:00", "--output", str(output)])
        return self._call(args)

    def validate_input(self, input_path: Path, *, collision_index: Path | None = None) -> dict[str, Any]:
        args = ["validate-input", *self._authority_args(), "--input", str(input_path)]
        if collision_index is not None:
            args.extend(["--collision-index", str(collision_index)])
        return self._call(args)

    def run(self, input_path: Path, output_dir: Path, run_id: str, *, mode: str, collision_index: Path | None = None) -> dict[str, Any]:
        args = [
            "run", *self._authority_args(), "--input", str(input_path), "--mode", mode,
            "--output-dir", str(output_dir), "--run-id", run_id,
            "--started-at", "1970-01-01T00:00:00+00:00",
            "--completed-at", "1970-01-01T00:00:00+00:00",
        ]
        if collision_index is not None:
            args.extend(["--collision-index", str(collision_index)])
        return self._call(args)

    def replay(self, run_dir: Path) -> dict[str, Any]:
        return self._call(["replay", "--run-dir", str(run_dir)])
