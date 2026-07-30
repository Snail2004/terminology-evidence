"""External staging and atomic immutable release publication."""

from __future__ import annotations

import os
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class PublicationError(ValueError):
    """Raised when release output could affect source or overwrite authority."""


def _fsync_parent(path: Path) -> None:
    try:
        descriptor = os.open(path.parent, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


@contextmanager
def external_atomic_stage(output: Path, repository_root: Path) -> Iterator[Path]:
    """Yield external staging; publish once by atomic rename on success."""
    output = output.resolve()
    repository_root = repository_root.resolve()
    try:
        output.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise PublicationError("release output must be outside the repository")
    if output.exists() or output.is_symlink():
        raise PublicationError("release output already exists and is immutable")
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = output.parent / f".{output.name}.{uuid.uuid4().hex}.staging"
    if staging.exists():
        raise PublicationError("staging collision")
    staging.mkdir()
    try:
        yield staging
        if output.exists() or output.is_symlink():
            raise PublicationError("release output appeared during staging")
        os.replace(staging, output)
        _fsync_parent(output)
    except BaseException:
        if staging.exists() and staging.parent == output.parent and staging.name.startswith(f".{output.name}."):
            shutil.rmtree(staging)
        raise
