---
target_repo: C:/Users/2021670/Documents/멀티 에이전트
claude_model: opus
write_scope:
  - tasks/AI_Powered_PPT/src/aippt/canvas/schema.json
  - tasks/AI_Powered_PPT/src/aippt/canvas/style.py
  - tasks/AI_Powered_PPT/src/aippt/canvas/render_canvas.py
  - tasks/AI_Powered_PPT/src/aippt/canvas/app.py
change_detail_path: tasks/AI_Powered_PPT/phase6_part1_change_detail.md
---
# Phase 6 (Part 1): Backend Media & Styling Support

## CRITICAL INSTRUCTION FOR WORKER
You are running within a dispatcher environment. The dispatcher has created an isolated workspace at `.editwork`. 
You MUST apply your edits to the files inside `.editwork/tasks/AI_Powered_PPT/...`.
DO NOT edit the files directly in the real repo.

## Objective
Update the `canvas-ir/1` schema and the Python backend (`app.py`, `render_canvas.py`, `style.py`) to support Video/Image rendering, 8-character hex colors (alpha/transparency), and multipart/form-data API.

## Requirements

### 1. `src/aippt/canvas/schema.json`
- Update the `color` definition pattern to allow an optional 2-character hex alpha channel at the end: `^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$`.
- Remove the text banning alpha from the `color` and `stroke` descriptions.
- Add `image` and `video` types to the `element` definition.
  - They should require: `id, type, x, y, w, h, src`.
  - `src` is a string (e.g., a filename or key corresponding to the multipart upload).
  - Add them to the `oneOf` array in `$defs/element`.

### 2. `src/aippt/canvas/style.py`
- Update `rgb(color: str)` or related logic to handle 8-character hex codes.
- PowerPoint uses `<a:solidFill>` with an optional `<a:alpha val="..."/>` child where `val` is a percentage of 100,000 (e.g., 50% is 50000).
- If an 8-character hex color is provided (e.g. `#FF003280`), extract the alpha channel (e.g., `80` in hex is 128 -> ~50.2% opacity), and inject the `<a:alpha>` tag into the shape's fill or stroke properties using `lxml` where appropriate.

### 3. `src/aippt/canvas/app.py`
- Modify `/api/download` to accept `multipart/form-data` instead of just a raw JSON body.
- Increase `MAX_BODY_BYTES` to `50 * 1024 * 1024` (50MB) to allow video uploads.
- The endpoint should expect a form field named `ir` containing the `deck.json` string, and optionally multiple file fields (e.g. `media_01.mp4`).
- Save the uploaded media files to temporary files (using `tempfile`), pass their paths to `render_canvas.py` (you may need to pass a dict mapping `src` to the temporary file path), and clean them up after the PPTX is generated.

### 4. `src/aippt/canvas/render_canvas.py`
- Update `render()` to accept a `media_map: dict[str, str]` (mapping the IR `src` to a local temporary file path).
- Implement rendering for `image` elements using `slide.shapes.add_picture(image_path, x, y, w, h)`.
- Implement rendering for `video` elements using `slide.shapes.add_movie(video_path, x, y, w, h, poster_frame_image=None)`.

Ensure your changes are robust and pass validation. Output `phase6_part1_change_detail.md` detailing the changes.
