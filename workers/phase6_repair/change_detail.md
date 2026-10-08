# Phase 6 Repair, round 2 (HTML export: fix Codex Critic BLOCK — contentEditable XSS) — change detail

Worker brief: temp file `tmp.icNiFbVXrP` (`target_repo: /c/Users/2021670/.ma-stg/stg.7SMkFSGt`,
`phase: phase6_repair`, `change_detail_path: workers/phase6_repair/change_detail.md`). Written here,
in the OUTER tree, per this task's established convention (the staging worktree is scratch; see
`[[ai-powered-ppt-phase-worker-pattern]]`) rather than literally under the temp `target_repo`. This
**overwrites** the previous `workers/phase6_repair/change_detail.md` (a round-1 repair attempt against
a different, now-discarded stage `stg.1dqAqylI`) — see "Relationship to the previous repair attempt"
below for what carries over and what's new.

## `write_scope` path-prefix bug — same as every prior phase

The temp brief's `write_scope` again drops the `tasks/AI_Powered_PPT/` prefix
(`/c/.../stg.7SMkFSGt/src/aippt/canvas/schema.json`, which does not exist — `stg.7SMkFSGt` is a full
repo clone, not just `src/`; confirmed by `ls` before editing anything). The canonical brief in the
outer tree (`brief_phase6_repair.md`) has the correctly-prefixed paths. Edited the real files at
`.ma-stg/stg.7SMkFSGt/tasks/AI_Powered_PPT/src/aippt/canvas/{schema.json,static/index.html,static/editor.js}`,
same as every prior phase's worker (including the round-1 repair) had to. **This is now the Nth
occurrence of this exact bug across this task's phases — the fix belongs in the brief/temp-file
generator, not in another worker noticing it again.** Did NOT follow the temp brief's own "cd into
the stage root and use bare `src/...` paths" instruction, because that path does not exist; instead
edited the real, correctly-prefixed files and am flagging the mismatch here so whatever scope-checker
runs next does not misreport this as a `scope_violation` the way `controller/phases/phase6_repair/state.json`
(the round-1 attempt) shows happened before (`review_verdict: "BLOCK"`, then `user_override:
"apply_anyway"`, then `event: "abort"` — the apply itself never completed because that attempt's stage
had already been discarded by the time it was revisited).

## Known separate infra bug: this stage's `.gitignore` still gitignores `tasks/*`

`stg.7SMkFSGt/.gitignore` contains `tasks/*` / `!tasks/.gitkeep` with no negation for
`tasks/AI_Powered_PPT/**`. Per `[[ma-stage-gitignore-empty-diff-trap]]`, if the dispatcher captures
this session's diff via `git add -A` (without `-f`), it will report `empty_diff_no_capture` regardless
of the fact that all three `write_scope` files were correctly edited on disk. If that happens: **do
not conclude the task was not done** — read the files directly (paths above) and check
line counts / the markers named below before assuming nothing was written.

## Starting state: this is a THIRD build of Phase 6 HTML export, not a delta

Confirmed by inspection before writing anything: this stage's `schema.json` had no `link` def,
`editor.js` had no `exportHTML`/`b-export-html`/media-embedding code beyond the pre-Phase-6 baseline,
and `index.html` had no `#b-export-html` or `#p-link`. `stg.7SMkFSGt` is a brand-new staging worktree,
unrelated to either the original Phase 6 attempt or the round-1 repair's `stg.1dqAqylI` (both
discarded without landing — see `controller/phases/phase6/state.json` and
`controller/phases/phase6_repair/state.json`, both `"applied": false`). So, same as the round-1
repair, this is the whole feature built from scratch, incorporating both the original design and every
fix from every review round to date, rather than a patch applied on top of pre-existing code.

## Relationship to the previous (round-1) repair attempt

Read `artifacts/claude-main-diff-1934939-13128.txt` (the diff this brief pointed at) and the round-1
`workers/phase6_repair/change_detail.md` (now overwritten by this file, but its content is summarized
here for continuity). Round 1 fixed two Codex Critic BLOCK issues from the *original* Phase 6 attempt:

1. **Blob URL export** — media `src` baked a session-only `blob:` object URL into the exported file.
   Fixed with `fileToDataURL()` / `mediaDataURL()`, converting to a `data:` URL before export.
2. **Link scheme injection** — `href="javascript:..."` was reachable via the `link` property.
   Fixed with `sanitizeLink()`, an http/https/mailto/`#anchor` ALLOWLIST.

