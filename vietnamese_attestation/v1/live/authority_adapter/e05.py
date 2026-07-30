"""Exact, independently anchored inputs for the E-05 zero-provider integration."""

from __future__ import annotations

import hashlib
import io
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator, FormatChecker

from ...strict_json import canonical_relative_ref, reject_link, strict_json_loads
from ..common import (
    LiveSchemaError,
    canonical_sha256,
    require_exact_keys,
    require_sha256,
    verify_seal,
)
from ..schemas import validate_provider_role_plan


E05_DELIVERY_SHA256 = "2fe7ce1aa2bbe5c25915b9a885b74dee7ede232d3d468982093a5247f7d343e6"
E05_INPUT_ZIP_SHA256 = "31f83c83913ec23ca09da3929136ca0cae881cc4e5b611c93983169e0c1dc369"
E05_INPUT_MANIFEST_SELF_SHA256 = "7af5011f0da66f71d5954b0c10568baa73b52341f3ad4e7411b69e8c01c0b821"
E05_AB_RECEIPT_SELF_SHA256 = "413b8dd854968466a73fac9a713fc6f58f6d34db731afdb828c88a9ed43d13d1"

MAIN_PROFILE_ZIP_SHA256 = "8434a13726648b7b50caf51d729212a13ba7a4f4cef26a6188026a1e65bbf3e7"
MAIN_PROFILE_SELF_SHA256 = "3f81ea9200c5d125602a286876baf25ac9ffb44ac8052e99e32f7fe8a0f89796"
MAIN_PROFILE_PHYSICAL_SHA256 = "1d1c3a2a2b85d1cb7898c034d979cef4d1e57bdb2d74ca98f28e935b05945f5e"
MAIN_PROFILE_ANCHOR_SELF_SHA256 = "d1edda618e07334a8e19dadb1d684535d32261e71793a9584d1072a3cf204a36"
MAIN_PROFILE_ANCHOR_PHYSICAL_SHA256 = "02c6bb03afc736db15869e867fe95ef7b93f26e203547cee2d29062c7a6d2307"

E05_BASE_COMMIT = "dc9d38e9925da5f38830381736481745bd22d260"
E05_BASE_TREE = "541ec5a514f62312b385195f2179ec43a5ef0ce5"
E05_REVIEW_PACKAGE_SHA256 = "7e97342fb634571345d5893ad0aab5abaa59977f0ceea67fff0650489033e2a7"
E05_PROVIDER_PLAN_SELF_SHA256 = "5320bfc4abd73c299113338c10ebd686516a130e62a4b8a6e5ebcd1115b811cf"
E05_PROVIDER_PLAN_PHYSICAL_SHA256 = "fb70908ba9826fff4518c9e0f5c380648d610dd04dd2e1b06e266aafd911f7e3"

DRAFT4_COMMIT = "c28b3ad3b60627f1bcd7722404b16aca88754ec7"
DRAFT4_TREE = "ac8d3489f67f4fec212009523b9ae9ce90dfbdab"

_SHA256_ROW = re.compile(r"([0-9a-f]{64})  (.+)")
_DELIVERY_MEMBERS = frozenset(
    {
        "DELIVERY_CHECKSUMS.sha256",
        "E05_EXACT_INTEGRATION_INPUTS_V1.zip",
        "README.md",
        "build_e05_input_package.py",
        "deterministic_ab_receipt.json",
    }
)
_PROTOCOL_FILES = {
    "LIVE_AUTHORIZATION_RECEIPT": "LIVE_AUTHORIZATION_RECEIPT_V1_1.schema.json",
    "LIVE_LEDGER_EVENT": "LIVE_LEDGER_EVENT_V1_1.schema.json",
    "RUN_START_RECEIPT": "RUN_START_RECEIPT_V1_1.schema.json",
    "RUN_STOP_RECEIPT": "RUN_STOP_RECEIPT_V1_1.schema.json",
    "USAGE_SNAPSHOT": "USAGE_SNAPSHOT_V1.schema.json",
}
_PROFILE_EXAMPLE_FILES = {
    "LIVE_AUTHORIZATION_RECEIPT": "main_run/main_live_authorization.json",
    "LIVE_LEDGER_EVENT": "main_run/main_stop_event.json",
    "RUN_START_RECEIPT": "main_run/main_run_start.json",
    "RUN_STOP_RECEIPT": "main_run/main_run_stop.json",
}


