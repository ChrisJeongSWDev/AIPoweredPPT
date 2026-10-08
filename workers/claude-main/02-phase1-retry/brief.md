---
target_repo: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT
write_scope:
  - tasks/AI_Powered_PPT/src/aippt/canvas/app.py
  - tasks/AI_Powered_PPT/tests/canvas/test_app.py
claude_model: sonnet
reviewer: codex-critic
change_detail_path: tasks/AI_Powered_PPT/workers/claude-main/02-phase1-retry/change_detail.md
---

# Phase 1 Worker Brief: Backend Model Selection & Multimodal Support (Retry)

You are `claude-main` (Sonnet). Your task is to implement the backend changes in `app.py` and update the corresponding unit tests in `test_app.py` for model selection and multimodal support.

## 1. Objectives

1. **Model Choices Allowlist:**
   - Define a map `MODEL_CHOICES` in `src/aippt/canvas/app.py` containing:
     - `"gemini-3.5-flash"`: `"gemini-3.5-flash"`
     - `"gemini-3.5-flash-extended"`: `"gemini-3.5-flash-extended"`
   - Set a fallback default `DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"`.
   - Reject `/api/generate` requests with model names not in `MODEL_CHOICES` with a `422 Unprocessable Entity` status code.

2. **Extend `api_context`:**
   - Modify the `/api/context` endpoint in `app.py` to return the available models list in the JSON response.
   - Example response payload structure update:
     ```json
     {
       "model": "gemini-3.5-flash",
       "models": [
         {"id": "gemini-3.5-flash", "label": "Gemini 3.5 Flash"},
         {"id": "gemini-3.5-flash-extended", "label": "Gemini 3.5 Flash Extended"}
       ]
     }
     ```

3. **Thread model and images in `/api/generate`:**
   - Read `model` and `images` from the JSON request body.
     - `images` will be a list of dicts: `[{"mime": "image/png", "data": "<base64_string>"}]`.
   - Validate base64 data for each image. If base64 decoding fails, reject with `422`.
   - Thread `model` and `images` parameter to `generate_live(prompt, pin, model=None, images=None)` and then to `_call_gemini(prompt, model=None, images=None)`.
   - Keep mock mode logic intact (mock path must ignore `model` and `images` to maintain compatibility).

4. **Live Multimodal Gemini Call:**
   - In `_call_gemini(prompt, model=None, images=None)`, build the multimodal query payload.
   - If images are provided:
     - Import and use the exact `google-genai` SDK objects (check how `client.models.generate_content` is called or constructed).
     - Construct parts: `types.Part.from_bytes(data=decoded_bytes, mime_type=mime_type)` for each image and combine with the text prompt.
     - Pass the model resolved from `MODEL_CHOICES.get(model, DEFAULT_GEMINI_MODEL)`.

5. **Update Test Stub:**
   - In `tests/canvas/test_app.py`, update `_stub_gemini`'s `fake_call(prompt)` signature to `fake_call(prompt, model=None, images=None)` to prevent TypeErrors in other tests.

6. **Add Backend Tests:**
   - Add new tests in `tests/canvas/test_app.py` verifying:
     - Invalid model rejection (returns 422).
     - Valid model parameter threads through to `_call_gemini`.
     - Valid images are decoded and passed to `_call_gemini`.
     - Mock mode ignores model and images.

## 2. Requirements & Constraints
- Do not modify files outside the `write_scope`.
- Preserve existing tests and code formatting.
- Ensure all tests pass.
- Write your analysis in English.
