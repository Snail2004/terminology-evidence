# REVIEW — D2L CONTEXT SUPPORT SET VALIDATION-READY V3

## Kết luận điều hành

V3 là một bước tiến rõ rệt và các tuyên bố kỹ thuật chính trong phần bàn giao hầu hết đều đúng.

Phán quyết:

```text
ARTIFACT INTEGRITY: PASS
MANIFEST / ZIP HASH: PASS
150 TERM-SENSE BALANCE: PASS
CANDIDATE COMPLETENESS: PASS
OFFSET CONTRACT: PASS WITH ONE SEMANTIC NOTE
SENTENCE-DISJOINT SPLIT: PASS
BLOCK-OVERLAP AUDIT: PASS
HUMAN REVIEW QUEUES: PASS
PILOT CONTENT PACKAGING: PASS
PILOT EXPERIMENTAL ISOLATION: FAIL
OFFICIAL CST READINESS: CORRECTLY BLOCKED
OFFICIAL C+E CALIBRATION: CORRECTLY BLOCKED
```

V3 có thể được dùng làm artifact chuẩn bị human review. Tuy nhiên, pilot 8 hiện không được dùng để chỉnh prompt, rubric hoặc threshold vì nó chứa cả validation và test senses.

---

# 1. Các tuyên bố đã được xác minh

## 1.1. Hash và toàn vẹn artifact

Đã xác minh:

- ZIP SHA-256:

```text
2f8e6ad0519854b161eda8cce61b13cdfc2f5ee54d205d18c27f279493c4fe52
```

- Manifest self-hash:

```text
258ebe5d907a0a108a1b80a1ec1aad3c6e265ed1a8edbd5701cc128e273122ce
```

- 55 file được liệt kê trong manifest đều có byte hash khớp.
- Cộng thêm `manifest.json` tạo thành đúng 56 file trong ZIP.
- Parent V2 manifest self-hash khớp với trường `parent.manifest_sha256`.
- Toàn bộ `audit_ref` và `audit_sha256` được dùng trong term, candidate và context đều trỏ tới file tồn tại và hash khớp.

Kết luận: tuyên bố `56/56` và hai hash được cung cấp là đúng.

---

## 1.2. Quy mô và cân bằng

Đã xác minh:

| Hạng mục | Số lượng |
|---|---:|
| Term-sense | 150 |
| Candidate instances | 450 |
| Candidate/sense | 3 cho cả 150 sense |
| Context records | 1.340 |
| Clear | 50 |
| Ambiguous | 50 |
| Collision/multi-target | 50 |

Không có:

- ID trùng;
- candidate chuỗi trùng trong cùng sense sau normalization;
- foreign key thiếu;
- mismatch giữa slot và candidate;
- mismatch giữa `shared_context_set_id`.

---

## 1.3. Split mới

Đã xác minh:

```text
development: 100
validation: 25
test: 25
```

Phân bố strata:

| Split | Clear | Ambiguous | Collision/multi-target |
|---|---:|---:|---:|
| Development | 34 | 33 | 33 |
| Validation | 8 | 9 | 8 |
| Test | 8 | 8 | 9 |

Đây là cân bằng gần tối đa với split có 25 sense.

---

## 1.4. Sentence leakage và block overlap

Đã tính lại trực tiếp từ `contexts.jsonl`:

- 0 `sentence_id` xuất hiện ở nhiều split;
- 0 `content_sha256` corpus-context xuất hiện ở nhiều split;
- 0 normalized source text xuất hiện ở nhiều split;
- component lớn nhất có đúng 24 sense;
- có đúng 79 sentence components;
- 48 block xuất hiện ở nhiều split;
- cả 48 block này đều xuất hiện chính xác trong `block_overlap_audit.csv`;
- audit không thiếu hoặc dư block.

Kết luận: tuyên bố “không còn sentence leakage” và “48 block overlap được audit” là đúng.

---

## 1.5. Offset contract

Tất cả 1.340 context đều khai báo:

```text
offset_coordinate_system =
CONTEXT_TEXT_UNICODE_CODEPOINT_INDEX
```

Đã xác minh:

- `match_start` và `match_end` đều nằm trong `source_text`;
- không có span rỗng hoặc vượt biên;
- 1.200 corpus context có absolute offsets;
- 140 synthetic context để absolute offsets null;
- toàn bộ source span khớp `matched_surface` khi so không phân biệt hoa/thường.

Kết luận: lỗi mixed coordinate của V2 đã được sửa.

### Ghi chú còn lại

Có 268 row mà source slice giữ nguyên hoa/thường, còn `matched_surface` được normalize:

```text
source slice: single GPU
matched_surface: single gpu
```

Không phải offset error, nhưng field name dễ làm consumer hiểu rằng đây là exact source slice.

Nên thêm một trong hai:

```text
matched_surface_exact
matched_surface_normalized
```

hoặc ghi rõ trong schema rằng `matched_surface` là case-normalized lookup surface.

---

## 1.6. Review queues

Đã xác minh coverage:

