# Codex Critic Review: Phase 1B Implementation

## Context
Claude Main (Opus) has just finished implementing Phase 1B: Frontend DOM-to-IR Adapter.
The goal was to build `app.py` (FastAPI), `index.html`, `style.css`, and `editor.js` to create a visual editor matching `HTML_to_PPTX_Plan.md` Section 5.
The automated test suite (`python -m pytest tests/canvas`) has been run by the orchestrator and all 302 tests passed cleanly.

## Files to Review
- `src/aippt/canvas/app.py`
- `src/aippt/canvas/static/index.html`
- `src/aippt/canvas/static/editor.js`
- `src/aippt/canvas/static/style.css`
- `tests/canvas/test_editor_source.py`
- `tests/canvas/test_app.py`

## Your Task (codex-critic)
Review the implementation and verify that all constraints were strictly followed:
1. **The Prime Directive**: Ensure `getBoundingClientRect` occurs EXACTLY ONCE across the entire JS codebase, specifically inside `toModel()`. No other DOM measurement APIs (e.g. `offsetWidth`, `getComputedStyle`, `event.rect`) may be used.
2. **Zoom Inversion**: Verify that all `deltaRect` values from dragging are divided by `zoom`.
3. **Template Pin Checks**: Ensure `app.py` calls `load_pin()` and `verify_pin()` at startup, and provides `template_sha256` via `/api/context` so the editor does not hardcode the SHA.
4. **Reserved Regions**: Confirm `HEADER_RESERVED` and `FOOTER_RESERVED` boundaries are correctly ported and strictly enforced in the JS.
5. **Inline SVG**: Confirm shapes use inline `<svg>` with `stroke-width` correctly applied without clipping (`overflow: visible`).
6. **No EMU Math in JS**: Ensure `12700` does not appear in JS; all math must be in logical units (1 pt).

If the implementation meets all requirements and safety constraints, output exactly:
`VERDICT: APPROVE`
Followed by a brief explanation of your verification.
If it fails any constraint, output `VERDICT: REJECT` and detail the exact code lines to fix.

Output your findings to stdout.
