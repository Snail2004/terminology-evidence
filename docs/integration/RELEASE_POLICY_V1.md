# Release Policy V1

`system_integration_harness_v1_rc1.zip` is a source/test release artifact. It
must contain only the four owned path families, release metadata and reports.
It must not contain credentials, raw provider credentials, `.pyc`,
`__pycache__`, `.pytest_cache`, or absolute local paths as authority identity.

The RC is integration tooling, not production approval authority. A real pilot
may be reported only when the dependency contract in the architecture document
is satisfied and every source receipt is verified. Missing dependencies are
reported as `REAL_PILOT_NOT_EXECUTED` or `BLOCKED_BY_<DEPENDENCY>`; they are not
fabricated or silently normalized.
