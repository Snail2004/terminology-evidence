# D2L remaining 100 Stage A package

This namespace prepares the 100 review targets that remain after the accepted
50-sense fast-track release. It is a derived, zero-network review artifact;
it is not a gold dataset and it does not emit final glossary decisions.

## Selection contract

The builder reads the immutable V3 parent and the accepted 50-sense selection.
It selects exactly 100 parent records:

- the 50 selected sense IDs are excluded;
- the original unsplit `in place` parent is excluded because the 50 release
  already contains the two repaired `in place` senses;
- `statistical power` is held out as an unresolved Stage A repair parent.

No source record, candidate, context, hash, or provenance is rewritten. The
derived files are exact parent subsets and every review payload carries the V3
manifest and record hashes.

## Review routing

The package is split into ten batches of ten senses:

- Reviewer 1 receives all 100 Stage A cases;
- Reviewer 2 receives the 65 `R3`/`R4` risk cases;
- `R4` cases require later adjudication;
- clear `R0` cases can be sampled for a later blind audit.

Each handoff ZIP is independent and contains only one reviewer input. Do not
combine reviewer outputs before the intake step. Reviewers fill only the
`review` object and preserve source fields and hashes.

## Build and validate

```powershell
python -B tools/build_remaining100_stage_a.py --output-root <OUTPUT_ROOT>
python -B tools/validate_remaining100_stage_a.py --artifact-root <OUTPUT_ROOT>
python -m unittest discover -s tests -p test_remaining100_stage_a.py
```

The package intentionally contains zero provider calls, zero Stage B labels,
and zero final glossary decisions. A successful structural validation means
`READY_FOR_STAGE_A_RISK_REVIEW`, not human-reviewed or official status.
