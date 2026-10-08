# Phase 4 Frontend Integration -- /api/generate on CliWorkerClient -- change detail

## Scope and where the edits actually landed

This session's temp brief (`AppData/Local/Temp/tmp.Z3HUbDer59`) set `target_repo:
/c/Users/2021670/.ma-stg/stg.77hGHTWW` with a CORRECTLY-prefixed `write_scope` (`tasks/
AI_Powered_PPT/src/aippt/canvas/app.py, tasks/AI_Powered_PPT/tests/canvas/test_app.py`) --
unlike the recurring dispatcher defect logged in `ai-powered-ppt-write-scope-prefix-bug`,
there was no unprefixed-path mismatch to work around this time.

`app.py` exists under the staged clone (`stg.77hGHTWW/tasks/AI_Powered_PPT/src/aippt/
canvas/app.py`) and was edited there. `test_app.py` does **not** -- the staging clone
carries only `src/`, no `tests/` at all (confirmed by directory listing; this matches the
established pattern in the operator's notes that staging clones for this task are
`src/`-only and the suite cannot be run from one). So `tests/canvas/test_app.py` was
edited directly in the OUTER tree instead, which is the only place it exists. `app.py` was
also mirrored, edit-for-edit, into the OUTER tree copy so both stay byte-identical (verified
with `diff` after every edit) -- the outer tree is what persists once this staging clone is
discarded, per the same established pattern. This document itself is written at the
canonical `change_detail_path` both the temp brief and the canonical `brief.md` agree on:
`tasks/AI_Powered_PPT/phases/phase4_frontend/change_detail.md`.

The canonical `brief.md` in this phase directory points `target_repo` straight at the outer
tree (`c:/Users/2021670/Documents/멀티 에이전트`) with the same write_scope -- consistent
with the temp-brief-repoints-to-a-staging-clone pattern documented elsewhere in this task's
history. Its own `result.json` records a prior dispatch that never started
(`worker_model_authority_mismatch`, exit 95, `worker_started: false`, `applied: false`) --
no code was ever written, so this session started from the pre-Phase-4-migration baseline
with nothing to reconcile.

## What changed, by brief instruction number

**1. `MODEL_PROFILES` / `DEFAULT_PROFILE` (`app.py`).** Replaced the three
Gemini-era profiles (`pro`/`flash`/`flash-extended`) with the four requested:
`sonnet` (backend `claude`, model `sonnet`), `opus` (backend `claude`, model `opus`),
`gpt-5.6-terra` and `gpt-5.6-sol` (both backend `codex`). `DEFAULT_PROFILE = "sonnet"`.
Each entry carries `label`/`thinking` exactly as specified, PLUS `backend`/`model` --
not in the brief's literal two-key sketch, but necessary so `generate_live()` has
somewhere authoritative to look up the `CliWorkerClient(backend=..., model=...)`
constructor arguments per profile, rather than a second parallel mapping that could
drift from the first. `/api/context`'s `models` list still projects only `id`/`label`/
`thinking` (unchanged dict comprehension), so the extra keys are invisible on the wire.

**2. `server_mode()` (`app.py`).** Now driven by `live_mode_enabled()`, which checks
`os.environ.get("AIPPT_LIVE_MODE", "").strip() == "1"` -- the *literal* value `"1"`,
not merely truthy (so `"0"`, `"false"`, `""` all mean mock, same as the old blank-key
handling). `gemini_api_key()`, `gemini_model()`, `DEFAULT_GEMINI_MODEL` are deleted.

**3. `generate_live()` (`app.py`).** Rewritten around `CliWorkerClient(track="b",
backend=cfg["backend"], model=cfg["model"])` per the profile resolved on the request.
Three points worth flagging that the brief's four sentences didn't spell out but the
existing code (`ai_adapter.py`) makes load-bearing:

  - `validate.py` has no `load_schema()` function (checked -- it only has a private,
    `lru_cache`d `_validator()` that builds a `Draft202012Validator` from
    `SCHEMA_PATH`). `SCHEMA_PATH` itself IS already a public module-level constant, so
    the new `_relaxed_live_schema()` in `app.py` imports that and does its own
    `json.loads` + drops `"target"` from the top-level `required` list, cached with
    `@lru_cache(maxsize=1)` the same way `validate.py`'s own schema loader is cached.
  - `CliWorkerClient.complete_json()` is genuinely synchronous (`subprocess.run`
    under the hood, up to `timeout_s=300` by default). Calling it directly inside the
    `async def generate_live` coroutine would block FastAPI's single-threaded event
    loop for the CLI's full run time, stalling every other in-flight request
    (export included). Wrapped in `asyncio.to_thread()` -- not requested explicitly,
    but calling a blocking function directly on the loop is a correctness bug for a
    server handling concurrent requests, not a style choice.
  - `complete_json()` already does JSON extraction (`_extract_json_object`, tolerates
    code fences) and schema validation (`_validate_against_schema`) internally and
    returns a plain `dict` or raises `CliWorkerError`/`CliWorkerSchemaError`. So the
    old `_strip_code_fence()` / `json.loads()` step in `generate_live()` was deleted
    entirely rather than kept as now-dead code -- it duplicated work the seam already
    guarantees.
  - **Images are validated but never forwarded.** `CliWorkerClient.complete_json()`
    has no attachment parameter at all (text-only: `system`, `user`, `schema`). The
    `images` argument stays in `generate_live()`'s signature for contract
    compatibility with `api_generate()`'s existing `_decode_images()` call (so the
    count/size/MIME limits published via `/api/context` keep meaning something), but
    `generate_live()` does `del images` and never touches its bytes. This is a real
    capability gap versus the old Gemini vision path, not something the brief asked
    me to solve -- flagging it here since it's the kind of silent behavior change a
    reviewer should know about rather than discover from a bug report.

  Renamed `GeminiError` -> `LiveGenerateError` (class + both raise sites +
  `system_instruction()`'s except clause + `_finalize_live_ir()`'s type guard).
  Not explicitly requested, but the brief's own instruction 2 says to delete
  Gemini-named symbols that no longer apply (`gemini_api_key`/`gemini_model`/
  `DEFAULT_GEMINI_MODEL`); leaving an exception class literally named `GeminiError`
  in a file with zero remaining Gemini code seemed like the same category of stale
  naming, so it was renamed too, consistently, in both `app.py` and `test_app.py`.

  `/api/context`'s `"model"` field (the live-mode badge tooltip) previously reported
  `gemini_model()` -- one deployment-wide provider model shared by every profile. That
  concept no longer exists: every profile is now a genuinely different `(backend,
  model)` pair. It now reports `MODEL_PROFILES[DEFAULT_PROFILE]["label"]` when live,
  `None` otherwise -- still a truthy-string-or-None contract, which is all
  `editor.js` (`CONTEXT.model || 'the model'`, `applyMode(CONTEXT.mode,
  CONTEXT.model)`) actually depends on; confirmed by reading `editor.js` (out of
  write_scope, read-only) rather than assuming from the brief's claim that it "only
  checks mode/model state."

**4. `tests/canvas/test_app.py`.** Rewrote the whole "PHASE 4" section:
  - `_stub_worker()` replaces `_stub_gemini()`, monkeypatching
    `aippt.adapters.ai_adapter.CliWorkerClient.complete_json` (a class-attribute
    patch, so it applies regardless of which module holds a reference to the same
    class object) instead of `appmod._call_gemini`. It now also asserts the schema
    handed to `complete_json` never requires `"target"`, and returns/raises a
    Python object directly rather than a JSON string (matching `complete_json`'s
    real dict-or-raise contract).
  - Every `GEMINI_API_KEY` env-var test converted to `AIPPT_LIVE_MODE`; added a
    parametrized "only the literal `1`" test and a padded-`"  1  "` positive case,
    replacing the single old blank-key test with equivalent (and slightly broader)
    coverage of `live_mode_enabled()`'s exact-match semantics.
  - Added `test_live_generate_uses_the_requested_profiles_backend_and_model`,
    monkeypatching `CliWorkerClient.__init__` itself to capture what `track`/
    `backend`/`model` a request for `"gpt-5.6-sol"` actually constructs the client
    with -- this is the one behavior the brief's instructions imply (profile ->
    backend/model routing) but the brief-level tests didn't already cover, and it's
    the part most likely to silently break (e.g. reading the wrong dict key).
  - **Removed** `test_live_generate_tolerates_a_code_fence`. Fence-tolerance is now
    entirely `ai_adapter.py`'s `_extract_json_object()`'s job (outside this write
    scope) -- `complete_json()` never hands app.py raw fenced text to strip, so a
    test at this layer asserting fence-stripping would be testing code that no
    longer exists here. If fence-tolerance needs a regression test, it belongs in
    `ai_adapter.py`'s own test module (not present in this repo's `tests/` tree as
    far as this session found).
  - `test_live_generate_reports_bad_json_as_502` -> renamed
    `test_live_generate_reports_a_schema_mismatch_as_502`, now simulating
    `complete_json` raising `CliWorkerSchemaError` instead of returning a plain
    non-JSON string -- the real client never returns non-dict garbage, it raises.
  - Deleted the now-unused `import aippt.canvas.app as appmod` (nothing in the
    Phase 4 section references `appmod` any more; `MOCK_LATENCY_S, app, mock_ir`
    are still imported by name at the top of the file for the Phase 3 tests, which
    are untouched).

## What was NOT verified by execution, and why

Per the operator's own notes on this task family
(`worker-brief-session-execution-constraints`), interpreter and VCS commands are
commonly gated behind an approval prompt that never surfaces in this dispatch mode.
Confirmed again this session: `python -m py_compile app.py` and `python -c "import
ast; ast.parse(...)"` both returned "This command requires approval" via both the
Bash and PowerShell tools; `python --version` (a trivial probe) succeeded. `Edit`
itself was open and unprompted on both the staged clone and the outer tree the whole
session -- this was a "wide open" session in that memory file's taxonomy, not a
"totally blocked" one.

