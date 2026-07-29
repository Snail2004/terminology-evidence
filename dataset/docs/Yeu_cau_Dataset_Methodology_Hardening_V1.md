# YÊU CẦU GIA CỐ DATASET CHO THIẾT KẾ THỰC NGHIỆM

**Tên artifact mục tiêu:** `dataset_methodology_hardening_v1`  
**Vai trò:** Companion artifact bổ sung cho dataset đã freeze  
**Nguyên tắc:** Không sửa hoặc ghi đè `d2l_context_support_set_validation_ready_v3`

---

## 1. Mục tiêu

Tạo một artifact bổ sung để:

- bảo đảm context của C là câu thật từ corpus;
- hỗ trợ bootstrap, confidence interval và paired comparison;
- bổ sung controlled corpus cho E;
- tạo adversarial subset độc lập một phần;
- tạo dữ liệu sense drift cho TAC;
- khóa trước cách chọn downstream blocks;
- tăng provenance và khả năng audit.

Artifact này không thay thế dataset V3 và không làm thay đổi manifest/hash hiện tại của V3.

---

## 2. Quy tắc bất biến

1. Không sửa record trong `d2l_context_support_set_validation_ready_v3`.
2. Không đổi `candidate_id`, `sense_id`, `scope_id` hoặc split đã freeze.
3. Không tạo nhãn người giả.
4. Không đưa synthetic context vào C score.
5. Không dùng validation/test để chỉnh prompt hoặc policy sau khi mở.
6. Mọi artifact mới phải bind tới parent dataset manifest.
7. Mọi thay đổi phải có version, checksum và validation report.

---

## 3. Audit corpus-only context cho C

### 3.1. Yêu cầu

Toàn bộ `same_sense_contexts` và `contrastive_contexts` dùng cho Context Substitution phải:

- được trích nguyên văn từ D2L hoặc corpus nguồn thật;
- có provenance đầy đủ;
- có term span và offsets xác định được;
- không phải câu do LLM sinh hoặc viết lại.

LLM chỉ được phép:

- lọc;
- phân loại sense;
- gán loại C1–C5;
- xếp hạng informativeness;
- đề xuất loại context không hợp lệ.

LLM không được phép viết context mới.

### 3.2. Metadata bắt buộc

```text
context_id
document_id
chapter_id
block_id
sentence_id
source_text
source_start_offset
source_end_offset
term_start_offset
term_end_offset
source_hash
origin
extraction_method
context_type
sense_id
scope_id
```

Allowed value:

```text
origin = CORPUS_EXTRACTED
```

Nếu cần lưu synthetic context cho mục đích khác:

```text
origin = SYNTHETIC_CONTROLLED
```

nhưng record này không được đưa vào:

```text
C score
C support set chính
TAC reference support set chính
```

### 3.3. Output audit

```text
corpus_origin_audit.csv
```

Mỗi context phải có trạng thái:

```text
PASS_CORPUS_EXTRACTED
FAIL_SYNTHETIC
FAIL_REWRITTEN
FAIL_OFFSET_INVALID
FAIL_SOURCE_HASH_MISMATCH
FAIL_PROVENANCE_INCOMPLETE
```

---

## 4. Metadata phục vụ thống kê

Bổ sung các khóa ổn định:

```text
candidate_id
candidate_version
sense_id
scope_id
split
document_id
occurrence_id
pairing_id
resampling_group_id
source_block_cluster_id
```

### 4.1. Ý nghĩa

- `pairing_id`: dùng để ghép cùng candidate hoặc occurrence giữa hai hệ thống khi chạy McNemar.
- `resampling_group_id`: đơn vị bootstrap; đề xuất dùng term-sense để tránh coi các candidate cùng sense là độc lập hoàn toàn.
- `source_block_cluster_id`: dùng để bootstrap hoặc split theo block, tránh leakage.
- `occurrence_id`: khóa cho downstream/TAC evaluation.

### 4.2. Quy tắc

Không tạo ID theo row order.

ID phải:

- deterministic;
- ổn định qua lần chạy lại;
- có thể tái tạo từ source identity;
- không thay đổi khi file được sắp xếp lại.

---

## 5. Controlled Vietnamese Corpus Registry cho E

### 5.1. Mục tiêu

Bổ sung danh sách nguồn tiếng Việt có kiểm soát, thay vì chỉ phụ thuộc web mở.

### 5.2. Loại nguồn

```text
UNIVERSITY_TEXTBOOK
UNIVERSITY_LECTURE
PUBLISHED_TRANSLATED_BOOK
PEER_REVIEWED_PAPER
THESIS_DISSERTATION
OFFICIAL_VENDOR_DOCUMENTATION
GOVERNMENT_OR_STANDARDS_DOCUMENT
OPEN_WEB
```

