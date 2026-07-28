# REVIEW — NORMALIZED REVIEW PACK V1.2
## `pilot_normalized_review_pack_v1_2`

## Kết luận điều hành

V1.2 đã sửa đúng gần như toàn bộ lỗ hổng kỹ thuật của validator V1.1:

- source fields được khóa bằng row payload hash;
- source rows được đối chiếu với pilot qua `--pilot-root`;
- hai reviewer và adjudicator được kiểm tra độc lập;
- invalid/not-same-sense context không bị ép gắn C1–C5;
- cross-table context overlap bị chặn;
- candidate relation target và cycle được kiểm tra;
- populated values trong partial mode được kiểm enum;
- structured whitespace và timestamp timezone được kiểm tra;
- contract, source bindings và immutable files đều có self-hash/file hash hợp lệ.

Tuy nhiên, review pack **chưa nên dùng để bắt đầu đồng thời cả bốn loại annotation**. Có hai vấn đề workflow/decision quan trọng:

1. `--require-complete` đang bắt adjudication cho **mọi annotation unit**, kể cả khi hai reviewer hoàn toàn đồng ý.
2. Definition/POS là upstream contract nhưng context và candidate sheets vẫn khóa theo definition model ban đầu; corrected definition chưa có đường propagate xuống các bước sau.

Phán quyết:

```text
ZIP / MANIFEST INTEGRITY: PASS
SOURCE IMMUTABILITY: PASS
PILOT CROSS-CHECK: PASS
PACKAGED TESTS: 17/17 PASS
PREVIOUS VALIDATOR P0 FIXES: PASS

DEFINITION-REVIEW STAGE: READY
PARALLEL FULL HUMAN ANNOTATION: BLOCKED
COMPLETION / ADJUDICATION POLICY: FAIL
CORRECTED-SENSE PROPAGATION: MISSING
LIVE CST: BLOCKED PENDING HUMAN REVIEW
THRESHOLD CALIBRATION: CORRECTLY DISALLOWED
```

---

# 1. Các tuyên bố đã xác minh

## 1.1. ZIP hash

```text
dfff18997915e05c997b37f265544614f15dbfad31f3e2c3e3d4c2da4e09740c
```

Khớp chính xác giá trị bàn giao.

## 1.2. Manifest và file integrity

Đã xác minh:

- manifest self-hash: PASS;
- annotation contract self-hash: PASS;
- source bindings self-hash: PASS;
- 12/12 file trong manifest khớp SHA-256;
- source pilot binding trỏ đúng `pilot_dev_only_v1_1`;
- V3/pilot parent chain không bị thay đổi.

## 1.3. Row counts

| Bảng | Số row |
|---|---:|
| Definition | 5 |
| Contrastive | 5 |
| Same-sense primary/backup context | 33 |
| Candidate | 15 |
| **Tổng annotation units** | **58** |

## 1.4. Source field binding

Đã đối chiếu trực tiếp với pilot:

- term/sense fields đúng;
- 38 context records đúng;
- candidate records đúng;
- source text đúng;
- exact/normalized matched surface đúng;
- source-record hashes đúng;
- source-payload hashes đúng;
- không có annotation unit trùng hoặc sai bảng.

Mutation `source_text = "tampered source text"` bị validator chặn đúng.

## 1.5. Reviewer và relation validation

Các mutation sau bị chặn đúng:

- cùng một người làm reviewer 1 và reviewer 2;
- adjudicator trùng reviewer;
- foreign/self/stale relation target;
- candidate relation cycle;
- duplicate ranks;
- rank ngoài 1–3;
- invalid enum ở partial mode;
- corrected definition thiếu text;
- invalid contrastive vẫn được đưa vào boundary test;
- structured whitespace;
- timestamp thiếu timezone;
- sửa annotation contract.

## 1.6. Test đóng gói

Đã chạy trực tiếp từ artifact:

```text
17 passed
```

JUnit đóng gói cũng chứa đúng 17 testcase và không có failure/error.

Tuyên bố `28/28 focused và adjacent tests` không được thể hiện trong ZIP hiện tại, nên chỉ xác minh được **17/17 packaged tests**. Có thể 28 test nằm trong repo đầy đủ, nhưng artifact chưa chứa report tương ứng.

---

# 2. P0 — `--require-complete` bắt adjudication trên mọi row

## Hiện trạng

Trong `_validate_actor()`:

```python
complete_status = "ADJUDICATED" if prefix == "adjudicated" else "REVIEWED"

if require_complete and status != complete_status:
    errors.append(...)
```

Validator gọi `_validate_actor()` cho:

```text
reviewer_1
reviewer_2
adjudicated
```

trên tất cả 58 annotation units.

## Mutation test độc lập

Mình điền đầy đủ:

- reviewer 1 = REVIEWED;
- reviewer 2 = REVIEWED;
- hai người khác nhau;
- mọi decision của hai reviewer giống hệt nhau;
- timestamps hợp lệ;
- không điền adjudication vì không có disagreement.

