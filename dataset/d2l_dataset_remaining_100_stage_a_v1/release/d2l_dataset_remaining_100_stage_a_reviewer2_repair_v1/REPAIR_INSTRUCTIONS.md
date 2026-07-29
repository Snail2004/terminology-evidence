# Reviewer 2 targeted repair

Review only the six listed cases. Fill only each `repair` object. If the existing three candidates remain valid and only need to be partitioned across the proposed split senses, set `candidate_set_decision` to `ACCEPT` and keep `candidate_replacements` empty. If candidate wording itself must change, set the decision to `REVISE` and provide at least one source-bound object with `candidate_id`, `candidate_slot`, and `replacement_target_vi`. Do not change any other field. Return only the completed `reviewer_2_repair_input.json`.
