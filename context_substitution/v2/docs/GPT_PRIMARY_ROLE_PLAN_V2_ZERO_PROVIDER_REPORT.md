# GPT-Primary Provider Role Plan V2: Zero-Provider Report

## Authority

```text
plan_id: cst_live_role_routing_gpt_primary_v2
schema: ContextSubstitutionProviderRolePlanV1 / 1.0.0
canonical self SHA256: 155261fc2c80e54b6e22e266104fa6a5a2040fa6faf4b8d7865bb970a763e815
physical SHA256: 6a229435a2d84198dc88bee26c3b4bb5645b7b086849c4f5e1a13217a9152e61
candidate_replicate_cap: 1
external provider calls: 0
network calls: 0
final decision owner: GLOBAL_TERMINOLOGY_VALIDATOR
```

V1 remains byte-identical and loadable as the replay authority. V2 was
selected before D0 for quota balance and cross-family independence. No claim
of superiority over V1 is made.

## Mandatory semantic calls

The baseline below uses frozen human-reviewed selection, five valid
same-sense contexts per candidate, one trial attempt and one contrastive
context per candidate.

| Fixture | Gemini translator | GPT quality gate | GPT primary | GPT contrastive | Mandatory Gemini | Mandatory GPT | Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| One candidate | 5 | 5 | 5 | 1 | 5 | 11 | 16 |
| One sense / three candidates | 15 | 15 | 15 | 3 | 15 | 33 | 48 |
| Five senses / fifteen candidates | 75 | 75 | 75 | 15 | 75 | 165 | 240 |

A second contrastive context adds one GPT Terra-low semantic call per
candidate. Therefore the one-sense mandatory GPT range is 33-36, and the
five-sense mandatory GPT range is 165-180.

Frozen Dataset selection makes zero Context Selector calls. A future
authorized non-frozen run would add one Gemini selector call per sense.

## Conditional semantic calls

| Condition | One candidate | One sense / three candidates | Five senses / fifteen candidates |
|---|---:|---:|---:|
| Secondary Gemini judge, maximum | 5 | 15 | 75 |
| Pairwise GPT tiebreaker, maximum | 0 | 3 | 15 |
| Trial regeneration: extra Gemini translator | 5 | 15 | 75 |
| Trial regeneration: extra GPT quality gate | 5 | 15 | 75 |

Secondary and pairwise calls are not mandatory. One invalid trial can add one
new Translator semantic call and one new Quality Gate semantic call for that
candidate-context. This regeneration is not a new candidate replicate.

## Physical requests

Semantic calls, provider requests and transport retries are separate. On a
first-request success, physical requests equal semantic calls. The sealed
ceiling is four physical requests for a Gemini semantic call (CKey retry,
then equivalent ShopAPI failover and retry) and two for a GPT semantic call
(local gateway retry).

For the one-contrastive baseline, mandatory physical-request ceilings are:

```text
one candidate: 42
one sense / three candidates: 126
five senses / fifteen candidates: 630
```

Automatic Gemini-to-GPT or GPT-to-Gemini fallback is forbidden. Cross-family
movement occurs only through the explicit Secondary Judge or Pairwise Hard
Case semantic roles and is recorded in the ledger.

## Zero-provider fixtures

The machine-readable fixture is:

```text
context_substitution/v2/tests/fixtures/provider_role_plan_gpt_primary_v2.zero_provider.json
self SHA256: 5f28c9a4f869ff45938bf3dd80680c39e4e1d3f1881195056c9d20f2c3b7a334
physical SHA256: b54703b7f8530061927e0bd84869980241ae646f23880498846888bd369f237f
```

It covers one candidate, one sense with three candidates, and the official
five-sense/fifteen-candidate scale. Synthetic senders exercise routing,
indices, retry and failover without opening a network connection.

## Gate evidence

Focused provider-plan, routing and catalog gate:

```text
37 passed
```

Full C gate with official five-sense Dataset and canonical Contracts R2 root:

```text
121 passed
0 skipped
```

Both commands use local synthetic senders or zero-provider projections. No
provider credential is loaded by the V2 routing tests and no network endpoint
is opened. Final JUnit files and their physical hashes are supplied in the
portable review bundle rather than committed as source.

## Status

```text
GPT_PRIMARY_ROLE_PLAN_V2_READY_FOR_INDEPENDENT_REVIEW
NEEDS_REWORK
```

`NEEDS_REWORK` remains the governance state until independent review accepts
the child and Main binds the exact V2 self and physical hashes. No D0 or live
authorization is implied.
