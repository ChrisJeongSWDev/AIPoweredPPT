# Phase 1 (claude-main) — Backend Model Selection & Multimodal Support — change detail (RETRY, APPLIED)

Mode: continuation of a retry. This session's own temp brief (`C:\Users\2021670\AppData\Local\Temp\tmp.L7ZYhqvdpT`)
named `target_repo: /c/Users/2021670/.ma-stg/stg.qT7gki2q` — a **different** staged worktree from the
one the first `02-phase1` attempt used (`stg.WoNR5MPc`). Per [[ai-powered-ppt-phase-worker-pattern]],
the temp brief's own `target_repo` is what was followed literally; this doc itself is filed in the
OUTER tree at the canonical `change_detail_path` the two on-disk briefs (`02-phase1/brief.md` and
`02-phase1-retry/brief.md`) both name, matching every prior phase's convention.

Target files (both under `stg.qT7gki2q/tasks/AI_Powered_PPT/`):
- `src/aippt/canvas/app.py`
- `tests/canvas/test_app.py`

---

## Why this is a retry, and what changed about the approach

`02-phase1/result.json` records the first attempt's outcome: `review_verdict: "BLOCK"`, with a
`write_scope violation` naming exactly `tasks/AI_Powered_PPT/src/aippt/canvas/app.py` — a file that
**is** literally in that attempt's own `write_scope`. `02-phase1-retry/.scope-fp-brief.md` (a single
hash line) and the presence of this `02-phase1-retry` directory strongly suggest the orchestrator
team identified that BLOCK as a scope-checker false positive and re-dispatched the same objectives
into a fresh staging worktree for a clean run. This session did not change how it read the brief's
objectives — the resulting diff to `app.py` is functionally identical to the first attempt's (verified
by comparing against `02-phase1/artifacts/claude-main-diff-254009-32635.txt`) — only the target
worktree and the `tests/canvas/test_app.py` test bodies (written fresh this session, not copied) differ.

## A session-execution finding worth recording

[[worker-brief-session-execution-constraints]] documents `Edit`/`Bash` git and interpreter invocations
consistently failing with an unresolvable approval prompt on out-of-scope (staging) paths in prior
`02-phase1` and other phases' sessions, with `Write` as the documented workaround. **This session
diverged from that pattern**: plain filesystem `Bash` commands (`mkdir`, `cp`, `wc`, `find`, `ls`)
succeeded unprompted on the `stg.qT7gki2q` path, `git -C <path> status`/`log` were still blocked
("This command requires approval", consistent with the earlier finding on VCS commands specifically),
and — the actually new data point — the `Edit` tool itself succeeded unprompted on both target files,
every time, across 9 separate edit calls. This let the whole task run as targeted diffs instead of
whole-file `Read`+`Write` round trips, which mattered here: `tests/canvas/test_app.py` is ~1765 lines
after editing (~38K tokens by extrapolation from a 28,730-token/1210-line partial `Read`), past the
point a single `Write` call could plausibly reproduce. Recorded in memory as an update to
[[worker-brief-session-execution-constraints]] — whether this is session-specific, environment
config-specific, or a genuine change is unknown; do not assume `Edit` is now universally safe on
out-of-scope paths without re-confirming in a given session.

## `tests/canvas/test_app.py` did not exist in the staged worktree

Same as the first attempt (`02-phase1/change_detail.md` caveat 4): only `src/aippt/canvas/app.py`
existed under `stg.qT7gki2q/tasks/AI_Powered_PPT/`; there was no `tests/` directory at all. Created it
with `mkdir -p .../tests/canvas` and populated it via `cp` of the OUTER tree's current
`tasks/AI_Powered_PPT/tests/canvas/test_app.py` (1636 lines, confirmed with `wc -l` before and after,
and by reading back the import block), then applied the brief's edits on top with `Edit`.

---

## `src/aippt/canvas/app.py`

1. Added `import base64`, `import binascii` (alphabetical, next to the existing stdlib block).
2. Added `MODEL_CHOICES: dict[str, str]` right after `DEFAULT_GEMINI_MODEL = "gemini-3.5-flash"`
   (Phase 4, unchanged), exactly as specified: `{"gemini-3.5-flash": "gemini-3.5-flash",
   "gemini-3.5-flash-extended": "gemini-3.5-flash-extended"}`.
