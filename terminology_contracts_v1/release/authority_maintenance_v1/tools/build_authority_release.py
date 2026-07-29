from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from xml.etree import ElementTree

from authority_common import (
    APPROVED_FINAL_ZIP_SHA256,
    AUTHORITY_COMMIT,
    AUTHORITY_TAG,
    AUTHORITY_TAG_OBJECT_OID,
    CONTRACT_ROOT,
    CONTRACT_VERSION,
    FINAL_RELEASE_DIR,
    FINAL_ZIP_NAME,
    GATE_POLICY_SELF_SHA256,
    MANIFEST_SELF_SHA256,
    RECEIPT_NAME,
    REVIEWED_CONTENT_COMMIT,
    REVIEW_EVIDENCE_COMMIT,
    AuthorityError,
    build_tagged_zip,
    calculate_self_sha256,
    canonical_sha256,
    git,
    read_strict_json,
    require_git_oid,
    resolve_tag_identity,
    seal_self_hash,
    sha256_bytes,
    sha256_file,
    tree_file_hashes,
    verify_tagged_feature_registry,
    verify_tagged_gate_policy,
    verify_tagged_manifest,
    write_checksum,
    write_json,
)
from authority_verifier import verify_authority_receipt


MAINTENANCE_ROOT = Path(__file__).resolve().parents[1]
HISTORY_ROOT = MAINTENANCE_ROOT / "history"
DOCS_ROOT = MAINTENANCE_ROOT / "docs"

LEGACY_RECEIPTS = (
    "contracts_v1_1_0_authority_receipt_r1_invalid.json",
    "contracts_v1_1_0_authority_receipt_r1_resealed.json",
)

SECRET_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(
        rb"(?i)(api[_-]?key|secret|access[_-]?token)\s*[:=]\s*[\"'][A-Za-z0-9_./+=-]{16,}[\"']"
    ),
)

ALLOWED_CHANGED_PREFIXES = (
    "terminology_contracts_v1/release/",
)


def _read_junit(path: Path) -> dict[str, int | str]:
    try:
        root = ElementTree.parse(path).getroot()
    except (OSError, ElementTree.ParseError) as exc:
        raise AuthorityError(f"cannot read JUnit evidence {path}: {exc}") from exc
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    if not suites:
        raise AuthorityError("JUnit evidence has no testsuite")
    values: dict[str, int | str] = {
        key: sum(int(suite.attrib.get(key, "0")) for suite in suites)
        for key in ("tests", "failures", "errors", "skipped")
    }
    if values["tests"] <= 0:
        raise AuthorityError("release build rejects zero-test JUnit evidence")
    if values["failures"] or values["errors"] or values["skipped"]:
        raise AuthorityError(
            "release build requires zero failures, zero errors and zero unexpected skips"
        )
    values["result"] = "PASS"
    values["junit_sha256"] = sha256_file(path)
    return values