@dataclass(frozen=True)
class E05ExactIntegrationInputs:
    """Verified values loaded only from the immutable Main delivery."""

    delivery_path: Path
    input_manifest: Mapping[str, Any]
    profile_anchor: Mapping[str, Any]
    main_profile: Mapping[str, Any]
    authorization_receipt: Mapping[str, Any]
    integration_run_spec: Mapping[str, Any]
    baseline_run_spec: Mapping[str, Any]
    candidate_set: Mapping[str, Any]
    provider_role_plan: Mapping[str, Any]
    owner_binding_receipt: Mapping[str, Any]
    protocol_schemas: Mapping[str, Mapping[str, Any]]
    protocol_schema_bytes: Mapping[str, bytes]
    profile_member_bytes: Mapping[str, bytes]

    @property
    def live_execution_authorized(self) -> bool:
        return False

    def require_live_execution_authority(self) -> None:
        raise LiveSchemaError("E-05 exact inputs are zero-provider integration authority only")


def load_e05_exact_integration_inputs(
    delivery_path: str | Path,
) -> E05ExactIntegrationInputs:
    """Load the single exact Main delivery without accepting caller-owned hashes."""

    delivery_file = _regular_file(delivery_path)
    delivery_raw = delivery_file.read_bytes()
    _require_physical(delivery_raw, E05_DELIVERY_SHA256, "E-05 delivery")
    delivery = _zip_members(delivery_raw, label="E-05 delivery")
    if set(delivery) != set(_DELIVERY_MEMBERS):
        raise LiveSchemaError("E-05 delivery member set mismatch")
    _verify_checksums(
        delivery,
        checksum_name="DELIVERY_CHECKSUMS.sha256",
        label="E-05 delivery",
    )

    ab_receipt = _json_object(delivery["deterministic_ab_receipt.json"], label="A/B receipt")
    _require_seal(ab_receipt, E05_AB_RECEIPT_SELF_SHA256, "A/B receipt")
    require_exact_keys(
        ab_receipt,
        {
            "build_a_label",
            "build_a_zip_sha256",
            "build_b_label",
            "build_b_zip_sha256",
            "byte_identical",
            "corpus_acquisition_authorized",
            "gold_access",
            "integrity",
            "network_calls",
            "provider_calls",
            "run_authorized",
            "schema_id",
            "schema_version",
            "status",
        },
        path="$.deterministic_ab_receipt",
    )
    if (
        ab_receipt["build_a_zip_sha256"] != E05_INPUT_ZIP_SHA256
        or ab_receipt["build_b_zip_sha256"] != E05_INPUT_ZIP_SHA256
        or ab_receipt["byte_identical"] is not True
        or ab_receipt["run_authorized"] is not False
        or ab_receipt["provider_calls"] != 0
        or ab_receipt["network_calls"] != 0
    ):
        raise LiveSchemaError("E-05 A/B receipt does not preserve the zero-provider boundary")

    input_zip_raw = delivery["E05_EXACT_INTEGRATION_INPUTS_V1.zip"]
    _require_physical(input_zip_raw, E05_INPUT_ZIP_SHA256, "E-05 nested input ZIP")
    members = _zip_members(input_zip_raw, label="E-05 nested input ZIP")
    _verify_checksums(members, checksum_name="CHECKSUMS.sha256", label="E-05 input")
    input_manifest = _json_object(members["manifest.json"], label="E-05 input manifest")
    _require_seal(input_manifest, E05_INPUT_MANIFEST_SELF_SHA256, "E-05 input manifest")
    _verify_manifest_inventory(input_manifest, members)
    if (
        input_manifest.get("status") != "E05_EXACT_INTEGRATION_INPUTS_READY_ZERO_PROVIDER"
        or input_manifest.get("run_authorized") is not False
        or input_manifest.get("provider_calls") != 0
        or input_manifest.get("network_calls") != 0
        or input_manifest.get("corpus_acquisition_authorized") is not False
        or input_manifest.get("gold_access") != 0
    ):
        raise LiveSchemaError("E-05 input manifest is not a zero-provider integration input")

    profile_zip_raw = members[
        "accepted_profile/Main_SI_Unified_Authority_Profile_c28b3ad_Review_V1.zip"
    ]
    _require_physical(profile_zip_raw, MAIN_PROFILE_ZIP_SHA256, "accepted Main profile ZIP")
    profile_members = _zip_members(profile_zip_raw, label="accepted Main profile ZIP")
    _verify_checksums(profile_members, checksum_name="CHECKSUMS.sha256", label="Main profile")

    anchor_raw = members[
        "accepted_profile/Main_SI_Unified_Profile_Independent_Acceptance_Receipt_V1.json"
    ]
    _require_physical(anchor_raw, MAIN_PROFILE_ANCHOR_PHYSICAL_SHA256, "Main profile anchor")
    profile_anchor = _json_object(anchor_raw, label="Main profile anchor")
    _validate_profile_anchor(profile_anchor)

    profile_raw = profile_members["HarnessTrustedMainAuthorityProfileV1.json"]
    _require_physical(profile_raw, MAIN_PROFILE_PHYSICAL_SHA256, "Main authority profile")
    main_profile = _json_object(profile_raw, label="Main authority profile")
    _require_seal(main_profile, MAIN_PROFILE_SELF_SHA256, "Main authority profile")
    _validate_main_profile(main_profile, profile_anchor)

    integration_spec = _sealed_member(
        members,
        "main_bindings/E05_ZERO_PROVIDER_INTEGRATION_RUN_SPEC_V1.json",
        label="E-05 integration run spec",
    )
    _validate_integration_spec(integration_spec)
    provider_plan_raw = members["main_bindings/E_PROVIDER_ROLE_PLAN_D0_V1.json"]
    _require_physical(provider_plan_raw, E05_PROVIDER_PLAN_PHYSICAL_SHA256, "E provider role plan")
    provider_role_plan = validate_provider_role_plan(
        _json_object(provider_plan_raw, label="E provider role plan")
    )
    if provider_role_plan["integrity"]["self_sha256"] != E05_PROVIDER_PLAN_SELF_SHA256:
        raise LiveSchemaError("E provider role plan self hash mismatch")
    _validate_provider_plan(provider_role_plan)

    candidate_raw = members["phase/phase_authorized_candidate_set.json"]
    candidate_set = _json_object(candidate_raw, label="phase candidate set")
    _require_seal(
        candidate_set,
        integration_spec["candidate_set"]["self_sha256"],
        "phase candidate set",
    )
    _require_physical(
        candidate_raw,
        integration_spec["candidate_set"]["physical_sha256"],
        "phase candidate set",
    )
    _validate_candidate_set(candidate_set)

    baseline_raw = members["phase/run_spec.zero_provider_baseline.json"]
    baseline_run_spec = _json_object(baseline_raw, label="zero-provider baseline run spec")
    if not verify_seal(baseline_run_spec):
        raise LiveSchemaError("zero-provider baseline run spec self hash mismatch")
    if baseline_raw != profile_members["main_run/run_spec.json"]:
        raise LiveSchemaError("zero-provider baseline run spec is not byte-identical to the profile")
    if candidate_raw != profile_members["main_run/phase_authorized_candidate_set.json"]:
        raise LiveSchemaError("phase candidate set is not byte-identical to the profile")

    owner_raw = members[
        "owner_bindings/SI_EV02_ProducerSafe_Owner_Binding_Acceptance_Receipt_V1.json"
    ]
    owner_binding = _json_object(owner_raw, label="SI owner-binding receipt")
    if not verify_seal(owner_binding):
        raise LiveSchemaError("SI owner-binding receipt self hash mismatch")
    _validate_owner_binding(
        owner_binding,
        members["owner_bindings/EV02_D0_BLIND_COHORT_PRODUCER_HANDOFF_7de0eca_V1.zip"],
    )

    protocol_schemas: dict[str, Mapping[str, Any]] = {}
    protocol_schema_bytes: dict[str, bytes] = {}
    declared_schemas = {
        row["role"]: row for row in integration_spec["draft4"]["schemas"]
    }
    if set(declared_schemas) != set(_PROTOCOL_FILES):
        raise LiveSchemaError("E-05 Draft4 role set mismatch")
    for role, filename in _PROTOCOL_FILES.items():
        path = f"protocol_schemas/{filename}"
        raw = members[path]
        profile_schema_ref = f"protocol/{filename}"
        if (
            profile_schema_ref in profile_members
            and raw != profile_members[profile_schema_ref]
        ):
            raise LiveSchemaError(f"Draft4 schema is not byte-identical to Main profile: {role}")
        if role != "USAGE_SNAPSHOT" and profile_schema_ref not in profile_members:
            raise LiveSchemaError(f"Draft4 profile schema is missing: {role}")
        if hashlib.sha256(raw).hexdigest() != declared_schemas[role]["physical_sha256"]:
            raise LiveSchemaError(f"Draft4 schema physical hash mismatch: {role}")
        protocol_schemas[role] = _json_object(raw, label=f"Draft4 schema {role}")
        protocol_schema_bytes[role] = raw

    authorization = _json_object(
        profile_members[_PROFILE_EXAMPLE_FILES["LIVE_AUTHORIZATION_RECEIPT"]],
        label="Draft4 authorization receipt",
    )
    validate_e05_protocol_instance_from_schema(
        authorization,
        role="LIVE_AUTHORIZATION_RECEIPT",
        schema=protocol_schemas["LIVE_AUTHORIZATION_RECEIPT"],
    )
    if (
        authorization.get("authorization_status") != "SYNTHETIC_TEST_ONLY"
        or authorization.get("test_only") is not True
        or "e_execution_binding" in authorization
        or not isinstance(authorization.get("bindings"), Mapping)
    ):
        raise LiveSchemaError("Draft4 authorization receipt does not use the reviewed bindings hold")
    if not verify_seal(authorization):
        raise LiveSchemaError("Draft4 authorization receipt self hash mismatch")

    for role, member_name in _PROFILE_EXAMPLE_FILES.items():
        value = _json_object(profile_members[member_name], label=f"Draft4 example {role}")
        validate_e05_protocol_instance_from_schema(
            value,
            role=role,
            schema=protocol_schemas[role],
        )
        if role != "LIVE_LEDGER_EVENT" and not verify_seal(value):
            raise LiveSchemaError(f"Draft4 example self hash mismatch: {role}")
        if role == "LIVE_LEDGER_EVENT":
            expected = canonical_sha256(
                {key: item for key, item in value.items() if key != "event_sha256"}
            )
            if value.get("event_sha256") != expected:
                raise LiveSchemaError("Draft4 example event hash mismatch")

    return E05ExactIntegrationInputs(
        delivery_path=delivery_file,
        input_manifest=input_manifest,
        profile_anchor=profile_anchor,
        main_profile=main_profile,
        authorization_receipt=authorization,
        integration_run_spec=integration_spec,
        baseline_run_spec=baseline_run_spec,
        candidate_set=candidate_set,
        provider_role_plan=provider_role_plan,
        owner_binding_receipt=owner_binding,
        protocol_schemas=protocol_schemas,
        protocol_schema_bytes=protocol_schema_bytes,
        profile_member_bytes=profile_members,
    )