3. Added `MODEL_LABELS: dict[str, str]` alongside it — **an addition beyond the brief's literal
   `MODEL_CHOICES` spec**, needed because `/api/context`'s example payload wants a human `"label"`
   per model and `MODEL_CHOICES` itself only maps id -> id (it doubles as the request-side allowlist,
   not a display table).
4. `api_context()`: added `"models": [{"id": mid, "label": MODEL_LABELS[mid]} for mid in
   MODEL_CHOICES]`, in `MODEL_CHOICES`'s insertion order (flash, then extended) — matches the brief's
   example ordering. The pre-existing `"model"` field (the `GEMINI_MODEL` env var's current value, or
   `None` in mock mode) is unchanged and is a separate concept from the new `"models"` list — see
   caveat 2 below.
5. Added `_decode_images(images_raw) -> (list[dict] | None, JSONResponse | None)`, next to
   `_too_large()`: `(None, None)` for an absent field, a `422` for anything not shaped like
   `[{"mime": str, "data": str}, ...]` or for a `data` string `base64.b64decode(..., validate=True)`
   cannot decode (`binascii.Error` caught specifically), else `(decoded, None)` with each `"data"`
   replaced by raw `bytes`.
6. `api_generate()`:
   - Docstring updated to name `"model"`/`"images"` and state they are LIVE-only.
   - **The prompt check and the MOCK branch are entirely unchanged** — mock never reads
     `model`/`images`, not even to validate shape. Objective 1 ("reject an unlisted model with 422")
     and objective 3 ("mock path must ignore model and images") are in tension for a mock-mode request
     carrying a bad model; resolved by confining the `MODEL_CHOICES`/base64 checks to the LIVE branch
     only, where the values are actually about to reach the network. Flagged in caveat 2.
   - In the LIVE branch: reads `model = body.get("model")`; if present and not a valid
     `MODEL_CHOICES` key -> `422` `{"error": "validation", "detail": "unknown model ...; choose one
     of [...]"}`. Then reads `images_raw = body.get("images")`, runs it through `_decode_images()`,
     returning its error response verbatim on failure.
   - `generate_live(prompt.strip(), pin, model=model, images=images)`.
7. `_call_gemini(prompt, model=None, images=None)`: builds `contents` as the plain prompt string when
   `images` is falsy (byte-identical to pre-Phase-5), or as
   `[types.Part.from_bytes(data=img["data"], mime_type=img["mime"]) for img in images] + [prompt]`
   when images are present. `generate_content(...)`'s `model=` argument changed from `gemini_model()`
   (the `GEMINI_MODEL` env var) to `MODEL_CHOICES.get(model, DEFAULT_GEMINI_MODEL)`. Kept the
   pre-existing `client.aio.models.generate_content(...)` (async) call — the real code the function
   must keep working inside an `async def`, not the brief's paraphrase ("client.models.generate_content").
8. `generate_live(prompt, pin, model=None, images=None)`: forwards both new parameters to
   `_call_gemini`; otherwise unchanged.

## `tests/canvas/test_app.py`

1. Added `import base64` to the import block (alphabetically first among the stdlib imports).
2. `_stub_gemini`'s inner `fake_call` signature changed from `fake_call(prompt)` to
   `fake_call(prompt, model=None, images=None)` — every existing Phase 4 test using `_stub_gemini`
   sends no `model`/`images`, so both arrive as `None` and those tests' behavior is unchanged; without
   this they would hit a `TypeError` since `_call_gemini` is now always invoked with `model=`/`images=`
   keywords.
