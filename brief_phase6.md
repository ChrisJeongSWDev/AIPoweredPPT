target_repo: tasks/AI_Powered_PPT
phase: phase6
claude_model: sonnet
change_detail_path: workers/phase6/change_detail.md
read_refs:
write_scope:
  - tasks/AI_Powered_PPT/src/aippt/canvas/schema.json
  - tasks/AI_Powered_PPT/src/aippt/canvas/static/index.html
  - tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js

# Task Overview
We are adding an HTML Export feature and extending the `canvas-ir/1` schema to support hyperlinks (`link` property) so that exported HTML can have interactive links (e.g. to a separate algorithm explanation slide). 

## Requirements
1. **IR Schema Extension (`schema.json`)**:
   - Add a `"link": {"type": "string"}` property to the schema. The safest place is either at the element level (for shapes) or inside the text run. Given PPTX usually links shapes or text, adding it to the `shape` definition (or globally to all elements via `additionalProperties` or similar) is easiest. Let's add it to `shape` (rect, ellipse, triangle, textbox) as an optional `"link": {"type": "string"}`.

2. **Frontend UI (`index.html` & `editor.js`)**:
   - Add a `<label>Link <input type="url" id="p-link"></label>` to `aside#props` in `index.html`.
   - Update `editor.js` to read/write this `link` property from the element's dataset.
   - Add a "Download HTML" button in `index.html` (e.g. `<button type="button" id="b-export-html">Download HTML</button>`) next to the "Export PPT" button.

3. **HTML Export Logic (`editor.js`)**:
   - Implement the `exportHTML()` function tied to the new "Download HTML" button.
   - The export must bundle the `div#stage` contents into a standalone HTML string (including necessary CSS from `style.css` or inline styles for absolute positioning).
   - Elements that have a `link` property should be wrapped in an `<a>` tag or have an `onclick` event to navigate to the link when clicked in the exported HTML.
   - Trigger a browser download of `presentation.html`.

## Guidelines
- Follow the single-source-of-truth geometry rules in `editor.js`.
- Make sure the exported HTML visually matches the canvas (absolute positioning, correct colors, z-index).
- Adhere strictly to the write_scope. Do not touch backend python files unless necessary (they shouldn't be, as schema.json drives validation).