def validate_e05_protocol_instance(
    inputs: E05ExactIntegrationInputs,
    *,
    role: str,
    value: Mapping[str, Any],
) -> dict[str, Any]:
    if role not in inputs.protocol_schemas:
        raise LiveSchemaError(f"unsupported E-05 Draft4 role: {role}")
    return validate_e05_protocol_instance_from_schema(
        value,
        role=role,
        schema=inputs.protocol_schemas[role],
    )


def validate_e05_protocol_instance_from_schema(
    value: Mapping[str, Any],
    *,
    role: str,
    schema: Mapping[str, Any],
) -> dict[str, Any]:
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        raise LiveSchemaError(
            f"E-05 Draft4 instance is invalid for {role}: {errors[0].message}"
        )
    return dict(value)


def _validate_profile_anchor(value: Mapping[str, Any]) -> None:
    _require_seal(value, MAIN_PROFILE_ANCHOR_SELF_SHA256, "Main profile anchor")
    require_exact_keys(
        value,
        {
            "accepted_scope",
            "independent_checks",
            "integrity",
            "reviewer_authority_id",
            "schema_id",
            "schema_version",
            "status",
            "target",
        },
        path="$.profile_anchor",
    )
    if (
        value["schema_id"] != "IndependentMainSIUnifiedProfileAcceptanceReceiptV1"
        or value["status"] != "MAIN_SI_UNIFIED_AUTHORITY_PROFILE_ACCEPTED_ZERO_PROVIDER_NOT_LIVE"
        or value["reviewer_authority_id"] != "independent-review-terminology-evidence-v1"
    ):
        raise LiveSchemaError("Main profile anchor identity/status mismatch")
    target = value["target"]
    require_exact_keys(
        target,
        {
            "profile_physical_sha256",
            "profile_relative_path",
            "profile_self_sha256",
            "protocol_commit",
            "protocol_tree",
            "publication_receipt_self_sha256",
            "review_zip_sha256",
            "si_commit",
            "si_tree",
        },
        path="$.profile_anchor.target",
    )
    expected = {
        "profile_physical_sha256": MAIN_PROFILE_PHYSICAL_SHA256,
        "profile_self_sha256": MAIN_PROFILE_SELF_SHA256,
        "protocol_commit": DRAFT4_COMMIT,
        "protocol_tree": DRAFT4_TREE,
        "review_zip_sha256": MAIN_PROFILE_ZIP_SHA256,
    }
    for key, item in expected.items():
        if target.get(key) != item:
            raise LiveSchemaError(f"Main profile anchor target mismatch: {key}")
    scope = value["accepted_scope"]
    if (
        scope.get("si_zero_provider_profile_owner_binding") is not True
        or scope.get("e_live_runtime_authority") is not False
        or scope.get("run_authorized") is not False
        or scope.get("corpus_acquisition_authorized") is not False
    ):
        raise LiveSchemaError("Main profile anchor grants an unsupported live scope")


