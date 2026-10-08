# Phase 6 Repair, round 4 (`phase6_repair3` — HTML export: contentEditable-serialization BLOCK) — change detail

Worker brief: temp file `tmp.z4gyIcT1cR` (`target_repo: /c/Users/2021670/.ma-stg/stg.t0liYUQf`,
`phase: phase6_repair3`, `change_detail_path: workers/phase6_repair3/change_detail.md`). Written here,
in the OUTER tree, per this task's established convention (the staging worktree is scratch; see
`[[ai-powered-ppt-phase-worker-pattern]]`) rather than literally under the temp brief's `target_repo`.

## `write_scope` path-prefix bug — same as every prior phase (fourth confirmed instance)

The temp brief's `write_scope` (`/c/.../stg.t0liYUQf/src/aippt/canvas/schema.json`, etc.) drops the
`tasks/AI_Powered_PPT/` prefix again. The canonical outer-tree brief, `brief_phase6_repair3.md`, has
`target_repo: tasks/AI_Powered_PPT` with the same bare `src/...` paths — correct there, because that
`target_repo` already scopes to the task subtree. The temp brief instead repoints `target_repo` at a
fresh whole-repo clone (`stg.t0liYUQf/src` does not exist; `stg.t0liYUQf/tasks/AI_Powered_PPT/src`
does — confirmed by `ls` before editing) but kept the un-prefixed paths. This is
`[[ai-powered-ppt-write-scope-prefix-bug]]`. Edited the real, correctly-prefixed files at
`.ma-stg/stg.t0liYUQf/tasks/AI_Powered_PPT/src/aippt/canvas/{schema.json,static/index.html,static/editor.js}`.
Flagging this so whatever scope-checker runs next does not misreport this as a `scope_violation`.

## Starting state: this is a fresh build from scratch, not a delta on top of a blocked attempt

Confirmed by `Grep` before writing anything: `exportElementHTML`/`sanitizeLink`/`b-export-html`/`"link"`
all had zero matches in the staged `schema.json`/`editor.js`/`index.html`. `stg.t0liYUQf` is a brand-new
staging worktree at the pre-Phase-6-HTML-export baseline — unrelated to whatever worktree the diff
attached to this brief (`artifacts/claude-main-diff-1989583-17592.txt`) was originally produced against.
Same pattern documented for `phase6_repair2` (see its own `change_detail.md`) and the general
`[[worker-brief-session-execution-constraints]]` finding that a prior round's `change_detail.md` saying
"APPLIED" is not proof the outer tree — or the next staging worktree — actually contains it: each fresh
`.ma-stg/stg.*` clone starts from whatever the outer tree's real `src/` looked like at clone time, and
none of rounds `phase6`, `phase6_repair`, or `phase6_repair2`'s work ever landed there. So this round,
like every prior one, rebuilds the WHOLE feature (original design + every fix from every review round to
date), not a patch on top of pre-existing code.

## Note on the brief's own feedback attribution

The brief quotes the Codex Critic BLOCK verdict verbatim (`editor.js:2203-2215`/`:2269`,
`clone.outerHTML`/`titleField.innerHTML`) and attaches `claude-main-diff-1989583-17592.txt` as "your
previous attempt" that this feedback blocked. Cross-checked the artifacts directory: that exact BLOCK
text is `codex-critic-stdout-1934939-13956.txt`, reviewing diff `claude-main-diff-1934939-13128.txt`
(11:11) — an EARLIER, still-vulnerable diff. The attached `1989583` diff (11:45) is actually the
`phase6_repair2` worker's OWN fix for that same feedback (its `claude-main-stdout-1989583-13005.txt`
narrates exactly this fix, and the diff's own comments are literally tagged "Phase 6 REPAIR #2 (Codex
Critic BLOCK)"). So the attached diff was not itself rejected for contentEditable serialization — it
already contains the fix the brief asks for. This does not change what to do: the diff is the correct,
already-reviewed design, and the actual bug (per "Starting state" above) is that no staging worktree so
far has ever had it durably applied. Applying this diff's content to the real `write_scope` files is
exactly what round 4 needed to do regardless of which round's BLOCK originally prompted the design.

## What was applied

Applied `artifacts/claude-main-diff-1989583-17592.txt` verbatim to the write_scope files (all hunks
matched the pre-existing baseline exactly; no adaptation needed):

- `schema.json`: added `$defs.link` (`{"type": "string", "description": "..."}`) and
  `"link": {"$ref": "#/$defs/link"}` to the four shape branches (`rect`, `ellipse`, `triangle`,
  `textbox`), after their existing `"text"` property. NOT added to `connector`/`image`/`video`.
- `index.html`: added `#b-export-html` ("Download HTML") next to `#b-export` in the Export group, and a
  `data-for="shape"` "Link" section (`#p-link`, `type="url"`) in the property panel, right before the
  `data-for="connector"` Connector section.
- `editor.js`:
  - `DEFAULTS.shape` / `DEFAULTS.textbox` gained `link: ''`.
  - `read()` / `write()` gained the `d.link` <-> `s.link` round trip on the shared non-connector,
    non-media branch.
  - `toIR()` emits `out.link = s.link` only when truthy (same pattern as `out.stroke`).
  - `stateFromIR()` gained `link: typeof e.link === 'string' ? e.link : def.link`.
  - `p-link` added to the `txControl(...)` list and given an `input` listener guarded by
    `!isConnector() && !isMedia()`.
  - `syncProps()` populates `$('p-link').value = s.link || ''`.
  - New block (inserted immediately before the `/* Load JSON */` comment, after the `$('b-export')`
    PPTX handler): `EXPORT_CSS`, `stripEditorChrome()`, `fileToDataURL()`, `mediaDataURL()`,
    `sanitizeLink()`, `exportElementHTML()`, `exportHTML()`, and the `$('b-export-html')` click wiring.

