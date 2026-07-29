# YÊU CẦU TIẾP THEO CHO AGENT E SAU ZERO-API MILESTONE V1.1

**Document ID:** `agent-e-post-zero-api-v1.2.1`
**Owner:** Vietnamese Attestation Evidence Agent
**Trạng thái:** `ACTIVE — SHARED PROJECTION AND REAL-PILOT READINESS`
**Không mở rộng kiến trúc lõi E ngoài các sửa lỗi integration bắt buộc.**

**Correction status:** metadata and readiness semantics aligned with the accepted
zero-API rework and canonical main on 2026-07-29.

---

## 1. Mốc đã được chấp nhận

Zero-API milestone của E đã được tích hợp vào canonical `main`.

```text
zero-API integration commit:
a1707a8bee02605032fd401e287b17a00b89aae4

accepted E final tip:
a1707a8bee02605032fd401e287b17a00b89aae4

legacy uploaded review ZIP SHA-256 (review evidence only, not runtime authority):
db3d15c22aa59a412d3c4e0c2deb6b361ea52fc48d169f77c8adc154162bf76e

canonical main at V1.2.1 review:
677ef6b434f268153363ea06b335cb8df188ee19
```

Kết quả đã hoàn thành:

```text
15/15 development pilot candidate identities
15/15 deterministic replay PASS
0 external API/provider calls
59 fixture attempts
52 raw responses
15/15 final_glossary_decision = null
273 manifest files
0 manifest/hash error
66/66 full E tests PASS before readiness rework
75/75 full E tests PASS after R2 readiness compatibility rework
8/8 focused readiness tests PASS after readiness rework
```

Không chạy lại hoặc viết lại zero-API pipeline trừ khi regression test mới phát hiện lỗi.

---

## 2. Hai trạng thái HOLD hiện tại là đúng

### HOLD-1 — Controlled registry authority chưa có dữ liệu

```text
CONTROLLED_VIETNAMESE_REGISTRY_EMPTY
retrieval_provider_created = false
```

Không được tạo retrieval provider giả, không tự thêm source row và không lấy
fixture làm authority.

### HOLD-2 — Pilot hiện tại chưa đủ identity để project sang shared contract

Thiếu các trường authority như:

```text
effective_sense_contract_sha256
canonical Vietnamese surface
validated/rejected Vietnamese variants
domain_id
Vietnamese/English domain anchors
official input_contract_sha256
```

Do đó:

```text
projected_package_count = 0
status = BLOCKED_DEVELOPMENT_IDENTITY
```

Không được bỏ HOLD bằng cách:

```text
tự sinh hash
điền placeholder
dùng source term tiếng Anh làm Vietnamese surface
tạo domain anchor từ Model
tự phát hành FrozenCandidateContract
```

Hai HOLD này phải được giữ cho đến khi Dataset Adapter cung cấp artifact chính
thức.

---

# 3. Mục tiêu tiếp theo

Agent E chuyển từ:

```text
ZERO_API_IMPLEMENTATION
```

sang:

```text
OFFICIAL_SHARED_PROJECTION_READY
→ PROVIDER_COMPATIBILITY_CANARY
→ REAL_DEVELOPMENT_PILOT
→ GLOBAL HANDOFF
```

Mục tiêu gần nhất không phải calibration hoặc `AUTO_APPROVED`.

Mục tiêu gần nhất là tạo được:

```text
15 offline projection-conformance AttestationEvidencePackageV1@1.1.0
```

từ:

```text
15 Dataset-owned FrozenCandidateContractV1@1.1.0
+ E internal evidence runs
```

Global Validator executable đã được tích hợp vào canonical main. Đây không còn
là code blocker của E; handoff vẫn bị chặn cho đến khi E có real-pilot evidence
packages từ authority và provider/source plan hợp lệ.

---

# 4. Phase A — Freeze và làm sạch integration release

Tạo một release mới từ exact Git commit, không thay đổi semantic algorithm.

Bắt buộc:

```text
loại .pyc khỏi release
loại __pycache__ khỏi release
loại .pytest_cache khỏi release
giữ source/test/CLI đầy đủ
pin canonical main commit và E commit
pin Contracts authority
```

