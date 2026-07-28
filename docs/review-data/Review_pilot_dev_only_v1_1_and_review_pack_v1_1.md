# REVIEW — PILOT DEVELOPMENT-ONLY V1.1
## `pilot_dev_only_v1_1` và `pilot_normalized_review_pack_v1_1`

## Kết luận

Patch V1.1 đã sửa đúng các lỗi chính của V1:

- pilot chỉ chứa development;
- đủ primary, backup và contrastive context;
- không còn context reference bị thiếu;
- có replacement contexts cho Trial Gate;
- review sheet đã tách đúng annotation unit;
- có hai reviewer và adjudication fields;
- có candidate-relation labels;
- V3 và các artifact cũ không bị ghi đè.

Phán quyết:

```text
PILOT BUNDLE INTEGRITY: PASS
REFERENCE CLOSURE: PASS
EXACT V3 SUBSET: PASS
DEVELOPMENT-ONLY ISOLATION: PASS
REPLACEMENT-PATH DATA: PASS
REVIEW TABLE NORMALIZATION: PASS
BLANK HUMAN LABELS: PASS

ANNOTATION VALIDATOR: CONDITIONAL PASS
HUMAN REVIEW START: BLOCKED UNTIL VALIDATOR P0 PATCH
LIVE CST: BLOCKED UNTIL HUMAN REVIEW
THRESHOLD CALIBRATION: CORRECTLY DISALLOWED
```

Pilot ZIP có thể được chấp nhận làm execution staging bundle. Review pack cần một patch validator nhỏ trước khi annotator bắt đầu nhập nhãn.

---

# 1. Các tuyên bố đã xác minh

## Hash

```text
Pilot ZIP:
664cd5bf9e3006ebd77cffa6665a3cd86690dff0201fc518cae407a121aa4f15

Review-pack ZIP:
bff05b5f1f0f0b8d1a3d184c7a5f0c3c95b56e21bc71cd48a74900fd3c9d9a69

V3 ZIP vẫn giữ nguyên:
2f8e6ad0519854b161eda8cce61b13cdfc2f5ee54d205d18c27f279493c4fe52
```

Hai manifest self-hash đều đúng. Mọi file được liệt kê trong manifest đều khớp SHA-256.

## Pilot counts

| Hạng mục | Kết quả |
|---|---:|
| Development senses | 5 |
| Validation senses | 0 |
| Test senses | 0 |
| Candidates | 15 |
| Primary contexts | 25 |
| Backup contexts | 8 |
| Corpus contrastive contexts | 5 |
| Tổng context | 38 |
| Synthetic contexts | 0 |
| UNSELECTED contexts | 0 |

## Reference closure

Đã kiểm tra toàn bộ:

- `primary_context_ids`;
- `backup_context_ids`;
- `contrastive_context_ids`;
- `definition_evidence_context_ids`;
- `part_of_speech_evidence_context_id`.

Kết quả:

```text
38 unique referenced contexts
38 packaged contexts
0 missing references
0 orphan contexts
```

## Exact subset của V3

Đối chiếu object-level:

```text
5/5 term records: identical
15/15 candidate records: identical
38/38 context records: identical
```

## Review tables

| File | Rows | Unit | Duplicate |
|---|---:|---|---:|
| Definition review | 5 | sense | 0 |
| Contrastive review | 5 | contrastive context | 0 |
| Context review | 33 | primary/backup context | 0 |
| Candidate annotation | 15 | candidate | 0 |

`context_role` khớp pilot trên cả 33 rows.

`matched_surface_exact` và `matched_surface_normalized` đều đúng trên toàn bộ context.

Tất cả reviewer/adjudication fields đang trống.

---

# 2. Những chức năng validator đang làm đúng

Các mutation test độc lập xác nhận validator chặn đúng:

| Trường hợp | Kết quả |
|---|---|
| Blank template ở partial mode | PASS |
| Blank template với `--require-complete` | FAIL |
| `CORRECTED` nhưng thiếu corrected definition | FAIL |
| Contrastive `INVALID` nhưng `use_in_test=TRUE` | FAIL |
| Morphological/duplicate relation trỏ sang foreign sense | FAIL |
| Rank ngoài 1–3 | FAIL theo code |
| Duplicate ranks trong cùng sense | FAIL theo code |

