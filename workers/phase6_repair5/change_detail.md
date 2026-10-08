# Phase 6 Repair, round 5 (reviewer switched to claude-review-sonnet, dispatcher path bug) — change detail

Worker brief: temp file `tmp.aAyuXRoRrC` (`target_repo` rendered as
`/c/Users/2021670/.ma-stg/stg.u2yTDruP`, `phase: phase6_repair5`,
`change_detail_path: workers/phase6_repair5/change_detail.md`). Written here, in the OUTER tree, per
this task's established convention (the staging worktree is scratch; see
`[[ai-powered-ppt-phase-worker-pattern]]`) rather than literally under the temp brief's `target_repo`.

## The temp brief itself was corrupted — reconstructed before doing anything else

Same corruption pattern as `phase6_repair4`'s temp brief (documented in that round's
`change_detail.md` and `[[ai-powered-ppt-phase-worker-pattern]]`): every literal `.` character in the
free-text/YAML had been replaced with the literal string `/c/Users/2021670/.ma-stg/stg.u2yTDruP` (this
round's own `target_repo` value) — `schema.json` became
`schema/c/Users/2021670/.ma-stg/stg.u2yTDruPjson`, sentence-ending periods became the same string, etc.
Reversing that single substitution reproduced the canonical outer-tree brief,
`tasks/AI_Powered_PPT/brief_phase6_repair5.md` (`target_repo: .`, identical `write_scope` and task
overview), confirmed by reading that file directly and cross-checking
`tasks/AI_Powered_PPT/controller/phases/phase6_repair5/state.json`'s pinned brief. Treated the
reconstructed text as the actual brief; did not treat any corrupted content as literal instructions,
consistent with the dispatch guard against command-line-option injection — this is a known,
previously-documented templating bug in whatever renders these temp briefs, not intentional content.

## Verified the reviewer-switch instruction against the controller's own audit trail before trusting it

The brief's claim ("previous run failed because `codex-critic` crashed with a 401; switched reviewer to
`claude-review-sonnet` to bypass the outage") is corroborated by the controller state, not just brief
prose:
- `controller/phases/phase6_repair4/state.json`: `review.verdict: "REVIEW_ERROR"`,
  `review.process_exit_code: 1`, `review.identity_match: "unknown"`,
  `violations: ["identity_violation"]`, `current_state: "REVIEW_PROCESS_FAILED"` — the prior round's
  worker succeeded (`worker_succeeded` event present) but the independent-reviewer identity check
  could not be verified because the reviewer process itself crashed.
- `controller/decisions/decision-008.json` (`decision_source: "operator_acknowledged_via_orchestrator"`,
  `requested_reviewer: "claude-review-sonnet"`, `phase_id: "phase6_repair5"`) and
  `controller/active-decision.json` / `controller/phase-pins/phase6_repair5.json` (pinned to this same
  decision, matching `payload_sha256`) show the reviewer substitution went through the controller's own
  candidate→confirm→pin decision pipeline as an operator-acknowledged decision, the same mechanism
  `phase6_repair3` used for its `user_override: "apply_anyway"` on a WARNING verdict — this is not an
  unaudited instruction asserted only by brief prose, so it was not treated as an attempt to route
  around the review gate outside the system's own controls (contrast
  `[[worker-brief-session-execution-constraints]]`'s guidance on declining brief instructions that ask
  to bypass a permission/sandbox boundary with no such record — that concern doesn't apply here because
  the audit trail exists).

## What "the previous run" actually was

Per the brief, "the exact same patch you generated in the previous run" = the patch
`workers/phase6_repair4/change_detail.md` documents: the original Phase 6 HTML-export diff
(`artifacts/claude-main-diff-1989583-17592.txt`, `schema.json` + `editor.js` + `index.html`, adding a
per-shape `link` field and a `Download HTML` exporter with `sanitizeLink()`/`exportElementHTML()`
XSS defenses) with two additional fixes layered on top (both were reviewer WARNINGs, not part of the
original diff's hunks):
1. Export filename fixed to the literal `presentation.html` (requirement in `brief_phase6.md` Sec 3),
   not `safeStem() + '.html'`.
2. `EXPORT_CSS` gained the `#stage::after` red-divider rule (copied verbatim from `style.css`), which
   the original diff omitted.

This round's `target_repo` (`stg.u2yTDruP`) is a brand-new staging clone — confirmed via `Grep` before
editing: zero matches for `exportElementHTML`/`sanitizeLink`/`b-export-html`/`"link"` in its
`schema.json`/`editor.js`/`index.html`, and all of the diff's context anchors (schema.json lines
91/110/129/148 and 280-284; editor.js lines 82, 432, 452, 1392, 1524, 1587, 1841, 2071, 2618) matched
the pre-existing baseline exactly at the same line numbers the diff expects — so, consistent with every
prior round in this family, this is a from-scratch reapplication of an already-reviewed patch, not a
delta on top of existing code. Per `[[ai-powered-ppt-phase-worker-pattern]]`, nothing from any staging
worktree round has ever durably landed in the outer tree's real `src/`, so this is expected.

## What was applied

Applied to `stg.u2yTDruP/tasks/AI_Powered_PPT/src/aippt/canvas/{schema.json,static/index.html,
static/editor.js}` via targeted `Edit` calls (each anchored on unique surrounding context, verified via
`Grep`/`Read` immediately beforehand):

