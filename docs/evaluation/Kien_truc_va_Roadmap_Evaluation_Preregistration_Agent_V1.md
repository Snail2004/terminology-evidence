# KIẾN TRÚC VÀ ROADMAP — EVALUATION & PREREGISTRATION AGENT V1

**Document ID:** `evaluation-preregistration-agent-v1.0`  
**Branch đề xuất:** `feature/evaluation-preregistration-v1`  
**Owner:** Evaluation & Preregistration Agent  
**Base:** latest reviewed canonical `main` tại thời điểm bắt đầu  
**Trạng thái:** `READY_TO_IMPLEMENT`  
**Mục tiêu:** Khóa trước thiết kế đánh giá, metric, split discipline, calibration protocol, statistical tests và report schemas trước khi xem validation/test result.

---

## 1. Sứ mệnh

Evaluation & Preregistration Agent không tạo evidence ngôn ngữ và không thay đổi quyết định của Dataset, C, E hoặc Global.

Agent này có nhiệm vụ:

```text
định nghĩa câu hỏi nghiên cứu
→ khóa metric registry
→ khóa experiment registry
→ khóa split/label policy
→ định nghĩa calibration protocol
→ định nghĩa statistical analysis
→ tạo synthetic evaluation fixtures
→ tạo report templates
→ phát hành preregistration receipt
```

Agent phải đảm bảo rằng sau khi có dữ liệu thật:

```text
không đổi metric để làm đẹp kết quả
không đổi threshold sau khi xem test
không sửa label để khớp hệ thống
không mở test trước khi freeze
không trộn development/validation/test
```

Agent không trả lời trực tiếp:

```text
candidate nào đúng
sense nào đúng
C/E evidence nào được chấp nhận
Global nên chọn gate action nào
```

---

## 2. Ownership và phạm vi

Đề xuất chỉ sửa:

```text
evaluation/**
experiments/**
tests/evaluation/**
docs/evaluation/**
docs/methodology/**
```

Không sửa:

```text
dataset/**
context_substitution/**
vietnamese_attestation/**
global_validator/**
integration_harness/**
terminology_contracts_v1/**
```

Không tạo hoặc chỉnh sửa:

```text
Stage A labels
Stage B gold labels
CalibrationArtifact production
GlobalDecisionPackage
TerminologyCertificate
```

Agent chỉ consume artifact đã được các owner phát hành.

---

## 3. Nguyên tắc preregistration

### 3.1. Freeze trước khi xem kết quả

Phải freeze trước validation/test:

```text
research questions
primary metrics
secondary metrics
unit of analysis
split mapping
label mapping
threshold selection procedure
statistical tests
ablation matrix
exclusion criteria
reporting rules
```

### 3.2. Development được phép thay đổi

Development được dùng cho:

```text
debug schema
kiểm feature availability
kiểm pipeline
ước lượng sơ bộ
chọn candidate metric definitions
```

Nhưng mọi thay đổi trên development phải được freeze trước validation.

### 3.3. Validation chỉ dùng để freeze operating point

Validation dùng để:

```text
fit logistic regression
chọn threshold theo policy đã preregister
đo threshold stability
freeze CalibrationArtifact
```

Không dùng validation để sửa label hoặc gate semantics.

### 3.4. Test chỉ mở một lần

Test dùng để:

```text
final unbiased evaluation
```

Sau khi test được mở:

```text
không đổi model
không đổi feature set
không đổi threshold
không đổi gate policy
không đổi metric
không đổi exclusion rule
```

---

## 4. Câu hỏi nghiên cứu

### RQ1 — Global reliability

```text
Global Validator có đạt độ chính xác chấp nhận được cho các candidate được tự động phê duyệt không?
```

Primary focus:

```text
AUTO_APPROVED precision
false approval count
coverage
human-review rate
```

### RQ2 — Giá trị của C

```text
Context Substitution có phân biệt candidate đúng-context và sai-sense tốt hơn baseline không?
```

### RQ3 — Giá trị của E

```text
Vietnamese Attestation có bổ sung tín hiệu hữu ích ngoài C không?
```

### RQ4 — Giá trị của hard gates

```text
Hard gates có giảm false approvals không và chi phí coverage/human-review là bao nhiêu?
```

### RQ5 — Giá trị của kết hợp C+E

```text
C+E có tốt hơn C-only và E-only không?
```