README cũng đã sửa đúng:

- không tuyên bố selector development;
- không cho threshold calibration;
- chỉ cho threshold-sensitivity smoke test.

---

# 3. P0 — Validator không bảo vệ immutable source fields

Đây là lỗi quan trọng nhất trước human annotation.

Validator hiện chỉ đọc row counts, annotation-unit IDs và human decision fields. Nó không đối chiếu các field nguồn với pilot:

```text
source_term
definition_en
candidate_target_vi
source_text
sense_id
context_role
matched_surface_exact
content_sha256
```

Mutation test:

```text
Thay source_text bằng "TAMPERED SOURCE TEXT"
→ validator vẫn PASS
```

Sau khi annotator chỉnh CSV, manifest file hash đương nhiên sẽ thay đổi. Vì vậy manifest hiện tại không còn đủ để phát hiện việc source cells bị sửa nhầm.

## Hậu quả

- annotator có thể vô tình sửa source sentence hoặc candidate;
- row có thể bị chuyển nhầm sense;
- kết quả annotation vẫn báo PASS;
- audit không chứng minh người chấm nhìn đúng dữ liệu pilot.

## Sửa bắt buộc

Một trong hai phương án:

### Phương án A — So sánh trực tiếp với pilot

Thêm CLI:

```text
python validate_annotations.py REVIEW_ROOT \
  --pilot-root PILOT_ROOT
```

Validator load `term_senses.jsonl`, `candidate_instances.jsonl`, `contexts.jsonl` và xác minh mọi non-human field.

### Phương án B — Row payload hash

Mỗi annotation row có:

```text
source_payload_sha256
```

Hash canonical JSON của toàn bộ immutable fields. Validator tính lại hash sau khi CSV được chỉnh.

Nên hỗ trợ cả hai; `--pilot-root` là nguồn sự thật mạnh nhất.

---

# 4. P0 — Hai reviewer chưa được kiểm tra là độc lập

Contract tuyên bố:

```text
independent_reviewer_count = 2
```

Nhưng validator chỉ kiểm tra hai status là `REVIEWED`; không kiểm tra reviewer IDs khác nhau.

Mutation test:

```text
reviewer_1_id = same-person
reviewer_2_id = same-person
adjudicator_id = same-person
→ validator PASS
```

Như vậy câu “ADJUDICATED requires two completed independent reviews” chưa được thực thi đầy đủ.

## Sửa bắt buộc

Khi row được adjudicate:

```text
reviewer_1_id != reviewer_2_id
```

Nên thêm policy riêng cho adjudicator:

```text
adjudicator_may_be_reviewer: true/false
```

Nếu luận văn yêu cầu rater thứ ba:

```text
adjudicator_id != reviewer_1_id
adjudicator_id != reviewer_2_id
```

Nếu adjudication là phiên họp hai reviewer, cho phép một reviewer ghi kết quả nhưng phải khai policy rõ.

---

# 5. P0 — Invalid context đang bị ép gắn C1–C5

Trong `validate_annotations.py`, context row luôn bắt buộc:

```text
context_type ∈ {C1, C2, C3, C4, C5}
```

kể cả khi:

```text
same_sense_label = NOT_SAME_SENSE
context_validity = INVALID
```

Mutation test:

```text
NOT_SAME_SENSE + INVALID + context_type blank
→ validator FAIL "invalid context type"
```

Điều này buộc annotator gán một loại C giả cho context không thuộc sense hoặc không hợp lệ.

## Sửa bắt buộc

Cross-field policy nên là:

```text
SAME_SENSE + VALID/WEAK
→ context_type bắt buộc C1–C5

NOT_SAME_SENSE hoặc INVALID
→ context_type phải blank hoặc NOT_APPLICABLE

UNCERTAIN
→ context_type có thể blank
```

Thêm enum:

```text
NOT_APPLICABLE
```

hoặc cho phép chuỗi rỗng trong các trường hợp trên.

---

# 6. P1 — Validator chưa kiểm tra cross-table identity

Validator chỉ kiểm tra duplicate trong từng file.

Mutation test:

```text
Đổi một contrastive context_id thành context_id đang có trong context sheet
→ validator vẫn PASS
```

Cần kiểm tra:

```text
contrastive_context_ids ∩ same_sense_context_ids = ∅
```

