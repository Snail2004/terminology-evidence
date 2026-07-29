from __future__ import annotations

import copy
import functools
import hashlib
import json
import re
import stat
import subprocess
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


AUTHORITY_TAG = "contracts-v1.1.0"
AUTHORITY_TAG_OBJECT_OID = "1a8c00d12f100145a276cd8304440ff0a7e8d2a1"
AUTHORITY_COMMIT = "38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed"
REVIEWED_CONTENT_COMMIT = "36e041abcaa0a8a34ab892ae094b0b3d9c3af2f4"
REVIEW_EVIDENCE_COMMIT = "147080746afee4f0059d9e51617097f7e383a8d1"
CONTRACT_ROOT = "terminology_contracts_v1"
CONTRACT_VERSION = "1.1.0"
MANIFEST_SELF_SHA256 = (
    "e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b"
)
GATE_POLICY_SELF_SHA256 = (
    "9f31e4579350e2f74dc1ec01632d8cd49802b5e7ee6f00931b71d430e5d9f4f2"
)
APPROVED_FINAL_ZIP_SHA256 = (
    "2f16fbd2614308be43619a6643f196d74d588ce12e9a4e30dcec3ab669a6f471"
)
FINAL_RELEASE_DIR = "release/v1.1.0-final"
FINAL_ZIP_NAME = "terminology_contracts_v1_1_0_final.zip"
RECEIPT_NAME = "contracts_v1_1_0_authority_receipt_r2.json"
FIXED_ZIP_TIME = (2026, 7, 29, 0, 0, 0)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_OID_RE = re.compile(r"^[0-9a-f]{40}$")


class AuthorityError(ValueError):
    pass


@dataclass(frozen=True)
class TagIdentity:
    tag_object_oid: str
    commit_oid: str
    contract_tree_oid: str


@dataclass(frozen=True)
class ManifestVerification:
    payload: dict[str, Any]
    physical_sha256: str
    self_sha256: str
    files: tuple[dict[str, Any], ...]
    checksums_bytes: bytes


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise AuthorityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise AuthorityError(f"non-finite JSON number is forbidden: {value}")


def strict_json_loads(text: str) -> Any:
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except AuthorityError:
        raise
    except (json.JSONDecodeError, ValueError) as exc:
        raise AuthorityError(f"invalid strict JSON: {exc}") from exc


