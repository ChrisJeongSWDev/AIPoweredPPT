# Phase 2: Editor UI Polish & Property Panel

## Goal
Implement the frontend Property Panel and improve UX based on the Phase 2 implementation plan.
The target is the visual editor built in Phase 1B (`src/aippt/canvas/static/index.html`, `editor.js`, `style.css`).

## Requirements
1. **Property Panel**: Add a right-side floating panel in the UI that appears when an element is selected.
   - It should expose exactly the styling properties supported by `Canvas IR` (as defined in `src/aippt/canvas/schema.json`): `fill`, `color`, `width` for strokes, `text.align`, `text.valign`, `run.size`, `run.color`, `run.bold`, `run.italic`.
   - Update the DOM elements and the IR serialization simultaneously when properties change.
2. **UX Polish**:
   - Double-click to edit text: elements should only enter `contenteditable` state when double-clicked. A single click should just select/drag.
   - Undo/Redo: Implement an event stack for `Ctrl+Z` / `Ctrl+Y` restoring previous geometry and property states.
   - Delete Key: Allow removing the currently selected element from the canvas by pressing `Delete` or `Backspace`.

## Rules for claude-review
- Analyze the `Canvas IR` schema to ensure no property is exposed that isn't supported.
- Check the current `editor.js` and `applyConstraints()` logic to ensure adding Undo/Redo and Property Panel doesn't violate the Prime Directive (`getBoundingClientRect` usage constraints) or the `HEADER_RESERVED` / `FOOTER_RESERVED` boundaries.
- Generate a strict `phase2_brief.md` for `claude-main` (Opus).
- The brief MUST append the standard YAML metadata block at the very end:
```yaml
---
claude_model: opus
mode: continuation
target_repo: .
change_detail_path: tasks/AI_Powered_PPT/phase2_change_detail.md
write_scope: src/aippt/canvas/static/index.html, src/aippt/canvas/static/editor.js, src/aippt/canvas/static/style.css, tests/canvas/test_app.py
```
