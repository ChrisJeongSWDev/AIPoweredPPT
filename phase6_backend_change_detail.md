# Phase 6 Backend — transparency, multipart API, media rendering — change detail (APPLIED)

Mode: continuation. All edits below were written to disk successfully in this session, to the three
files in `write_scope`, under the path the brief's CRITICAL INSTRUCTION named:
`.editwork/tasks/AI_Powered_PPT/src/aippt/canvas/...` (see caveat 1 on why that path was used
as-is here, unlike phase5/phase6_sub1's `.editwork` discrepancy).

Target files (all under `.editwork/tasks/AI_Powered_PPT/src/aippt/canvas/`):
- `style.py`
- `app.py`
- `render_canvas.py`

---

## `style.py`

1. Added `from lxml import etree` (brief-mandated import for element construction).
2. Added `_split_alpha(color) -> (hex6, alpha_val | None)`: splits an 8-digit `#RRGGBBAA` into the
   opaque 6-digit color and an alpha value out of 100000
   (`round(int(alpha_hex, 16) / 255.0 * 100000)`), or returns `(hex6, None)` for a plain 6-digit
   color. Centralizes the hex-pair math the brief specifies so `rgb()` and the new alpha injector
   share one conversion.
3. `rgb()` now routes through `_split_alpha()` and discards the alpha half — `RGBColor.from_string`
   only ever receives 6 hex digits, so no existing caller (fonts, run colors, connectors) changes
   behavior for 6-digit input.
4. Added `apply_alpha(solid_fill_el, color)`: if `color` carries an alpha byte, finds the
   `<a:srgbClr>` child of the given `<a:solidFill>` element and appends (or idempotently replaces)
   an `<a:alpha val="...">` child on that color element via `etree.SubElement`. **Deviation from the
   brief's literal wording, made deliberately**: the brief says to append `<a:alpha>` "inside
   `solidFill`", but per ECMA-376 (`CT_Color`/`EG_ColorTransform`), `<a:alpha>` is a transform on the
   *color choice child* (`<a:srgbClr>`), not a direct sibling of `<a:solidFill>` — appending it
   directly under `<a:solidFill>` is well-formed XML that PowerPoint silently ignores (no
   transparency renders at all). Placing it on `<a:srgbClr>` is what actually produces visible
   transparency, which is the point of the feature; this is documented at the call site and in
   `apply_alpha`'s docstring in case a reviewer expected the literal reading.
5. `apply_fill()`: after setting the solid color, calls
   `apply_alpha(shp._element.spPr.find(qn("a:solidFill")), fill)` — the shape fill's `<a:solidFill>`
   is a direct child of `<a:spPr>` (a sibling of `<a:ln>`), so this cannot pick up the line's fill by
   accident.
6. `apply_line()`: after setting stroke color/width, calls
   `apply_alpha(shp._element.spPr.find(qn("a:ln")).find(qn("a:solidFill")), stroke["color"])` — the
   line's `<a:solidFill>` lives *inside* `<a:ln>`, so it's located via `<a:ln>` first, not at spPr's
   top level. `<a:ln>` is guaranteed present at this point because accessing `shp.line.color` (the
   line above) already lazily created it.
7. No signature changes to `apply_fill`/`apply_line`/`draw_shape`/`rgb` — all existing call sites
   (including `add_runs`'s `run.font.color.rgb = rgb(r["color"])`) are unaffected; an 8-digit color
   passed to a run's font color would silently drop its alpha (run-level alpha was not requested by
   the brief, and DrawingML text alpha is a different, unrelated element).

## `app.py`

1. Added imports: `shutil`, `tempfile`, and `UploadFile` from `fastapi`.
2. `MAX_BODY_BYTES` changed from `2 * 1024 * 1024` to `50 * 1024 * 1024`, per the brief. This
   constant is shared with `/api/generate`'s `_read_json()` guard, so that endpoint's ceiling rises
   too (the brief did not ask for a second, separate constant, and introducing one wasn't judged
   necessary — no known caller sends a `/api/generate` prompt anywhere close to either ceiling).
3. **`/api/export` (POST, JSON in, .pptx out) was renamed to `/api/download` and rewritten to accept
   `multipart/form-data`** instead of a JSON body. See caveat 2 — the brief describes changing "the
   POST `/api/download` endpoint" as if it already existed; the only existing endpoint with that
   shape (canvas-ir/1 in, `.pptx` bytes out, `Content-Disposition: attachment`) was `/api/export`, so
   it was renamed rather than left in place alongside a new, separate route.
   - Reads the IR JSON from form field `"ir"` (handles both a plain text field, which arrives as
     `str`, and one sent as a Blob/file part, which arrives as `UploadFile` — `await field.read()` in
     the latter case).
   - Every other form part is treated as an uploaded media file: `form.multi_items()` is walked,
     skipping the `"ir"` field and any non-`UploadFile` value, and each remaining upload is written
     to `Path(tempfile.mkdtemp(prefix="aippt-media-")) / Path(upload.filename).name` — `.name` strips
     any directory components the browser/client sent, so a filename cannot escape the temp
     directory it's confined to.
   - Builds `media_map: dict[str, str]` = `{uploaded filename: temp file path}` and passes it to
     `render(ir, media_map=media_map)`.
   - The temp directory is removed (`shutil.rmtree(..., ignore_errors=True)`) in a `finally` block
     that wraps both the `render()` call and `prs.save(buf)` — so it's cleaned up whether rendering
     succeeds, fails with a mapped error (`StalePayloadError`/`CanvasValidationError`/
     `TemplatePinError`), or raises something unmapped.
   - The existing size check (`Content-Length` header vs `MAX_BODY_BYTES`) is still run up front. See
     caveat 3 on why there is no second, post-parse size check here the way `_read_json()` has one
     for JSON bodies.
   - Error-mapping order (StalePayloadError before its parent CanvasValidationError,
     TemplatePinError logged as a 500) is unchanged from the old `/api/export`.
4. Updated the module docstring's "THE SERVER WRITES NO FILES" paragraph — that claim is no longer
   true for `/api/download` — to say the *rendered deck* is still never written to disk, and added a
   new paragraph explaining that uploaded media *is* written, but only to a per-request temp
   directory that's removed once the response is built.
5. `/api/generate` and everything else in the file is untouched.

## `render_canvas.py`

1. Added `from aippt.canvas.geometry import emu` (needed by the two new draw functions below; this
   module did not previously import `emu` itself — `style.py` and `connectors.py` already do).
2. Added `draw_image(slide, el, media_map)`: computes `left/top/width/height` via `emu()`, looks up
   `media_map.get(el["src"])`, and calls
   `slide.shapes.add_picture(path, left, top, width, height)`. Raises `ValueError` with the element's
   `id`/`src` if no upload matches — chosen over silently skipping the element or passing `None`
   straight to `add_picture` (which would raise a much less legible `TypeError` from inside
   python-pptx/Pillow).
3. Added `draw_video(slide, el, media_map)`: same geometry lookup, calls
   `slide.shapes.add_movie(path, left, top, width, height, poster_frame_image=None)` per the brief.
   Same `ValueError` guard as `draw_image`. `poster_frame_image=None` is literal per the brief;
   schema.json's `video` def (added in phase6_sub1) has no field to carry a poster image yet.
4. `draw(slide, el, media_map)` — signature changed from `draw(slide, el)`. Dispatches `"connector"`
   to `draw_connector` (unchanged), `"image"`/`"video"` to the two new functions, and everything else
   (`"rect"`/`"ellipse"`/`"triangle"`/`"textbox"`) to `draw_shape` (unchanged), same as before.
5. `render(ir, media_map=None)` — new keyword parameter, typed `dict[str, str] | None = None` per
   this codebase's existing Optional-typing convention (e.g. `style.py`'s
   `text: dict[str, Any] | None`), rather than the brief's literal `dict[str, str] = None` (which
   would be a type-checker error under `from __future__ import annotations` + strict mode). Defaults
   to `{}` internally so `draw()`'s signature can stay non-Optional. The CLI's `main()` still calls
   `render(ir)` with no `media_map` — a CLI deck containing an `image`/`video` element will raise
   `ValueError` from `draw_image`/`draw_video` (no upload mechanism exists for the CLI path; out of
   scope for this brief, which only asked for multipart handling in `app.py`).

