---
task_slug: review-workflow-codex-review
session_id: 07061c78-9c6c-446f-92da-9528d337d892
target_repo: C:/Users/2021670/Documents/멀티 에이전트
write_scope: []
---

# Codex Review Task: Evaluate Two-Pass Review Workflow Implementation

Please conduct a strict technical code review on the implementation of the AI PPT Two-Pass Review Workflow.

## Target Files to Review:
1. `tasks/AI_Powered_PPT/prompts/25_slide_review.md`
2. `tasks/AI_Powered_PPT/src/aippt/adapters/ai_adapter.py`
3. `tasks/AI_Powered_PPT/src/aippt/canvas/app.py`
4. `tasks/AI_Powered_PPT/src/aippt/canvas/static/index.html`
5. `tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js`

## Review Focus & Criteria:
1. **JSON Output Template & Default Value Handling**:
   - Is the JSON schema/template injection in `25_slide_review.md` and `app.py` / `ai_adapter.py` sufficiently explicit?
   - Will workers reliably output JSON adhering to `canvas-ir/1` schema?
   - Are missing fields and defaults handled gracefully by `_finalize_live_ir` in `app.py` and `stateFromIR` in `editor.js`?
2. **Review Model Check & Selector Workflow**:
   - Does the frontend (`index.html`, `editor.js`) correctly toggle and transmit `review` (bool) and `reviewer_model` (str)?
   - Does `api_generate` and `generate_live` in `app.py` correctly handle the two-pass generation when `review=True`?
   - Are errors in the review pass handled gracefully (falling back to initial draft without breaking)?

## Expected Output Format:
Provide a clear, detailed code review report covering:
- **Summary Verdict**: `VERDICT: APPROVE` or `VERDICT: BLOCK` (with reasons)
- **Detailed Evaluation**: Itemized feedback for Scope 1 and Scope 2.
- **Recommendations & Edge Cases**: Any potential issues or edge cases found.
