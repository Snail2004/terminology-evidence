from __future__ import annotations

import hashlib


ARTIFACT_NAME = "d2l_stage_a_targeted_repair_review_complete_5_senses_v1"
POLICY_ID = "d2l-stage-a-targeted-repair-review-complete-5-senses-v1.0"
STATUS = "STAGE_A_REVIEW_COMPLETE"
CREATED_AT_DEFAULT = "2026-07-29T13:00:00Z"

SOURCE_REVIEW_ARTIFACT_NAME = "d2l_stage_a_targeted_repair_review_pack_5_senses_v1"
SOURCE_REVIEW_MANIFEST_SHA256 = (
    "0648e699af2a6d1e0ccb77c35707f688574ed1714a67e3806db65436d73ec015"
)
SOURCE_REVIEW_MANIFEST_PHYSICAL_SHA256 = (
    "419f6af277ede673e097e9e640bdafa9f6b046721ffdf4a8406c5a52f93c6b37"
)
SOURCE_REVIEW_ZIP_SHA256 = (
    "36031531b2d0f52d37e06e4860d3e85cd26acda8af0a1997563e0cf78639679c"
)

SOURCE_RESULT_ARTIFACT_NAME = "d2l_stage_a_targeted_repair_review_result_5_senses_v1"
SOURCE_RESULT_MANIFEST_SHA256 = (
    "acf053cfaeefebb57f4e5fe98f2df91b73f78e2cf698da2a45a4c1271a338445"
)
SOURCE_RESULT_MANIFEST_PHYSICAL_SHA256 = (
    "4f31b59d0c422510309d0d1d8193f1ef1ed949d2d898cc5c5c26d7c5ddc8c463"
)
SOURCE_RESULT_ZIP_SHA256 = (
    "d0a5e02338f19781c4d17ccb25743d59248ca2e64ae20bdc11a0d989f3f4a115"
)

ADJUDICATION_INPUT_SHA256 = (
    "76c276af401c633ad9f341d482513689ec6121d36731f25662e8459d6666c1d5"
)

MAIN_DATASET_AUTHORITY_COMMIT = "7fd046cc6a9b8f78fd122549feaefa4b2ab83821"
MAIN_DATASET_AUTHORITY_ZIP_SHA256 = (
    "9b6a9ee1272b6403054b61f5399d4391328d1d2d8a964b1102af0a2656bc2738"
)
MAIN_DATASET_AUTHORITY_MANIFEST_SHA256 = (
    "16bd2b9c7a974bdccfb977384fa1a35381e6e810c110f489f31d1606398ce2f5"
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
ADJUDICATION_OUTPUT_FIELDS = (
    "adjudicated_definition_decision",
    "adjudicated_definition_en",
    "adjudicated_candidate_set_decision",
    "adjudicated_candidate_2_vi",
    "adjudication_notes",
    "adjudication_status",
)
ADJUDICATION_CSV_FIELDS = (
    *ADJUDICATION_SOURCE_FIELDS,
    "source_payload_sha256",
    *ADJUDICATION_OUTPUT_FIELDS,
)

EXPECTED_CASES = {
    ("fully-connected layers", "NO_SPLIT"),
    ("in place", "IN_PLACE_MUTATION"),
    ("in place", "ESTABLISHED_CONFIGURATION"),
    ("Adam", "NO_SPLIT"),
    ("statistical power", "NO_SPLIT"),
}
ADJUDICATED_CASES = {("Adam", "NO_SPLIT"), ("statistical power", "NO_SPLIT")}

SUMMARY_CSV_FIELDS = (
    "review_case_id",
    "output_sense_id",
    "source_term",
    "split_label",
    "definition_en",
    "part_of_speech",
    "scope",
    "candidate_1_vi",
    "candidate_2_vi",
    "candidate_3_vi",
    "resolution_method",
    "review_status",
)


def stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}{hashlib.sha256(payload).hexdigest()[:24]}"
