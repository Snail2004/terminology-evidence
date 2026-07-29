# Huong dan review 5 sense

Day la goi review co muc tieu cho 5 sense con bi chan o Stage A. Ba reviewer
lam doc lap va chi sua file CSV mang dung slot cua minh trong
`reviewer_templates/`.

Voi moi dong:

1. Doc dinh nghia, POS, scope va split de xuat.
2. Doi chieu du 5 context that trong `contexts_25.csv` hoac casebook.
3. Doi chieu 3 candidate tieng Viet trong `candidates_15.csv`.
4. Dien cac cot quyet dinh. Neu chon `REVISE`, ghi noi dung sua vao cot
   `corrected_*` tuong ung.
5. Dat `review_status=COMPLETE` khi dong da hoan tat.

Gia tri quyet dinh khuyen nghi:

- definition/POS/scope/context/candidate: `ACCEPT`, `REVISE`, `UNJUDGEABLE`.
- split: `ACCEPT_SPLIT`, `NO_SPLIT`, `REVISE_SPLIT`, `NOT_APPLICABLE`.

Khong sua cac cot tu `schema_id` den `source_payload_sha256`. Validator se
phat hien thay doi phan source. Khong xem hoac gop ket qua reviewer khac truoc
khi nop file cua minh.

Goi nay khong chon thuat ngu dich cuoi, khong dien Stage B gold va khong tao
official contract. No chi dong cac blocker Stage A bang bang chung corpus.
