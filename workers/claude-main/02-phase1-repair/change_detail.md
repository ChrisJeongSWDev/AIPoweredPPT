# Phase 1 (claude-main) — Backend Model Selection & Multimodal Support — change detail (REPAIR, APPLIED)

Mode: repair of a codex-critic BLOCK. Per [[ai-powered-ppt-phase-worker-pattern]] and the identical
precedent in `02-phase1/change_detail.md` and `02-phase1-retry/change_detail.md`, this session's own
temp brief (`C:\Users\2021670\AppData\Local\Temp\tmp.lmTfaVdCG8`) named
`target_repo: /c/Users/2021670/.ma-stg/stg.lXn3qHPE` — a **different** staged worktree from either
prior attempt (`stg.WoNR5MPc`, `stg.qT7gki2q`) — not the outer-tree `target_repo` this directory's own
`brief.md` names. The temp brief's `target_repo` was followed literally; this doc is filed in the
OUTER tree at the canonical `change_detail_path` both on-disk briefs name, matching every prior
phase's convention.

Target files (both under `stg.lXn3qHPE/tasks/AI_Powered_PPT/`):
- `src/aippt/canvas/app.py`
- `tests/canvas/test_app.py`

---

## Why this is a repair, and what the two prior attempts actually left behind

Neither prior attempt's edits ever reached the outer tree: `02-phase1` ended `review_verdict: "BLOCK"`
(a write_scope-violation false positive per `02-phase1-retry`'s analysis), and `02-phase1-retry` ended
`REVIEW_ERROR` ("Review gate decision aborted by user. Target repo was not modified."). So, despite
both sessions independently implementing essentially the same Phase 5 design and writing it to their
own (different, now-discarded) staged worktrees, **the outer tree's `app.py`/`test_app.py` were still
exactly at the pre-Phase-5 baseline** when this session started — confirmed by reading both files in
the outer tree and finding them byte-identical to `stg.lXn3qHPE`'s pre-edit copies. This brief's own
"CRITICAL FIX REQUIRED" section names two defects that trace directly to `02-phase1`'s original diff
(preserved in `02-phase1/result.json`'s `diff` field):

1. **`test_app.py` was never updated in a run that actually landed.** `02-phase1-retry`'s change_detail
   claims the stub fix and 8 new tests were written, but that session's target worktree was abandoned
   (`REVIEW_ERROR`) before anything could be reviewed or merged, so as far as the outer tree and any
   real review are concerned this was never done. Redone fresh here, in `stg.lXn3qHPE`.
2. **`_decode_images` only caught `binascii.Error`.** Confirmed directly in `02-phase1/result.json`'s
   diff (`except binascii.Error as exc:`, no `ValueError`) and independently in `02-phase1-retry`'s
   change_detail point 5, which documents the identical narrower catch. Both prior attempts share this
   bug. Fixed in this session — see below.

## `tests/canvas/test_app.py` did not exist in the staged worktree

Same finding as both prior attempts: only `src/aippt/canvas/app.py` existed under
`stg.lXn3qHPE/tasks/AI_Powered_PPT/`; there was no `tests/` directory. Created `tests/canvas/` with a
plain filesystem `mkdir`/`cp` of the outer tree's current `tests/canvas/test_app.py` (1636 lines,
confirmed with `wc -l` on both sides before editing), then applied the edits below on top with `Edit`.
Plain filesystem `Bash` (`mkdir`, `cp`, `wc -l`) ran unprompted on the staged path this session, same
as `02-phase1-retry` found; `Edit` also ran unprompted on both target files every time. `python`/`awk`
invocations (both a bare `ast.parse` syntax check and a line-length `awk`) came back "This command
requires approval" with no prompt able to surface, on both the staged path and the outer tree — command
execution stayed unavailable this session, consistent with every prior phase in this family. See
[[worker-brief-session-execution-constraints]].

---

## `src/aippt/canvas/app.py`

1. Added `import base64`, `import binascii` (alphabetical, next to the existing stdlib block).
2. Added `MODEL_CHOICES: dict[str, str]` right after `DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"`
   (Phase 4, unchanged): `{"gemini-3.5-flash": "gemini-3.5-flash", "gemini-3.5-flash-extended":
   "gemini-3.5-flash-extended"}` — an id-to-id allowlist; membership (`in MODEL_CHOICES`) is the
   request-side check, and once validated the id IS what the SDK is called with.
3. Added `MODEL_LABELS: dict[str, str]` alongside it — an addition beyond the brief's literal
   `MODEL_CHOICES` spec, needed because `/api/context`'s example payload wants a human `"label"` per
   model and `MODEL_CHOICES` itself only maps id -> id. Same two-dict shape both prior attempts used;
   not flagged as a defect by either BLOCK/REVIEW_ERROR outcome, so kept as-is rather than redesigned.
4. `api_context()`: added `"models": [{"id": mid, "label": MODEL_LABELS[mid]} for mid in
   MODEL_CHOICES]`, in `MODEL_CHOICES`'s insertion order (flash, then extended) — matches the brief's
   example ordering exactly. The pre-existing `"model"` field (the `GEMINI_MODEL` env var's current
   value, live-mode-only) is unchanged and is a separate concept from the new `"models"` list.
5. Added `_decode_images(images_raw) -> (list[dict] | None, JSONResponse | None)`, next to
   `_too_large()`: `(None, None)` for an absent field; a `422` for anything not shaped like
   `[{"mime": str, "data": str}, ...]`; else `base64.b64decode(img["data"], validate=True)`, catching
   **`(binascii.Error, ValueError)`** — THE CRITICAL FIX. `validate=True` only governs the base64
   alphabet check inside `binascii`; the str -> ASCII-bytes coercion that runs BEFORE that, inside
   Python's own `base64._bytes_from_decode_data`, raises a plain `ValueError` for any non-ASCII
   character in the input string (confirmed against CPython's `base64.py` source, not by running it —
   see verification caveat below). A handler that only caught `binascii.Error` let that shape of input
   fall through unhandled, which FastAPI/Starlette turns into an unhandled-exception 500. Catching both
   closes it: any malformed `"data"` string now returns this function's `422`, never a 500.
6. `api_generate()`:
   - Docstring updated to name `"model"`/`"images"` and state they are LIVE-only.
   - The prompt check and the MOCK branch are unchanged — mock never reads `model`/`images`, matching
     objective 3 ("mock path must ignore model and images") literally. The `MODEL_CHOICES`/base64
     checks are confined to the LIVE branch, after the mode is already known.
   - In the LIVE branch: reads `model = body.get("model")`; if present and not a valid `MODEL_CHOICES`
     key -> `422` `{"error": "validation", "detail": "unknown model ...; choose one of [...]"}`. Then
     reads `images_raw = body.get("images")`, runs it through `_decode_images()`, returning its error
     response verbatim on failure.
   - `generate_live(prompt.strip(), pin, model=model, images=images)`.
7. `_call_gemini(prompt, model=None, images=None)`: builds `contents` as the plain prompt string when
   `images` is falsy (byte-identical to pre-Phase-5), or as
   `[types.Part.from_bytes(data=img["data"], mime_type=img["mime"]) for img in images] + [prompt]` when
   images are present. `generate_content(...)`'s `model=` argument changed from `gemini_model()` (the
   `GEMINI_MODEL` env var) to `MODEL_CHOICES.get(model, DEFAULT_GEMINI_MODEL)`. Kept the pre-existing
   `client.aio.models.generate_content(...)` (async) call, not the brief's paraphrased sync accessor —
   switching would block the event loop inside this `async def`.
