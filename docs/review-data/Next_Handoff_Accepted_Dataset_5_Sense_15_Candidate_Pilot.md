# NEXT HANDOFF — ACCEPTED DATASET 5-SENSE / 15-CANDIDATE PILOT

## Accepted Dataset pins

```text
ZIP SHA-256:
9b6a9ee1272b6403054b61f5399d4391328d1d2d8a964b1102af0a2656bc2738

Manifest self SHA-256:
16bd2b9c7a974bdccfb977384fa1a35381e6e810c110f489f31d1606398ce2f5
```

Status:

```text
ACCEPTED_FOR_REAL_ZERO_NETWORK_PILOT
```

## Main

1. Record the exact Dataset producer Git commit/path scope.
2. Store this independent review beside the exact Dataset artifact.
3. Pin the ZIP and manifest hashes in the integration run specification.
4. Record the one-test packaged JUnit as an internal build gate, not the 8-test
   suite.
5. Do not alter or rebuild the accepted Dataset artifact before downstream use.

## Agent C

Consume exactly:

```text
5 Effective Sense contracts
15 Frozen Candidate contracts
15 Constraint Evidence packages
```

Produce 15 official C packages using the accepted Dataset identities. Return a
sealed zero-provider release for independent review.

## Agent E

Consume the same exact Dataset identities.

Use only the approved controlled Vietnamese registry. If registry evidence is
not ready, emit explicit HOLD states rather than fabricated attestation.

Produce 15 official E packages or an exact per-candidate external-input HOLD
report.

## System Integration Harness

Preflight the accepted Dataset package and pin its exact ZIP/manifest hashes.

Do not run the final 15-candidate Global integration until:

```text
15 C packages are accepted
15 E packages or allowed explicit E HOLD packages are accepted
all exact joins pass
```

Final development-mode invariants:

```text
0 AUTO_APPROVED
0 certificates
0 provider/network calls
15/15 replay PASS
```
