# Context Substitution provider setup

Two committed, non-secret artifacts divide transport from semantic authority:

- `provider_catalog.v1.json` binds adapter, endpoint and credential filename.
- `provider_role_plan.v1.json` binds each semantic role to an exact model,
  generation settings, retry budget and permitted equivalent transport routes.

Credential values remain outside Git in one `API-Key` directory:

- `CKEY.txt`: primary CKey OpenAI-compatible transport pinned to
  `vuduythanh2023/gemini-3.5-flash`. The tested
  `tranhieu13102003/gemini-3.5-flash` variant is currently permission-denied
  and is not admitted to the automatic route until its access is fixed.
- `GEMINI-KEY.txt`: equivalent ShopAPI Gemini transport (OpenAI-compatible
  Chat Completions endpoint; the model remains `gemini-3.5-flash`).
- `LOCAL-GPT-GATEWAY.txt`: local OpenAI-compatible GPT gateway.

## Sealed role matrix

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

## Zero-provider preflight

Set only the credential root. Model, family, endpoint ordering and retry
overrides named `CST_PROVIDER_*` are rejected for an authorized run.

```powershell
$env:CST_CREDENTIALS_ROOT = '<path-to-API-Key>'
$plan = 'context_substitution/v2/providers/provider_role_plan.v1.json'
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