---

## Verification plan (NOT executed — see caveat 4)

```
pip install -e ".[editor,dev]"
python -m aippt.canvas.render_canvas some_deck_with_image.json -o out.pptx   # expect ValueError (no media_map)
python -m aippt.canvas.app   # then POST a multipart/form-data request with "ir" + a file field to /api/download
python -m pytest -q
```

## Out-of-scope / caveats

1. **`.editwork` path was used as the brief instructed, and it was NOT empty.** Phase 5 and
   phase6_sub1's change-detail files both recorded a discrepancy where `.editwork`'s `tasks/`
   directory was empty (only `.gitkeep`) and the edit was redirected to the real repo tree instead.
   That was **not** the case for this task: `.editwork/tasks/AI_Powered_PPT/src/aippt/canvas/`
   contained real, current files — byte-identical in size and timestamp to the same files under the
   real tree (`tasks/AI_Powered_PPT/src/aippt/canvas/`), including phase6_sub1's `schema.json`
   changes (image/video defs, alpha-capable color pattern). Whatever sync step closed the earlier gap
   (the repo's recent commit history includes several "Local: sync ... to MultiAgent Source"
   commits) appears to have already run before this task started. All three edits were applied only
   under the `.editwork` path per the CRITICAL INSTRUCTION; the real tree's copies were read for
   reference (schema.json, validate.py) but never written.

