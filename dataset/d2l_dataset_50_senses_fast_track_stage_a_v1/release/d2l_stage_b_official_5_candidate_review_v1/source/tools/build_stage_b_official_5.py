from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping

try:
    from .common import (
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_integrity,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from .spec import CREATED_AT_DEFAULT, stable_id
except ImportError:  # pragma: no cover - direct script execution
    from common import (  # type: ignore
        build_deterministic_zip,
        build_file_inventory,
        canonical_json_bytes,
        replace_directory,
        seal_integrity,
        seal_record,
        sha256_bytes,
        sha256_file,
        strict_json_object,
        write_checksums,
        write_json,
        write_jsonl,
    )
    from spec import CREATED_AT_DEFAULT, stable_id  # type: ignore


ARTIFACT_NAME = "d2l_stage_b_official_5_candidate_review_v1"
POLICY_ID = "d2l-stage-b-official-5-candidate-review-v1.0"
STATUS = "READY_FOR_STAGE_B_REVIEW"
OFFICIAL_MANIFEST_SHA256 = (
    "16bd2b9c7a974bdccfb977384fa1a35381e6e810c110f489f31d1606398ce2f5"
)
OFFICIAL_RELEASE_ZIP_SHA256 = (
    "9b6a9ee1272b6403054b61f5399d4391328d1d2d8a964b1102af0a2656bc2738"
)
AUTHORITY_COMMIT = "7fd046cc6a9b8f78fd122549feaefa4b2ab83821"
SOURCE_DOCUMENT_SHA256 = (
    "c22620a96e3fbd97526f13ea9ccf508307d1175ea9bb8d3a5b6dfefb098a3f7f"
)
ALLOWED_LABELS = (
    "ACCEPT",
    "CONDITIONAL",
    "REJECT",
    "SPLIT_REQUIRED",
    "HUMAN_UNJUDGEABLE",
)


def _manifest_self_hash(manifest: Mapping[str, Any]) -> str:
    payload = dict(manifest)
    payload.pop("manifest_sha256", None)
    return sha256_bytes(canonical_json_bytes(payload))


def _blank_review() -> dict[str, Any]:
    return {
        "candidate_gold_label": "",
        "allowed_scope": "",
        "validated_variants": [],
        "rejected_variants": [],
        "reason_codes": [],
        "positive_context_refs": [],
        "vietnamese_evidence_refs": [],
        "review_notes": "",
        "review_status": "",
    }


def _context_projection(context: Mapping[str, Any]) -> dict[str, Any]:
    provenance = context.get("provenance")
    if not isinstance(provenance, Mapping):
        provenance = {}
    synthetic = context.get("binding_kind") == "SYNTHETIC_BOUNDARY_PROBE"
    return {
        "context_id": context["context_id"],
        "context_role": context["context_role"],
        "sense_relation": context["sense_relation"],
        "boundary_only": synthetic or context.get("sense_relation") != "SAME_SENSE",
        "synthetic": synthetic,
        "source_text": context["source_text"],
        "matched_surface": context.get("matched_surface"),
        "content_sha256": context["content_sha256"],
        "chapter_id": provenance.get("chapter_id"),
        "block_id": provenance.get("block_id"),
        "sentence_id": provenance.get("sentence_id"),
        "source_start": provenance.get("source_start"),
        "source_end": provenance.get("source_end"),
        "source_artifact_sha256": provenance.get("source_artifact_sha256"),
    }


def _candidate_case(
    *,
    sense: Mapping[str, Any],
    candidate: Mapping[str, Any],
    contexts: list[Mapping[str, Any]],
    reviewer_slot: str,
) -> dict[str, Any]:
    source_payload = {
        "schema_id": "D2LStageBOfficialCandidateReviewSourceV1",
        "schema_version": "1.0.0",
        "policy_id": POLICY_ID,
        "term_id": sense["term_id"],
        "sense_id": sense["sense_id"],
        "source_term": sense["source_term"],
        "definition_en": sense["definition"],
        "part_of_speech": sense["part_of_speech"],
        "scope_id": sense["scope_id"],
        "candidate_id": candidate["candidate_instance_id"],
        "candidate_target_vi": candidate["candidate_target_vi"],
        "candidate_instance_sha256": candidate["candidate_instance_sha256"],
        "shared_context_set_id": sense["shared_context_set_id"],
        "contexts": [_context_projection(row) for row in contexts],
    }
    return seal_record(
        {
            "schema_id": "D2LStageBOfficialCandidateReviewCaseV1",
            "schema_version": "1.0.0",
            "policy_id": POLICY_ID,
            "case_id": stable_id(
                "stageb_", sense["sense_id"], candidate["candidate_instance_id"], reviewer_slot
            ),
            "reviewer_slot": reviewer_slot,
            "source_payload": source_payload,
            "source_payload_sha256": sha256_bytes(canonical_json_bytes(source_payload)),
            "review": _blank_review(),
            "provider_call_count": 0,
            "final_gold_label": None,
            "final_glossary_decision": None,
        },
        "case_sha256",
    )


def _load_official_input(official_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    manifest = strict_json_object(official_root / "manifest.json")
    if manifest.get("manifest_sha256") != OFFICIAL_MANIFEST_SHA256:
        raise ValueError("official 5 manifest authority hash mismatch")
    if sha256_file(official_root / "manifest.json") == "":
        raise ValueError("official manifest cannot be read")
    senses = [
        json.loads(line)
        for line in (official_root / "materialized_input" / "term_senses_5.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    candidates = [
        json.loads(line)
        for line in (official_root / "materialized_input" / "candidate_instances_15.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    contexts = [
        json.loads(line)
        for line in (official_root / "materialized_input" / "contexts_29.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    if len(senses) != 5 or len(candidates) != 15:
        raise ValueError("official 5 input counts mismatch")
    if any(
        row.get("source_artifact_sha256") not in {None, SOURCE_DOCUMENT_SHA256}
        for row in contexts
        if isinstance(row.get("provenance"), Mapping)
    ):
        raise ValueError("official context source binding mismatch")
    return senses, candidates, contexts


def _build_reviewer_input(
    *, senses: list[Mapping[str, Any]], candidates: list[Mapping[str, Any]], contexts: list[Mapping[str, Any]], reviewer_slot: str
) -> dict[str, Any]:
    contexts_by_sense: dict[str, list[Mapping[str, Any]]] = {}
    candidates_by_sense: dict[str, list[Mapping[str, Any]]] = {}
    for row in contexts:
        contexts_by_sense.setdefault(row["sense_id"], []).append(row)
    for row in candidates:
        candidates_by_sense.setdefault(row["sense_id"], []).append(row)
    cases: list[dict[str, Any]] = []
    for sense in sorted(senses, key=lambda row: row["source_term"].casefold()):
        sense_candidates = sorted(
            candidates_by_sense[sense["sense_id"]],
            key=lambda row: sha256_bytes(
                f"{reviewer_slot}\x1f{row['candidate_instance_id']}".encode("utf-8")
            ),
        )
        sense_contexts = sorted(
            contexts_by_sense[sense["sense_id"]],
            key=lambda row: (row["context_role"], row["context_id"]),
        )
        for candidate in sense_candidates:
            cases.append(
                _candidate_case(
                    sense=sense,
                    candidate=candidate,
                    contexts=sense_contexts,
                    reviewer_slot=reviewer_slot,
                )
            )
    source_input = [
        {"case_id": row["case_id"], "case_sha256": row["case_sha256"]}
        for row in cases
    ]
    return {
        "schema_id": "D2LStageBOfficialCandidateReviewerInputV1",
        "schema_version": "1.0.0",
        "policy_id": POLICY_ID,
        "reviewer_slot": reviewer_slot,
        "authority_commit": AUTHORITY_COMMIT,
        "official_manifest_sha256": OFFICIAL_MANIFEST_SHA256,
        "official_release_zip_sha256": OFFICIAL_RELEASE_ZIP_SHA256,
        "case_count": len(cases),
        "independence_requirement": "DO_NOT_VIEW_OTHER_REVIEWER_OUTPUTS",
        "return_contract": "RETURN_THIS_JSON_WITH_ONLY_REVIEW_FIELDS_FILLED",
        "cases": cases,
        "source_input_sha256": sha256_bytes(canonical_json_bytes(source_input)),
    }


def _write_handoff(
    staging: Path, reviewer_slot: str, payload: Mapping[str, Any]
) -> tuple[str, str]:
    work = staging / ".handoff" / reviewer_slot
    work.mkdir(parents=True)
    write_json(work / "review_input.json", payload)
    (work / "MESSAGE.md").write_text(
        f"Review Stage B official 5 candidates as {reviewer_slot}. Return only the completed "
        "review_input.json file and do not inspect any other reviewer output.\n",
        encoding="utf-8",
        newline="\n",
    )
    (work / "REVIEW_INSTRUCTIONS.md").write_text(
        "# Stage B candidate review instructions\n\n"
        "Review each candidate independently using the supplied sense definition and "
        "D2L contexts. Fill only `review`. Allowed candidate_gold_label values are "
        "ACCEPT, CONDITIONAL, REJECT, SPLIT_REQUIRED, HUMAN_UNJUDGEABLE. Use "
        "positive_context_refs only for same-sense real contexts; synthetic contexts "
        "are boundary-only. Do not use C/E/Global output, intended candidate roles, "
        "or another reviewer's label. Preserve all source fields and hashes. Set "
        "review_status=COMPLETE and return only the completed JSON.\n",
        encoding="utf-8",
        newline="\n",
    )
    write_checksums(work, work / "CHECKSUMS.sha256")
    relative = f"handoff/{reviewer_slot}.zip"
    zip_path = staging / relative
    build_deterministic_zip(work, zip_path)
    return relative, sha256_file(zip_path)


def _write_source_bundle(staging: Path) -> None:
    namespace = Path(__file__).resolve().parents[1]
    for relative in (
        ".gitattributes",
        "README.md",
        "tools/__init__.py",
        "tools/common.py",
        "tools/spec.py",
        "tools/build_stage_b_official_5.py",
        "tools/validate_stage_b_official_5.py",
        "tests/test_stage_b_official_5.py",
    ):
        source = namespace / relative
        if not source.is_file():
            raise ValueError(f"missing source bundle file: {relative}")
        destination = staging / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)


def build_stage_b_official_5(
    *, official_root: Path, output_root: Path, created_at: str
) -> dict[str, Any]:
    official_root = official_root.resolve(strict=True)
    senses, candidates, contexts = _load_official_input(official_root)
    output_root = output_root.resolve()
    output_root.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{ARTIFACT_NAME}.", dir=output_root.parent))
    staging = temporary / ARTIFACT_NAME
    staging.mkdir()
    try:
        write_json(
            staging / "authority_binding.json",
            {
                "schema_id": "D2LStageBAuthorityBindingV1",
                "policy_id": POLICY_ID,
                "authority_commit": AUTHORITY_COMMIT,
                "official_manifest_sha256": OFFICIAL_MANIFEST_SHA256,
                "official_release_zip_sha256": OFFICIAL_RELEASE_ZIP_SHA256,
                "source_document_sha256": SOURCE_DOCUMENT_SHA256,
            },
        )
        write_jsonl(staging / "source_term_senses_5.jsonl", senses)
        write_jsonl(staging / "source_candidates_15.jsonl", candidates)
        write_jsonl(staging / "source_contexts_29.jsonl", contexts)
        handoffs = []
        for reviewer_slot in ("reviewer_1", "reviewer_2"):
            payload = _build_reviewer_input(
                senses=senses,
                candidates=candidates,
                contexts=contexts,
                reviewer_slot=reviewer_slot,
            )
            write_json(staging / f"{reviewer_slot}_input.json", payload)
            relative, digest = _write_handoff(staging, reviewer_slot, payload)
            handoffs.append(
                {
                    "reviewer_slot": reviewer_slot,
                    "case_count": payload["case_count"],
                    "zip_path": relative,
                    "zip_sha256": digest,
                }
            )
        report = seal_integrity(
            {
                "schema_id": "D2LStageBOfficial5ReviewReportV1",
                "schema_version": "1.0.0",
                "policy_id": POLICY_ID,
                "status": STATUS,
                "created_at": created_at,
                "sense_count": 5,
                "candidate_count": 15,
                "reviewer_count": 2,
                "judgments_required": 30,
                "authority_commit": AUTHORITY_COMMIT,
                "official_manifest_sha256": OFFICIAL_MANIFEST_SHA256,
                "provider_call_count": 0,
                "final_gold_label_count": 0,
                "final_glossary_decision": None,
                "handoffs": handoffs,
            }
        )
        write_json(staging / "RELEASE_REPORT.json", report)
        _write_source_bundle(staging)
        shutil.rmtree(staging / ".handoff")
        files = build_file_inventory(staging, {"manifest.json", "CHECKSUMS.sha256"})
        manifest = {
            "schema_id": "D2LStageBOfficial5ReviewManifestV1",
            "schema_version": "1.0.0",
            "artifact_name": ARTIFACT_NAME,
            "policy_id": POLICY_ID,
            "status": STATUS,
            "created_at": created_at,
            "sense_count": 5,
            "candidate_count": 15,
            "judgments_required": 30,
            "provider_call_count": 0,
            "final_gold_label_count": 0,
            "final_glossary_decision": None,
            "official_manifest_sha256": OFFICIAL_MANIFEST_SHA256,
            "files": files,
        }
        manifest["manifest_sha256"] = _manifest_self_hash(manifest)
        write_json(staging / "manifest.json", manifest)
        write_checksums(staging, staging / "CHECKSUMS.sha256")
        try:
            from .validate_stage_b_official_5 import validate_artifact
        except ImportError:  # pragma: no cover
            from validate_stage_b_official_5 import validate_artifact  # type: ignore
        errors = validate_artifact(staging)
        if errors:
            raise ValueError("internal validation failed: " + "; ".join(errors))
        zip_name = f"{ARTIFACT_NAME}_release.zip"
        temporary_zip = temporary / zip_name
        build_deterministic_zip(staging, temporary_zip)
        replace_directory(staging, output_root)
        final_zip = output_root.parent / zip_name
        os.replace(temporary_zip, final_zip)
        zip_sha = sha256_file(final_zip)
        (output_root.parent / f"{zip_name}.sha256").write_text(
            f"{zip_sha} *{zip_name}\n", encoding="ascii", newline="\n"
        )
        return {
            "status": STATUS,
            "artifact_root": str(output_root),
            "manifest_sha256": manifest["manifest_sha256"],
            "release_zip": str(final_zip),
            "release_zip_sha256": zip_sha,
            "handoffs": handoffs,
        }
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def main() -> int:
    namespace = Path(__file__).resolve().parents[1]
    official_default = (
        namespace.parent
        / "d2l_stage_a_pilot_5_senses_official_v1"
        / "release"
        / "d2l_stage_a_pilot_5_senses_official_v1"
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--official-root", type=Path, default=official_default)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--created-at", default=CREATED_AT_DEFAULT)
    args = parser.parse_args()
    result = build_stage_b_official_5(
        official_root=args.official_root,
        output_root=args.output_root,
        created_at=args.created_at,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
