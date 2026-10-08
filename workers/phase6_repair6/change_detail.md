# Phase 6 Repair, round 6 (reviewer switched to claude-review-sonnet again; `target_repo` bypass) — change detail

Worker brief: temp file `tmp.byh1julgJY` (`target_repo: /c/Users/2021670/.ma-stg/stg.BLj9uma7`,
`phase: phase6_repair6`, `change_detail_path: workers/phase6_repair6/change_detail.md`). Written here,
in the OUTER tree, per this task's established convention (the staging worktree is scratch; see
`[[ai-powered-ppt-phase-worker-pattern]]`) rather than literally under the temp brief's `target_repo`.

## The temp brief was NOT corrupted this round — cross-checked before trusting it

Unlike `phase6_repair4`/`phase6_repair5` (documented `.`-global-replace corruption), this round's temp
brief is a clean, targeted substitution: the canonical outer-tree brief `brief_phase6_repair6.md` has
`target_repo: tasks/..` and the identical sentence "The `target_repo` is `tasks/..` to bypass the
dispatcher double-prefix bug and the `.` regex bug" — the temp brief has the same sentence with
`tasks/..` consistently replaced by the real staging path
(`/c/Users/2021670/.ma-stg/stg.BLj9uma7`) in both the YAML frontmatter and the prose. Confirmed by
reading `brief_phase6_repair6.md` directly; `write_scope` and the task overview are otherwise
byte-identical between temp and canonical. Treated the temp brief as accurate.

## Verified the administrative claims against the controller's own audit trail, not brief prose alone

- `controller/decisions/decision-009.json`: `decision_source: "operator_acknowledged_via_orchestrator"`,
  `requested_reviewer: "claude-review-sonnet"`, `phase_id: "phase6_repair6"`.
- `controller/phase-pins/phase6_repair6.json` and `controller/phases/phase6_repair6/state.json` both pin
  `decision-009` by matching `payload_sha256`; `state.json` shows a normal
  `propose_candidate -> request_confirmation -> authorize -> precheck -> spawn_worker` event sequence
  (`events.jsonl`), i.e. this dispatch went through the controller's real decision pipeline, the same
  mechanism `phase6_repair5`'s `decision-008` used for its own reviewer swap.
- `controller/phases/phase6_repair5/state.json`: `current_state: "REVIEW_RUNNING"`, `applied: false`,
  `review.ran: false` — round 5 never actually completed review or apply (consistent with
  `[[ai-powered-ppt-phase-worker-pattern]]`'s recurring finding that no staging worktree's work has ever
  landed durably).

So: the reviewer-swap and `target_repo`-bypass instructions are corroborated by the controller's own
records, not just asserted in brief prose — not treated as an unaudited attempt to route around review.

## What "the previous run" actually was, and an honesty note on reproducing it byte-for-byte

Per the brief, "the exact same patch you generated in the previous run" traces back through
`workers/phase6_repair5/change_detail.md` -> `phase6_repair4` -> `phase6_repair3` -> `phase6_repair2` ->
`phase6_repair` -> the original Phase 6 HTML-export design: a per-shape `link` field
(`sanitizeLink()`-gated) and a `Download HTML` exporter (`exportElementHTML()`/`exportHTML()`) that
rebuilds text from `normalizeText()`/`paragraphsToHTML()` rather than serializing the live
`contenteditable` via `outerHTML`/`innerHTML` (the contentEditable-XSS fix `phase6_repair2` introduced
and every round since has carried forward), plus two later fixes: the literal `presentation.html`
filename and `EXPORT_CSS` carrying the `#stage::after` red-divider rule.

**No literal diff bytes were available to this session anywhere.** `find`-ing
`tasks/AI_Powered_PPT/workers/phase6_repair*` in the outer tree turns up only `change_detail.md` prose
in every round's directory — no `artifacts/` subdirectory, no `claude-main-diff-*.txt`, in any of them
(rounds 2-4 each narrate reading such a file, but it was evidently attached to those sessions directly
and never persisted to the outer tree afterward). This round's own temp brief attached no diff either.
So "the exact same patch" was reconstructed from the accumulated, highly detailed prose specification
across all five prior `change_detail.md` files (function names, exact insertion points, security
rationale, and — critically — the two later-round fixes folded in from the start, matching how
`phase6_repair5` itself describes doing this). This is a faithful reconstruction of the documented
design and its security properties, not a byte-for-byte replay of an unavailable diff. Flagging this
explicitly rather than silently claiming verbatim reproduction.

