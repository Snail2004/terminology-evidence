from __future__ import annotations


ARTIFACT_NAME = "d2l_stage_a_targeted_repair_review_result_5_senses_v1"
POLICY_ID = "d2l-stage-a-targeted-repair-review-result-5-senses-v1.0"
STATUS = "ADJUDICATION_REQUIRED"
CREATED_AT_DEFAULT = "2026-07-29T12:00:00Z"

SOURCE_REVIEW_ARTIFACT_NAME = (
    "d2l_stage_a_targeted_repair_review_pack_5_senses_v1"
)
SOURCE_REVIEW_MANIFEST_SHA256 = (
    "0648e699af2a6d1e0ccb77c35707f688574ed1714a67e3806db65436d73ec015"
)
SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256 = (
    "419f6af277ede673e097e9e640bdafa9f6b046721ffdf4a8406c5a52f93c6b37"
)
SOURCE_REVIEW_ZIP_SHA256 = (
    "36031531b2d0f52d37e06e4860d3e85cd26acda8af0a1997563e0cf78639679c"
)

REVIEW_INPUT_SHA256 = {
    "reviewer_1": "b305abac44eb4ae9c03ecd9dfbd0280c4f4e19964725e4c9a59fddc051514628",
    "reviewer_2": "e621d34e124b6299e8c9091599615095c17706029c5cd9485bc74419b528990f",
    "reviewer_3": "689501d471bd0569e50d8fdd7d7e106f7f8a3a20891f634975bd19455a98d61c",
}
REVIEWER_SLOTS = tuple(REVIEW_INPUT_SHA256)

REVIEW_SOURCE_FIELDS = (
    "schema_id",
    "review_case_id",
    "output_sense_id",
    "parent_sense_id",
    "parent_term_id",
    "source_term",
    "split_label",
    "proposed_definition_en",
    "proposed_part_of_speech",
    "proposed_scope",
    "repair_action",
    "proposal_basis",
    "context_evidence_ids",
    "context_block_ids",
    "candidate_ids",
    "candidate_targets_vi",
)
REVIEW_HUMAN_FIELDS = (
    "definition_decision",
    "corrected_definition_en",
    "part_of_speech_decision",
    "corrected_part_of_speech",
    "scope_decision",
    "corrected_scope",
    "split_decision",
    "context_evidence_decision",
    "candidate_set_decision",
    "review_notes",
    "review_status",
)
REVIEW_CSV_FIELDS = (
    *REVIEW_SOURCE_FIELDS,
    "source_payload_sha256",
    "reviewer_slot",
    *REVIEW_HUMAN_FIELDS,
)
DECISION_FIELDS = (
    "definition_decision",
    "part_of_speech_decision",
    "scope_decision",
    "split_decision",
    "context_evidence_decision",
    "candidate_set_decision",
)

ALLOWED_STANDARD_DECISIONS = {"ACCEPT", "REVISE", "UNJUDGEABLE"}
ALLOWED_SPLIT_DECISIONS = {
    "ACCEPT_SPLIT",
    "NO_SPLIT",
    "REVISE_SPLIT",
    "NOT_APPLICABLE",
}

CONSENSUS_CASES = {
    ("fully-connected layers", "NO_SPLIT"),
    ("in place", "IN_PLACE_MUTATION"),
    ("in place", "ESTABLISHED_CONFIGURATION"),
}
ADJUDICATION_CASES = {
    ("Adam", "NO_SPLIT"): "DEFINITION_DECISION_AND_CORRECTION_DISAGREEMENT",
    (
        "statistical power",
        "NO_SPLIT",
    ): "UNANIMOUS_CANDIDATE_SET_REVISION_WITHOUT_EXACT_REPLACEMENT",
}

ADJUDICATION_OUTPUT_FIELDS = (
    "adjudicated_definition_decision",
    "adjudicated_definition_en",
    "adjudicated_candidate_set_decision",
    "adjudicated_candidate_2_vi",
    "adjudication_notes",
    "adjudication_status",
)

ADJUDICATION_SOURCE_FIELDS = (
    "schema_id",
    "review_case_id",
    "output_sense_id",
    "parent_sense_id",
    "source_term",
    "split_label",
    "issue_type",
    "proposed_definition_en",
    "candidate_ids",
    "candidate_targets_vi",
    "reviewer_1_definition_decision",
    "reviewer_1_corrected_definition_en",
    "reviewer_1_candidate_set_decision",
    "reviewer_1_review_notes",
    "reviewer_2_definition_decision",
    "reviewer_2_corrected_definition_en",
    "reviewer_2_candidate_set_decision",
    "reviewer_2_review_notes",
    "reviewer_3_definition_decision",
    "reviewer_3_corrected_definition_en",
    "reviewer_3_candidate_set_decision",
    "reviewer_3_review_notes",
)
ADJUDICATION_CSV_FIELDS = (
    *ADJUDICATION_SOURCE_FIELDS,
    "source_payload_sha256",
    *ADJUDICATION_OUTPUT_FIELDS,
)