2. **"the POST `/api/download` endpoint" did not exist before this change — `/api/export` was
   renamed to it.** No route named `/api/download` existed anywhere in the repo (checked via
   grep across `tasks/AI_Powered_PPT`), and the frontend (`static/editor.js`) still calls
   `fetch('/api/export', ...)` with a JSON body. `editor.js`/`index.html` are not in `write_scope` for
   this brief, so they were left untouched — meaning **the editor's existing "export" button is now
   broken against this backend** until a future phase updates it to POST multipart to
   `/api/download` with an `"ir"` field. Flagging this explicitly since it's a behavior change with
   no corresponding frontend update in this task's scope.

3. **No post-parse total-size check on the multipart body**, unlike `_read_json()`'s two-layer check
   for JSON (`Content-Length` header, then actual buffered length). Starlette's `Request.form()`
   parses and spools multipart parts internally (large parts go to temp files automatically) before
   this code sees any of it, so there is no single "raw bytes read so far" value to compare against
   `MAX_BODY_BYTES` the way the JSON path does. The `Content-Length` header check still runs up
   front and rejects any request that *declares* an oversized body; a chunked request that lies about
   its length (declares small, sends large) would not be caught until `python-multipart` (or memory)
   protests. Adding a manual streaming byte-counter around `request.form()` was judged more machinery
   than this brief asked for; noting it here as a known gap rather than silently shipping it.

4. **`python-multipart` is required for `Request.form()` and is not currently declared as a
   dependency.** `pyproject.toml`'s `[editor]` extra lists only `fastapi`/`uvicorn`; FastAPI's
   multipart form parsing needs the separate `python-multipart` package installed, or
   `await request.form()` raises at request time. `pyproject.toml` is not in this brief's
   `write_scope`, so it was not edited — flagging so a future phase (or whoever wires up
   `[editor]`) adds `python-multipart` to it.

5. **Command execution was unavailable for this worker.** Every `python`/`pip` invocation (via
   both Bash and PowerShell) came back "requires approval" with no prompt able to surface in this
   non-interactive session — including a plain `python -m py_compile` syntax check. All three edits
   were instead verified by re-reading each full file after editing: checking import correctness
   (added `emu`, `etree`, `UploadFile`, `shutil`, `tempfile`), signature threading (`media_map` passed
   consistently from `render()` → `draw()` → `draw_image`/`draw_video`), and cross-referencing
   python-pptx's actual internal structure (`CT_Shape.spPr`, `LineFormat`/`FillFormat`'s
   `from_fill_parent` lazily creating `<a:ln>`) from memory rather than by importing and inspecting
   the installed library. This was not confirmed by running the renderer or its test suite.
