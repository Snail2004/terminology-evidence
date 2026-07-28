# CODE REVIEW — VIETNAMESE ATTESTATION EVIDENCE V1
## Next-step contract for the implementation agent

**Artifact reviewed:** `vietnamese_attestation.zip`  
**Review scope:** source architecture, contracts, retrieval, fetch/cache, extraction,
deduplication, source authority, judging routes, aggregation, provenance and declared
implementation status.

## Executive verdict

The implementation has a good architectural skeleton and respects the most important
authority boundary:

```text
Evidence E only
final_glossary_decision = null
no dependency on Context Substitution
```

However, the current implementation must **not** be promoted as a research-ready E
component and should **not** begin a semantic live canary yet.

There are four reproduced correctness defects that can materially produce a false
`ATTESTED` result:

1. A `GENERAL_WORD` can produce `ATTESTED`.
2. `E_coverage` can be 1.0 even when only a small fraction of fetched documents
   contains a candidate snippet.
3. Completely unrelated documents from one organization are collapsed into one
   evidence cluster.
4. Any PDF from any domain is automatically promoted to source tier B.

There are also major audit/replay gaps. Live calls made before those gaps are fixed
would consume money but would not produce a fully reproducible research artifact.

```text
ARCHITECTURE ALIGNMENT: CONDITIONAL PASS
STATIC COMPILE: PASS
MVP DEMO READINESS: PASS
SEMANTIC LIVE CANARY: BLOCKED
RESEARCH PILOT: BLOCKED
CALIBRATED E SCORE: NOT A REQUIRED E DELIVERABLE
GLOBAL C+E INTEGRATION: OUTSIDE THIS AGENT'S SCOPE
```

---

# 1. What is implemented well

## 1.1. Authority boundary

`runtime/engine.py:145–149` always emits:

```json
{
  "observed_variants": [],
  "final_glossary_decision": null
}
```

`contracts/output.py:134–139` rejects any non-null glossary decision.

This is correct. E is an evidence provider, not a glossary decision engine.

## 1.2. Frozen input contract

`contracts/frozen_candidate.py` binds:

- candidate;
- sense;
- definition;
- known surfaces;
- domain anchors;
- policy versions;
- source artifact;
- self-hash.

The canonical surface is required to equal `candidate_vi`, and the contract is
self-hashed.

## 1.3. Schema-bound Judge

The Judge:

- receives original and masked snippets;
- cannot return extra fields;
- must quote an evidence span from the original snippet;
- uses `SAME / RELATED / DIFFERENT / UNCERTAIN`;
- uses `TECHNICAL_TERM / GENERAL_WORD / ...`;
- cannot return an arbitrary score or glossary decision.

`contracts/judge.py:111–140` verifies that a Judge evidence span exists in the
snippet.

## 1.4. Bounded route failover

`judging/router.py` fails over only on transport or schema failure. A valid
`DIFFERENT` result does not trigger another route. This is correct availability
routing.

## 1.5. Exact candidate masking

`evidence/spans.py` keeps the exact local span and constructs the masked snippet
deterministically. The output contract rechecks the span and mask.

## 1.6. Basic operational protections

The code includes:

- URL canonicalization;
- robots policy;
- fetch cache;
- host rate limiting;
- bounded fetch retry;
- HTTP size limit;
- HTML, text and text-PDF extraction;
- request/response hashes;
- Judge token counts;
- package self-hash.

These are good foundations.

---

# 2. P0 correctness defects — fix before semantic live canary

## P0-1. `ATTESTED` can be produced with zero accepted evidence

### Locations

- `runtime/aggregation.py:28–43`
- `runtime/aggregation.py:89–99`
- `runtime/aggregation.py:138–169`
- `runtime/engine.py:357–400`

The engine accepts evidence only when all of these hold:

```text
judgeability = JUDGEABLE
domain_match = true
candidate_role = TECHNICAL_TERM
concept_relation = SAME
```

But aggregation defines positive evidence as only:

```python
concept_relation in {"SAME", "RELATED"} and domain_match
```

It does not require `candidate_role == TECHNICAL_TERM`.

The local-status logic counts all `SAME` clusters, including a result labeled
`GENERAL_WORD`.

### Reproduced case

Two tier-A sources from two organizations, both judged:

