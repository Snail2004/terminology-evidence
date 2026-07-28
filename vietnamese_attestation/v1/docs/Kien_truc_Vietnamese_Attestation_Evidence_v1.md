# KIẾN TRÚC VIETNAMESE ATTESTATION EVIDENCE — V1
## Agent-Ready Implementation Contract

**Tên module:** Vietnamese Attestation Evidence  
**Mã viết tắt:** `VAE` hoặc `E`  
**Phiên bản hợp đồng:** `1.0.0`  
**Vai trò trong luận văn:** Evidence Provider độc lập cho Terminology Validator  
**Miền MVP:** Thuật ngữ Anh–Việt trong Machine Learning / D2L  
**Đầu ra chính:** Feature vector về attestation, conventionality, source quality và concept match  
**Không phải:** Correctness oracle, bilingual dictionary lookup, glossary decision engine hoặc web-frequency counter

---

# 0. CHỈ THỊ CHO AGENT TRIỂN KHAI

## 0.1. MUST

Agent triển khai **MUST**:

1. Nhận một `FrozenCandidateContract` đã khóa version.
2. Chạy độc lập với Context Substitution Test.
3. Không đọc kết quả hoặc điểm của nhánh C.
4. Tìm tài liệu tiếng Việt từ curated corpus và/hoặc Web Search API.
5. Fetch, extract, locate candidate span và tạo snippet có provenance.
6. Phân biệt URL với nguồn bằng chứng độc lập.
7. Deduplicate ở cấp URL, nội dung, tài liệu, publisher và tổ chức.
8. Phân loại source authority bằng policy có phiên bản.
9. Phân loại domain và concept theo schema khóa trước.
10. Xuất feature vector, counts, flags, evidence và provenance.
11. Phân biệt không có bằng chứng với lỗi retrieval.
12. Đặt `final_glossary_decision = null`.
13. Hỗ trợ cache, replay và versioned rerun.
14. Có test cho duplicate echo, wrong domain và popular-but-wrong candidate.
15. Fail-safe khi source, extraction hoặc Judge không đủ tin cậy.

## 0.2. MUST NOT

Agent triển khai **MUST NOT**:

1. Gọi E là correctness score.
2. Dùng số kết quả tìm kiếm làm bằng chứng đúng.
3. Đếm nhiều bản sao của cùng tài liệu như nhiều bằng chứng.
4. Dùng search-result snippet làm evidence cuối khi fetch được trang gốc.
5. Tự đổi `candidate_vi`, `sense_id`, `scope_id` hoặc `definition_en`.
6. Đưa kết quả C vào Attestation Judge.
7. Dùng E một mình để phê duyệt glossary.
8. Tự động seal observed variant.
9. Xem `NO_ATTESTATION` là bằng chứng candidate sai.
10. Crawl toàn Internet hoặc toàn domain trong MVP.
11. Xây OCR phức tạp trong V1.
12. Dùng exact-string count làm conventionality.
13. Trộn source authority với concept match thành một nhãn duy nhất.
14. Ghi đè âm thầm kết quả cũ.
15. Thay đổi policy sau khi mở test set.

## 0.3. Definition of Done

VAE V1 chỉ được xem là hoàn thành khi toàn bộ checklist ở Mục 29 đạt.

---

# 1. VAI TRÒ VÀ RANH GIỚI

## 1.1. Câu hỏi VAE trả lời

> Ứng viên tiếng Việt này có được sử dụng trong các tài liệu tiếng Việt đáng tin cậy, độc lập, đúng domain và nói về cùng concept hay không?

## 1.2. Câu hỏi VAE không trả lời

> Ứng viên này chắc chắn đúng hay sai?

VAE đo:

- attestation;
- mức được thừa nhận;
- mức sử dụng ổn định;
- chất lượng và tính độc lập của nguồn;
- độ phù hợp domain;
- mức tương đồng concept.

VAE không thay thế:

- Context Substitution Test;
- Global Gate Engine;
- human annotation;
- gold glossary dùng ở evaluation;
- translation quality estimation.

## 1.3. Quan hệ với C và Global Validator

```text
                    FrozenCandidateContract
                              ↓
              ┌───────────────┴───────────────┐
              ↓                               ↓
      Context Substitution Test        Vietnamese Attestation
               C                               E
              ↓                               ↓
        C Evidence Package             E Evidence Package
              └───────────────┬───────────────┘
                              ↓
                    Global Gate Engine
                              ↓
                 Calibrated Decision Policy
                              ↓
                    Versioned Certificate
```

C và E có thể chạy song song nhưng không trao đổi kết quả trong lúc thu thập evidence.

---

# 2. THUẬT NGỮ

| Thuật ngữ | Định nghĩa |
|---|---|
| Candidate | Phương án tiếng Việt cần kiểm định |
| Term sense | Một nghĩa cụ thể của source term |
| Attestation | Quan sát cho thấy candidate được dùng trong tài liệu tiếng Việt |
| Evidence document | Tài liệu đã fetch và extract thành công |
| Evidence snippet | Đoạn có candidate span và context xung quanh |
| Independent cluster | Nhóm tài liệu được xem là một nguồn bằng chứng độc lập |
| Authority | Mức tin cậy của nguồn phát hành |
| Domain match | Mức snippet thuộc đúng lĩnh vực |
| Concept match | Mức snippet nói cùng concept với `definition_en` |
| Conventionality | Mức cách dùng ổn định qua nhiều tổ chức và loại tài liệu |
| Duplicate echo | Nhiều URL lặp lại cùng nội dung hoặc cùng nguồn gốc |
| Observed variant | Surface form tìm thấy nhưng chưa được chứng nhận |
| Frozen contract | Input đã khóa version, không thay đổi trong run |
| Local status | Trạng thái nội bộ của E, không phải glossary decision |

---

# 3. INPUT CONTRACT

## 3.1. FrozenCandidateContract

