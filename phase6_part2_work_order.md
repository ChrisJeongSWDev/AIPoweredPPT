---
target_repo: C:/Users/2021670/Documents/멀티 에이전트
claude_model: opus
write_scope:
  - tasks/AI_Powered_PPT/src/aippt/canvas/static/index.html
  - tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js
change_detail_path: tasks/AI_Powered_PPT/phase6_part2_change_detail.md
---
# Phase 6 (Part 2): Frontend Media, Styling, Copy/Paste, and Alignment

## CRITICAL INSTRUCTION FOR WORKER
You are running within a dispatcher environment. The dispatcher has created an isolated workspace at `.editwork`. 
You MUST apply your edits to the files inside `.editwork/tasks/AI_Powered_PPT/...`.
DO NOT edit the files directly in the real repo.

## Objective
Update the visual editor (`index.html` and `editor.js`) to support Video/Image loading, Copy/Paste, Multi-selection alignment, transparency, and 1pt borders.

## Requirements

### 1. `index.html` UI Changes
- Add `Image` and `Video` buttons to the `tools` section (e.g. `<button data-tool="image">Image</button>`).
- Add a hidden `<input type="file" id="f-media" accept="image/*,video/*" multiple>` for media selection.
- Add Alignment buttons to a new `<section>` (e.g. "Align Left", "Align Center", "Align Right", "Align Top", "Align Middle", "Align Bottom").
- Add an Opacity range slider (`<input type="range" min="0" max="100" id="p-opacity">`) and a "Border (1pt)" toggle to the properties (`#props`) panel.

### 2. `editor.js` Modifications
- **Media Loading**:
  - When the user selects `Image` or `Video` tool, trigger the file input.
  - Read the files, generate `URL.createObjectURL(file)`, and create an SVG `<image>` or `<foreignObject><video></foreignObject>` element on the stage.
  - Maintain a global Map `mediaFiles = new Map()` mapping the `id` of the element to the actual `File` object.
- **Styling Properties (Opacity & Border)**:
  - Opacity: When setting opacity on a shape, convert it to an 8-character hex color (`#RRGGBBAA`) for the `fill` or `stroke` in the IR, and update the SVG elements `fill-opacity` / `stroke-opacity` accordingly.
  - Border: When the 1pt border toggle is on, set `strokeWidth: 1` and `strokeColor` to black (or a chosen color). When off, set `stroke: null`.
- **Copy / Paste**:
  - Add a `keydown` listener to `document` or `stage`. If `ev.ctrlKey && ev.key === 'c'`, serialize the currently selected element(s) into memory.
  - If `ev.ctrlKey && ev.key === 'v'`, deserialize the memory, offset the coordinates (e.g., `x += 10, y += 10`), assign new `id`s, add them to the stage, and push a single undo state.
- **Multi-Selection & Alignment**:
  - Modify the selection logic: If `ev.shiftKey` is held when clicking an element, add it to the selection array instead of replacing it. Show bounding boxes for all selected items.
  - Alignment logic: For the selected items, find the bounding box of the entire selection. Align each item to the chosen edge (Top, Center, Bottom, etc.) by modifying its `x` or `y`, and push an undo state.
- **Export `/api/download`**:
  - Change the export logic to `FormData`.
  - Append `ir` (the JSON string) to the FormData.
  - Append each file from the `mediaFiles` Map to the FormData with keys matching their `src` property in the JSON IR (so the backend can map them).
  - Use `fetch` with POST and `FormData`, handle the Blob response, and trigger download.

Ensure your changes do not violate the Prime Directive (no `getBoundingClientRect` etc.). Output `phase6_part2_change_detail.md` detailing the changes.
