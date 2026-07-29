# Context Substitution provider setup

Committed, non-secret artifacts divide transport from semantic authority:

- `provider_catalog.v1.json` binds adapter, endpoint and credential filename.
- `provider_role_plan.v1.json` is the immutable Gemini-primary V1 replay
  authority.
- `provider_role_plan.gpt_primary.v2.json` is the reviewed GPT-primary policy
  revision selected before D0 for quota balance and cross-family independence.
  It retains the V1 schema and does not reinterpret V1 runs.

Credential values remain outside Git in one `API-Key` directory:

- `CKEY.txt`: primary CKey OpenAI-compatible transport pinned to
  `vuduythanh2023/gemini-3.5-flash`. The tested
  `tranhieu13102003/gemini-3.5-flash` variant is currently permission-denied
  and is not admitted to the automatic route until its access is fixed.
- `GEMINI-KEY.txt`: equivalent ShopAPI Gemini transport (OpenAI-compatible
  Chat Completions endpoint; the model remains `gemini-3.5-flash`).
- `LOCAL-GPT-GATEWAY.txt`: local OpenAI-compatible GPT gateway.

## Sealed V1 replay matrix

| Role | Model/profile | Setting | Automatic transport order |
|---|---|---|---|
| Context selector | Gemini 3.5 Flash | thinking low | CKey, then ShopAPI |
| Trial translator | GPT-5.6 Luna | reasoning none | local gateway only |
| Trial quality gate | Gemini 3.5 Flash | thinking low | CKey, then ShopAPI |
| Primary context judge | Gemini 3.5 Flash | thinking low | CKey, then ShopAPI |
| Contrastive judge | Gemini 3.5 Flash | thinking low | CKey, then ShopAPI |
| Secondary judge | GPT-5.6 Terra | reasoning low | explicit escalation only |
| Pairwise hard case | GPT-5.6 Terra | reasoning medium | explicit escalation only |

CKey and ShopAPI may fail over because they carry the same Gemini model,
generation contract and canonical prompt. ShopAPI uses prompt-only JSON
schema instructions because its OpenAI-compatible capability does not expose
the native Gemini schema dialect. Gemini never automatically falls through to GPT. The
secondary and hard-case GPT calls are separate semantic roles and are recorded
as explicit escalation events.

## Sealed GPT-primary V2 matrix

| Role | Model/profile | Setting | Automatic transport order |
|---|---|---|---|
| Context selector | Gemini 3.5 Flash | thinking low | CKey, then ShopAPI; frozen Dataset selection makes zero calls |
| Trial translator | Gemini 3.5 Flash | thinking low | CKey, then ShopAPI |
| Trial quality gate | GPT-5.6 Luna | reasoning none | local gateway only |
| Primary context judge | GPT-5.6 Terra | reasoning low | local gateway only |
| Contrastive judge | GPT-5.6 Terra | reasoning low | local gateway only |
| Secondary judge | Gemini 3.5 Flash | thinking low | conditional; CKey, then ShopAPI |
| Pairwise hard case | GPT-5.6 Terra | reasoning medium | conditional; local gateway only |

V2 canonical self SHA256 is
`155261fc2c80e54b6e22e266104fa6a5a2040fa6faf4b8d7865bb970a763e815`;
its physical SHA256 is
`6a229435a2d84198dc88bee26c3b4bb5645b7b086849c4f5e1a13217a9152e61`.
Automatic failover remains same-family only. Primary GPT and conditional
secondary Gemini remain in different model families and independence groups.
No comparative V1/V2 provider pilot is claimed; D0 is the first empirical run.

## Zero-provider preflight

Set only the credential root. Model, family, endpoint ordering and retry
overrides named `CST_PROVIDER_*` are rejected for an authorized run.

```powershell
$env:CST_CREDENTIALS_ROOT = '<path-to-API-Key>'
$plan = 'context_substitution/v2/providers/provider_role_plan.gpt_primary.v2.json'
$planSha = (Get-FileHash -Algorithm SHA256 $plan).Hash.ToLowerInvariant()
python -m context_substitution.v2 provider-preflight `
  --provider-role-plan $plan `
  --provider-role-plan-sha256 $planSha
```

Preflight reads the three credential files, verifies adapter dependencies and
the exact physical role-plan hash, performs zero provider calls, and redacts
local credential/catalog paths from its published output.

## Failure behavior

Timeout, connection and malformed structured output failures use the bounded
retry inventory in the role plan. Gemini can then move from CKey to ShopAPI
inside the same equivalence group. Unknown physical outcomes are written as a
hard stop before raising; they are never replayed automatically. Every attempt
records semantic-call, provider-request, route, retry and budget indices.

`context-run` still requires `--allow-api`, the role-plan file and its expected
physical SHA256. Provider order and model identities cannot be supplied from
the command line or environment.
