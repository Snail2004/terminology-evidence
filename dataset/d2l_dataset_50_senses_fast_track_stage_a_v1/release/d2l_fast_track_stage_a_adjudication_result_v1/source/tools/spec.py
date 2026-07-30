from __future__ import annotations

import hashlib


ARTIFACT_NAME = "d2l_dataset_50_senses_fast_track_stage_a_v1"
POLICY_ID = "d2l-dataset-50-senses-fast-track-stage-a-v1.0"
STATUS = "PARTIAL_BATCH_READY"
CREATED_AT_DEFAULT = "2026-07-29T14:00:00Z"

V3_MANIFEST_SHA256 = "258ebe5d907a0a108a1b80a1ec1aad3c6e265ed1a8edbd5701cc128e273122ce"
V3_MANIFEST_PHYSICAL_SHA256 = (
    "b5f2067427c6b88344109f2c62f8db02ac61b0cef76f193d5285f378ff5f96a8"
)
SOURCE_BATCH_MANIFEST_SHA256 = (
    "bccab90ee3c1c16a6e2075f8fca9fd459d437ac5ef99bb5e902095c4b59ebf00"
)
SOURCE_BATCH_MANIFEST_PHYSICAL_SHA256 = (
    "5cee2eaa69e6f600575fbf7feb174b4bd3a0c9f077086123bbe9f5972e10cf94"
)
OFFICIAL_5_MANIFEST_SHA256 = (
    "16bd2b9c7a974bdccfb977384fa1a35381e6e810c110f489f31d1606398ce2f5"
)
OFFICIAL_5_MANIFEST_PHYSICAL_SHA256 = (
    "3be573ff7bf47bf0ca45862e5310f691574af88c9dcb66c9c9e7d25f2c0a8321"
)
REVIEWED_15_MANIFEST_SHA256 = (
    "e602af02edf1fb877a9541c5e37f939f4f35ded34ac878d773fc83b96ed3fb48"
)
REVIEWED_15_MANIFEST_PHYSICAL_SHA256 = (
    "fa0c2d2e5e1a1dae12c08e637150cbea0404480d492c35b0f51592dd792c5dcd"
)
REPAIRED_5_MANIFEST_SHA256 = (
    "2b731280ea715353461874f3387cb6aed4b5947e9f1b7aba320e1e803b7b36c2"
)
REPAIRED_5_MANIFEST_PHYSICAL_SHA256 = (
    "a1613ec18d59c2cbcbfd0293fbcaa3949a9f4d3377f25e0afc092f4dcb718ea3"
)

MAIN_DATASET_AUTHORITY_COMMIT = "7fd046cc6a9b8f78fd122549feaefa4b2ab83821"
MAIN_DATASET_AUTHORITY_ZIP_SHA256 = (
    "9b6a9ee1272b6403054b61f5399d4391328d1d2d8a964b1102af0a2656bc2738"
)
SOURCE_DOCUMENT_SHA256 = (
    "c22620a96e3fbd97526f13ea9ccf508307d1175ea9bb8d3a5b6dfefb098a3f7f"
)
SOURCE_DOCUMENT_REF = "source://d2l_document_snapshot/document.json"

NEW_SENSE_QUOTAS = {
    "clear": 13,
    "ambiguous": 15,
    "collision_or_multi_target": 16,
}
POOL_STRATUM_COUNTS = {
    "clear": 18,
    "ambiguous": 23,
    "collision_or_multi_target": 19,
}
LANE_COUNTS = {"A_OFFICIAL": 5, "B_REVIEW_READY": 6, "C_REPAIRED": 5, "D_NEW": 44}
RISK_COUNTS_NEW = {
    "R0_CLEAR": 13,
    "R3_AMBIGUOUS": 15,
    "R4_SPLIT_OR_POS_RISK": 16,
}
RISK_BY_STRATUM = {
    "clear": "R0_CLEAR",
    "ambiguous": "R3_AMBIGUOUS",
    "collision_or_multi_target": "R4_SPLIT_OR_POS_RISK",
}
REVIEW_REQUIREMENT_BY_RISK = {
    "R0_CLEAR": "SOURCE_GROUND_PLUS_BLIND_AUDIT",
    "R3_AMBIGUOUS": "TWO_DISTINCT_BLIND_REVIEWERS",
    "R4_SPLIT_OR_POS_RISK": "TWO_DISTINCT_REVIEWERS_PLUS_MANDATORY_ADJUDICATION",
}
REVIEW_SLOTS_BY_RISK = {
    "R0_CLEAR": ("reviewer_1",),
    "R3_AMBIGUOUS": ("reviewer_1", "reviewer_2"),
    "R4_SPLIT_OR_POS_RISK": ("reviewer_1", "reviewer_2", "adjudicator"),
}

REVIEW_FIELDS = (
    "definition_decision",
    "corrected_definition_en",
    "part_of_speech_decision",
    "corrected_part_of_speech",
    "scope_decision",
    "corrected_scope",
    "evidence_decision",
    "invalid_evidence_context_ids",
    "candidate_set_decision",
    "candidate_replacements",
    "sense_status",
    "proposed_split_labels",
    "review_notes",
    "review_status",
)

ALLOWED_STANDARD_DECISIONS = ("ACCEPT", "REVISE", "UNJUDGEABLE")
ALLOWED_SENSE_STATUS = (
    "READY_FOR_CONTRACT_CONSTRUCTION",
    "REVISION_REQUIRED",
    "SPLIT_REQUIRED",
    "UNRESOLVED",
    "QUARANTINED",
)


def stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}{hashlib.sha256(payload).hexdigest()[:24]}"
