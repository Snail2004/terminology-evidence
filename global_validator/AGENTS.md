# Global Validator Agent Rules

- Ownership is limited to `global_validator/**`.
- `terminology_contracts_v1` is immutable authority.
- Never import producer-internal C/E packages.
- Never read raw datasets at runtime.
- Apply hard gates before scoring.
- Development mode cannot emit `AUTO_APPROVED` or a certificate.
- Frozen mode requires a loaded and verified calibration artifact.
- Stage explicit owned paths only; never use `git add .` or `git add -A`.
