---
target_repo: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT
claude_model: sonnet
---
# Phase 5: PowerPoint-like Editor UX Improvements

## Objective
Enhance the editor UX to more closely match PowerPoint's behavior when inserting shapes and text boxes.

1. **Click-to-drop (Auto-size on click)**: When inserting a shape or textbox using the toolbar tools, if the user simply clicks the canvas without dragging (or drags less than 5 units), automatically insert a default-sized element at the click location.
   - For `rect`, `ellipse`, `triangle`: `100 x 100`.
   - For `textbox`: `200 x 50`.
   - For `connector`: A diagonal line of `100x100` (`x2 = x1 + 100`, `y2 = y1 + 100`).
   - If the auto-sized element goes out of bounds, rely on the existing `applyConstraints` logic (which clamps to the slide) or ensure it doesn't overflow `CANVAS.w` and `CANVAS.h`.

2. **Auto-focus for Textboxes**: When a new `textbox` is inserted (either via drag or click-to-drop), immediately put it into "editing" mode so the user can start typing right away without needing to double-click. This means calling the same logic as the `dblclick` handler: set `contenteditable` to `true`, add the `editing` class to the element, call `beginTx()`, and `focus()` on the `.txt .body`.

## Target Files
- `src/aippt/canvas/static/editor.js`

## Verification
- Run tests (`pytest`) to ensure no syntax errors.
- Ensure that `tests/canvas/test_editor_source.py` (Gate 1) passes (i.e. do not use forbidden APIs like `getBoundingClientRect` outside `toModel`).

