import os
import re

app_py_path = "src/aippt/canvas/app.py"
render_py_path = "src/aippt/canvas/render_canvas.py"
req_path = "requirements.txt"

# 1. Update requirements.txt
with open(req_path, "r", encoding="utf-8") as f:
    reqs = f.read()
if "python-multipart" not in reqs:
    reqs += "\npython-multipart>=0.0.9\n"
    with open(req_path, "w", encoding="utf-8") as f:
        f.write(reqs)

# 2. Update render_canvas.py
with open(render_py_path, "r", encoding="utf-8") as f:
    r_code = f.read()

r_code = r_code.replace(
    "def render_append(ir: dict[str, Any], target_bytes: bytes) -> Presentation:",
    "def render_append(ir: dict[str, Any], target_bytes: bytes, media_map: dict[str, str] | None = None) -> Presentation:"
)
r_code = r_code.replace(
    "        draw(slide, el)",
    "        draw(slide, el, media_map)"
)

with open(render_py_path, "w", encoding="utf-8") as f:
    f.write(r_code)

# 3. Update app.py
with open(app_py_path, "r", encoding="utf-8") as f:
    a_code = f.read()

# Add imports if missing
if "import tempfile" not in a_code:
    a_code = a_code.replace("import urllib.parse", "import urllib.parse\nimport tempfile\nimport shutil")
if "UploadFile" not in a_code:
    a_code = a_code.replace("Request, Response", "Request, Response, UploadFile")

# Add _read_multipart_ir function before _read_json
multipart_func = """
async def _read_multipart_ir(request: Request) -> tuple[Any, dict[str, str] | None, JSONResponse | None, str | None]:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return None, None, _too_large(), None

    try:
        form = await request.form()
    except Exception as exc:
        return None, None, JSONResponse({"error": "malformed", "detail": f"body is not valid multipart/form-data: {exc}"}, status_code=400), None

    ir_field = form.get("ir")
    if ir_field is None:
        return None, None, JSONResponse({"error": "validation", "detail": 'the form must include a field named "ir"'}, status_code=422), None
    
    ir_raw = await ir_field.read() if isinstance(ir_field, UploadFile) else ir_field.encode("utf-8")

    try:
        ir = json.loads(ir_raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, None, JSONResponse({"error": "malformed", "detail": f'the "ir" field is not valid UTF-8 JSON: {exc}'}, status_code=400), None

    tmp_dir = tempfile.mkdtemp(prefix="aippt-media-")
    media_map: dict[str, str] = {}
    for name, value in form.multi_items():
        if name == "ir" or not isinstance(value, UploadFile):
            continue
        filename = Path(value.filename or name).name
        dest = Path(tmp_dir) / filename
        dest.write_bytes(await value.read())
        media_map[filename] = str(dest)
        
    return ir, media_map, None, tmp_dir

"""

if "_read_multipart_ir" not in a_code:
    a_code = a_code.replace("async def _read_json", multipart_func + "\nasync def _read_json")

# Replace api_export with api_download
old_export = """@app.post("/api/export")
async def api_export(request: Request) -> Response:
    \"\"\"canvas-ir/1 in, .pptx bytes out. In memory, start to finish.

    The error mapping is the whole job, and the ORDER of the except clauses is the load-bearing
    part: StalePayloadError SUBCLASSES CanvasValidationError, so catching the parent first would
    report every stale payload as a 422 and tell the user to fix a deck that is perfectly fine. It
    is caught first, and it stays first.
    \"\"\"
    ir, err = await _read_json(request)
    if err is not None:
        return err

    try:
        prs = render(ir)  # validates, checks the pin, checks the SHA, draws
    except StalePayloadError as exc:  # MUST precede CanvasValidationError -- it is a subclass
        return JSONResponse({"error": "stale", "detail": str(exc)}, status_code=409)
    except CanvasValidationError as exc:
        return JSONResponse({"error": "validation", "detail": str(exc)}, status_code=422)
    except TemplatePinError as exc:
        # Unreachable if the startup gate ran -- the template cannot drift mid-process without
        # someone editing it underneath us. Log it loudly rather than pretend it cannot happen.
        log.exception("template pin failed at REQUEST time; the startup gate should have caught it")
        return JSONResponse({"error": "template", "detail": str(exc)}, status_code=500)

    buf = io.BytesIO()
    prs.save(buf)  # in memory. No temp file, no output directory, nothing on disk.

    return Response(
        content=buf.getvalue(),
        media_type=PPTX_MIME,
        headers={"Content-Disposition": content_disposition(ir.get("title", ""))},
    )"""

