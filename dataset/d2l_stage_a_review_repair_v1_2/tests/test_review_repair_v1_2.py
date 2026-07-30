from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
TOOLS_ROOT = PACKAGE_ROOT / "tools"
sys.path.insert(0, str(TOOLS_ROOT))

from blind_audit import MANDATORY_TERMS, build_blind_pack, select_blind_cases  # noqa: E402
from common import read_csv, read_json, seal, validate_self_hash  # noqa: E402
from consensus import resolve_evidence_aware_consensus  # noqa: E402
from evidence import (  # noqa: E402
    evidence_role,
    project_legacy_evidence_roles,
    validate_explicit_evidence,
)
from policy import load_consensus_policy, load_review_schema  # noqa: E402
from provenance import pending_provenance_template, validate_provenance_group  # noqa: E402
from review_validation import validate_review_record  # noqa: E402
from validate_repair_artifact import validate_artifact  # noqa: E402


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _context(context_id: str, *, boundary: bool = False) -> dict:
    if boundary:
        return {
            "binding_kind": "SYNTHETIC_BOUNDARY_PROBE",
            "context_id": context_id,
            "context_role": "CONTRASTIVE",
            "context_slot": "X1",
            "context_type": "CONTRASTIVE",
            "sense_relation": "CONTRASTIVE",
            "content_sha256": _sha(context_id + "content"),
            "context_sha256": _sha(context_id + "context"),
            "source_text": "Synthetic boundary context.",
            "provenance": {"source_kind": "MODEL_GENERATED_SYNTHETIC"},
            "term_id": "term_1",
            "sense_id": "sense_1",
        }
    return {
        "binding_kind": "EXACT_SURFACE_MATCH_CANDIDATE_NEUTRAL",
        "context_id": context_id,
        "context_role": "PRIMARY",
        "context_slot": "C1",
        "context_type": "C1",
        "sense_relation": "SAME_SENSE",
        "content_sha256": _sha(context_id + "content"),
        "context_sha256": _sha(context_id + "context"),
        "source_text": "A corpus-extracted context for the term.",
        "matched_surface": "term",
        "provenance": {
            "source_kind": "MODEL_CLASSIFICATION",
            "block_id": "block_1",
            "chapter_id": "chapter_1",
            "sentence_id": "sentence_1",
        },
        "term_id": "term_1",
        "sense_id": "sense_1",
    }


def _projected(context: dict) -> dict:
    return {
        "context_id": context["context_id"],
        "context_role": context["context_role"],
        "context_slot": context["context_slot"],
        "context_type_proposal": context["context_type"],
        "sense_relation": context["sense_relation"],
        "content_sha256": context["content_sha256"],
        "context_sha256": context["context_sha256"],
        "source_text": context["source_text"],
        "matched_surface_exact": "term",
        "block_id": (context.get("provenance") or {}).get("block_id", ""),
        "chapter_id": (context.get("provenance") or {}).get("chapter_id", ""),
        "sentence_id": (context.get("provenance") or {}).get("sentence_id", ""),
    }


class EvidenceTests(unittest.TestCase):
    def test_synthetic_context_is_boundary_only_and_rejected_as_positive(self) -> None:
        corpus = _context("ctx_corpus")
        synthetic = _context("ctxx_synthetic", boundary=True)
        self.assertEqual(evidence_role(corpus), "POSITIVE_ELIGIBLE")
        self.assertEqual(evidence_role(synthetic), "BOUNDARY_ONLY")
        review = {
            "term_id": "term_1",
            "sense_id": "sense_1",
            "positive_definition_evidence_ids": [synthetic["context_id"]],
            "positive_pos_evidence_ids": [corpus["context_id"]],
            "boundary_context_ids": [],
        }
        errors = validate_explicit_evidence(
            review,
            {corpus["context_id"]: corpus, synthetic["context_id"]: synthetic},
        )
        self.assertTrue(any("non-positive" in error for error in errors))

    def test_positive_evidence_from_another_sense_is_rejected(self) -> None:
        corpus = _context("ctx_foreign")
        review = {
            "term_id": "term_1",
            "sense_id": "different_sense",
            "positive_definition_evidence_ids": [corpus["context_id"]],
            "positive_pos_evidence_ids": [corpus["context_id"]],
            "boundary_context_ids": [],
        }
        errors = validate_explicit_evidence(review, {corpus["context_id"]: corpus})
        self.assertTrue(any("another sense" in error for error in errors))

    def test_rejected_decision_does_not_require_fabricated_positive_evidence(self) -> None:
        boundary = _context("ctxx_boundary", boundary=True)
        review = {
            "term_id": "term_1",
            "sense_id": "sense_1",
            "definition_status": "REJECTED",
            "part_of_speech_status": "UNCERTAIN",
            "positive_definition_evidence_ids": [],
            "positive_pos_evidence_ids": [],
            "boundary_context_ids": [boundary["context_id"]],
        }
        self.assertEqual(
            validate_explicit_evidence(review, {boundary["context_id"]: boundary}),
            [],
        )

    def test_legacy_projection_never_claims_reviewer_intent(self) -> None:
        corpus = _context("ctx_corpus")
        synthetic = _context("ctxx_synthetic", boundary=True)
        case = {
            "term_id": "term_1",
            "sense_id": "sense_1",
            "case_sha256": _sha("case"),
            "evidence_contexts": {
                "definition": [_projected(corpus)],
                "part_of_speech": [_projected(corpus)],
                "primary": [_projected(corpus)],
                "backup": [],
                "contrastive": [_projected(synthetic)],
            },
        }
        projection = project_legacy_evidence_roles(
            case=case,
            review_row={"evidence_context_ids": "ctx_corpus;ctxx_synthetic"},
            context_authority={"ctx_corpus": corpus, "ctxx_synthetic": synthetic},
            reviewer_slot=1,
        )
        self.assertFalse(projection["projection_is_reviewer_intent"])
        self.assertEqual(projection["proposed_boundary_context_ids"], ["ctxx_synthetic"])
        self.assertIn(
            "BOUNDARY_REFERENCE_IN_LEGACY_UNSEPARATED_FIELD",
            projection["blocker_codes"],
        )