```json
{
  "judgeability": "JUDGEABLE",
  "concept_relation": "SAME",
  "domain_match": true,
  "candidate_role": "GENERAL_WORD"
}
```

produce:

```text
status = ATTESTED
recommendation = EVIDENCE_AVAILABLE
accepted_evidence count = 0
```

### Required fix

Create one deterministic predicate and use it everywhere:

```python
def is_strong_positive_evidence(row):
    return (
        row["judge"]["judgeability"] == "JUDGEABLE"
        and row["judge"]["concept_relation"] == "SAME"
        and row["judge"]["domain_match"] is True
        and row["judge"]["candidate_role"] == "TECHNICAL_TERM"
        and row["source_tier"] != "X"
    )
```

Use the same predicate for:

- accepted evidence;
- SAME cluster count used by local status;
- authority;
- positive-source independence;
- conventionality;
- organization count;
- strong-source gate.

Add invariant:

```text
status = ATTESTED
→ accepted_evidence_count >= min_same_clusters_for_attested
```

Machine-translation suspicion must be controlled by a versioned policy:

```text
FLAG_ONLY
DOWNWEIGHT
EXCLUDE_FROM_STRONG_POSITIVE
```

Do not leave it implicit.

---

## P0-2. `E_coverage` omits candidate-span yield

### Locations

- `runtime/engine.py:203–280`
- `runtime/aggregation.py:44–55`

Coverage is currently:

```text
min(fetch coverage, extraction coverage, Judge coverage)
```

Judge coverage is calculated only over documents that already produced a candidate
snippet and survived deduplication.

### Reproduced case

Given:

```text
20 fetch attempts
20 fetch successes
20 extraction successes
2 documents containing the candidate
2 Judgeable representatives
```

the implementation returns:

```text
E_coverage = 1.0
```

The 18 documents with no candidate span disappear from the denominator.

### Required fix

Preserve stage counts:

```text
search_query_attempt_count
search_query_success_count
raw_result_count
unique_url_count
fetch_attempt_count
fetch_success_count
extraction_success_count
language_eligible_count
candidate_span_document_count
candidate_occurrence_count
pre_dedup_snippet_count
post_dedup_cluster_count
judged_cluster_count
judgeable_cluster_count
```

Define versioned coverage subfeatures:

```text
search_coverage
fetch_coverage
extraction_coverage
language_coverage
span_yield
judge_coverage
```

Do not silently use only their minimum without calibration. At minimum export all
subfeatures and define:

```text
E_coverage_v1 = min(
    search_coverage,
    fetch_coverage,
    extraction_coverage,
    judge_coverage
)
```

while reporting `span_yield` separately. If `span_yield` is included in
`E_coverage`, document and version that choice.

Important distinction:

```text
low span yield
≠ retrieval system failure
≠ proof candidate is wrong
```

It may support `NOT_ATTESTED` only when search/fetch/extraction coverage is adequate.

---

## P0-3. Source authority is unsafe

### Location

- `evidence/sources.py:35–49`

Current policy assigns tier B to:

```python
elif content_kind == "pdf":
    tier = "B"
```

It also assigns tier B to any `.org` domain.

### Reproduced case

```text
https://spam-example.com/file.pdf
```

is classified as:

```text
source_type = technical_pdf
source_tier = B
```

A file format is not source authority.

### Required fix

1. Add source tier `X` to contracts and aggregation.
2. Default unknown sources conservatively to C or D.
3. Never derive B solely from `content_kind == "pdf"`.
4. Never derive B solely from `.org`.
5. Use a versioned source policy with:
   - verified organization overrides;
   - public-sector/academic domain rules;
   - author and publisher metadata;
   - document type;
   - spam/mirror/MT risk;
   - reason codes.
6. Output:

```json
{
  "source_tier": "B",
  "source_tier_reasons": ["VERIFIED_UNIVERSITY_DOMAIN"],
  "source_policy_version": "source-tier-v2"
}
```

Authority rules must be auditable without asking the LLM to invent a tier.

---

## P0-4. Deduplication collapses every document from one organization

### Location

- `evidence/dedup.py:41–52`

Current union rule:

```python
if same_organization or exact or near:
    union(left, right)
```

Two completely unrelated documents from the same organization therefore become one
cluster.

### Reproduced case

Two unrelated articles under `same.org` receive the same
`independent_cluster_id`.