def _validate_main_profile(
    value: Mapping[str, Any], anchor: Mapping[str, Any]
) -> None:
    if (
        value.get("schema_id") != "HarnessTrustedMainAuthorityProfileV1"
        or value.get("status") != "ZERO_PROVIDER_TRUST_PROFILE_ACCEPTED"
        or value.get("issuer_id") != "terminology-evidence-main-maintainer"
        or value.get("authority_id") != "main-d0-zero-provider-trust-authority-v1"
        or value.get("final_glossary_decision") is not None
    ):
        raise LiveSchemaError("Main authority profile identity/status mismatch")
    protocol = value.get("protocol")
    if not isinstance(protocol, Mapping):
        raise LiveSchemaError("Main authority profile lacks protocol binding")
    if protocol.get("commit") != DRAFT4_COMMIT or protocol.get("tree") != DRAFT4_TREE:
        raise LiveSchemaError("Main authority profile protocol identity mismatch")
    if protocol.get("status") != "DRAFT4_PUBLIC_SURFACE_UNPROMOTED":
        raise LiveSchemaError("Main authority profile unexpectedly promotes Draft4")
    if anchor["target"]["profile_self_sha256"] != value["integrity"]["self_sha256"]:
        raise LiveSchemaError("Main profile is not bound by the independent anchor")


