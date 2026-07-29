# Context Substitution provider setup

`provider_catalog.v1.json` is the single non-secret source for route order,
adapter, model, endpoint, timeout, retry count, and credential filename.
Credential values must remain outside Git in one `API-Key` directory.

## Credential files

- `GEMINI-KEY.txt`: ShopAPI
- `CKEY.txt`: CKey
- `LOCAL-GPT-GATEWAY.txt`: OpenAI-compatible local gateway

Point the runtime at that directory once:

```powershell
$env:CST_CREDENTIALS_ROOT = '<path-to-API-Key>'
python -m context_substitution.v2 provider-preflight
```

The preflight reads and validates the three credential files but performs zero
provider calls and never prints credential values.

## Fast overrides

The committed catalog remains the default. A local run can change settings
without editing source files:

```powershell
$env:CST_PROVIDER_SHOPAPI_MODEL = 'gemini-3.5-flash'
$env:CST_PROVIDER_SHOPAPI_MAX_ATTEMPTS = '2'
$env:CST_PROVIDER_CKEY_MODEL = 'gemini-3.5-flash'
$env:CST_PROVIDER_GATEWAY_MODEL = 'gpt-5.5'
$env:CST_PROVIDER_GATEWAY_BASE_URL = 'http://localhost:8317/v1'
```

When changing model families, also set the matching
`CST_PROVIDER_<NAME>_MODEL_FAMILY` and
`CST_PROVIDER_<NAME>_INDEPENDENCE_GROUP` values so audit and independence
metadata remain truthful. Base URL and retry-count variables follow the same
`CST_PROVIDER_<NAME>_BASE_URL` and `CST_PROVIDER_<NAME>_MAX_ATTEMPTS` pattern.

Repeat `--provider` to choose or reorder routes for one invocation:

```powershell
python -m context_substitution.v2 provider-preflight `
  --provider gateway --provider shopapi --provider ckey
```

## Failure behavior

Each route receives a bounded number of attempts. Timeout, connection, and
malformed structured output failures retry the same route before failover.
Authentication, quota, and rate-limit failures move directly to the next
route. Unknown failures stop immediately so an ambiguous provider outcome is
not silently replayed. `context-run` still requires explicit `--allow-api`.
