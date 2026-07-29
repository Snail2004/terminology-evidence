# INDEPENDENT REVIEW — GLOBAL TERMINOLOGY VALIDATOR V1.1

**Artifact:** `global_validator.zip`  
**Artifact SHA-256:** `6c900a9543486189f5538c88027fd98b61652e3d855869c97733b5d5a0e96017`  
**Claimed implementation commit:** `056b520ede25c40aa3c72ca9785dccecab4691d3`  
**Claimed parent:** `f8f019910fe999a48e8e11d10602e164c8e38105`  
**Review date:** 2026-07-29  
**External API/network calls:** 0

---

## 1. Verdict

```text
CORE ALGORITHM: PASS WITH FINDINGS
STRICT INPUT / JOIN / COLLISION BINDING: PASS
DEVELOPMENT_HEURISTIC: PASS
FROZEN CONTRACT FIXTURE: PASS
ZERO-API SYNTHETIC PILOT: PASS
PRODUCTION AUTO_APPROVAL: CORRECTLY BLOCKED
DECISION AUTHORITY BINDING: FAIL
MERGE READINESS: NEEDS PATCH
OVERALL: CONDITIONAL_ACCEPT_AFTER_RC2
```

Implementation đã bao phủ gần như toàn bộ kiến trúc thuật toán đã giao. Tuy
nhiên, chưa nên merge vào `main` ở trạng thái hiện tại vì Global-owned
gate-action policy chưa được pin như một authority bắt buộc và các lệnh
`verify-decision`/certificate verification chưa chứng minh rằng decision thực
sự được tạo bằng đúng policy/config đó.

---

## 2. Scope và khả năng kiểm chứng Git

Archive chỉ chứa cây:

```text
global_validator/**
```

Không phát hiện file Dataset, C, E hoặc common contracts bị đóng gói vào ZIP.

Số file:

```text
63 file nội dung sạch
110 file vật lý trong ZIP
43 .pyc/__pycache__ files
4 .pytest_cache files
```

Con số 63 phù hợp với handoff. Phần chênh lệch là cache sinh trong quá trình
chạy test.

Archive không chứa `.git` object database, `git bundle` hoặc patch có commit
metadata. Vì vậy reviewer không thể độc lập chứng minh:

```text
commit = 056b520...
parent = f8f0199...
worktree CLEAN
```

Reviewer chỉ có thể xác nhận scope vật lý của ZIP nằm trong
`global_validator/**`.

Trước merge cần cung cấp một trong:

```text
git format-patch
git bundle
git show --stat --name-status <commit>
signed/hashed diff receipt
```

---

## 3. Kết quả chạy độc lập

Tôi dựng lại layout repository với đúng Contracts V1.1.0 và authority receipt
đã công bố.

Do ZIP không có Git history/tag objects, tôi chỉ bypass bước
`git rev-parse contracts-v1.1.0^{commit}` trong bản sao review. Các kiểm tra sau
vẫn chạy thật:

```text
receipt bytes
authority fields
contracts manifest
GatePolicyArtifact hash
feature registry hash
schema and semantic validation
```

Kết quả:

```text
Global Validator tests: 34 passed
Contracts V1.1 tests: 113 passed, 2 skipped
Python parse/compile: PASS
Release report self-hashes: PASS
Release evidence semantic regeneration: PASS
```

Các release report được tạo lại cho nội dung JSON giống hoàn toàn report trong
ZIP. Khác biệt byte chỉ là line ending `CRLF` so với `LF`; canonical self-hash
và semantic fields giống nhau.

Synthetic integration được tái tạo:

```text
5 senses
15 candidates
15 PROVISIONAL
0 AUTO_APPROVED
0 certificate
0 network/provider call
15/15 replay PASS
```

Frozen contract fixture được tái tạo:

```text
approval_score = 0.880481737215655
decision = AUTO_APPROVED
certificate exact projection = PASS
official certificate bundle verification = PASS
fixture_only = true
production_authority = false
```

---

# 4. Những phần đã đạt

## 4.1. Authority boundary

Đã kiểm tra đúng:

```text
authority tag
authority commit field
manifest self/physical hashes
sealed GatePolicyArtifact
feature registry
schema version
```

