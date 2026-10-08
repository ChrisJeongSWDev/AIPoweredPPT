# Phase 6: Media & Advanced UX (Draft Brief)

## Objective
Implement Phase 6: Video/Image insertion, Copy/Paste, Multi-selection alignment, 1pt borders, and transparency.

## Target Repo
C:/Users/2021670/Documents/멀티 에이전트

## Write Scope
- tasks/AI_Powered_PPT/src/aippt/canvas/schema.json
- tasks/AI_Powered_PPT/src/aippt/canvas/style.py
- tasks/AI_Powered_PPT/src/aippt/canvas/app.py
- tasks/AI_Powered_PPT/src/aippt/canvas/render_canvas.py
- tasks/AI_Powered_PPT/src/aippt/canvas/static/index.html
- tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js

## Requirements
1. **Schema Updates (`schema.json`)**:
   - Update `color` pattern to `^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$` to allow alpha channel.
   - Remove the restriction in `stroke` description that bans alpha.
   - Add new `image` and `video` types to the `element` definition. They must have `id, type, x, y, w, h` and a way to identify the media (e.g. `mediaId` mapping to the multipart form, or `src` as base64).

2. **Backend Rendering (`render_canvas.py`, `style.py`, `app.py`)**:
   - `app.py`: The `/api/download` endpoint must accept `multipart/form-data` instead of just JSON so the browser can send large video/image blobs along with the JSON IR. Increase MAX_BODY_BYTES to 50MB.
   - `style.py`: Update `rgb(color: str)` to parse the 8-character hex code and apply the alpha channel `<a:alpha val="..."/>` to the `solidFill` XML tag.
   - `render_canvas.py`: Handle `image` using `slide.shapes.add_picture(...)` and `video` using `slide.shapes.add_movie(...)`.

3. **Frontend Editor (`index.html`, `editor.js`)**:
   - `index.html`: Add `Image` and `Video` buttons to the toolbar. Add a hidden `<input type="file" accept="image/*,video/*">`. Add Align buttons (Top, Bottom, Center, etc.). Add Opacity slider and Border (1pt) toggle to the properties panel.
   - `editor.js`:
     - **Media Loading**: Read dropped or selected files, create Blob URLs, render them on the `<div id="stage">` as `<img class="el">` or `<video class="el">`. Keep the original files in a `Map` to be sent to the backend.
     - **Copy/Paste**: Add a `keydown` listener for `Ctrl+C` / `Ctrl+V`. Duplicate the selected element(s), shift `x, y` by +10, assign a new ID, and push an undo state.
     - **Multi-select & Alignment**: Modify the selection logic to support array-based multi-selection (Shift-Click). Implement alignment logic that calculates the bounding box and aligns the chosen axis.
     - **Export**: When downloading JSON, base64 encode the media? Or just skip media? When exporting PPTX via `/api/download`, construct a `FormData` object containing the `deck.json` IR and the media files, and POST it.

## Verification
- Backend tests should pass with the new schema.
- Frontend should not use BANNED APIs (`getBoundingClientRect`, etc.).
