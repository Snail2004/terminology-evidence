from __future__ import annotations

import hashlib
from typing import Any


ARTIFACT_NAME = "d2l_stage_a_targeted_repair_review_pack_5_senses_v1"
POLICY_ID = "d2l-stage-a-targeted-repair-review-5-senses-v1.0"
STATUS = "READY_FOR_TARGETED_HUMAN_REVIEW"
CREATED_AT_DEFAULT = "2026-07-29T10:00:00Z"

V3_MANIFEST_SHA256 = "258ebe5d907a0a108a1b80a1ec1aad3c6e265ed1a8edbd5701cc128e273122ce"
V3_MANIFEST_PHYSICAL_SHA256 = (
    "b5f2067427c6b88344109f2c62f8db02ac61b0cef76f193d5285f378ff5f96a8"
)
REVIEWED_MANIFEST_SHA256 = (
    "e602af02edf1fb877a9541c5e37f939f4f35ded34ac878d773fc83b96ed3fb48"
)
REVIEWED_MANIFEST_PHYSICAL_SHA256 = (
    "fa0c2d2e5e1a1dae12c08e637150cbea0404480d492c35b0f51592dd792c5dcd"
)
OFFICIAL_11_MANIFEST_SHA256 = (
    "5a3c3d9631361c2798e972c837d2af1cbf234e4264fdeb06fb8cd7bcab7ffd0a"
)
OFFICIAL_11_MANIFEST_PHYSICAL_SHA256 = (
    "797fa0f0646e385caf9760b3556376221f23f67cad39393c35dbcc5d248a4011"
)
SOURCE_DOCUMENT_SHA256 = (
    "c22620a96e3fbd97526f13ea9ccf508307d1175ea9bb8d3a5b6dfefb098a3f7f"
)
SOURCE_DOCUMENT_REF = "source://d2l_document_snapshot/document.json"

MAIN_DATASET_AUTHORITY_COMMIT = "7fd046cc6a9b8f78fd122549feaefa4b2ab83821"
MAIN_DATASET_AUTHORITY_ZIP_SHA256 = (
    "9b6a9ee1272b6403054b61f5399d4391328d1d2d8a964b1102af0a2656bc2738"
)
MAIN_DATASET_AUTHORITY_MANIFEST_SHA256 = (
    "16bd2b9c7a974bdccfb977384fa1a35381e6e810c110f489f31d1606398ce2f5"
)
MAIN_DATASET_AUTHORITY_PIN_SHA256 = (
    "7ae7c94176e32b419cfac4bb36704d633c550068e34d00b80389ebb20f035b05"
)
MAIN_DATASET_AUTHORITY_PIN_PHYSICAL_SHA256 = (
    "d55d1919050b9cab7c2bd5e08f0200b20d1bdd2cabfd5dcbcc241733fe9771da0"
)

PARENT_IN_PLACE = "d2lce_2684090fd4500122fec2a334"
PARENT_STATISTICAL_POWER = "d2lce_2b76c0f26436945cdf880aed"
PARENT_ADAM = "d2lce_7ef8ed3f93210606a27312a4"
PARENT_FULLY_CONNECTED = "d2lce_98b37a7bcb47cd2ef2e5f296"


def stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}{hashlib.sha256(payload).hexdigest()[:24]}"


IN_PLACE_MUTATION_ID = stable_id(
    "d2lce_", PARENT_IN_PLACE, "IN_PLACE_MUTATION", "v1"
)
IN_PLACE_ESTABLISHED_ID = stable_id(
    "d2lce_", PARENT_IN_PLACE, "ESTABLISHED_CONFIGURATION", "v1"
)


