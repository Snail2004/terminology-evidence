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