```json
{
  "candidate_id": "term-inference-vi-01",
  "source_term": "inference",
  "candidate_vi": "suy luận",
  "candidate_version": "candidate-v1",
  "sense_id": "model_execution",
  "scope_id": "machine_learning",
  "sense_contract": {
    "definition_en": "The process in which a trained model produces outputs for new inputs.",
    "definition_review_status": "VERIFIED",
    "definition_provenance": ["d2l-ch03-b015", "d2l-ch03-b021"],
    "sense_inventory_version": "sense-v2"
  },
  "known_surfaces": {
    "canonical": "suy luận",
    "validated_variants": ["quá trình suy luận"],
    "rejected_variants": ["suy diễn logic"]
  },
  "domain_profile": {
    "domain_name": "machine learning",
    "vi_anchors": ["học máy", "mô hình", "mạng nơ-ron", "dự đoán"],
    "en_anchors": ["machine learning", "model", "neural network", "prediction"]
  },
  "run_policy": {
    "attestation_policy_version": "attestation-v1",
    "query_policy_version": "query-v1",
    "source_policy_version": "source-tier-v1",
    "dedup_policy_version": "dedup-v1",
    "judge_policy_version": "attestation-judge-v1"
  }
}
```

## 3.2. Run identity

Mỗi run phải gắn với tuple:

```text
candidate_id
candidate_version
sense_id
scope_id
sense_inventory_version
attestation_policy_version
```

Nếu một trường thay đổi, tạo `attestation_run_id` mới.

## 3.3. Input validation

Blocking:

```text
candidate_id rỗng
candidate_vi rỗng
sense_id rỗng
scope_id rỗng
definition_en rỗng
sense_inventory_version rỗng
policy version thiếu
```

Warning:

```text
definition_review_status = UNVERIFIED
domain anchors rỗng
không có validated variants
definition provenance thiếu một phần
```

---

# 4. OUTPUT CONTRACT

## 4.1. VietnameseAttestationPackage

```json
{
  "candidate_id": "term-inference-vi-01",
  "candidate_version": "candidate-v1",
  "source_term": "inference",
  "candidate_vi": "suy luận",
  "sense_id": "model_execution",
  "scope_id": "machine_learning",
  "sense_inventory_version": "sense-v2",
  "attestation_evidence": {
    "features": {
      "E_authority": 0.75,
      "E_independence": 0.67,
      "E_domain": 1.0,
      "E_concept": 0.83,
      "E_conventionality": 0.60,
      "E_coverage": 0.90
    },
    "counts": {
      "query_count": 3,
      "raw_result_count": 28,
      "unique_url_count": 18,
      "fetch_attempt_count": 18,
      "fetch_success_count": 15,
      "extraction_success_count": 14,
      "candidate_snippet_count": 9,
      "independent_cluster_count": 4,
      "same_concept_cluster_count": 3,
      "related_cluster_count": 1,
      "different_cluster_count": 0,
      "uncertain_cluster_count": 0,
      "unique_organization_count": 3
    },
    "status": "ATTESTED",
    "flags": []
  },
  "accepted_evidence": [],
  "rejected_evidence": [],
  "observed_variants": [],
  "recommendation_to_global_validator": "EVIDENCE_AVAILABLE",
  "final_glossary_decision": null,
  "provenance": {
    "attestation_run_id": "attest-2026-001",
    "query_policy_version": "query-v1",
    "source_policy_version": "source-tier-v1",
    "dedup_policy_version": "dedup-v1",
    "judge_policy_version": "attestation-judge-v1",
    "search_provider": "brave",
    "extractor_version": "trafilatura-x.y",
    "embedding_model_version": "embedding-v1",
    "judge_model_id": "model-family-b",
    "judge_prompt_hash": "sha256:...",
    "started_at": "...",
    "completed_at": "..."
  }
}
```

## 4.2. Output invariants

Luôn có:

```json
{"final_glossary_decision": null}
```

VAE không trả:

```text
AUTO_APPROVED
REJECTED
SPLIT_REQUIRED
final winner
probability of correctness
```

---

# 5. KIẾN TRÚC MODULE

```text
FrozenCandidateContract
        ↓
ContractValidator
        ↓
AttestationPlanner
        ↓
┌───────────────────────────────┐
│ CuratedCorpusRetriever        │
│ WebSearchRetriever            │
└───────────────┬───────────────┘
                ↓
SearchResultNormalizer
                ↓
UrlCanonicalizer
                ↓
DocumentFetcher + RawCache
                ↓
ContentTypeRouter
        ┌───────┴────────┐
        ↓                ↓
HtmlExtractor       PdfTextExtractor
        └───────┬────────┘
                ↓
LanguageDetector
                ↓
CandidateSpanLocator
                ↓
SnippetBuilder
                ↓
SourceQualityProfiler
                ↓
GlobalDeduplicator
                ↓
DomainValidator
                ↓
ConceptMatchValidator
                ↓
ConventionalityAnalyzer
                ↓
AttestationFeatureAggregator
                ↓
LocalStatusPolicy
                ↓
EvidencePackageStore
```

---

# 6. MODULE CONTRACTS

## 6.1. ContractValidator

Input: `FrozenCandidateContract`

Output:

```json
{"valid": true, "blocking_errors": [], "warnings": []}
```

Rules:

- Không sửa input.
- Không tự bổ sung sense.
- Không gọi LLM để “sửa” định nghĩa.
- Warning phải truyền tới output package.

## 6.2. AttestationPlanner

Trách nhiệm:

- tạo query plan;
- đặt search budget;
- cho curated corpus và web chạy song song;
- không đánh giá evidence.

Output:

```json
{
  "query_plan_id": "qp-001",
  "queries": [],
  "max_unique_urls": 20,
  "max_fetches": 20,
  "target_evidence_clusters": 3,
  "early_stop_enabled": true
}
```

## 6.3. CuratedCorpusRetriever

MVP retrieval:

```text
BM25 + multilingual embeddings
```

Không được:

