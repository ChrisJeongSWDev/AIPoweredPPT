---
target_repo: C:/Users/2021670/Documents/멀티 에이전트
claude_model: sonnet
write_scope: tasks/AI_Powered_PPT/src/aippt/canvas/static/index.html, tasks/AI_Powered_PPT/src/aippt/canvas/static/style.css, tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js, tasks/AI_Powered_PPT/src/aippt/canvas/static/interactions.js
change_detail_path: tasks/AI_Powered_PPT/phase6_frontend_change_detail.md
---
# Phase 6 Frontend: Advanced Media & Editor Features

## CRITICAL INSTRUCTION
You MUST apply your edits to `.editwork/tasks/AI_Powered_PPT/src/aippt/canvas/static/...`.

## Tasks

### 1. Media Files (Image/Video) Support
- **UI**: Add "Add Image" and "Add Video" buttons to the sidebar toolbar. When clicked, trigger a file input (`<input type="file" accept="image/*">` etc.).
- **State**: When a user selects a file, read the file and store the `File` object in a global map (e.g., `window.uploadedMedia = window.uploadedMedia || {}; uploadedMedia[file.name] = file;`). 
- **DOM**: Add a new element to the `ir.slides[activeSlideIndex].elements` array with `type: "image"` or `"video"`, and `src: file.name`. Render an `<img>` or `<video>` tag inside the stage so it can be resized/moved like text boxes. (Use `URL.createObjectURL(file)` as the DOM `src`).
- **Export**: Modify `exportPPT()` in `editor.js`. Change the fetch call to `/api/download`. Instead of sending JSON, use `FormData`. `formData.append("ir", JSON.stringify(payload))`. Then loop through `uploadedMedia` and `formData.append(filename, fileObj)`. Remove `application/json` headers so the browser sets the multipart boundary automatically.

### 2. Multi-selection & Alignment
- **Selection**: Allow Shift+Click in `editor.js` / `interactions.js` to select multiple elements. Keep track of them (e.g., `window.selectedElementIds = [...]`).
- **UI**: Add Alignment buttons in the properties panel: Align Top, Bottom, Left, Right, Center X, Center Y.
- **Logic**: When alignment buttons are clicked, find all selected elements, determine the bounding box (e.g. min Y for Top align), and update their `x` or `y` values.

### 3. Copy / Paste
- Add global keyboard listeners for `Ctrl+C` (or `Cmd+C`) and `Ctrl+V` (or `Cmd+V`).
- On Copy, serialize the currently selected element(s) into memory.
- On Paste, duplicate them with a new `id`, slightly offset (`x + 20`, `y + 20`), and add to the current slide.

### 4. Transparency (Alpha) & 1pt Border
- **Alpha**: Add an opacity slider (0-100%) in the style panel for Fill Color. When generating the color string for the IR, if opacity is < 100%, append the hex alpha value to the color (e.g. `#FF000080` for 50% opacity red). Update the DOM element's style to reflect this (`rgba` or `opacity`).
- **Border**: Add a "1pt Border" toggle (checkbox) in the properties panel. If checked, add `border: { color: "#000000", width: 1 }` to the IR element, and show a `1px solid black` border on the DOM element.

### 5. FIX THE MULTI-SELECTION STATE LEAK (Bug Fix)
- You previously implemented multi-selection, but there was a state leak. `var multi` (the alignment set) was not cleared during `restore()` (undo/redo) or `loadIR()`.
- **Action Required**: Add a `clearMulti()` function and call it inside `restore()` (before the new snapshot is applied) and inside `loadIR()` (when clearing the stage) to ensure no detached DOM elements remain in the `multi` array.
- Also ensure that deleting the `selected` element removes it from `multi`.