| Queue | Số row | Coverage |
|---|---:|---|
| Definition review | 150 | đúng toàn bộ sense |
| Contrastive review | 150 | đúng toàn bộ selected contrastive context |
| Context-type review | 1.148 | đúng toàn bộ primary + backup same-sense contexts |
| Candidate annotation | 450 | đúng toàn bộ candidate |
| Repair queue | 150 | đúng toàn bộ sense |

Mọi human field đều để trống như tuyên bố.

---

## 1.7. Pilot package

Đã xác minh:

- 8 sense;
- 24 candidate;
- 48 context;
- mỗi sense có 5 primary + 1 contrastive;
- cả 48 context đều là corpus context;
- 0 synthetic context;
- pilot records là exact subset của dataset chính theo record hash;
- human review fields đều trống.

Về mặt packaging, pilot đúng như mô tả.

---

# 2. P0 — Pilot hiện làm lộ validation/test

Đây là vấn đề quan trọng nhất.

Phân bố 8 sense trong pilot:

```text
development: 5
validation: 1
test: 2
```

Các sense ngoài development:

| Source term | Split |
|---|---|
| address | validation |
| biases | test |
| norm | test |

Nếu pilot được dùng để:

- sửa prompt;
- điều chỉnh rubric;
- chọn threshold;
- phân tích lỗi để sửa hệ thống;
- quyết định retry/Judge 2 policy;

thì validation và test không còn độc lập.

## Hành động bắt buộc

Không dùng pilot 8 hiện tại cho development.

Hai lựa chọn hợp lệ:

### Lựa chọn A — Pilot development-only 5 sense

Giữ năm sense development hiện tại:

```text
Generator
multiple channels
hypothesis
keys
channels
```

### Lựa chọn B — Pilot 6–8 sense development-only

Dataset có sáu corpus-contrastive sense trong development. Sense thứ sáu là:

```text
statistical power
```

nhưng cần sửa primary-context coverage trước khi thêm.

Để đủ tám sense, chọn thêm hai development senses có synthetic contrastive đã được người review là `VALID_BOUNDARY`.

## Quy tắc

```text
Development pilot
→ được dùng sửa hệ thống

Validation
→ chỉ dùng calibration sau khi policy đã ổn định

Test
→ không mở label hoặc kết quả cho tới lần chạy cuối
```

Pilot hiện tại có thể giữ để audit lịch sử, nhưng phải gắn:

```text
PILOT_INVALID_FOR_METHOD_DEVELOPMENT_DUE_TO_SPLIT_EXPOSURE
```

---

# 3. P0 — Phiếu human review trong pilot chưa đủ chi tiết

`pilot_8_corpus_contrastive/human_review_sheet.csv` có 24 row, một row mỗi candidate.

Nó chỉ có các field tổng quát:

```text
human_definition_status
human_contrastive_status
human_context_type_status
human_candidate_label
```

Nó không có:

- human definition text hoặc correction;
- contrastive label `VALID_BOUNDARY / WEAK_BOUNDARY / INVALID`;
- nhãn same-sense cho từng context;
- context type C1–C5 cho từng context;
- candidate rank;
- ACCEPT / CONDITIONAL / REJECT tách biệt;
- adjudication fields.

Ngoài ra, sense-level fields bị lặp ba lần theo ba candidate, có thể dẫn đến ba giá trị không nhất quán cho cùng definition hoặc contrastive context.

## Hành động bắt buộc

Pilot folder nên có bốn bảng normalized:

```text
pilot_definition_review.csv       — 1 row/sense
pilot_contrastive_review.csv      — 1 row/contrastive context
pilot_context_review.csv          — 1 row/primary context
pilot_candidate_annotation.csv    — 1 row/candidate
```

Có thể tạo bằng cách filter bốn queue gốc theo pilot `sense_id`.

Không dùng một sheet 24 row để lưu cả sense-level, context-level và candidate-level annotation.

---

# 4. P1 — Context-type coverage vẫn chưa được sửa

V3 làm đúng khi không giả tạo nhãn người, nhưng về mặt CST readiness:

- chỉ 1/150 sense có đủ proposed C1–C5;
- trong selected primary contexts:
  - 36 sense chỉ có một loại context;
  - 60 sense có hai loại;
  - 37 sense có ba loại;
  - 16 sense có bốn loại;
  - 1 sense có đủ năm loại.

Trong pilot:

- 6/8 sense có cả năm primary context đều đang được model đề xuất là C1;
- 1 sense có hai loại;
- 1 sense có ba loại.

Vì thế pilot chỉ được chạy sau human context review hoặc reselection.

Điều này phù hợp với trạng thái:

```text
VALIDATION_READY_HUMAN_REVIEW_REQUIRED
```

nhưng chưa phù hợp với việc gọi trực tiếp CST live.

---

# 5. P1 — Split 25/25 còn yếu cho mục tiêu precision ≥95%

Mỗi validation/test split có:

```text
25 senses × 3 candidates = 75 candidate instances
```

