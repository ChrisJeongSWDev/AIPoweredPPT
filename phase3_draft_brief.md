# Phase 3: AI Prompt-to-PPTX (Mock Mode)

## Goal
Add a prompt input UI and a mock generation backend to simulate AI-powered PPTX creation, ensuring the entire architecture is ready for a real LLM.

## Requirements

### 1. Frontend (`index.html`, `style.css`, `editor.js`)
- Add a text input area (e.g. textarea) and a "Generate (✨)" button to the UI (e.g. at the bottom of the editor or inside the left toolbar).
- When the button is clicked, show a loading state, and send a `POST` request to `/api/generate` with `{ "prompt": "<user text>" }`.
- On success, pass the returned `Canvas IR` JSON to the existing `loadIR(json)` function.
- `loadIR()` already handles all validation, so no new validation logic is needed here.

### 2. Backend (`src/aippt/canvas/app.py`)
- Add a new route: `@app.post("/api/generate")`
- This endpoint must return a **Mock `Canvas IR` JSON** (a hardcoded payload that successfully passes validation).
- The mock payload should be a visually pleasing arrangement of 3-4 shapes (e.g., a "Q3 Marketing Strategy" summary with a few text boxes and connecting arrows) demonstrating that the backend can send valid IR based on the schema.
- Wait `1.5 seconds` (using `asyncio.sleep(1.5)`) before returning the response to simulate network latency and test the frontend's loading state.

## Rules for claude-review
- Ensure the new `/api/generate` endpoint returns a valid schema payload (template SHA must match the active server context, layout_index=3, etc. You can dynamically inject the active `template_sha256` into the mock payload).
- Do not use external APIs.
- Append the standard YAML metadata block at the end:
```yaml
---
claude_model: opus
mode: continuation
target_repo: .
change_detail_path: tasks/AI_Powered_PPT/phase3_change_detail.md
write_scope: src/aippt/canvas/static/index.html, src/aippt/canvas/static/editor.js, src/aippt/canvas/static/style.css, src/aippt/canvas/app.py, tests/canvas/test_app.py
```
