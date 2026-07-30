# KẾ HOẠCH KIẾN TRÚC THAY ĐỔI C + E TRONG MỘT PHIÊN

**Phiên bản:** V1  
**Mục tiêu:** đóng narrow rework của C và E trong một phiên kỹ thuật, sau đó tạo gói regression review cho đúng sense `underflow` với 3 candidates.

## 1. Phạm vi phiên

Phiên này chỉ thay đổi:

```text
C:
- freeze context role theo context_id;
- arbitration khi hai judge bất đồng critical.

E:
- candidate-specific acquisition plan;
- BGE-M3 local dense embedding để xếp hạng lead và occurrence;
- exact-span gate giữ nguyên;
- reason codes chi tiết;
- telemetry tách embedding/local/network/provider.

Integration:
- chạy regression lại 3 candidates của sense underflow;
- Global chỉ replay theo output mới;
- đóng gói independent-review package.
```

Không thay đổi:

```text
- Dataset cohort;
- sense definition;
- candidate identities;
- C rubric;
- C score aggregation;
- E positive-evidence predicate;
- E source independence rule;
- Global decision architecture;
- Stage-B gold;
- calibration thresholds;
- full D0 cohort.
```

## 2. Trạng thái đầu vào

Sense regression:

```text
source_term:
underflow

sense_id:
d2lce_9bd5113780f8e8160a24e6ad

candidates:
- tràn dưới
- tụt dưới ngưỡng số học
- mất chính xác do quá nhỏ
```

Các vấn đề cần đóng:

```text
C-ISSUE-01:
context_type thay đổi giữa các candidate.

C-ISSUE-02:
một primary judge có thể phát fatal semantic gate dù secondary judge đánh giá ngược lại.

E-ISSUE-01:
hai candidate mới tái sử dụng snapshot không có exact span.

E-ISSUE-02:
Judge không được gọi vì retrieval recall thấp.

E-ISSUE-03:
ATTESTATION_UNJUDGEABLE chưa cho biết thất bại ở acquisition, span hay Judge.

E-ISSUE-04:
recorded/local embedding telemetry cần tách khỏi provider/network calls.
```

## 3. Kiến trúc đích

```text
                         FROZEN DATASET / COHORT
                                  |
                    +-------------+-------------+
                    |                           |
                    v                           v
              C CONTEXT PATH               E EVIDENCE PATH
                    |                           |
        frozen context_role_map                 |
                    |                 candidate-specific queries
          primary + secondary                   |
                    |                 lexical lead collection
            critical arbitration                |
                    |                 BGE-M3 lead ranking
          decision-neutral C output             |
                    |                    fetch/extract
                    |                           |
                    |                 exact candidate/variant span
                    |                           |
                    |                 occurrence window generation
                    |                           |
                    |                 BGE-M3 occurrence ranking
                    |                           |
                    |                    top snippets/document
                    |                           |
                    |                       E Judge
                    |                           |
                    +-------------+-------------+
                                  |
                             GLOBAL REPLAY
                                  |
                    DEVELOPMENT DECISION ONLY
```

## 4. Thay đổi C

### C-01 — Frozen context-role map

Tạo một artifact duy nhất:

```json
{
  "schema_id": "FrozenContextRoleMapV1",
  "sense_id": "d2lce_9bd5113780f8e8160a24e6ad",
  "contexts": [
    {
      "context_id": "ctx_...",
      "context_type": "definition"
    }
  ]
}
```

Quy tắc:

```text
- context_type là thuộc tính của context trong sense;
- không được suy ra lại theo candidate;
- tất cả candidate dùng cùng context_id, context_type và coverage rule;
- hash artifact phải được bind vào từng C run.
```

### C-02 — Critical disagreement arbitration

Quy tắc mới:

```text
Nếu:
primary semantic_equivalence <= 2
và secondary semantic_equivalence >= 3

thì:
CRITICAL_JUDGE_DISAGREEMENT = true
fatal semantic gate = suppressed
C recommendation tối đa = HUMAN_REVIEW_REQUIRED
```

Tương tự cho trường hợp đảo chiều primary/secondary.

Fatal reject chỉ giữ khi:

```text
- hai judge cùng xác nhận critical error; hoặc
- deterministic rule xác nhận contradiction/wrong sense/candidate-induced distortion.
```

Không thay đổi raw scores. Không thay đổi rubric.

### C-03 — Output additions

Bổ sung vào C output:

```json
{
  "context_role_map_sha256": "...",
  "critical_arbitration": {
    "triggered": true,
    "reason": "PRIMARY_SECONDARY_CRITICAL_DISAGREEMENT",
    "fatal_gate_suppressed": true
  }
}
```

### C-04 — C tests bắt buộc

```text
1. cùng context_id luôn có cùng context_type ở mọi candidate;
2. candidate không thể override role map;
3. primary fatal + secondary nonfatal => HUMAN_REVIEW_REQUIRED;
4. secondary fatal + primary nonfatal => HUMAN_REVIEW_REQUIRED;
5. hai judge cùng fatal => fatal reject giữ nguyên;
6. deterministic contradiction => fatal reject giữ nguyên;
7. final_glossary_decision vẫn null;
8. gold access = 0.
```