Exact-byte fallback cho receipt hiện tại là hẹp và fail-closed: chỉ đúng physical
SHA đã công bố mới được chấp nhận.

## 4.2. Strict JSON

Đã từ chối:

```text
duplicate JSON key
NaN
Infinity
trailing garbage
non-object root
```

Đây là hardening tốt hơn shared contracts loader hiện tại.

## 4.3. Input và artifact binding

Đã kiểm tra:

```text
exact candidate key
input_contract_sha256
nested self hashes
assembly package hashes
physical collision index SHA
collision evidence-reference SHA
```

Collision index được kiểm trước gate/score trong cả development lẫn frozen mode.

## 4.4. Gates

Đã có đúng 12 gates theo registry, C/E signal projection, constraint projection
và precedence:

```text
FATAL_SPLIT
> FATAL_REJECT
> ESCALATE_HUMAN
> CAP_PROVISIONAL
> NONE
```

## 4.5. Feature và calibration

Feature assembly dùng registry machine-readable, không hard-code feature vector.

Frozen scoring:

```text
logistic regression only
exact model feature set
threshold from operating point
score replay
exact example-fixture hash
production expected calibration hash
```

Copied example calibration không thể giả làm production calibration.

## 4.6. Certificate

Certificate issuer chiếu chính xác:

```text
allowed variants
rejected variants
scope
positive C support refs
accepted E refs
C_mean
E features
threshold operating-point ID
artifact hashes
```

Official certificate-bundle verifier được gọi trước khi persist certificate.

---

# 5. P0 findings

## P0-GV-1 — Global action-selection policy chưa phải authority bắt buộc

`GatePolicyArtifactV1` chỉ giới hạn tập action được phép. Implementation thêm:

```text
gate_action_selection_v1.0.0.json
SHA-256:
4220b15b7b5d5b740946b9b258a5e1f25469a8f8409ca6e1a0b399464285c9f5
```

Mapping hiện tại là hợp lý:

```text
unresolved_polysemy                  → FATAL_SPLIT
wrong_sense                         → FATAL_REJECT
contradiction                       → FATAL_REJECT
insufficient_evidence               → CAP_PROVISIONAL
missing_contrastive_context         → CAP_PROVISIONAL
incomplete_context_type_coverage    → CAP_PROVISIONAL
attestation_unjudgeable             → CAP_PROVISIONAL
```

Tôi duyệt mapping này làm **Global action policy V1.0**.

Nhưng runtime hiện chấp nhận bất kỳ self-hashed custom policy nào, miễn action
nằm trong `allowed_actions`. CLI cũng cho truyền `--action-policy`.

### Reproduction

Tôi đổi riêng:

```text
unresolved_polysemy:
FATAL_SPLIT → ESCALATE_HUMAN
```

Policy mới vẫn pass loader vì cả hai action đều được shared GatePolicy cho phép.

Cùng một Global Input cho kết quả:

```text
policy mặc định  → SPLIT_REQUIRED
policy thay thế  → HUMAN_REVIEW
```

Không có authority artifact nào buộc operator phải dùng SHA `4220...`.

### Impact

Decision semantics có thể thay đổi theo file do operator cung cấp. Một release
không thể tuyên bố deterministic authority nếu policy chọn action chưa được pin
bên ngoài chính file đó.

### Required patch

Một trong hai phương án:

```text
A. Main authority receipt pin:
   global_gate_action_policy_sha256 = 4220...

B. Global release authority sidecar pin:
   exact policy SHA + main commit + contracts authority
```

Runtime phải yêu cầu expected policy SHA và từ chối policy khác.

Production CLI không được tùy ý nhận một `--action-policy` không có authority
pin.

---

## P0-GV-2 — `verify-decision` không xác minh decision được tạo bằng configured policy

`verify_decision_artifact(...)` hiện chủ yếu gọi common schema/semantic
validator. Nó không rebuild exact gate set và exact decision bằng
`RunConfig.gate_action_policy_path`.

### Reproduction A — thay gate action

Từ decision có:

```text
unresolved_polysemy = FATAL_SPLIT
decision = SPLIT_REQUIRED
```

Tôi đổi và reseal thành:

```text
unresolved_polysemy = ESCALATE_HUMAN
decision = HUMAN_REVIEW
```

Sau đó cập nhật gate hash, replay hash và decision self hash.

