# Codex Critic Review: Phase 3 Prompt-to-PPTX (Mock Mode)

## Context
Claude Main (Opus) has just finished Phase 3.
The goal was to:
1. Add a Mock `/api/generate` endpoint that simulates an AI generator returning `Canvas IR` JSON (with a 1.5s latency).
2. Add a Prompt UI (Textarea + Generate button) that calls this endpoint.
3. Wire the returned JSON directly into the existing `loadIR()` gate, completely avoiding re-implementing any validation logic in the frontend or backend generator itself.

All 421 automated tests (including 30 new Phase 3 tests) have passed flawlessly.

## Files to Review
- `src/aippt/canvas/app.py`
- `src/aippt/canvas/static/index.html`
- `src/aippt/canvas/static/style.css`
- `src/aippt/canvas/static/editor.js`
- `tests/canvas/test_app.py`

## Your Task
Review the implementation and verify that all constraints were strictly followed:
1. **The Mock Engine**: Verify that `/api/generate` does NOT call any external API (`openai`, `anthropic`, `httpx` outside of standard FastAPI tools etc.) and returns the mock IR.
2. **The Validation Gate**: Verify that `editor.js` strictly calls `loadIR(ir)` when it receives the payload, rather than attempting to bypass the `illegalReason()` gate or doing unsafe DOM mutation.
3. **Undo/Redo Integrity**: Verify that generating a new deck correctly replaces the whole stage and pushes exactly ONE valid `undo` step, mirroring the file-import logic.

If the implementation meets all requirements and safety constraints, output exactly:
`VERDICT: APPROVE`
Followed by a brief explanation.

If it fails any constraint, output `VERDICT: REJECT` and detail the exact code lines to fix.

Output your findings to stdout.