- `schema.json`: added `"link": {"$ref": "#/$defs/link"}` to the four shape branches (`rect`,
  `ellipse`, `triangle`, `textbox` — not `connector`/`image`/`video`) via one `replace_all` Edit (all
  four occurrences were byte-identical context), plus a new `$defs.link` string definition inserted
  after `$defs.line_width`.
- `index.html`: added `#b-export-html` ("Download HTML") next to `#b-export`, and a `data-for="shape"`
  "Link" section (`#p-link`) before the `data-for="connector"` section.
- `editor.js`: `DEFAULTS.shape`/`DEFAULTS.textbox` gained `link: ''`; `read()`/`write()` round-trip
  `d.link`/`s.link`; `toIR()` emits `out.link` when truthy; `stateFromIR()` derives `link` from `e.link`
  with a `def.link` fallback; `p-link` added to the `txControl(...)` id list and given an input listener
  guarded by `!isConnector() && !isMedia()`; `syncProps()` populates `$('p-link').value`; new block
  (`EXPORT_CSS`, `stripEditorChrome()`, `fileToDataURL()`, `mediaDataURL()`, `sanitizeLink()`,
  `exportElementHTML()`, `exportHTML()`, `$('b-export-html')` wiring) inserted before the
  `/* Load JSON */` comment — with the two layered fixes folded directly in this time (not applied as a
  separate pass): `EXPORT_CSS` includes the `#stage::after` red-divider rule from the start, and the
  final `download(...)` call uses the literal `'presentation.html'` instead of `safeStem() + '.html'`.

Security properties (unchanged from the already-reviewed design): `exportElementHTML()` never
serializes the live `contenteditable` body via `outerHTML`/`innerHTML` — it re-derives paragraphs
through `normalizeText()`/`paragraphsToHTML()` (the same pair `toIR()` uses), admitting no tag or
attribute a paste could smuggle in. The title gets the same treatment via `esc(titleString())`.
`sanitizeLink()` is an http/https/mailto/`#anchor` allowlist (scheme-syntax regex, not a denylist).
Media `src` is embedded as a `data:` URL (`fileToDataURL()`/`mediaDataURL()`), never the live
tab-scoped `blob:` URL.

## Verification performed (and what could not be run)

Same interpreter-access constraints as every prior round in this family
(`[[worker-brief-session-execution-constraints]]`): `Bash node --check` came back "This command
requires approval" with no prompt surfacing; a chained `PowerShell Get-Content | ConvertFrom-Json`
was refused for the same reason (compound command). A single, unchained `PowerShell Get-Content -Raw |
ConvertFrom-Json` (still one pipeline, but not a `;`-chained compound) DID run unprompted and confirmed
`schema.json` parses as valid JSON with `$defs.link` present. No automated JS-syntax check was
obtainable this session; every inserted/modified region of `editor.js` was instead re-read via `Read`
after editing and manually brace/quote/paren-balanced (the full ~220-line inserted block, lines
~2086-2304, was re-read in full for this purpose, not just spot-anchors).

Verified by hand:
- `Grep` count for `"link"` in `schema.json`: 5 (4 `$ref` usages + 1 `$defs.link` definition).
- `Grep` count for `exportElementHTML|sanitizeLink|b-export-html|p-link|EXPORT_CSS|stage::after` in
  `editor.js`: 20 occurrences, matching the expected spread across the new block, DEFAULTS, read/write,
  toIR, stateFromIR, txControl list, and the input-listener/syncProps lines.
- `Grep` count for `b-export-html|id="p-link"` in `index.html`: 2 (one each).
- Every function the new block references (`normalizeText`, `paragraphsToHTML`, `esc`, `titleString`,
  `safeStem`, `download`, `isMediaType`, `isMedia`, `warn`, `clearWarnings`, `setStatus`) was confirmed
  to already exist elsewhere in the file via `Grep` (line numbers: 103, 651, 1265, 1335, 1425, 1427,
  1451, 1513, 1996, 2007, 2937).

**Not verified (no execution available):** the exported `.html` was not opened in a browser; the JS was
not run through Node; `pytest tests/canvas/` was not run. A session with real execution access should
run the existing suite and manually exercise: draw a shape, set a Link, add an image, paste rich
content (including a hyperlink and bold/colored text) into a text body AND the title, click Download
HTML, confirm the downloaded file is literally named `presentation.html`, confirm the red divider
renders, and view-source the result to confirm no `<script>`, `on*=` attribute, or `javascript:` string
appears inside a `.txt .body` or `#title-field`.

## Recommendation to the orchestrator

Same structural gap flagged by every prior round in this family
(`[[ai-powered-ppt-phase-worker-pattern]]`): no staging worktree's approved work has ever merged into
the outer tree's real `src/`, so each repair round re-derives the same fix from a fresh clone rather
than starting from where the last round left off. That gap is orthogonal to (and not fixed by) this
round's reviewer substitution — even if `claude-review-sonnet` approves this patch cleanly, it will
still land only in `stg.u2yTDruP`, which the next round's fresh clone will not see. Recommend the merge
gap be fixed independent of whichever reviewer identity is in use.
