# REVIEW ĐỘC LẬP — TERMINOLOGY CONTRACTS V1.1 RC2

**Artifact:** `terminology_contracts_v1_1_rc2.zip`
**SHA-256:** `2530ebf80d4826a740d1d1efad5952adf8611cec67797d7bd806731a15cb1954`
**Declared channel:** `v1.1.0-rc2`

## Verdict

```text
RELEASE ENGINEERING: PASS
RC1 FINDINGS: CLOSED
COMMON AUTHORITY FREEZE: BLOCKED
PUBLISH TO C / E / GLOBAL VALIDATOR: NOT YET
```

RC2 đã sửa đúng toàn bộ blocker được nêu trong review RC1. Tuy nhiên, review độc lập phát hiện hai lỗi mới ở **liên kết evidence → hard gates**. Hai lỗi này cho phép một Global Validator sai implementation vẫn tạo quyết định hợp lệ theo contract, kể cả khi C/E đã báo tín hiệu phải chặn.

---

## 1. Những phần đã xác minh đạt

- ZIP SHA-256 khớp file checksum bên ngoài.
- `CHECKSUMS.sha256` nội bộ: PASS.
- Manifest: PASS.
- Cấu trúc ZIP an toàn; không traversal, symlink, `.pyc`, `__pycache__`.
- Credential scan: không phát hiện secret.
- Legacy V1.0 được giữ.
- Migration deterministic trên fixtures.
- Dataset mapping chạy với V3 và development pilot.
- Independent test:
  - không khai báo dataset root: `77 passed, 2 skipped`;
  - với V3 + pilot thật: `79 passed`.
- Frozen Candidate stale binding bị từ chối.
- Frozen score được replay từ logistic model.
- Empty/unknown/missing decision features bị từ chối.
- Global Input đã chứa Effective Sense, Frozen Candidate và Constraint Evidence.
- Full replay hash đã bind input/features/gates.
- Certificate bundle verifier phát hiện random artifact hash.
- TAC span binding hoạt động.
- `NaN`/`Infinity` bị từ chối.
- Frozen calibration chỉ hỗ trợ logistic regression.
- Feature mapping đã machine-readable.
- Gate IDs unique và đầy đủ.

---

# Blocking findings mới

## P0-N1 — C/E evidence không bắt buộc được chiếu sang GateResultSet

### Đã tái hiện

Các case sau vẫn validate thành công với gate tương ứng để `triggered=false`:

```text
ContextEvidence:
  contrastive_status = ABSENT
  flag = missing_contrastive_context

GateResult:
  missing_contrastive_context.triggered = false

→ Frozen AUTO_APPROVED vẫn hợp lệ
```

```text
AttestationEvidence:
  local_status = ATTESTATION_UNJUDGEABLE
  accepted_evidence_refs = []

GateResult:
  attestation_unjudgeable.triggered = false

→ Frozen AUTO_APPROVED vẫn hợp lệ
```

```text
ContextEvidence:
  local_status = CONTEXT_UNSUPPORTED
  flag = wrong_sense / CRITICAL

GateResult:
  wrong_sense.triggered = false

→ Frozen AUTO_APPROVED vẫn hợp lệ
```

Validator hiện chỉ chiếu ba constraint:

```text
sense_definition_unverified
unresolved_polysemy
target_collision
```

Nó chưa chiếu các tín hiệu deterministic từ C/E.

### Tác động

Hard gates là contribution trung tâm, nhưng contract hiện cho phép Global Validator bỏ qua chính các hard flags do C/E cung cấp.

### Patch bắt buộc

Chọn một thiết kế canonical:

**Khuyến nghị: thêm `gate_signals` vào C/E package**

```json
{
  "gate_signals": [
    {
      "gate_id": "wrong_sense",
      "asserted": true,
      "reason_codes": ["CONTEXT_WRONG_SENSE"],
      "evidence_refs": []
    }
  ]
}
```

C/E chỉ assert tín hiệu; không chọn global action.

Sau đó semantic validator phải kiểm tra:

```text
asserted=true  → GateResult.triggered=true
asserted=false → không được tự kích hoạt trừ khi nguồn khác assert
```

Tối thiểu phải enforce:

```text
missing_contrastive_context
incomplete_context_type_coverage
attestation_unjudgeable
wrong_sense
concept_mismatch
contradiction
judge_disagreement
insufficient_evidence
```

---

## P0-N2 — Không có policy xác định action hợp lệ theo từng gate