## 5. Thay đổi E

### E-01 — BGE-M3 local embedding authority

Chốt pilot:

```text
model family:
BGE-M3

runtime:
LM Studio local embedding endpoint

quantization:
Q8_0

context capacity:
8192

mode:
dense embedding only

similarity:
cosine after L2 normalization
```

Main phải pin:

```json
{
  "schema_id": "EmbeddingModelAuthorityV1",
  "model_family": "BGE-M3",
  "model_file": "<exact GGUF filename>",
  "model_file_sha256": "<exact SHA-256>",
  "quantization": "Q8_0",
  "embedding_dimension": "<measured dimension>",
  "context_length": 8192,
  "runtime": "LM Studio",
  "runtime_version": "<exact version>",
  "endpoint": "http://127.0.0.1:<port>/v1/embeddings",
  "normalization": "L2",
  "similarity": "COSINE",
  "network_classification": "LOCAL_LOOPBACK_NOT_EXTERNAL_NETWORK"
}
```

Không chấp nhận chỉ ghi `bge-m3` mà thiếu file hash.

### E-02 — Candidate-specific query plan

Mỗi candidate có 4–6 query classes:

```text
Q1 exact candidate
Q2 candidate + source term
Q3 candidate + Vietnamese domain anchor
Q4 candidate + Vietnamese concept anchor
Q5 authoritative-site restriction
Q6 approved variants
```

Ví dụ `tràn dưới`:

```text
"tràn dưới"
"tràn dưới" underflow
"tràn dưới" "dấu phẩy động"
"tràn dưới" "số quá nhỏ"
"tràn dưới" IEEE 754
"mức tràn dưới"
```

Query plan phải được hash-bind. Variant không được LLM tự mở rộng ngoài danh sách đã duyệt.

### E-03 — Lead ranking bằng embedding

Lead representation:

```text
title
search snippet
URL host
query classes đã match
```

Query representation:

```text
source term
sense definition
domain/subdomain
Vietnamese concept description
excluded senses
```

Dense embedding chỉ quyết định thứ tự fetch.

Không được dùng lead similarity làm attestation evidence.

### E-04 — Exact-span gate giữ nguyên

Sau fetch/extract:

```text
document phải chứa exact candidate hoặc approved variant.
```

Đoạn semantic gần nhưng không chứa candidate được ghi:

```text
CONCEPT_RELEVANT_NO_CANDIDATE_SURFACE
```

và không được tính là evidence.

### E-05 — Occurrence ranking

Trong mỗi document:

```text
1. tìm tất cả exact/variant occurrences;
2. tạo window 384–768 token quanh occurrence;
3. tối đa 3 windows/document;
4. embed intended-sense query;
5. embed excluded-sense queries;
6. tính intended_similarity;
7. tính max_excluded_similarity;
8. tính sense_margin;
9. chọn top snippets để E Judge.
```

Giai đoạn D0:

```text
- chỉ dùng top-k ranking;
- chưa dùng fixed threshold để quyết định SAME/DIFFERENT;
- similarity và margin chỉ là retrieval diagnostics.
```

### E-06 — Positive evidence không đổi

Accepted occurrence vẫn phải đồng thời:

```text
judgeability = JUDGEABLE
concept_relation = SAME
domain_relation = MATCH
usage_type = TECHNICAL_TERM
```

`ATTESTED` vẫn yêu cầu:

```text
>= 2 independent SAME clusters
>= 2 independent organizations
```

Embedding không được tự phát `ATTESTED`, `WEAKLY_ATTESTED` hoặc `NOT_ATTESTED`.

### E-07 — Acquisition caps

D0 regression defaults:

```text
unique URLs tối đa/candidate:
20

successful fetch/extract tối thiểu trước kết luận no-evidence:
6

occurrence windows tối đa/document:
3

Judge snippets tối đa/candidate:
12

early stop:
2 independent SAME clusters + 2 organizations
```

Nếu authority chưa cho phép acquisition mới, phiên chỉ chạy recorded/local fixtures và trả `READY_FOR_AUTHORIZED_REGRESSION`.

### E-08 — Reason codes

Bổ sung:

```text
CANDIDATE_SPECIFIC_SEARCH_NOT_RUN
SEARCH_BUDGET_EXHAUSTED
NO_FETCHABLE_DOCUMENT
NO_EXACT_SPAN_AFTER_SEARCH
CONCEPT_RELEVANT_NO_CANDIDATE_SURFACE
NO_JUDGEABLE_SNIPPET
JUDGE_RETURNED_UNCERTAIN
INSUFFICIENT_INDEPENDENT_ORGANIZATIONS
```

`ATTESTATION_UNJUDGEABLE` là trạng thái tổng; reason code chỉ ra điểm pipeline thất bại.

### E-09 — Telemetry

Tách bốn loại:

```json
{
  "embedding_calls": 0,
  "embedding_inputs": 0,
  "embedding_tokens": 0,
  "embedding_latency_ms": 0,
  "documents_ranked": 0,
  "occurrence_windows_ranked": 0,
  "provider_calls": 0,
  "external_network_calls": 0,
  "local_loopback_calls": 0
}
```