- dùng gold bilingual glossary;
- đánh dấu candidate đúng chỉ vì corpus có occurrence;
- dùng test ẩn như runtime corpus.

## 6.4. WebSearchRetriever

- Gọi Search API.
- Không scrape trang HTML search results.
- Lưu raw response.
- Tôn trọng rate limit và retry policy.

Default:

```yaml
provider: brave
country: VN
search_lang: vi
count_per_query: 10
extra_snippets: true
max_queries_per_candidate: 3
```

Output:

```json
{
  "provider": "brave",
  "query_id": "query-001",
  "rank": 1,
  "title": "...",
  "url": "...",
  "description": "...",
  "extra_snippets": [],
  "retrieved_at": "...",
  "raw_response_hash": "sha256:..."
}
```

## 6.5. SearchResultNormalizer

Chuẩn hóa mọi provider về schema chung.

Không được:

- coi description là evidence cuối;
- tính authority dựa trên rank;
- loại result chỉ vì rank thấp nếu còn trong budget.

## 6.6. UrlCanonicalizer

Rules:

- lowercase host;
- bỏ fragment;
- bỏ tracking parameters;
- chuẩn hóa trailing slash;
- giữ content parameters cần thiết;
- ưu tiên canonical URL khi xác minh được;
- không merge hai URL có nội dung khác.

## 6.7. DocumentFetcher

Trách nhiệm:

- robots check;
- timeout;
- retry;
- domain throttling;
- content-type inspection;
- raw cache;
- content hash.

Default:

```yaml
timeout_seconds: 20
max_retries: 2
max_response_bytes: 15000000
per_domain_concurrency: 2
global_concurrency: 12
user_agent: "TermValidationResearchBot/1.0"
```

Statuses:

```text
FETCHED
ROBOTS_BLOCKED
HTTP_ERROR
TIMEOUT
CONTENT_TOO_LARGE
UNSUPPORTED_CONTENT_TYPE
```

## 6.8. RawCache

Cache key:

```text
canonical_url + retrieval_date_bucket + fetch_policy_version
```

Phải lưu:

- raw bytes hoặc reference;
- headers;
- HTTP status;
- retrieved_at;
- content hash;
- robots result;
- fetch policy version.

Không ghi đè âm thầm raw content cũ.

## 6.9. HtmlExtractor

MVP dùng Trafilatura hoặc tương đương.

Phải trích:

- main text;
- title;
- author nếu có;
- publication date nếu có;
- headings;
- paragraph boundaries;
- language hint;
- canonical URL nếu có.

Statuses:

```text
EXTRACTED
EMPTY_MAIN_TEXT
EXTRACTION_FAILED
LANGUAGE_MISMATCH
```

## 6.10. PdfTextExtractor

V1 hỗ trợ:

- PDF có text layer;
- metadata cơ bản;
- trang và offset nếu có thể.

V1 không bắt buộc:

- scanned PDF cần OCR;
- layout phức tạp;
- công thức hình ảnh.

Scanned PDF phải gắn:

```text
UNSUPPORTED_SCANNED_PDF
```

Không xem là `NO_ATTESTATION`.

## 6.11. LanguageDetector

Labels:

```text
VIETNAMESE
MIXED_VI_EN
NON_VIETNAMESE
UNCERTAIN
```

`MIXED_VI_EN` có thể giữ nếu snippet tiếng Việt rõ ràng.

## 6.12. CandidateSpanLocator

Surface classes:

```text
EXACT_CANONICAL
VALIDATED_VARIANT
OBSERVED_UNVALIDATED_VARIANT
ACCENTLESS_FORM
PARTIAL_MATCH
NO_MATCH
```

Normalization:

- Unicode NFC;
- whitespace;
- punctuation;
- case;
- không bỏ dấu cho positive evidence chính;
- preserve original offsets.

Rules:

- `EXACT_CANONICAL`, `VALIDATED_VARIANT`: vào validation.
- `OBSERVED_UNVALIDATED_VARIANT`: lưu riêng.
- `ACCENTLESS_FORM`: không tính strong attestation mặc định.
- `PARTIAL_MATCH`: không tính positive evidence.

## 6.13. SnippetBuilder

Window:

```text
câu chứa candidate
+ tối đa 2 câu trước
+ tối đa 2 câu sau
```

Limits:

```yaml
min_words: 40
target_words: 150
max_words: 300
```

Output:

```json
{
  "snippet_id": "snippet-001",
  "document_id": "doc-001",
  "section_title": "...",
  "paragraph_index": 12,
  "snippet_text": "...",
  "candidate_span": {
    "surface": "suy luận",
    "start": 315,
    "end": 323,
    "surface_class": "EXACT_CANONICAL"
  },
  "snippet_hash": "sha256:..."
}
```

## 6.14. SourceQualityProfiler

Source tiers:

| Tier | Loại nguồn |
|---|---|
| A | Cơ quan nhà nước, tiêu chuẩn, đại học, bài báo khoa học, giáo trình có tác giả |
| B | Vendor docs, nhà xuất bản kỹ thuật, tổ chức chuyên môn |
| C | Technical blog có tác giả và nguồn dẫn |
| D | Forum, aggregator, nội dung không rõ tác giả |
| X | Spam, mirror dịch máy, page farm |

Output:

```json
{
  "source_tier": "A",
  "publisher_id": "org-001",
  "publisher_domain": "example.edu.vn",
  "author_present": true,
  "date_present": true,
  "document_type": "academic_pdf",
  "domain_whitelisted": true,
  "machine_translation_suspected": false,
  "source_policy_version": "source-tier-v1"
}
```

Authority không được suy ra chỉ bằng LLM.

## 6.15. GlobalDeduplicator

Dedup levels:

1. URL canonical.
2. Exact content hash.
3. Near-duplicate paragraph.
4. Title/author/date.
5. Same publisher.
6. Same organization.
7. Mirror/source relationship.

Đơn vị independence:

```text
independent evidence cluster
```

Output:

```json
{
  "cluster_id": "cluster-001",
  "representative_snippet_id": "snippet-001",
  "member_document_ids": ["doc-001", "doc-014", "doc-022"],
  "publisher_id": "org-001",
  "organization_id": "org-001",
  "dedup_reasons": ["NEAR_DUPLICATE_CONTENT", "SAME_ORGANIZATION"],
  "near_duplicate_score": 0.94
}
```

Một cluster chỉ đóng góp tối đa một evidence unit cho independence count.

## 6.16. DomainValidator

Input:

- `scope_id`;
- domain anchors;
- metadata;
- section title;
- snippet.

Labels:

```text
MATCH
PARTIAL
MISMATCH
UNCERTAIN
```

Output:

```json
{
  "domain_relation": "MATCH",
  "rule_score": 0.8,
  "embedding_score": 0.84,
  "judge_label": "MATCH",
  "reason": "...",
  "policy_version": "domain-v1"
}
```

Embedding không quyết định một mình.

## 6.17. ConceptMatchValidator

Nhiệm vụ: so sánh `definition_en` với ý nghĩa trong Vietnamese snippet.

Labels:

```text
SAME
RELATED
DIFFERENT
UNCERTAIN
```

Input:

```json
{
  "definition_en": "...",
  "scope_id": "machine_learning",
  "candidate_vi": "suy luận",
  "snippet_original": "...",
  "snippet_masked": "... [TERM] ...",
  "candidate_span": {},
  "source_profile": {}
}
```

Output:

```json
{
  "concept_relation": "SAME",
  "candidate_role": "TECHNICAL_TERM",
  "evidence_span": "...",
  "machine_translation_suspected": false,
  "reason": "Đoạn mô tả quá trình mô hình tạo đầu ra từ dữ liệu mới."
}
```

Rules:

```text
SAME → strong positive attestation
RELATED → weak observation
DIFFERENT → negative/wrong-sense observation
UNCERTAIN → không tính positive
```

Anti-shortcut: Judge phải nhận cả snippet gốc và snippet đã mask candidate.

## 6.18. ConventionalityAnalyzer

Conventionality không phải raw frequency.

Feature từ:

- independent clusters;
- organizations;
- document types;
- tier A/B sources;
- canonical/variant stability;
- phân bố qua nguồn;
- date span nếu có.

## 6.19. AttestationFeatureAggregator

Output features:

```text
E_authority
E_independence
E_domain
E_concept
E_conventionality
E_coverage
```

Không dùng fixed weighted sum trong core.

Có thể tạo `E_diagnostic` cho UI nhưng phải ghi:

```text
not a correctness probability
not used as final decision unless calibrated
```

## 6.20. LocalStatusPolicy

Local statuses:

```text
ATTESTED
WEAKLY_ATTESTED
NOT_ATTESTED
CONFLICTING_ATTESTATION
ATTESTATION_UNJUDGEABLE
```

Heuristic V1:

```text
ATTESTED
- >= 2 SAME independent clusters
- >= 2 organizations
- >= 1 tier A/B source
- domain match tốt
- retrieval coverage đủ

WEAKLY_ATTESTED
- chỉ 1 strong cluster
- hoặc nhiều evidence nhưng authority/domain thấp

NOT_ATTESTED
- retrieval thành công đủ
- không có SAME/RELATED evidence hợp lệ

CONFLICTING_ATTESTATION
- có cả SAME và DIFFERENT strong clusters

ATTESTATION_UNJUDGEABLE
- fetch/extraction coverage quá thấp
- Judge failures
- sense definition không đủ
```

Ngưỡng là config versioned, phải calibration sau.

---

# 7. QUERY POLICY

## 7.1. Query classes

### Q1 — Exact candidate

```text
"{{candidate_vi}}"
```

### Q2 — Candidate + domain anchors

```text
"{{candidate_vi}}" "{{vi_anchor_1}}"
"{{candidate_vi}}" "{{vi_anchor_2}}"
```

### Q3 — Candidate + source term

```text
"{{candidate_vi}}" "{{source_term}}"
```

### Q4 — Restricted sources

```text
site:edu.vn "{{candidate_vi}}" "{{domain_anchor}}"
site:gov.vn "{{candidate_vi}}" "{{domain_anchor}}"
filetype:pdf "{{candidate_vi}}" "{{domain_anchor}}"
```

## 7.2. MVP budget

```yaml
queries_per_candidate: 3
results_per_query: 10
max_unique_urls: 20
max_fetches: 20
target_independent_clusters: 3
```

## 7.3. Early stopping

Có thể dừng khi:

```text
>= 3 SAME independent clusters
>= 2 organizations
>= 1 tier A/B source
fetch coverage >= configured minimum
```

Trong validation/test nên cân nhắc tắt early stopping để có dữ liệu đầy đủ.

## 7.4. Query provenance

```json
{
  "query_id": "q-001",
  "query_text": "...",
  "query_class": "CANDIDATE_DOMAIN",
  "provider": "brave",
  "query_policy_version": "query-v1",
  "executed_at": "..."
}
```

---

# 8. FAILURE TAXONOMY

Không gom mọi thất bại vào `NO_ATTESTATION`.

## Search

```text
NO_SEARCH_RESULTS
SEARCH_PROVIDER_ERROR
SEARCH_RATE_LIMITED
SEARCH_TIMEOUT
```

## Fetch

```text
ROBOTS_BLOCKED
HTTP_ERROR
TIMEOUT
CONTENT_TOO_LARGE
UNSUPPORTED_CONTENT_TYPE
```

## Extraction

```text
EMPTY_MAIN_TEXT
EXTRACTION_FAILED
UNSUPPORTED_SCANNED_PDF
LANGUAGE_MISMATCH
```

## Evidence

```text
NO_CANDIDATE_SPAN
ONLY_PARTIAL_MATCH
WRONG_DOMAIN
DIFFERENT_CONCEPT
DUPLICATE_ECHO
LOW_AUTHORITY_ONLY
MACHINE_TRANSLATION_RISK
```

