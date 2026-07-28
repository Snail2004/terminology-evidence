from __future__ import annotations

import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from context_substitution.v2.contracts.common import sha256_text
from context_substitution.v2.contracts.run import validate_context_substitution_run
from context_substitution.v2.providers.base import (
    ContextProviderRoute,
    FailoverStructuredModel,
    ProviderRawResponse,
)
from context_substitution.v2.providers.ledger import ProviderResponseLedger
from context_substitution.v2.runtime.calibration import validate_threshold_policy
from context_substitution.v2.runtime.engine import run_d2l_context_substitution
from context_substitution.v2.integration.common import seal_object


REPLAY_REPORT_SCHEMA_ID = "D2LContextSubstitutionReplayReportV1"
REPLAY_REPORT_SCHEMA_VERSION = "1.0.0"


def replay_context_run(
    *,
    input_payload: Mapping[str, Any],
    original_run: Mapping[str, Any],
    ledger_root: Path,
) -> dict[str, Any]:
    original = validate_context_substitution_run(original_run)
    plan = _ReplayPlan.load(Path(ledger_root))
    routes = _routes_for_replay(
        plan,
        route_order=original["execution_policy"]["provider_route_order"],
    )
    with tempfile.TemporaryDirectory(prefix="cst-replay-") as temporary:
        model = FailoverStructuredModel(
            routes,
            response_ledger=ProviderResponseLedger(Path(temporary) / "ledger"),
            audit_run_id="replay:" + original["integrity"]["run_sha256"][:24],
        )
        replayed = run_d2l_context_substitution(
            input_payload,
            model,
            candidate_target_ids=[
                candidate["candidate_id"] for candidate in original["candidates"]
            ],
            threshold_policy=validate_threshold_policy(
                original["execution_policy"]["threshold_policy"]
            ),
            evaluation_mode=original["execution_policy"]["evaluation_mode"],
        )
    plan.require_exhausted()
    original_hash = original["integrity"]["run_sha256"]
    replayed_hash = replayed["integrity"]["run_sha256"]
    if original_hash != replayed_hash:
        raise ValueError(
            "deterministic replay differs from the original normalized run: "
            f"{original_hash} != {replayed_hash}"
        )
    report = {
        "schema_id": REPLAY_REPORT_SCHEMA_ID,
        "schema_version": REPLAY_REPORT_SCHEMA_VERSION,
        "status": "PASS",
        "original_run_sha256": original_hash,
        "replayed_run_sha256": replayed_hash,
        "provider_attempt_count": len(plan.attempts),
        "raw_response_count": plan.raw_response_count,
        "raw_response_hashes_verified": plan.raw_response_count,
        "provider_call_count": 0,
        "normalized_output_equal": True,
        "final_glossary_decision": None,
        "integrity": {},
    }
    return seal_object(report, integrity_key="report_sha256")


@dataclass
class _ReplayPlan:
    root: Path
    attempts: list[dict[str, Any]]
    cursor: int
    raw_response_count: int

    @classmethod
    def load(cls, root: Path) -> "_ReplayPlan":
        attempt_path = root / "provider_attempts.jsonl"
        rows = [
            json.loads(line)
            for line in attempt_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        attempts = [dict(row) for row in rows if row.get("record_kind") == "PROVIDER_ATTEMPT"]
        if not attempts:
            raise ValueError("provider ledger contains no replayable attempts")
        raw_count = 0
        for index, row in enumerate(attempts):
            required = {
                "provider_route_id",
                "model_id",
                "model_family",
                "independence_group",
                "tag",
                "request_sha256",
                "retry_index",
                "accepted",
            }
            missing = sorted(required - set(row))
            if missing:
                raise ValueError(
                    f"provider attempt {index} lacks replay fields: {', '.join(missing)}"
                )
            ref = row.get("raw_response_ref")
            if ref is None:
                continue
            target = root / Path(str(ref))
            data = target.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if digest != row.get("raw_response_sha256"):
                raise ValueError(f"raw response hash mismatch at attempt {index}")
            raw_count += 1
        return cls(root=root, attempts=attempts, cursor=0, raw_response_count=raw_count)

    def sender(self, route_id: str) -> Callable[..., ProviderRawResponse]:
        def send(
            *,
            system_prompt: str,
            user_payload_json: str,
            response_schema: Mapping[str, Any],
            max_output_tokens: int,
            tag: str,
        ) -> ProviderRawResponse:
            del system_prompt, response_schema, max_output_tokens
            if self.cursor >= len(self.attempts):
                raise AssertionError("replay requested an attempt beyond the ledger")
            row = self.attempts[self.cursor]
            self.cursor += 1
            if row["provider_route_id"] != route_id or row["tag"] != tag:
                raise AssertionError(
                    "replay order mismatch: "
                    f"expected {row['provider_route_id']}:{row['tag']}, got {route_id}:{tag}"
                )
            if row["request_sha256"] != sha256_text(user_payload_json):
                raise AssertionError(f"replay request hash mismatch for {tag}")
            ref = row.get("raw_response_ref")
            if ref is None:
                raise ConnectionError(str(row.get("failure_reason") or "replayed transport failure"))
            text = (self.root / Path(str(ref))).read_text(encoding="utf-8")
            return ProviderRawResponse(
                text=text,
                payload=None,
                request_id=row.get("request_id"),
                input_tokens=int(row.get("input_tokens", 0)),
                output_tokens=int(row.get("output_tokens", 0)),
                reasoning_tokens=int(row.get("reasoning_tokens", 0)),
                cached=bool(row.get("cached", False)),
                latency_ms=int(row.get("latency_ms", 0)),
            )

        return send

    def require_exhausted(self) -> None:
        if self.cursor != len(self.attempts):
            raise ValueError(
                f"replay consumed {self.cursor}/{len(self.attempts)} provider attempts"
            )


def _routes_for_replay(
    plan: _ReplayPlan, *, route_order: Sequence[str]
) -> list[ContextProviderRoute]:
    first_by_route: dict[str, Mapping[str, Any]] = {}
    for row in plan.attempts:
        first_by_route.setdefault(str(row["provider_route_id"]), row)
    routes: list[ContextProviderRoute] = []
    for route_id in route_order:
        row = first_by_route.get(str(route_id))
        if row is None:
            routes.append(
                ContextProviderRoute(
                    route_id=str(route_id),
                    model_id=f"replay-unused-{route_id}-pinned-v1",
                    model_family=f"replay-unused-{route_id}",
                    independence_group=f"replay-unused-{route_id}",
                    sender=_unused_route_sender(str(route_id)),
                )
            )
            continue
        routes.append(
            ContextProviderRoute(
                route_id=str(route_id),
                model_id=str(row["model_id"]),
                model_family=str(row["model_family"]),
                independence_group=str(row["independence_group"]),
                sender=plan.sender(str(route_id)),
            )
        )
    return routes


def _unused_route_sender(route_id: str):
    def send(**_: Any) -> ProviderRawResponse:
        raise AssertionError(f"sealed but unused replay route was called: {route_id}")

    return send