Quy tắc:

```text
LM Studio local embedding:
provider_calls = 0
external_network_calls = 0
local_loopback_calls > 0 được phép

recorded fixtures:
mọi network count = 0

real search/fetch:
external_network_calls ghi đúng request thực tế
```

## 6. Global compatibility

Không redesign Global.

Chỉ khóa interpretation:

```text
ATTESTATION_UNJUDGEABLE:
missing/insufficient evidence
không phải negative attestation
không tự phát fatal reject
```

Global output bổ sung:

```json
{
  "primary_decision_causes": [
    "C_SEMANTIC_FATAL_GATE"
  ],
  "supporting_uncertainties": [
    "E_NO_EXACT_SPAN_AFTER_SEARCH"
  ]
}
```

Nếu critical C gate bị arbitration suppress:

```text
Global không được dùng gate cũ để REJECT.
```

## 7. Trình tự thực hiện trong một phiên

### Khối A — Freeze inputs

Main phát:

```text
- exact C base commit;
- exact E base commit;
- frozen context-role map;
- exact BGE-M3 model authority;
- candidate query plans;
- underflow three-candidate regression cohort;
- execution boundary.
```

### Khối B — C narrow child

Agent C:

```text
- implement role-map binding;
- implement critical arbitration;
- run focused + full C tests;
- produce complete Git bundle and patch.
```

### Khối C — E narrow child

Agent E:

```text
- implement LM Studio embedding adapter;
- implement query plan;
- implement lead/occurrence ranking;
- preserve exact-span gate;
- add reason codes and telemetry;
- run zero-network and local-loopback tests;
- produce complete Git bundle and patch.
```

C và E có thể làm song song sau Khối A.

### Khối D — Integration regression

Sau khi hai child xanh:

```text
- chạy lại đúng 3 candidates underflow;
- dùng cùng context-role map;
- E chạy candidate-specific acquisition khi authority cho phép;
- Global replay;
- không mở gold;
- không chạy 12 candidates còn lại.
```

### Khối E — Review package

Một umbrella chứa ba target độc lập:

```text
1. C narrow child;
2. E narrow child;
3. underflow three-candidate regression.
```

Không target nào tự cấp acceptance cho target khác.

## 8. Acceptance gates

### C PASS

```text
- context role byte-identical giữa candidate runs;
- critical disagreement chuyển HUMAN_REVIEW;
- unanimous fatal vẫn REJECT;
- deterministic fatal vẫn REJECT;
- output decision-neutral;
- full tests PASS;
- source/patch/Git evidence exact.
```

### E PASS

```text
- exact BGE-M3 authority pin;
- local embedding reproducible;
- embedding chỉ ranking;
- exact-span gate bắt buộc;
- candidate-specific query plan;
- tối đa 3 windows/document;
- reason codes chính xác;
- positive-evidence predicate không đổi;
- telemetry tách đúng local/provider/external network;
- full tests PASS.
```

### Regression PASS

```text
- cùng exact Dataset/cohort inputs;
- C role map giống nhau cho 3 candidates;
- không false fatal từ single-judge disagreement;
- E Judge được gọi khi có exact span;
- no-span phải có evidence-effort receipt;
- Global replay deterministic;
- primary cause và supporting uncertainty tách rõ;
- final_glossary_decision = null;
- gold access = 0.
```

## 9. Không ép trước kết quả ngôn ngữ

Phiên này không đặt trước rằng:

```text
tràn dưới phải PASS;
candidate nào phải REJECT;
candidate nào phải thắng.
```

Mục tiêu là kết quả:

```text
- có đủ evidence;
- có arbitration hợp lý;
- có provenance;
- tái lập được;
- không nhầm missing evidence thành negative evidence.
```

## 10. Điều kiện mở D0 remainder

Sau independent review của regression:

```text
underflow regression PASS
        ↓
second-sense 3-candidate canary PASS
        ↓
mới chạy 9 candidates còn lại
```

Không chạy thẳng toàn bộ phần còn lại sau code change.

## 11. Deliverables cuối phiên

```text
C:
- child commit/parent/tree;
- source ZIP;
- patch;
- complete Git bundle;
- focused/full JUnit;
- role-map receipt.

E:
- child commit/parent/tree;
- source ZIP;
- patch;
- complete Git bundle;
- focused/live/full JUnit;
- embedding authority receipt;
- query-plan receipt;
- telemetry fixtures.

Integration:
- 3 candidate C/E/Global outputs;
- ledgers;
- replay;
- aggregate summary;
- A/B deterministic review ZIP;
- CHECKSUMS;
- credential scan;
- reviewer handoff.
```

## 12. Final execution boundary

```text
GOLD_ACCESS = NO
FINAL_GLOSSARY_DECISION = null
FULL_D0_REMAINDER = HOLD
PRODUCTION_AUTO_APPROVAL = NO
```

Local BGE-M3 embedding is an internal retrieval component. It does not activate
provider authority or grant glossary acceptance.
