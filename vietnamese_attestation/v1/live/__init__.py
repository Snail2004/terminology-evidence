"""Zero-provider E Live API and controlled-corpus tooling."""

from .aggregation import aggregate_candidate, build_attestation_package
from .common import LIVE_TOOL_SCHEMA_VERSION, LiveSchemaError
from .protocol_adapter import Draft4LifecycleAdapter
from .judge import FixtureJudge, make_judge_request, make_judge_response
from .ledger import EventLedger, verify_event_chain
from .policies import (
    make_aggregation_policy,
    make_budget,
    make_provider_role_plan,
    make_query_template_set,
    make_retrieval_policy,
)
from .registry import admit_source, make_registry, validate_registry
from .provider_adapters import GeminiOfficialAdapter
from .retrieval import FixtureDiscovery, FixtureFetcher, extract_snapshot_evidence
from .schemas import *
from .service import ELiveService
from .snapshot import build_snapshot, inspect_snapshot, verify_snapshot, zip_snapshot

__all__ = [
    "ELiveService",
    "Draft4LifecycleAdapter",
    "EventLedger",
    "FixtureDiscovery",
    "FixtureFetcher",
    "FixtureJudge",
    "GeminiOfficialAdapter",
    "LIVE_TOOL_SCHEMA_VERSION",
    "LiveSchemaError",
    "admit_source",
    "aggregate_candidate",
    "build_attestation_package",
    "build_snapshot",
    "extract_snapshot_evidence",
    "inspect_snapshot",
    "make_aggregation_policy",
    "make_budget",
    "make_judge_request",
    "make_judge_response",
    "make_provider_role_plan",
    "make_query_template_set",
    "make_registry",
    "make_retrieval_policy",
    "validate_registry",
    "verify_event_chain",
    "verify_snapshot",
    "zip_snapshot",
]
