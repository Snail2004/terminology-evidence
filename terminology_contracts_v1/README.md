# Terminology Inter-Module Contracts V1

Đây là **hợp đồng chung bắt buộc** giữa Dataset, Context Substitution (C),
Vietnamese Attestation (E), Global Validator, Calibration, Certificate và TAC.

## Mục tiêu

- C và E có thể thay đổi nội bộ mà không làm hỏng Global Validator.
- Không join bằng text, row order hoặc array index.
- Mọi handoff được khóa bằng `candidate_key`, version và SHA-256.
- C/E chỉ xuất evidence; `final_glossary_decision` luôn `null`.
- Gates và quyết định cuối chỉ thuộc Global Validator.
- Trọng số/threshold không được đặt trước; chỉ xuất hiện trong calibration artifact đã freeze.

## Quy tắc bắt buộc cho agent

1. Đọc `AGENT_RULES.md` trước khi sửa module.
2. Dùng schema trong thư mục `schemas/` làm authority.
3. Không copy field definition sang module riêng rồi tự thay đổi.
4. Mọi breaking change phải tăng major version và có adapter.
5. Dataset/sense/candidate contract phải bất biến trong một run.
6. C và E không được đọc output của nhau.
7. Global Validator phải fail closed khi join key/hash không khớp.
8. Validation/test chỉ được mở bằng calibration artifact đã xác minh.

## Luồng chuẩn

```text
EffectiveSenseContractV1
        ↓
FrozenCandidateContractV1
        ├── ContextEvidencePackageV1
        └── AttestationEvidencePackageV1
                   ↓
          GlobalValidatorInputV1
                   ↓
             GateResultSetV1
                   ↓
        GlobalDecisionPackageV1
                   ↓
       TerminologyCertificateV1
                   ↓
           TACOccurrenceInputV1
```

## Kiểm tra nhanh

```bash
python -m pip install -e .
python -m terminology_contracts.cli validate-dir examples/valid --schema-dir schemas
python -m terminology_contracts.cli validate-global examples/valid/global_validator_input.json --schema-dir schemas
python -m unittest discover -s tests -v
```

`examples/invalid/` là mẫu phải bị validator từ chối.
