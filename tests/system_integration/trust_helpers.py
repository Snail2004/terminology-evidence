"""Zero-network trusted Main/producer fixtures for Harness conformance tests."""

from __future__ import annotations

import copy
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence

from integration_harness.adapter_v1.producer import candidate_set_sha256
from integration_harness.adapter_v1.trust import (
    LIVE_AUTHORIZATION_SCHEMA_ID,
    LIVE_LEDGER_EVENT_SCHEMA_ID,
    LIVE_PROTOCOL_VERSION,
    PROTOCOL_SCHEMA_PINS,
    RUN_START_SCHEMA_ID,
    RUN_STOP_SCHEMA_ID,
    ZERO_PROVIDER_PROFILE,
    load_trusted_authority_profile,
)
from integration_harness.hashing import self_sha256, sha256_bytes, sha256_file
from integration_harness.jsonio import canonical_bytes, dump_json, load_json


ISSUER_ID = "system-integration-maintainer"
AUTHORITY_ID = "main-reviewed-producer-set-authority-v1"
PROTOCOL_COMMIT = "a" * 40
PROTOCOL_TREE = "b" * 40
STOP_REASON = "EXTERNAL_ACQUISITION_STOP_RECEIPT"
OBSERVED_AT = "2026-07-30T00:00:00Z"


