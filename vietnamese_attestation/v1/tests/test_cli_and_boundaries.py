from __future__ import annotations

import ast
import json
from pathlib import Path

from .conftest import judge_payload

from vietnamese_attestation.v1.contracts.output import (
    validate_attestation_package,
)
from vietnamese_attestation.v1.cli.run import (
    main,
)


PRODUCTION_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = PRODUCTION_ROOT / "cli"


def test_offline_cli_writes_a_valid_non_authoritative_package(
    tmp_path: Path,
    frozen_candidate: dict[str, object],
) -> None:
    candidate_path = tmp_path / "candidate.json"
    fixture_path = tmp_path / "fixture.json"
    output_path = tmp_path / "attestation.json"
    run_store_root = tmp_path / "run-store"
    candidate_path.write_text(
        json.dumps(frozen_candidate, ensure_ascii=False),
        encoding="utf-8",
    )
    surface = str(frozen_candidate["candidate_vi"])
    urls = [
        "https://lab-one.edu.vn/ml/inference",
        "https://lab-two.edu.vn/ml/inference",
    ]
    rows = [{"url": url, "title": "Machine learning guide"} for url in urls]
    fixture = {
        "search_provider_id": "fixture_search",
        "search_results_by_query_class": {
            "EXACT_CANDIDATE": rows,
            "CANDIDATE_DOMAIN": rows,
            "CANDIDATE_SOURCE_TERM": rows,
        },
        "documents": {
            urls[0]: {
                "content_type": "text/html",
                "text": (
                    "<p>Trong hoc may, "
                    + surface
                    + " la qua trinh mo hinh tao du doan cho du lieu moi. "
                    "Tai lieu nay trinh bay cach trien khai mo hinh.</p>"
                ),
            },
            urls[1]: {
                "content_type": "text/html",
                "text": (
                    "<p>Khi phuc vu mo hinh da huan luyen, "
                    + surface
                    + " sinh dau ra tu mau dau vao chua tung thay. "
                    "Giao trinh phan tich do tre va tai nguyen tinh toan.</p>"
                ),
            },
        },
        "judge_routes": [
            {
                "route_id": "fixture_judge",
                "model_id": "fixture-model",
                "payloads_by_evidence_id": {"*": judge_payload()},
            }
        ],
        "timestamps": [
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:01Z",
        ],
    }
    fixture_path.write_text(
        json.dumps(fixture, ensure_ascii=False),
        encoding="utf-8",
    )

    assert (
        main(
            [
                "--candidate",
                str(candidate_path),
                "--offline-fixture",
                str(fixture_path),
                "--output",
                str(output_path),
                "--run-store-root",
                str(run_store_root),
            ]
        )
        == 0
    )

    package = validate_attestation_package(
        json.loads(output_path.read_text(encoding="utf-8"))
    )
    assert package["attestation_evidence"]["status"] == "ATTESTED"
    assert package["final_glossary_decision"] is None
    package_copy = (
        run_store_root
        / "runs"
        / package["provenance"]["attestation_execution_id"]
        / "package.json"
    )
    assert package_copy.read_bytes() == output_path.read_bytes()
    assert (
        package["provenance"]["frozen_candidate_sha256"]
        == frozen_candidate["integrity"]["frozen_candidate_sha256"]
    )


def test_vietnamese_attestation_does_not_import_context_substitution() -> None:
    for source in PRODUCTION_ROOT.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=source)
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                modules.append(node.module)
            elif isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
        assert not any(
            module.startswith("context_substitution")
            or module.startswith(
                "pipeline.eval.terminology_evidence.context_substitution"
            )
            for module in modules
        ), source
        assert not any(
            module.startswith("pipeline.eval.terminology_evidence")
            for module in modules
        ), source


def test_concern_directories_remain_split() -> None:
    for directory in [PRODUCTION_ROOT, *PRODUCTION_ROOT.rglob("*")]:
        if not directory.is_dir():
            continue
        direct_modules = [
            source
            for source in directory.glob("*.py")
            if source.name != "__init__.py"
        ]
        assert len(direct_modules) <= 12, directory
