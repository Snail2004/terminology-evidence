# V1.0 to V1.1 migration

`v1_0_0_to_v1_1_0.py` is the explicit compatibility bridge. It preserves
candidate identity and producer evidence, adds V1.1 provenance/default fields,
and recomputes nested and outer self hashes.

Migrated Frozen Candidate, gate set, Global Input, calibration, decision, and
certificate payloads are marked incomplete where V1.0 did not contain enough
binding data. They can be stored and inspected
with `--allow-legacy-migration`, but cannot open native V1.1 frozen issuance.

```powershell
python migrations/v1_0_0_to_v1_1_0.py source.json target.json report.json
```

Running the migration on an already-V1.1 payload is rejected explicitly.
Migration never invents a native Frozen Candidate content binding or constraint
evidence. Verified producers must build a new native-complete envelope.
