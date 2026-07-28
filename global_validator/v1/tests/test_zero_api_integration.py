from __future__ import annotations

import json
import socket
from pathlib import Path

from global_validator.v1.audit import replay_run
from global_validator.v1.authority import verify_authority
from global_validator.v1.engine import run_global_validator

from .helpers import load_base_input, make_candidate_input


def test_five_sense_fifteen_candidate_development_pilot_is_zero_api(
    valid_input_path: Path,
    repository_root: Path,
    authority_receipt: Path,
    tmp_path: Path,
    config_factory,
    monkeypatch,
) -> None:
    authority = verify_authority(
        authority_receipt,
        repository_root / "terminology_contracts_v1",
        repository_root=repository_root,
    )
    base = load_base_input(valid_input_path)
    inputs = tmp_path / "inputs"
    inputs.mkdir()

    def forbid_network(*_args, **_kwargs):
        raise AssertionError("network access is forbidden in Global Validator")

    monkeypatch.setattr(socket, "create_connection", forbid_network)

    decisions = []
    certificates = 0
    replayed = 0
    candidate_ids: set[str] = set()
    sense_ids: set[str] = set()
    for sense_index in range(5):
        for candidate_index in range(3):
            payload = make_candidate_input(
                base,
                sense_index=sense_index,
                candidate_index=candidate_index,
                schema_dir=authority.schema_dir,
                gate_policy_path=authority.gate_policy_path,
                feature_registry_path=authority.feature_registry_path,
            )
            path = inputs / f"candidate-{sense_index}-{candidate_index}.json"
            path.write_text(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    indent=2,
                    allow_nan=False,
                )
                + "\n",
                encoding="utf-8",
            )
            run_id = f"pilot-{sense_index}-{candidate_index}"
            result = run_global_validator(
                path,
                config_factory(output_root=tmp_path / "runs", run_id=run_id),
            )
            decisions.append(result.decision["decision"])
            certificates += int(result.certificate is not None)
            replayed += int(replay_run(result.run_dir).matched)
            candidate_ids.add(result.global_input["candidate_key"]["candidate_id"])
            sense_ids.add(result.global_input["candidate_key"]["sense_id"])

    assert len(decisions) == 15
    assert len(candidate_ids) == 15
    assert len(sense_ids) == 5
    assert decisions == ["PROVISIONAL"] * 15
    assert certificates == 0
    assert replayed == 15