Kết quả:

```text
58 errors
mỗi row: "adjudicated is incomplete"
```

## Vì sao đây là lỗi

Protocol luận văn trước đó là:

> Hai annotator độc lập; adjudication khi có disagreement.

V1.2 đang biến nó thành:

> Mọi row luôn phải có người thứ ba adjudicate.

Điều này:

- tăng 58 lượt adjudication không cần thiết;
- làm sai định nghĩa agreement/adjudication;
- khiến `--require-complete` không phản ánh protocol nghiên cứu;
- có thể tạo artificial third-judge influence trên cả những row đã thống nhất.

## Sửa bắt buộc

Thêm policy:

```json
{
  "adjudication_policy": "ON_DISAGREEMENT"
}
```

Tạo decision signature theo từng table.

### Definition signature

```text
definition_status
corrected definition text khi CORRECTED
```

### Contrastive signature

```text
contrastive_label
use_in_sense_boundary_test
```

### Context signature

```text
same_sense_label
context_type
context_validity
```

### Candidate signature

```text
applicability
semantic_fit_label
candidate_rank
candidate_decision
candidate_relation
relation target
```

Quy tắc:

```text
reviewer 1 và reviewer 2 cùng signature
→ row complete, adjudication phải blank hoặc optional

hai signature khác nhau
→ adjudication bắt buộc
→ adjudicator khác cả hai reviewer
→ adjudicated decision fields đầy đủ
```

Thêm test:

```text
agreement_without_adjudication_passes_require_complete
disagreement_without_adjudication_fails
disagreement_with_third_party_adjudication_passes
```

---

# 3. P0 — Corrected definition chưa propagate xuống context/candidate review

## Hiện trạng

Cả năm pilot sense đang có:

```text
definition_status = MODEL_GROUNDED_PENDING_HUMAN_REVIEW
part_of_speech_status = MODEL_INFERRED_FROM_CORPUS
```

Definition sheet cho phép:

```text
ACCEPTED
CORRECTED
REJECTED
```

Nhưng ba sheet còn lại đã đóng băng:

```text
definition_en = model definition ban đầu
```

và các source fields này được khóa bằng `source_payload_sha256`.

## Tình huống lỗi

1. Hai reviewer sửa definition của `keys`.
2. Adjudicator chốt corrected definition.
3. Context/candidate sheets vẫn hiển thị model definition cũ.
4. Nếu sửa trực tiếp `definition_en` trong các sheet đó, validator báo source tamper.
5. Nếu không sửa, annotator đánh giá context/candidate theo definition lỗi thời.

## Hậu quả

Kết luận CST vẫn có thể bị lệch dù definition review đã hoàn thành đúng.

Đây chính là upstream risk mà kiến trúc đã cảnh báo:

```text
conditional on correct sense identification
```

## Sửa bắt buộc

Human review phải chạy theo hai stage.

### Stage A — Sense contract review

Review:

- definition;
- part of speech;
- scope note nếu có.

Sau adjudication, tạo artifact mới:

```text
pilot_reviewed_sense_contract_v1
```

Mỗi sense có:

```json
{
  "sense_id": "...",
  "effective_definition_en": "...",
  "effective_part_of_speech": "...",
  "definition_source": "MODEL_ACCEPTED | HUMAN_CORRECTED",
  "review_status": "ADJUDICATED",
  "review_provenance": {}
}
```

### Stage B — Context, contrastive và candidate annotation

Regenerate ba sheet từ `effective_definition_en`.

Không chạy Stage B trước khi Stage A hoàn tất.

## POS cũng cần review

Definition sheet hiện chỉ hiển thị `part_of_speech` như immutable source field, không có:

```text
reviewer_1_part_of_speech_status
reviewer_1_corrected_part_of_speech
...
```

Trong pilot, POS vẫn do model infer. CST có tiêu chí grammatical fit nên POS cần được:

```text
ACCEPTED / CORRECTED / UNCERTAIN
```

ở Stage A.

---

# 4. P1 — Rank và morphological/duplicate relation chưa đồng bộ

Trong pilot có trường hợp thực:

```text
keys:
- khóa
- các khóa
```

Hai candidate có thể được gắn:

```text
MORPHOLOGICAL_VARIANT
```

Tuy nhiên validator vẫn bắt mỗi candidate phải có rank duy nhất 1–3.

Điều này có thể buộc annotator:

- xếp hạng giả hai surface vốn cùng lexical candidate;
- biến morphology preference thành terminology preference;
- đếm trùng candidate trong calibration.

## Policy nên chọn một trong hai

### Group-ranking

```text
MORPHOLOGICAL_VARIANT / DUPLICATE
→ relation target bắt buộc
→ rank để blank
→ candidate kế thừa rank của canonical target
```

### Shared rank

