# Vietnamese Attestation V1.1 Rework Receipt

Status: REVIEW

This receipt maps the independent V1 review to the 0-API V1.1 candidate. It
does not authorize a semantic live canary or claim research calibration.

## Closed correctness findings

| Finding | V1.1 closure |
| --- | --- |
| General words could become `ATTESTED` | One strong-positive predicate now binds acceptance, aggregation and package validation. |
| `ATTESTED` could have no accepted evidence | The output contract enforces accepted cluster, organization and source thresholds. |
| Coverage hid documents with no candidate span | Stage counts and six rederived coverage/yield values are sealed; span yield participates in versioned `E_coverage`. |
| Arbitrary PDF or `.org` gained tier B | Unknown PDF is D; `.org` alone is C; tier X and authority reason codes are supported. |
| Same-organization documents collapsed | Duplicate clustering uses content similarity only; organization is a separate independence identity. |
| Duplicate members disappeared | Every cluster exports representative, all member IDs/content hashes, publisher and organization IDs, and reasons. |

## Closed audit/replay findings

- Search attempts, raw responses and normalized results are retained.
- Every selected URL has exactly one terminal status; capped URLs are recorded
  as `FETCH_LIMIT_NOT_SELECTED`.
- Fetch bodies, extraction attempts/text, span observations, duplicate
  clusters, Judge attempts, and valid or invalid Judge responses are retained.
- Content-addressed artifacts and stream hashes are verified by
  `AuditReplayReader` at five replay boundaries.
- Stable `run_spec_id` and unique `attestation_execution_id` are separate.
- Cached evidence preserves its original `retrieved_at`, HTTP/fetch/robots and
  redirect metadata.
- Redacted execution identity includes configuration, provider endpoints,
  fetch/cache/robots behavior, source overrides, extraction, language, dedup,
  prompt and model routes.

## Closed pre-canary quality findings

- HTML extraction prefers main/article content and excludes common page chrome.
- Visible-text fallback is explicitly labeled for review.
- `min_words` is enforced.
- A deterministic Vietnamese-language gate runs before Judge.
- Search has bounded retry and rate limiting.
- Restricted-source queries are configurable and disabled by default.
- Search/Judge/fetch/token/cost telemetry is emitted with explicit unknown
  pricing when a versioned price table is not supplied.

## Real V3/pilot input adapter

- The adapter accepts only the exact physical V3 and pilot V1.1 ZIP hashes
  declared by the C/E handoff.
- V3 maps `150` senses, `450` candidates and `1,340` contexts; pilot maps
  `5`, `15` and `38` and is byte-subset-bound to the exact V3 parent.
- `candidate_id` and `candidate_version` remain byte-for-byte equal to
  `candidate_instance_id` and `candidate_instance_sha256`.
- Candidate-slot, source-row, manifest, file, row, offset and selected-context
  references fail closed on drift.
- English source surfaces are not treated as Vietnamese variants. Known
  Vietnamese surfaces and domain anchors remain explicitly unavailable.
- Candidate rows remain non-official, non-calibrated and pending human review;
  provider calls are zero and `final_glossary_decision` remains `null`.
- One V3 POS evidence-context reference is absent from the package. E does not
  consume that array and binds definition provenance by `term_sense_sha256`;
  the exact observation is recorded in `REAL_DATASET_ADAPTER_V1.md`.

## Deliberately not claimed

- The deterministic language detector is a prefilter, not a research-grade
  language classifier.
- Embedding domain similarity is not implemented as a gate.
- V1.1 counts all candidate occurrences but still judges one deterministic
  representative snippet per document.
- Surface discovery remains disabled.
- No ShopAI, CKey, official Gemini, Brave, or semantic end-to-end live call was
  executed during this rework.
- Human evidence labels, threshold calibration, live compatibility canaries,
  and the later research pilot remain required before promotion beyond REVIEW.
