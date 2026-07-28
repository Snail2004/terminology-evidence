# Consumer Guide: Global Validator

The Global Validator validates both producer packages before assembling
`GlobalValidatorInputV1`.

- Verify exact candidate key, input hash, nested self hashes, and assembly hashes.
- Verify the canonical Frozen Candidate binding and consume only the serialized
  sense/polysemy/collision constraint package; do not read raw dataset state.
- Apply registered hard gates before any calibrated score.
- Respect `FATAL_SPLIT > FATAL_REJECT > ESCALATE_HUMAN > CAP_PROVISIONAL > NONE`.
- Do not auto-approve or emit a certificate reference in development mode.
- In frozen mode, load and verify the actual calibration artifact, registered
  feature mappings, exact feature-key set, logistic parameters, and threshold.
- Reassemble the feature vector from Global Input, recompute the score, and
  derive the decision from score plus gate precedence.
- Record complete `run_metadata`; its replay hash covers all inputs, features,
  gates, engine, run specification, and execution configuration.