### RQ6 — Giá trị downstream

```text
Validated glossary có cải thiện terminology correctness và adherence trong dịch tài liệu không?
```

### RQ7 — Giá trị của TAC

```text
TAC có giảm lỗi application-level mà không tăng escalation quá mức không?
```

### RQ8 — Độ ổn định calibration

```text
Threshold và decision có ổn định dưới bootstrap theo sense_id không?
```

---

## 5. Đơn vị phân tích

### 5.1. Candidate-level

Primary unit:

```text
(source_term, sense_id, scope_id, candidate_vi)
```

Dùng cho:

```text
C/E/Global evaluation
Stage B gold
calibration
gate analysis
```

### 5.2. Sense-level

Dùng để:

```text
bootstrap
split
grouped reporting
avoid candidate dependence
```

Ba candidate trong cùng sense không được coi là ba observation độc lập hoàn toàn.

### 5.3. Occurrence-level

Dùng cho TAC:

```text
(source occurrence, target occurrence, certificate)
```

### 5.4. Block/document-level

Dùng cho downstream translation:

```text
translation block
chapter
document
```

---

## 6. Label model

### 6.1. Stage B gold labels

Allowed:

```text
ACCEPT
CONDITIONAL
REJECT
SPLIT_REQUIRED
HUMAN_UNJUDGEABLE
```

### 6.2. Binary mapping cho primary reliability

Preregistered binary mapping:

```text
POSITIVE:
  ACCEPT

NEGATIVE:
  REJECT
  SPLIT_REQUIRED

EXCLUDED_FROM_PRIMARY_BINARY:
  CONDITIONAL
  HUMAN_UNJUDGEABLE
```

Secondary mapping:

```text
ACCEPT + CONDITIONAL → usable
REJECT + SPLIT_REQUIRED → not usable
HUMAN_UNJUDGEABLE → excluded
```

Mọi kết quả phải báo cả hai mapping, nhưng primary claim dùng mapping đầu.

### 6.3. Global decision statuses

```text
AUTO_APPROVED
PROVISIONAL
HUMAN_REVIEW
REJECTED
SPLIT_REQUIRED
```

### 6.4. Global-to-gold correctness

Primary:

```text
AUTO_APPROVED đúng khi gold = ACCEPT
REJECTED đúng khi gold = REJECT
SPLIT_REQUIRED đúng khi gold = SPLIT_REQUIRED
```

Routing decisions:

```text
PROVISIONAL
HUMAN_REVIEW
```

không tính trực tiếp là sai; chúng được đo bằng:

```text
review burden
coverage
routing appropriateness
```

---

## 7. Metric registry

## 7.1. Primary metrics

### AUTO_APPROVED precision

```text
TP_auto / (TP_auto + FP_auto)
```

Trong đó:

```text
TP_auto = AUTO_APPROVED và gold ACCEPT
FP_auto = AUTO_APPROVED và gold khác ACCEPT
```

### AUTO_APPROVED coverage

```text
AUTO_APPROVED count / eligible candidate count
```

### False approval count

```text
số candidate AUTO_APPROVED nhưng gold không phải ACCEPT
```

### Human-review rate

```text
(HUMAN_REVIEW + PROVISIONAL) / eligible candidate count
```

### Hard rejection accuracy

```text
(REJECTED hoặc SPLIT_REQUIRED đúng gold) / total hard decisions
```

---

## 7.2. Secondary metrics

```text
macro precision theo sense
macro recall
F1 cho ACCEPT-vs-rest
routing accuracy
gate trigger rate
gate precision
gate false-trigger rate
decision distribution
unjudgeable rate
coverage after gate
```

### Calibration metrics

```text
Brier score
log loss
expected calibration error
reliability bins
```

Chỉ áp dụng khi có approval_score thật.

### Threshold stability

```text
bootstrap threshold distribution
95% interval
decision flip rate
coverage variability
precision variability
```

---

## 7.3. C metrics

```text
C score distribution theo gold
C local status confusion
wrong-sense detection recall
context-supported precision
contrastive failure rate
judge disagreement rate
unjudgeable rate
```

### C ablation

```text
without contrastive
without backup contexts
single judge vs dual judge
without pairwise
```

---

## 7.4. E metrics

```text
accepted evidence yield
SAME precision
DIFFERENT precision
unjudgeable rate
insufficient-evidence rate
source-tier distribution
organization independence
dedup reduction
machine-translation suspicion rate
```

