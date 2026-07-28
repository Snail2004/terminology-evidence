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