def _validate_integration_spec(value: Mapping[str, Any]) -> None:
    if not verify_seal(value):
        raise LiveSchemaError("E-05 integration run spec self hash mismatch")
    if (
        value.get("schema_id") != "MainE05ZeroProviderIntegrationRunSpecV1"
        or value.get("status") != "E05_EXACT_INTEGRATION_INPUT_ONLY"
        or value.get("execution_permitted") is not False
        or value.get("run_authorized") is not False
    ):
        raise LiveSchemaError("E-05 integration run spec grants execution")
    base = value.get("e_integration_base", {})
    if (
        base.get("commit") != E05_BASE_COMMIT
        or base.get("tree") != E05_BASE_TREE
        or base.get("review_package_sha256") != E05_REVIEW_PACKAGE_SHA256
    ):
        raise LiveSchemaError("E-05 integration base identity mismatch")
    draft4 = value.get("draft4", {})
    if (
        draft4.get("commit") != DRAFT4_COMMIT
        or draft4.get("tree") != DRAFT4_TREE
        or draft4.get("authorization_representation") != "bindings"
        or draft4.get("stop_event_representation")
        != "LIVE_LEDGER_EVENT.event_kind=STOP_EVENT"
    ):
        raise LiveSchemaError("E-05 Draft4 integration decision mismatch")
    profile = value.get("accepted_profile", {})
    if (
        profile.get("anchor_physical_sha256") != MAIN_PROFILE_ANCHOR_PHYSICAL_SHA256
        or profile.get("anchor_self_sha256") != MAIN_PROFILE_ANCHOR_SELF_SHA256
        or profile.get("profile_self_sha256") != MAIN_PROFILE_SELF_SHA256
        or profile.get("zip_physical_sha256") != MAIN_PROFILE_ZIP_SHA256
    ):
        raise LiveSchemaError("E-05 accepted profile binding mismatch")
    role_plan = value.get("provider_role_plan", {})
    if (
        role_plan.get("active_gateway") != "gemini_official"
        or role_plan.get("model_id") != "gemini-3.5-flash"
        or role_plan.get("alternate_gateways_authorized") is not False
        or role_plan.get("physical_sha256") != E05_PROVIDER_PLAN_PHYSICAL_SHA256
        or role_plan.get("self_sha256") != E05_PROVIDER_PLAN_SELF_SHA256
    ):
        raise LiveSchemaError("E-05 provider role-plan binding mismatch")