### Consequences

- only one representative is judged;
- concept conflict within one organization disappears;
- conventionality across several documents is lost;
- a weak representative can replace a strong document;
- `candidate_snippet_count` is reduced to representative count.

### Required redesign

Separate these concepts:

```text
duplicate_cluster_id
publisher_id
organization_id
independence_group_id
```

Duplicate clustering should use:

- exact content hash;
- near-duplicate content;
- mirror/source relationship;
- canonical URL relationship.

Organization must not be a duplicate condition.

Independence can be computed separately:

```text
independent organization count
independent publisher count
unique document count
duplicate cluster count
```

Preserve every cluster member and dedup reason:

```json
{
  "duplicate_cluster_id": "...",
  "representative_evidence_id": "...",
  "member_evidence_ids": ["..."],
  "dedup_reasons": ["NEAR_DUPLICATE_CONTENT"]
}
```

Judge one representative per duplicate cluster, not one representative per
organization.

---

# 3. P0 audit and reproducibility gaps — fix before spending API budget

## P0-5. Failures are swallowed instead of recorded

### Locations

- `runtime/engine.py:185–201`
- `runtime/engine.py:220–237`

Current behavior:

```text
Search error → increment one counter
Fetch error → continue
Extraction error → continue
No candidate span → continue
```

The output cannot distinguish:

```text
SEARCH_TIMEOUT
SEARCH_RATE_LIMITED
ROBOTS_BLOCKED
HTTP_404
HTTP_429
FETCH_TIMEOUT
CONTENT_TOO_LARGE
UNSUPPORTED_CONTENT_TYPE
EXTRACTION_FAILED
UNSUPPORTED_SCANNED_PDF
LANGUAGE_MISMATCH
NO_CANDIDATE_SPAN
```

### Required fix

Create an append-only per-stage event ledger:

```text
search_attempts.jsonl
search_results.jsonl
url_attempts.jsonl
extraction_attempts.jsonl
span_observations.jsonl
dedup_clusters.jsonl
judge_attempts.jsonl
```

Every URL receives a terminal stage/status. Aggregate counts must be derived from the
ledger, not maintained separately by hand.

---

## P0-6. Raw replay is not implemented

The package stores hashes and normalized outputs but not enough material to replay:

- raw Search response is not stored;
- invalid Judge response is not stored;
- fetch failure response/status is not stored;
- extracted text snapshot is not referenced in the final package;
- duplicate cluster members are discarded.

### Required fix

Create a content-addressed run store:

```text
runs/<execution_id>/
├── run_manifest.json
├── search/
│   ├── requests.jsonl
│   ├── responses/<sha256>.json
│   └── normalized_results.jsonl
├── fetch/
│   ├── attempts.jsonl
│   └── bodies/<sha256>
├── extraction/
│   ├── records.jsonl
│   └── texts/<sha256>.txt
├── snippets/snippets.jsonl
├── dedup/clusters.jsonl
├── judge/
│   ├── attempts.jsonl
│   └── responses/<sha256>.json
└── package.json
```

Public research artifacts may expose only permitted snippets and hashes, but the local
audit store must permit deterministic replay.

Support:

```text
REPLAY_FROM_SEARCH
REPLAY_FROM_FETCH
REPLAY_FROM_EXTRACTION
REPLAY_FROM_SNIPPETS
REPLAY_FROM_JUDGE
```

---

## P0-7. Run identity can collide across changing web results

### Locations

- `runtime/engine.py:431–469`

`attestation_run_id` depends on:

- frozen candidate hash;
- query-plan ID;
- execution-config hash;
- run policy.

It does not include execution time or retrieval snapshot.

A second run weeks later can retrieve different pages but receive the same run ID.

### Required fix

Split identity into:

```text
run_spec_id
```

Stable hash of candidate + policy/config.

```text
attestation_execution_id
```

Unique execution identifier including start time/nonce or retrieval snapshot manifest
hash.

Bind the final package to both.

---

## P0-8. Cache provenance is stale and incomplete

### Locations

- `retrieval/fetch.py:71–119`
- `runtime/engine.py:269–270`

The disk cache stores:

- URL;
- content type;
- content hash;
- body.

It does not store:

- retrieved time;
- HTTP status;
- headers;
- fetch-policy version;
- robots result;
- redirect chain.