### 5.3. Metadata bắt buộc

```text
source_id
source_tier
organization_id
organization_name
document_id
title
publication_type
publisher
author
publication_year
url_or_catalog_ref
language
domain
content_hash
retrieved_at
machine_translation_suspected
dedup_group_id
license_or_access_note
```

### 5.4. Quy tắc

- Cùng tổ chức không đồng nghĩa cùng document.
- Duplicate document và organization independence phải được tách riêng.
- Không mặc định mọi PDF là nguồn authority cao.
- `machine_translation_suspected` chỉ là cờ rủi ro, không phải bằng chứng kết luận.
- `INSUFFICIENT_EVIDENCE` là kết quả hợp lệ và phải được thống kê.

### 5.5. Output

```text
controlled_vietnamese_source_registry.jsonl
```

---

## 6. Adversarial set độc lập một phần

### 6.1. Hai nguồn case

```text
AUTHOR_DESIGNED
BLIND_SECOND_PARTY
```

### 6.2. Quy tắc

- Freeze protocol sinh adversarial trước khi chỉnh gate logic.
- Người hoặc agent tạo blind subset không được xem implementation gate cuối.
- Không trộn adversarial vào development/validation/test chính.
- Báo cáo riêng kết quả theo nguồn case.

### 6.3. Loại adversarial đề xuất

```text
POPULAR_WRONG_CALQUE
WRONG_SENSE_NATURAL_CANDIDATE
UNRESOLVED_POLYSEMY
TARGET_COLLISION
HIGH_ROUNDTRIP_BUT_WRONG
MODEL_SELF_PREFERENCE
TAIL_CONTEXT_FAILURE
CONTRADICTION
INSUFFICIENT_EVIDENCE_TRAP
```

### 6.4. Metadata

```text
adversarial_id
generation_source
creator_id
creation_protocol_version
source_term
candidate_vi
sense_id
scope_id
attack_type
expected_gate
blind_status
opened_at
adjudication_status
```

### 6.5. Output

```text
adversarial_manifest.json
```

---

## 7. TAC Sense-Drift Evaluation Set

### 7.1. Hai nhóm

```text
NATURAL_DRIFT
SYNTHETIC_CONTROLLED_DRIFT
```

### 7.2. Mục tiêu

Tạo dữ liệu đủ để calibration threshold `tau` cho TAC Tier 2 theo:

```text
sense_drift_recall
escalation_rate
false_escalation_rate
```

### 7.3. Synthetic drift

Synthetic drift phải:

- dùng cùng source surface;
- thay đổi sense hoặc domain;
- giữ provenance của occurrence được chèn;
- không làm thay đổi C evidence;
- chỉ dùng cho TAC evaluation/calibration.

Ví dụ:

```text
inference — statistical inference
inference — model execution
```

### 7.4. Metadata

```text
tac_case_id
source_term
original_sense_id
injected_sense_id
original_scope_id
injected_scope_id
source_domain
target_domain
drift_type
injection_method
is_synthetic
source_occurrence_ref
expected_class
```

Allowed `expected_class`:

```text
SAME
RELATED
DIFFERENT
AMBIGUOUS
```

### 7.5. Output

```text
tac_drift_manifest.json
```

---

## 8. Downstream Block Selection cho A–D

### 8.1. Mục tiêu

Khóa trước danh sách block dùng cho thí nghiệm:

```text
A — không glossary
B — raw glossary
C — validated glossary
D — validated glossary + TAC
```

Cùng một block phải được dùng ở cả bốn nhánh.

### 8.2. Tiêu chí chọn

```text
terminology_density
ambiguous_term_count
multi_sense_term_count
collision_risk_count
candidate_competition_count
tail_context_count
block_length
domain_subsection
```

### 8.3. Quy tắc

- Freeze danh sách block trước khi xem output A–D.
- Không chọn block dựa trên việc hệ thống nào cho kết quả đẹp hơn.
- Được phép chủ đích chọn block giàu thuật ngữ khó vì đó là population mục tiêu.
- Phải ghi rõ giới hạn generalization.

### 8.4. Metadata

```text
block_id
document_id
chapter_id
terminology_density
ambiguous_term_count
multi_sense_term_count
collision_risk_count
selection_reason
block_selection_policy_version
selected_before_model_run
```

### 8.5. Output

```text
downstream_block_selection.jsonl
```

---

## 9. Parent binding và provenance

Mọi artifact phải có:

```text
parent_dataset_schema_id
parent_dataset_schema_version
parent_dataset_manifest_sha256
artifact_schema_id
artifact_schema_version
artifact_manifest_sha256
generation_policy_version
created_at
created_by
record_count
split_summary
leakage_audit_ref
```

Mọi record dẫn xuất phải lưu:

```text
parent_record_id
parent_record_sha256
transformation_id
transformation_version
```

---

## 10. Validation bắt buộc

### 10.1. Corpus context

```text
0 synthetic context trong C primary support set
100% context có source hash hợp lệ
100% offsets nằm trong source text
100% context có document/block/sentence provenance
```

### 10.2. Statistical metadata

```text
pairing_id không null cho paired experiments
resampling_group_id deterministic
không duplicate occurrence_id
không leakage giữa split theo source cluster
```

### 10.3. E registry

```text
source tier hợp lệ
document hash không null
duplicate group hợp lệ
organization_id tách khỏi document_id
```

### 10.4. Adversarial

```text
AUTHOR_DESIGNED và BLIND_SECOND_PARTY được tách rõ
blind subset chưa bị mở trước thời điểm freeze gate
expected gate không được dùng làm runtime input
```

### 10.5. TAC drift

```text
natural và synthetic tách riêng
synthetic cases không xuất hiện trong C scoring dataset
expected class đầy đủ
```

### 10.6. Downstream

```text
cùng block IDs cho A/B/C/D
selection policy được freeze trước model run
```

---

## 11. Artifact bàn giao

```text
dataset_methodology_hardening_v1.zip
dataset_methodology_hardening_v1.zip.sha256
methodology_protocol.md
corpus_origin_audit.csv
controlled_vietnamese_source_registry.jsonl
adversarial_manifest.json
tac_drift_manifest.json
downstream_block_selection.jsonl
validation_report.json
CHECKSUMS.sha256
manifest.json
```

---

## 12. Không thuộc phạm vi Dataset Agent

Dataset Agent không được:

- sửa thuật toán C;
- sửa thuật toán E;
- đặt trọng số C/E;
- đặt threshold;
- tạo decision cuối;
- tạo human label giả;
- sửa validation/test sau khi freeze;
- đưa expected adversarial label vào runtime input;
- thay đổi raw dataset V3.

---

## 13. Definition of Done

Chỉ báo hoàn thành khi:

1. dataset V3 không bị sửa;
2. companion artifact bind đúng parent manifest;
3. toàn bộ C contexts được audit là corpus-extracted;
4. statistical IDs đầy đủ và deterministic;
5. controlled Vietnamese source registry hợp lệ;
6. adversarial set có blind subset độc lập;
7. TAC drift tách natural/synthetic;
8. downstream block list được pre-register;
9. leakage audit pass;
10. manifest và checksum pass;
11. không có secret, `.pyc`, `__pycache__`;
12. validation report nêu rõ các record chưa đạt.

---

## 14. Prompt giao Dataset Agent

```text
Bạn là Dataset Agent.

Không sửa hoặc ghi đè d2l_context_support_set_validation_ready_v3.
Hãy tạo companion artifact dataset_methodology_hardening_v1 để gia cố
thiết kế thực nghiệm.

Công việc gồm:

1. Audit toàn bộ context dùng cho C; chỉ chấp nhận câu trích nguyên văn từ
   corpus thật. LLM chỉ được lọc/phân loại, không viết context.
2. Bổ sung provenance, offsets, source hash và origin cho context.
3. Bổ sung pairing_id, resampling_group_id, source_block_cluster_id và
   occurrence_id phục vụ bootstrap, confidence interval và McNemar.
4. Tạo controlled Vietnamese corpus registry cho E với source tier,
   organization independence, MT suspicion và dedup metadata.
5. Tạo adversarial subset riêng gồm AUTHOR_DESIGNED và BLIND_SECOND_PARTY;
   freeze protocol trước khi gate logic được xem dữ liệu blind.
6. Tạo TAC sense-drift evaluation set, tách NATURAL_DRIFT và
   SYNTHETIC_CONTROLLED_DRIFT. Synthetic cases không được trộn vào C evidence.
7. Tạo danh sách downstream blocks giàu thuật ngữ theo tiêu chí pre-registered
   và dùng cùng block cho A/B/C/D.
8. Mọi artifact phải bind parent manifest, có checksum, leakage audit,
   split summary và version.

Không sửa thuật toán C/E, không tạo nhãn người giả, không thay đổi
validation/test sau khi freeze và không gọi API ngoài nếu không được cấp phép.

Bàn giao đầy đủ ZIP, checksum, manifest, methodology protocol,
các registry/manifest con và validation report.
```
