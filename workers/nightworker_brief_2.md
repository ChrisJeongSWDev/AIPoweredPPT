---
target_repo: tasks/AI_Powered_PPT
write_scope:
  - src/aippt/canvas/static/editor.js
  - src/aippt/canvas/app.py
  - src/aippt/adapters/ai_adapter.py
claude_model: sonnet
change_detail_path: tasks/AI_Powered_PPT/workers/change_detail.md
---

# NightWorker Repair Brief - Iteration 2

You are acting as the `claude-main` worker in a NightWorker loop. Your task is to repair the AI-Powered PPT generation workflow based on a recent architectural review, and address the WARNING raised by Codex Review in the previous iteration.

## Previous Iteration Codex Review Feedback
```
VERDICT: WARNING
The request correctly sends the selected profile ID, and the server independently validates it against `MODEL_PROFILES`.
Issue: after generation, the UI status still displays `CONTEXT.model`, which is the server default profile—not the profile sent in this request. Selecting Opus or a GPT profile can therefore report “from Claude Sonnet 5.” The model picker also remains enabled while a request is in flight.
```

## Requirements

1. **Frontend to Backend Trigger (`editor.js`)**:
   - The UI contains a `<select id="p-model">` drop-down (in `index.html`).
   - Modify `editor.js` to read the value of this `#p-model` drop-down.
   - Include the selected model in the JSON payload sent to `POST /api/generate` (e.g., `{ "prompt": promptText, "model": selectedModel }`).

2. **UI State & Feedback Fixes (`editor.js`)**:
   - Ensure that the model picker dropdown (`#p-model`) is disabled during generation (in flight) alongside the Generate button.
   - Update the UI status text (e.g., `setStatus(...)`) after generation to display the actual selected profile ID rather than hardcoding `CONTEXT.model`.

3. **Worker Execution & JSON Delivery (`app.py`, `ai_adapter.py`)**:
   - The backend `_resolve_profile()` logic is already correct. Do not modify backend files unless absolutely necessary.
   - Ensure the JSON returned by `generate_live()` adheres to the `canvas-ir/1` schema.

## Instructions
- Edit the files listed in the `write_scope`.
- You MUST write a detailed Change Detail Log explaining your changes in the result output.
- Do NOT write to any files outside the `write_scope`.
