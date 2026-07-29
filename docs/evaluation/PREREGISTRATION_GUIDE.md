# AR-2 Preregistration Guide

## 1. Chon dung mode

- Dung `SYNTHETIC_LOCAL_CONFORMANCE` de kiem tra schema, metric, report va release
  plumbing. Mode nay luon la `CONFORMANCE_ONLY`.
- Dung `REAL_AUTHORITY` chi khi bay external authority artifact dung voi profile
  da review va artifact hash cua evaluation plan da san sang.
- Dung `LEGACY_READ_ONLY` chi de verify receipt V1 cu. Khong dung mode nay de
  freeze hay tao receipt moi.

## 2. Freeze truoc validation

1. Xac minh worktree clean va exact full Git commit.
2. Validate tat ca registry.
3. Build `REAL_AUTHORITY` receipt voi du bay authority path va artifact hash.
4. Verify lai receipt cung current registry, Git repo va external authority.
5. Tao `DurablePreregistrationStore` tren mot state root moi.
6. Goi `freeze()` mot lan. Ledger event `PREREGISTRATION_FROZEN` la authority;
   `state.json` chi la projection.

Khong mo validation neu receipt khong phai `REAL_AUTHORITY` hoac projection khong
khop replay ledger.

## 3. Access sequence

Thu tu bat buoc:

```text
FROZEN_BEFORE_VALIDATION
-> VALIDATION_ACCESSED
-> CALIBRATION_ARTIFACT_FROZEN
-> HIDDEN_TEST_ACCESSED
```

Moi transition duoc ghi mot event hash-chain duoi exclusive writer lock. Restart
process khong reset access history. Hai writer dong thoi hoac lan mo thu hai deu
fail closed.

## 4. Amendment

- Truoc validation: primary amendment phai chi ro version preregistration moi;
  state chuyen sang `REFREEZE_REQUIRED`.
- Sau validation nhung truoc hidden test: primary amendment van bat buoc refreeze
  va khong duoc tiep tuc primary path cu.
- Sau hidden test: cam primary amendment. Chi cho phep exploratory declaration
  trong namespace `exploratory/**`, khong co preregistration version moi.

Mau pre-validation nam tai
`docs/evaluation/examples/amendment_prevalidation_v1.json`.

## 5. Projection recovery

Chi recovery khi ledger hash-chain con hop le nhung `state.json` bi mat/hong/lech.
Recovery phai:

1. lock exclusive writer;
2. replay toan bo ledger;
3. tao receipt moi bang immutable create;
4. bind old/new projection hash va ledger head;
5. append `RECOVERY_RECORDED`;
6. atomic publish projection moi.

Khong recovery neu ledger bi tamper; phai dung va dieu tra authority.

## 6. External release

```powershell
$head = git rev-parse HEAD
python -B -m evaluation.v1.tools.build_release `
  --source-commit $head `
  --output C:\work\terminology-evidence-artifacts\evaluation-ar2-release-v1

python -B -m evaluation.v1.cli verify-release `
  C:\work\terminology-evidence-artifacts\evaluation-ar2-release-v1
```

Output phai la mot path moi nam ngoai repository. Release builder khong overwrite
artifact cu va khong co dirty-worktree exception.
