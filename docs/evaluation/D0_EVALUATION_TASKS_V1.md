# AGENT EVALUATION — HAI TASK SONG SONG

Base authority:

```text
publication:
f7289661aed3db124b55ef67ba3bd1f7f7dc92ea

plan self:
7029a0dc43bc0b6e4967f6a205cb541dc23468100b287375ff1adc1307955490

freeze receipt self:
9ecd51676bf3bd758feeb9c330c257629a03f59c8601be10404c30a556762b3a
```

Mode:

```text
no provider
no producer output access yet
gold remains closed
```

---

## TASK EV-01 — PRE-D0 AMENDMENT + REFREEZE

### Mục tiêu

Đóng điều kiện bắt buộc trước khi mở D0 gold.

### Nội dung amendment

1. Xác nhận natural validation/test không có strict negatives.
2. Giữ nguyên label mapping:
   - positive = ACCEPT;
   - negative = REJECT + SPLIT_REQUIRED;
   - excluded = CONDITIONAL + UNJUDGEABLE.
3. Nêu rõ D0 chỉ là development experiment.
4. Các metric không được ước lượng từ natural D0 nếu thiếu negative:
   - specificity;
   - false-auto-approval;
   - critical-error recall;
   - production threshold claims.
5. Tách natural benchmark và adversarial negative companion.
6. Khóa output-seal-before-gold-access rule.
7. Khóa bảng số liệu:
   - coverage;
   - calls;
   - retry/malformed;
   - latency;
   - token/cost;
   - status distributions;
   - agreement;
   - manual-review;
   - error analysis.

### Output

```text
append-only amendment
new plan/freeze receipt hashes
exact parent/child/publication identity
no mapping change
gold access remains NO
```

### Status

```text
PRE_D0_ADDENDUM_REFROZEN
```

---

## TASK EV-02 — BLIND D0 COHORT AUTHORITY + RESULT SHELLS

### Mục tiêu

Chọn và seal cohort D0 nhưng không lộ gold.

### Cohort constraints

```text
5 senses
15 candidates
3 candidates/sense
all 5 senses have contrastive context
one candidate designated as canary
canary belongs to the same 15-candidate D0 cohort
```

### Producer-safe output cho Main/SI/C/E

Chỉ chứa:

```text
experiment/cohort ID
sense IDs
candidate IDs
context-set IDs/hashes
candidate-set hash
selection authority hash
phase membership:
CANARY candidate 1
REMAINDER candidates 2–15
```

Không chứa:

```text
gold labels
reviewer decisions
candidate rank
winner
expected result
split statistics
```

### Result shells

Chuẩn bị sẵn bảng trống cho:

```text
run inventory
C metrics
E metrics
Global-development outputs
token/cost/latency
status distribution
human agreement after gold open
manual-review rate
candidate error analysis
```

### Output

```text
D0_BLIND_COHORT_AUTHORITY_READY
D0_RESULT_TABLE_SHELLS_READY
D0_GOLD_ACCESS_NO
```

### Cấm

```text
Không mở D0 gold trước output seal.
Không mở validation/test.
Không gửi label distribution cho producer agents.
```