def _validate_provider_plan(value: Mapping[str, Any]) -> None:
    if value.get("policy_id") != "e-d0-gemini-official-role-plan-v1":
        raise LiveSchemaError("E-05 provider policy identity mismatch")
    if value.get("external_provider_call_count") != 0:
        raise LiveSchemaError("E-05 provider plan is not zero-provider input")
    roles = value.get("roles", [])
    if [row.get("semantic_role") for row in roles] != [
        "PRIMARY_ATTESTATION_JUDGE",
        "SECONDARY_ATTESTATION_JUDGE",
    ]:
        raise LiveSchemaError("E-05 provider semantic role set/order mismatch")
    for row in roles:
        if (
            row.get("provider_id") != "gemini_official"
            or row.get("model_id") != "gemini-3.5-flash"
            or row.get("mode") != "LIVE_PROVIDER"
            or row.get("generation_config") != {"reasoning": "none", "temperature": 0}
            or row.get("max_retries") != 1
        ):
            raise LiveSchemaError("E-05 provider route/model/config mismatch")
    if value.get("secondary_condition") != [
        "PRIMARY_CONCEPT_UNCERTAIN",
        "INDEPENDENT_CLUSTER_CONFLICT",
    ]:
        raise LiveSchemaError("E-05 secondary escalation condition mismatch")