The engine labels every document with the current run's `started_at`, including an old
cache hit.

### Required fix

Store cache metadata and use the actual retrieval timestamp.

Cache identity must include or record:

```text
canonical_url
fetch_policy_version
retrieval date/snapshot
content hash
```

A run may intentionally reuse an old snapshot, but it must say so explicitly.

---

## P0-9. Execution-config hash omits important behavior

### Location

- `runtime/engine.py:447–469`

The hash includes provider IDs and Judge model IDs, but omits:

- provider endpoints;
- Search parameters;
- fetch timeout/retry/size;
- robots policy;
- user agent;
- cache policy;
- source overrides;
- dedup threshold;
- source policy implementation;
- extraction configuration.

Two behaviorally different runs can share one execution-config hash.

### Required fix

Every component must expose a redacted `identity_payload()` and version:

```text
SearchProvider
DocumentFetcher
RobotsPolicy
FetchCache
Extractor
SourceProfiler
Deduplicator
LanguageDetector
DomainValidator
JudgeProvider
CostPolicy
```

Never include API secrets.

---

# 4. P1 evidence-quality fixes — before end-to-end development pilot

## P1-1. HTML extraction is not main-content extraction

### Location

- `retrieval/extraction.py:27–93`

The current HTML parser concatenates all visible page text, including navigation,
menus, cookie banners, footer and unrelated page sections.

Because the span locator chooses the first occurrence, a menu or navigation occurrence
can become evidence.

### Required fix

Use Trafilatura or an equivalent main-content extractor.

Preserve:

- title;
- author;
- publication date;
- headings;
- paragraph boundaries;
- section title;
- extraction method/version.

Keep the simple HTML parser only as a labeled fallback:

```text
MAIN_CONTENT_EXTRACTED
FALLBACK_VISIBLE_TEXT
```

Fallback evidence should be downweighted or sent to review.

---

## P1-2. Only the first occurrence is used

### Location

- `evidence/spans.py:69–96`

The engine chooses one first occurrence across all canonical/validated surfaces.

### Required fix

Produce all bounded occurrences, then select or retain:

```text
canonical occurrence
validated-variant occurrence
section/title context
main-body occurrence
duplicate occurrence
```

Selection must be deterministic and recorded.

At minimum, choose the best main-body occurrence rather than the earliest page
occurrence.

---

## P1-3. `min_words` is configured but ignored

### Locations

- `config.py:17–21`
- `evidence/spans.py:20–66`

### Reproduced case

With `min_words=20`, the text:

```text
Đây là suy luận.
```

still produces a valid snippet.

### Required fix

Apply the configured lower bound or rename the configuration.

More importantly, distinguish:

```text
snippet too short
candidate only in heading
candidate only in caption
candidate only in code
candidate only in metadata
```

---

## P1-4. No independent Vietnamese language check

Before Judge calls, add a deterministic language detector:

```text
VIETNAMESE
MIXED_VI_EN
NON_VIETNAMESE
UNCERTAIN
```

Do not Judge non-Vietnamese snippets as Vietnamese attestation.

Store detector model/version and confidence.

This should be completed before semantic end-to-end canary.

---

## P1-5. Domain validation is Judge-only

Do not immediately turn embeddings into a gate.

Implement independent diagnostics:

1. deterministic domain anchors;
2. multilingual embedding similarity;
3. Attestation Judge domain label.

Export all three and measure them against human labels.

Embedding is a probe/feature until validation demonstrates value.

---

## P1-6. Search adapter lacks Search-level retry/rate limiting

`BraveSearchProvider` performs one request. Fetch retry/rate limiting does not protect
Search API calls.

Add:

- bounded Search retry;
- Search rate limiter;
- HTTP status/error taxonomy;
- Retry-After handling;
- latency;
- raw request/response snapshot;
- provider request ID when returned.

Also preserve query text and rank in the run ledger.

---

## P1-7. Query plan does not include restricted-source retrieval

The current three queries are:

```text
exact candidate
candidate + domain anchors
candidate + source term
```

Add a configurable restricted-source query class, not necessarily for every run:

```text
site:edu.vn
site:gov.vn
filetype:pdf
```

Do not hard-code it into scientific weighting before measuring retrieval value.

---

# 5. Feature semantics and scalar score

## Do not make a scalar `E_score` the next deliverable