### Đã tái hiện

Payload sau vẫn hợp lệ:

```text
gate_id = wrong_sense
triggered = true
action = CAP_PROVISIONAL
decision = PROVISIONAL
```

Trong kiến trúc đã chốt, `wrong_sense` phải dẫn tới:

```text
FATAL_REJECT
hoặc FATAL_SPLIT
```

Tương tự, contract hiện cho phép:

```text
concept_mismatch → CAP_PROVISIONAL
target_collision → FATAL_REJECT
insufficient_evidence → FATAL_SPLIT
```

miễn action thuộc enum chung và decision khớp precedence.

### Tác động

Các agent có thể triển khai semantics hard gate khác nhau nhưng tất cả vẫn “contract-valid”.

### Patch bắt buộc

Bổ sung một artifact được seal:

```text
GatePolicyArtifactV1
```

Tối thiểu gồm:

```json
{
  "gate_policy_id": "gate-policy-v1",
  "gate_policy_version": "1.0.0",
  "gate_registry_version": "1.1.0",
  "rules": {
    "wrong_sense": {
      "allowed_actions": ["FATAL_REJECT", "FATAL_SPLIT"]
    },
    "concept_mismatch": {
      "allowed_actions": ["FATAL_REJECT"]
    },
    "target_collision": {
      "allowed_actions": ["ESCALATE_HUMAN"]
    },
    "insufficient_evidence": {
      "allowed_actions": ["CAP_PROVISIONAL", "ESCALATE_HUMAN"]
    }
  },
  "integrity": {"self_sha256": "..."}
}
```

Global Decision và Calibration phải bind:

```text
gate_policy_artifact_sha256
```

không chỉ bind một chuỗi `gate_policy_version`.

Validator phải reject action không nằm trong rule của gate.

---

# High-priority hardening

## P1-N1 — Collision index chưa được verify như một artifact

`ConstraintEvidencePackageV1` cho phép:

```text
target_collision.status = CLEAR
collision_index_sha256 = bất kỳ SHA-256 khác zero
```

nhưng không có path/ref hoặc bundle verifier cho collision index.

Nên bổ sung:

```text
collision_index_ref: EvidenceRef
```

và mở rộng bundle verification để load/verify index hoặc một sealed collision-result artifact.

## P1-N2 — Threshold stability metadata chưa phản ánh góp ý phương pháp mới

Calibration hiện có:

```text
confidence_level
precision_lower_bound
uncertainty_method
sample counts
```

nhưng chưa có metadata cho bootstrap operating-point stability.

Nên thêm optional block trước khi freeze:

```json
{
  "threshold_stability": {
    "method": "CLUSTER_BOOTSTRAP",
    "resampling_unit": "sense_id",
    "replicate_count": 1000,
    "threshold_median": 0.84,
    "threshold_ci_lower": 0.78,
    "threshold_ci_upper": 0.90,
    "decision_flip_rate": 0.06
  }
}
```

Điểm này không phá interface C/E, nhưng thêm ngay sẽ tránh phát hành V1.1.1 ngay sau khi tag.

---

# Minor findings

- README mô tả `release/v1.1.0-rc2/` nằm trong package, nhưng ZIP loại thư mục `release`.
- Audit ghi `junit_sha256`, nhưng JUnit không nằm trong các file người dùng gửi để đối chiếu. Test count vẫn được tái hiện độc lập.
- Nên đổi root folder khi merge từ `terminology_contracts_v1_1_rc2/` về đường dẫn ổn định `terminology_contracts_v1/`.

---

# Release plan đề xuất

Giữ RC2 là:

```text
terminology_contracts_v1.1.0-rc2
```

Contract Steward sửa hai P0 trên cùng branch và phát hành:

```text
terminology_contracts_v1.1.0-rc3
```

Re-review tối thiểu cần chứng minh các case sau bị reject:

```text
C reports wrong_sense but gate stays false
C has ABSENT contrastive but gate stays false
E is ATTESTATION_UNJUDGEABLE but gate stays false
wrong_sense uses CAP_PROVISIONAL
concept_mismatch uses ESCALATE_HUMAN/CAP_PROVISIONAL
target_collision uses FATAL_REJECT
insufficient_evidence uses FATAL_SPLIT
decision/calibration references a different gate policy artifact
```

Sau khi pass:

```text
merge chore/contracts-v1.1 → main
tag contracts-v1.1.0
publish đúng commit/tag cho C, E và Global Validator
```