class ProvenanceTests(unittest.TestCase):
    def test_pending_provenance_blocks_and_distinct_complete_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            sidecars = []
            for slot in (1, 2, 3):
                path = root / f"review_{slot}.csv"
                path.write_text(f"slot,{slot}\n", encoding="utf-8")
                paths.append(path)
                sidecars.append(
                    pending_provenance_template(
                        review_path=path,
                        reviewer_slot=slot,
                        batch_id="development_001",
                        source_bundle_sha256=_sha("source"),
                        instruction_sha256=_sha("instruction"),
                    )
                )
            self.assertEqual(
                validate_provenance_group(sidecars, paths)["status"], "BLOCKED"
            )
            complete = []
            for slot, sidecar in enumerate(sidecars, start=1):
                value = dict(sidecar)
                value.update(
                    {
                        "status": "COMPLETE",
                        "reviewer_type": "HUMAN",
                        "reviewer_id": f"reviewer-{slot}",
                        "started_at": "2026-07-29T01:00:00Z",
                        "completed_at": "2026-07-29T02:00:00Z",
                        "run_id": f"run-{slot}",
                        "independence_attestation": True,
                        "other_reviewer_outputs_visible": False,
                    }
                )
                complete.append(seal(value, "provenance_sha256"))
            self.assertEqual(
                validate_provenance_group(complete, paths)["status"], "PASS"
            )
            duplicate = [dict(value) for value in complete]
            duplicate[1]["reviewer_id"] = duplicate[0]["reviewer_id"]
            duplicate[1] = seal(duplicate[1], "provenance_sha256")
            report = validate_provenance_group(duplicate, paths)
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("reviewer_id values must be distinct", report["errors"])

    def test_same_physical_review_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "review.csv"
            path.write_text("same\n", encoding="utf-8")
            sidecar = pending_provenance_template(
                review_path=path,
                reviewer_slot=1,
                batch_id="development_001",
                source_bundle_sha256=_sha("source"),
                instruction_sha256=_sha("instruction"),
            )
            report = validate_provenance_group([sidecar, sidecar, sidecar], [path] * 3)
            self.assertEqual(report["status"], "FAIL")
            self.assertIn("reviewer outputs must be distinct physical files", report["errors"])


class ConsensusTests(unittest.TestCase):
    def _decision(self, definition: str = "same") -> dict:
        return {
            "definition_status": "ACCEPTED",
            "effective_definition_en": definition,
            "part_of_speech_status": "ACCEPTED",
            "effective_part_of_speech": "noun",
        }

    def test_unanimous_legacy_reviews_are_not_auto_finalized(self) -> None:
        evidence = [{"blocker_codes": ["LEGACY_EVIDENCE_ROLE_CONFIRMATION_REQUIRED"]}] * 3
        row = resolve_evidence_aware_consensus(
            term="ordinary term",
            term_id="term",
            sense_id="sense",
            case_sha256=_sha("case"),
            decisions=[self._decision()] * 3,
            evidence_reports=evidence,
            provenance_status="BLOCKED",
        )
        self.assertEqual(row["agreement"], "AGREEMENT_3_OF_3")
        self.assertEqual(row["finalization_status"], "BLOCKED_PENDING_REPAIR_INPUTS")
        self.assertIsNone(row["final_glossary_decision"])
        self.assertTrue(validate_self_hash(row, "record_sha256"))

    def test_majority_and_semantic_cases_require_adjudication_or_split(self) -> None:
        clean = [{"blocker_codes": []}] * 3
        majority = resolve_evidence_aware_consensus(
            term="ordinary term",
            term_id="term",
            sense_id="sense",
            case_sha256=_sha("case"),
            decisions=[self._decision(), self._decision(), self._decision("other")],
            evidence_reports=clean,
            provenance_status="PASS",
        )
        self.assertEqual(majority["finalization_status"], "ADJUDICATION_REQUIRED")
        split = resolve_evidence_aware_consensus(
            term="in place",
            term_id="term",
            sense_id="sense",
            case_sha256=_sha("case"),
            decisions=[self._decision()] * 3,
            evidence_reports=clean,
            provenance_status="PASS",
        )
        self.assertEqual(split["finalization_status"], "SPLIT_REQUIRED")