The six-dimensional feature vector is the correct core output:

```text
E_authority
E_independence
E_domain
E_concept
E_conventionality
E_coverage
```

E is attestation evidence, not correctness probability.

Do not create:

```text
E_score = fixed weighted sum
```

and do not call any scalar a probability of correctness.

## What may be calibrated

### E-local calibration

Using human attestation labels, tune:

- `ATTESTED`;
- `WEAKLY_ATTESTED`;
- `NOT_ATTESTED`;
- `CONFLICTING_ATTESTATION`;
- `ATTESTATION_UNJUDGEABLE`.

This calibrates local status policy, not candidate correctness.

### Global calibration

A separate Global Validator may later learn or calibrate:

```text
C features + E features + gates
→ approval score / system decision
```

That scalar belongs to the Global Validator, not to the E module.

---

# 6. Observed variants

The implementation always emits:

```json
"observed_variants": []
```

Do not add free-form LLM variant generation inside E.

Implement a bounded surface-observation ledger first:

```text
canonical surface occurrences
validated variant occurrences
rejected variant occurrences
unrecognized expanded surface observations
```

An unrecognized surface may be exported only as:

```text
PROPOSE_FOR_CST_VARIANT_CHECK
```

It must not enter `allowed_variants`.

Variant discovery is lower priority than aggregation correctness, replay and evaluation.

---

# 7. Cost reporting

Add cost telemetry before live canary so the canary itself is measurable.

Output:

```text
search_requests
search_cost
judge_attempts by route
input/output tokens by route
estimated Judge cost
fetch count
elapsed time by stage
cost per candidate
cost per judged cluster
cost per accepted evidence cluster
```

Pricing must come from a versioned runtime configuration, not be permanently hard-coded.
Record currency, effective date and unknown-price status.

---

# 8. Correct next-step sequence

## Phase E0 — Pre-canary hardening, 0 API

The E agent should do this now.

### Required code changes

1. Fix accepted/positive evidence aggregation.
2. Fix coverage and count semantics.
3. Redesign duplicate versus organization grouping.
4. Replace unsafe PDF/`.org` authority rules.
5. Add failure ledger and replay store.
6. Split stable run spec from unique execution ID.
7. Fix cache retrieval timestamps and identity.
8. Expand execution-config identity.
9. Add main-content extraction and language detection.
10. Enforce `min_words`.
11. Add cost aggregator.
12. Package tests/JUnit and remove `__pycache__`.

### Required tests

Add regression tests for:

```text
general word cannot become ATTESTED
ATTESTED implies accepted evidence
20 fetches / 2 spans cannot report full span coverage
unknown PDF is not automatically tier B
same organization + different content is not a duplicate
duplicate mirrors collapse correctly
cached retrieved_at is preserved
second execution receives a distinct execution ID
every URL has one terminal failure/success status
main-text extraction rejects navigation-only occurrence
min_words is enforced
```

## Phase E1 — Direct live compatibility canary

Only after Phase E0 passes.

Run each route directly, with failover disabled:

```text
ShopAI-only
CKey-only
Gemini-official-only
```

Use one fixed, reviewed snippet and verify:

- endpoint;
- authentication;
- request schema;
- structured-output support;
- response parsing;
- usage fields;
- error taxonomy;
- raw replay;
- latency and cost.

Separately run one Brave Search query and one or two fetches.

This canary validates transport/schema only. It does not produce thesis evidence.

## Phase E2 — Development-only end-to-end pilot

Use the existing development-only pilot after its sense definitions/POS are human
reviewed and frozen.

Recommended initial scale:

```text
5 senses
15 candidates
```

For every candidate:

- run E;
- human-label the top evidence clusters;
- inspect duplicate clusters;
- inspect C-high/E-low and C-low/E-high later when C becomes available.

Do not calibrate thresholds from only 15 candidates.

## Phase E3 — E component evaluation

Use approximately 30–50 candidate instances for development diagnostics, not
necessarily 30 complete term-senses.

Create:

- Integration A–F;
- adversarial E set;
- cluster-level human labels;
- candidate-level human attestation labels.

Report:

```text
Evidence Precision@5
strong-source discovery rate
duplicate precision/recall
domain accuracy
SAME precision/recall
false SAME rate
Judge–human kappa
local-status confusion matrix
cost/candidate
```

