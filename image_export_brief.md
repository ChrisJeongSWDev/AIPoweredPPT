---
mode: edit
claude_model: sonnet
target_repo: c:/Users/2021670/Documents/멀티 에이전트
write_scope: tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js, tasks/AI_Powered_PPT/src/aippt/canvas/render_canvas.py, tasks/AI_Powered_PPT/src/aippt/canvas/style.py
change_detail_path: tasks/AI_Powered_PPT/image_export_change_detail.md
approved_write_manifest: tasks/AI_Powered_PPT/image_export_write_manifest.txt
---

# Task Description
The user reported an error when exporting a deck with an image: `KeyError: 'image'`.
This occurs because the frontend (`editor.js`) sends `{"type": "image", "src": "photo-1.jpg"}` in the JSON IR, but the backend (`style.py`) does not implement `image` handling, nor does it receive the actual image bytes.

You must implement the following changes exactly as described below:

## 1. Frontend: Base64 Encode Image `src` in `editor.js`
In `tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js`, modify the `$('b-export').addEventListener('click', ...)` function.
Before calling `var res = await fetch('/api/export', { method: 'POST', body: JSON.stringify(ir) });`, you must traverse `ir.elements` and convert any `image` element's `src` from a filename (e.g. `photo-1.jpg`) into a Base64 Data URI (`data:image/mime;base64,...`).

**Implementation Details:**
- You can use the existing `fileToBase64(file)` helper function.
- `window.uploadedMedia[el.src]` contains `{ file: File, url: ... }`. Use `fileToBase64(file)`.
- Use `await Promise.all(...)` to asynchronously fetch all base64 data for image elements, just like it is done in `generate()` for `/api/generate`.
- Replace `el.src` with `"data:" + media.file.type + ";base64," + data;`.
- If an element's `src` is not in `window.uploadedMedia`, the existing `missing` media check already catches it and aborts the export, so you don't need to worry about missing files in the translation step.

## 2. Backend: Implement `draw_image` in `style.py`
In `tasks/AI_Powered_PPT/src/aippt/canvas/style.py`:
- Import `io` and `base64`.
- Implement a new function `draw_image(slide: Any, el: dict[str, Any]) -> Any`:
  ```python
  import io
  import base64

  def draw_image(slide: Any, el: dict[str, Any]) -> Any:
      left, top = emu(el["x"]), emu(el["y"])
      width, height = emu(el["w"]), emu(el["h"])
      
      src = el.get("src", "")
      if src.startswith("data:"):
          # format: data:image/png;base64,iVBOR...
          header, b64 = src.split(",", 1)
          img_data = base64.b64decode(b64)
          img_io = io.BytesIO(img_data)
          shp = slide.shapes.add_picture(img_io, left, top, width, height)
      else:
          raise ValueError(f"Unsupported image src format for element {el['id']}")
      
      shp.name = el["id"]
      shp.rotation = float(el.get("rotation") or 0.0)
      return shp
  ```

## 3. Backend: Route `image` in `render_canvas.py`
In `tasks/AI_Powered_PPT/src/aippt/canvas/render_canvas.py`:
- In the `draw(slide: Any, el: dict[str, Any]) -> Any` function, add a branch for `el["type"] == "image"`.
- Import `draw_image` from `.style` and call it.
  ```python
  def draw(slide: Any, el: dict[str, Any]) -> Any:
      if el["type"] == "connector":
          return draw_connector(slide, el)
      elif el["type"] == "image":
          from .style import draw_image
          return draw_image(slide, el)
      return draw_shape(slide, el)
  ```

# Rules
- Do NOT implement video support. Focus strictly on `image`.
- Do NOT use `app.py` or modify `/api/export` to use `multipart/form-data`. The Base64 approach is explicitly chosen.
- Make sure to document your changes in `tasks/AI_Powered_PPT/image_export_change_detail.md`.