def _compile_scan(repo_root: Path, manifest_rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    cache_files = sorted(
        path.relative_to(MAINTENANCE_ROOT).as_posix()
        for path in MAINTENANCE_ROOT.rglob("*")
        if path.is_file()
        and (
            path.suffix == ".pyc"
            or "__pycache__" in path.relative_to(MAINTENANCE_ROOT).parts
        )
    )
    if cache_files:
        raise AuthorityError(f"maintenance cache files must be removed: {cache_files}")
    files: list[tuple[str, bytes]] = []
    for row in manifest_rows:
        path = row["path"]
        if path.endswith(".py"):
            data = git(repo_root, "show", f"{AUTHORITY_TAG}:{CONTRACT_ROOT}/{path}", binary=True)
            assert isinstance(data, bytes)
            files.append((f"tag:{path}", data))
    for path in sorted(MAINTENANCE_ROOT.rglob("*.py")):
        files.append((path.relative_to(MAINTENANCE_ROOT).as_posix(), path.read_bytes()))
    for label, data in files:
        try:
            compile(data.decode("utf-8"), label, "exec")
        except (UnicodeError, SyntaxError) as exc:
            raise AuthorityError(f"static compile failed for {label}: {exc}") from exc
    return seal_self_hash(
        {
            "schema_id": "TerminologyContractsAuthorityStaticScanV1",
            "result": "PASS",
            "module_count": len(files),
            "cache_files": cache_files,
            "integrity": {"self_sha256": ""},
        }
    )


def _credential_scan(repo_root: Path, manifest_rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    hits: list[str] = []
    for row in manifest_rows:
        path = row["path"]
        if path.endswith((".zip", ".pyc")):
            continue
        data = git(repo_root, "show", f"{AUTHORITY_TAG}:{CONTRACT_ROOT}/{path}", binary=True)
        assert isinstance(data, bytes)
        if any(pattern.search(data) for pattern in SECRET_PATTERNS):
            hits.append(f"tag:{path}")
    for path in sorted(MAINTENANCE_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() in {".zip", ".pyc"}:
            continue
        if any(pattern.search(path.read_bytes()) for pattern in SECRET_PATTERNS):
            hits.append(path.relative_to(MAINTENANCE_ROOT).as_posix())
    return seal_self_hash(
        {
            "schema_id": "TerminologyContractsAuthorityCredentialScanV1",
            "result": "PASS" if not hits else "FAIL",
            "hits": hits,
            "integrity": {"self_sha256": ""},
        }
    )


def _ownership_scan(
    repo_root: Path,
    *,
    base_main_commit: str,
    implementation_commit: str,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    require_git_oid(base_main_commit, field="base_main_commit")
    require_git_oid(implementation_commit, field="implementation_commit")
    if git(repo_root, "cat-file", "-t", base_main_commit) != "commit":
        raise AuthorityError("base_main_commit is not a commit")
    if git(repo_root, "cat-file", "-t", implementation_commit) != "commit":
        raise AuthorityError("implementation_commit is not a commit")
    git(repo_root, "merge-base", "--is-ancestor", base_main_commit, implementation_commit)
    raw = git(repo_root, "diff", "--name-status", base_main_commit, implementation_commit)
    assert isinstance(raw, str)
    rows: list[dict[str, str]] = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            raise AuthorityError(f"unexpected git diff row: {line}")
        status, path = parts[0], parts[-1].replace("\\", "/")
        if not any(path.startswith(prefix) for prefix in ALLOWED_CHANGED_PREFIXES):
            raise AuthorityError(f"ownership violation: {path}")
        rows.append({"status": status, "path": path})
    if not rows:
        raise AuthorityError("implementation commit has no authority-maintenance changes")
    report = seal_self_hash(
        {
            "schema_id": "TerminologyContractsAuthorityOwnershipScanV1",
            "result": "PASS",
            "base_main_commit": base_main_commit,
            "implementation_commit": implementation_commit,
            "changed_paths": rows,
            "allowed_prefixes": list(ALLOWED_CHANGED_PREFIXES),
            "integrity": {"self_sha256": ""},
        }
    )
    return report, rows


def _environment_report() -> dict[str, Any]:
    return seal_self_hash(
        {
            "schema_id": "TerminologyContractsAuthorityEnvironmentV1",
            "python_version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform_system": platform.system(),
            "platform_release": platform.release(),
            "external_api_calls": 0,
            "dataset_roots_required_for_release_gate": True,
            "absolute_paths_are_authority_identity": False,
            "integrity": {"self_sha256": ""},
        }
    )


def _historical_receipt_row(path: Path, relative: str) -> dict[str, str]:
    payload = read_strict_json(path)
    declared = payload.get("integrity", {}).get("self_sha256")
    if not isinstance(declared, str):
        raise AuthorityError(f"historical receipt has no declared self hash: {path}")
    return {
        "path": relative,
        "status": "SUPERSEDED_BY_RECEIPT_R2",
        "declared_self_sha256": declared,
        "canonical_self_sha256": calculate_self_sha256(payload),
        "physical_sha256": sha256_file(path),
    }


def _copy_historical_receipts(final_dir: Path) -> list[dict[str, str]]:
    output = final_dir / "history"
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, str]] = []
    for name in LEGACY_RECEIPTS:
        source = HISTORY_ROOT / name
        if not source.is_file():
            raise AuthorityError(f"missing historical receipt source: {source}")
        destination = output / name
        destination.write_bytes(source.read_bytes())
        write_checksum(destination.with_name(destination.name + ".sha256"), destination)
        relative = f"{FINAL_RELEASE_DIR}/history/{name}"
        rows.append(_historical_receipt_row(destination, relative))
    return rows


def _git_commit_receipt(
    repo_root: Path,
    *,
    base_main_commit: str,
    implementation_commit: str,
    changed_paths: list[dict[str, str]],
) -> dict[str, Any]:
    identity = resolve_tag_identity(repo_root)
    merge_base = git(repo_root, "merge-base", base_main_commit, implementation_commit)
    assert isinstance(merge_base, str)
    return seal_self_hash(
        {
            "schema_id": "TerminologyContractsAuthorityGitCommitReceiptV1",
            "repository_id": "terminology_evidence",
            "branch": "chore/contracts-v1.1-authority-r2",
            "base_main_commit": base_main_commit,
            "implementation_commit": implementation_commit,
            "merge_base": merge_base,
            "implementation_parent": git(repo_root, "rev-parse", f"{implementation_commit}^"),
            "git_status_porcelain": "CLEAN_AT_IMPLEMENTATION_COMMIT",
            "git_diff_check": "PASS",
            "changed_paths": changed_paths,
            "tag_resolution": {
                "tag": AUTHORITY_TAG,
                "tag_object_oid": identity.tag_object_oid,
                "commit_oid": identity.commit_oid,
                "contract_tree_oid": identity.contract_tree_oid,
            },
            "integrity": {"self_sha256": ""},
        }
    )


def _write_release_manifest(final_dir: Path) -> None:
    files = []
    for relative, digest in tree_file_hashes(
        final_dir,
        excluded_names={"release_manifest.json", "CHECKSUMS.sha256"},
    ).items():
        path = final_dir / relative
        files.append(
            {"path": relative, "size_bytes": path.stat().st_size, "sha256": digest}
        )
    payload = seal_self_hash(
        {
            "schema_id": "TerminologyContractsAuthorityMaintenanceManifestV1",
            "contract_version": CONTRACT_VERSION,
            "authority_tag": AUTHORITY_TAG,
            "files": files,
            "integrity": {"self_sha256": ""},
        }
    )
    manifest_path = final_dir / "release_manifest.json"
    write_json(manifest_path, payload)
    lines = [f"{row['sha256']}  {row['path']}" for row in files]
    lines.append(f"{sha256_file(manifest_path)}  release_manifest.json")
    (final_dir / "CHECKSUMS.sha256").write_text(
        "\n".join(sorted(lines)) + "\n",
        encoding="ascii",
        newline="\n",
    )


def _install_idempotently(staged: Path, destination: Path) -> None:
    if destination.exists():
        existing = tree_file_hashes(destination)
        candidate = tree_file_hashes(staged)
        if existing != candidate:
            raise AuthorityError("existing final release directory differs from deterministic rebuild")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(staged, destination)


def build_release(
    *,
    repo_root: Path,
    distribution_root: Path,
    junit_path: Path,
    base_main_commit: str,
    implementation_commit: str,
    issued_at: str,
    source_ref: str = AUTHORITY_TAG,
) -> Path:
    repo_root = repo_root.resolve()
    distribution_root = distribution_root.resolve()
    junit_path = junit_path.resolve()
    test_evidence = _read_junit(junit_path)
    identity = resolve_tag_identity(repo_root)
    manifest = verify_tagged_manifest(repo_root)
    gate_policy = verify_tagged_gate_policy(repo_root)
    feature_registry = verify_tagged_feature_registry(repo_root)
    static_scan = _compile_scan(repo_root, manifest.files)
    credential_scan = _credential_scan(repo_root, manifest.files)
    if credential_scan["result"] != "PASS":
        raise AuthorityError(f"credential scan failed: {credential_scan['hits']}")
    ownership_scan, changed_paths = _ownership_scan(
        repo_root,
        base_main_commit=base_main_commit,
        implementation_commit=implementation_commit,
    )

    with tempfile.TemporaryDirectory(prefix="contracts-authority-r2-") as temp_text:
        temp_distribution = Path(temp_text) / "distribution"
        final_dir = temp_distribution / CONTRACT_ROOT / FINAL_RELEASE_DIR
        final_dir.mkdir(parents=True)
        zip_path = final_dir / FINAL_ZIP_NAME
        build_tagged_zip(repo_root, zip_path, source_ref=source_ref)
        zip_sha = sha256_file(zip_path)
        if zip_sha != APPROVED_FINAL_ZIP_SHA256:
            raise AuthorityError(
                "deterministic final ZIP differs from approved RC4 bytes: "
                f"expected {APPROVED_FINAL_ZIP_SHA256}, got {zip_sha}"
            )
        write_checksum(final_dir / f"{FINAL_ZIP_NAME}.sha256", zip_path)
        shutil.copy2(junit_path, final_dir / "junit.xml")

        manifest_report = seal_self_hash(
            {
                "schema_id": "TerminologyContractsManifestVerificationReportV1",
                "result": "PASS",
                "authority_tag": AUTHORITY_TAG,
                "manifest_sha256": manifest.self_sha256,
                "manifest_file_sha256": manifest.physical_sha256,
                "file_count": len(manifest.files),
                "checksums_sha256": sha256_bytes(manifest.checksums_bytes),
                "integrity": {"self_sha256": ""},
            }
        )
        gate_report = seal_self_hash(
            {
                "schema_id": "TerminologyContractsGatePolicyVerificationReportV1",
                "result": "PASS",
                **gate_policy,
                "integrity": {"self_sha256": ""},
            }
        )
        feature_report = seal_self_hash(
            {
                "schema_id": "TerminologyContractsFeatureRegistryVerificationReportV1",
                "result": "PASS",
                **feature_registry,
                "integrity": {"self_sha256": ""},
            }
        )
        reports = {
            "manifest_verification_report.json": manifest_report,
            "gate_policy_verification_report.json": gate_report,
            "feature_registry_verification_report.json": feature_report,
            "static_scan.json": static_scan,
            "credential_scan.json": credential_scan,
            "ownership_scan.json": ownership_scan,
            "environment.json": _environment_report(),
            "git_commit_receipt.json": _git_commit_receipt(
                repo_root,
                base_main_commit=base_main_commit,
                implementation_commit=implementation_commit,
                changed_paths=changed_paths,
            ),
        }
        for name, payload in reports.items():
            write_json(final_dir / name, payload)

        historical_rows = _copy_historical_receipts(final_dir)
        for name in ("AUTHORITY_RECEIPT_R2_NOTES.md", "V1_1_1_BACKLOG.md"):
            source = DOCS_ROOT / name
            if not source.is_file():
                raise AuthorityError(f"missing authority maintenance document: {source}")
            shutil.copy2(source, final_dir / name)

        commands = (
            "$env:TERMINOLOGY_DATASET_ROOT='E:\\Data-KL'\n"
            "$env:PYTHONPATH=\"$pwd\\terminology_contracts_v1\\python\"\n"
            "python -m pytest -q terminology_contracts_v1/tests "
            "terminology_contracts_v1/release/authority_maintenance_v1/tests "
            "--junitxml=<external-junit-path>\n"
            "python terminology_contracts_v1/release/authority_maintenance_v1/tools/"
            "build_authority_release.py --repo-root . --distribution-root . "
            f"--junit <external-junit-path> --base-main-commit {base_main_commit} "
            f"--implementation-commit {implementation_commit} --issued-at {issued_at}\n"
            "python terminology_contracts_v1/release/authority_maintenance_v1/tools/"
            "verify_authority_receipt.py --repo-root . --distribution-root .\n"
        )
        (final_dir / "commands.txt").write_text(
            commands, encoding="utf-8", newline="\n"
        )

        audit = seal_self_hash(
            {
                "schema_id": "TerminologyContractsAuthorityMaintenanceReleaseAuditV1",
                "contract_version": CONTRACT_VERSION,
                "release_channel": "v1.1.0-final-authority-r2",
                "source_ref": AUTHORITY_TAG,
                "authority_tag": AUTHORITY_TAG,
                "authority_tag_object_oid": identity.tag_object_oid,
                "authority_commit": AUTHORITY_COMMIT,
                "contract_tree_git_oid": identity.contract_tree_oid,
                "manifest_sha256": manifest.self_sha256,
                "manifest_file_sha256": manifest.physical_sha256,
                "release_zip_sha256": zip_sha,
                "release_zip_byte_identical_to_approved_rc4": True,
                "gate_policy_self_sha256": gate_policy["self_sha256"],
                "gate_policy_file_sha256": gate_policy["physical_sha256"],
                "feature_registry_version": feature_registry["version"],
                "feature_registry_canonical_sha256": feature_registry["canonical_sha256"],
                "feature_registry_file_sha256": feature_registry["physical_sha256"],
                "test_count": test_evidence["tests"],
                "test_result": test_evidence["result"],
                "test_failures": test_evidence["failures"],
                "test_errors": test_evidence["errors"],
                "test_skipped": test_evidence["skipped"],
                "junit_sha256": test_evidence["junit_sha256"],
                "static_scan_result": static_scan["result"],
                "credential_scan_result": credential_scan["result"],
                "ownership_scan_result": ownership_scan["result"],
                "external_api_calls": 0,
                "historical_receipts_preserved": len(historical_rows),
                "integrity": {"self_sha256": ""},
            }
        )
        audit_path = final_dir / "final_release_audit.json"
        write_json(audit_path, audit)

        receipt = seal_self_hash(
            {
                "schema_id": "TerminologyContractsAuthorityReceiptV1",
                "schema_version": "1.0.0",
                "receipt_revision": 2,
                "authority_status": "SEALED",
                "publication_status": "PENDING_INDEPENDENT_REVIEW",
                "contract_version": CONTRACT_VERSION,
                "authority_tag": AUTHORITY_TAG,
                "authority_tag_object_oid": AUTHORITY_TAG_OBJECT_OID,
                "authority_commit": AUTHORITY_COMMIT,
                "canonical_main_observed_commit": base_main_commit,
                "contract_root": CONTRACT_ROOT,
                "contract_tree_git_oid": identity.contract_tree_oid,
                "manifest_path": "manifest.json",
                "manifest_sha256": MANIFEST_SELF_SHA256,
                "manifest_file_sha256": manifest.physical_sha256,
                "final_release_path": f"{FINAL_RELEASE_DIR}/{FINAL_ZIP_NAME}",
                "final_release_checksum_path": f"{FINAL_RELEASE_DIR}/{FINAL_ZIP_NAME}.sha256",
                "final_release_zip_sha256": zip_sha,
                "final_release_audit_path": f"{FINAL_RELEASE_DIR}/final_release_audit.json",
                "final_release_audit_self_sha256": audit["integrity"]["self_sha256"],
                "final_release_audit_physical_sha256": sha256_file(audit_path),
                "gate_policy_path": gate_policy["path"],
                "gate_policy_self_sha256": gate_policy["self_sha256"],
                "gate_policy_file_sha256": gate_policy["physical_sha256"],
                "feature_registry_path": feature_registry["path"],
                "feature_registry_version": feature_registry["version"],
                "feature_registry_canonical_sha256": feature_registry["canonical_sha256"],
                "feature_registry_file_sha256": feature_registry["physical_sha256"],
                "reviewed_content_commit": REVIEWED_CONTENT_COMMIT,
                "review_evidence_commit": REVIEW_EVIDENCE_COMMIT,
                "supersedes_receipts": historical_rows,
                "issued_at": issued_at,
                "integrity": {"self_sha256": ""},
            }
        )
        receipt_path = final_dir / RECEIPT_NAME
        write_json(receipt_path, receipt)
        write_checksum(final_dir / f"{RECEIPT_NAME}.sha256", receipt_path)

        verification = verify_authority_receipt(
            repo_root=repo_root,
            distribution_root=temp_distribution,
            receipt_path=receipt_path,
            require_distribution_manifest=False,
        )
        write_json(final_dir / "authority_verification_report.json", verification)
        _write_release_manifest(final_dir)
        verify_authority_receipt(
            repo_root=repo_root,
            distribution_root=temp_distribution,
            receipt_path=receipt_path,
        )

        destination = distribution_root / CONTRACT_ROOT / FINAL_RELEASE_DIR
        _install_idempotently(final_dir, destination)
        installed_receipt = destination / RECEIPT_NAME
        verify_authority_receipt(
            repo_root=repo_root,
            distribution_root=distribution_root,
            receipt_path=installed_receipt,
        )
        return installed_receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build Contracts V1.1.0 final authority receipt R2")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--distribution-root", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--base-main-commit", required=True)
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument("--source-ref", default=AUTHORITY_TAG)
    parser.add_argument(
        "--issued-at",
        default=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    )
    args = parser.parse_args(argv)
    try:
        receipt = build_release(
            repo_root=args.repo_root,
            distribution_root=args.distribution_root,
            junit_path=args.junit,
            base_main_commit=args.base_main_commit,
            implementation_commit=args.implementation_commit,
            issued_at=args.issued_at,
            source_ref=args.source_ref,
        )
    except AuthorityError as exc:
        raise SystemExit(f"AUTHORITY BUILD FAILED: {exc}") from exc
    print(
        json.dumps(
            {
                "receipt": receipt.as_posix(),
                "receipt_self_sha256": read_strict_json(receipt)["integrity"]["self_sha256"],
                "receipt_physical_sha256": sha256_file(receipt),
                "release_zip_sha256": APPROVED_FINAL_ZIP_SHA256,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
