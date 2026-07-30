# Narrow high-risk proposal repair

Repair every case using only the supplied source payload and audit. Edit only each `repair` object. Keep `repair.revised_proposal` as a complete proposal, preserve temporary child IDs, and retain an exact one-time partition of source candidates and contexts. Change only the child fields identified by the audit, set `repair_status` to `COMPLETE`, and explain the change in `repair_notes`. Synthetic or boundary-only contexts are never positive evidence. Do not add Stage B gold, ranks, winners, or final glossary decisions. Return the completed JSON file only.