Cho phép cùng rank trong cùng equivalence group nhưng vẫn cấm trùng rank giữa các independent alternatives.

Group-ranking đơn giản và dễ phân tích hơn.

---

# 5. P1 — Chưa có finalization artifact sau annotation

Manifest hiện đánh dấu bốn CSV là:

```text
mutable_after_annotation = true
```

Đây là đúng trong giai đoạn nhập nhãn.

Nhưng sau khi chỉnh CSV:

- hash trong manifest vẫn là hash blank template;
- `validation_report.json` vẫn là report PASS của template trắng;
- chưa có immutable manifest cho completed human annotation;
- chưa có hashes của reviewer decisions cuối.

## Cần thêm

```text
finalize_annotations.py
```

Sau khi `--require-complete` PASS, script tạo:

```text
pilot_human_annotations_v1/
├── annotated CSVs
├── final_validation_report.json
├── annotation_manifest.json
├── reviewer/agreement summary
└── SHA-256 cho mọi file
```

Final report nên chứa:

```text
input CSV hashes
validator SHA-256
contract SHA-256
pilot manifest SHA-256
agreement counts
adjudication counts
completed_at
```

`validation_report.json` hiện tại nên đổi tên thành:

```text
template_validation_report.json
```

để tránh bị hiểu nhầm là report của dữ liệu đã annotation.

---

# 6. P1 — Metadata được điền nhưng status rỗng vẫn có thể PASS

Mutation:

```text
reviewer_1_id = "reviewer-a"
reviewer_1_status = ""
mọi decision field = ""
```

Kết quả partial validation:

```text
PASS
```

Validator chỉ bắt “decision populated without status”, chưa bắt actor metadata.

Nên thêm:

```text
actor ID hoặc timestamp hoặc notes có dữ liệu
→ status không được blank
```

Điều này không chặn annotation chính thức khi dùng `--require-complete`, nhưng giúp draft state nhất quán.

---

# 7. P2 — Cross-artifact consistency có thể khóa chặt hơn

Artifact hiện tự nhất quán, nhưng validator chưa kiểm trực tiếp:

- manifest `row_counts` so với actual rows;
- contract `source_pilot_manifest_sha256` so với pilot;
- source bindings `source_pilot_manifest_sha256` so với pilot;
- `schema_version/policy_id` giữa manifest, contract và bindings;
- pilot `manifest_file_sha256` ngoài semantic self-hash.

Không phải lỗi dữ liệu hiện tại, nhưng nên thêm để tránh package creator tạo artifact chéo version.

---

# 8. P2 — Timestamp ordering

Validator kiểm ISO-8601 và timezone đúng, nhưng chưa kiểm:

```text
adjudicated_at >= reviewer_1_reviewed_at
adjudicated_at >= reviewer_2_reviewed_at
```

Nên thêm khi adjudication có mặt.

---

# 9. P2 — Portability

`commands.txt` dùng Windows path:

```text
..\pilot_dev_only_v1_1
validation\test_validator_v1_2.py
```

Phù hợp máy hiện tại, nhưng nên thêm lệnh POSIX hoặc dùng `pathlib`-neutral examples.

---

# 10. Trạng thái sử dụng phù hợp

## Có thể bắt đầu ngay

```text
Stage A:
definition review
```

sau khi sửa conditional adjudication hoặc dùng validator partial trong quá trình nhập.

## Chưa nên bắt đầu

```text
context review
contrastive review
candidate annotation
```

cho tới khi effective definition và POS được freeze.

## Chưa được chạy

```text
live CST
threshold calibration
official precision–coverage
```

---

# 11. Patch đề xuất

Không cần sửa pilot data hoặc V3.

Tạo:

```text
pilot_normalized_review_pack_v1_3
```

Nội dung tối thiểu:

1. `adjudication_policy = ON_DISAGREEMENT`.
2. Conditional completion logic.
3. Definition + POS review Stage A.
4. Effective sense-contract output.
5. Regeneration command cho Stage B sheets.
6. Group-ranking policy cho variants/duplicates.
7. `finalize_annotations.py`.
8. Tests cho workflow mới.
9. JUnit/report của toàn bộ packaged tests.

---

# 12. Phán quyết cuối

```text
REVIEW PACK V1.2 ENGINEERING QUALITY:
TỐT

PREVIOUS VALIDATOR FIXES:
PASS

PACKAGED TESTS:
17/17 PASS

START DEFINITION REVIEW:
CONDITIONAL PASS

START ALL FOUR REVIEW TABLES IN PARALLEL:
BLOCKED

ANNOTATION COMPLETION POLICY:
FAIL — UNCONDITIONAL ADJUDICATION

CORRECTED SENSE CONTRACT HANDOFF:
MISSING

LIVE CST:
BLOCKED PENDING REVIEWED SENSE CONTRACT + HUMAN CONTEXT/CANDIDATE LABELS
```
