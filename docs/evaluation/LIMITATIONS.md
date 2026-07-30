# Evaluation & Preregistration AR-2 - Limitations

1. Chua truy cap validation split hay hidden test split; khong co result de danh
   gia gia thuyet nghien cuu.
2. Chua tao human gold, adjudication record hay candidate correctness label.
3. Chua fit/review production calibration artifact va khong pin production
   threshold.
4. Synthetic fixtures chi kiem tra conformance va determinism; khong phai thesis
   evidence, pilot result hay production readiness.
5. Khong goi provider, network, search hoac external API.
6. Khong tao Global decision/action va khong thay doi output cua Dataset, C, E
   hay Global Validator.
7. `LEGACY_READ_ONLY` chi verify receipt cu; legacy bytes khong duoc dien giai
   lai theo policy V2.
8. Projection recovery chi sua projection khi ledger con hop le. Ledger hash
   drift khong co auto-repair.
9. Release chi chung minh source/test/artifact conformance tai exact Git commit;
   no khong tu dong nang status thanh production hay mo data split.
10. Roadmap goc duoc luu byte-identical trong `docs/evaluation/`; moi thay doi
    kien truc dong bang can mot architecture decision moi, khong sua ngam trong
    implementation.
