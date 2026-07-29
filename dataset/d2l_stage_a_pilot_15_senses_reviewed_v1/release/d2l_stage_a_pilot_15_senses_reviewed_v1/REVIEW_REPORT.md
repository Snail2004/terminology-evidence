# D2L Stage A Pilot 15 Sense Reviewed V1

## Phán quyết

Đây là companion artifact sau khi hợp nhất review của ba người. Gói P0 `d2l_stage_a_pilot_15_senses_v1` vẫn bất biến.

- Review hoàn tất về mặt cấu trúc: **15/15 sense**.
- Đủ điều kiện dựng candidate contract: **11/15**.
- Cần xử lý mục tiêu: **4/15**.
- Official runtime contract được phát hành: **0**.
- Stage B gold label được tự động điền: **0**.
- `final_glossary_decision`: **null**; quyết định này thuộc Global Validator.

## Bốn blocker còn lại

| Sense | Trạng thái | Việc cần làm |
|---|---|---|
| in place | `SPLIT_REQUIRED` | `CONSTRUCT_SEPARATE_SENSE_RECORDS_AND_REVIEW_POS_PER_SPLIT` |
| statistical power | `UNRESOLVED` | `REPLACE_WRONG_SENSE_POSITIVE_CONTEXT_WITH_VALID_PRIMARY_EVIDENCE` |
| Adam | `REVISION_REQUIRED` | `PROVIDE_EXACT_CORRECTED_DEFINITION_TEXT_OR_ADDITIONAL_PRIMARY_EVIDENCE` |
| fully-connected layers | `UNRESOLVED` | `ADD_SAME_SENSE_DEFINITION_EVIDENCE_BEFORE_DEFINITION_ACCEPTANCE` |

## Phân loại 15 sense

| Sense | Risk | Cơ sở | Final definition | Final POS | Final scope | Kết quả |
|---|---|---|---|---|---|---|
| null hypothesis | R0_CLEAR | SOURCE_GROUND_PLUS_BLIND_AUDIT | ACCEPT | ACCEPT | ACCEPT | READY_FOR_CONTRACT_CONSTRUCTION |
| attention scoring function | R3_AMBIGUOUS | TWO_REVIEWER_CONSENSUS | ACCEPT | ACCEPT | ACCEPT | READY_FOR_CONTRACT_CONSTRUCTION |
| Jupyter notebook | R3_AMBIGUOUS | TWO_REVIEWER_CONSENSUS | ACCEPT | ACCEPT | ACCEPT | READY_FOR_CONTRACT_CONSTRUCTION |
| in place | R4_SPLIT_OR_POS_RISK | ADJUDICATION | REVISE | REVISE | SPLIT_REQUIRED | SPLIT_REQUIRED |
| statistical power | R3_AMBIGUOUS | ADJUDICATION | UNJUDGEABLE | UNJUDGEABLE | UNJUDGEABLE | UNRESOLVED |
| contexts | R3_AMBIGUOUS | TWO_REVIEWER_CONSENSUS | ACCEPT | ACCEPT | ACCEPT | READY_FOR_CONTRACT_CONSTRUCTION |
| Adam | R3_AMBIGUOUS | ADJUDICATION | REVISE | ACCEPT | ACCEPT | REVISION_REQUIRED |
| Gradient Clipping | R0_CLEAR | SOURCE_GROUND_PLUS_BLIND_AUDIT | ACCEPT | ACCEPT | ACCEPT | READY_FOR_CONTRACT_CONSTRUCTION |
| fully-connected layers | R3_AMBIGUOUS | ADJUDICATION | UNJUDGEABLE | ACCEPT | ACCEPT | UNRESOLVED |
| underflow | R1_QUALIFIED | SINGLE_HUMAN_REVIEW | ACCEPT | ACCEPT | ACCEPT | READY_FOR_CONTRACT_CONSTRUCTION |
| momentum | R0_CLEAR | SOURCE_GROUND_PLUS_BLIND_AUDIT | ACCEPT | ACCEPT | ACCEPT | READY_FOR_CONTRACT_CONSTRUCTION |
| output gate | R2_MISSING | SINGLE_HUMAN_REVIEW | ACCEPT | ACCEPT | ACCEPT | READY_FOR_CONTRACT_CONSTRUCTION |
| learning rate | R3_AMBIGUOUS | TWO_REVIEWER_CONSENSUS | ACCEPT | ACCEPT | ACCEPT | READY_FOR_CONTRACT_CONSTRUCTION |
| word embedding | R3_AMBIGUOUS | TWO_REVIEWER_CONSENSUS | ACCEPT | ACCEPT | ACCEPT | READY_FOR_CONTRACT_CONSTRUCTION |
| vanishing gradients | R3_AMBIGUOUS | TWO_REVIEWER_CONSENSUS | ACCEPT | ACCEPT | ACCEPT | READY_FOR_CONTRACT_CONSTRUCTION |

## Phạm vi dữ liệu

- 15 selected sense, 45 candidate instances, 73 context và candidate index được sao chép nguyên byte từ P0 trong `source_dataset/`.
- Review provenance: 25 slot reviewer (15 reviewer 1, 10 reviewer 2).
- Adjudication: 4 record, gồm disagreement, R4 và E-unjudgeable.
- Blind audit: 3/3 case đã hoàn tất.
- Stage B vẫn là template mở; không có nhãn vàng hoặc Vietnamese attestation giả lập.

## Lineage và kiểm tra

- Parent P0 manifest self-hash: `32b3bbea775362504ef698cfe65a4a9e27890f761d7067b1c88dad7a9670bb6e`.
- Reviewer input hashes: `{'reviewer_1': '54993660d76ceeac435efceb384ece2edd9d757ad6bd226d591409c1610fd238', 'reviewer_2': '0f2672527685aac13fae0053aea2077efa0c538d74cb9c72be2b8312e72abb62', 'blind_audit': '9259a723548b0dba3eb451b55eea64a6416b6c11b93a645e9f2220ee50459a65', 'adjudicator': '93e357475cec456247ada86c33fe07de4751ec40a919da4ea4988b52848adff7'}`.
- Mỗi JSONL decision/provenance/adjudication có self-hash; toàn bộ file có manifest và CHECKSUMS.
- Không gọi provider/API; không sửa contract authority v1.1.0.

## Cách kiểm tra

```text
python -B source/tools/validate_reviewed_pilot.py --artifact-root . --zip-path ../d2l_stage_a_pilot_15_senses_reviewed_v1_reviewer_handoff.zip
```

`source/` chứa builder, validator và test để reviewer có thể tái chạy kiểm định.