### E ablation

```text
controlled sources only
open web only
without dedup
without organization independence
without domain filter
```

---

## 7.5. Global gate metrics

Mỗi gate:

```text
trigger count
trigger rate
gold distribution
precision of trigger
false-trigger count
decision impact
coverage impact
```

Gate families:

```text
fatal split
fatal reject
human escalation
provisional cap
```

---

## 7.6. TAC metrics

Primary TAC labels:

```text
VALID_APPLICATION
VALID_WITH_VARIANT
WRONG_SENSE
UNGRAMMATICAL_APPLICATION
MISSING_APPLICATION
HUMAN_REVIEW
```

Metrics:

```text
wrong-sense recall
missing-application recall
valid-application precision
escalation rate
false alarm rate
certificate coverage
Tier 1 resolution rate
Tier 2 escalation rate
Tier 3 human-review rate
```

Natural và synthetic drift phải báo riêng.

---

## 7.7. Downstream translation metrics

Arms:

```text
A — no glossary
B — raw glossary
C — validated glossary without TAC
D — validated glossary + TAC/two-pass
```

Metrics:

```text
terminology correctness
terminology adherence
wrong-term propagation
missing-term count
intra-document consistency
human pairwise preference
reference-free translation quality
back-translation fact preservation
```

Không gộp TAC với MT quality tổng quát.

---

## 8. Experiment registry

## 8.1. E0 — Contract conformance

```text
synthetic fixtures
no gold
goal: schema/invariant validation
```

## 8.2. E1 — Development zero-network integration

```text
15 official development candidates
no live provider calls
goal: exact join and replay
```

## 8.3. E2 — C component evaluation

```text
candidate-level Stage B gold
C features/statuses
```

## 8.4. E3 — E component evaluation

```text
candidate-level Stage B gold
E features/statuses
```

## 8.5. E4 — Global development evaluation

```text
DEVELOPMENT_HEURISTIC
no AUTO_APPROVED claim
routing/gate behavior only
```

## 8.6. E5 — Calibration

```text
development + validation
logistic regression only
threshold selection
bootstrap stability
```

## 8.7. E6 — Hidden test

```text
frozen model
frozen threshold
frozen gate/action policy
one-time execution
```

## 8.8. E7 — Ablation

```text
C-only
E-only
C+E
C+E without gates
full system
```

## 8.9. E8 — Downstream A–D

```text
same source blocks
same translation model/config
same decoding settings
only glossary/TAC condition differs
```

## 8.10. E9 — TAC evaluation

```text
natural drift
controlled synthetic drift
reported separately
```

---

## 9. Calibration protocol

### 9.1. Model

Chỉ dùng:

```text
logistic regression
```

Không thử nhiều model rồi chọn model tốt nhất trên validation.

### 9.2. Feature set

Feature set phải khớp machine-readable feature registry.

Không thêm feature sau khi validation mở.

### 9.3. Training split

```text
development:
feature design/debug

validation:
fit/freeze logistic coefficients và operating point
```

Nếu contract yêu cầu fit trên combined development+validation sau model freeze, phải preregister rõ.

### 9.4. Operating point

Primary target:

```text
maximize coverage
subject to lower-bound precision target
```

Ví dụ:

```text
precision target ≥ 95%
```

Nhưng claim cuối phải dùng confidence interval, không chỉ point estimate.

Nếu validation sample quá nhỏ để chứng minh target:

```text
chọn threshold theo rule đã định
báo “consistent with target”
không tuyên bố definitive guarantee
```

### 9.5. Bootstrap

Bootstrap theo:

```text
sense_id
```

Không bootstrap từng candidate độc lập.

Mỗi replicate:

```text
sample senses with replacement
include all candidates of selected senses
fit/replay threshold theo preregistered rule
record threshold/precision/coverage/flip rate
```

### 9.6. Freeze artifact

CalibrationArtifact phải bind:

```text
feature contract version
feature names/order
coefficients
intercept
operating point
threshold
reviewed dataset SHA
gate policy SHA
action policy SHA
software commit
self hash
external approval anchor
```

Evaluation Agent không tự phát production CalibrationArtifact.

Nó chỉ tạo:

```text
calibration input pack
calibration script
calibration report
candidate artifact proposal
```

Maintainer/reviewer mới freeze.

---

## 10. Statistical analysis

