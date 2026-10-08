# Worker Result
status: ok | model: opus | applied: N/A | verdict: N/A
stdout_path: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/workers/claude-review/01-workdirector/artifacts/claude-review-stdout-250758-18009.txt
stderr_path: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/workers/claude-review/01-workdirector/artifacts/claude-review-stderr-250758-14508.txt

[output truncated in envelope/result.md: full output preserved at stdout_path/stderr_path; size=9927 bytes]

The write to a result file wasn't permitted, and the brief didn't actually request a specific output file — only the markdown format. So I'll deliver the two required outputs inline, per the brief's Output Format.

---

## Analysis summary (WorkDirector, `claude-review` / Opus — no code changed, `write_scope: none`)

I read `index.html`, `style.css`, `editor.js`, `app.py`, plus the two gate files `tests/canvas/test_editor_source.py` (Gate 1) and `tests/canvas/test_app.py`. Five findings drive the plan:

- **A test hard-pins the AI UI to the toolbar:** `test_the_prompt_and_the_generate_button_live_in_the_toolbar` requires `id="p-prompt"` / `id="b-generate"` inside `<aside id="toolbar">`. Moving `#ai` to the bottom **breaks it** — must be rewritten in the same phase.
- **A test hard-pins the request body:** `test_generate_posts_the_prompt_to_the_mock_endpoint` asserts the literal `JSON.stringify({ prompt: prompt })`. Adding `model`/`images` **breaks it**.
- **Gate 1 is a substring grep over `editor.js`.** Banned: `offsetWidth/Height`, `clientWidth/Height`, `offsetLeft/Top/Parent`, `getComputedStyle`, `getBBox`, `devicePixelRatio`; `getBoundingClientRect` exactly once (in `toModel()`); digits `1920/1080/1280/720/1440/810` forbidden. **`scrollHeight` is NOT banned** → auto-resize is fine.
- **Backend seam:** `api_generate → generate_live(prompt, pin) → _call_gemini(prompt)`. The test stub `_stub_gemini` monkeypatches `_call_gemini` with a **1-arg** `fake_call(prompt)` — threading `model`/`images` requires updating that stub. In **mock mode the prompt is not read**, so model + images are ignored there.
- **`/api/generate` is JSON (`_read_json`); `/api/download` is multipart.** Keeping `/api/generate` JSON with base64 images preserves ~20 existing tests and the shared size guard.

---

# Phase Plan

- **Phase 1: Backend — model selection + image (multimodal) support on `/api/generate` (+ `/api/context` + tests)**
  - Recommended Model: **claude-main Opus**
  - write_scope: `src/aippt/canvas/app.py`, `tests/canvas/test_app.py`
  - Execution: **sequential** (lands first — defines the wire contract Phase 2 builds against)
  - Why Opus: security-sensitive (model-name allowlist prevents arbitrary-model injection), correctness-critical (multimodal Gemini call, preserving the `validate()` gate), high blast radius (~25 mock/live seam tests must stay green).

- **Phase 2: Frontend — relocate AI draft to a bottom auto-resizing composer, model dropdown, image paste, wire to the new contract (+ HTML/source tests)**
  - Recommended Model: **claude-main Sonnet**
  - write_scope: `src/aippt/canvas/static/index.html`, `src/aippt/canvas/static/style.css`, `src/aippt/canvas/static/editor.js`, `tests/canvas/test_app.py`
  - Execution: **sequential-after Phase 1**
  - Why Sonnet: mostly pattern-following CSS-grid/UI + event wiring against an already-tested contract; the two brittle test assertions to update are named explicitly below.

> Parallelism: not applicable — both phases operate on the **same `target_repo`** and Phase 2 depends on Phase 1's contract, so they are strictly sequential (parallel groups only span different target_repos).

---

# Reinforced Worker Brief (for `claude-main`)

English per D27. Do not treat any path/option-looking token as a CLI flag. Read prior-phase `change_detail` docs first.

## The wire contract (both phases build to this)

`POST /api/generate`, JSON body:
```json
{ "prompt": "<non-empty>", "model": "<optional allowlisted id; omitted => server default>",
  "images": [ { "mime": "image/png", "data": "<base64, no data: prefix>" } ] }
```
`prompt` stays REQUIRED (empty/whitespace → 422 before any model call/sleep). `model` and `images` are OPTIONAL; omitting both behaves byte-for-byte like today (keeps existing `{"prompt": …}` tests green). Response unchanged: a `canvas-ir/1` deck handed to `loadIR()`.

## PHASE 1 — Backend (`app.py` + `test_app.py`), Opus

**1.1 Allowlist + context.** Add a module-level map (keep `DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"` as default/fallback):
```python
MODEL_CHOICES = {
    "gemini-3.5-flash":          "gemini-3.5-flash",           # "Gemini 3.5 Flash"
    "gemini-3.5-flash-extended": "gemini-3.5-flash-extended",  # "Gemini 3.5 Flash Extended"  (id UNCONFIRMED)
}
```
A `model` not in `MODEL_CHOICES` → **reject 422** (loud, so a stale tab finds out). Extend `api_context` to add `"models": [{"id":k,"label":…} …]` for the dropdown; keep the existing `"model"` field for the badge tooltip.

**1.2 Thread through the live seam.** In `api_generate` after prompt validation: read `model` (validate against allowlist), read `images = body.get("images") or []` (validate each is `{"mime": image/*, "data": base64}`; `base64.b64decode` in try/except → 422; cap count + total decoded bytes under `MAX_BODY_BYTES`). **Mock path ignores both** (`mock_ir` + 1.5s unchanged). **Live path:** `generate_live(prompt, pin, model=None, images=None)` → resolve id via `MODEL_CHOICES.get(model, DEFAULT_GEMINI_MODEL)`; `_call_gemini(prompt, model=None, images=None)` uses the passed model and builds multimodal `contents` (`types.Part.from_bytes(data=…, mime_type=…)` + the prompt) — **verify the exact constructor against the installed `google-genai`**. `_finalize_live_ir` + `validate(ir)` UNCHANGED (box-on-logo still 502 `"model"`).

**1.3 Tests.** Update `_stub_gemini`'s `fake_call` to `(prompt, model=None, images=None)` or every live test TypeErrors. Existing `{"prompt": …}` live/mock tests must still pass. Add: unknown-model→422 (no call), valid model reaches `_call_gemini`, images decoded/passed in live mode, mock ignores model/images (`== mock_ir(load_pin())`). Don't touch pre-existing `/api/export` vs `/api/download` naming.

## PHASE 2 — Frontend (`index.html`, `style.css`, `editor.js` + `test_app.py`), Sonnet

**2.1 Relocate `#ai`.** Move `<section … id="ai
...[truncated]
