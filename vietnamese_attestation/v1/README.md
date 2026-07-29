# Vietnamese Attestation Evidence V1

Status: REVIEW. The standalone implementation, CLI, tests and audit/replay
contracts are present in this owned version directory.

The implementing session owns only `vietnamese_attestation/**`. Evidence E is
independent from Context Substitution and never emits a final glossary
decision.

The public standalone boundary accepts `FrozenCandidateContractV1@1.1.0` and
emits `AttestationEvidencePackageV1@1.1.0` under the locally published
`contracts-v1.1.0` authority. The richer internal V1.1 package remains a
content-bound replay ledger and is not a competing shared contract.

The development pilot also has a deterministic zero-API runner. It executes
all 15 real pilot candidate identities against 15 synthetic fixture scenarios,
retains file audit streams and raw responses, verifies all replay modes, and
records zero external provider calls. Development pilot identities are not
projected to the shared contract because their effective sense contract,
Vietnamese surface authority, and domain anchors are intentionally unavailable.

Post-zero-API readiness is available through:

```powershell
python -m vietnamese_attestation.v1.cli.readiness `
  --repository-root C:\work\terminology_evidence-worktrees\vietnamese-attestation-v1 `
  --authority-receipt C:\work\terminology-evidence-authority\contracts-v1.1.0\authority_receipt.json `
  --zero-api-artifact-root C:\work\terminology-evidence-artifacts\vietnamese-attestation-v1.1-zero-api-20260729-v3 `
  --controlled-registry dataset\dataset_methodology_hardening_v1\release\controlled_vietnamese_source_registry.jsonl `
  --output-root C:\work\terminology-evidence-artifacts\vietnamese-attestation-v1.1-post-zero-api-rc1
```

The readiness release reads source bytes from an exact Git commit, excludes
cache files without deleting the worktree, verifies Contracts V1.1 and the
accepted 15/15 zero-API replay, and reports the remaining Dataset, controlled
registry, and live-canary HOLD states. It does not call a provider and never
promotes fixture packages to real attestation evidence authority.