### 10.1. Confidence intervals

Dùng:

```text
Wilson interval cho precision/proportion đơn giản
bootstrap CI theo sense cho aggregate metrics
```

### 10.2. Paired comparison

Dùng McNemar cho paired binary outcomes:

```text
V3 vs V4
B vs C
C vs D
C-only vs C+E
no-gates vs gates
```

Chỉ khi cùng candidate/block được đánh giá ở cả hai condition.

### 10.3. Continuous paired metrics

Cho score/block-level metrics:

```text
paired bootstrap
hoặc
Wilcoxon signed-rank nếu preregistered và assumptions phù hợp
```

Không chọn test sau khi xem distribution mà không ghi amendment.

### 10.4. Multiple comparisons

Primary hypotheses được xác định trước.

Secondary analyses:

```text
exploratory
```

Nếu có nhiều formal secondary tests:

```text
Holm correction
```

### 10.5. Effect size

Luôn báo:

```text
absolute difference
relative difference
confidence interval
paired discordant counts
```

Không chỉ báo p-value.

---

## 11. Split discipline

### 11.1. Development

Được xem nhiều lần.

### 11.2. Validation

Không được dùng để sửa:

```text
labels
sense authority
candidate generation
gate semantics
feature registry
```

Chỉ dùng theo preregistration.

### 11.3. Test

Không mở trước freeze receipt.

### 11.4. Grouped split

Split phải theo:

```text
sense_id
source-block cluster
```

Không để cùng source block cluster nằm ở nhiều split.

### 11.5. Leakage checks

Bắt buộc:

```text
candidate hash overlap
sense overlap
source-block overlap
evidence-source overlap nếu policy cấm
glossary/gold leakage
test artifact access log
```

---

## 12. Exclusion policy

Một case chỉ được exclude theo reason code preregistered:

```text
CORRUPT_ARTIFACT
MISSING_REQUIRED_GOLD
INVALID_SCHEMA
UNRESOLVED_SENSE_AUTHORITY
HUMAN_UNJUDGEABLE
PROTOCOL_VIOLATION
```

Không exclude vì:

```text
system làm sai
score xấu
candidate khó
gate bất lợi
```

Mỗi exclusion phải có:

```text
candidate_id
reason
artifact ref
timestamp
reviewer approval
```

Báo cả before/after exclusion counts.

---

## 13. Ablation matrix

Minimum:

| ID | C | E | Gates | Calibration | TAC |
|---|---:|---:|---:|---:|---:|
| A0 | 0 | 0 | 0 | 0 | 0 |
| A1 | 1 | 0 | 0 | 1 | 0 |
| A2 | 0 | 1 | 0 | 1 | 0 |
| A3 | 1 | 1 | 0 | 1 | 0 |
| A4 | 1 | 1 | 1 | 1 | 0 |
| A5 | 1 | 1 | 1 | 1 | 1 |

A0 có thể là baseline policy/raw glossary tùy experiment.

Không tạo weight tùy ý giữa C và E ngoài calibrated model.

---

## 14. Preregistration artifacts

Bắt buộc:

```text
research_questions_v1.json
metric_registry_v1.json
experiment_registry_v1.json
label_mapping_v1.json
split_policy_v1.json
calibration_protocol_v1.json
statistical_analysis_plan_v1.json
exclusion_policy_v1.json
ablation_registry_v1.json
report_schema_v1.json
preregistration_receipt.json
CHECKSUMS.sha256
```

`preregistration_receipt.json` bind:

```text
all file hashes
Git commit
Dataset manifest
Contracts authority
Global action policy
created_at
status = FROZEN_BEFORE_VALIDATION
self hash
```

---

## 15. Amendment policy

Sau freeze, thay đổi chỉ được qua:

```text
preregistration_amendment_<n>.json
```

Bắt buộc:

```text
reason
affected artifacts
before/after hash
whether validation/test đã được seen
impact on claims
approver
timestamp
```

Nếu test đã mở:

```text
primary analysis không được đổi
new analysis chỉ exploratory/post hoc
```

---

## 16. Evaluation pipeline

```text
Artifact Loader
      ↓
Authority Verifier
      ↓
Gold Joiner
      ↓
Eligibility Filter
      ↓
Metric Engine
      ↓
Bootstrap Engine
      ↓
Paired Test Engine
      ↓
Ablation Engine
      ↓
Report Builder
      ↓
Reproducibility Verifier
```

