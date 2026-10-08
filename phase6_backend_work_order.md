---
target_repo: C:/Users/2021670/Documents/멀티 에이전트
claude_model: sonnet
write_scope:
  - tasks/AI_Powered_PPT/src/aippt/canvas/style.py
  - tasks/AI_Powered_PPT/src/aippt/canvas/app.py
  - tasks/AI_Powered_PPT/src/aippt/canvas/render_canvas.py
change_detail_path: tasks/AI_Powered_PPT/phase6_backend_change_detail.md
---
# Phase 6 Backend: Transparency, Multipart API, and Media Rendering

## CRITICAL INSTRUCTION
You MUST apply your edits to `.editwork/tasks/AI_Powered_PPT/src/aippt/canvas/...`. DO NOT edit the real repo directly.

## Task
1. **`style.py`**:
   - Update `rgb(color: str)` or logic using it. If the color string is 8 characters long (e.g. `#FF003280`), the last two characters represent alpha (00-FF).
   - In PowerPoint, transparency is applied by adding an `<a:alpha val="..."/>` tag inside `<a:solidFill>`.
   - `val` is out of 100000. So `alpha_val = int((int(alpha_hex, 16) / 255.0) * 100000)`.
   - Update `style.py` to parse this alpha and inject the `<a:alpha>` tag into fills and strokes where applicable using `lxml` (e.g., `from lxml import etree`, find the `solidFill` or `ln` element, and append `<a:alpha val="..."/>` if alpha is present). Keep it robust.

2. **`app.py`**:
   - Change the POST `/api/download` endpoint to accept `multipart/form-data`.
   - Update `MAX_BODY_BYTES = 50 * 1024 * 1024` (50MB).
   - Read the IR JSON from a form field named `ir`.
   - Handle any uploaded media files in the form data. Save them to a temporary directory using `tempfile`.
   - Pass a mapping of the uploaded filenames to their temporary file paths into the `render()` function (e.g., `media_map`).

3. **`render_canvas.py`**:
   - Update `render()` to accept `media_map: dict[str, str] = None` which maps `src` values to local temp file paths.
   - For `element["type"] == "image"`, call `slide.shapes.add_picture(media_map.get(element["src"]), x, y, w, h)`.
   - For `element["type"] == "video"`, call `slide.shapes.add_movie(media_map.get(element["src"]), x, y, w, h, poster_frame_image=None)`.
