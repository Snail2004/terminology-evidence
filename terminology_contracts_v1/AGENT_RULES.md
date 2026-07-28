# Agent Integration Rules — MUST / MUST NOT

## Dataset / Sense agent

- MUST xuất immutable IDs, versions, manifest hash và reviewed sense-contract hash.
- MUST tạo artifact mới thay vì sửa artifact frozen.
- MUST NOT giả lập human labels.

## Context Substitution agent

- MUST nhận `FrozenCandidateContractV1`.
- MUST xuất `ContextEvidencePackageV1`.
- MUST preserve canonical sentence `context_id` trong evidence refs.
- MUST NOT trả final glossary decision.
- MUST NOT đọc E output.

## Vietnamese Attestation agent

- MUST nhận cùng `FrozenCandidateContractV1` với C.
- MUST xuất `AttestationEvidencePackageV1` với sáu E features.
- MUST preserve accepted/rejected evidence and replay provenance.
- MUST NOT đọc C output hoặc tự thêm allowed variants.
- Variant mới chỉ được đề xuất `PROPOSE_FOR_CST_VARIANT_CHECK`.

## Global Validator agent

- MUST validate schema, self-hash and all join keys before gates.
- MUST apply gates before scoring.
- MUST NOT emit `AUTO_APPROVED` under `DEVELOPMENT_HEURISTIC`.
- MUST bind a real `CalibrationArtifactV1` for `FROZEN_CALIBRATED`.
- MUST fail closed on contract mismatch.

## TAC agent

- MUST consume a sealed `TerminologyCertificateV1`.
- MUST operate per occurrence, not revalidate candidate from scratch.
- MUST record glossary/certificate/TAC policy versions.

## Breaking changes

- Adding optional fields: minor version.
- Tightening enum, changing meaning, deleting/renaming fields: major version.
- Every major version requires migration adapter and fixture tests.
