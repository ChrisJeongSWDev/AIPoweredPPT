# Phase 3: Integration of Headless Worker Client into Generative Pipeline -- change detail

## Path deviation (read this first)

This session's temp brief (`AppData/Local/Temp/tmp.ZMJeG9ljEK`) set `target_repo:
/c/Users/2021670/.ma-stg/stg.EafvhN35` (a repo-rooted clone of the whole mono-repo) and
`write_scope: .../src/aippt/adapters/ai_adapter.py` / `change_detail_path:
.../tasks/phase3_integration/change_detail.md`, both with the `tasks/AI_Powered_PPT/`
segment dropped -- the same recurring dispatcher defect logged in the operator's notes
(`ai-powered-ppt-write-scope-prefix-bug`). Confirmed by directory listing before touching
anything: `stg.EafvhN35/src` does not exist; `stg.EafvhN35/tasks/AI_Powered_PPT/src/aippt/
adapters/ai_adapter.py` does, and it was the fresh, pre-Phase-3 `NotImplementedError` stub
(each staging clone starts clean -- this is not a carry-over from any earlier attempt).
Edited the real, correctly-prefixed file at `stg.EafvhN35/tasks/AI_Powered_PPT/src/aippt/
adapters/ai_adapter.py`, and wrote this document to the canonical location the on-disk
`brief.md` for this task actually specifies (this file, `tasks/AI_Powered_PPT/tasks/
phase3_integration/change_detail.md`) rather than the non-existent `tasks/
phase3_integration/change_detail.md` the temp brief named.

This is at least the second attempt at this exact `phase3_integration` task directory
under this same bug: an immediately-prior session (staging clone `stg.pbZbUGS6`) already
implemented and documented essentially this same brief here, in useful detail, before its
apply/review round was aborted (`result.json`: `"review_decision": "abort"`,
`"reviewer_observed_evidence": "process_failed"`, `applied: false` -- an aborted gate, not
a content rejection; `stg.pbZbUGS6` no longer exists, so none of that session's code
persists anywhere outside its own prose). That prior document was read in full and used as
a cross-check on the manifest/schema/critic-note details below, but the implementation in
`stg.EafvhN35` was written independently against the current repo files, not transcribed
from the prior session's listings -- consistent with `ma-repair-instruction-mismatch`
(verify a repair note against real records, not against a paraphrase, and that includes a
prior session's own paraphrase).

## Repair instructions cross-checked against the actual prior attempt

Before implementing, verified the temp brief's "Repair Instructions (from codex-critic)"
section against real records. `result.json` / `controller/decisions/decision-001.json` in
this task directory confirm a real `codex-critic` review occurred and was blocked
(`review_process_exit_code: 9`, `applied: false`, `review_decision: "abort"`). Cross-checked
all five critic complaints directly against the current repo state (not against the prior
session's prose):

1. **Layout mismatch never checked.** Confirmed: the pre-Phase-3 stub had no such check at
   all (it had no body -- `raise NotImplementedError`).
2. **Body-content budget never checked at all.** Same -- nothing to check, stub only.
3. **`generate_deck` calling `render/fit.py:check_budget()` directly, which is still
   `NotImplementedError`.** Confirmed by reading `render/fit.py` directly in this staging
   clone: `is_cjk`, `visual_width`, `estimate_text_height`, `check_budget`,
   `fit_text_frame`, `split_overflow`, `detect_overflow_in_png` are all still
   `NotImplementedError` bodies. Calling any of them from `generate_deck` would abort
   every filled slide unconditionally, before a `GenerationResult` could ever be returned.
4. **Title-budget lookup never fires for this manifest.** Confirmed directly against
   `reference/layout_manifest.json` (outer tree; this staging clone has no `reference/` --
   see below): every placeholder in every one of the 5 layouts is reported `"type":
   "BODY"`, and `analyze_pptx_master.content_budget()` only adds `max_title_chars_cjk`
   when `ph_type in {"TITLE", "CENTER_TITLE", "VERTICAL_TITLE"}`. That condition is never
   true for this manifest, so a title check keyed on `"max_title_chars_cjk" in budget`
   silently never fires.
5. **Aggregate character-sum check misses per-item line rounding.** Confirmed against the
   critic's own numeric example (4 bullets x 11 chars in a 6-bullet x 10-char placeholder:
   44 <= 60 passes a raw sum, but each bullet wraps to `ceil(11/10) = 2` lines, 8 lines
   total, which overflows 6).

All five hold up as real, specific, current defects to fix -- not a stale or
mismatched repair note.

## What was implemented

All four functions in `ai_adapter.py` (`build_system_prompt`, `generate_outline`,
`fill_slide`, `generate_deck`), replacing their `NotImplementedError` bodies, plus the
supporting private helpers below. Also updated the module's top-of-file `STATUS:`
docstring line, which was stale (said every function but `CliWorkerClient` still raised
`NotImplementedError`).

- **`build_system_prompt(manifest, catalog_md)`** -- reads `prompts/
  00_system_deck_author.md` (resolved via `_PROJECT_ROOT = Path(__file__).resolve()
  .parents[3]`, verified against the actual directory depth of `ai_adapter.py` and cross-
  checked against the identical convention already used at the same depth by
  `canvas/pin.py` and `tools/calibrate.py`) and substitutes `{{LAYOUT_CATALOG}}` with
  `catalog_md`. `manifest` is accepted but unused (`del manifest`, documented, mirroring
  `complete_json`'s existing `del max_tokens` pattern for the same reason) -- the
  instruction only asks for the catalog substitution here.
- **`_load_catalog_md()`** (new helper) -- reads the pre-rendered `reference/
  layout_catalog.md` from disk rather than regenerating it via
  `analyze_pptx_master.render_catalog(manifest)`, so `ai_adapter.py` never needs a
  `python-pptx` dependency of its own.
- **`generate_outline(client, topic, sources, manifest, target_slides=12)`** -- reads
  `prompts/10_outline_storyboard.md`, substitutes `{{TOPIC}}` / `{{SOURCES}}`
  (`"\n".join(sources)`) / `{{TARGET_SLIDES}}`, calls `client.complete_json` against a new
  `_outline_schema(manifest)` (object requiring `slides` + `rationale`; each slide entry
  requires `id`, `layout_id`, `title`, `intent`, `key_points`, with optional
  `source_refs`; `layout_id` is a closed `enum` built from the manifest's own
  `masters[].layouts[]`, so an invented layout is rejected by the provider's own
  structured-output mechanism, before `validate_against_manifest` would ever see it).
  Returns `result["slides"]`.
- **`fill_slide(client, outline_entry, manifest, sources, *, repair_note="")`** -- looks
  up `outline_entry["layout_id"]` via a new `_find_layout(manifest, layout_id)`, raising
  plain `CliWorkerError` (not `CliWorkerSchemaError`) if it names a layout that doesn't
  exist at all -- a structural defect no repair prompt can fix, and one the outline
  schema's own `enum` should already make unreachable. Formats that layout's placeholder
  budgets with a new `_format_layout_budget(layout)`, styled after
  `analyze_pptx_master.render_catalog`'s per-placeholder line format (reads the
  manifest's own precomputed `content_budget` fields directly; does not import
  `analyze_pptx_master`). Substitutes all six `{{...}}` placeholders in `prompts/
  20_slide_fill.md` and validates via a new `_slide_schema()` -- `ir/schema.json`'s
  `$defs.slide` (lowercase key) lifted to the document root with the full `$defs` carried
  alongside so its internal `#/$defs/...` refs still resolve against the new root.
  **Signature change:** added a keyword-only `repair_note: str = ""`, not in the original
  stub -- required for `generate_deck`'s repair loop to hand back a specific error at
  `{{REPAIR_NOTE}}`. Default-valued and additive; any call written against the original
  4-positional signature is unaffected.
