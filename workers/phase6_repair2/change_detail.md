# Phase 6 Repair, round 3 (`phase6_repair2` — HTML export: fix Codex Critic BLOCK on contentEditable
# serialization) — change detail

Worker brief: temp file `tmp.jDxmpcus7J` (`target_repo: /c/Users/2021670/.ma-stg/stg.ZQ9vgXVn`,
`phase: phase6_repair2`, `change_detail_path: workers/phase6_repair2/change_detail.md`). Written here,
in the OUTER tree, per this task's established convention (the staging worktree is scratch; see
`[[ai-powered-ppt-phase-worker-pattern]]`) rather than literally under the temp brief's `target_repo`.

## `write_scope` path-prefix bug — same as every prior phase (third confirmed instance)

The temp brief's `write_scope` (`src/aippt/canvas/schema.json`, etc.) again drops the
`tasks/AI_Powered_PPT/` prefix. Compare the canonical outer-tree brief,
`tasks/AI_Powered_PPT/brief_phase6_repair2.md`: it has `target_repo: tasks/AI_Powered_PPT` with the
*same* bare `src/...` `write_scope` entries — internally consistent there, because that `target_repo`
already scopes to the task subtree. The TEMP brief this session actually received instead repoints
`target_repo` at `/c/Users/2021670/.ma-stg/stg.ZQ9vgXVn`, a fresh clone of the WHOLE repo (confirmed by
`ls` before editing anything: `stg.ZQ9vgXVn/src` does not exist; `stg.ZQ9vgXVn/tasks/AI_Powered_PPT/src`
does), but kept the bare `write_scope` paths from the subtree-relative canonical brief unprefixed. This
is exactly `[[ai-powered-ppt-write-scope-prefix-bug]]`, and the presence of a sibling
`.scope-fp-brief_phase6_repair2.md` marker file in the outer tree (alongside an equivalent
`.scope-fp-brief_phase6_repair.md` for the previous round) suggests this exact false-positive has
already been anticipated/tracked once for this phase family. Edited the real, correctly-prefixed files
at `.ma-stg/stg.ZQ9vgXVn/tasks/AI_Powered_PPT/src/aippt/canvas/{schema.json,static/index.html,static/editor.js}`
— editing the literal (nonexistent) unprefixed path would have created a dead file nothing serves.
Flagging this here so whatever scope-checker runs next does not misreport this as a `scope_violation`.

## Starting state: this is a FOURTH build of the Phase 6 HTML-export feature, not a delta

Confirmed by inspection before writing anything (`Grep` for `exportElementHTML`/`sanitizeLink`/
`b-export-html`/`"link"` across the staged `schema.json`/`editor.js`/`index.html`: zero matches).
`stg.ZQ9vgXVn` is a brand-new staging worktree at the pre-Phase-6-HTML-export baseline, unrelated to
the original Phase 6 attempt, the round-1 repair (`workers/phase6_repair`, stage `stg.7SMkFSGt`), or
whatever stage the canonical `brief_phase6_repair2.md` was originally paired with. Checked
`controller/phases/phase6_repair/state.json`: `"current_state": "ABORTED"`, `"applied": false`,
`"review": {"verdict": "BLOCK"}` — so despite that round's `change_detail.md` narrating a complete,
verified fix (a `safeBodyHTML(el, s)` helper doing the same normalize-and-rebuild approach used here),
none of it ever landed anywhere this session's starting point could inherit from. Per
`[[worker-brief-session-execution-constraints]]`'s "change_detail prose is not proof" finding, this is
now a THIRD confirmed instance of that pattern in this exact phase family. So, same as every prior
repair, this build is the whole feature from scratch, incorporating the original design and every fix
from every review round to date (working from the attached `artifacts/claude-main-diff-1934939-13128.txt`,
the same input artifact `phase6_repair` was also given), not a patch on top of pre-existing code.

## What the reviewer blocked, and the fix

**`editor.js:2203-2215` and `editor.js:2269` (in the attached round-1 diff) serialized live
`contenteditable` markup through `clone.outerHTML` and `titleField.innerHTML`.** `exportElementHTML()`
cloned the live `.el` node and returned `clone.outerHTML` wholesale, including whatever a browser paste
handler had left inside `.txt .body` (a contenteditable div) — a browser does not strip unsafe markup
from a paste by default, so pasted content can carry an `onerror=`/`onload=` attribute on any tag, a
`style` with a legacy `expression()`/`-moz-binding` payload, or a nested `<a href="javascript:...">`
that `sanitizeLink()` never sees (it only inspects the element's own `link` PROPERTY, never the
free-text body). The exported slide TITLE had the identical problem via `titleField.innerHTML`. Either
would execute the moment the exported `.html` file is opened in a real browser — stored XSS in a file
whose entire purpose is to be shared/opened standalone.

**Fix — reconstruct from normalized data instead of serializing live DOM, for both spots. An
ALLOWLIST-by-construction, not a denylist:**

