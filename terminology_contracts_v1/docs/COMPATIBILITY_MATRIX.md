# Compatibility Matrix

| Producer payload | V1.1 validator | Native issuance | Action |
|---|---:|---:|---|
| Native V1.1 RC2 | Yes | Yes, when complete | Validate and verify bundle |
| V1.0 | Legacy schema only | No | Migrate explicitly |
| Migrated V1.1 evidence | Yes | Evidence only | Preserve bindings |
| Migrated calibration | Inspection only | No | Verify/reseal real artifact |
| Migrated decision | Inspection only | No | Re-run Global Validator |
| Migrated certificate | Inspection only | No | Issue from complete decision |
| Unknown version | No | No | Fail closed |

Migration never fabricates evidence, review hashes, calibration eligibility, or
missing decision/certificate provenance.

V1.0 and migrated V1.1 retain legacy allowlist semantics. New RC2 invariants
apply only to native `COMPLETE` artifacts; migration cannot promote a legacy
artifact to complete authority.
