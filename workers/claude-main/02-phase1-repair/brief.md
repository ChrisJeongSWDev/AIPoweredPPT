---
target_repo: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT
write_scope:
  - src/aippt/canvas/app.py
  - tests/canvas/test_app.py
claude_model: sonnet
reviewer: codex-critic
change_detail_path: tasks/AI_Powered_PPT/workers/claude-main/02-phase1-repair/change_detail.md
---

# Phase 1 Worker Brief: Backend Model Selection & Multimodal Support (Repair)

You are `claude-main` (Sonnet). Your task is to implement the backend changes in `app.py` and update the corresponding unit tests in `test_app.py` for model selection and multimodal support.

**CRITICAL FIX REQUIRED (codex-critic BLOCK verdict):**
Your previous attempt was BLOCKED for the following reasons:
1. `test_app.py` changes were omitted or incomplete. Existing `fake_call(prompt)` conflicts with the new keyword call `_call_gemini(..., model=model, images=images)`, causing live tests to raise `TypeError`. **You MUST update the test stubs and add new Phase 1 tests.**
2. `_decode_images` only catches `binascii.Error`, but non-ASCII base64 strings can raise `ValueError`, producing a 500 server error instead of the required 422. **You MUST catch `ValueError` (or generically) to ensure a 422 Unprocessable Entity response.**

## 1. Objectives

1. **Model Choices Allowlist:**
   - Define a map `MODEL_CHOICES` in `src/aippt/canvas/app.py` containing `"gemini-3.5-flash"` and `"gemini-3.5-flash-extended"`.
   - Set a fallback default `DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"`.
   - Reject `/api/generate` requests with model names not in `MODEL_CHOICES` with a `422 Unprocessable Entity` status code.

2. **Extend `api_context`:**
   - Modify the `/api/context` endpoint in `app.py` to return the available models list in the JSON response: `[{"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash"}, {"id": "gemini-3.5-flash-extended", "label": "Gemini 3.5 Flash Extended"}]`

3. **Thread model and images in `/api/generate`:**
   - Read `model` and `images` from the JSON request body.
   - Validate base64 data for each image. If base64 decoding fails (`binascii.Error`, `ValueError`), reject with `422`.
   - Thread `model` and `images` to `generate_live(prompt, pin, model=None, images=None)` and then to `_call_gemini(prompt, model=None, images=None)`.
   - Mock mode logic must ignore `model` and `images`.

4. **Live Multimodal Gemini Call:**
   - In `_call_gemini`, build the multimodal query payload.
   - If images are provided: construct `types.Part.from_bytes(data=decoded_bytes, mime_type=mime_type)` for each image and combine with the text prompt.

5. **Update Test Stub (CRITICAL):**
   - In `tests/canvas/test_app.py`, update `_stub_gemini`'s `fake_call(prompt)` signature to `fake_call(prompt, model=None, images=None)` to prevent TypeErrors in tests.

6. **Add Backend Tests:**
   - Add new tests in `tests/canvas/test_app.py` verifying:
     - Invalid model rejection (returns 422).
     - Valid model parameter threads through to `_call_gemini`.
     - Valid images are decoded and passed to `_call_gemini`.
     - Invalid base64 strings return 422.

## 2. Requirements & Constraints
- Do not modify files outside the `write_scope`.
- Preserve existing tests and code formatting.
- Ensure all tests pass.
- Write your analysis in English.