Nếu test có đủ 75 auto-approved candidate và không có lỗi, lower bound Clopper–Pearson hai phía 95% mới xấp xỉ 95,2%.

Nếu coverage là 50%, chỉ khoảng 37 candidate được auto-approved. Ngay cả 37/37 đúng, lower bound 95% chỉ khoảng 90,5%.

Do đó split này có thể báo:

- observed precision;
- bootstrap/exact confidence interval;
- coverage;
- failure analysis;

nhưng có thể không đủ để khẳng định chắc chắn “precision thực ≥95%” nếu auto-approval coverage thấp.

## Khuyến nghị

- giữ 100/25/25 nếu ưu tiên workload và thesis scope;
- luôn báo exact/binomial confidence interval;
- diễn đạt mục tiêu 95% là operating target trên validation;
- không tuyên bố đã chứng minh 95% trên test nếu khoảng tin cậy không hỗ trợ;
- cân nhắc bổ sung adversarial/test cases hoặc tăng test nếu workload cho phép.

---

# 6. P1 — Sentence-disjoint chỉ an toàn nếu runtime dùng đúng sentence boundary

V3 chọn `sentence_id` làm leakage unit. Điều này hợp lý khi CST evidence item là đúng `source_text` sentence.

Tuy nhiên, nếu runtime sau này đưa vào prompt:

- cả source block;
- câu trước/câu sau từ cùng block;
- chapter-local retrieved context;
- definition được tạo từ test contexts;

thì 48 block overlap có thể trở thành leakage gián tiếp.

## Cần freeze policy

```json
{
  "evaluation_text_boundary_policy": "SOURCE_SENTENCE_ONLY",
  "neighbor_context_allowed": false
}
```

Hoặc nếu cho phép neighbors, split phải được xây theo block/window tương ứng.

---

# 7. P1 — Reproducibility chưa hoàn toàn portable

Nhiều provenance field còn chứa absolute Windows paths:

```text
C:/work/...
E:/Data-KL/...
```

Các hash đã có và artifact tự nhất quán, nhưng reviewer khác không thể replay source extraction chỉ từ ZIP vì source snapshot không được đóng gói.

## Khuyến nghị

- thay absolute path bằng relative artifact URI;
- đóng gói source package snapshot tối thiểu;
- hoặc cung cấp immutable source bundle riêng và registry:

```text
artifact://d2l-source-snapshot-v1/document.json
```

V3 đủ để audit record-level, chưa đủ để tái dựng source-level hoàn toàn trên máy khác.

---

# 8. P2 — 4/4 test chưa thể audit từ ZIP

ZIP không chứa:

- test source;
- validator script;
- test report;
- command đã chạy;
- environment/dependency lock.

Mình đã độc lập xác minh các invariant chính, nhưng không thể xác nhận chính xác “4/4” là bốn test nào.

Nên thêm:

```text
validation_tests/
test_report.json
commands.txt
requirements.lock hoặc environment metadata
```

---

# 9. Đánh giá chất lượng pilot corpus-contrastive

Các contrastive context trong pilot nhìn chung thực sự khác sense:

- `biases`: cognitive bias;
- `Generator`: random-number/helper generator trong code;
- `hypothesis`: statistical hypothesis;
- `norm`: add-and-norm normalization component;
- `keys`: dictionary keys;
- `address`: memory address;
- `channels`: memory channels;
- `multiple channels`: memory modules/channels.

Đây là tập boundary probe hữu ích.

Tuy nhiên:

- một số contrastive là code-heavy;
- một số primary là heading, image caption hoặc code block;
- model context-type proposals còn yếu.

Human review và source-quality filtering vẫn cần thiết trước live pilot.

---

# 10. Phán quyết cuối

## Những gì V3 đã đạt thật

```text
✓ artifact integrity
✓ complete 150 × 3 candidate matrix
✓ stable local offset contract
✓ sentence-disjoint split
✓ explicit block-overlap audit
✓ complete human review queues
✓ exact corpus-only pilot subset
✓ honest blocking of official CST
```

## Những gì phải sửa trước khi bắt đầu pilot phương pháp

```text
1. Thay pilot bằng development-only pilot.
2. Tạo normalized review sheets theo đúng annotation unit.
3. Human-review/reselect pilot contexts.
4. Không sử dụng validation/test outputs để sửa prompt.
```

## Trạng thái đề xuất

```text
DATASET V3: ACCEPTED AS HUMAN-REVIEW STAGING ARTIFACT
CURRENT PILOT 8: REJECTED FOR METHOD DEVELOPMENT
DEVELOPMENT-ONLY PILOT: REQUIRED
OFFICIAL CST: BLOCKED PENDING HUMAN REVIEW
OFFICIAL C+E CALIBRATION: BLOCKED PENDING HUMAN REVIEW
```

Artifact tiếp theo không nhất thiết phải là dataset V4 toàn bộ. Có thể tạo một patch nhỏ:

```text
pilot_dev_only_v1
+
pilot_normalized_review_pack_v1
```

và giữ nguyên V3 bất biến.
