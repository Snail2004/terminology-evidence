# Vietnamese Attestation Evidence V1.1

Status: REVIEW (pre-canary hardening complete; no live API gate run)

## Responsibility

This package produces Evidence E for one frozen English-Vietnamese term-sense
candidate. It is independent from Context Substitution and never makes the
final glossary decision. Every output keeps `final_glossary_decision` equal to
`null`; a future Global Terminology Validator owns the C+E decision.

The core result remains the six-dimensional Evidence E feature vector. V1.1
does not invent a weighted scalar or call E a probability of correctness.

## Standalone shared-contract boundary

The public input is `FrozenCandidateContractV1` 1.1.0 from the local
`contracts-v1.1.0` authority. It is schema-, self-hash-, and top-level
`input_contract_sha256`-validated before retrieval. The adapter preserves the
exact `candidate_key` and binds the internal execution to the complete shared
input. The shared contract has no separate `term_id`; its `candidate_id` is
used only as a deterministic internal alias and is never written back into the
shared join key.

The public result is `AttestationEvidencePackageV1` 1.1.0. It contains the six
E features, coverage metrics, accepted/rejected evidence references, proposed
variant observations, `run_spec_id`, `execution_config_sha256`, the complete
five-row producer gate-signal set, and `final_glossary_decision: null`.
Gate signals are derived only from sealed E status/count/coverage/evidence
facts; E never selects a global gate action.
The full `VietnameseAttestationPackageV1` 1.1.0 remains the audit store's
`package.json`; the shared projection is stored as `shared-package.json` and
binds the rich ledger through `provenance.raw_ledger_ref` and its SHA-256.
Legacy internal input/output is still accepted for fixture and compatibility
runs.

## V1.1 correctness policies

- Package schema: `VietnameseAttestationPackageV1` version `1.1.0`.
- Strong-positive policy: `strong-positive-v1`.
- Coverage policy: `attestation-coverage-v1.1`.
- Status policy: `attestation-status-v1.1`.
- Source policy: `source-tier-v2`.
- Dedup policy: `dedup-v2`.
- Fetch/cache policy: `attestation-fetch-v2`.
- Language detector: `vi-rule-detector-v1`.
- Cost policy default: `attestation-cost-v1` with unknown prices unless a
  versioned price table is supplied.
- Real dataset adapter: `VietnameseAttestationDatasetAdapterV1` version
  `1.0.0`, policy `d2l_vietnamese_attestation_real_dataset_adapter_v1`.

Accepted evidence must be Judgeable, SAME-sense, domain-matched, labeled as a
technical term, and not use source tier X. The machine-translation suspicion
rule is explicitly sealed as `FLAG_ONLY`, `DOWNWEIGHT`, or
`EXCLUDE_FROM_STRONG_POSITIVE`. `ATTESTED` is contract-bound to its accepted
cluster, independent-organization, and strong-source thresholds.

Coverage exports and rederives all stage subfeatures:

- search coverage;
- fetch coverage;
- extraction coverage;
- Vietnamese-language coverage;
- candidate span yield;
- Judge coverage.

`E_coverage` is the documented minimum of those six values. Low span yield is
reported separately and is not treated as a transport failure.

## Retrieval and evidence

HTML extraction prefers `<main>` or `<article>` and excludes navigation,
header, footer, aside, form, script and style content. A labeled visible-text
fallback remains available and adds `FALLBACK_EXTRACTION_REVIEW`. Text and PDF
extraction keep their own method labels. `min_words` is enforced before Judge,
and non-Vietnamese snippets are not sent to Judge.

Unknown PDFs are tier D, and an `.org` suffix alone is only tier C. Tier A/B is
derived from conservative public-sector/academic rules or explicit reviewed
overrides with reason codes. Duplicate clustering uses exact or near-duplicate
content only; organization is not a duplicate condition. The package retains
each duplicate cluster, representative, every member, content hashes,
publisher/organization identities, and reason codes.

## Audit and replay

Each execution receives:

- stable `run_spec_id` for frozen candidate plus redacted behavior identities;
- unique `attestation_execution_id` for the concrete web snapshot.

The file audit store is append-only during execution and retains:

```text
runs/<execution_id>/
|-- run_manifest.json
|-- search/requests.jsonl
|-- search/responses/<sha256>.json
|-- search/normalized_results.jsonl
|-- fetch/attempts.jsonl
|-- fetch/bodies/<sha256>
|-- extraction/records.jsonl
|-- extraction/texts/<sha256>.txt
|-- snippets/snippets.jsonl
|-- dedup/clusters.jsonl
|-- judge/attempts.jsonl
|-- judge/responses/<sha256>.json
`-- package.json
```

Every selected URL receives one terminal outcome. URLs omitted by the fetch cap
receive `FETCH_LIMIT_NOT_SELECTED`. Raw built-in Search responses, fetch bodies,
extracted text, invalid Judge responses, normalized Judge responses, and dedup
members are content-addressed. `AuditReplayReader` verifies hashes and supports
the five sealed replay boundaries from Search through Judge.

The cache stores the original retrieval timestamp, HTTP status, redacted
headers, fetch-policy version, robots result, redirect chain, URL and content
hash. A cache hit preserves that timestamp instead of pretending it was fetched
at the current run start.

## Judge routes

Default availability order:

1. ShopAI (`SHOPAI_API_KEY`)
2. CKey (`CKEY_API_KEY`, `CKEY_BASE_URL`)
3. official Gemini (`GEMINI_API_KEY`)

Fallback occurs only after transport or schema failure. A valid semantic
result, including `DIFFERENT`, is final for that snippet. Search has its own
bounded retry and rate limiter. Judge request/response hashes, raw responses,
token counts, route attempts and cost-price status are retained.

## CLI

Strict zero-API pilot adaptation:

```powershell
python -m vietnamese_attestation.v1.cli.adapt_dataset `
  --source-zip <dataset>\pilot_dev_only_v1_1.zip `
  --parent-v3-zip <dataset>\d2l_context_support_set_validation_ready_v3.zip `
  --output adapter-package.json `
  --receipt-output adapter-receipt.json