### 16.1. Artifact Loader

Chỉ đọc explicit manifests.

### 16.2. Authority Verifier

Verify:

```text
Dataset release
Stage B gold release
C/E/Global releases
CalibrationArtifact
preregistration receipt
```

### 16.3. Gold Joiner

Exact join bằng candidate identity.

### 16.4. Eligibility Filter

Áp preregistered exclusions.

### 16.5. Metric Engine

Deterministic.

### 16.6. Bootstrap Engine

Seed phải được pin.

### 16.7. Paired Test Engine

Dùng exact paired IDs.

### 16.8. Report Builder

Xuất JSON + CSV + Markdown.

### 16.9. Reproducibility Verifier

Chạy lại cùng input phải ra cùng report semantic hash.

---

## 17. Output reports

### Candidate-level

```text
candidate_results.csv
candidate_errors.jsonl
decision_confusion.csv
gate_analysis.csv
```

### Aggregate

```text
primary_metrics.json
secondary_metrics.json
bootstrap_summary.json
paired_tests.json
ablation_summary.json
```

### Downstream

```text
translation_arm_metrics.json
tac_metrics.json
pairwise_preferences.csv
```

### Narrative

```text
EVALUATION_REPORT.md
LIMITATIONS.md
DEVIATIONS_FROM_PREREGISTRATION.md
```

---

## 18. Report rules

Mỗi metric phải có:

```text
name
definition
unit
eligible N
excluded N
point estimate
confidence interval
split
artifact hashes
```

Mỗi comparison phải có:

```text
paired N
discordant counts
effect size
CI
p-value nếu applicable
correction method
```

Không viết:

```text
“đạt 95% chắc chắn”
```

khi CI không hỗ trợ.

Nên viết:

```text
“point estimate đạt mục tiêu và kết quả nhất quán với target trong sample hiện tại”
```

khi sample nhỏ.

---

## 19. Synthetic fixtures

Agent phải tạo fixtures cho:

```text
perfect classifier
all positive predictions
all negative predictions
zero eligible rows
one-sense grouped bootstrap
candidate dependence
paired discordance
missing gold
duplicate candidate
split leakage
threshold tie
decision flip
```

Không dùng fixture kết quả như evidence luận văn.

---

## 20. Test matrix

### Registry validation

```text
duplicate metric ID → reject
unknown label → reject
unknown experiment → reject
missing primary metric → reject
```

### Join

```text
candidate mismatch → reject
gold duplicate → reject
missing gold → exclude/reject theo policy
```

### Split

```text
sense overlap → reject
source-block overlap → reject
test opened before freeze → reject
```

### Metrics

```text
known confusion matrix → exact result
Wilson interval fixture → exact result
bootstrap seed → deterministic
McNemar fixture → exact result
```

### Preregistration

```text
hash drift → reject
amendment missing reason → reject
post-test primary metric change → reject
```

### Reporting

```text
missing eligible N → reject
CI missing for primary metric → reject
raw p-value without effect size → reject
```

---

## 21. Milestones

### M0 — Bootstrap

```text
branch
ownership
package skeleton
CLI/tests
```

### M1 — Registries

```text
research questions
metrics
experiments
labels
splits
```

### M2 — Synthetic metric engine

```text
confusion
precision/coverage
Wilson
bootstrap
McNemar
```

### M3 — Preregistration freeze system

```text
receipt
hashing
amendments
access log
```

### M4 — Component evaluation templates

```text
C
E
Global
gates
```

### M5 — Downstream/TAC templates

```text
A–D
TAC natural/synthetic
```

### M6 — Development dry run

Dùng synthetic hoặc development-only data.

### M7 — Validation freeze support

Chỉ khi Stage B gold và real C/E/Global outputs sẵn sàng.

### M8 — Hidden test execution support

Chỉ sau approved freeze receipt.

---

## 22. Dependency contract

### Dataset Agent

```text
Stage A authority
Stage B gold labels
split manifest
exclusion annotations
```

### C

```text
official C packages
feature registry projection
local status
```

### E

```text
official E packages
source/evidence summaries
local status
```

### Global

```text
decision packages
gate results
approval score
CalibrationArtifact
```

### Integration Harness

```text
sealed end-to-end runs
artifact inventory
join reports
replay receipts
```

### Contract Steward

```text
Contracts authority
feature registry
GatePolicy
```

