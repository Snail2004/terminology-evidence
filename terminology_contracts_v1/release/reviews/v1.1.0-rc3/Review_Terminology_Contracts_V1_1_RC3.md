# INDEPENDENT REVIEW — TERMINOLOGY CONTRACTS V1.1 RC3

**Artifact:** `terminology_contracts_v1_1_rc3.zip`
**Artifact SHA-256:** `25e8705631d52cccc8620dc0936c3245897b694abf8eafd8e9f54e0bd94b34f3`
**Reviewed release channel:** `v1.1.0-rc3`

## Verdict

```text
RELEASE ENGINEERING: PASS
RC2 BLOCKERS: CLOSED
COMMON AUTHORITY FREEZE: BLOCKED
PUBLISH TO C / E / GLOBAL VALIDATOR / TAC: NOT YET
RECOMMENDED NEXT CANDIDATE: v1.1.0-rc4
```

RC3 đã sửa đúng các vấn đề của RC2: producer gate-signal projection, sealed
per-gate action policy, collision-index binding và threshold-stability metadata.

Independent execution:

```text
ZIP SHA-256: PASS
Internal checksums: PASS
Manifest: PASS
Tests without real dataset root: 89 passed, 2 skipped
Tests with real V3 + pilot: 91 passed
Static compile: PASS
ZIP safety and packaged cache scan: PASS
```

Tuy nhiên, certificate hiện chưa phải một projection bất biến từ các artifact đã
được kiểm định. Có thể sửa các trường ảnh hưởng trực tiếp tới TAC, reseal
certificate, rồi toàn bộ `verify_certificate_bundle(...)` vẫn PASS.

---

# P0-RC3-1 — Certificate application contract is not bound to source artifacts

## Reproduced mutations accepted by the bundle verifier

Các certificate sau đều được reseal và được `verify_certificate_bundle(...)`
chấp nhận:

```text
allowed_variants = ["hoàn toàn sai"]
forbidden_candidates = []
scope_note = "Valid in every domain and every context."
evidence_summary.C_mean = 0.01
evidence_summary.E_features = arbitrary values
threshold_version = "arbitrary-threshold-v999"
```

Các hash của Frozen Candidate, C, E, gates, decision, calibration và policy vẫn
trỏ tới artifact thật; chỉ nội dung certificate bị sửa.

## Impact

- Có thể thêm variant chưa từng được C xác nhận.
- Có thể xóa blacklist đã được freeze.
- Có thể mở rộng scope sau khi candidate đã được duyệt.
- Có thể ghi summary không phản ánh C/E thật.
- TAC có thể tin vào certificate đã bị mở rộng dù decision và evidence gốc không
  cho phép.

Đây là lỗi authority-boundary, không chỉ là lỗi hiển thị báo cáo.

## Required patch

Trong `verify_certificate_bundle(...)`, bắt buộc kiểm tra tối thiểu:

```text
certificate.allowed_variants
    == frozen_candidate.surfaces.validated_variants_vi

certificate.forbidden_candidates
    == frozen_candidate.surfaces.rejected_variants_vi

certificate.scope_note
    == frozen_candidate.scope_note

certificate.evidence_summary.C_mean
    == context_evidence.features.C_mean

certificate.evidence_summary.E_features
    == attestation_evidence.features

certificate.threshold_version
    == canonical calibration operating-point/version identifier
```

Nếu muốn certificate chỉ lấy một subset variant hoặc blacklist, phải có một
sealed `ApplicationContractPolicy` và hash của policy đó. Không cho issuer tự
chọn subset bằng code không được contract hóa.

Nên kiểm tra thêm:

```text
certificate.issued_at >= decision.run_metadata.completed_at
certificate.policy_version == decision.decision_policy.policy_version
```

Trường policy version đã được kiểm tra; timestamp ordering chưa được kiểm tra.

---

# P0-RC3-2 — Contrastive or negative contexts can become certificate validity contexts

## Reproduction

Certificate fixture ban đầu dùng positive context `ctx-1`.

Tôi thay:

```text
validity_context_refs =
    context_evidence.support_set.contrastive_refs
```

tức dùng `ctx-x1`, một contrastive/out-of-scope context, rồi reseal certificate.

Kết quả:

```text
verify_certificate_bundle(...) → PASS
```

Tôi đồng thời nhúng certificate đã sửa vào TAC occurrence input, reseal TAC và
chạy bundle verification:

```text
TAC bundle verification → PASS
```

## Root cause

Verifier hiện gộp:

```text
positive_support_refs
contrastive_refs
negative_or_boundary_refs
```

rồi chấp nhận `validity_context_refs` thuộc bất kỳ nhóm nào.

## Impact

TAC Tier 2 có thể dùng context khác sense hoặc context biên làm vùng tham chiếu
hợp lệ. Điều này có thể mở rộng certificate sang đúng loại occurrence mà
contrastive test được tạo ra để loại trừ.

## Required patch

Với V1.1, nên khóa:

```text
certificate.validity_context_refs
    == context_evidence.support_set.positive_support_refs
```

Không nhận:

```text
contrastive_refs
negative_or_boundary_refs
```

Nếu cần chọn subset của positive refs, phải thêm một versioned support-selection
policy và bind hash của policy đó vào certificate. Lựa chọn an toàn và đơn giản
cho V1.1 là exact set equality.

---

# P1 hardening recommendations

## P1-1 — Native gate signals are semantic-required but not JSON-schema-required

`gate_signals` không nằm trong `required` của C/E V1.1 schema; semantic validator
mới bắt buộc nó. Agent dùng JSON Schema đơn lẻ có thể tưởng payload hợp lệ.

Patch đề xuất:

- thêm conditional requirement cho native V1.1; hoặc
- ghi nổi bật trong producer guides rằng JSON Schema validation không đủ và CI
  bắt buộc gọi official semantic validator.

## P1-2 — Standalone GateResultSet validation does not load gate policy

Per-gate action được kiểm tra khi validate Global Decision, nhưng validate riêng
`GateResultSetV1` không đối chiếu `GatePolicyArtifact`.

Patch đề xuất:

```text
validate_gate_result_with_policy(...)
```

và dùng hàm này trong Global Validator CI trước khi tạo decision.

---

# Release recommendation

Không publish RC3 như frozen authority.

Quy trình đề xuất:

```text
RC3 giữ nguyên làm review candidate
→ Contract Steward vá certificate derivation/binding
→ phát hành terminology_contracts_v1.1.0-rc4
→ chạy regression tests
→ independent review ngắn
→ merge vào main
→ tag contracts-v1.1.0
→ publish đúng tag cho toàn bộ agents
```

## Regression tests bắt buộc cho RC4

Các mutation sau phải bị reject:

```text
injected allowed variant
removed frozen rejected variant
expanded scope_note
fabricated C_mean/E_features summary
arbitrary threshold_version
contrastive context used as validity context
negative/boundary context used as validity context
TAC embedding a certificate with any mutation above
certificate issued before decision completion
```

## Publication rule

C, E và Global Validator vẫn có thể tiếp tục internal development. Không khóa
serializer/certificate/TAC integration vào RC3 và không phát certificate authority
dựa trên RC3.