def _validate_candidate_set(value: Mapping[str, Any]) -> None:
    if (
        value.get("schema_id") != "LivePhaseAuthorizedCandidateSetV1_1"
        or value.get("schema_version") != "1.1.0-draft.4"
        or value.get("phase_id") != "D0_ONE_CANDIDATE"
        or value.get("run_id") != "RUN-D0"
        or value.get("candidate_count") != 1
        or value.get("sense_count") != 1
    ):
        raise LiveSchemaError("E-05 phase candidate set identity mismatch")
    rows = value.get("ordered_candidates")
    if not isinstance(rows, list) or len(rows) != 1:
        raise LiveSchemaError("E-05 phase candidate set must contain exactly one candidate")


def _validate_owner_binding(value: Mapping[str, Any], handoff_raw: bytes) -> None:
    if (
        value.get("schema_id")
        != "IndependentSIEV02ProducerSafeOwnerBindingAcceptanceReceiptV1"
        or value.get("status") != "SI_EV02_OWNER_BINDING_ACCEPTED_NOT_LIVE_AUTHORITY"
        or value.get("reviewer_authority_id")
        != "independent-review-terminology-evidence-v1"
    ):
        raise LiveSchemaError("SI owner-binding receipt identity/status mismatch")
    boundary = value.get("authority_boundary", {})
    if (
        boundary.get("owner_binding_accepted") is not True
        or boundary.get("official_live_authority_active") is not False
        or boundary.get("run_authorized") is not False
        or boundary.get("corpus_acquisition_authorized") is not False
    ):
        raise LiveSchemaError("SI owner-binding receipt grants unsupported authority")
    expected = value.get("accepted_bindings", {}).get("producer_handoff_sha256")
    if expected != hashlib.sha256(handoff_raw).hexdigest():
        raise LiveSchemaError("SI owner-binding producer handoff hash mismatch")
    handoff_members = _zip_members(handoff_raw, label="EV-02 producer-safe handoff")
    if set(handoff_members) != {
        "CHECKSUMS.sha256",
        "EV02_D0_Blind_Cohort_Independent_Acceptance_Receipt_V1.json",
        "README.md",
        "d0_blind_cohort_authority_v1.json",
    }:
        raise LiveSchemaError("EV-02 producer-safe handoff member set mismatch")
    _verify_checksums(
        handoff_members,
        checksum_name="CHECKSUMS.sha256",
        label="EV-02 producer-safe handoff",
    )


def _verify_manifest_inventory(
    manifest: Mapping[str, Any], members: Mapping[str, bytes]
) -> None:
    rows = manifest.get("files")
    if not isinstance(rows, list):
        raise LiveSchemaError("E-05 input manifest files must be a list")
    refs: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise LiveSchemaError(f"E-05 manifest row {index} is not an object")
        require_exact_keys(
            row,
            {"path", "sha256", "size_bytes"},
            path=f"$.files[{index}]",
        )
        ref, _ = canonical_relative_ref(row["path"])
        require_sha256(row["sha256"], path=f"$.files[{index}].sha256")
        if ref not in members:
            raise LiveSchemaError(f"E-05 manifest member is missing: {ref}")
        raw = members[ref]
        if hashlib.sha256(raw).hexdigest() != row["sha256"] or len(raw) != row["size_bytes"]:
            raise LiveSchemaError(f"E-05 manifest binding mismatch: {ref}")
        refs.append(ref)
    if refs != sorted(set(refs)):
        raise LiveSchemaError("E-05 manifest refs must be sorted and unique")
    if set(refs) != set(members) - {"CHECKSUMS.sha256", "manifest.json"}:
        raise LiveSchemaError("E-05 manifest does not cover the exact package inventory")


def _sealed_member(
    members: Mapping[str, bytes], member: str, *, label: str
) -> dict[str, Any]:
    value = _json_object(members[member], label=label)
    if not verify_seal(value):
        raise LiveSchemaError(f"{label} self hash mismatch")
    return value