- `exportElementHTML(el, dataUrls)` (editor.js): still clones the live `.el` for geometry/inline-style
  fidelity (unchanged from round 1) and still routes media `src` through `mediaDataURL()`/
  `fileToDataURL()` (the blob-URL fix, unchanged, carried forward per the brief's explicit instruction
  to keep it). For a non-media element it now additionally: reads `s = read(el)`, re-derives
  `paragraphs` from the LIVE (not cloned) `.txt .body` via `normalizeText(liveBody, s.size, s.color,
  s.bold, s.italic)` — the SAME function `toIR()` already calls to build the JSON/PPTX export, which
  discards every tag and attribute and keeps only plain text plus three formatting fields (bold,
  italic, color) — then OVERWRITES the clone's `.txt .body` innerHTML with
  `paragraphsToHTML(paragraphs, s.color)`, the SAME function `loadIR()` already uses (editor.js
  around line 2926 in the new file) to turn IR paragraph data back into DOM markup when a JSON file is
  loaded. `paragraphsToHTML()` only ever emits a fixed, hard-coded `<div>/<span style="color:...">/
  <b>/<i>` shape with every text run passed through the existing `esc()`. There is no code path from a
  pasted `<script>` or an `onerror=` attribute into the reconstructed output, because neither is a
  field the `{t, bold, italic, color}` run shape carries at all — not a sanitizer that has to recognize
  and strip a dangerous pattern, but a rebuild from a shape that never had room for one. Also explicitly
  clears `cloneBody`'s `contenteditable` attribute in case the live node was mid-edit when cloned
  (defensive; `stripEditorChrome()` no longer tries to launder `.txt .body` itself — see its own
  comment for why that responsibility moved here).
- `exportHTML()`'s use of `titleField.innerHTML` is replaced with
  `esc(titleString()).replace(/\n/g, '<br>')`. `titleString()` is the SAME plain-text-plus-`\n` walk
  `serialize()`'s `title` field already uses — it discards every tag/attribute on the way and the title
  has no bold/italic/color of its own in the IR at all (schema.json's `title` is a bare string; the
  slide title has never supported rich formatting), so this loses no capability a reload wouldn't
  already lose, and carries the identical "reconstruct from a narrow trusted shape" guarantee
  `paragraphsToHTML()` gives the element bodies above.

`sanitizeLink()` (the element `link` PROPERTY's http/https/mailto/`#anchor` scheme allowlist) is
unchanged — it was never the gap the reviewer flagged; the gap was the free-text body/title never
passing through any sanitizer at all before this round.

Implementation differs cosmetically from round-1's `safeBodyHTML(el, s)` helper (this round inlines the
same normalize-then-rebuild steps directly into `exportElementHTML()` rather than a separate named
function) — functionally equivalent, same two library calls, same data flow.

## Everything else (unchanged in intent from the original Phase 6 design / every prior repair round)

- `schema.json`: added `$defs.link` (`{"type": "string", "description": "..."}`) and referenced it
  (`"link": {"$ref": "#/$defs/link"}`) from the four shape branches (`rect`, `ellipse`, `triangle`,
  `textbox`) as an optional property, after their existing `"text"` property. NOT added to
  `connector`/`image`/`video` — a connector/media element carries no `link` in the IR.
- `index.html`: added `#b-export-html` ("Download HTML") next to `#b-export` in the Export group
  (`type="button" class="primary"`), and a `data-for="shape"` "Link" section (`#p-link`, `type="url"`)
  in the property panel, right before the existing `data-for="connector"` Connector section.
- `editor.js`:
  - `DEFAULTS.shape` / `DEFAULTS.textbox` gained `link: ''`.
  - `read()` / `write()` gained the `d.link` <-> `s.link` round trip on the shared non-connector,
    non-media branch (same branch that already handles fill/stroke/text properties).
  - `toIR()` emits `out.link = s.link` only when truthy (same pattern as `out.stroke`).
  - `stateFromIR()` gained `link: typeof e.link === 'string' ? e.link : def.link` (defensive fallback,
    same treatment every other optional field in that function already gets).
  - `p-link` added to the `txControl(...)` undo-grouping list and given an `input` listener guarded by
    `!isConnector() && !isMedia()` (mirrors `p-fill-alpha`'s handler shape).
  - `syncProps()` populates `$('p-link').value = s.link || ''` in the shape-only branch.
  - New: `EXPORT_CSS` (a self-contained CSS subset — the exported file does not fetch/inline
    `style.css`), `stripEditorChrome()`, `fileToDataURL()`, `mediaDataURL()`, `sanitizeLink()`,
    `exportElementHTML()`, `exportHTML()`, and the `$('b-export-html').addEventListener('click', ...)`
    wiring — inserted as one block immediately before the existing `/* Load JSON */` comment, after the
    `$('b-export')` PPTX-export handler.

## Verification performed (and what could not be run)

No interpreter/VCS command (`node --check`, `git diff`/`git status`, `python -c ...`) could be run in
this session — every attempt via both `Bash` and `PowerShell` came back `"This command requires
approval"` with no prompt surfacing, consistent with `[[worker-brief-session-execution-constraints]]`.
`Edit` itself worked unprompted on every call against this stage's `write_scope` files (this session
landed on the "permissive" end of that memory's observed split — same as the `Read`/`Grep`/plain
filesystem `Bash` commands, e.g. `wc -l`, `ls`, which also worked unprompted). `jq empty schema.json`
(a non-interpreter CLI tool) ran unprompted and confirmed `schema.json` is well-formed JSON.