Confirmed via `Grep` before editing: zero matches for `exportElementHTML`/`sanitizeLink`/
`b-export-html`/`"link"` in `stg.BLj9uma7`'s `schema.json`/`editor.js`/`index.html` — a brand-new
staging clone at the pre-Phase-6-HTML-export baseline, so this is a from-scratch build, not a delta.

## What was applied

Applied to `stg.BLj9uma7/tasks/AI_Powered_PPT/src/aippt/canvas/{schema.json,static/index.html,
static/editor.js}` via targeted `Edit` calls, each anchored on unique surrounding context read
immediately beforehand:

- **`schema.json`**: added `$defs.link` (a bare string def) immediately after `$defs.line_width`, and
  `"link": {"$ref": "#/$defs/link"}` to all four shape branches (`rect`, `ellipse`, `triangle`,
  `textbox`, via one `replace_all` Edit on the byte-identical `"text": {"$ref": "#/$defs/text"}` line —
  confirmed exactly 4 matches beforehand) — not `connector`/`image`/`video`.
- **`index.html`**: added `#b-export-html` ("Download HTML") next to `#b-export` in the Export group,
  and a `data-for="shape"` "Link" section (`#p-link`, `type="url"`) immediately before the
  `data-for="connector"` Connector section.
- **`editor.js`**:
  - `DEFAULTS.shape` / `DEFAULTS.textbox` gained `link: ''`.
  - `read()` / `write()` round-trip `d.link` <-> `s.link` on the shared non-connector, non-media branch.
  - `toIR()` emits `out.link = s.link` only when truthy (same pattern as `out.stroke`), after the
    stroke line.
  - `stateFromIR()` gained `link: typeof e.link === 'string' ? e.link : def.link`.
  - `p-link` added to the `txControl(...)` undo-grouping list, and given an `input` listener guarded by
    `!isConnector() && !isMedia()`.
  - `syncProps()` populates `$('p-link').value = s.link || ''` in the shape-only branch.
  - New block inserted immediately before the `/* Load JSON */` comment (after the `$('b-export')`
    handler): `EXPORT_CSS`, `stripEditorChrome()`, `fileToDataURL()`, `mediaDataURL()`, `sanitizeLink()`,
    `exportElementHTML()`, `exportHTML()`, and the `$('b-export-html')` click wiring.