## Judge

```text
JUDGE_SCHEMA_INVALID
JUDGE_UNCERTAIN
JUDGE_TIMEOUT
JUDGE_DISAGREEMENT
```

---

# 9. EVIDENCE ACCEPTANCE POLICY

Một snippet vào `accepted_evidence` khi:

```text
fetch_status = FETCHED
extraction_status = EXTRACTED
language ∈ {VIETNAMESE, MIXED_VI_EN}
surface_class ∈ {EXACT_CANONICAL, VALIDATED_VARIANT}
domain_relation ∈ {MATCH, PARTIAL}
concept_relation = SAME
source_tier != X
dedup representative = true
```

`RELATED` lưu trong supporting observations.

`DIFFERENT` lưu như negative evidence.

---

# 10. OBSERVED VARIANT POLICY

Khi phát hiện variant:

```json
{
  "surface": "pha suy luận",
  "occurrence_count": 3,
  "independent_cluster_count": 2,
  "concept_relation": "SAME",
  "status": "PROPOSE_FOR_CST_VARIANT_CHECK"
}
```

Không được:

- thêm trực tiếp vào `allowed_variants`;
- coi attested variant là contextually valid;
- sửa Frozen Candidate Contract giữa run.

Workflow:

```text
Observed variant
→ CST variant check
→ Global Validator
→ certificate revision
```

---

# 11. FEATURE DEFINITIONS

## E_authority

Chất lượng source tiers của accepted clusters. Không phải correctness.

## E_independence

Independent clusters, organizations, publisher diversity, duplicate echo rate.

## E_domain

Mức accepted snippets nằm đúng domain/scope.

## E_concept

Tỷ lệ và độ mạnh của `SAME` concept evidence.

## E_conventionality

Mức ổn định qua organizations, document types, source tiers và surface forms.

## E_coverage

Độ đầy đủ của retrieval:

```text
fetch success
extraction success
candidate-span yield
judge completion
```

Coverage thấp không đồng nghĩa candidate không attested.

---

# 12. FLAGS

```text
SENSE_DEFINITION_UNVERIFIED
NO_ATTESTATION
SINGLE_SOURCE_ONLY
DUPLICATE_ECHO
WRONG_DOMAIN_ATTESTATION
DIFFERENT_CONCEPT_ATTESTATION
MACHINE_TRANSLATION_RISK
LOW_AUTHORITY_ONLY
FETCH_COVERAGE_LOW
CONFLICTING_ATTESTATION
JUDGE_UNCERTAIN
OBSERVED_NEW_VARIANT
```

Mapping recommendation:

```text
NO_ATTESTATION
→ không reject tự động
→ có thể giới hạn tối đa PROVISIONAL

CONFLICTING_ATTESTATION
→ HUMAN_REVIEW recommendation

DIFFERENT_CONCEPT_ATTESTATION từ nhiều strong clusters
→ concept mismatch investigation

DUPLICATE_ECHO
→ giảm independence

FETCH_COVERAGE_LOW
→ ATTESTATION_UNJUDGEABLE
```

---

# 13. DATA MODEL GỢI Ý

Tables:

```text
attestation_runs
search_queries
search_results
fetched_documents
extracted_documents
candidate_snippets
source_profiles
evidence_clusters
domain_judgments
concept_judgments
observed_variants
attestation_features
attestation_packages
```

Không ghi đè; mọi thay đổi tạo record/version mới.

---

# 14. API CONTRACT GỢI Ý

## POST `/attestation/runs`

Request: `FrozenCandidateContract`

Response:

```json
{"attestation_run_id": "attest-2026-001", "status": "QUEUED"}
```

## GET `/attestation/runs/{run_id}`

```json
{
  "status": "RUNNING",
  "stage": "CONCEPT_VALIDATION",
  "progress": {
    "queries_done": 3,
    "documents_fetched": 15,
    "clusters_validated": 2
  }
}
```

## GET `/attestation/runs/{run_id}/result`

Trả `VietnameseAttestationPackage`.

## POST `/attestation/runs/{run_id}/retry`

Chỉ retry failed stage; không sửa contract.

---

# 15. STATE MACHINE

```text
CREATED
→ CONTRACT_VALIDATED
→ PLANNED
→ SEARCHING
→ FETCHING
→ EXTRACTING
→ LOCATING_SPANS
→ DEDUPLICATING
→ VALIDATING_DOMAIN
→ VALIDATING_CONCEPT
→ AGGREGATING
→ COMPLETED
```

Failure states:

```text
FAILED_CONTRACT
FAILED_SEARCH
FAILED_FETCH_COVERAGE
FAILED_EXTRACTION_COVERAGE
FAILED_JUDGE
CANCELLED
```

Partial completion:

```text
COMPLETED_WITH_WARNINGS
```

---

# 16. CONCURRENCY MODEL

Trong E:

```text
queries chạy song song có giới hạn
fetch chạy theo domain throttling
extraction chạy worker local
Judge chạy batch nhỏ hoặc concurrency giới hạn
```

Defaults:

```yaml
search_concurrency: 3
fetch_global_concurrency: 12
fetch_per_domain_concurrency: 2
extract_concurrency: 4
judge_concurrency: 5
```

Aggregation phải deterministic, sort theo stable keys.

---

# 17. CACHE VÀ REPLAY

Cache layers:

- search-response cache;
- raw-document cache;
- extracted-text cache;
- embedding cache;
- Judge cache.

Cache keys gồm version:

```text
query + provider + query_policy_version
canonical_url + fetch_policy_version
raw_content_hash + extractor_version
snippet_hash + embedding_model_version
definition_hash + snippet_hash + judge_prompt_hash + judge_model_id
```

Replay modes:

```text
REPLAY_FROM_RAW_SEARCH
REPLAY_FROM_FETCHED_DOCUMENTS
REPLAY_FROM_EXTRACTED_TEXT
REPLAY_FROM_SNIPPETS
REPLAY_FROM_JUDGE_OUTPUTS
```

---

# 18. ATTESTATION JUDGE PROMPT CONTRACT

System role:

```text
Bạn là Attestation Judge.
Bạn không chọn thuật ngữ và không quyết định glossary.
Bạn chỉ so sánh source sense definition với một snippet tiếng Việt.
Không xem tần suất hoặc authority là bằng chứng concept đúng.
```

Input:

```json
{
  "definition_en": "...",
  "scope_id": "machine_learning",
  "candidate_vi": "suy luận",
  "snippet_original": "...",
  "snippet_masked": "... [TERM] ...",
  "source_type": "academic_pdf"
}
```

Output:

```json
{
  "judgeability": "JUDGEABLE",
  "concept_relation": "SAME",
  "domain_match": true,
  "candidate_role": "TECHNICAL_TERM",
  "machine_translation_suspected": false,
  "evidence_span": "...",
  "reason": "..."
}
```

Enums:

```text
judgeability:
JUDGEABLE
INSUFFICIENT_SNIPPET
INVALID_SNIPPET
AMBIGUOUS_CONCEPT

concept_relation:
SAME
RELATED
DIFFERENT
UNCERTAIN

candidate_role:
TECHNICAL_TERM
GENERAL_WORD
NAME
QUOTE
METALANGUAGE
UNDETERMINED
```

Judge không trả:

```text
score tổng
APPROVE/REJECT
confidence percentage
final glossary decision
```

---

# 19. PSEUDOCODE

```python
async def run_vietnamese_attestation(contract):
    contract_result = validate_frozen_contract(contract)

    if not contract_result.valid:
        return build_failed_contract_package(
            contract=contract,
            errors=contract_result.blocking_errors,
        )

    run = create_attestation_run(contract)

    plan = build_query_plan(
        contract=contract,
        max_queries=3,
        max_unique_urls=20,
    )

    corpus_task = search_curated_corpus(contract, plan)
    web_task = search_web(
        contract=contract,
        plan=plan,
        country="VN",
        search_lang="vi",
    )

    corpus_results, web_results = await gather_safe(
        corpus_task,
        web_task,
    )

    normalized = normalize_search_results(
        corpus_results + web_results
    )

    canonical_results = canonicalize_urls(normalized)
    unique_results = deduplicate_urls(canonical_results)

    fetched_documents = await fetch_documents_with_cache(
        unique_results,
        max_fetches=20,
        respect_robots=True,
    )

    extracted_documents = extract_supported_documents(
        fetched_documents,
        html_extractor="trafilatura",
        pdf_text_extractor="pdf-text-v1",
    )

    language_filtered = filter_or_flag_languages(
        extracted_documents
    )

    snippets = locate_candidate_spans_and_build_snippets(
        documents=language_filtered,
        canonical_surface=contract.candidate_vi,
        validated_variants=contract.known_surfaces.validated_variants,
    )

    source_profiles = profile_source_quality(
        snippets=snippets,
        policy_version=contract.run_policy.source_policy_version,
    )

    clusters = global_deduplicate_and_cluster(
        snippets=snippets,
        source_profiles=source_profiles,
        policy_version=contract.run_policy.dedup_policy_version,
    )

    cluster_judgments = []

    for cluster in stable_sort(clusters):
        representative = select_representative_snippet(cluster)

        domain_result = validate_domain(
            snippet=representative,
            scope_id=contract.scope_id,
            domain_profile=contract.domain_profile,
        )

        concept_result = await validate_concept(
            definition_en=contract.sense_contract.definition_en,
            scope_id=contract.scope_id,
            candidate_vi=contract.candidate_vi,
            snippet_original=representative.snippet_text,
            snippet_masked=mask_candidate(representative),
        )

        cluster_judgments.append(
            build_cluster_judgment(
                cluster=cluster,
                domain_result=domain_result,
                concept_result=concept_result,
            )
        )

    accepted, rejected, observations = classify_evidence(
        cluster_judgments
    )

    conventionality = analyze_conventionality(
        accepted_evidence=accepted
    )

    features = aggregate_attestation_features(
        all_results=cluster_judgments,
        accepted_evidence=accepted,
        conventionality=conventionality,
        retrieval_stats=collect_retrieval_stats(run),
    )

    local_status, flags = apply_local_status_policy(
        features=features,
        judgments=cluster_judgments,
        contract_warnings=contract_result.warnings,
    )

    observed_variants = collect_observed_variants(
        snippets=snippets,
        contract=contract,
    )

    return build_attestation_package(
        contract=contract,
        features=features,
        status=local_status,
        flags=flags,
        accepted_evidence=accepted,
        rejected_evidence=rejected,
        observations=observations,
        observed_variants=observed_variants,
        recommendation_to_global_validator=build_recommendation(
            local_status,
            flags,
        ),
        final_glossary_decision=None,
        provenance=collect_full_provenance(run),
    )
```

---

# 20. DEFAULT CONFIG V1

```yaml
attestation:
  policy_version: "attestation-v1"

  retrieval:
    use_curated_corpus: true
    use_web_search: true
    search_provider: "brave"
    country: "VN"
    search_lang: "vi"
    max_queries_per_candidate: 3
    results_per_query: 10
    max_unique_urls: 20
    max_fetches: 20
    early_stop:
      enabled: true
      same_concept_clusters: 3
      organizations: 2
      require_strong_source: true

  fetching:
    timeout_seconds: 20
    retries: 2
    max_response_bytes: 15000000
    global_concurrency: 12
    per_domain_concurrency: 2
    respect_robots: true

  extraction:
    html_extractor: "trafilatura"
    support_text_pdf: true
    support_scanned_pdf: false

  snippets:
    context_sentences_before: 2
    context_sentences_after: 2
    min_words: 40
    target_words: 150
    max_words: 300

  dedup:
    exact_hash: true
    near_duplicate: true
    group_same_organization: true
    near_duplicate_threshold: 0.90

  judging:
    batch_size: 5
    temperature: 0
    require_masked_snippet: true

  status_policy:
    min_same_clusters_for_attested: 2
    min_organizations_for_attested: 2
    require_tier_a_or_b: true
    min_fetch_coverage: 0.50
```