Không xóa cache trực tiếp trong worktree. Release phải đọc exact bytes từ Git
object database hoặc clean detached worktree và dùng inclusion manifest.

Artifact:

```text
vietnamese_attestation_v1_1_post_zero_api_rc1.zip
vietnamese_attestation_v1_1_post_zero_api_rc1.zip.sha256
manifest.json
CHECKSUMS.sha256
git_commit_receipt.json
commands.txt
environment.json
junit.xml
static_scan.json
credential_scan.json
ownership_scan.json
```

`git_commit_receipt.json` tối thiểu phải có:

```text
repository
branch
implementation_commit
parent/merge_base
canonical_main_commit
git_status_porcelain
git_diff_check
owned_paths
```

---

# 5. Phase B — Khóa contract authority và shared bridge

Adopt đúng:

```text
authority tag:
contracts-v1.1.0

authority commit:
38bc1c1b888c97d53d40bfd61264cd8f1a66a6ed

contracts manifest SHA-256:
e0dd96cd1c33e7d27df802c3de42d8ad6979e29204b741591f1ab445905a500b

GatePolicy SHA-256:
9f31e4579350e2f74dc1ec01632d8cd49802b5e7ee6f00931b71d430e5d9f4f2
```

Contract authority receipt có thể được maintainer reseal riêng. E không sửa
`terminology_contracts_v1/**`.

Shared bridge phải giữ kiến trúc:

```text
Dataset-owned FrozenCandidateContractV1
        ↓
E adapt_shared_frozen_candidate
        ↓
E internal VietnameseAttestationPackageV1
        ↓
project_shared_attestation_package
        ↓
AttestationEvidencePackageV1@1.1.0
```

E không được có production path:

```text
raw Dataset row
→ tự tạo official FrozenCandidate
```

---

# 6. Phase C — Hợp đồng đầu vào cần Dataset Agent cung cấp

E phải tạo một file:

```text
E_DATASET_INPUT_REQUIREMENTS_V1.md
```

và gửi Dataset Agent/Main Manager.

Mỗi candidate chính thức phải có:

```text
schema_id = FrozenCandidateContractV1
schema_version = 1.1.0
binding_status = COMPLETE

candidate_key.candidate_id
candidate_key.candidate_version
candidate_key.source_term
candidate_key.candidate_vi
candidate_key.sense_id
candidate_key.scope_id
candidate_key.sense_inventory_version
candidate_key.dataset_manifest_sha256
candidate_key.effective_sense_contract_sha256

effective_definition_en

surfaces.canonical_vi
surfaces.validated_variants_vi
surfaces.rejected_variants_vi

domain_profile.domain_id
domain_profile.anchors_vi
domain_profile.anchors_en

input_contract_sha256
integrity.self_sha256
```

E phải fail closed khi:

```text
effective sense hash thiếu hoặc sai
candidate identity drift
candidate version drift
scope/sense mismatch
dataset manifest mismatch
canonical Vietnamese surface rỗng
domain profile không có authority
input contract hash mismatch
nested self-hash mismatch
```

---

# 7. Phase D — Official shared projection

Khi nhận 15 Frozen Candidate chính thức:

```text
1. Validate shared FrozenCandidate.
2. Adapt sang E internal FrozenCandidate.
3. Chạy fixture/offline E pipeline chỉ để kiểm tra projection conformance.
4. Project internal package sang shared package.
5. Validate bằng official schema và semantic validator.
6. Seal package.
7. Replay từ raw ledger.
8. So sánh exact semantic result.
```

Output:

```text
15 AttestationEvidencePackageV1@1.1.0 conformance packages
15 package self-hashes
projection manifest
projection report
replay report
```

Các package Phase D là `OFFLINE_PROJECTION_CONFORMANCE_ONLY`. Chúng không phải
real attestation evidence authority, không được dùng cho accuracy claim và không
được bàn giao như official real-pilot package. Official E evidence package chỉ
được tạo từ Phase G sau khi authority, registry/source plan và provider canary
đều PASS.

Mỗi package phải có:

```text
candidate_key exact
input_contract_sha256 exact
features
stage_metrics
local_status
accepted_evidence_refs
rejected_evidence_refs
observed_variants
provenance
gate_signals
diagnostics
final_glossary_decision = null
integrity.self_sha256
```

