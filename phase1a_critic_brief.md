# Codex Critic Review: Phase 1A Implementation

## Context
Claude Main (Opus) has just finished implementing Phase 1A of the Canvas Backend (Canvas IR -> PPTX renderer).
The goal was to implement the JSON schema, validation logic, coordinate geometry, styling engine, connector logic, and the final rendering module `render_canvas.py`, matching the rigorous requirements in `phase1a_brief.md` and `HTML_to_PPTX_Plan.md`.
The automated test suite (`python -m pytest tests/canvas`) has been run by the orchestrator and all 240 tests passed cleanly.

## Files to Review
- `src/aippt/canvas/schema.json`
- `src/aippt/canvas/validate.py`
- `src/aippt/canvas/geometry.py`
- `src/aippt/canvas/style.py`
- `src/aippt/canvas/connectors.py`
- `src/aippt/canvas/render_canvas.py`
- `tests/canvas/test_roundtrip.py`
- `tests/canvas/test_validate.py`
- `tests/canvas/test_geometry.py`

## Your Task (codex-critic)
Review the implementation and verify that all constraints were strictly followed:
1. **Geometry Constraints**: Ensure `intersects(a, b)` uses strict overlap (half-open rule) and `emu(u)` uses `round()`. The stroke bleed must intentionally NOT be included in the bounding box calculation.
2. **Validator Integrity**: Ensure `#4472C4` is explicitly rejected, and control characters (except `\t` and `\n`) are rejected. Ensure `validate.py` raises `CanvasValidationError` accumulating ALL violations.
3. **Style Correctness**: Ensure `set_run_fonts` writes `<a:ea>` via lxml explicitly and `insert_element_before` maintains correct DrawingML schema sequence. Confirm `<p:style>` blocks are stripped from shapes and connectors.
4. **Connector Arrowheads**: Ensure `<a:headEnd>` is appended BEFORE `<a:tailEnd>` in `connectors.py` to prevent PowerPoint corruption.
5. **Pin Checks**: Confirm `render_canvas.py` strictly checks `ir["target"]["template_sha256"]` against the pin and fails fast if stale.
6. **No Spurious Features**: Confirm the code is free of unwanted features (like attempting autofit or modifying external files).

If the implementation meets all requirements and safety constraints, output exactly:
`VERDICT: APPROVE`
Followed by a brief explanation of your verification.
If it fails any constraint, output `VERDICT: REJECT` and detail the exact code lines to fix.

Output your findings to stdout.