8. `generate_live(prompt, pin, model=None, images=None)`: forwards both new parameters to
   `_call_gemini`; otherwise unchanged.

Kept every new/changed line at or under the project's `ruff` `line-length = 100` (`pyproject.toml`);
checked with `Select-String -Pattern "^.{101,}$"` (PowerShell) since a `python`/`ruff` invocation itself
was blocked — see verification caveat. Pre-existing lines already over 100 (present before this
session's edits) were left untouched, not my scope to reflow.

## `tests/canvas/test_app.py`

1. Added `import base64` to the stdlib import block (alphabetically first).
2. `_stub_gemini`'s inner `fake_call` signature changed from `fake_call(prompt)` to
   `fake_call(prompt, model=None, images=None)` — THE OTHER CRITICAL FIX. Every existing Phase 4 test
   that uses `_stub_gemini` sends no `model`/`images`, so both arrive as `None` and those tests'
   behavior is unchanged; without this fix every one of them would hit a `TypeError` at
   `_call_gemini(prompt.strip(), model=model, images=images)`'s call site, since `app.py`'s
   `_call_gemini` is now always invoked with those keywords. Also updated the one other inline
   `_call_gemini` monkeypatch in the file (`must_not_call` inside
   `test_live_generate_still_refuses_an_empty_prompt_immediately`) to the same three-parameter shape,
   for consistency, even though that test's assertion (`called["n"] == 0`) means it is never actually
   invoked.
3. Added a `PHASE 5` section at the end of the file (after `test_without_a_key_generate_is_still_the_
   mock`) with 9 new tests:
   - `test_context_serves_the_available_models_list` — `/api/context`'s `"models"` matches the brief's
     example exactly (id + label, in `MODEL_CHOICES` order).
   - `test_the_model_allowlist_and_default_are_what_the_brief_specifies` — `MODEL_CHOICES`'s keys and
     `DEFAULT_GEMINI_MODEL` match the brief's literal values.
   - `test_live_generate_refuses_an_unknown_model` — an unlisted `"model"` in a LIVE request is `422`,
     and (via a call-counting `_call_gemini` stub) the model is never invoked.
   - `test_live_generate_threads_the_requested_model_to_call_gemini` — a valid `"model"` reaches
     `_call_gemini` unchanged.
   - `test_live_generate_decodes_images_and_passes_the_raw_bytes_to_call_gemini` — a base64-encoded
     image round-trips to the exact original `bytes` by the time `_call_gemini` sees it.
   - `test_live_generate_refuses_an_image_with_invalid_base64_data` — an ASCII string with invalid
     base64-alphabet characters (`binascii.Error`) is `422`, model never called.
   - `test_live_generate_refuses_non_ascii_base64_data_as_422` — **the regression test for the critical
     fix**: `"data": "한글데이터"` (non-ASCII) is `422` with `"error": "validation"`, not an unhandled
     500; the docstring spells out exactly why (`ValueError`, not `binascii.Error`, from Python's own
     str -> ASCII coercion). This is the one new test that did not exist in either prior attempt.
   - `test_live_generate_refuses_a_malformed_images_shape` — an image dict missing `"data"` is `422`,
     model never called.
   - `test_mock_mode_ignores_model_and_images` — a mock-mode request carrying a bogus model AND bogus
     (non-base64) image data gets back a `200` byte-identical to a request with neither field.

---

## Verification (NOT executed by running pytest — command execution was unavailable, see below)

```
pip install -e ".[editor,dev,ai]"
python -m pytest tests/canvas/test_app.py -q
```

Instead: the full edited `app.py` (728 lines) and the full edited `test_app.py`'s Phase 4/5 boundary
and new section (roughly lines 1490-1783) were read back end-to-end after all edits, checked for
brace/paren balance and consistent naming, and every new/changed code path was hand-traced against
each new test: which branch it exercises, what `_call_gemini`/`_decode_images` does with the exact
input, and what status code and body that produces. `base64._bytes_from_decode_data`'s ASCII-coercion
`ValueError` (the critical-fix scenario) was confirmed against CPython's documented/published
`base64.py` source, not by running it — no `python`/`pytest`/`ruff` invocation was able to run this
session (see below). Line lengths were checked with PowerShell `Select-String -Pattern "^.{101,}$"`
against the project's `ruff` `line-length = 100` setting (`pyproject.toml`), since running `ruff`
itself was equally unavailable.

## Out-of-scope / caveats

1. **Only the two `write_scope` files, under `stg.lXn3qHPE`, were edited.** The outer tree's own
   `src/aippt/canvas/app.py` / `tests/canvas/test_app.py` were read (the latter as the base for the
   `cp`) but never written to by this session.

2. **Mock-mode validation of `model`/`images` is deliberately skipped, not merely deferred** — same
   judgment call both prior attempts made, for the same reason: objective 3 ("mock path must ignore
   model and images") reads as the controlling instruction over objective 1's unconditional-sounding
   422, so the allowlist/base64 checks run only in the LIVE branch. `test_mock_mode_ignores_model_and_
   images` pins this down with a `200`, not a `422`.

3. **Command execution (`pytest`, `python -c`, `awk`, `ruff`) was not available this session.** Both
   `Bash` and `PowerShell` invocations of `python`/`ast.parse`/`awk` came back "This command requires
   approval" with no prompt able to surface, on both the staged worktree path and the outer tree.
   Plain filesystem operations (`Bash` `mkdir`/`cp`/`wc -l`/`ls`, `PowerShell` `Select-String`/
   `Get-ChildItem`) and the `Edit` tool worked unprompted throughout. No test in this suite (old or
   new) was actually executed; see the verification section above for what was done instead.

4. **`api_context()`'s pre-existing `"model"` field and the new `"models"` list remain two independent
   concepts that happen to overlap in value** — same observation both prior attempts recorded.
   `"model"` is `gemini_model()` (the `GEMINI_MODEL` env var or `DEFAULT_GEMINI_MODEL`), live-mode-only.
   `"models"` is the static `MODEL_CHOICES` allowlist, always present. Nothing enforces `GEMINI_MODEL`
   (if set) is itself a member of `MODEL_CHOICES`, and a request with no `"model"` field always resolves
   to the literal `DEFAULT_GEMINI_MODEL` constant via `_call_gemini`'s `MODEL_CHOICES.get(model,
   DEFAULT_GEMINI_MODEL)`, not to whatever `GEMINI_MODEL` is set to. Not in this brief's stated scope
   to unify.

5. **`_call_gemini`'s `MODEL_CHOICES.get(model, DEFAULT_GEMINI_MODEL)` assumes `model` is already
   `None` or a validated key** by the time it's called — true for the only real call site
   (`generate_live` <- `api_generate`, which validates first).

6. **Test fixtures for the pre-existing tests were not created.** `tests/fixtures/canvas/*.json` (used
   by `test_export_minimal_returns_a_one_slide_pptx` and others) do not exist under the staged worktree
   and creating them is outside this brief's `write_scope`. Irrelevant to whether the new PHASE 5 tests
   are individually correct, but means the full suite cannot actually turn green in this worktree
   without files outside `write_scope` also being staged — same caveat both prior attempts recorded.
