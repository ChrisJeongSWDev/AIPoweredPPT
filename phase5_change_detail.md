# Phase 5 — PowerPoint-like editor UX (click-to-drop + textbox auto-focus) — change detail (APPLIED)

Mode: continuation. All six edits below were written to disk successfully in this session, to the
single file in `write_scope`.

Target file:
- `src/aippt/canvas/static/editor.js`

---

## `src/aippt/canvas/static/editor.js`

**a. New constants** — `DROP_THRESHOLD = 5` and `DROP_SIZES` (`rect`/`ellipse`/`triangle`:
100x100, `textbox`: 200x50) added immediately after `var ZOOM_MAX = 200;`.

**b. `dblclick` handler collapsed** — the handler's body (select → find `.txt .body` → set
`contenteditable` → add `.editing` → `beginTx()` → `focus()`) was extracted into a new
`startEditing(el)` function; the `dblclick` listener now just guards `tool`/`connector` and calls
`startEditing(el)`.

**c. `startEditing(el)`** added right before `function stopEditing() {` (i.e., immediately after
`wire()`'s closing brace) — the shared body described above, plus an early return for
`type === 'connector'` (a connector carries no text) that the old inline dblclick body didn't need
because the caller already excluded connectors.

**d. Drag-creation gated behind `DROP_THRESHOLD`** — in the stage `pointerDrag` `move:` handler,
before the `tool === 'connector'` branch: while `!ctx.made` and the pointer hasn't cleared 5 model
units on either axis from `ctx.origin`, the frame returns early and nothing is drawn/sized yet.

**e. `end:` handler rewritten** for click-to-drop + auto-focus:
- `ctx.made` (a real draw-out happened) → `finishCreate(ctx.made)`.
- Otherwise (click, or a sub-threshold wobble) → build a candidate at `ctx.origin`: for
  `connector`, a fixed diagonal (`x2/y2 = x1/y1 + 100`); otherwise the tool's `DROP_SIZES` entry
  (falling back to `DROP_SIZES.rect` for an unlisted tool). Runs through
  `applyConstraints(cand, { alt: true })` (alt so it isn't re-snapped, but still clamped into the
  slide). If illegal, status message and no drop. If legal, `addEl(makeEl(legal))`, `select()`,
  `pushUndo(ctx.before)` (one undo step for the whole drop), then `finishCreate(made)`.

**f. `finishCreate(el)` helper** added right after the stage `pointerDrag({...})` block closes,
before `stage.addEventListener('pointerdown', ...)`: `setTool('select')`, `syncProps()`, the
"Created …" status message, and — the requirement-2 payoff — `if (el.dataset.type === 'textbox')
startEditing(el)`, so a freshly created textbox (drawn or dropped) opens straight into editing.

All six anchors were located verbatim in the pre-edit source and matched the brief's "Replace"/
"Insert" blocks exactly before editing; no other lines were touched.

---

## Verification plan (NOT executed — see caveat)

```
pip install -e ".[editor,dev]"
python -m pytest tests/canvas/test_editor_source.py -q   # Gate 1: forbidden-API grep
python -m pytest -q                                        # full suite
```

## Out-of-scope / caveats

1. **Suite not run.** The session permission layer denied all command execution (`pytest`,
   `node --check`) for this non-interactive worker — every `Bash`/`PowerShell` invocation came back
   "requires approval" with no prompt surfaced. The edit was instead verified by re-reading every
   changed region against the live source after each `Edit` call, confirming brace/paren balance and
   that no other code moved. Gate 1 is a plain substring grep over this file for banned
   measured-geometry APIs (see the file's header comment); none of the added code calls any DOM
   measurement API, so it should pass, but this was not executed to confirm.
2. **`target_repo` path discrepancy.** The worker brief (temp file) named
   `target_repo: .../tasks/AI_Powered_PPT/.editwork`, but `.editwork/` in this task folder is an
   unrelated stray git clone (a different, unrelated C#/VwISystem project — no `src/aippt` tree
   exists under it at all). `phase5_work_order.md` and `phase5_brief.md` (this task's own planning
   docs) both give `target_repo: .../tasks/AI_Powered_PPT` (no `.editwork`), matching where
   `src/aippt/canvas/static/editor.js` actually lives and where every prior phase's change-detail
   file recorded its edits. Treated `.editwork` as a stale/incorrect path and applied the edit to
   the real file at `tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js` instead. Flagging this
   for the user in case `.editwork` was meant to be a separate deliverable.
3. **Connector click-to-drop placement.** The brief places the dropped connector's origin at
   `ctx.origin` (the down-point), same as a shape drop — not centered on the click. This matches
   the brief's explicit example (`x1: o.x, y1: o.y, x2: o.x + 100, y2: o.y + 100`) verbatim, so no
   deviation was made even though it means the diagonal always extends down-right from the click.