và mọi row phải khớp đúng annotation unit từ pilot.

Vấn đề này cũng được giải quyết nếu triển khai `--pilot-root`.

---

# 7. P1 — Candidate relation target còn có thể chứa dữ liệu rác

Validator kiểm tra target khi relation là:

```text
MORPHOLOGICAL_VARIANT
DUPLICATE
```

Nhưng với:

```text
INDEPENDENT_ALTERNATIVE
UNCERTAIN
```

target có thể chứa một ID không tồn tại mà vẫn PASS.

Mutation test:

```text
relation = INDEPENDENT_ALTERNATIVE
target = does-not-exist
→ validator PASS
```

Nên khóa:

```text
MORPHOLOGICAL_VARIANT / DUPLICATE
→ target bắt buộc, cùng sense, không phải self

INDEPENDENT_ALTERNATIVE / UNCERTAIN
→ target phải blank
```

Nên phát hiện thêm cycle:

```text
A variant of B
B variant of A
```

và duplicate chain không có canonical root.

---

# 8. P1 — Partial mode có thể báo PASS cho draft không nhất quán

Khi status chưa phải `REVIEWED`, validator bỏ qua toàn bộ decision fields.

Ví dụ:

```text
reviewer_1_status = IN_PROGRESS
reviewer_1_candidate_rank = abc
reviewer_1_candidate_decision = UNKNOWN
```

có thể vẫn PASS.

Điều này không ảnh hưởng `--require-complete`, nhưng dễ làm báo cáo partial mode gây hiểu nhầm.

Nên:

- validate mọi nonblank field dù status đang `IN_PROGRESS`;
- warning nếu human fields có dữ liệu nhưng status trống;
- strip whitespace trước validation;
- kiểm tra timestamp ISO-8601.

---

# 9. P1 — Annotation contract và validator đang lặp policy

`annotation_contract.json` mô tả policy, nhưng validator không đọc file này. Enum và constraints được hardcode lần hai trong Python.

Nguy cơ:

```text
contract đổi
validator không đổi
→ hai nguồn sự thật lệch nhau
```

Nên để validator load `annotation_contract.json`, hoặc sinh cả contract và validator constants từ một schema chung.

---

# 10. Tuyên bố 11/11 test

Hai artifact có:

- validator source;
- commands;
- packaged validation report.

Mình xác minh validator chạy và blank template báo PASS. Tuy nhiên ZIP không chứa test suite hoặc test report liệt kê 11 test, nên chưa thể audit chính xác tuyên bố `11/11`.

Nên đóng gói:

```text
test_report.json
test_case_ids
command
validator_sha256
```

Mình đã chạy mutation tests độc lập và kết quả cho thấy validator có cả các kiểm tra đúng và các lỗ hổng nêu trên.

---

# 11. Human review có thể bắt đầu chưa?

Chưa nên nhập nhãn vào bản V1.1 hiện tại, vì sửa schema sau khi annotation bắt đầu sẽ gây migration.

Hãy tạo patch nhỏ:

```text
pilot_normalized_review_pack_v1_2
```

Không cần sửa pilot ZIP.

## Patch tối thiểu

1. `--pilot-root` hoặc `source_payload_sha256`.
2. Enforce `reviewer_1_id != reviewer_2_id`.
3. Cho phép `NOT_APPLICABLE` context type khi invalid/not-same-sense.
4. Cross-table context ID validation.
5. Require blank relation target cho independent/uncertain.
6. Thêm validator test report.

Sau đó:

```text
blank-template validation
→ PASS

human annotation
→ reviewer 1
→ reviewer 2
→ adjudication
→ --require-complete
→ PASS
```

---

# 12. Phán quyết cuối

```text
PILOT DEV-ONLY V1.1:
ACCEPTED

REFERENCE CLOSURE:
PASS

RETRY/REPLACEMENT DATA:
PASS

REVIEW PACK V1.1:
CONDITIONAL PASS

HUMAN ANNOTATION:
BLOCKED UNTIL VALIDATOR V1.2

LIVE CST:
BLOCKED UNTIL HUMAN REVIEW COMPLETE

THRESHOLD CALIBRATION:
CORRECTLY NOT ALLOWED
```

Không cần tạo lại V3 hoặc pilot data. Chỉ cần sửa review-pack validator/schema trước khi bắt đầu annotation.
