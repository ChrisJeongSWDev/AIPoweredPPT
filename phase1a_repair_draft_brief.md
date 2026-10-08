# Phase 1A Repair Brief (Iteration 1)

## Context
Claude Main (Opus) implemented Phase 1A successfully (240 tests passed), but Codex Critic REJECTED the implementation due to a violation of the requirement: "validate.py must raise CanvasValidationError accumulating ALL violations."

## Critic Feedback
`validate()` does not accumulate all violations:
- `src/aippt/canvas/validate.py:80-89` short-circuits stale canvases and separates schema and semantic validation.
- `src/aippt/canvas/validate.py:95-100` raises schema errors before semantic checks can run.
- `src/aippt/canvas/validate.py:231-232` raises semantic errors separately.
- `tests/canvas/test_validate.py:114-125` explicitly expects other detectable violations to be suppressed.

For example, a zero-width element combined with a separate `#4472C4` element reports only the schema error. Refactor the validation stages to return problem lists and raise one aggregated `CanvasValidationError`; update the short-circuit test and add mixed schema-plus-semantic coverage.

## Your Task (claude-review)
1. Read `src/aippt/canvas/validate.py` and `tests/canvas/test_validate.py`.
2. Analyze the critic's feedback.
3. Write a reinforced `phase1a_repair_brief.md` targeting Claude Main (Opus). 
   - Instruct Claude Main to refactor `validate()` so that schema validation and semantic validation run regardless of whether the other fails, and ALL errors are aggregated into a single `CanvasValidationError`.
   - Update the tests to expect the aggregated error list, and add a test case for mixed schema + semantic errors as the critic suggested.
   - Set the `write_scope` to `src/aippt/canvas/validate.py, tests/canvas/test_validate.py`.
   - Set `claude_model: opus` and `mode: continuation` in the frontmatter.

Output ONLY the reinforced brief text in markdown format. Do not try to save it to a file, just output it in your response so the orchestrator can copy it.
