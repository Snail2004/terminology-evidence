from __future__ import annotations

import argparse
import json
from pathlib import Path

from artifact import build_artifact, validate_artifact
from common import deterministic_zip, sha256_file, write_text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack-root", type=Path, required=True)
    parser.add_argument("--anchor-reference", type=Path, required=True)
    parser.add_argument("--anchored-consensus", type=Path, required=True)
    parser.add_argument("--review-file", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    if len(args.review_file) != 3:
        parser.error("--review-file must be supplied exactly three times")

    summary = build_artifact(
        pack_root=args.pack_root,
        review_paths=args.review_file,
        anchor_reference_path=args.anchor_reference,
        anchored_consensus_path=args.anchored_consensus,
        output_root=args.output_root,
    )
    report = validate_artifact(args.output_root)
    if report["status"] != "PASS":
        raise ValueError(json.dumps(report, ensure_ascii=False))
    archive = args.output_root.with_suffix(".zip")
    deterministic_zip(args.output_root, archive)
    write_text(
        archive.with_suffix(".zip.sha256"),
        f"{sha256_file(archive)}  {archive.name}",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "artifact_status": summary["artifact_status"],
                "output_root": str(args.output_root),
                "zip_sha256": sha256_file(archive),
                "blind_case_count": summary["blind_case_count"],
                "adjudication_case_count": summary["adjudication_case_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