---

## 23. Definition of Done V1

Agent đạt `PREREGISTRATION_READY` khi:

1. Tất cả registry schemas có validator.
2. Research questions được pin.
3. Primary/secondary metrics được phân biệt.
4. Label mapping được freeze.
5. Split policy được freeze.
6. Calibration protocol được freeze.
7. Bootstrap theo sense_id được triển khai.
8. Wilson interval được triển khai.
9. McNemar paired test được triển khai.
10. Ablation matrix được freeze.
11. Exclusion policy được freeze.
12. Synthetic fixtures pass.
13. Reports deterministic.
14. Preregistration receipt có self-hash.
15. Amendment workflow tồn tại.
16. Source release sạch cache/credential.
17. Independent review chấp nhận.

Agent đạt `READY_FOR_VALIDATION` khi thêm:

18. Stage B gold development/validation sẵn sàng.
19. Real C/E/Global outputs sẵn sàng.
20. Development dry run hoàn tất.
21. Không còn split leakage.
22. Validation access chưa xảy ra trước freeze.
23. Freeze receipt được maintainer phê duyệt.

Agent đạt `READY_FOR_HIDDEN_TEST` khi thêm:

24. CalibrationArtifact được review và pin.
25. Threshold/operating point freeze.
26. Test access log còn rỗng.
27. Main maintainer cấp phép mở test.

---

## 24. Không thuộc phạm vi V1

```text
annotation UI
gold label creation
provider calls
feature engineering
Global model implementation
threshold tự ý chọn
test execution trước freeze
production certificate
domain-transfer benchmark lớn
```

---

## 25. Release artifact

```text
evaluation_preregistration_v1_rc1.zip
evaluation_preregistration_v1_rc1.zip.sha256
```

Bên trong:

```text
source/
tests/
docs/
registries/
fixtures/
junit.xml
commands.txt
environment.json
static_scan.json
credential_scan.json
ownership_scan.json
git_commit_receipt.json
release_manifest.json
CHECKSUMS.sha256
synthetic_metric_report.json
preregistration_example_receipt.json
```

---

## 26. Báo cáo Agent gửi reviewer

```text
repository
branch
base main commit
implementation commit
changed paths
registry counts
test result
synthetic metric result
preregistration receipt hash
release ZIP/SHA
validation access status
test access status
remaining blockers
```

---

## 27. Prompt giao trực tiếp cho Agent

```text
You are the Evaluation & Preregistration Agent for the terminology-evidence
project.

Create branch feature/evaluation-preregistration-v1 from the latest reviewed
canonical main.

Do not modify Dataset, C, E, Global Validator, Integration Harness or shared
Contracts internals.

Build a standalone preregistration and evaluation framework that:

1. Freezes research questions, metric definitions, label mappings, split policy,
   calibration protocol, statistical analysis, exclusions and ablations before
   validation/test.
2. Uses candidate-level analysis grouped by sense_id.
3. Defines AUTO_APPROVED precision, coverage, false approvals and human-review
   rate as primary Global metrics.
4. Defines component metrics for C, E, hard gates, TAC and downstream arms A–D.
5. Implements Wilson intervals, grouped bootstrap by sense_id and paired
   McNemar tests.
6. Implements threshold-stability and decision-flip analysis.
7. Uses logistic regression only and the exact machine-readable feature registry.
8. Enforces development/validation/test discipline and one-time hidden test access.
9. Rejects split leakage, candidate/gold mismatch and preregistration hash drift.
10. Produces deterministic JSON/CSV/Markdown reports.
11. Creates a self-hashed preregistration receipt and append-only amendment workflow.
12. Supports synthetic fixtures now and real development/validation/test artifacts
    only when their authorities are ready.
13. Never creates or edits gold labels, Global decisions or production calibration.
14. Never changes primary metrics after test access.
15. Clearly labels post-hoc analyses as exploratory.

Deliver:
- source and tests;
- research question, metric, experiment, label, split, calibration,
  statistical, exclusion and ablation registries;
- preregistration receipt and amendment schema;
- synthetic fixtures and deterministic reports;
- CLI;
- JUnit, commands, environment and scan reports;
- Git receipt;
- release manifest/checksums;
- RC ZIP and SHA.

Report back with branch/commit/base, changed paths, registry counts, tests,
synthetic results, preregistration receipt hash, release SHA and blockers.
```