```

The adapter verifies the exact physical ZIP, manifest, all manifest-bound
files, row hashes, joins and cardinalities. It maps V3 as `150/450/1340` and
pilot V1.1 as `5/15/38`. It does not read C outputs, does not infer known
Vietnamese surfaces or domain anchors, and emits no final glossary decision.
See `REAL_DATASET_ADAPTER_V1.md` for the authority and schema observations.

Offline fixture execution:

```powershell
python -m vietnamese_attestation.v1.cli.run `
  --candidate candidate.json `
  --development-input `
  --offline-fixture fixture.json `
  --run-store-root .artifacts/vietnamese-attestation `
  --output attestation.json
```

`--development-input` is fixture-only. Official execution must instead provide
all of `--dataset-release-manifest`, `--dataset-release-receipt`,
`--dataset-release-receipt-sha256`, `--candidate-root` and
`--official-candidate-id`. The loader verifies the externally pinned receipt,
exact 15-member set, producer, physical hashes, candidate self-hashes and all
candidate/sense/scope/dataset/effective-sense/input joins before engine setup.
The run store also contains the rich internal replay package. Running directly
from the repository requires both package roots on `PYTHONPATH`:

```powershell
$env:PYTHONPATH="$PWD;$PWD\terminology_contracts_v1\python"
```

Live execution additionally requires `BRAVE_SEARCH_API_KEY`, all configured
Judge credentials, and a cache root:

```powershell
python -m vietnamese_attestation.v1.cli.run `
  --dataset-release-manifest dataset_release_manifest.json `
  --dataset-release-receipt dataset_release_receipt.json `
  --dataset-release-receipt-sha256 <trusted-receipt-physical-sha256> `
  --candidate-root frozen_candidates `
  --official-candidate-id <candidate-id> `
  --cache-root .cache/vietnamese-attestation `
  --run-store-root .artifacts/vietnamese-attestation `
  --output attestation.json
```

Verified replay:

```powershell
python -m vietnamese_attestation.v1.cli.replay `
  --manifest .artifacts/vietnamese-attestation/runs/<execution_id>/run_manifest.json `
  --expected-manifest-sha256 <externally-sealed-manifest-sha256> `
  --mode REPLAY_FROM_JUDGE `
  --output replay.json
```

Development pilot zero-API execution:

```powershell
python -m vietnamese_attestation.v1.cli.zero_api `
  --source-zip dataset/pilot_dev_only_v1_1.zip `
  --parent-v3-zip dataset/d2l_context_support_set_validation_ready_v3.zip `
  --controlled-registry dataset/dataset_methodology_hardening_v1/release/controlled_vietnamese_source_registry.jsonl `
  --output-root <artifact-root>
```

This executes the exact 15 pilot candidate identities with deterministic
offline evidence fixtures. The scenarios cover strong independent evidence,
duplicate echo, same-organization documents, RELATED, DIFFERENT, UNCERTAIN,
Judge unavailable, search/fetch/extraction failure, non-Vietnamese content,
missing spans, suspected machine translation, unknown PDF, and conflicting
attestation. Each run writes an internal E package, content-addressed audit
artifacts, raw responses, and verified replay results. External provider calls
remain zero. `zero_api_artifact_manifest.json` binds every generated file by
relative path, physical SHA-256, and byte count.

The controlled Vietnamese registry published by Dataset Methodology Hardening
V1 is currently byte-empty and is reported as `BLOCKED_EXTERNAL_INPUT`.
Likewise, the development pilot has no effective sense contract SHA, approved
Vietnamese surface inventory, or domain anchors. Shared V1.1 projection is
therefore withheld as `BLOCKED_DEVELOPMENT_IDENTITY`; the runner does not invent
authority hashes or silently coerce development candidates into official
packages.

Post-zero-API readiness adds a commit-bound, cache-free source release and
machine-readable verification reports. The release independently verifies the
published Contracts V1.1 authority, all 273 zero-API artifact members, 15/15
replay manifests, zero external calls, and the two external-input HOLD states.
Offline shared packages remain projection-conformance artifacts only; real E
evidence authority requires official Dataset inputs, an approved source plan,
and provider compatibility canaries.
The release gate also requires a parsed, exact 80-test E-suite JUnit report with
zero failures, errors or skips. Its exact testcase identity set and test-source
tree are hash-pinned; missing, renamed, fabricated or unrelated reports cannot
produce a PASS release.

## Remaining gates

- No live Search or Judge request has been made by this implementation gate.
- Direct ShopAI-only, CKey-only, Gemini-only and Brave compatibility canaries
  remain required before a semantic live pilot.
- Embedding-domain similarity remains a diagnostic proposal, not a gate.
- New surface discovery remains disabled; `observed_variants` is bounded and
  cannot mutate the candidate contract.
- The zero-API 5-sense/15-candidate input adapter and deterministic E2E fixture
  run are complete. Controlled-corpus retrieval remains blocked by the empty
  registry, and shared projection remains blocked by development-only identity
  gaps. Human cluster labels, live semantic pilot execution, local-status
  calibration, and the later 150-term research set remain separate gates.
