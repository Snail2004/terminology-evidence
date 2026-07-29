# Context Substitution V2.3 Version Matrix

| Layer | Active identity | Notes |
|---|---|---|
| Package path | `context_substitution/v2` | Stable major namespace; C-owned only |
| Runtime run schema | `D2LContextSubstitutionRunV2` / `2.3.0` | Sealed provider role plan, split request indices, raw replay, and calibration bindings; `2.2.0` remains immutable legacy |
| Runtime input schema | `D2LContextSubstitutionInputV2` / `2.2.0` | V3/Pilot origin plus reviewed-selection contract |
| Reviewed adapter | `D2LContextSubstitutionReviewedSupportAdapterV1` / `1.0.0` | Reads V3 and Pilot V1.1 directories or ZIPs |
| Adapter receipt | `D2LContextSubstitutionAdapterReceiptV1` / `1.0.0` | Self-hashed, zero-API, decision-neutral |
| Support freeze schema | `D2LContextSupportSetFreezeV1` / `1.0.0` | Legacy immutable preparation contract remains supported |
| Gold evaluation schema | `D2LContextSubstitutionGoldEvaluationV2` / `2.0.0` | Evaluation-only; unchanged |
| Calibration artifact | `CSTCalibrationArtifactV1` / `1.0.0` | Nonzero dataset/gold hashes and measured precision floor |
| Selector | `d2l_context_selector_v2_1` | Model-classified development or frozen human-reviewed rows |
| Trial translator | `d2l_context_trial_translator_v2_1` | Literal/expansion surface binding |
| Trial quality gate | `d2l_trial_translation_quality_gate_v2_1` | External-error separation |
| Context Judge | `d2l_context_judge_v2_1` | Pinned model identity; no Gemini-only restriction |
| Aggregation | `d2l_context_aggregate_normalized_v2_1` | Missing contrastive/type coverage cannot become eligible |
| Raw replay | `CONTENT_ADDRESSED_V1` | Required for frozen execution |
| Provider role plan V1 | `cst_live_role_routing_v1` / `ContextSubstitutionProviderRolePlanV1` `1.0.0` | Immutable Gemini-primary replay authority; self `cff7bbf...d3085d9`, physical `1f62b9a...a80315` |
| Provider role plan V2 | `cst_live_role_routing_gpt_primary_v2` / `ContextSubstitutionProviderRolePlanV1` `1.0.0` | Pre-D0 GPT-primary policy revision; V1 is not overwritten; self `155261f...3e815`, physical `6a22943...52e61` |
| Provider ledger manifest | `ContextSubstitutionProviderLedgerManifestV1` / `1.1.0` | Exact ordered run/ledger and raw-response-set binding |
| Shared authority | `contracts-v1.1.0` / `38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed` | Official immutable C/E/Global contract authority |
| Context evidence output | `ContextEvidencePackageV1` / `1.1.0` | Candidate/input/provenance bound; C gate signals only; final decision null |
| Local package-set manifest | `ContextEvidencePackageSetManifestC1` / `1.1.0` | `COMPLETE` for Dataset-authority inputs; `SYNTHETIC_LOCAL_CONFORMANCE` for synthetic fixtures |
| External consumer | Global Validator V1.1 / canonical integration `b87a1458b3bb0da20792a308769ae0da4442f7e3` | Active consumer; C does not import or inspect Global internals |
| Finalized reviewed selection input | `D2LContextSubstitutionFinalizedReviewedSelectionV1` / `1.0.0` | Dataset authority output only; no C-side vote resolution |
| Development candidate fixture | `ContextSubstitutionTestCandidateFixtureV1` / `1.0.0` | Test-only HOLD; cannot enter official projection |
| Integration release audit | `ContextSubstitutionIntegrationReleaseAuditV1` / `1.1.0` | RC2 fail-closed semantic evidence gate |
| Development threshold policy | `d2l_context_status_development_heuristic_v2_1` | Cannot authorize frozen test-set evidence |
| Frozen threshold policy | Calibration-artifact-selected version | Requires exact calibration artifact ref/hash |
| CLI module | `context_substitution.v2` | Validate, adapt, run, replay, project, release, and gold-evaluate |

Legacy V2.2 payloads retain their original global-route validation and replay
semantics; they are not silently reinterpreted as V2.3. Legacy term-evidence
V1 remains a compatibility projection and rejects lossy merged two-judge
evidence.

Provider role plan V2 was selected before D0 for quota balance and
cross-family independence. No claim of superiority over V1 is made. A
comparative A/B provider-plan pilot is waived; a separately authorized
one-candidate operational canary remains required before D0.
