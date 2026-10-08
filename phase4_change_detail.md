# Phase 4 — live Gemini author — change detail (APPLIED)

Mode: continuation. All edits below were written to disk successfully in this session. The 5
files in `write_scope` were changed exactly as specified. `style.css` (brief §4) is **out of
write_scope** and was intentionally **not** modified — see "Out-of-scope / caveats" at the end.

Target files (all under `tasks/AI_Powered_PPT/`):
- `src/aippt/canvas/app.py`
- `src/aippt/canvas/static/index.html`
- `src/aippt/canvas/static/editor.js`
- `requirements.txt`
- `tests/canvas/test_app.py`

---

## 1) `src/aippt/canvas/app.py`

**a. `import os`** added to the stdlib block (between `import logging` and `import re`).

**b. Module docstring** — the `/api/generate` paragraph was rewritten from "IS A MOCK" to the
two-mode (mock without a key, live Gemini with one) description. Text-only; no test depends on it.

**c. Phase-4 module constants + exception** added after the `_UNSAFE_STEM` block, before `lifespan`:
- `DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"`
- `PROMPT_PATH = Path(__file__).resolve().parents[3] / "Gemini_Web_Prompt.md"`
  (verified: `parents[3]` = project root `AI_Powered_PPT`, where `Gemini_Web_Prompt.md` exists)
- `class GeminiError(RuntimeError)` — upstream-failure sentinel; deliberately not a
  `CanvasValidationError` (502 vs 422).

**d. `/api/context`** — two keys appended to the returned dict: `"mode": server_mode()` and
`"model": gemini_model() if server_mode() == "live" else None`.

**e. `api_generate`** rewritten to dual-mode:
- Empty/missing prompt → 422 **before** any model call or sleep (unchanged behaviour).
- `gemini_api_key() is None` → the Phase-3 mock path verbatim (validate → sleep 1.5s → return).
- Key present → `generate_live(prompt.strip(), pin)`; `GeminiError` → 502 `{"error":"generate"}`;
  the assembled deck then runs the real `validate()`, and a `CanvasValidationError` →
  502 `{"error":"model"}`.

**f. Live-author helpers** added after `_too_large()` (before `content_disposition()`):
`gemini_api_key()` (whitespace-only key treated as absent), `gemini_model()`, `server_mode()`,
`system_instruction()` (reads `PROMPT_PATH`, `OSError`→`GeminiError`), `_strip_code_fence()` with
`_FENCE_OPEN`/`_FENCE_CLOSE`, `_finalize_live_ir()` (overwrites schema/canvas/target from the live
pin; the model is never trusted with them), `_call_gemini()` (THE network seam — lazy `google.genai`
import, `ImportError`→`GeminiError`, SDK exceptions folded into one `GeminiError`, empty response
guarded), and `generate_live()` (calls the seam, strips a fence, `json.loads`, finalizes).

Invariants preserved for the existing Phase-3 grep tests: `"asyncio.sleep(MOCK_LATENCY_S)"` is still
present; no SHA literal is added; the only new import lines are `os` (stdlib) and the lazy
`from google import genai` / `from google.genai import types` **inside** `_call_gemini` — none of
`httpx/aiohttp/openai/anthropic/urllib.request/socket/requests` appear.

## 2) `src/aippt/canvas/static/index.html`

`#ai` section: badge given `id="ai-mode"` + `title`, added `<button id="b-paste">Paste Gem JSON</button>`,
gave the first hint `id="ai-hint"`, and added a second hint about pasting Web-Gem JSON.

## 3) `src/aippt/canvas/static/editor.js`

- Added `stripFence()`, `pasteGemJSON()` (clipboard → `stripFence` → `JSON.parse` → `loadIR` →
  `pushUndo`, with graceful warnings for no-clipboard / refused-access / empty / non-JSON / refused
  deck), wired `$('b-paste').addEventListener('click', pasteGemJSON)`, and added `applyMode(mode,
  model)` — all inserted right after the existing `$('b-generate')…` wiring.
- `loadContext()`: `applyMode(CONTEXT.mode, CONTEXT.model)` called immediately after
  `CONTEXT = await res.json();`.
- `generate()` success status made mode-aware (`from <model>.` when live, else the MOCK message).

Gate 1 safety: none of the added tokens are on the banned lists; the
`$('b-generate').addEventListener('click', generate)` string is intact.

## 4) `requirements.txt`

Added an active Phase-4 section with `google-genai>=0.3.0` (documented OPTIONAL at runtime; lazy
import; also the `ai` extra).

## 5) `tests/canvas/test_app.py`

Appended the Phase-4 block: `import aippt.canvas.app as appmod`, `_LIVE_DECK`, `_stub_gemini`
(monkeypatches `appmod._call_gemini`), and 10 tests covering context mode/model, blank-key handling,
pin injection + no-sleep, live export, fence tolerance, bad-JSON 502, upstream 502, on-logo 502
(`error == "model"`, detail contains `HEADER_RESERVED`), immediate 422 with no model call, and the
key-absent mock fallback. Env is set per-test via `monkeypatch`, so the module-scoped Phase-3 tests
and the `generated` fixture see no key and are untouched.

---

## Verification plan (NOT executed — see caveat)

```
pip install -e ".[editor,dev]"     # google-genai NOT required for the suite (seam is mocked)
python -m pytest tests/canvas/test_app.py -q
```

## Out-of-scope / caveats

1. **`style.css` (brief §4) NOT applied.** `style.css` is absent from `write_scope`, so the green
   `#ai h2 .tag.live { background:#e6f4ea; color:#137333; }` rule was intentionally skipped. This is
   cosmetic only: `applyMode` still adds the `.live` class and swaps the badge text/tooltip; without
   the rule the live badge simply keeps the default grey styling. No test checks the CSS. To finish
   the visual polish, add that one rule after the `#ai h2 .tag { … }` block.
2. **Suite not run.** The session permission layer denied all command execution (`pytest`,
   `py_compile`) for this non-interactive worker. Edits were verified by re-reading the applied
   regions against the real current source, and the validator was confirmed to emit
   `intersects HEADER_RESERVED`. The changes should be run through the plan above before merge.
3. **Assumptions** (brief was silent): `target`/`schema`/`canvas` are enforced from the live pin;
   live failures are 502 (upstream/model) vs the user's 422; the assembled deck is validated
   server-side before return; default model `gemini-2.5-flash` overridable via `GEMINI_MODEL`; the
   `Gemini_Web_Prompt.md` vs canvas-default brand-red mismatch (`#E63312` vs `#FF0032`) is left
   as-is (both are legal, neither is the forbidden `#4472C4`).