new_download = """@app.post("/api/download")
async def api_download(request: Request) -> Response:
    ir, media_map, err, tmp_dir = await _read_multipart_ir(request)
    if err is not None:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return err

    try:
        try:
            prs = render(ir, media_map=media_map)
        except StalePayloadError as exc:
            return JSONResponse({"error": "stale", "detail": str(exc)}, status_code=409)
        except CanvasValidationError as exc:
            return JSONResponse({"error": "validation", "detail": str(exc)}, status_code=422)
        except TemplatePinError as exc:
            log.exception("template pin failed at REQUEST time")
            return JSONResponse({"error": "template", "detail": str(exc)}, status_code=500)

        buf = io.BytesIO()
        prs.save(buf)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return Response(
        content=buf.getvalue(),
        media_type=PPTX_MIME,
        headers={"Content-Disposition": content_disposition(ir.get("title", ""))},
    )"""

a_code = a_code.replace(old_export, new_download)

old_append = """@app.post("/api/append_slide")
async def api_append_slide(request: Request) -> Response:
    ir, err = await _read_json(request)
    if err is not None:
        return err

    target_b64 = ir.get("target", {}).get("target_pptx_b64")
    if not target_b64:
        return JSONResponse({"error": "missing_target", "detail": "Target PPTX base64 missing."}, status_code=400)
    
    # Remove it from IR to not confuse validate()
    del ir["target"]["target_pptx_b64"]
    
    target_bytes = base64.b64decode(target_b64)

    try:
        from aippt.canvas.render_canvas import render_append
        prs = render_append(ir, target_bytes)
    except StalePayloadError as exc:
        return JSONResponse({"error": "stale", "detail": str(exc)}, status_code=409)
    except CanvasValidationError as exc:
        return JSONResponse({"error": "validation", "detail": str(exc)}, status_code=422)
    except TemplatePinError as exc:
        log.exception("template pin failed at REQUEST time; the startup gate should have caught it")
        return JSONResponse({"error": "template", "detail": str(exc)}, status_code=500)

    buf = io.BytesIO()
    prs.save(buf)  # in memory. No temp file, no output directory, nothing on disk.

    return Response(
        content=buf.getvalue(),
        media_type=PPTX_MIME,
        headers={"Content-Disposition": content_disposition(ir.get("title", ""))},
    )"""

new_append = """@app.post("/api/append_slide")
async def api_append_slide(request: Request) -> Response:
    ir, media_map, err, tmp_dir = await _read_multipart_ir(request)
    if err is not None:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return err

    target_b64 = ir.get("target", {}).get("target_pptx_b64")
    if not target_b64:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return JSONResponse({"error": "missing_target", "detail": "Target PPTX base64 missing."}, status_code=400)
    
    del ir["target"]["target_pptx_b64"]
    target_bytes = base64.b64decode(target_b64)

    try:
        try:
            from aippt.canvas.render_canvas import render_append
            prs = render_append(ir, target_bytes, media_map=media_map)
        except StalePayloadError as exc:
            return JSONResponse({"error": "stale", "detail": str(exc)}, status_code=409)
        except CanvasValidationError as exc:
            return JSONResponse({"error": "validation", "detail": str(exc)}, status_code=422)
        except TemplatePinError as exc:
            log.exception("template pin failed at REQUEST time")
            return JSONResponse({"error": "template", "detail": str(exc)}, status_code=500)

        buf = io.BytesIO()
        prs.save(buf)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return Response(
        content=buf.getvalue(),
        media_type=PPTX_MIME,
        headers={"Content-Disposition": content_disposition(ir.get("title", ""))},
    )"""

a_code = a_code.replace(old_append, new_append)

with open(app_py_path, "w", encoding="utf-8") as f:
    f.write(a_code)
print("PATCH SUCCESSFUL")
