---
target_repo: tasks/AI_Powered_PPT
write_scope:
  - src/aippt/canvas/static/editor.js
  - src/aippt/canvas/app.py
  - src/aippt/adapters/ai_adapter.py
claude_model: sonnet
change_detail_path: tasks/AI_Powered_PPT/workers/change_detail.md
---

# NightWorker Repair Brief

You are acting as the `claude-main` worker in a NightWorker loop. Your task is to repair the AI-Powered PPT generation workflow based on a recent architectural review.

## Requirements

1. **Frontend to Backend Trigger (`editor.js`)**:
   - The UI contains a `<select id="p-model">` drop-down (in `index.html`).
   - Modify `editor.js` to read the value of this `#p-model` drop-down.
   - Include the selected model in the JSON payload sent to `POST /api/generate` (e.g., `{ "prompt": promptText, "model": selectedModel }`).
   - Ensure that the Generate button remains disabled during generation.

2. **Worker Execution & JSON Delivery (`app.py`, `ai_adapter.py`)**:
   - In `app.py` (`api_generate`), the `model` field should now be properly received and resolved using `_resolve_profile()`.
   - Ensure `generate_live()` passes the correct profile to `CliWorkerClient`.
   - If `generate_live()` currently uses `complete_json` on a single massive schema which causes a 300s timeout, refactor it to safely generate or ensure `CliWorkerClient` is instantiated with the right `backend` and `model` from the profile.
   - Ensure that image attachments are passed through if possible, or gracefully ignored if unsupported, without breaking the CLI integration.

3. **Slide Generation Workflow**:
   - Ensure the JSON generated and returned by `generate_live()` adheres to the `canvas-ir/1` schema and is compatible with `loadIR()` on the frontend.
   - The architectural flow is: Generate (creates JSON for UI Canvas) -> Export (serializes UI Canvas to JSON -> Python `render()` -> PPTX). Ensure this handoff is fully preserved without data loss.

## Instructions
- Edit the files listed in the `write_scope`.
- You MUST write a detailed Change Detail Log explaining your changes in the result output.
- Do NOT write to any files outside the `write_scope`.