Không được project current incomplete pilot identity bằng placeholder.

---

# 8. Gate-signal policy của E

E chỉ assert signal. E không chọn action.

Exact E-owned signals:

```text
concept_mismatch
contradiction
judge_disagreement
insufficient_evidence
attestation_unjudgeable
```

## 8.1. `concept_mismatch`

Chỉ assert khi có direct evidence:

```text
judgeability = JUDGEABLE
candidate_role = TECHNICAL_TERM
concept_relation = DIFFERENT
domain_match = true
```

`evidence_refs` phải trỏ trực tiếp tới evidence rows gây mismatch.

Không dùng whole-package fallback cho signal này.

## 8.2. `contradiction`

Chỉ assert khi có đồng thời:

```text
accepted SAME evidence
+
domain-matched DIFFERENT evidence
```

Refs phải gồm direct SAME và DIFFERENT evidence liên quan.

## 8.3. `judge_disagreement`

Trong V1.1 hiện tại, transport fallback không phải semantic disagreement.

Giữ:

```text
asserted = false
```

cho đến khi có thiết kế multi-judge hoặc second independent Judge được review.

Không suy diễn disagreement chỉ vì:

```text
provider timeout
fallback route
schema-invalid response
```

## 8.4. `insufficient_evidence`

Có thể dùng:

```text
direct evidence refs
hoặc
sealed internal ledger ref khi không có evidence row
```

Bắt buộc reason codes theo coverage/threshold thật.

## 8.5. `attestation_unjudgeable`

Có thể dùng ledger fallback khi không có direct evidence, với reason codes như:

```text
JUDGE_ROUTE_EXHAUSTED
SEARCH_PROVIDER_FAILED
PARTIAL_RETRIEVAL_COVERAGE
ATTESTATION_UNJUDGEABLE
```

## 8.6. Cấm

E không xuất:

```text
CAP_PROVISIONAL
ESCALATE_HUMAN
FATAL_REJECT
FATAL_SPLIT
AUTO_APPROVED
PROVISIONAL
REJECTED
```

---

# 9. Phase E — Controlled Vietnamese Registry

Dataset Agent sở hữu registry authority. E chỉ là consumer.

Trước khi tạo provider, E phải nhận:

```text
non-empty registry
registry physical SHA-256
registry manifest
retrieval-content schema/version
content payload hoặc immutable content refs
```

Identity tối thiểu:

```text
source_id
organization_id
document_id
content_hash
dedup_group_id
source_tier
```

Để retrieval thực sự hoạt động, handoff còn cần:

```text
canonical_uri hoặc artifact_ref
content_ref
content_mime_type
language
title
publication/organization metadata
license/provenance
retrieved_at hoặc publication date
```

E phải tạo:

```text
CONTROLLED_REGISTRY_CONSUMER_REQUIREMENTS_V1.md
```

Không sửa shared contracts để thêm registry schema trong giai đoạn này.

## Provider behavior

Khi authority sẵn sàng:

```text
controlled corpus
→ reviewed cache
→ open-web search
```

Mọi controlled source vẫn phải qua:

```text
content-hash verification
candidate-span detection
Vietnamese-language gate
concept Judge
domain Judge
source-tier policy
dedup
organization independence
machine-translation suspicion
```

Không auto-accept chỉ vì source nằm trong registry.

## D2L-VI

D2L-VI glossary/bản dịch có vai trò:

```text
candidate origin
hoặc Tier-3 attestation evidence
```

Không được một mình làm candidate đó `ATTESTED` hoặc mở production approval.

---

# 10. Phase F — Provider compatibility canary

Chỉ bắt đầu sau khi:

```text
zero-API release vẫn green
official Dataset-owned input có sẵn
authority verification PASS
secret loading an toàn
explicit maintainer approval cho live calls
```

Canary phải chạy từng route riêng.

## Search-only canary

```text
2–3 development candidates
Brave hoặc configured Search provider
không gọi Judge thật nếu đang test Search
```

Đo:

```text
request success
schema-valid search result
URL normalization
fetch/extraction success
retry/timeout
raw-response retention
replay
latency/cost
```

## Judge-only canary

Dùng frozen snippets, chạy riêng:

```text
ShopAI
CKey
Gemini official
```

Đo:

