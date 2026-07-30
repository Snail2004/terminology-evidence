from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tools.artifact import build_fasttrack_artifact
else:
    from .artifact import build_fasttrack_artifact


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--glossary-repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--created-at", required=True)
    args = parser.parse_args()
    manifest = build_fasttrack_artifact(
        repo_root=args.repo_root,
        glossary_repository=args.glossary_repo,
        output=args.output,
        created_at=args.created_at,
    )
    print(json.dumps({
        "status": manifest["status"],
        "manifest_sha256": manifest["manifest_sha256"],
        "counts": manifest["counts"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