Tune E-local heuristics only on development data.

## Phase E4 — Global Validator handoff

This is **not the E agent's responsibility**.

The E agent must deliver:

- frozen E output schema;
- sample packages;
- replay artifacts;
- feature dictionary;
- failure taxonomy;
- cost schema;
- join keys.

A separate Global Validator agent joins:

```text
candidate_id
candidate_version
sense_id
scope_id
sense_inventory_version
```

with C output and gates.

Do not import C into E and do not let E read C scores.

---

# 9. Integration A–F required cases

## A — Strong candidate

```text
multiple SAME technical-term clusters
multiple organizations
at least one strong source
adequate coverage
```

Expected local status: `ATTESTED`.

## B — Duplicate echo

```text
one original
multiple mirrors
```

Expected: one duplicate cluster, explicit member ledger, no inflated independence.

## C — Popular but wrong sense/domain

Expected:

```text
high raw occurrence count possible
low valid positive evidence
not ATTESTED
```

## D — Correct but new

One strong SAME source.

Expected:

```text
WEAKLY_ATTESTED
never REJECTED solely for low frequency
```

## E — Retrieval failure

Most URLs blocked/fail.

Expected:

```text
ATTESTATION_UNJUDGEABLE
not NOT_ATTESTED
```

## F — Conflicting evidence

Strong SAME and strong DIFFERENT evidence.

Expected:

```text
CONFLICTING_ATTESTATION
```

Conflict policy must ignore irrelevant-domain or unusable weak rows unless explicitly
configured.

---

# 10. Review of the agent's proposed next step

The proposal:

> Run 5–10 terms through all three routes, then create 30 labeled term-senses and
> calibrate a scalar E score.

is only partly correct.

## Correct parts

- live route compatibility must be tested;
- human-labeled evidence is required;
- fixed weights must not be guessed.

## Required corrections

1. Do pre-canary hardening first.
2. Test each route directly, not only through failover.
3. Do not make scalar `E_score` a required E output.
4. Label evidence clusters as well as candidate-level attestation.
5. Start with 30–50 candidate instances for E development diagnostics.
6. Leave C+E combination to a separate Global Validator.
7. Do not promote/merge before P0 regressions and packaged tests pass.

---

# 11. Promotion verdict

Current candidate:

```text
REVIEW
```

should remain unmerged.

Promotion conditions:

```text
P0 regression suite passes
raw replay demonstrated
direct provider canary passes or is explicitly marked unavailable
source-tier policy fixed
coverage/count contract fixed
dedup/member ledger fixed
tests and CLI included in review artifact
reviewer signs off
```

After these conditions, promote as:

```text
Vietnamese Attestation Evidence V1 — implementation-ready development component
```

Do not label it:

```text
calibrated E score
research-validated E
production-ready attestation oracle
```

---

# 12. Copy-ready instruction for the E agent

```text
Keep Vietnamese Attestation independent from Context Substitution and preserve
final_glossary_decision=null.

Do not run semantic live canary yet.

Create a pre-canary V1.1 patch that:
1. defines one strong-positive evidence predicate and uses it consistently;
2. guarantees ATTESTED cannot occur with zero accepted technical-term evidence;
3. exports pre-dedup snippets, duplicate clusters, cluster members and dedup reasons;
4. separates duplicate clustering from organization independence;
5. fixes E_coverage and exports stage-level coverage/yield metrics;
6. removes automatic tier-B promotion for arbitrary PDF/.org sources and adds tier X;
7. stores append-only Search/fetch/extraction/span/dedup/Judge event ledgers;
8. supports raw replay from every stage;
9. separates run_spec_id from unique attestation_execution_id;
10. stores actual cached retrieved_at and complete redacted component identities;
11. uses main-content HTML extraction, enforces min_words and adds language detection;
12. aggregates Search/Judge cost using versioned price configuration;
13. adds the P0 regression tests listed in the review;
14. packages CLI, tests, JUnit report and removes __pycache__.

After reviewer approval, run direct ShopAI-only, CKey-only and Gemini-only schema
canaries plus one Brave canary. Then run the development-only 5-sense/15-candidate
pilot after human-reviewed sense contracts are frozen.

Keep the six E features. Do not invent a fixed weighted scalar E_score. A future
Global Validator will calibrate C+E+gates.
```