def make_trusted_profile(
    repo_root: Path,
    output_root: Path,
    *,
    candidates: Sequence[Any],
    producers: Mapping[str, Mapping[str, Any]],
    run_id: str = "RUN-D0",
    phase_id: str = "D0_ONE_CANDIDATE",
    split_id: str = "official-five-sense",
    valid_until: str = "2099-01-01T00:00:00Z",
) -> dict[str, Any]:
    """Create a schema-valid, explicitly synthetic trust profile and its pins."""

    output_root.mkdir(parents=True, exist_ok=True)
    draft_root = (
        Path(repo_root).parent
        / "live-run-protocol-v1-1-draft"
        / "docs"
        / "live-run-protocol"
        / "v1_1"
    )
    protocol_root = output_root / "protocol"
    protocol_root.mkdir(parents=True, exist_ok=True)
    schema_files: list[dict[str, str]] = []
    source_names = {
        "live_authorization": "LIVE_AUTHORIZATION_RECEIPT_V1_1.schema.json",
        "run_start": "RUN_START_RECEIPT_V1_1.schema.json",
        "run_stop": "RUN_STOP_RECEIPT_V1_1.schema.json",
        "ledger_event": "LIVE_LEDGER_EVENT_V1_1.schema.json",
    }
    for kind in sorted(source_names):
        source = draft_root / source_names[kind]
        destination = protocol_root / source.name
        shutil.copyfile(source, destination)
        pin = PROTOCOL_SCHEMA_PINS[kind]
        schema_files.append(
            {
                "kind": kind,
                "schema_id": pin["schema_id"],
                "schema_version": LIVE_PROTOCOL_VERSION,
                "relative_path": f"protocol/{source.name}",
                "physical_sha256": sha256_file(destination),
            }
        )

    candidate_hash = candidate_set_sha256(candidates)
    filler = "c" * 64
    authorities = {
        key: ("d" * 40 if key.endswith("commit") or key.endswith("tree_git_oid") else filler)
        for key in (
            "dataset_release_physical_sha256", "dataset_manifest_self_sha256",
            "dataset_manifest_physical_sha256", "split_cohort_inventory_self_sha256",
            "split_cohort_inventory_physical_sha256", "c_release_commit",
            "c_release_tree_git_oid", "e_release_commit", "e_release_tree_git_oid",
            "e_release_manifest_self_sha256", "e_release_zip_physical_sha256",
            "harness_cohort_inventory_self_sha256", "harness_cohort_inventory_physical_sha256",
            "global_batch_authority_self_sha256", "global_batch_authority_physical_sha256",
            "harness_authority_set_self_sha256", "harness_authority_set_physical_sha256",
            "global_development_policy_self_sha256", "global_development_policy_physical_sha256",
            "evaluation_frozen_plan_self_sha256", "evaluation_frozen_plan_physical_sha256",
            "evaluation_pre_d0_addendum_self_sha256", "evaluation_pre_d0_addendum_physical_sha256",
            "c_provider_plan_binding_self_sha256", "c_provider_plan_binding_physical_sha256",
            "c_replay_authority_self_sha256", "c_replay_authority_physical_sha256",
            "protocol_authority_self_sha256", "protocol_authority_physical_sha256",
        )
    }
    bindings = {
        "run_spec_self_sha256": filler,
        "run_spec_physical_sha256": filler,
        "phase_authorized_candidate_set_self_sha256": candidate_hash,
        "phase_authorized_candidate_set_physical_sha256": filler,
        "c_role_plan_self_sha256": "155261fc2c80e54b6e22e266104fa6a5a2040fa6faf4b8d7865bb970a763e815",
        "c_role_plan_physical_sha256": "6a229435a2d84198dc88bee26c3b4bb5645b7b086849c4f5e1a13217a9152e61",
        "e_registry_sha256": filler,
        "e_corpus_sha256": filler,
        "e_retrieval_policy_sha256": filler,
        "query_template_set_sha256": filler,
        "brave_plan_terms_receipt_sha256": filler,
        "pre_acquisition_authorities": authorities,
    }
    authorization = {
        "schema_id": LIVE_AUTHORIZATION_SCHEMA_ID,
        "schema_version": LIVE_PROTOCOL_VERSION,
        "receipt_id": "synthetic-main-authorization",
        "authorization_status": "SYNTHETIC_TEST_ONLY",
        "test_only": True,
        "phase_id": phase_id,
        "issued_at": OBSERVED_AT,
        "valid_from": OBSERVED_AT,
        "valid_until": valid_until,
        "issuer_id": ISSUER_ID,
        "authority_id": AUTHORITY_ID,
        "approval_artifact_self_sha256": filler,
        "approval_artifact_physical_sha256": filler,
        "protocol_commit": PROTOCOL_COMMIT,
        "protocol_tree_git_oid": PROTOCOL_TREE,
        "bindings": bindings,
        "budget_spec_sha256": filler,
        "secret_readiness_receipt_sha256": filler,
        "secret_readiness_receipt_self_sha256": filler,
        "prior_gate_receipt_sha256": None,
        "integrity": {},
    }
    authorization["integrity"]["self_sha256"] = self_sha256(authorization)
    authorization_path = output_root / "main_live_authorization.json"
    dump_json(authorization_path, authorization)

    run_start = {
        "schema_id": RUN_START_SCHEMA_ID,
        "schema_version": LIVE_PROTOCOL_VERSION,
        "receipt_id": "synthetic-main-run-start",
        "phase_id": phase_id,
        "issued_at": OBSERVED_AT,
        "authorization_receipt_self_sha256": authorization["integrity"]["self_sha256"],
        "authorization_receipt_physical_sha256": sha256_file(authorization_path),
        "run_spec_self_sha256": bindings["run_spec_self_sha256"],
        "run_spec_physical_sha256": bindings["run_spec_physical_sha256"],
        "phase_authorized_candidate_set_self_sha256": candidate_hash,
        "phase_authorized_candidate_set_physical_sha256": bindings[
            "phase_authorized_candidate_set_physical_sha256"
        ],
        "budget_spec_sha256": authorization["budget_spec_sha256"],
        "secret_readiness_receipt_sha256": authorization[
            "secret_readiness_receipt_sha256"
        ],
        "secret_readiness_receipt_self_sha256": authorization[
            "secret_readiness_receipt_self_sha256"
        ],
        "initial_ledger_head": None,
        "integrity": {},
    }
    run_start["integrity"]["self_sha256"] = self_sha256(run_start)
    run_start_path = output_root / "main_run_start.json"
    dump_json(run_start_path, run_start)

    event = {
        "event_kind": "STOP_EVENT",
        "event_index": 1,
        "previous_event_sha256": None,
        "phase_id": phase_id,
        "run_id": run_id,
        "producer": "main_protocol",
        "issued_at": OBSERVED_AT,
        "stop_reason": STOP_REASON,
    }
    event["event_sha256"] = sha256_bytes(canonical_bytes(event))
    event_path = output_root / "main_stop_event.json"
    dump_json(event_path, event)
    stop = {
        "schema_id": RUN_STOP_SCHEMA_ID,
        "schema_version": LIVE_PROTOCOL_VERSION,
        "receipt_id": "synthetic-main-stop",
        "phase_id": phase_id,
        "issued_at": OBSERVED_AT,
        "terminal_status": "EXTERNAL_HOLD",
        "stop_reason": STOP_REASON,
        "authorization_receipt_self_sha256": authorization["integrity"]["self_sha256"],
        "run_start_receipt_self_sha256": run_start["integrity"]["self_sha256"],
        "final_ledger_head_sha256": event["event_sha256"],
        "usage_snapshot_self_sha256": filler,
        "usage_snapshot_physical_sha256": filler,
        "preserved_artifact_manifest_sha256": filler,
        "integrity": {},
    }
    stop["integrity"]["self_sha256"] = self_sha256(stop)
    stop_path = output_root / "main_run_stop.json"
    dump_json(stop_path, stop)

    def self_binding(path: Path, value: Mapping[str, Any]) -> dict[str, str]:
        return {
            "relative_path": path.name,
            "physical_sha256": sha256_file(path),
            "self_sha256": value["integrity"]["self_sha256"],
        }

    def event_binding(path: Path, value: Mapping[str, Any]) -> dict[str, str]:
        return {
            "relative_path": path.name,
            "physical_sha256": sha256_file(path),
            "event_sha256": value["event_sha256"],
        }

    producer_values = []
    for role in sorted(producers):
        producer_values.append(dict(producers[role]))
    profile = {
        "schema_id": "HarnessTrustedMainAuthorityProfileV1",
        "schema_version": "1.0.0",
        "status": ZERO_PROVIDER_PROFILE,
        "issuer_id": ISSUER_ID,
        "authority_id": AUTHORITY_ID,
        "run_id": run_id,
        "phase_id": phase_id,
        "split_id": split_id,
        "parent_dataset": {
            "zip_physical_sha256": filler,
            "manifest_self_sha256": filler,
            "sense_identity_sha256": filler,
            "candidate_identity_sha256": filler,
            "context_identity_sha256": filler,
            "parent_candidate_count": len(candidates),
            "authorized_candidate_set_sha256": candidate_hash,
        },
        "protocol": {
            "status": "DRAFT4_PUBLIC_SURFACE_UNPROMOTED",
            "commit": PROTOCOL_COMMIT,
            "tree": PROTOCOL_TREE,
            "schemas": sorted(schema_files, key=lambda item: item["kind"]),
        },
        "producer_authorities": producer_values,
        "main_run_authority": {
            "live_authorization_receipt": self_binding(authorization_path, authorization),
            "run_start_receipt": self_binding(run_start_path, run_start),
            "run_stop_receipt": self_binding(stop_path, stop),
            "stop_event": event_binding(event_path, event),
        },
        "final_glossary_decision": None,
        "integrity": {},
    }
    profile["integrity"]["self_sha256"] = self_sha256(profile)
    profile_path = output_root / "profile.json"
    dump_json(profile_path, profile)
    raw = profile_path.read_bytes()
    loaded = load_trusted_authority_profile(
        profile_path,
        expected_physical_sha256=sha256_bytes(raw),
        expected_self_sha256=profile["integrity"]["self_sha256"],
        expected_issuer_id=ISSUER_ID,
        expected_authority_id=AUTHORITY_ID,
    )
    return {
        "path": profile_path,
        "physical_sha256": sha256_bytes(raw),
        "self_sha256": profile["integrity"]["self_sha256"],
        "issuer_id": ISSUER_ID,
        "authority_id": AUTHORITY_ID,
        "profile": loaded,
        "authorization": authorization_path,
        "run_start": run_start_path,
        "run_stop": stop_path,
        "stop_event": event_path,
    }
