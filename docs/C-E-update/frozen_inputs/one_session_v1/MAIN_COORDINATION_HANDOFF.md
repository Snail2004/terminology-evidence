# Main Coordination Handoff: C + E One-Session V1

Status: `FROZEN_INPUTS_READY_FOR_PARALLEL_C_E_IMPLEMENTATION`

## Exact Bases

- Main: `7aaf1118dcc4a9a67bc9639d30b29062cffd28ef`
- C: `1bda670825034e715933c8f329aa958a994c8dcc`
- E: `48c701862671c73a5227aa34eaf8d029583986cc`

## C Inputs

- `FROZEN_BASES_V1.json`
- `FROZEN_CONTEXT_ROLE_MAP_V1.json`
- `UNDERFLOW_THREE_CANDIDATE_COHORT_V1.json`
- `ONE_SESSION_EXECUTION_BOUNDARY_V1.json`
- `Yeu_cau_Agent_C_One_Session_Narrow_Rework_V1.md`
- `Ke_hoach_Kien_truc_One_Session_C_E_BGE_M3_V1.md`

## E Inputs

- `FROZEN_BASES_V1.json`
- `EMBEDDING_MODEL_AUTHORITY_V1.json`
- `APPROVED_CANDIDATE_VARIANTS_V1.json`
- `UNDERFLOW_CANDIDATE_QUERY_PLANS_V1.json`
- `UNDERFLOW_THREE_CANDIDATE_COHORT_V1.json`
- `ONE_SESSION_EXECUTION_BOUNDARY_V1.json`
- `Yeu_cau_Agent_E_One_Session_BGE_M3_Retrieval_Rework_V1.md`
- `Ke_hoach_Kien_truc_One_Session_C_E_BGE_M3_V1.md`

LM Studio is user-managed and expected to remain available. E may use exact-model
auto-load and loopback requests. These calls are recorded as local loopback, not
provider or external-network calls.

## Test Policy

During implementation, run only tests covering changed behavior. Before each
child handoff, run the owned full suite exactly once. Do not rerun Contracts,
Global, Dataset, or the other producer's broad suite.

## Closed Boundaries

- Gold access: no.
- Full D0 remainder: hold.
- Provider and external-network calls during implementation: zero.
- Embedding cannot create or change attestation.
- Final glossary decision remains null.