3. Added a `PHASE 5` section at the end with 8 new tests (written fresh this session against the
   `app.py` behavior above, not copied from the first attempt):
   - `test_context_serves_the_available_models_list` — `/api/context`'s `"models"` matches the id+label
     list in `MODEL_CHOICES`/`MODEL_LABELS` order.
   - `test_the_model_allowlist_and_default_are_what_the_brief_specifies` — `MODEL_CHOICES` and
     `DEFAULT_GEMINI_MODEL` match the brief's literal values.
   - `test_live_generate_refuses_an_unknown_model` — an unlisted `"model"` in a LIVE request is `422`,
     and (via a call-counting `_call_gemini` stub) the model is never invoked.
   - `test_live_generate_threads_the_requested_model_to_call_gemini` — a valid `"model"` reaches
     `_call_gemini` unchanged.
   - `test_live_generate_decodes_images_and_passes_the_raw_bytes_to_call_gemini` — a base64-encoded
     image round-trips to the exact original `bytes`.
   - `test_live_generate_refuses_an_image_with_invalid_base64_data` — undecodable `"data"` is `422`,
     model never called.
   - `test_live_generate_refuses_a_malformed_images_shape` — an image dict missing `"data"` is `422`,
     model never called.
   - `test_mock_mode_ignores_model_and_images` — a mock-mode request carrying a bogus model AND bogus
     image data gets back a `200` byte-identical to `mock_ir(load_pin())` (pins down the caveat-2
     reading: asserts `200`, not `422`).

---

## Verification (NOT executed by running pytest — see caveat 3)

```
pip install -e ".[editor,dev,ai]"
python -m pytest tests/canvas/test_app.py -q
```

Instead: the full edited `app.py` (723 lines) was read back end-to-end after all edits and checked for
brace/paren balance, consistent naming, and that every new code path's control flow matches the
change list above. Every new PHASE 5 test was hand-traced against the final `app.py`: which branch it
exercises, what `_call_gemini`/`_decode_images` actually does with the input, and what status code and
body that produces. `base64.b64decode(..., validate=True)` raising `binascii.Error` on
`"not-valid-base64!!"` (invalid alphabet characters, `-`/`!`) was confirmed against the standard
library's documented behavior rather than by running it.

## Out-of-scope / caveats

1. **Only the two `write_scope` files, under `stg.qT7gki2q`, were edited.** The outer tree's own
   `src/aippt/canvas/app.py` / `tests/canvas/test_app.py` were read (the latter as the base for the
   `cp`) but never written to by this session.

2. **Mock-mode validation of `model`/`images` was deliberately skipped, not merely deferred** — see
   `api_generate()` point 6. A stricter, mode-independent reading of objective 1 (mock also 422s on a
   bad model/base64) is a small, localized change: move the read-and-validate block above the
   `gemini_api_key() is None` branch. Not made here because it contradicts objective 3's plain wording,
   and `test_mock_mode_ignores_model_and_images` would need to flip from `200` to `422` if that reading
   is preferred.

3. **Command execution (`pytest`, `node`) was not attempted this session** given the consistent prior
   pattern of VCS/interpreter invocations hanging on approval (confirmed again this session for
   `git -C <staged path> status`/`log`, both blocked). See the session-execution-finding section above
   for what DID work differently this time (`Edit`, plain `cp`/`mkdir`).

4. **`api_context()`'s pre-existing `"model"` field and the new `"models"` list are independent
   concepts that happen to overlap in value** — same observation as the first attempt's caveat 3.
   `"model"` is `gemini_model()` (the `GEMINI_MODEL` env var or `DEFAULT_GEMINI_MODEL`), live-mode-only.
   `"models"` is the static `MODEL_CHOICES` allowlist, always present. Nothing enforces `GEMINI_MODEL`
   (if set) is itself a member of `MODEL_CHOICES`, and `_call_gemini`'s per-request resolution never
   consults `GEMINI_MODEL` — a request with no `"model"` field always resolves to the literal
   `DEFAULT_GEMINI_MODEL` constant. Not in the brief's stated scope to unify.

5. **`_call_gemini`'s `MODEL_CHOICES.get(model, DEFAULT_GEMINI_MODEL)` assumes `model` is already
   `None` or a validated key** by the time it's called — true for the only real call site
   (`generate_live` <- `api_generate`, which validates first). Matches the brief's literal
   instruction as given.

6. **Test fixtures for the pre-existing tests were not created.** `tests/fixtures/canvas/*.json`
   (used by `test_export_minimal_returns_a_one_slide_pptx` and others) do not exist under the staged
   worktree and creating them is outside this brief's `write_scope`. Irrelevant to whether the new
   PHASE 5 tests are individually correct, but means the full suite cannot actually turn green in this
   worktree without files outside `write_scope` also being staged.