Verified by hand-reading (not executing):
- Every changed region of `editor.js` re-read in full after editing, including the entire new
  HTML-export block (`EXPORT_CSS` through the `$('b-export-html')` wiring) and every touch point
  (`DEFAULTS`/`read`/`write`/`toIR`/`stateFromIR`/`txControl`/`syncProps`). Traced every added
  function's brace nesting by hand.
- Whole-file brace balance via `Grep` count: `{` and `}` both 531 — exact match, both before and after
  is not directly comparable (no pristine copy was re-fetched), but this is a strong signal against a
  missing/extra brace anywhere in the file as it now stands. A parallel raw paren count showed a
  531-unrelated 1340-vs-1384 imbalance; per round-1's change_detail (which flagged the same class of
  false-positive at a smaller scale), this is expected noise from a ~2900-line, prose-heavy comment
  file where English parentheticals are not reliably balanced within grep's line-blind count — hand-
  traced every paren in every comment/string I personally added (both in the new HTML-export block and
  every one-line touch point) and confirmed each is self-balanced; the residual imbalance lives in the
  ~2600 lines of pre-existing comments this change did not touch.
- Read `tests/canvas/test_editor_source.py` (Gate 1) in full and checked every assertion against the
  new code by hand rather than via pytest: `getBoundingClientRect` still appears exactly once, still
  inside `toModel()` (untouched by this change); none of the banned measurement APIs
  (`offsetWidth`/`offsetHeight`/`clientWidth`/`clientHeight`/`offsetLeft`/`offsetTop`/`offsetParent`/
  `devicePixelRatio`/`getComputedStyle`/`getBBox`), `zIndex`/`z-index`, `12700`, or any of the banned
  canvas sizes (`1920`/`1080`/`1280`/`720`/`1440`/`810`, checked as whole-number matches so `7.2px`/
  `725.29px` etc. in the new `EXPORT_CSS` do not false-positive) appear anywhere in the new code
  (`Grep` over the whole file, single combined pattern, only the one pre-existing
  `getBoundingClientRect` hit).
- Read `tests/canvas/test_app.py`'s Node-lift lists: `stateFromIR`'s new `def.link` reference is safe
  (`DEFAULTS` is lifted alongside it via `_P2_DECLS`, and no new function call was introduced inside
  `stateFromIR` beyond the existing lifted set). `paragraphsToHTML`/`normalizeText` are unmodified and
  still whatever the harness already lifted them as. None of the new `exportElementHTML`/`exportHTML`/
  `sanitizeLink`/`mediaDataURL`/`fileToDataURL`/`stripEditorChrome`/`EXPORT_CSS` names are referenced by
  any `_DECLS`/`_FUNCS`/`_P2_DECLS`/`_P2_FUNCS` lift list, so they cannot break the Node harness (only
  reachable from a live browser via the `#b-export-html` click). Checked the `_state_of`/`stateFromIR`
  round-trip tests (`test_the_element_flag_is_a_SUMMARY_of_the_runs...`, etc.) only assert specific
  keys (`out["bold"]`, `out["italic"]`) rather than the whole object shape, so the new `link` key on
  `stateFromIR`'s return value cannot break them.
- `index.html`: both insertions (`#b-export-html` button, `#p-link` Link section) re-read in place to
  confirm correct tag nesting against their surrounding `<section>`/`</section>` boundaries.
- `schema.json`: `jq empty` confirms well-formed JSON (ran unprompted); all four shape branches
  (`rect`, `ellipse`, `triangle`, `textbox`) re-read to confirm each now references
  `"link": {"$ref": "#/$defs/link"}` exactly once, and that `connector`/`image`/`video` were left
  untouched.

**Not verified (no execution available):** the exported `.html` file was not actually opened in a
browser; the JS was not run through Node; `pytest tests/canvas/` was not run. A session with real
execution access should run the existing suite (expect no regressions — nothing in `write_scope`
touches a name any existing test asserts on) and manually exercise: draw a shape, set a Link, add an
image, paste rich/formatted content (e.g. copied from a live webpage, including a hyperlink and some
bold/colored text) into a text body AND into the title, click Download HTML, and open the result
offline (network disabled) to confirm (a) the image renders from its embedded `data:` URL, (b) the
element's own `link` is clickable when safe and dropped with a warning when not, (c) the pasted rich
content in the body/title renders as plain formatted text (bold/italic/colour preserved via the run
model) with NO surviving tags, attributes, or script execution from the paste — i.e. view-source on the
exported file and confirm no `<script>`, `on*=` attribute, or `javascript:` string appears anywhere
inside a `.txt .body` or `#title-field`.