CASE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "case_key": "in_place_mutation",
        "source_term": "in place",
        "parent_sense_id": PARENT_IN_PLACE,
        "output_sense_id": IN_PLACE_MUTATION_ID,
        "split_label": "IN_PLACE_MUTATION",
        "proposed_definition_en": (
            "Performed directly on an existing object or memory location rather "
            "than by creating a separate replacement."
        ),
        "proposed_part_of_speech": "adverb",
        "proposed_scope": "ARRAY_OR_PARAMETER_UPDATE_ON_EXISTING_STORAGE",
        "repair_action": "SPLIT_PARENT_AND_REVIEW_MUTATION_SENSE",
        "proposal_basis": "CORPUS_EVIDENCE_AND_PRIOR_SPLIT_ADJUDICATION",
        "block_ids": (
            "d2l_preliminaries_ndarray_b091",
            "d2l_preliminaries_ndarray_b092",
            "d2l_preliminaries_ndarray_b099",
            "d2l_preliminaries_ndarray_b104",
            "d2l_computational_performance_hybridize_b064",
        ),
        "new_candidate_targets": (
            "tại chỗ",
            "cập nhật tại chỗ",
            "trực tiếp trên đối tượng hiện có",
        ),
        "source_candidate_ids": (),
    },
    {
        "case_key": "in_place_established",
        "source_term": "in place",
        "parent_sense_id": PARENT_IN_PLACE,
        "output_sense_id": IN_PLACE_ESTABLISHED_ID,
        "split_label": "ESTABLISHED_CONFIGURATION",
        "proposed_definition_en": (
            "Present, established, or arranged so that the relevant system, "
            "component, or process is ready or operating."
        ),
        "proposed_part_of_speech": "adverb",
        "proposed_scope": "SYSTEM_COMPONENT_OR_PROCESS_READINESS",
        "repair_action": "SPLIT_PARENT_AND_REVIEW_ESTABLISHED_SENSE",
        "proposal_basis": "CORPUS_EVIDENCE_AND_PRIOR_SPLIT_ADJUDICATION",
        "block_ids": (
            "d2l_introduction_index_b079",
            "d2l_linear_networks_linear_regression_scratch_b047",
            "d2l_linear_networks_linear_regression_concise_b057",
            "d2l_multilayer_perceptrons_mlp_b020",
            "d2l_optimization_adam_b013",
        ),
        "new_candidate_targets": (
            "đã được thiết lập",
            "đã sẵn sàng",
            "đang được áp dụng",
        ),
        "source_candidate_ids": (),
    },
    {
        "case_key": "adam",
        "source_term": "Adam",
        "parent_sense_id": PARENT_ADAM,
        "output_sense_id": PARENT_ADAM,
        "split_label": "NO_SPLIT",
        "proposed_definition_en": "An optimization algorithm used to train models.",
        "proposed_part_of_speech": "proper_noun",
        "proposed_scope": "DEEP_LEARNING_OPTIMIZATION_ALGORITHM",
        "repair_action": "REVIEW_TRIMMED_DEFINITION_WITH_NEW_PRIMARY_EVIDENCE",
        "proposal_basis": "CORPUS_EVIDENCE_AND_PRIOR_ADJUDICATION",
        "block_ids": (
            "d2l_optimization_index_b002",
            "d2l_optimization_adam_b004",
            "d2l_optimization_adam_b006",
            "d2l_computer_vision_image_augmentation_b055",
            "d2l_multilayer_perceptrons_kaggle_house_price_b053",
        ),
        "new_candidate_targets": (),
        "source_candidate_ids": (
            "candidate_eb4b9982b22d45554720135e",
            "candidate_d2ab7fc22d0620dfdeb0a667",
            "candidate_5b40ab20a731994cf4619c72",
        ),
    },
    {
        "case_key": "statistical_power",
        "source_term": "statistical power",
        "parent_sense_id": PARENT_STATISTICAL_POWER,
        "output_sense_id": PARENT_STATISTICAL_POWER,
        "split_label": "NO_SPLIT",
        "proposed_definition_en": (
            "The probability that a statistical test rejects the null hypothesis "
            "when the null hypothesis is false."
        ),
        "proposed_part_of_speech": "noun_phrase",
        "proposed_scope": "STATISTICAL_HYPOTHESIS_TESTING",
        "repair_action": "REPLACE_WRONG_SENSE_CONTEXT_WITH_PRIMARY_EVIDENCE",
        "proposal_basis": "DIRECT_CORPUS_DEFINITION_AND_FORMULA",
        "block_ids": (
            "d2l_appendix_mathematics_for_deep_learning_statistics_b064",
            "d2l_appendix_mathematics_for_deep_learning_statistics_b065",
            "d2l_appendix_mathematics_for_deep_learning_statistics_b066",
            "d2l_appendix_mathematics_for_deep_learning_statistics_b067",
            "d2l_appendix_mathematics_for_deep_learning_statistics_b068",
        ),
        "new_candidate_targets": (),
        "source_candidate_ids": (
            "candidate_71daf6039ab2e893cedccaf3",
            "candidate_8a4dcddfb53356985673d7d4",
            "candidate_494d3d67a89723a07ce74292",
        ),
    },
    {
        "case_key": "fully_connected_layers",
        "source_term": "fully-connected layers",
        "parent_sense_id": PARENT_FULLY_CONNECTED,
        "output_sense_id": PARENT_FULLY_CONNECTED,
        "split_label": "NO_SPLIT",
        "proposed_definition_en": (
            "Layers in which each output unit is connected to all input units "
            "from the previous layer."
        ),
        "proposed_part_of_speech": "noun_phrase",
        "proposed_scope": "NEURAL_NETWORK_LAYER_CONNECTIVITY",
        "repair_action": "ADD_DIRECT_SAME_SENSE_DEFINITION_EVIDENCE",
        "proposal_basis": "DIRECT_CORPUS_CONNECTIVITY_DEFINITION",
        "block_ids": (
            "d2l_linear_networks_linear_regression_b091",
            "d2l_linear_networks_linear_regression_concise_b021",
            "d2l_linear_networks_softmax_regression_b015",
            "d2l_multilayer_perceptrons_index_b002",
            "d2l_multilayer_perceptrons_mlp_b013",
        ),
        "new_candidate_targets": (),
        "source_candidate_ids": (
            "candidate_69d487fc044881f9f782de53",
            "candidate_bacd2b7d8eb5d2ff10742c27",
            "candidate_ed0f208b38e5ecb43e4b5efc",
        ),
    },
)

EXPECTED_PARENT_IDS = {
    PARENT_IN_PLACE,
    PARENT_STATISTICAL_POWER,
    PARENT_ADAM,
    PARENT_FULLY_CONNECTED,
}
EXPECTED_OUTPUT_SENSE_IDS = {row["output_sense_id"] for row in CASE_SPECS}
EXPECTED_BLOCK_IDS = {
    block_id for row in CASE_SPECS for block_id in row["block_ids"]
}

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

REVIEWER_SLOTS = ("reviewer_1", "reviewer_2", "reviewer_3")

REJECTED_PARENT_CONTEXTS = (
    {
        "parent_sense_id": PARENT_STATISTICAL_POWER,
        "source_context_id": "ctx_e35e3b1e2bfeb5965b0bd614",
        "rejection_reason": "WRONG_SENSE_EXPRESSIVE_POWER",
    },
    {
        "parent_sense_id": PARENT_FULLY_CONNECTED,
        "source_context_id": "ctxx_e58b72f11fa52345b99c8a32",
        "rejection_reason": "SYNTHETIC_BOUNDARY_NOT_POSITIVE_EVIDENCE",
    },
)