- **`generate_deck(client, topic, sources, manifest_path, *, max_repairs=2)`** -- loads
  the manifest JSON from `manifest_path`, calls `generate_outline` once, then per outline
  entry runs a bounded loop (`max_repairs + 1` attempts) around `fill_slide`. Each attempt:
  1. `_check_layout_matches_entry(slide_dict, entry)` -- critic fix #1. Raises
     `CliWorkerSchemaError` naming both the outline's and the response's `layout_id` on a
     mismatch. `CliWorkerSchemaError`'s own class docstring (`"the model answered but got
     the shape wrong -- repairable by re-prompting"`) is what justifies catching it in the
     retry loop, and the critic's own instruction says the same thing explicitly.
  2. `_parse_and_validate_slide(slide_dict, manifest)` -- wraps the slide in a throwaway
     one-slide deck and reuses `Deck.from_dict` (structural errors JSON Schema cannot
     express, e.g. a ragged table row) + `Deck.validate_against_manifest` (unknown
     `layout_id`, belt-and-suspenders with step 1, raised as `IRValidationError`).
  3. `_check_slide_budget(parsed, layout)` -- critic fixes #2-#5, implemented **locally**,
     without calling `render.fit.check_budget` (still `NotImplementedError`): checks
     `slide.title` against a title-role placeholder's char cap (with the fallback
     heuristic documented in the function's own docstring, and repeated below since it is
     the least obvious design choice in this patch), and each `slide.blocks[i]` against
     `body_placeholders[i]`'s cap, positionally (`ir/schema.json`'s own documented "blocks
     map onto non-title placeholders in order"), using `math.ceil(len(item) /
     max_chars_per_bullet_cjk)` summed per block -- not a raw character sum -- per critic
     fix #5. Verified against the critic's own numeric example: 4 items of 11 chars each,
     cap 10 chars/line, max 6 lines -> `ceil(11/10) = 2` per item x 4 = 8 lines -> 8 > 6,
     correctly flagged (a raw sum of 44 <= 60 would have passed it).

  On either exception type, the error string becomes the next `repair_note` and the loop
  retries; after `max_repairs` failed attempts it raises `RuntimeError` naming the slide
  id, its layout, and the last error. Returns a `GenerationResult` with the assembled
  `Deck` (title truncated to 120 chars, the schema's cap, since `topic` is unbounded
  caller-supplied text), `attempts` = total `fill_slide` calls across the whole deck,
  `repaired` = True if any slide needed more than one attempt, and `token_usage={}`
  (neither CLI track exposes token accounting, so this is honestly empty, not a stub).

## Design choice: the title-placeholder fallback heuristic

`analyze_pptx_master.content_budget()` only tags a placeholder's budget with
`max_title_chars_cjk` when its `ph_type` is TITLE/CENTER_TITLE/VERTICAL_TITLE. Every
placeholder in `reference/layout_manifest.json` is reported as plain `BODY` (confirmed
directly against the manifest for all 5 layouts, all 9 placeholders), so that tag never
appears for this template and a title-vs-body split has to come from somewhere else.
`_check_slide_budget` uses the layout's first placeholder (manifest order, which is
idx-ascending) as the title's target. This was checked, not assumed: idx-ascending is also
top-to-bottom in every layout that has more than one placeholder in this manifest
(cross-checked each placeholder's `inches.top` against its `idx` directly), and the one
single-placeholder layout (`2_사용자 지정 레이아웃`) has nothing else for its one
placeholder to be but the title target. The budget applied to it is its own single-line
character cap (`max_chars_per_bullet_cjk`, since `max_bullets` is 1 for every first
placeholder in this manifest) rather than a fabricated multi-line title cap -- there is
nothing in the manifest to derive a 2-line title cap from for a `BODY`-typed placeholder,
and a placeholder whose own budget already says "one line" should not be treated as
holding more. If `content_budget()` is later extended to tag a real title placeholder
(`max_title_chars_cjk` present), the same code path picks that up automatically -- the
lookup checks `max_title_chars_cjk` first and only falls back to
`max_chars_per_bullet_cjk` when it's absent.

## Design choice: aggregate vs. positional body-budget check

Chose positional (`blocks[i]` vs `body_placeholders[i]`) over summing all body text
against a combined pool, since `ir/schema.json` documents the positional mapping as the
actual renderer contract, and a combined-pool check can miss a single overflowing block
whose overage is masked by another under-using block's slack. Blocks beyond the number of
available body placeholders are not checked (the schema says they fall through to
free-floating shapes with no declared budget) -- not a gap, since there's nothing to check
them against. `code`/`image`/`diagram` blocks are excluded from the per-item line count
entirely (`_block_text_items` returns `[]` for them) -- they are not character-budgeted
the way bullets/paragraphs/tables/steps/cards are (monospace/fixed-width, area, and
Mermaid source respectively), and pretending otherwise would just be a second, wrong
estimate on top of the real geometry work `render/fit.py` still owes.

Both the title and body checks budget against the `_cjk` figures unconditionally, never
`_latin`: `ir/schema.json`'s own `deck.language` doc says a `"mixed"` deck (the default)
budgets against CJK as the pessimistic case, and neither the outline nor the fill stage
carries a per-slide language signal this pipeline could budget against `_latin`
selectively even if it wanted to. Budgeting English content against the Korean cap is
stricter than necessary, never unsafe.

## Environment quirk (same as logged for every prior attempt at this task)

This staging clone (`stg.EafvhN35`) contains only `tasks/AI_Powered_PPT/src/` under this
project -- no `prompts/`, `reference/`, or `tasks/phase3_integration/` exist here (the
repo-root `.gitignore` has `tasks/*` with only `.gitkeep` tracked, so none of this
project's data files are ever committed into a fresh clone). `prompts/
00_system_deck_author.md`, `prompts/10_outline_storyboard.md`, `prompts/20_slide_fill.md`,
and `reference/layout_manifest.json` / `reference/layout_catalog.md` were all read from
the OUTER tree to verify their placeholder tokens and manifest shape against the code
written here. The code resolves them relative to its own file location at runtime
(`Path(__file__).resolve().parents[3]`), correct in any full checkout (verified: those
files exist at that relative depth in the outer tree) but not exercisable end-to-end from
inside this stage, since the stage lacks `prompts/`/`reference/` entirely.

## Verification performed (and not performed)

Every attempt to invoke the Python interpreter in this session (`python -m py_compile`,
via the Bash tool, both as part of a compound command and standalone) was refused with
"This command requires approval," with no prompt ever surfacing -- consistent with every
prior attempt on this task family. Plain read-only tool calls (`Read`, `Glob`, `Grep`,
non-Python `Bash`) succeeded unprompted throughout. Instead:

- Read the full edited file back after every change and hand-traced control flow,
  f-string/dict-literal syntax, bracket/paren pairing, and indentation around every new
  block, including a full re-read of the entire file after the last edit.
- Cross-checked every symbol imported from `..ir.models` (`Bullets`, `Callout`, `Cards`,
  `Deck`, `DeckMeta`, `Heading`, `IR_VERSION`, `IRValidationError`, `Paragraph`, `Slide`,
  `Steps`, `Table`, `load_schema`) against that module's actual source (read in full),
  including each `Block` subclass's real field names (`.items`, `.rows`, `.text.plain`,
  `.title`) used inside `_block_text_items`.
- Cross-checked `manifest`'s `masters[].layouts[].placeholders[]` shape (`idx`, `type`,
  `inches.top`, `content_budget.*`) against `reference/layout_manifest.json` in the outer
  tree directly, not from memory or from the prior attempt's prose -- including manually
  verifying the idx-ascending/top-to-bottom claim used for the title-placeholder fallback
  against all 9 real placeholders across all 5 layouts.
- Cross-checked all `{{...}}` placeholder tokens substituted in each prompt against the
  actual prompt files (`00_system_deck_author.md`, `10_outline_storyboard.md`,
  `20_slide_fill.md`), and `ir/schema.json`'s `$defs.slide`/`$defs` shape directly.
- Traced the critic's numeric bullet-overflow example (4 x 11-char items, cap 10, max 6)
  through `_line_count`/`_block_text_items`/`_check_slide_budget` by hand to confirm it is
  actually caught (8 lines computed > 6 max) and that a naive character sum (44 <= 60)
  would not have caught it -- the specific regression this patch exists to fix.
- Did not re-verify `CliWorkerClient` (implemented in a prior phase, untouched here) or
  attempt a live `claude`/`codex` round trip -- same interpreter/process gate, and out of
  this phase's write_scope regardless.

**A reviewer's first act should be a syntax check** (`python -m py_compile
tasks/AI_Powered_PPT/src/aippt/adapters/ai_adapter.py`), then a smoke call of
`generate_deck` against a trivial fake `LLMClient` whose `complete_json` returns
canned outline/slide dicts -- including one deliberately-mismatched `layout_id` and one
deliberately-overflowing bullets block, to confirm both new checks actually fire and that
the retry loop terminates. Neither could be run from this session.