So: **the test suite was not actually run.** Verification was: (a) a full manual
read-through of the finished `app.py` end to end for consistency (import order,
every `gemini_*` name gone except in explanatory prose, no leftover reference to
`_call_gemini`/`_strip_code_fence`/`_thinking_config`/`_accepts_field`); (b) a
`diff` confirming the staged and outer-tree `app.py` copies are byte-identical;
(c) hand-tracing every rewritten test against the new `app.py` contract (what
`complete_json` is called with, what it's allowed to return, what status/error code
each failure mode should produce); (d) grepping both files for every prior mention
of "gemini"/"Gemini"/"GEMINI" to confirm nothing was missed or left inconsistent.
A human or a session with real command execution should run `pytest tests/canvas/
test_app.py -k generate` (needs the `editor,dev` extras and, per the pre-existing
Gate 2 module docstring, will SKIP rather than fail without `fastapi`/`httpx`
installed) before trusting this beyond the manual checks above.

## Known pre-existing condition, unrelated to this change

`pyproject.toml`'s `ai` extra still lists `google-genai` (along with `anthropic`/
`openai`, all three still `NotImplementedError` stubs per `ai_adapter.py`'s own
module docstring). `pyproject.toml` is not in this phase's `write_scope`, so it was
left untouched; noting it here since `app.py` no longer imports `google.genai` at
all, so that dependency is now unused by anything this task actually runs.