def _verify_checksums(
    members: Mapping[str, bytes], *, checksum_name: str, label: str
) -> None:
    raw = members.get(checksum_name)
    if raw is None:
        raise LiveSchemaError(f"{label} CHECKSUMS is missing")
    try:
        text = raw.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        raise LiveSchemaError(f"{label} CHECKSUMS is not strict ASCII") from exc
    if not text.endswith("\n"):
        raise LiveSchemaError(f"{label} CHECKSUMS must end with one newline")
    refs: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = _SHA256_ROW.fullmatch(line)
        if match is None:
            raise LiveSchemaError(f"{label} CHECKSUMS row is malformed: {line_number}")
        expected, raw_ref = match.groups()
        ref, _ = canonical_relative_ref(raw_ref)
        if ref in refs:
            raise LiveSchemaError(f"{label} CHECKSUMS contains duplicate refs")
        if ref not in members:
            raise LiveSchemaError(f"{label} CHECKSUMS references a missing member: {ref}")
        if hashlib.sha256(members[ref]).hexdigest() != expected:
            raise LiveSchemaError(f"{label} CHECKSUMS hash mismatch: {ref}")
        refs.append(ref)
    if refs != sorted(refs):
        raise LiveSchemaError(f"{label} CHECKSUMS refs are not sorted")
    if set(refs) != set(members) - {checksum_name}:
        raise LiveSchemaError(f"{label} CHECKSUMS does not cover the exact ZIP inventory")


def _zip_members(raw: bytes, *, label: str) -> dict[str, bytes]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw), mode="r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise LiveSchemaError(f"{label} is not a valid ZIP") from exc
    with archive:
        infos = archive.infolist()
        if [item.filename for item in infos] != sorted(item.filename for item in infos):
            raise LiveSchemaError(f"{label} member order is not canonical")
        result: dict[str, bytes] = {}
        case_keys: set[str] = set()
        for info in infos:
            if info.is_dir() or info.flag_bits & 0x1:
                raise LiveSchemaError(f"{label} contains a directory or encrypted member")
            ref, case_key = canonical_relative_ref(info.filename)
            if case_key in case_keys:
                raise LiveSchemaError(f"{label} contains duplicate/case-confusable members")
            case_keys.add(case_key)
            mode = (info.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise LiveSchemaError(f"{label} contains a symbolic-link member")
            try:
                result[ref] = archive.read(info)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise LiveSchemaError(f"{label} member cannot be read: {ref}") from exc
        return result


def _json_object(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        text = raw.decode("utf-8", errors="strict")
        value = strict_json_loads(text)
    except (UnicodeDecodeError, ValueError) as exc:
        raise LiveSchemaError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise LiveSchemaError(f"{label} must be a JSON object")
    return value


def _regular_file(path: str | Path) -> Path:
    supplied = Path(path).absolute()
    try:
        reject_link(supplied)
        resolved = supplied.resolve(strict=True)
        reject_link(resolved)
    except (OSError, ValueError) as exc:
        raise LiveSchemaError(f"cannot resolve E-05 delivery: {path}") from exc
    if not resolved.is_file():
        raise LiveSchemaError(f"E-05 delivery is not a regular file: {path}")
    return resolved


def _require_physical(raw: bytes, expected: str, label: str) -> None:
    if hashlib.sha256(raw).hexdigest() != expected:
        raise LiveSchemaError(f"{label} physical SHA-256 mismatch")


def _require_seal(value: Mapping[str, Any], expected: str, label: str) -> None:
    if value.get("integrity", {}).get("self_sha256") != expected or not verify_seal(value):
        raise LiveSchemaError(f"{label} canonical self hash mismatch")


__all__ = [
    "DRAFT4_COMMIT",
    "DRAFT4_TREE",
    "E05_BASE_COMMIT",
    "E05_BASE_TREE",
    "E05_DELIVERY_SHA256",
    "E05ExactIntegrationInputs",
    "load_e05_exact_integration_inputs",
    "validate_e05_protocol_instance",
]
