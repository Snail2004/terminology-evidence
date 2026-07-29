# Evaluation & Preregistration AR-2 - Implementation V1

## Pham vi da trien khai

Implementation nay hien thuc hoa quyet dinh AR-2 tren base canonical
`7094ee007a1edb2d77ffeb2ab984af5977cec103`, chi trong cac namespace:

- `evaluation/**`
- `tests/evaluation/**`
- `docs/evaluation/**`

Khong sua Dataset, Context Substitution, Vietnamese Attestation, Global
Validator, Contracts, integration harness, gold label hay calibration threshold
production. Khong co provider/network call.

## Sau nhom thanh phan

1. **Registry va identity**: registry nghien cuu, metric, experiment, split,
   exclusion, label mapping va statistical analysis duoc validate bang JSON
   strict, hash vat ly va self hash.
2. **Evaluation plumbing**: exact candidate join, split leakage guard, eligibility,
   primary metrics, Wilson interval, sense-grouped bootstrap, McNemar,
   deterministic calibration conformance va report JSON/CSV/Markdown.
3. **Authority va receipt**: ba mode tach biet `REAL_AUTHORITY`,
   `SYNTHETIC_LOCAL_CONFORMANCE`, `LEGACY_READ_ONLY`; real mode bind exact
   Contract R2, detached AR-1 approval, Global action policy, Dataset manifest,
   split assignments va Evaluation registries. State freeze chi nhan
   `VerifiedRealReceipt` tao tu receipt vat ly va current authority bytes.
4. **Durable preregistration state**: append-only hash-chain ledger, single
   exclusive writer, atomic state projection, one-time validation/test access,
   amendment/refreeze policy va projection recovery gom immutable plan,
   `RECOVERY_RECORDED`, final publish, completion receipt.
5. **Exact test authority**: committed manifest bind exact JUnit testcase set;
   release chi pass khi tests > 0 va failures/errors/skipped deu bang 0.
6. **Git-object release**: source lay tu exact Git commit/tree, normal mode yeu
   cau clean exact HEAD, artifact duoc verify ngay trong external staging va chi
   publish mot lan bang atomic rename. Verifier bind manifest voi Git source
   receipt, source ZIP, expected-test authority, parsed JUnit, registry/source
   scan, commands/environment va `RELEASE_CHECKSUMS.sha256`.

## Authority dang pin

- Contract R2 authority module tree:
  `938bca1f9c60596ef9403a43f0355476ad42afef`
- Detached approval binding physical SHA256:
  `3ad39870e4e95c51ac88ee6a3d451504d41ba26d3bf5dc6569d25a585a7147a5`
- Detached approval binding canonical self SHA256:
  `ab7acbccfbdf64b74071133d4e049a06cbafc66c989f9b9f7ce52a08caa720b2`
- Evaluation allowed-authority profile self SHA256:
  `415d0a32291221f8bbd2c36c8b4a44301f471781d4598d8db647eeb3e74fb33f`
- Expected testcase identity SHA256:
  `1cdabfeb0c857a8eb3aecefcc021c451cc72125828514837d009921981058a31`

## Nguyen tac fail-closed

- Path phai la POSIX relative, NFC canonical, khong backslash, drive/UNC,
  traversal, symlink, junction/reparse point hay case-confusable duplicate.
- Receipt, verified capability, ledger event, projection, recovery plan/
  completion, manifest va registry bi
  thay doi mot byte se bi reject.
- Dirty/untracked worktree, sai HEAD, sai Git object, JUnit rong/do/skip, testcase
  thua/thieu, release co file thua hoac RELEASE_CHECKSUMS drift deu dung truoc
  PASS.
- Tat ca receipt/event timestamp phai la RFC3339 co timezone va khong duoc lui.
- Synthetic receipt khong the freeze; legacy receipt khong the build moi.
- Sau hidden-test access, primary analysis khong the sua. Exploratory work phai
  o namespace rieng va khong duoc refreeze primary claims.

## Trang thai nghien cuu

Implementation nay la `CONFORMANCE_ONLY` cho den khi Maintainer tao mot
`REAL_AUTHORITY` preregistration receipt va thuc hien quy trinh access da review.
Khong co ket qua validation/test, human gold, threshold production hay ket luan
chat luong thuat ngu nao duoc phat sinh trong phase nay.
