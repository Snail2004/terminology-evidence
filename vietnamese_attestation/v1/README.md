# Vietnamese Attestation Evidence V1

Status: REVIEW. The standalone implementation, CLI, tests and audit/replay
contracts are present in this owned version directory.

The implementing session owns only `vietnamese_attestation/**`. Evidence E is
independent from Context Substitution and never emits a final glossary
decision.

The public official boundary accepts a Dataset-owned set of 15
`FrozenCandidateContractV1@1.1.0` members only after its externally pinned
release receipt, manifest, physical member hashes, producer and identity joins
verify. A loose COMPLETE shared candidate is rejected unless the caller
explicitly selects fixture-only `--development-input`. Output remains
`AttestationEvidencePackageV1@1.1.0` under the locally published
`contracts-v1.1.0` authority.

The development pilot also has a deterministic zero-API runner. It executes
all 15 real pilot candidate identities against 15 synthetic fixture scenarios,
retains file audit streams and raw responses, verifies all replay modes, and
records zero external provider calls. Development pilot identities are not
projected to the shared contract because their effective sense contract,
Vietnamese surface authority, and domain anchors are intentionally unavailable.

Post-zero-API readiness is available through:

```powershell
python -m vietnamese_attestation.v1.cli.readiness `
  --repository-root <repository-root> `
  --authority-receipt terminology_contracts_v1\release\v1.1.0-final\contracts_v1_1_0_authority_receipt_r2.json `
  --zero-api-artifact-root <zero-api-artifact-root> `
  --controlled-registry dataset\dataset_methodology_hardening_v1\release\controlled_vietnamese_source_registry.jsonl `
  --dataset-release-zip <official-dataset-zip> `
  --dataset-input-pin <official-dataset-pin> `
  --junit <junit-report> `
  --output-root <release-output-root>
```

The readiness release reads source bytes from an exact Git commit, excludes
cache files without deleting the worktree, verifies Contracts V1.1 and the
accepted 15/15 zero-API replay, and reports any missing Dataset binding plus
the controlled-registry and live-canary HOLD states. With the exact official
Dataset supplied, only the controlled-registry and live-canary HOLD states
remain. It does not call a provider and never promotes fixture packages to
real attestation evidence authority.
The JUnit input is mandatory and must be the exact 80-test E-suite with zero
failures, errors or skips. Both the testcase identity set and E test-source
tree are hash-pinned.
