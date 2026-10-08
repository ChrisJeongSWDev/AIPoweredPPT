# UI Sidebar/Composer Refactor (Codex Critic Work Order) — change detail

Worker brief: temp file `tmp.xuvBYJf1FP` (`target_repo: /c/Users/2021670/.ma-stg/stg.jefKC919`,
`write_scope: tasks/AI_Powered_PPT/src/aippt/canvas/static/{index.html,style.css}`,
`change_detail_path: tasks/AI_Powered_PPT/change_detail.md`). Written here, in the OUTER tree, per
this task's established convention (the staging worktree is scratch and no staging worktree's work
has ever landed durably — see `[[ai-powered-ppt-phase-worker-pattern]]`) rather than literally under
the temp brief's `target_repo`.

## Cross-checked the temp brief before trusting it

The temp brief's Work Order (items 1-7 + the two top-level instructions) is byte-identical to the
canonical outer-tree brief `update_ui_brief.md` (`target_repo: c:/Users/2021670/Documents/멀티
에이전트`, same `write_scope` paths, same `change_detail_path` value) — only `target_repo` differs,
swapped to the real staging path. This is the same "`target_repo` bypass" pattern documented in
`workers/phase6_repair6/change_detail.md`. Also cross-referenced the full source review at
`artifacts/codex-director-stdout-2333388-13109.txt` (dated minutes before `update_ui_brief.md`),
which contains the identical Work Order text plus the audit findings behind it and an item 8
validation checklist not included in the brief itself:

- 232px sidebar has no horizontal overflow.
- Two-column groups stay equal-width with consistent gaps.
- Server Template controls are all stacked and 100% wide.
- The composer never overlaps `#status` or the stage.
- Hiding/showing `#props` does not displace or incorrectly center the composer.
- All existing IDs and control order required by JavaScript remain intact.

Treated item 8 as the real acceptance bar even though the dispatched brief only carried items 1-7.

## What was applied

Applied to `stg.jefKC919/tasks/AI_Powered_PPT/src/aippt/canvas/static/{index.html,style.css}` via
targeted `Edit` calls. No JavaScript, stage-contract CSS (the `#stage`, `#stage::before/::after`,
`#title-field`, `.el` blocks), or element IDs were touched — confirmed via `Grep` on `editor.js`
beforehand that every affected button (`b-view-json`, `b-json`, `b-load`, `b-paste`, `b-export`,
`b-export-html`, `b-save-design`, `b-load-design`, `b-delete-design`) is bound purely by
`getElementById`, never by class name or DOM order, so reclassing/reordering them is safe.

**AI composer (`#ai`, work order item 2):**
- `position: absolute; bottom: 24px; left: 50%; transform: translateX(-50%); z-index: 1000;`
  removed. Replaced with `grid-area: composer; justify-self: center;` — this is what actually seats
  it in `#app`'s existing `'toolbar composer composer'` grid row (the row was already declared;
  `#ai` just never claimed it, which is exactly the bug the Codex audit described).
- Kept the width cap (`width: 720px; max-width: calc(100% - 32px)`) and the solid-white
  bordered/shadowed single-container look unchanged.
- Added `margin: 12px 0 16px` as a normal-flow replacement for the old `bottom: 24px` offset (the
  grid row is `auto`-height, so this is the only remaining source of breathing room above/below the
  composer).