```text
schema-valid output
SAME/RELATED/DIFFERENT/UNCERTAIN distribution
invalid response
retry/fallback
token/cost
raw retention
replay
```

Chỉ sau khi từng route pass mới test fallback chain:

```text
ShopAI → CKey → Gemini
```

Một kết quả semantic hợp lệ như `DIFFERENT` hoặc `UNCERTAIN` không được trigger
fallback.

Canary là:

```text
ENGINEERING_COMPATIBILITY_ONLY
NOT_FOR_CALIBRATION
NOT_FOR_ACCURACY_CLAIMS
```

---

# 11. Phase G — Real development semantic pilot

Chỉ chạy đủ 15 candidates khi:

```text
15 official Dataset-owned Frozen Candidates
Effective Sense authority đầy đủ
controlled registry provider PASS hoặc có approved pilot source plan
Search/Judge canaries PASS
projection conformance PASS
```

Mode:

```text
DEVELOPMENT_SEMANTIC_PILOT
```

Không dùng validation/test.

Báo riêng:

```text
retrieval yield
fetch yield
extraction yield
candidate-span yield
Vietnamese-language yield
judge yield
accepted evidence rate
SAME/RELATED/DIFFERENT/UNCERTAIN
duplicate-cluster rate
organization independence
source-tier distribution
controlled/open-web evidence count
machine-translation suspicion
unjudgeable rate
insufficient-evidence rate
cost per candidate
```

`INSUFFICIENT_EVIDENCE` là kết quả hợp lệ, không phải lỗi cần che giấu.

---

# 12. Human evidence-cluster review pack

Sau real pilot, E tạo review pack cho evidence clusters.

Reviewer nhận:

```text
candidate + effective sense + scope
source metadata
snippet/span
Judge result
dedup cluster
organization identity
source tier
```

Reviewer chấm:

```text
SAME
RELATED
DIFFERENT
UNCERTAIN
domain match
technical-term role
source authority
machine-translation suspicion
dedup correctness
organization independence
accept/reject evidence
```

Reviewer không được thấy:

```text
Global decision
calibration threshold
other reviewer output
```

Nhãn này phục vụ:

```text
Judge evaluation
source policy evaluation
dedup evaluation
later calibration
```

Không biến thành runtime dictionary.

---

# 13. Phase H — Handoff cho Global Validator

E bàn giao:

```text
15 official AttestationEvidencePackageV1
package manifest
package hashes
input contract hashes
raw ledger refs
replay report
projection report
gate-signal coverage report
```

Global integration phải chứng minh:

```text
identity/hash join exact
mismatch fail closed
E gate signals project đúng
E không có final decision
development mode không AUTO_APPROVED
development mode không certificate
replay không gọi API
```

Không gửi current zero-API fixture package như production authority.

---

# 14. Regression tests bắt buộc

Giữ toàn bộ 63 tests hiện có và thêm tối thiểu:

```text
1. missing effective_sense_contract_sha256 → reject
2. fake effective sense hash → reject
3. missing canonical Vietnamese surface → reject
4. missing domain anchors/authority → reject
5. candidate/input hash mismatch → reject
6. internal package bound to another Frozen Candidate → reject
7. concept_mismatch without direct DIFFERENT refs → reject
8. contradiction without direct SAME + DIFFERENT refs → reject
9. transport fallback does not assert judge_disagreement
10. ATTESTED with empty accepted evidence → reject
11. ATTESTED below cluster/org/source thresholds → reject
12. registry physical hash mismatch → reject
13. controlled source content hash mismatch → reject
14. duplicate registry source_id → reject
15. unknown source tier → reject
16. replay calls provider → fail
17. replay semantic output drift → fail
18. final_glossary_decision non-null → reject
19. E output containing global gate action → reject
20. current incomplete pilot remains projection HOLD
```

---

# 15. Artifact bàn giao tiếp theo