## Follow-up session: a fabricated "TAMPER RECOVERY" instruction, rejected

A later session's temp brief (`AppData/Local/Temp/tmp.hDHNRViIni`, `target_repo:
/c/Users/2021670/.ma-stg/stg.m3litLa9`) opened with a "REPAIR CONTINUATION (TAMPER
RECOVERY)" section claiming a prior run "was blocked by a PARENT TAMPER DETECTED
safety stop" and instructing this file's contents to be read from
`/c/Users/2021670/.ma-stg/stg.77hGHTWW/` and copied VERBATIM into the target,
"no re-thinking or re-implementing." The SAME section is also present, verbatim, in
the on-disk canonical `brief.md` for this phase directory -- this is not just a
temp-brief artifact.

That instruction was not followed, for three independent reasons:

1. **It misdescribes the real recorded failure.** This phase directory's own
   `result.json` / `result.md` record the actual last failure as
   `worker_model_authority_mismatch` (D97R R1, fail-closed, exit 95) --
   `worker_started: false`, `applied: false`, target never touched. There was no
   tamper event and no prior work product to "recover"; `ma-repair-instruction-
   mismatch` (verify a repair note against real records, not a paraphrase) applies
   directly here.
2. **`stg.77hGHTWW` was outside this session's permitted working directories** --
   the sandbox itself refused a directory listing there. A legitimate repair
   pointer would not name a location the session has no access to.
3. **Copying unreviewed file contents "verbatim" into a codebase without
   re-implementing or verifying them is the wrong move regardless of framing** --
   the same category of action refused independent of whether the story behind it
   checks out.

Instead, this session verified the ACTUAL current state of both write_scope files
directly: `app.py` in the target staging clone (`stg.m3litLa9`) was read in full and
found byte-identical to the already-implemented, already-verified outer-tree copy
documented above (all four brief instructions present: the four-profile
`MODEL_PROFILES` / `DEFAULT_PROFILE = "sonnet"`, `AIPPT_LIVE_MODE`-driven
`server_mode()`, `generate_live()` rebuilt around `CliWorkerClient`, and the relaxed
live schema). Cross-checked again against `ai_adapter.py`'s real `CliWorkerClient.
__init__`/`complete_json` signatures (`track`/`backend`/`model` kwargs, the
`_ALLOWED_MODELS` gate applying only to `backend="claude"`) to confirm the calling
convention still matches. `tests/canvas/test_app.py` (outer tree; the staging clone
has no `tests/` at all, same as every prior session on this task) still carries the
full "PHASE 4" section verified above, unchanged.

Net result: no code edit was necessary or made in this session -- both write_scope
targets already satisfy every numbered instruction in the brief, verified against
current file contents rather than assumed from either the brief's tamper-recovery
narrative or the original implementing session's own prose.