- `.submit-btn`: `border-radius: 50%` → `8px` (rounded square, mid-range of the requested 7-9px),
  `width`/`height` 32px → 34px (mid-range of 32-36px), `background: #1a1a1a` → `#1e293b` with hover
  `#334155` (matches the app's existing dark-action hover elsewhere), `transition: all` →
  `background-color` only (the only property that changes on hover).
- Dead mobile rules (`.composer-head`, `.composer-model`, `.composer-box`, `.composer-actions` —
  none exist in the HTML) replaced with rules targeting the classes the HTML actually has:
  `.composer-toolbar` (stacks to column), `.toolbar-left` / `.toolbar-right` (space-between /
  flex-end) under the same `max-width: 720px` media query.
- `.icon-btn` (the attachment "+" button) kept **circular** — its icon semantics (a circular
  affordance button, matching the model-picker's own hover chip) explicitly warrant it per work
  order item 7's exception clause; only its `transition: all` was narrowed to
  `background-color, color`.

**Scoped layout classes (item 3), applied to JSON & Data / Export Deck / Server Templates only —
`.row` (History/Media/Arrange/Align) was left untouched, per the explicit "do not repurpose `.row`
globally" instruction:**
- `.action-stack` (`display:flex; flex-direction:column; gap:6px`) — vertical 100%-width stacks.
- `.action-grid-2` (`display:grid; grid-template-columns:1fr 1fr; gap:6px`) — equal two-column
  actions.
- `.sidebar-action` — normalized `width:100%`, `min-height:34px`, `padding:8px 10px`,
  `font-size:12px`, `font-weight:500`, `border-radius:5px`, plus a `:focus-visible` outline
  (`2px solid #1e88ff`, the app's existing selection-accent colour, `outline-offset:2px`).
- `.sidebar-action--primary`, `--featured`, `--danger` modifiers for the dark (`#1e293b`, hover
  `#334155`), featured, and destructive (`#ef4444`, hover `#dc2626`) treatments.

**JSON & Data (item 4):** wrapped in `.action-stack`; "View & Copy JSON" is `sidebar-action
sidebar-action--featured` (full-width, first); Download/Load JSON moved into a nested
`.action-grid-2`; "Paste Gem JSON" is `sidebar-action` (full-width, last). All three inline `style=`
attributes the Codex audit named (`#b-view-json`, `#b-paste`, `#b-delete-design`) are removed.

**Export Deck (item 5):** `.row` → `.action-grid-2`; both buttons `sidebar-action
sidebar-action--primary` (equal-width, dark).

**Server Templates (item 6):** rebuilt as one `.action-stack` in the exact required order — Name
label/input, Save button, Templates label/select, Load button, Delete button — replacing the old
layout where Save/Load/Delete sat together in a 3-column `.row` and Name/Templates were separate
full-width fields above it. Delete is `sidebar-action--danger`, placed last as a separate full-width
action.

**Shared button styling (item 7):** the base `button, select, input[...]` rule's
`transition: all 0.15s ease` narrowed to `background-color, border-color, color` (the only
properties any hover/focus state in this file actually changes). Removed the now-redundant
`#b-load, #b-load-design { width: 100%; }` rule — both ids carry `.sidebar-action` (`width:100%`)
now, in their own grid cell / stack slot, so the old rule was dead weight.

## One judgment call beyond what the work order fully specifies

Item 4 says: "Represent the featured blue treatment with a CSS modifier **if it is retained** as
the checklist's intended visual exception" — conditional, not a mandate. The Codex audit's own
framing calls the bright blue (`#2563eb`) a "bypass" of the shared `#1e293b` system, and item 7
asks for a *coordinated, common* slate treatment across sidebar actions. Given both signals point
the same direction, `.sidebar-action--featured` was implemented as the **same** `#1e293b`/`#334155`
palette as `--primary`, distinguished only by weight (700) and size (13px) rather than by
reintroducing a separate colour. This resolves the "bypass" finding outright but is a judgment call,
not a re-derivation of an explicit instruction — flagging it explicitly. If blue was in fact the
intended permanent exception, only `.sidebar-action--featured`'s `background`/`border-color`/hover
values (style.css) need to change back to `#2563eb`/a matching hover; no HTML change would be
needed since the modifier class is already in place on `#b-view-json`.

## Verification performed (and what could not be run)

Same interpreter-access constraints as this task's other worker rounds
(`[[worker-brief-session-execution-constraints]]`) — no browser or JS runtime available in this
session.

Verified by hand:
- `Grep`-counted `{` / `}` in the edited `style.css`: 125 / 125 — balanced.
- Read the full edited region of both files back after editing.
- `Grep`'d `editor.js` for every touched id and for `classList`/`querySelectorAll`/DOM-order
  dependencies (`nextElementSibling` etc.): none of the reclassed/reordered buttons are referenced
  by anything but `getElementById`; the only DOM-order-sensitive code operates on `.tool` buttons
  and `.el` stage children, neither of which was touched.
- `Grep`'d `index.html` for every remaining `style="..."` attribute: only the two stage-contract
  `--zoom` custom-property declarations remain (`#stage-wrap`, `#stage`), which item 1 explicitly
  says not to touch.
- Confirmed via `Grep` that `.composer-toolbar`, `.toolbar-left`, `.toolbar-right` (the classes the
  new media query targets) exist in `index.html` and that the previously-targeted
  `.composer-head`/`.composer-model`/`.composer-box`/`.composer-actions` do not exist anywhere in
  the file (so the old rules really were dead).

**Not verified (no execution available):** not opened in a browser. A session with real execution
access should load the canvas editor and confirm: the composer sits above `#status`, centered, at
both a wide viewport and ≤720px width; toggling element selection (which shows/hides `#props`)
does not shift or miscenter the composer; the submit button reads as a dark rounded square, not a
circle; the sidebar at 232px shows no horizontal scrollbar; and the Server Templates group renders
as five full-width stacked controls in the specified order.

## Recommendation to the orchestrator

Same durable-merge gap flagged by every prior round in this family
(`[[ai-powered-ppt-phase-worker-pattern]]`): this was applied to a `.ma-stg` staging clone, not the
outer tree's real `src/`. If this refactor is meant to actually ship, the staging worktree's
`index.html`/`style.css` need to be copied/merged back into
`tasks/AI_Powered_PPT/src/aippt/canvas/static/` in the outer tree.