Defaults là engineering configuration, không phải hằng số khoa học.

---

# 21. UNIT TESTS BẮT BUỘC

## Contract

- thiếu `candidate_vi` → blocking;
- thiếu `sense_id` → blocking;
- `definition_review_status=UNVERIFIED` → warning;
- version thay đổi → run ID mới.

## URL

- tracking URL được canonicalize;
- fragment bị bỏ;
- hai URL khác content không bị merge.

## Fetch

- robots blocked;
- timeout;
- retry;
- response quá lớn;
- unsupported content type.

## Extraction

- article HTML;
- navigation-heavy HTML;
- text PDF;
- scanned PDF;
- empty extraction.

## Span

- exact canonical;
- validated variant;
- unvalidated variant;
- accentless form;
- partial match;
- no match.

## Dedup

- cùng URL;
- mirror;
- cùng nội dung khác URL;
- cùng publisher nhưng nội dung khác;
- nhiều publisher sao chép cùng bài.

## Domain

- đúng ML;
- statistical domain khác;
- general-language usage;
- ambiguous snippet.

## Concept

- SAME;
- RELATED;
- DIFFERENT;
- UNCERTAIN;
- candidate chỉ xuất hiện trong quote;
- candidate là general word.

## Status

- strong attestation;
- single source;
- no results;
- retrieval failure;
- conflicting strong evidence;
- low-authority-only evidence.

---

# 22. INTEGRATION TESTS

## Case A — Strong candidate

```text
3 independent SAME clusters
3 organizations
1 tier A source
domain MATCH
```

Expected: `ATTESTED`.

## Case B — Duplicate echo

```text
10 URLs
1 original article
9 mirrors
```

Expected:

```text
independent_cluster_count = 1
DUPLICATE_ECHO
không ATTESTED mạnh
```

## Case C — Popular but wrong sense

Expected:

```text
E_conventionality có thể cao
E_domain thấp
E_concept thấp
WRONG_DOMAIN_ATTESTATION
```

## Case D — Correct but new

Một strong academic source, ít occurrence.

Expected:

```text
WEAKLY_ATTESTED hoặc evidence available
không REJECTED
```

## Case E — Retrieval failure

Search có kết quả nhưng fetch bị block gần hết.

Expected:

```text
ATTESTATION_UNJUDGEABLE
FETCH_COVERAGE_LOW
không NOT_ATTESTED
```

## Case F — Conflicting attestation

Có strong SAME và strong DIFFERENT clusters.

Expected:

```text
CONFLICTING_ATTESTATION
recommend HUMAN_REVIEW
```

---

# 23. ADVERSARIAL TEST SET

Tối thiểu 20–30 cases:

1. 10 URL sao chép cùng nội dung.
2. Candidate phổ biến nhưng sai sense.
3. Candidate chỉ xuất hiện trong menu/footer.
4. Candidate xuất hiện trong nội dung dịch máy.
5. Candidate xuất hiện trên SEO page.
6. Candidate đúng nhưng chỉ có một luận văn.
7. Candidate dùng ở domain khác.
8. Candidate chỉ xuất hiện trong tiêu đề.
9. Candidate dạng không dấu.
10. Candidate mới nhưng đúng.
11. Candidate nằm trong quote.
12. Candidate là tên sản phẩm.
13. Candidate là từ thường, không phải technical term.
14. Nhiều trang cùng tổ chức.
15. PDF mirror và HTML của cùng tài liệu.
16. Snippet ngắn, thiếu concept.
17. Search description đúng nhưng trang gốc không có candidate.
18. Candidate span bị tách bởi markup.
19. RELATED bị nhầm thành SAME.
20. Strong source nhưng tài liệu không phải tiếng Việt.

Metrics:

```text
duplicate echo rejection
wrong-domain rejection
false SAME rate
false NOT_ATTESTED rate
source-independence accuracy
retrieval failure classification
```

---

# 24. HUMAN ANNOTATION PROTOCOL

Đơn vị: independent evidence cluster đại diện.

Labels:

```text
Concept: SAME / RELATED / DIFFERENT / UNCERTAIN
Domain: MATCH / PARTIAL / MISMATCH / UNCERTAIN
Source usefulness: STRONG / USABLE / WEAK / UNUSABLE
Duplicate relation: INDEPENDENT / DUPLICATE / SAME_ORGANIZATION / UNCERTAIN
Candidate-level: ATTESTED / WEAKLY_ATTESTED / NOT_ATTESTED / CONFLICTING / UNJUDGEABLE
```

Agreement:

- Cohen’s kappa cho hai annotator;
- adjudication cho disagreement;
- không điều chỉnh policy sau test.

---

# 25. METRICS

## Retrieval

```text
Evidence Precision@5
Strong-source discovery rate
Fetch success rate
Extraction success rate
Candidate-span yield
```

## Dedup

```text
Duplicate pair precision
Duplicate pair recall
Independent cluster accuracy
```

## Judge

```text
SAME precision
SAME recall
false SAME rate
domain classification accuracy
Judge–human kappa
```

## Candidate-level

```text
E-only acceptance prediction
C-only acceptance prediction
C+E prediction
C–E correlation
auto-approval precision
coverage
```

## Cost

```text
search requests/candidate
fetches/candidate
LLM calls/candidate
tokens/candidate
elapsed time/candidate
cost/accepted evidence cluster
```

---

# 26. C–E DISAGREEMENT ANALYSIS

Bắt buộc tạo bốn nhóm:

| C | E | Ý nghĩa |
|---|---|---|
| Cao | Cao | Candidate mạnh |
| Cao | Thấp | Đúng ngữ nghĩa nhưng mới hoặc hiếm |
| Thấp | Cao | Calque phổ biến, wrong sense hoặc conventional nhưng không phù hợp |
| Thấp | Thấp | Candidate yếu hoặc thiếu bằng chứng |

VAE phải xuất đủ feature để Experiment Runner phân nhóm, nhưng VAE không đọc C trong runtime.

---

# 27. SECURITY VÀ ETHICS

- Không bypass robots.
- Không đăng nhập trang private.
- Không lưu dữ liệu cá nhân không cần thiết.
- Không crawl quá mức.
- Tôn trọng license.
- Chỉ lưu snippet cần cho audit.
- Không tái phân phối toàn bộ nội dung có bản quyền.
- Không dùng nội dung web làm gold truth.

---

# 28. MVP IMPLEMENTATION ORDER

## Phase 1 — Deterministic skeleton

1. Input schema.
2. Query generation.
3. Search adapter.
4. URL canonicalization.
5. Fetch + cache.
6. HTML extraction.
7. Candidate span.
8. Snippet.
9. Basic source tiers.
10. Exact/content-hash dedup.
11. Output package.

## Phase 2 — Semantic validation

1. Domain anchors.
2. Multilingual embedding.
3. Attestation Judge.
4. Masked snippet.
5. SAME/RELATED/DIFFERENT/UNCERTAIN.
6. Feature aggregation.

## Phase 3 — Research completeness

1. Global near-duplicate clustering.
2. Organization independence.
3. Conventionality.
4. Human annotation subset.
5. Adversarial set.
6. C–E disagreement analysis.
7. Cost reporting.

---

# 29. ACCEPTANCE CRITERIA — DEFINITION OF DONE

## Contract

- [ ] Nhận `FrozenCandidateContract`.
- [ ] Không thay đổi candidate/sense/scope.
- [ ] Version mismatch tạo run mới.
- [ ] `final_glossary_decision = null`.

## Retrieval

- [ ] Có curated corpus adapter hoặc interface.
- [ ] Có Web Search API adapter.
- [ ] Query có exact candidate và domain anchors.
- [ ] Có search budget.
- [ ] Có raw search provenance.

## Fetch và extraction

- [ ] Có robots check.
- [ ] Có rate limiting.
- [ ] Có timeout/retry.
- [ ] Có raw cache.
- [ ] Extract HTML.
- [ ] Extract text PDF hoặc flag unsupported.
- [ ] Phân biệt fetch failure và no evidence.

## Evidence

- [ ] Locate candidate span.
- [ ] Tạo snippet có offsets.
- [ ] Có source profile.
- [ ] Có global dedup.
- [ ] Đếm independent clusters, không đếm URL.
- [ ] Có domain validation.
- [ ] Có concept validation.
- [ ] Có masked snippet.
- [ ] Có observed variant workflow.

## Output

- [ ] Có E feature vector.
- [ ] Có counts.
- [ ] Có local status.
- [ ] Có flags.
- [ ] Có accepted/rejected evidence.
- [ ] Có provenance đầy đủ.
- [ ] Không trả glossary decision.

## Evaluation

- [ ] Unit tests.
- [ ] Integration cases A–F.
- [ ] Adversarial set.
- [ ] Human-labeled subset.
- [ ] Báo cáo retrieval, dedup, Judge và cost metrics.
- [ ] Hỗ trợ phân tích C cao/E thấp và C thấp/E cao.

---

# 30. SCOPE GUARDRAILS

| Yêu cầu | Hành động |
|---|---|
| Quyết định candidate đúng hay sai | Chuyển Global Validator |
| Dùng kết quả C để điều chỉnh E | Không thực hiện |
| Tự thêm variant vào certificate | Chỉ tạo proposal |
| Chạy COMET/Back-translation | Ngoài VAE |
| Validate toàn bộ bản dịch | Ngoài VAE |
| Crawl toàn website | Ngoài MVP |
| OCR scanned PDF hàng loạt | Flag unsupported hoặc module ngoài |
| Dùng search count làm score | Không thực hiện |
| Phê duyệt vì authority cao | Không thực hiện |
| Reject vì không tìm thấy web result | Không thực hiện |

---

# 31. TÓM TẮT TRIỂN KHAI CHO AGENT

```text
INPUT:
Frozen candidate + sense contract

DO:
1. Validate contract
2. Generate 2–3 queries
3. Search curated corpus and web
4. Normalize and canonicalize URLs
5. Fetch with cache, robots and rate limits
6. Extract HTML/text PDF
7. Find canonical/validated candidate surfaces
8. Build provenance-backed snippets
9. Profile source authority
10. Globally deduplicate and cluster
11. Validate domain
12. Validate concept using original + masked snippet
13. Analyze conventionality
14. Aggregate E features
15. Emit local status, flags and evidence package

DO NOT:
- decide glossary
- use C results
- count raw URLs
- treat web prevalence as correctness
- auto-seal variants
- reject solely for no attestation

OUTPUT:
VietnameseAttestationPackage
with final_glossary_decision = null
```

---

# 32. KẾT LUẬN

Vietnamese Attestation Evidence là một hệ thống retrieval–validation tạo bằng chứng về:

```text
authority
independence
domain relevance
concept match
conventionality
retrieval coverage
```

Nó không phải correctness oracle.

Bằng chứng E chỉ có ý nghĩa khi kết hợp với:

```text
Contextual Evidence C
+
Global Hard Gates
+
Calibrated Decision Policy
```

Thiết kế này bảo đảm agent không lệch scope:

- E độc lập với C;
- evidence tách khỏi constraint;
- URL tách khỏi independent evidence;
- attestation tách khỏi correctness;
- local status tách khỏi glossary decision;
- observed variant tách khỏi allowed variant;
- retrieval failure tách khỏi no evidence;
- mọi kết quả có thể audit và replay.