**Security properties (matching every prior round's design):** `exportElementHTML()` never serializes
the live `contenteditable` body via `outerHTML`/`innerHTML` — it clones the live `.el` for
geometry/inline-style fidelity, then for a non-media element overwrites the clone's `.txt .body` with
`paragraphsToHTML(normalizeText(liveBody, ...), s.color)`, the same normalize-then-rebuild round trip
`toIR()` already uses, which discards every tag/attribute a paste could smuggle in and keeps only
`{text, bold, italic, color}`. The title gets the same treatment via `esc(titleString())` (never
`titleField.innerHTML`). `sanitizeLink()` is an http/https/mailto/`#anchor` scheme ALLOWLIST, applied
once at export time — the property panel's `<input type="url">` is not treated as a security boundary.
Media `src` is embedded as a `data:` URL (`fileToDataURL()`/`mediaDataURL()`), never the live
tab-scoped `blob:` URL. `EXPORT_CSS` includes `#stage::after`'s red-divider rule verbatim from
`style.css` (`left:46.4px;top:71px;width:742.3px;height:2px;background:#FF0032` — read directly from
this round's `style.css`, byte-identical to what `phase6_repair4`/`5` describe), and the download uses
the literal filename `presentation.html`, not `safeStem() + '.html'`.

**One judgment call beyond what prior `change_detail.md` prose fully specifies:** when an element's
`link` is set but fails `sanitizeLink()`, this implementation calls `warn(...)` naming the element and
the rejected value, rather than silently dropping it. Every prior round's own manual-verification
checklist says to confirm "the element's own link is clickable when safe and dropped with a warning
when not" — but none of the five prior `change_detail.md` files describe the warning's actual
mechanism, so this is a reconstruction of that stated intent, not a re-derivation of a specific
verified implementation.

## Verification performed (and what could not be run)

Same interpreter-access constraints as every round in this family
(`[[worker-brief-session-execution-constraints]]`): `Bash node --check` and `PowerShell node --check`
both came back "This command requires approval" with no prompt surfacing, both as single unchained
commands. `PowerShell`'s `Get-Content -Raw | ConvertFrom-Json` (a single pipeline, not a `;`-chained
compound) ran unprompted and confirmed `schema.json` parses as valid JSON with `$defs.link` present and
referenced from all four shape branches (`$defs` object listed `link` alongside every other def).

Verified by hand:
- `Grep` count for `"link"` in `schema.json`: 5 (4 `$ref` usages + 1 `$defs.link` key).
- `Grep` count for `b-export-html|id="p-link"` in `index.html`: 2 (one each).
- Whole-file brace balance in `editor.js` via `Grep` count: `{` and `}` both 525 — exact match.
- Every inserted/modified region of `editor.js` re-read in full after editing (the entire new
  ~140-line HTML-export block, plus every touch point: `DEFAULTS`, `read`/`write`, `toIR`,
  `stateFromIR`, the `txControl` list, the new `p-link` input listener, `syncProps()`).
- Read `tests/canvas/test_editor_source.py` (Gate 1) requirements and `Grep`'d the edited file directly:
  `getBoundingClientRect` still appears exactly once; none of the banned measurement APIs
  (`offsetWidth`/`offsetHeight`/`clientWidth`/`clientHeight`/`offsetLeft`/`offsetTop`/`offsetParent`/
  `devicePixelRatio`/`getComputedStyle`/`getBBox`), `zIndex`/`z-index`, `12700`, or any banned canvas
  size (`1920`/`1080`/`1280`/`720`/`1440`/`810`, whole-number matched) appear anywhere in the file.
- Read `tests/canvas/test_app.py`'s Node-lift lists (`_DECLS`/`_FUNCS`/`_P2_DECLS`/`_P2_FUNCS`):
  `stateFromIR` and `DEFAULTS` are both lifted (`_P2_FUNCS`/`_P2_DECLS`), so the new `def.link`
  reference inside `stateFromIR` is safe; `read`/`write`/`toIR` are NOT in any lift list, so the
  round-trip edits there cannot affect the Node harness at all; none of the new
  `exportElementHTML`/`exportHTML`/`sanitizeLink`/`mediaDataURL`/`fileToDataURL`/`stripEditorChrome`
  names appear in any lift list, so they cannot break it either (only reachable via a live browser
  click). Read the `stateFromIR` round-trip tests directly: they assert individual keys
  (`out["bold"]`, `out["italic"]`), not whole-object equality, so the new `link` key cannot break them.
- Confirmed every function the new block references (`normalizeText`, `paragraphsToHTML`, `esc`,
  `titleString`, `download`, `isMediaType`, `isMedia`, `isConnector`, `warn`, `clearWarnings`,
  `setStatus`, `read`, `stage`, `window.uploadedMedia`, `$`) already exists elsewhere in the file via
  `Grep`.

**Not verified (no execution available):** the exported `.html` was not opened in a browser; the JS was
not run through Node; `pytest tests/canvas/` was not run. A session with real execution access should
run the existing suite and manually exercise: draw a shape, set a Link (both a safe `https://` URL and
an unsafe `javascript:` one), add an image, paste rich content (including a hyperlink and bold/colored
text) into a text body AND the title, click Download HTML, confirm the downloaded file is literally
named `presentation.html`, confirm the red divider renders, confirm the unsafe link produces a warning
and is absent from the file, and view-source the result to confirm no `<script>`, `on*=` attribute, or
`javascript:` string appears inside a `.txt .body` or `#title-field`.

## Recommendation to the orchestrator

Same durable-merge gap every round in this family has flagged (`[[ai-powered-ppt-phase-worker-pattern]]`):
no staging worktree's work has ever landed in the outer tree's real `src/`, so this is the sixth
from-scratch rebuild of the same feature. New this round: if bit-for-bit reproduction of "the exact same
patch" is actually required by whatever consumes these `change_detail.md` files, the dispatcher should
attach the actual diff artifact to the brief (or persist it under the relevant `workers/<phase>/`
directory in the outer tree) rather than relying on each round's prose description of the round before
it — five rounds of prose transcription is a lossy channel even when every round is honest about what it
changed, and this round could not verify its reconstruction against any ground truth beyond that prose.