Both fixes are carried forward unchanged into this round — the reviewer's note on *this* brief says so
explicitly ("You already fixed the Blob URL and href injection in your previous run, so just keep
those fixes"). What round 1 did **not** fix, and what this round adds, is below.

## What THIS round's reviewer blocked, and the fix

**`editor.js:2203-2215` and `editor.js:2269` (in the round-1 diff) serialized live `contenteditable`
markup through `clone.outerHTML` and `titleField.innerHTML`.** `exportElementHTML()` cloned the live
`.el` node and returned `clone.outerHTML` wholesale — including whatever the browser's paste handler
had left inside `.txt .body` (a contenteditable div). A browser does not strip unsafe markup from a
paste into a contenteditable by default; pasted content can carry a `<script>`, an `onerror=`/`onclick=`
attribute on any tag, or a nested `<a href="javascript:...">`, none of which `sanitizeLink()` ever
sees (it only inspects the element's own `link` PROPERTY, never the free-text body). The same problem
existed for the slide title via `titleField.innerHTML`. Either would execute the moment the exported
`.html` file is opened in a browser — a stored-XSS vector baked into a file meant to be shared/opened
standalone.

**Fix — reconstruct from normalized data instead of serializing live markup, for both spots:**

- Added `safeBodyHTML(el, s)` in `editor.js`, which calls the SAME `normalizeText()` +
  `paragraphsToHTML()` round trip `toIR()` and the JSON load path already use elsewhere in this file.
  `normalizeText()` walks the live `.txt .body` DOM and extracts ONLY text plus bold/italic/colour —
  any other tag or attribute (a `<script>`, an event-handler attribute, a nested unsafe `<a>`) is
  discarded on the way in, never carried through. `paragraphsToHTML()` then re-serializes that data
  into a fixed, known-safe tag set (`<div>`/`<span style="color:...">`/`<b>`/`<i>`), escaping every
  text run through the existing `esc()`. `exportElementHTML()` now clones the live element (for
  geometry/inline-style fidelity, unchanged from round 1), then OVERWRITES the clone's `.txt .body`
  innerHTML with `safeBodyHTML()`'s output before calling `.outerHTML` on the clone — so the live raw
  contenteditable content is never the thing that gets serialized.
- Replaced `titleField.innerHTML` in `exportHTML()` with `esc(titleString()).replace(/\n/g, '<br>')`.
  `titleString()` is the SAME plain-text extraction `toIR()`'s `title` field already uses (walks the
  DOM, keeps only text and `BLOCK_TAGS`-triggered line breaks, drops every tag) — it cannot carry a
  pasted `<script>` or attribute through because it never reads any attribute or tag name into its
  output at all. The title has never supported bold/italic runs (see that function's own comment), so
  this loses nothing a reload wouldn't already lose; `\n` becomes an explicit `<br>`, the same
  convention `paragraphsToHTML()` uses for a run's own embedded newlines.

`sanitizeLink()` (the element `link` property scheme allowlist) is untouched — it was never the gap;
the gap was the free-text body/title never going through any sanitizer at all.

## Everything else (unchanged in intent from the original Phase 6 design / round-1 repair)

- `schema.json`: added `$defs.link` (`{"type": "string"}` + description) and referenced it from the
  four shape branches (`rect`, `ellipse`, `triangle`, `textbox`) as an optional property. Not added to
  `connector`/`image`/`video`.
- `index.html`: added `#b-export-html` ("Download HTML") next to `#b-export` in the Export group, and
  a `data-for="shape"` "Link" section (`#p-link`, `type="url"`) in the property panel.
- `editor.js`:
  - `DEFAULTS.shape`/`DEFAULTS.textbox` gained `link: ''`.
  - `read()`/`write()` gained the `d.link`/`s.link` round trip on the non-connector, non-media branch.
  - `toIR()` emits `out.link = s.link` only when truthy.
  - `stateFromIR()` gained `link: typeof e.link === 'string' ? e.link : def.link`.
  - `p-link` added to the `txControl(...)` list and given an `input` listener guarded by
    `!isConnector() && !isMedia()`.
  - `syncProps()` populates `$('p-link').value = s.link || ''`.
  - New: `EXPORT_CSS`, `stripEditorChrome()`, `fileToDataURL()`, `mediaDataURL()`, `sanitizeLink()`,
    `safeBodyHTML()` (new this round), `exportElementHTML()`, `exportHTML()`, and the
    `$('b-export-html')` click wiring.

## Verification performed (and what could not be run)

No interpreter/VCS command (`python -c ...`, `node --check`, `git status`) could be run in this
session — each returned `"This command requires approval"` with no prompt surfacing, consistent with
`[[worker-brief-session-execution-constraints]]`. `Edit` itself, however, worked unprompted on every
one of the ~14 calls against this stage's `write_scope` files (tested the first, smallest edit before
committing to the rest — this session landed on the "permissive" end of that memory's observed split).
`jq empty schema.json` (a non-interpreter CLI tool) ran unprompted and confirmed `schema.json` is
well-formed JSON. `grep`/`wc`/`Read`/`Grep` also ran unprompted for verification.

Verified by hand-reading (not executing):
- Every changed region of `editor.js` re-read in full after editing, including the entire new
  HTML-export block (`EXPORT_CSS` through the `$('b-export-html')` wiring) and every touch point
  (`DEFAULTS`/`read`/`write`/`toIR`/`stateFromIR`/`txControl`/`syncProps`).
- Ran the file-level Gate 1 structural checks from `tests/canvas/test_editor_source.py` (read in the
  outer tree, since staged worktrees carry no `tests/`) as literal `Grep` queries against the edited
  file rather than via pytest: `getBoundingClientRect` appears exactly once (confirmed via `Grep`
  count); none of `12700`, `1920`, `1080`, `1280`, `720`, `1440`, `810`, `zIndex`, `z-index`,
  `offsetWidth`, `offsetHeight`, `clientWidth`, `clientHeight`, `offsetLeft`, `offsetTop`,
  `offsetParent`, `devicePixelRatio`, `getComputedStyle`, `getBBox` appear anywhere in `editor.js`
  (single combined `Grep`, zero matches).
- Checked `tests/canvas/test_app.py`'s Node-lift lists (`_DECLS`/`_FUNCS`/`_P2_DECLS`/`_P2_FUNCS`):
  `stateFromIR`'s new `def.link` reference is safe (`DEFAULTS` is lifted alongside it in
  `_P2_DECLS`); `paragraphsToHTML` is unmodified and still lifted in `_FUNCS`; none of the new
  `safeBodyHTML`/`exportElementHTML`/`exportHTML`/`sanitizeLink`/`mediaDataURL`/`fileToDataURL`
  functions are referenced by any lift list, so they cannot break the Node harness (they are only
  reachable from a live browser via the `#b-export-html` click).
- A rough whole-file brace-balance count (`{` vs `}` via `Grep`/`wc`) came back exactly even
  (551/551) both before and after the full edit set. A parallel paren count showed a pre-existing
  2-count imbalance unrelated to any inserted region (isolated by re-reading every added block in
  full; each is self-balanced) — almost certainly a decorative artifact in unrelated prose comments
  elsewhere in this ~3000-line file, not a defect introduced here.
- `index.html`: both insertions (`#b-export-html` button, `#p-link` Link section) re-read in place to
  confirm correct tag nesting against their surrounding `<section>`/`</section>` boundaries.
- `schema.json`: `jq empty` confirms well-formed JSON; all four shape branches (`rect`, `ellipse`,
  `triangle`, `textbox`) re-read to confirm each now references `"link": {"$ref": "#/$defs/link"}`
  and that `connector`/`image`/`video` were left untouched.

**Not verified (no execution available):** the exported `.html` file was not actually opened in a
browser; the JS was not run through Node; `pytest tests/canvas/` was not run. A session with real
execution access should run the existing suite (expect no regressions — nothing in `write_scope`
touches a name any existing test asserts on) and manually exercise: draw a shape, set a Link, add an
image, paste rich/formatted content (e.g. from a webpage, including a hyperlink) into a text body and
into the title, click Download HTML, and open the result offline (network disabled) to confirm (a)
the image renders from its embedded `data:` URL, (b) the element's own `link` is clickable when safe
and dropped with a warning when not, and (c) the pasted rich content in the body/title renders as
plain formatted text (bold/italic/colour preserved via the run model) with NO surviving tags,
attributes, or script execution from the paste — i.e. view-source on the exported file and confirm no
`<script>`, `on*=` attribute, or `javascript:` string appears anywhere in a `.txt .body` or
`#title-field`.
