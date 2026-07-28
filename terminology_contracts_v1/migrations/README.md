# V1.0 to V1.1 migration

`v1_0_0_to_v1_1_0.py` is the explicit compatibility bridge. It preserves
candidate identity and producer evidence, adds V1.1 provenance/default fields,
and recomputes nested and outer self hashes.

Migrated calibration, decision, and certificate payloads are marked incomplete
where V1.0 did not contain enough provenance. They can be stored and inspected
with `--allow-legacy-migration`, but cannot open native V1.1 frozen issuance.

```powershell
python migrations/v1_0_0_to_v1_1_0.py source.json target.json report.json
```

Running the migration on an already-V1.1 payload is rejected explicitly.