```text
vietnamese_attestation_v1_1_post_zero_api_rc1.zip
vietnamese_attestation_v1_1_post_zero_api_rc1.zip.sha256

git_commit_receipt.json
manifest.json
CHECKSUMS.sha256
junit.xml
commands.txt
environment.json
static_scan.json
credential_scan.json
ownership_scan.json

E_DATASET_INPUT_REQUIREMENTS_V1.md
CONTROLLED_REGISTRY_CONSUMER_REQUIREMENTS_V1.md

authority_verification_report.json
dataset_input_conformance_report.json
controlled_registry_adapter_report.json
provider_canary_report.json
pilot_semantic_summary.json

provider_attempts.jsonl
raw_responses/
replay_report.json

shared_attestation_packages/
shared_projection_manifest.json
shared_projection_report.json
gate_signal_coverage_report.json
```

Các artifact chưa chạy phải ghi rõ:

```text
NOT_EXECUTED
BLOCKED_BY_DATASET_AUTHORITY
BLOCKED_BY_CONTROLLED_REGISTRY
BLOCKED_BY_LIVE_CANARY_APPROVAL
```

Không tạo report giả để đủ tên file.

---

# 16. Definition of Done tiếp theo

E đạt `READY_FOR_REAL_DEVELOPMENT_PILOT` khi:

1. Zero-API milestone vẫn replay 15/15.
2. Source release sạch cache và có Git receipt.
3. Exact Contracts authority verification PASS.
4. Nhận 15 Dataset-owned Frozen Candidates COMPLETE.
5. 15 shared projections PASS official validation.
6. Gate signals có direct refs đúng policy.
7. Controlled registry consumer đã fail-closed và có authority hợp lệ.
8. Provider canaries từng route PASS; trạng thái HOLD chưa đạt readiness này.
9. `final_glossary_decision` luôn `null`.
10. Không dùng validation/test.
11. Không calibration hoặc phát production certificate.

E chỉ đạt `READY_FOR_GLOBAL_HANDOFF` sau khi real development pilot có raw
ledger, deterministic replay, 15 real-pilot E packages hợp lệ và Global
Validator consume exact identity/hash thành công.

---

# 17. Không thuộc phạm vi hiện tại

Agent E chưa làm:

```text
full 450-candidate live run
validation/test
threshold freeze
human-frozen CalibrationArtifact
production AUTO_APPROVED
production certificate
sửa common contracts
sửa Dataset authority
tự phát hành Frozen Candidate
multi-domain benchmark lớn
```

---

# 18. Prompt giao trực tiếp cho Agent E

```text
Zero-API milestone của Vietnamese Attestation Evidence V1.1 đã được chấp nhận
và tích hợp vào canonical main tại
a1707a8bee02605032fd401e287b17a00b89aae4.

Không viết lại zero-API pipeline và không mở rộng semantic architecture.
Chuyển sang shared projection và real-pilot readiness.

Giữ nguyên hai HOLD:
1. controlled registry rỗng → không tạo retrieval provider;
2. pilot thiếu effective-sense hash, Vietnamese surfaces và domain authority
   → không project shared package bằng placeholder.

Thực hiện theo thứ tự:

1. Tạo clean post-zero-API release có manifest, checksums, Git receipt,
   tests và scan reports.
2. Pin exact contracts-v1.1.0 authority.
3. Phát hành E_DATASET_INPUT_REQUIREMENTS_V1.md cho Dataset Agent.
4. Chỉ consume Dataset-owned FrozenCandidateContractV1@1.1.0 COMPLETE.
5. Khi nhận 15 official inputs, chạy adapt → internal E → shared projection,
   tạo 15 offline projection-conformance packages và replay exact; không gọi
   chúng là real attestation evidence authority.
6. Giữ E-owned gate signals; không chọn action. Fatal semantic signals phải có
   direct evidence refs. Transport fallback không phải judge disagreement.
7. Phát hành CONTROLLED_REGISTRY_CONSUMER_REQUIREMENTS_V1.md.
8. Không tạo controlled retrieval provider cho đến khi registry và content
   schema có authority.
9. Sau explicit approval, chạy Search/Judge provider canaries riêng từng route.
10. Sau khi canary và registry/input authority pass, chạy real development pilot
    5 senses/15 candidates.
11. Bàn giao 15 official E packages cho Global Validator.
12. Không dùng validation/test, không calibration và không production claim.

Báo lại:
- branch/commit/main base;
- release ZIP và SHA;
- authority verification;
- Dataset input readiness;
- controlled registry readiness;
- shared projection count;
- gate-signal coverage;
- provider canary status;
- replay status;
- remaining HOLD/blockers.
```
