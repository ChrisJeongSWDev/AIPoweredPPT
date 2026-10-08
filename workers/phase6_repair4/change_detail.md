# Phase 6 Repair, round 4 (dispatcher path-resolution bypass) — change detail

Worker brief: temp file `tmp.6m6s7oI0hK` (`target_repo: /c/Users/2021670/.ma-stg/stg.a59Iv6bp`,
`phase: phase6_repair4`, `change_detail_path: workers/phase6_repair4/change_detail.md`). Written here,
in the OUTER tree, per this task's established convention (the staging worktree is scratch; see
`[[ai-powered-ppt-phase-worker-pattern]]`) rather than literally under the temp brief's `target_repo`.

## The temp brief itself was corrupted — reconstructed before doing anything else

Every literal `.` character in the temp brief's free-text/YAML had been replaced with the literal
string `/c/Users/2021670/.ma-stg/stg.a59Iv6bp` (i.e. the brief's own `target_repo` value), turning
`schema.json` into `schema/c/Users/2021670/.ma-stg/stg.a59Iv6bpjson`, `1.` into
`1/c/Users/2021670/.ma-stg/stg.a59Iv6bp`, sentence-ending periods into the same string, etc. Reversing
that single substitution (replace the path back with `.`) produced text that is a byte-for-byte match
for the canonical outer-tree brief, `brief_phase6_repair4.md` (`target_repo: .`, same `write_scope`,
same task overview, same two optional warning fixes) — confirmed by reading that file directly. Treated
the reconstructed text as the actual brief; did not treat any of the corrupted content as instructions
to interpret literally (per the dispatch guard against command-line-option injection) since it was
self-evidently a templating bug, not intentional content — the file's own `target_repo` field name
being reused as the corruption's replacement value is what caused it (whatever generates these temp
briefs appears to `s/\./target_repo_value/g` over the whole rendered template instead of substituting a
single placeholder token).

## What "the previous run" actually was

