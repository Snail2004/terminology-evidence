# Consumer Guide: Global Validator

The Global Validator validates both producer packages before assembling
`GlobalValidatorInputV1`.

- Verify exact candidate key, input hash, nested self hashes, and assembly hashes.
- Apply registered hard gates before any calibrated score.
- Respect `FATAL_SPLIT > FATAL_REJECT > ESCALATE_HUMAN > CAP_PROVISIONAL > NONE`.
- Do not auto-approve or emit a certificate reference in development mode.
- In frozen mode, load and verify the actual calibration artifact, registered
  feature names, dataset/gate bindings, model parameters, and threshold.
- Record complete `run_metadata` and replay specification hash.