**The security fix this round exists to (re-)deliver, specifically:** `exportElementHTML()` does NOT
serialize the live `contenteditable` `.txt .body` via `outerHTML`/`innerHTML`. It clones the live `.el`
for geometry/inline-style fidelity, but for a non-media element it re-derives `paragraphs` from the LIVE
body via `normalizeText(liveBody, s.size, s.color, s.bold, s.italic)` — the same function `toIR()` uses
for the JSON/PPTX export path, which discards every tag/attribute and keeps only `{text, bold, italic,
color}` — then overwrites the clone's body with `paragraphsToHTML(paragraphs, s.color)`, which only ever
emits a fixed `<div>/<span style="color:...">/<b>/<i>` shape through `esc()`. There is no data path from
a pasted `<script>`/`onerror=` attribute into the reconstructed output, because neither is a field that
shape carries. The exported title has the same treatment: `esc(titleString()).replace(/\n/g, '<br>')`
instead of `titleField.innerHTML` (`titleString()` is the same plain-text-plus-`\n` walk `serialize()`
already uses for the title). `sanitizeLink()` (the element `link` PROPERTY's http/https/mailto/`#anchor`
allowlist) and the blob→`data:` URL media-embedding fix (`fileToDataURL()`/`mediaDataURL()`) are both
carried forward unchanged, per the brief's explicit instruction.

## Verification performed (and what could not be run)

No interpreter/VCS command (`python -c`, `node --check`, `git status`) could be run in this session —
every `Bash` attempt came back "This command requires approval" with no prompt surfacing, consistent
with `[[worker-brief-session-execution-constraints]]`. `Edit`/`Write`/`Bash mkdir`/`Grep`/`Read` all
worked unprompted against both the staging worktree and this outer-tree path (this session landed on the
permissive end of that memory's observed split). `PowerShell`'s `ConvertFrom-Json` cmdlet (not a
general-purpose interpreter invocation) ran unprompted and confirmed `schema.json` parses as valid JSON
after all four edits. A `[regex]::Matches(...)`-based brace-balance check was blocked by the PowerShell
tool's own sandbox ("Command contains subexpressions $()"), so no automated brace count was obtained for
`editor.js`; instead, every inserted/modified region was re-read via `Read` after editing and hand-
checked for matching braces/parens against the source diff, which is a byte-for-byte match (I verified
this file section against the diff character-for-character rather than re-deriving it), so it carries the
same syntactic correctness as whatever review already passed it on the JS-syntax dimension.

Verified by hand:
- Every one of the diff's 4 `schema.json` hunks (rect/ellipse/triangle/textbox) and the new `$defs.link`
  entry applied at the correct anchor, confirmed by `Grep` showing exactly 4 occurrences of
  `"link": {"$ref": "#/$defs/link"}` and one `"link": {` def block.
- Every `editor.js` hunk's surrounding context (the lines immediately before/after each hunk) matched the
  diff's context lines exactly before editing, confirmed via `Read`/`Grep` at each anchor point — i.e.
  this was not a blind patch-apply, each insertion point was individually located and confirmed absent
  beforehand.
- Confirmed every function/variable the new block references (`normalizeText`, `paragraphsToHTML`,
  `esc`, `titleString`, `safeStem`, `download`, `isMediaType`, `isMedia`, `warn`, `clearWarnings`,
  `setStatus`, `stage`, `window.uploadedMedia`, `read`) already exists elsewhere in the file, so no
  `ReferenceError` is introduced.
- Confirmed `stateFromIR()`'s new `def.link` / `e.link` reads are in scope (`def` and `e` are both
  parameters/locals already in that function, re-read in place after editing).
- `index.html`: both insertions re-read in place to confirm correct `<section>`/`</section>` nesting.

**Not verified (no execution available):** the exported `.html` file was not opened in a browser; the JS
was not run through Node; `pytest tests/canvas/` was not run. A session with real execution access
should run the existing suite and manually exercise: draw a shape, set a Link, add an image, paste rich
content (e.g. copied from a live webpage, including a hyperlink and bold/colored text) into a text body
AND into the title, click Download HTML, and open the result offline to confirm (a) the image renders
from its embedded `data:` URL, (b) the element's own `link` is clickable when safe and dropped with a
warning otherwise, (c) the pasted rich content renders as plain formatted text (bold/italic/colour
preserved via the run model) with NO surviving tags, attributes, or script execution — view-source on the
exported file and confirm no `<script>`, `on*=` attribute, or `javascript:` string appears anywhere
inside a `.txt .body` or `#title-field`.

## Recommendation to the orchestrator

This is now the fourth from-scratch rebuild of the same feature (`phase6`, `phase6_repair`,
`phase6_repair2`, this round), each starting from a freshly-provisioned `.ma-stg/stg.*` clone that does
not inherit the previous round's applied edits, because nothing durable ever lands between rounds — see
`[[ai-powered-ppt-phase-worker-pattern]]`'s "-retry/-repair sibling saying APPLIED does NOT mean the
outer tree reflects it" finding, now reconfirmed a third+ time in this exact phase family. If the
Codex Critic review step operates on the staging worktree's diff rather than on a durably-merged outer
tree, consider whether a passing review should trigger an actual merge into the outer tree's `src/`
before the next round is dispatched — otherwise every future repair round will keep re-discovering
(and re-fixing) the same already-solved problem from zero.