def read_strict_json(path: Path) -> dict[str, Any]:
    try:
        payload = strict_json_loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise AuthorityError(f"cannot read JSON artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuthorityError(f"JSON artifact must contain an object: {path}")
    return payload


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AuthorityError(f"value cannot be canonicalized: {exc}") from exc


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def calculate_self_sha256(value: Mapping[str, Any]) -> str:
    clone = copy.deepcopy(dict(value))
    integrity = clone.get("integrity")
    if isinstance(integrity, dict):
        integrity.pop("self_sha256", None)
    return canonical_sha256(clone)


def seal_self_hash(value: Mapping[str, Any]) -> dict[str, Any]:
    clone = strict_json_loads(
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    )
    if not isinstance(clone, dict):
        raise AuthorityError("sealed artifact must be an object")
    integrity = clone.setdefault("integrity", {})
    if not isinstance(integrity, dict):
        raise AuthorityError("integrity must be an object")
    integrity["self_sha256"] = calculate_self_sha256(clone)
    return clone


def verify_self_hash(value: Mapping[str, Any], *, label: str) -> str:
    integrity = value.get("integrity")
    if not isinstance(integrity, Mapping):
        raise AuthorityError(f"{label}: integrity object is required")
    declared = integrity.get("self_sha256")
    calculated = calculate_self_sha256(value)
    if declared != calculated:
        raise AuthorityError(
            f"{label}: self_sha256 mismatch: declared {declared!r}, "
            f"calculated {calculated}"
        )
    return calculated


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        raise AuthorityError(f"cannot hash {path}: {exc}") from exc


def require_sha256(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise AuthorityError(f"{field}: lowercase SHA-256 is required")
    return value


def require_git_oid(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not GIT_OID_RE.fullmatch(value):
        raise AuthorityError(f"{field}: lowercase 40-character Git OID is required")
    return value


def safe_relative_path(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise AuthorityError(f"{field}: non-empty relative path is required")
    if "\\" in value or value.startswith(("/", "\\")):
        raise AuthorityError(f"{field}: portable forward-slash path is required")
    if len(value) >= 2 and value[1] == ":":
        raise AuthorityError(f"{field}: drive-qualified path is forbidden")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise AuthorityError(f"{field}: unsafe path segment")
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_checksum(path: Path, artifact: Path) -> None:
    path.write_text(
        f"{sha256_file(artifact)}  {artifact.name}\n",
        encoding="ascii",
        newline="\n",
    )


def read_checksum(path: Path, *, expected_name: str) -> str:
    try:
        text = path.read_text(encoding="ascii")
    except (OSError, UnicodeError) as exc:
        raise AuthorityError(f"cannot read checksum {path}: {exc}") from exc
    lines = text.splitlines()
    if len(lines) != 1:
        raise AuthorityError(f"checksum must contain exactly one line: {path}")
    parts = lines[0].split("  ")
    if len(parts) != 2 or parts[1] != expected_name:
        raise AuthorityError(f"checksum filename mismatch: {path}")
    return require_sha256(parts[0], field=str(path))


def git(repo_root: Path, *args: str, binary: bool = False) -> str | bytes:
    command = ["git", "-C", str(repo_root), *args]
    try:
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        stderr = ""
        if isinstance(exc, subprocess.CalledProcessError):
            stderr = exc.stderr.decode("utf-8", errors="replace").strip()
        raise AuthorityError(
            f"Git command failed: {' '.join(command)}"
            + (f": {stderr}" if stderr else "")
        ) from exc
    if binary:
        return completed.stdout
    return completed.stdout.decode("utf-8", errors="strict").strip()


def resolve_tag_identity(repo_root: Path) -> TagIdentity:
    object_type = git(repo_root, "cat-file", "-t", f"refs/tags/{AUTHORITY_TAG}")
    if object_type != "tag":
        raise AuthorityError(f"{AUTHORITY_TAG}: annotated tag object is required")
    tag_object = git(repo_root, "rev-parse", f"refs/tags/{AUTHORITY_TAG}")
    commit = git(repo_root, "rev-list", "-n", "1", AUTHORITY_TAG)
    tree = git(repo_root, "rev-parse", f"{AUTHORITY_TAG}:{CONTRACT_ROOT}")
    assert isinstance(tag_object, str)
    assert isinstance(commit, str)
    assert isinstance(tree, str)
    if tag_object != AUTHORITY_TAG_OBJECT_OID:
        raise AuthorityError(
            f"authority tag object moved: expected {AUTHORITY_TAG_OBJECT_OID}, "
            f"got {tag_object}"
        )
    if commit != AUTHORITY_COMMIT:
        raise AuthorityError(
            f"authority tag commit moved: expected {AUTHORITY_COMMIT}, got {commit}"
        )
    return TagIdentity(tag_object, commit, tree)


@functools.lru_cache(maxsize=None)
def _git_blob_cached(repo_root_text: str, relative: str, ref: str) -> bytes:
    result = git(Path(repo_root_text), "show", f"{ref}:{CONTRACT_ROOT}/{relative}", binary=True)
    assert isinstance(result, bytes)
    return result


def git_blob(repo_root: Path, relative: str, *, ref: str = AUTHORITY_TAG) -> bytes:
    safe_relative_path(relative, field="Git artifact path")
    return _git_blob_cached(str(repo_root.resolve()), relative, ref)


def _calculate_manifest_self_sha256(payload: Mapping[str, Any]) -> str:
    clone = copy.deepcopy(dict(payload))
    integrity = clone.get("integrity")
    if isinstance(integrity, dict):
        integrity.pop("manifest_sha256", None)
    return canonical_sha256(clone)


def _is_excluded(path: str, prefixes: Iterable[str]) -> bool:
    return any(path == prefix or path.startswith(prefix.rstrip("/") + "/") for prefix in prefixes)


def verify_tagged_manifest(repo_root: Path) -> ManifestVerification:
    manifest_bytes = git_blob(repo_root, "manifest.json")
    try:
        payload = strict_json_loads(manifest_bytes.decode("utf-8"))
    except UnicodeError as exc:
        raise AuthorityError(f"manifest is not UTF-8: {exc}") from exc
    if not isinstance(payload, dict):
        raise AuthorityError("manifest must be an object")
    if payload.get("schema_id") != "TerminologyContractsPackageManifestV1":
        raise AuthorityError("manifest schema_id mismatch")
    if payload.get("package_version") != CONTRACT_VERSION:
        raise AuthorityError("manifest package_version mismatch")
    calculated_self = _calculate_manifest_self_sha256(payload)
    declared_self = payload.get("integrity", {}).get("manifest_sha256")
    if declared_self != calculated_self or calculated_self != MANIFEST_SELF_SHA256:
        raise AuthorityError(
            f"manifest self hash mismatch: declared {declared_self!r}, "
            f"calculated {calculated_self}"
        )
    rows = payload.get("files")
    if not isinstance(rows, list) or not rows:
        raise AuthorityError("manifest files must be a non-empty array")
    verified_rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise AuthorityError(f"manifest.files[{index}] must be an object")
        path = safe_relative_path(row.get("path"), field=f"manifest.files[{index}].path")
        if path in seen:
            raise AuthorityError(f"duplicate manifest path: {path}")
        seen.add(path)
        blob = git_blob(repo_root, path)
        if row.get("size_bytes") != len(blob):
            raise AuthorityError(f"manifest size mismatch: {path}")
        if row.get("sha256") != sha256_bytes(blob):
            raise AuthorityError(f"manifest file hash mismatch: {path}")
        verified_rows.append(row)
    excluded = payload.get("excluded_paths")
    if not isinstance(excluded, list) or not all(isinstance(item, str) for item in excluded):
        raise AuthorityError("manifest excluded_paths must be a string array")
    listed = git(
        repo_root,
        "ls-tree",
        "-r",
        "--name-only",
        AUTHORITY_TAG,
        "--",
        CONTRACT_ROOT,
    )
    assert isinstance(listed, str)
    prefix = CONTRACT_ROOT + "/"
    actual = {
        line.removeprefix(prefix)
        for line in listed.splitlines()
        if line.startswith(prefix)
        and line.removeprefix(prefix) != "manifest.json"
        and not _is_excluded(line.removeprefix(prefix), excluded)
    }
    if actual != seen:
        missing = sorted(seen - actual)
        extra = sorted(actual - seen)
        raise AuthorityError(f"manifest tree mismatch: missing={missing}, extra={extra}")

    checksums = git_blob(repo_root, "CHECKSUMS.sha256")
    expected_lines = [f"{row['sha256']}  {row['path']}" for row in verified_rows]
    expected_lines.append(f"{sha256_bytes(manifest_bytes)}  manifest.json")
    expected_checksums = ("\n".join(expected_lines) + "\n").encode("ascii")
    if checksums != expected_checksums:
        raise AuthorityError("tagged CHECKSUMS.sha256 does not match manifest")
    return ManifestVerification(
        payload=payload,
        physical_sha256=sha256_bytes(manifest_bytes),
        self_sha256=calculated_self,
        files=tuple(verified_rows),
        checksums_bytes=checksums,
    )


def verify_tagged_gate_policy(repo_root: Path) -> dict[str, str]:
    path = "policies/gate_policy_v1.0.0.json"
    data = git_blob(repo_root, path)
    payload = strict_json_loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise AuthorityError("GatePolicy artifact must be an object")
    self_hash = verify_self_hash(payload, label="GatePolicy")
    if self_hash != GATE_POLICY_SELF_SHA256:
        raise AuthorityError("GatePolicy authority self hash mismatch")
    if payload.get("schema_id") != "GatePolicyArtifactV1":
        raise AuthorityError("GatePolicy schema_id mismatch")
    return {
        "path": path,
        "self_sha256": self_hash,
        "physical_sha256": sha256_bytes(data),
    }


def verify_tagged_feature_registry(repo_root: Path) -> dict[str, str]:
    path = "registries/feature_contract_v1.1.0.json"
    data = git_blob(repo_root, path)
    payload = strict_json_loads(data.decode("utf-8"))
    if not isinstance(payload, dict):
        raise AuthorityError("feature registry must be an object")
    if payload.get("registry_id") != "TerminologyFeatureContractRegistryV1_1":
        raise AuthorityError("feature registry id mismatch")
    if payload.get("registry_version") != CONTRACT_VERSION:
        raise AuthorityError("feature registry version mismatch")
    return {
        "path": path,
        "version": CONTRACT_VERSION,
        "canonical_sha256": canonical_sha256(payload),
        "physical_sha256": sha256_bytes(data),
    }


def build_tagged_zip(repo_root: Path, output: Path, *, source_ref: str = AUTHORITY_TAG) -> ManifestVerification:
    if source_ref != AUTHORITY_TAG:
        raise AuthorityError(
            f"final authority package must be built from exact tag {AUTHORITY_TAG}"
        )
    resolve_tag_identity(repo_root)
    manifest = verify_tagged_manifest(repo_root)
    manifest_bytes = git_blob(repo_root, "manifest.json")
    members = [
        (row["path"], git_blob(repo_root, row["path"]))
        for row in manifest.files
    ]
    members.extend(
        [
            ("manifest.json", manifest_bytes),
            ("CHECKSUMS.sha256", manifest.checksums_bytes),
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for relative, data in sorted(members):
            info = zipfile.ZipInfo(f"{CONTRACT_ROOT}/{relative}", FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compresslevel=9)
    verify_zip_against_tag(repo_root, output, manifest=manifest)
    return manifest


def verify_zip_against_tag(
    repo_root: Path,
    zip_path: Path,
    *,
    manifest: ManifestVerification | None = None,
) -> str:
    manifest = manifest or verify_tagged_manifest(repo_root)
    expected = {
        f"{CONTRACT_ROOT}/{row['path']}": git_blob(repo_root, row["path"])
        for row in manifest.files
    }
    expected[f"{CONTRACT_ROOT}/manifest.json"] = git_blob(repo_root, "manifest.json")
    expected[f"{CONTRACT_ROOT}/CHECKSUMS.sha256"] = manifest.checksums_bytes
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)) or set(names) != set(expected):
                raise AuthorityError("final ZIP member set differs from tagged manifest")
            if archive.testzip() is not None:
                raise AuthorityError("final ZIP CRC verification failed")
            for member in members:
                relative = member.filename.removeprefix(CONTRACT_ROOT + "/")
                parts = Path(relative).parts
                mode = member.external_attr >> 16
                if (
                    not member.filename.startswith(CONTRACT_ROOT + "/")
                    or relative.startswith(("/", "\\"))
                    or ".." in parts
                    or stat.S_ISLNK(mode)
                ):
                    raise AuthorityError(f"unsafe final ZIP member: {member.filename}")
                if archive.read(member) != expected[member.filename]:
                    raise AuthorityError(f"final ZIP content differs from tag: {member.filename}")
    except (OSError, zipfile.BadZipFile) as exc:
        raise AuthorityError(f"cannot verify final ZIP {zip_path}: {exc}") from exc
    return sha256_file(zip_path)


def tree_file_hashes(root: Path, *, excluded_names: Iterable[str] = ()) -> dict[str, str]:
    excluded = set(excluded_names)
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in excluded
    }