class BlindAuditTests(unittest.TestCase):
    def test_selection_and_pack_are_development_only_and_hide_model_fields(self) -> None:
        cases = []
        consensus = []
        authority = {}
        names = list(MANDATORY_TERMS) + [f"term {index:02d}" for index in range(37)]
        for index, name in enumerate(names):
            sense_id = f"sense_{index:02d}"
            context_id = f"ctx_{index:02d}"
            context = _context(context_id)
            authority[context_id] = context
            projected = _projected(context)
            cases.append(
                {
                    "case_sha256": _sha(f"case-{index}"),
                    "source_payload_sha256": _sha(f"source-{index}"),
                    "scope_id": "scope",
                    "term_id": f"term_id_{index}",
                    "sense_id": sense_id,
                    "source_term": name,
                    "surfaces": [name],
                    "split": "development",
                    "model_definition_en": "hidden definition",
                    "model_definition_confidence": 0.70 + index / 1000,
                    "model_part_of_speech": "noun",
                    "model_part_of_speech_confidence": 0.71 + index / 1000,
                    "evidence_contexts": {
                        "primary": [projected],
                        "backup": [],
                        "contrastive": [],
                        "definition": [projected],
                        "part_of_speech": [projected],
                    },
                }
            )
            consensus.append(
                {
                    "sense_id": sense_id,
                    "agreement": (
                        "MAJORITY_2_OF_3" if name in MANDATORY_TERMS else "AGREEMENT_3_OF_3"
                    ),
                }
            )
        selected = select_blind_cases(cases, consensus)
        self.assertEqual(len(selected), 13)
        self.assertEqual(
            {case["source_term"] for _, case in selected} & MANDATORY_TERMS,
            MANDATORY_TERMS,
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "blind"
            manifest = build_blind_pack(
                output_root=root,
                selected=selected,
                context_authority=authority,
            )
            self.assertEqual(manifest["sense_count"], 13)
            rows = read_csv(root / "blind_cases.csv")
            self.assertTrue(all(row["split"] == "development" for row in rows))
            self.assertFalse(
                {
                    "model_definition_en",
                    "model_definition_confidence",
                    "model_part_of_speech",
                    "model_part_of_speech_confidence",
                    "context_type_proposal",
                }
                & set(rows[0])
            )
            self.assertTrue(validate_self_hash(read_json(root / "manifest.json"), "manifest_sha256"))


class PolicyTests(unittest.TestCase):
    def test_policy_and_schema_are_consistent_and_do_not_decide_glossary(self) -> None:
        schema = load_review_schema()
        policy = load_consensus_policy()
        self.assertEqual(
            schema["properties"]["policy_id"]["const"],
            policy["review_policy_id"],
        )
        self.assertFalse(policy["confidence_vote_weight"])
        self.assertIsNone(policy["final_glossary_decision"])

    def test_v1_2_review_record_enforces_case_values_and_evidence(self) -> None:
        corpus = _context("ctx_corpus")
        case = {
            "case_sha256": _sha("case"),
            "source_payload_sha256": _sha("source"),
            "term_id": "term_1",
            "sense_id": "sense_1",
            "model_definition_en": "A model definition.",
            "model_part_of_speech": "noun",
        }
        review = {
            "schema_id": "D2LCSTParallelReviewRecordV1_2",
            "policy_id": "d2l_cst_stage_a_evidence_aware_review_v1_2",
            "case_sha256": case["case_sha256"],
            "source_payload_sha256": case["source_payload_sha256"],
            "term_id": case["term_id"],
            "sense_id": case["sense_id"],
            "definition_status": "ACCEPTED",
            "effective_definition_en": case["model_definition_en"],
            "part_of_speech_status": "ACCEPTED",
            "effective_part_of_speech": case["model_part_of_speech"],
            "positive_definition_evidence_ids": [corpus["context_id"]],
            "positive_pos_evidence_ids": [corpus["context_id"]],
            "boundary_context_ids": [],
            "scope_note": "Scoped sense.",
            "confidence": 0.9,
            "rationale": "Corpus evidence supports both decisions.",
            "risk_flags": [],
        }
        self.assertEqual(
            validate_review_record(
                review=review,
                case=case,
                context_authority={corpus["context_id"]: corpus},
            ),
            [],
        )

    def test_committed_repair_artifact_is_structurally_valid(self) -> None:
        report = validate_artifact(PACKAGE_ROOT / "release")
        self.assertEqual(report["status"], "PASS", report["errors"])
        self.assertEqual(
            report["artifact_status"],
            "BLOCKED_PENDING_PROVENANCE_ADJUDICATION_AND_BLIND_AUDIT",
        )


if __name__ == "__main__":
    unittest.main()