`verify-decision` vẫn:

```text
ACCEPTED
```

dù config đang trỏ tới policy mặc định yêu cầu `FATAL_SPLIT`.

### Reproduction B — giả execution config

Tôi thay:

```text
run_metadata.execution_config_sha256 = ffff...ffff
```

rồi tính lại replay/self hashes.

`verify-decision` vẫn:

```text
ACCEPTED
```

Điều này cho thấy `execution_config_sha256` hiện được bind về mặt nội bộ nhưng
không được đối chiếu với config/policy thật được loader cung cấp.

### Required patch

`verify-decision` phải thực hiện exact deterministic recomputation:

```text
load verified Global Input
load exact pinned action policy
load calibration when frozen
rebuild GateResultSet
reassemble features
replay score
resolve decision
build expected GlobalDecisionPackage
compare exact semantic hash/content
```

Không chỉ schema-validate decision do caller đưa vào.

`verify-certificate-bundle` cũng phải gọi bước exact decision recomputation này
hoặc deterministic replay tương đương.

---

# 6. P1 findings

## P1-GV-1 — Timestamp đảo ngược vẫn pass `verify-decision`

Tôi thay:

```text
started_at  = 2026-07-30
completed_at = 2026-07-29
```

rồi reseal decision. `verify-decision` vẫn chấp nhận.

Engine generation path đã kiểm tra time ordering, nhưng external verifier chưa
kiểm tra.

Patch:

```text
started_at <= completed_at
certificate.issued_at >= completed_at
```

ở cả generation và verification path.

---

## P1-GV-2 — Fallback evidence vượt quá phạm vi finding đã báo

Constraint fallback hiện dùng sealed `ConstraintEvidencePackageV1` khi upstream
state không có ref:

```text
UNVERIFIED
UNRESOLVED
UNJUDGEABLE
```

**Tôi chấp nhận convention này**, vì chính trạng thái đã seal trong package là
bằng chứng trực tiếp cho constraint gate.

Tuy nhiên code cũng dùng whole-package fallback cho C/E gate signal khi producer
asserts gate nhưng để `evidence_refs=[]`.

Ví dụ:

```text
wrong_sense asserted
direct refs empty
→ artifact://global-input/c
```

Đây không chỉ là constraint fallback và chưa được handoff mô tả đầy đủ.

Yêu cầu:

```text
fatal semantic C/E gates
(concept_mismatch, wrong_sense, contradiction)
→ direct evidence refs bắt buộc

judge disagreement
→ refs tới context/judge disagreement cụ thể

coverage gates
→ coverage/support-set audit ref
```

Whole-package fallback có thể giữ cho migration/diagnostic, nhưng native COMPLETE
fatal signal không nên chỉ trỏ đến toàn package.

---

## P1-GV-3 — Replay bundle phụ thuộc đường dẫn repository tuyệt đối

`audit/run_spec.json` lưu:

```text
repository_root = absolute local path
```

`replay_run` sau đó quay lại repository đó để:

```text
load contracts tree
verify Git tag
load schemas
```

Vì vậy một run bundle được copy sang máy reviewer khác không tự replay được nếu
không tái tạo đúng repository authority bên ngoài.

Wheel cũng không chứa common contracts/schemas/receipt; nó không phải standalone
runtime artifact.

Patch theo một trong hai hướng:

```text
1. Bundle một immutable authority snapshot cần thiết cho replay;
hoặc
2. Replay CLI nhận --authority-root và verify exact receipt/manifest hashes,
   không bind absolute original path.
```

`repository_root` không nên là authority value được lưu cố định theo máy.

---

## P1-GV-4 — Replay chưa verify CHECKSUMS trước khi chạy

`replay_run` không gọi checksum verification trước khi đọc run spec/input/output.

Certificate bundle verifier có kiểm checksum, nhưng development replay không có
bước tương đương.

Yêu cầu:

```text
replay:
verify CHECKSUMS
verify run-spec/action-policy binding
then recompute decision
```

Nên có external bundle SHA hoặc manifest receipt để phát hiện việc toàn bundle
bị rewrite rồi tự tạo lại CHECKSUMS.

---

## P1-GV-5 — Review ZIP chưa sạch và thiếu release receipt

ZIP chứa:

```text
43 pyc/cache files
4 pytest-cache files
```

Không có:

```text
global_validator release ZIP SHA sidecar
manifest
CHECKSUMS cho source release
environment.json
credential_scan.json
static_scan.json
ownership/diff receipt
Git patch/bundle
```

Các scan được handoff khai báo PASS nhưng chưa có đủ machine-readable artifact
để reviewer xác minh.

---

## P1-GV-6 — Commit và clean-worktree claim chưa thể độc lập kiểm tra

Scope vật lý là đúng, nhưng exact commit/parent/clean state chưa kiểm tra được từ
ZIP.

Bắt buộc thêm:

```text
git_commit_receipt.json
git diff --check output
git status --porcelain output
git show --name-status output
```

và hash các file này trong release manifest.

---

# 7. Authority receipt và calibration

## 7.1. Authority receipt

Exact-byte fallback hiện fail-closed và có thể dùng tạm cho development review.

Nhưng production/common-authority publication vẫn phải chờ maintainer reseal
receipt bằng canonical self-hash đúng. Implementation findings cũng ghi rõ
declared, recomputed và physical hashes khác nhau.

**Verdict:**

```text
development compatibility: ACCEPT
permanent production authority: BLOCKED UNTIL RESEALED
```

## 7.2. Calibration

Implementation đã khóa đúng contract fixture và không cho copy fixture thành
production.

Nhưng `expected_calibration_sha256` do operator nhập chưa phải bằng chứng rằng
artifact đã được human-review. Chưa có external approval anchor.

**Verdict:**

```text
frozen algorithm implementation: ACCEPT
fixture testing: ACCEPT
production AUTO_APPROVED: BLOCKED
production certificate publication: BLOCKED
```

---

# 8. Real pilot

Synthetic 15-candidate fixture chỉ chứng minh:

```text
contract integration
development invariants
storage/replay mechanics
```

Nó không chứng minh semantic quality.

Real pilot chỉ chạy sau khi nhận đủ:

```text
15 Dataset-owned FrozenCandidateContractV1
15 COMPLETE ConstraintEvidencePackageV1
15 official C packages
15 official E packages
15 assembled GlobalValidatorInputV1
```

Không dùng C-local hoặc Global-local Frozen Candidate fixture làm authority.

---

# 9. Regression tests bắt buộc cho RC2

```text
1. action policy hash khác approved SHA → reject
2. custom allowed policy qua --action-policy → reject khi không có matching pin
3. decision gate action khác configured policy → verify-decision reject
4. fake execution_config_sha256 → verify-decision reject
5. started_at > completed_at → reject
6. certificate issued_at < completed_at → reject
7. asserted fatal C/E signal thiếu direct evidence refs → reject
8. replay CHECKSUMS mismatch → reject trước evaluation
9. replay trên authority root mới nhưng cùng exact hashes → pass
10. replay không phụ thuộc original absolute path
11. tampered run_spec action-policy hash → reject
12. certificate bundle phải exact-replay decision trước PASS
```

Giữ toàn bộ test hiện có.

---

# 10. Chỉ thị tiếp theo cho Agent Global

```text
1. Không thay thuật toán lõi.
2. Pin Global action policy SHA 4220... bằng authority sidecar/receipt.
3. Biến verify-decision thành exact recomputation verifier.
4. Cho certificate-bundle verification kiểm exact action policy và decision replay.
5. Bổ sung timestamp ordering vào verifier.
6. Giới hạn fallback C/E; giữ constraint-package fallback.
7. Verify CHECKSUMS trước replay.
8. Bỏ absolute repository-root dependency khỏi portable replay.
9. Dọn pyc/cache.
10. Tạo integration RC2 có manifest, SHA, scan reports và Git receipt.
11. Chưa chạy real pilot cho đến khi C/E/Dataset packages chính thức sẵn sàng.
12. Chưa tuyên bố production-ready cho đến khi authority receipt được reseal và
    human-frozen CalibrationArtifact được pin.
```

---

# 11. Final decision

```text
CONDITIONAL_ACCEPT_AFTER_RC2
```

Global Validator không cần viết lại. Core engine đã đúng hướng và có chất lượng
tốt. Patch cần tập trung vào **authority binding và independent verification**,
không phải thêm feature mới.