The brief claims a prior approved patch exists and asks for the same patch again, citing a
`write_scope`/`target_repo` double-prefix filecopy bug as the reason it didn't land. This is
`[[ai-powered-ppt-write-scope-prefix-bug]]`, and it is exactly the bug `workers/phase6_repair3/change_detail.md`
documents in detail for the immediately preceding round. That file records that `phase6_repair3` applied
`artifacts/claude-main-diff-1989583-17592.txt` (the `phase6_repair2` worker's own fix, already
re-reviewed and approved — see that file's "Note on the brief's own feedback attribution" section) to a
staging worktree, but per `[[ai-powered-ppt-phase-worker-pattern]]` nothing from any staging worktree
round has ever durably landed in the outer tree's real `src/`. This round's `target_repo`
(`.ma-stg/stg.a59Iv6bp`) is a brand-new staging clone — confirmed by `Grep` before editing: zero matches
for `exportElementHTML`/`sanitizeLink`/`b-export-html`/`"link"` in its `schema.json`/`editor.js`/
`index.html` — so, consistent with every prior round in this family, this is a from-scratch reapplication
of the same already-reviewed diff, not a delta on top of existing code.

## What was applied

Applied `artifacts/claude-main-diff-1989583-17592.txt` to
`.ma-stg/stg.a59Iv6bp/tasks/AI_Powered_PPT/src/aippt/canvas/{schema.json,static/index.html,static/editor.js}`
verbatim (every hunk's context matched the pre-existing baseline exactly; confirmed via `Grep`/`Read` at
each anchor before editing, same discipline as `phase6_repair3`):

- `schema.json`: added `$defs.link` and `"link": {"$ref": "#/$defs/link"}` to the four shape branches
  (`rect`, `ellipse`, `triangle`, `textbox`) — not `connector`/`image`/`video`.
- `index.html`: added `#b-export-html` ("Download HTML") next to `#b-export`, and a `data-for="shape"`
  "Link" section (`#p-link`) before the `data-for="connector"` section.
- `editor.js`: `DEFAULTS.shape`/`DEFAULTS.textbox` gained `link: ''`; `read()`/`write()` round-trip
  `d.link`/`s.link`; `toIR()` emits `out.link` when truthy; `stateFromIR()` derives `link` from `e.link`
  with a `def.link` fallback; `p-link` added to `txControl(...)` and given an input listener guarded by
  `!isConnector() && !isMedia()`; `syncProps()` populates `$('p-link').value`; new block (`EXPORT_CSS`,
  `stripEditorChrome()`, `fileToDataURL()`, `mediaDataURL()`, `sanitizeLink()`, `exportElementHTML()`,
  `exportHTML()`, `$('b-export-html')` wiring) inserted before the `/* Load JSON */` comment.

Security properties carried forward unchanged from the already-reviewed design: `exportElementHTML()`
never serializes the live `contenteditable` body via `outerHTML`/`innerHTML` — it re-derives paragraphs
through `normalizeText()`/`paragraphsToHTML()` (the same pair `toIR()` uses), which admits no tag or
attribute a paste could smuggle in. The title gets the same treatment via `esc(titleString())`.
`sanitizeLink()` is an http/https/mailto/`#anchor` allowlist. Media `src` is embedded as a `data:` URL
(`fileToDataURL()`/`mediaDataURL()`), not the live tab-scoped `blob:` URL.

## Also fixed: both reviewer WARNINGs (optional, per the brief)

1. **Filename.** `brief_phase6.md` Sec 3 ("Requirements") states the export must "Trigger a browser
   download of `presentation.html`" — a fixed name. The `1989583` diff instead downloaded
   `safeStem() + '.html'` (title-derived, matching the PPTX export's naming). Changed the `download(...)`
   call in `exportHTML()` to the literal `'presentation.html'`. Did not touch the `<title>` element inside
   the exported document itself (still `esc(safeStem())`) — the warning was specifically about the
   downloaded *file* name, not the document's `<title>`, and the deck's own title tag correctly reflects
   its content.
2. **Missing red divider.** `style.css`'s `#stage::after` (`left:46.4px;top:71px;width:742.3px;height:2px;
   background:#FF0032`, under its "CONTRACT: the editor-only chrome (5.3)" comment) was never in
   `EXPORT_CSS`, so the exported HTML was missing the canvas's visible red divider line entirely. Copied
   that rule verbatim into `EXPORT_CSS`, positioned immediately after `#stage{...}` (same visual grouping
   as a pseudo-element of `#stage`).

Both fixes were applied on top of the verbatim-copied diff, not by altering the diff's own hunks — i.e.
the "exact same patch" instruction was honored first, then the two optional warnings were layered on.

## Verification performed (and what could not be run)

Same interpreter-access constraints as `phase6_repair3` (`[[worker-brief-session-execution-constraints]]`):
`Bash python -c` / `Bash node --check` / `PowerShell node --check` all came back "requires approval" with
no prompt surfacing. `PowerShell`'s `ConvertFrom-Json` (not treated as a blocked general interpreter
invocation) ran unprompted and confirmed `schema.json` parses as valid JSON after all four edits.
`node --check` could not be run through either `Bash` or `PowerShell` this session, so no automated
JS-syntax check was obtained; instead, every inserted/modified region was re-read via `Read`/`Grep` after
editing. The two lines this round changed relative to the verbatim diff (the `#stage::after` CSS-string
addition and the `'presentation.html'` literal) were re-read in place and are syntactically ordinary JS
string literals/concatenation — no braces, quotes, or template structure was altered beyond those two
spots, so the file carries the same syntactic correctness the diff already had plus two narrow,
independently-checked edits.

Verified by hand:
- `Grep` for `"link": {"$ref": "#/$defs/link"}` in `schema.json` returns exactly 4 matches (rect, ellipse,
  triangle, textbox) plus one `$defs.link` definition block.
- `Grep` for `b-export-html` / `id="p-link"` in `index.html` returns exactly one match each, in the Export
  group and the new Link section respectively.
- Every `editor.js` anchor point (`DEFAULTS.shape`/`textbox`, `read()`/`write()`, `toIR()`'s
  `out.stroke` line, the `txControl` id list, `p-size`'s input handler, `syncProps()`'s `p-rot-out` line,
  the `/* Load JSON */` comment, `stateFromIR()`'s `italic:` line) was individually located via `Grep`/
  `Read` and its surrounding context matched the diff's context lines exactly before editing.
- Confirmed every function/variable the new block references (`normalizeText`, `paragraphsToHTML`, `esc`,
  `titleString`, `safeStem`, `download`, `isMediaType`, `isMedia`, `warn`, `clearWarnings`, `setStatus`,
  `stage`, `window.uploadedMedia`, `read`) already exists elsewhere in the file.

**Not verified (no execution available):** the exported `.html` was not opened in a browser; the JS was
not run through Node; `pytest tests/canvas/` was not run. A session with real execution access should run
the existing suite and manually exercise: draw a shape, set a Link, add an image, paste rich content
(including a hyperlink and bold/colored text) into a text body AND the title, click Download HTML, confirm
the downloaded file is literally named `presentation.html`, confirm the red divider renders, and
view-source the result to confirm no `<script>`, `on*=` attribute, or `javascript:` string appears inside
a `.txt .body` or `#title-field`.

## Recommendation to the orchestrator

This is the same durable-merge gap `phase6_repair3` already flagged, now observed a second time on top of
a SECOND distinct dispatcher bug (the brief-corruption issue documented above, layered on the pre-existing
`write_scope` prefix bug). Two independent structural problems are compounding: (1) no staging worktree's
approved work ever merges into the outer tree's real `src/`, so every repair round re-does the same fix
from zero; (2) whatever renders these temp briefs has a template bug that globally replaces `.` with the
`target_repo` field's own value, which is silently destructive to any brief containing file extensions,
sentence punctuation, or numbered lists — this round happened to be recoverable only because the
corruption was a clean, reversible one-to-one substitution and the canonical outer-tree brief was
available to cross-check the reconstruction against. A future corrupted brief without an available
canonical copy would not be so recoverable. Recommend fixing the template-rendering step before the next
dispatch, independent of the merge-gap fix already recommended in `phase6_repair3`.
