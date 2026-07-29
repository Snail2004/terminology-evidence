# YÊU CẦU AGENT EVALUATION — FREEZE ANALYSIS PLAN 50/150 V1

**Priority:** P0 trước khi xem kết quả C/E/Global
**Mode:** zero-network, no validation/test opening, no sealed-gold opening
**Không được:** tạo gold, sửa nhãn Dataset, chọn threshold từ dữ liệu chưa được mở hợp lệ.

## Mục tiêu

Freeze kế hoạch phân tích cho 50 senses / 150 candidates trước khi producer
outputs và Stage B gold được đối chiếu.

## Phạm vi cần khóa

### Dataset / human review

```text
label distribution
raw agreement
Cohen's kappa
agreement by clear / ambiguous / risk
adjudication rate
HUMAN_UNJUDGEABLE rate
confidence intervals
missing-data handling
```

### Primary label mapping

```text
Positive: ACCEPT
Negative: REJECT + SPLIT_REQUIRED
Excluded primary: CONDITIONAL + HUMAN_UNJUDGEABLE
Secondary: ACCEPT + CONDITIONAL vs REJECT + SPLIT_REQUIRED
```

### C metrics

```text
trial validity
evidence coverage
support/mixed/contradiction
critical-gate frequency
within-sense ranking
C-vs-gold cross-tab
escalation rate
request/token/cost
```

### E metrics

```text
controlled-corpus coverage
Brave fallback rate
eligible/independent source counts
sense-match and domain-match rates
ATTESTED_STRONG/LIMITED
NO_EVIDENCE/UNJUDGEABLE/CONFLICTING
```

### Global / pipeline metrics

```text
development status distribution
gate routing
identity join success
replay success
0 AUTO_APPROVED
0 certificate
```

### Statistical policy

```text
Wilson intervals for proportions
bootstrap confidence intervals
paired McNemar where applicable
bootstrap threshold stability
decision-flip rate
no overclaim from small D0
```

## Access order

```text
D0 development canary
→ seal C/E/Global outputs
→ authorized development-gold open

D1 development
→ analysis-plan revision only if preregistered rules permit

V1 validation
→ only after D1 and policy freeze

T1 held-out test
→ only after validation/calibration freeze
```

## Deliverables

```text
ANALYSIS_PLAN_50_150_V1.md
analysis_plan_50_150_v1.json
planned_tables_v1.json
gold_access_event_templates
hash-chain/receipt bindings
manifest + CHECKSUMS
```

## Return status

```text
ANALYSIS_PLAN_FROZEN_FOR_D0
NEEDS_REWORK_BEFORE_GOLD_ACCESS
BLOCKED_BY_DATASET_SPLIT_OR_LABEL_SCHEMA
```
