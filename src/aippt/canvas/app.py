#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The same-origin editor server. Plan Sec 9, Phase 1C tasks 3.1-3.3, pulled forward into 1B.

    python -m aippt.canvas.app        # -> http://127.0.0.1:8000

THIS IS AN ADAPTER, NOT A SECOND RENDERER. It owns exactly two things the CLI does not: it serves
the editor's static files same-origin, and it hands a JSON body to render_canvas.render(). Every
rule it appears to enforce -- the schema, the reserved regions, the accent1 ban, the template pin --
is enforced by the frozen backend; this module only maps the resulting exception onto an HTTP status
a browser can act on. If this file and the CLI ever disagree about the same payload, the bug is
here.

THE CLI STAYS FIRST-CLASS (task 3.3). Corporate IT blocks localhost servers often enough that
`python -m aippt.canvas.render_canvas deck.json -o out.pptx` is the fallback that always works. So
the dependency arrow points one way only: app.py imports the canvas package, and NOTHING under
canvas/ imports app.py. FastAPI stays an OPTIONAL extra (`pip install -e ".[editor]"`) and the
renderer installs and runs without it.

THE SERVER WRITES NO FILES FOR RENDERING. prs.save() goes to a BytesIO. There is no temp directory,
no output path, and no filename taken from the payload -- `target.template` is informational and is
ignored (schema.json says so in as many words). Honouring a path from the body would be an
arbitrary-file read, which is precisely the hole task 3.2 exists to close.

AI_PPT_v2 PHASE 4 ADDS THE ONE EXCEPTION: /api/designs. A user-named canvas-ir/1 deck is written to
SAVED_DECKS_DIR, a single fixed directory next to this file -- never a path the request chooses. The
name is validated against a strict allowlist before it ever reaches Path() (_validate_design_name /
_design_path below), so this remains not an arbitrary-file write: the caller picks a filename stem
inside one sandboxed folder and nothing else about the path.

/api/generate HAS TWO MODES, AND THE ENVIRONMENT PICKS ONE (Phase 4; repointed at a headless CLI
worker by the CliWorkerClient migration). Without AIPPT_LIVE_MODE=1 it is the Phase 3 MOCK: it
calls no model, reaches no network, and reads nothing from the prompt -- one hardcoded canvas-ir/1
deck, 1.5 s late. With AIPPT_LIVE_MODE=1 it is the LIVE author: it reads the prompt, calls a
locally-authenticated claude/codex CLI through CliWorkerClient.complete_json()
(aippt.adapters.ai_adapter -- no API key, no HTTP), and assembles the reply into a deck. Either way
the editor's request shape, its loading state, its failure paths and its hand-off to loadIR() are
identical, and either way the deck goes through validate() before it answers -- a mock that ships an
invalid deck would prove the wiring works while quietly breaking the only thing the wiring carries,
and a model is exactly the author most likely to put a box on the logo. The mode is read at REQUEST
time (server_mode()), so the same process serves whichever the environment says.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import io
import json
import logging
import os
import re
import unicodedata
import urllib.parse
import tempfile
import shutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

LIVE_LOG_PATH = Path(__file__).resolve().parents[3] / "artifacts" / "multiagent_live.log"
LIVE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

from fastapi import FastAPI, Request, Response, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from aippt.adapters.ai_adapter import CliWorkerClient, CliWorkerError
from aippt.canvas.geometry import CANVAS
from aippt.canvas.pin import TemplatePinError, load_pin, verify_pin
from aippt.canvas.render_canvas import render
from aippt.canvas.style import BRAND_RED, EA, FORBIDDEN, LATIN
from aippt.canvas.validate import CanvasValidationError, SCHEMA_PATH, StalePayloadError, validate

log = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).with_name("static")

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

# A one-slide deck of boxes and arrows is a few KB of JSON. Anything approaching a megabyte is a
# mistake or an attack, and either way the renderer should not be the thing that discovers it.
# Note: Increased to 50MB to support the Add Slide To feature (sending target PPTX as base64 in JSON).
MAX_BODY_BYTES = 50 * 1024 * 1024

DEFAULT_STEM = "deck"

# The latency an LLM call would cost, simulated. It is not padding: the editor's loading state is
# real UI with a real failure mode (a button you can press twice), and a mock that answered
# instantly would never exercise it. It is spent ONLY on the success path -- a malformed request is
# refused immediately, because no model would have been called for that one either.
MOCK_LATENCY_S = 1.5

# Everything a filesystem, a Content-Disposition header or a shell could misread. The title is
# author-controlled text and it NEVER reaches the filesystem -- but it does reach a header and then
# a browser's Save dialog, so it is sanitized on the way out regardless.
_UNSAFE_STEM = re.compile(r'[\x00-\x1f\x7f"\\/:*?<>|]+')

# Phase 4: the live author. The ENVIRONMENT, not the code, chooses the mode -- AIPPT_LIVE_MODE=1
# means "call a real CLI worker"; absent (or anything else) means "serve the Phase 3 mock".

# --- the model allowlist (Phase 1; repointed at CliWorkerClient by the headless-worker migration) -
#
# THE CLIENT PICKS A PROFILE, NEVER A MODEL ID DIRECTLY. Everything the editor can ask for is a key
# of this dict, and the (backend, model) pair behind it -- the exact constructor arguments
# CliWorkerClient(backend=..., model=...) takes -- is chosen HERE, by the server. A body carrying
# "model": "gpt-9-ultra" (or "../../etc/passwd") is refused by membership before any subprocess ever
# runs, and re-pointing a profile at a different CLI model is a one-line server change that no
# browser has to hear about. `thinking` is published to the editor (see /api/context) as a UI hint
# only -- CliWorkerClient has no thinking-level knob of its own, unlike the google-genai client this
# replaced.
DEFAULT_PROFILE = "sonnet"

MODEL_PROFILES: dict[str, dict[str, str]] = {
    "sonnet": {
        "label": "Claude Sonnet 5", "thinking": "MEDIUM", "backend": "claude", "model": "sonnet",
    },
    "opus": {
        "label": "Claude Opus", "thinking": "HIGH", "backend": "claude", "model": "opus",
    },
    "gpt-5.6-terra": {
        "label": "GPT 5.6 Terra", "thinking": "HIGH", "backend": "codex", "model": "gpt-5.6-terra",
    },
    "gpt-5.6-sol": {
        "label": "GPT 5.6 Sol", "thinking": "HIGH", "backend": "codex", "model": "gpt-5.6-sol",
    },
}

# --- the image attachment limits (Phase 1) ------------------------------------------------------
#
# MAX_BODY_BYTES (2 MB) already caps the wire, but it caps the WRONG number: base64 expands 4:3, so
# the most that can arrive intact is ~1.5 MB decoded, and a caller who trips the body limit gets a
# 413 about a number they never chose. These caps are stated in the units the caller actually sent
# (a count of images, a total of decoded bytes) and are published in /api/context so the editor can
# refuse locally instead of discovering the limit by being refused.
#
# The count limit is NOT redundant with the byte limit: twenty 60 KB thumbnails fit under the byte
# ceiling comfortably and would still make one very slow, very expensive call.
MAX_BODY_BYTES = 100 * 1024 * 1024  # 100MB for PPTX/media attachments
MAX_IMAGES = 4
MAX_IMAGE_BYTES = 1_400_000

# The MIME types this server accepts and validates. Historically fed straight into the Gemini
# vision path; CliWorkerClient (the current live author -- see generate_live()) has no attachment
# parameter at all, so an accepted image is validated and then DISCARDED, never forwarded to the
# model. Kept EXACT after normalisation regardless -- never a `startswith("image/")` test, which
# would wave through image/svg+xml (an XML document with script in it) as an "image".
IMAGE_MIME_TYPES = ("image/png", "image/jpeg", "image/webp", "image/heic", "image/heif")

# Two spellings of the same field, in precedence order. The editor's own upload code and a former
# Gemini-SDK-shaped payload disagreed about the name ("mime" vs "mime_type"); both are still
# accepted here for compatibility, and a 422 over a synonym would be a cross-phase break with no
# user-visible cause. Both are read; `mime` is canonical downstream.
_MIME_KEYS = ("mime", "mime_type")

# The system instruction the live author injects. It is the SAME contract the Web-Gem workflow
# pastes into gemini.google.com, kept in one file so the two paths cannot drift. It lives at the
# project root: canvas/ -> aippt/ -> src/ -> <project root>.
PROMPT_PATH = Path(__file__).resolve().parents[3] / "GEM_Knowledge_API.md"

# Multi-agent live log (Phase 2/3): ai_adapter.py's CliWorkerClient mirrors the worker subprocess's
# stderr to this exact path in real time (see ai_adapter._run_cli) -- same "canvas/ -> aippt/ ->
# src/ -> project root" convention as PROMPT_PATH above, so both modules agree on the path without
# either importing the other's constant.
LIVE_LOG_PATH = Path(__file__).resolve().parents[3] / "artifacts" / "multiagent_live.log"


# --- server-side design storage (AI_PPT_v2 Phase 4) ---------------------------------------------
#
# THE ONE EXCEPTION TO "THE SERVER WRITES NO FILES FOR RENDERING", see the module docstring above.
# SAVED_DECKS_DIR is a single fixed directory next to this file -- never a path the request chooses
# -- and every name that reaches it is validated by _validate_design_name()/_design_path() below
# before Path() ever sees it, so this stays a sandboxed, allowlisted write, not an arbitrary one.
SAVED_DECKS_DIR = Path(__file__).with_name("saved_decks")
SAVED_DECKS_DIR.mkdir(exist_ok=True)

# The same forbidden-character set _UNSAFE_STEM strips out of a downloaded filename, but as an
# allowlist anchored end to end (^...$) rather than a strip-and-continue substitution: a design name
# that FAILS this match is refused outright with a 422, not silently mangled into something the
# caller never typed.
_SAFE_DESIGN_NAME = re.compile(r'^[^\x00-\x1f\x7f\\/:*?"<>|]{1,80}$')

# Windows reserves these device names AT THE FILESYSTEM LEVEL, regardless of extension: "CON.json"
# opens the console device exactly like "CON" does, so a save/load through SAVED_DECKS_DIR would
# either fail outright or silently miss the file entirely. Checked case-insensitively against the
# portion of the name before its FIRST '.' -- the same portion that ends up before the first '.' in
# the on-disk "<name>.json", which is what Windows actually looks at (a raw suffix like "my.con"
# is fine; the reserved word has to be the leading component, not a trailing one).
_RESERVED_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{d}" for d in "123456789"}
    | {f"LPT{d}" for d in "123456789"}
)


class LiveGenerateError(RuntimeError):
    """A live model call failed -- the mock path (AIPPT_LIVE_MODE unset) NEVER raises this.

    Carries a human reason the editor shows verbatim. Deliberately NOT a CanvasValidationError: a
    model that returns unusable text is an upstream (502) failure, not a user's invalid deck (422).
    """


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Both pin gates, ONCE, at process start -- never per request.

    TemplatePinError is deliberately NOT caught: an unverified template must stop the process from
    starting at all. A server that boots and then 500s on every export has told the operator the
    same thing far less clearly, and a server that quietly falls back to another layout has told
    them nothing at all and will ship a wrong-looking deck (pin.py's whole reason to exist).
    """
    pin = load_pin()
    verify_pin(pin)
    app.state.pin = pin
    log.info(
        "pin OK: %s @ %s",
        pin["renderer_template"]["filename"],
        pin["renderer_template"]["sha256"],
    )
    yield


app = FastAPI(
    title="aippt canvas editor",
    version="1",
    lifespan=lifespan,
    # No CORS middleware, on purpose. The editor is served from this same origin; a browser needs
    # no cross-origin grant to talk to it, and adding one would only widen who can.
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html; charset=utf-8")


@app.get("/api/context")
async def api_context(request: Request) -> dict[str, Any]:
    """Everything the editor must NOT hard-code.

    Chiefly the template SHA. If the editor carried a literal SHA, re-pinning the template -- a
    deliberate, reviewed act (Sec 4.3) -- would turn into a silent 409 for every user of every
    stale browser tab, and the fix would be "hard-refresh", which nobody would guess. Serving it
    keeps reference/template_pin.json the single source of truth on both sides of the wire.

    THE SAME ARGUMENT NOW COVERS THE MODEL PICKER AND THE ATTACHMENT LIMITS (Phase 1). A picker with
    hardcoded options drifts from the server's allowlist the day a profile is added or renamed, and
    every drift is a 422 the user cannot read. `models` / `default_model` / `images` are the server
    telling the editor what it will accept, so both sides cannot disagree.

    EVERY PRE-EXISTING KEY IS UNCHANGED IN SHAPE. `model` still reports a human string in live mode
    (the badge tooltip) -- it is not the profile id. It used to report the single Gemini deployment
    model every profile shared; now every profile is a genuinely different (backend, model) pair
    (see MODEL_PROFILES), so there is no longer one provider model to report globally. It reports
    the DEFAULT profile's label instead -- a caller who named a different profile on the request
    itself already knows which one it asked for.
    """
    pin = request.app.state.pin
    return {
        "template_sha256": pin["renderer_template"]["sha256"],
        "layout_index": pin["layout_signature"]["layout_index"],
        "canvas": dict(CANVAS),
        "brand": {"red": f"#{BRAND_RED}", "forbidden": f"#{FORBIDDEN}"},
        "fonts": {"latin": LATIN, "ea": EA},
        "mode": server_mode(),
        "model": MODEL_PROFILES[DEFAULT_PROFILE]["label"] if server_mode() == "live" else None,
        "models": [
            {"id": pid, "label": prof["label"], "thinking": prof["thinking"]}
            for pid, prof in MODEL_PROFILES.items()
        ],
        "default_model": DEFAULT_PROFILE,
        "images": {
            "max_count": MAX_IMAGES,
            "max_bytes": MAX_IMAGE_BYTES,
            "mime_types": list(IMAGE_MIME_TYPES),
            # Ordered: the first one present on an object wins. Published so a client does not have
            # to guess which spelling this server speaks -- it speaks both.
            "mime_keys": list(_MIME_KEYS),
        },
    }


@app.get("/api/log")
async def api_get_log() -> Response:
    """Returns multi-agent live execution logs."""
    if not LIVE_LOG_PATH.is_file():
        return JSONResponse({"log": "[INFO] No log file found yet. Waiting for worker executions..."})
    try:
        content = LIVE_LOG_PATH.read_text(encoding="utf-8", errors="replace")
        if not content.strip():
            content = "[INFO] Log file is currently empty. Waiting for worker executions..."
        return JSONResponse({"log": content})
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/download")
@app.post("/api/export")
async def api_export(request: Request) -> Response:
    """canvas-ir/1 in, .pptx bytes out. In memory, start to finish.

    The error mapping is the whole job, and the ORDER of the except clauses is the load-bearing
    part: StalePayloadError SUBCLASSES CanvasValidationError, so catching the parent first would
    report every stale payload as a 422 and tell the user to fix a deck that is perfectly fine. It
    is caught first, and it stays first.
    """
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
        headers={"Content-Disposition": content_disposition(ir["title"])},
    )


@app.post("/api/append_slide")
async def api_append_slide(request: Request) -> Response:
    ir, media_map, err, tmp_dir = await _read_multipart_ir(request)
    if err is not None:
        if tmp_dir:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return err

    target_b64 = ir.get("target", {}).get("target_pptx_b64")
    if not target_b64:
        if tmp_dir:
            import shutil
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
        except Exception as exc:
            log.exception("append slide failed")
            return JSONResponse({"error": "server_error", "detail": str(exc)}, status_code=500)

        buf = io.BytesIO()
        prs.save(buf)
    finally:
        if tmp_dir:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return Response(
        content=buf.getvalue(),
        media_type=PPTX_MIME,
        headers={"Content-Disposition": content_disposition(ir.get("title", ""))},
    )


def _generate_standalone_html(ir: dict[str, Any], media_map: dict[str, str] | None = None) -> str:
    title = ir.get("title", "Deck") or "Deck"
    canvas = ir.get("canvas", {"w": 960, "h": 540})
    cw = canvas.get("w", 960)
    ch = canvas.get("h", 540)
    elements = ir.get("elements", [])

    elements_html = []
    for el in elements:
        if not isinstance(el, dict):
            continue
        etype = el.get("type")
        eid = el.get("id", "")

        if etype == "connector":
            x1 = el.get("x1", 0)
            y1 = el.get("y1", 0)
            x2 = el.get("x2", 0)
            y2 = el.get("y2", 0)
            color = el.get("color", "#000000")
            width = el.get("width", 1)
            kind = el.get("kind", "straight")
            arrow = el.get("arrow", "none")

            min_x, min_y = min(x1, x2), min(y1, y2)
            w = max(abs(x2 - x1), 1)
            h = max(abs(y2 - y1), 1)
            ax, ay = x1 - min_x, y1 - min_y
            bx, by = x2 - min_x, y2 - min_y

            marker_id = f"m-{eid}"
            marker_svg = f'<defs><marker id="{marker_id}" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse" markerUnits="strokeWidth"><path d="M 0 0 L 10 5 L 0 10 z" fill="{color}"/></marker></defs>'

            mk_attrs = ""
            if arrow in ("start", "both"):
                mk_attrs += f' marker-start="url(#{marker_id})"'
            if arrow in ("end", "both"):
                mk_attrs += f' marker-end="url(#{marker_id})"'

            if kind == "elbow":
                mx = (ax + bx) / 2
                path_html = f'<polyline points="{ax},{ay} {mx},{ay} {mx},{by} {bx},{by}" fill="none" stroke="{color}" stroke-width="{width}"{mk_attrs}/>'
            else:
                path_html = f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" fill="none" stroke="{color}" stroke-width="{width}"{mk_attrs}/>'

            svg_code = f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" style="overflow:visible;">{marker_svg}{path_html}</svg>'
            el_style = f"position: absolute; left: {min_x}pt; top: {min_y}pt; width: {w}pt; height: {h}pt; pointer-events: none;"
            elements_html.append(f'<div id="{eid}" style="{el_style}">{svg_code}</div>')
            continue

        x = el.get("x", 0)
        y = el.get("y", 0)
        w = el.get("w", 100)
        h = el.get("h", 100)
        rot = el.get("rotation") or el.get("rot") or 0
        fill = el.get("fill") or "transparent"
        stroke = el.get("stroke") or {}
        stroke_color = stroke.get("color") or el.get("strokeColor") or ""
        stroke_width = stroke.get("width") if stroke.get("width") is not None else el.get("strokeWidth", 0)

        if etype in ("image", "video"):
            src = el.get("src", "")
            img_src = src
            if media_map and src in media_map:
                try:
                    with open(media_map[src], "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("ascii")
                        mime = "image/png" if src.lower().endswith(".png") else "image/jpeg"
                        img_src = f"data:{mime};base64,{b64}"
                except Exception:
                    img_src = src

            media_tag = f'<img src="{img_src}" style="width:100%;height:100%;object-fit:contain;" alt=""/>' if etype == "image" else f'<video src="{img_src}" controls style="width:100%;height:100%;"></video>'
            el_style = f"position: absolute; left: {x}pt; top: {y}pt; width: {w}pt; height: {h}pt; transform: rotate({rot}deg);"
            elements_html.append(f'<div id="{eid}" style="{el_style}">{media_tag}</div>')
            continue

        text_obj = el.get("text", {}) if isinstance(el.get("text"), dict) else {}
        align = text_obj.get("align", "LEFT").lower() if text_obj.get("align") else "left"
        valign = text_obj.get("valign", "TOP").lower() if text_obj.get("valign") else "top"

        flex_valign = "flex-start"
        if valign == "middle":
            flex_valign = "center"
        elif valign == "bottom":
            flex_valign = "flex-end"

        paras_html = []
        for p in text_obj.get("paragraphs", []):
            if not isinstance(p, dict):
                continue
            runs_html = []
            for r in p.get("runs", []):
                if not isinstance(r, dict):
                    continue
                t = r.get("t", "")
                size = r.get("size", 14)
                color = r.get("color", "#000000")
                bold = "font-weight: bold;" if r.get("bold") else ""
                italic = "font-style: italic;" if r.get("italic") else ""
                escaped_t = (
                    t.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\n", "<br>")
                )
                runs_html.append(
                    f'<span style="font-size: {size}pt; color: {color}; {bold} {italic}">{escaped_t}</span>'
                )
            p_text = "".join(runs_html)
            paras_html.append(f'<div style="text-align: {align};">{p_text}</div>')

        inner_text_html = "".join(paras_html)

        svg_bg = ""
        if etype == "ellipse":
            svg_bg = f'<svg width="100%" height="100%" viewBox="0 0 {w} {h}" preserveAspectRatio="none" style="position:absolute;top:0;left:0;z-index:0;"><ellipse cx="{w/2}" cy="{h/2}" rx="{w/2}" ry="{h/2}" fill="{fill}" stroke="{stroke_color}" stroke-width="{stroke_width}"/></svg>'
        elif etype == "triangle":
            svg_bg = f'<svg width="100%" height="100%" viewBox="0 0 {w} {h}" preserveAspectRatio="none" style="position:absolute;top:0;left:0;z-index:0;"><polygon points="{w/2},0 {w},{h} 0,{h}" fill="{fill}" stroke="{stroke_color}" stroke-width="{stroke_width}"/></svg>'
        elif etype in ("rect", "textbox"):
            if fill != "transparent" or stroke_color:
                svg_bg = f'<svg width="100%" height="100%" viewBox="0 0 {w} {h}" preserveAspectRatio="none" style="position:absolute;top:0;left:0;z-index:0;"><rect x="0" y="0" width="{w}" height="{h}" fill="{fill}" stroke="{stroke_color}" stroke-width="{stroke_width}"/></svg>'

        container_style = f"position: absolute; left: {x}pt; top: {y}pt; width: {w}pt; height: {h}pt; transform: rotate({rot}deg); display: flex; flex-direction: column; justify-content: {flex_valign}; box-sizing: border-box; padding: 4pt;"
        text_wrapper = f'<div style="position: relative; z-index: 1; width: 100%;">{inner_text_html}</div>'

        elements_html.append(
            f'<div id="{eid}" style="{container_style}">{svg_bg}{text_wrapper}</div>'
        )

    all_elements = "\n    ".join(elements_html)

    return f'''<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      padding: 20px;
      background-color: #1a1a1a;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      font-family: 'Century Gothic', '맑은 고딕', sans-serif;
    }}
    .slide-deck {{
      background: #ffffff;
      width: {cw}pt;
      height: {ch}pt;
      position: relative;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
      overflow: hidden;
    }}
  </style>
</head>
<body>
  <div class="slide-deck">
    {all_elements}
  </div>
</body>
</html>'''


@app.post("/api/export_html")
async def api_export_html(request: Request) -> Response:
    content_type = request.headers.get("content-type", "")
    tmp_dir = None
    media_map = None
    if "multipart/form-data" in content_type:
        ir, media_map, err, tmp_dir = await _read_multipart_ir(request)
        if err is not None:
            if tmp_dir:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            return err
    else:
        ir, err = await _read_json(request)
        if err is not None:
            return err

    try:
        try:
            validate(ir)
        except StalePayloadError as exc:
            return JSONResponse({"error": "stale", "detail": str(exc)}, status_code=409)
        except CanvasValidationError as exc:
            return JSONResponse({"error": "validation", "detail": str(exc)}, status_code=422)
        except TemplatePinError as exc:
            log.exception("template pin failed at REQUEST time")
            return JSONResponse({"error": "template", "detail": str(exc)}, status_code=500)

        html_str = _generate_standalone_html(ir, media_map=media_map)
    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    return Response(
        content=html_str,
        media_type="text/html",
        headers={"Content-Disposition": 'attachment; filename="deck.html"'},
    )



@app.post("/api/generate")
async def api_generate(request: Request) -> Response:
    """{"prompt", "model"?, "images"?} in, canvas-ir/1 out. MOCK without AIPPT_LIVE_MODE=1, LIVE with it.

    Either way the editor hands what comes back straight to loadIR(), which judges every element
    before it touches the stage -- so a model draft is no more trusted than a hand-edited file. The
    request shape, the loading state and the hand-off are identical in both modes; only the author
    behind the seam changes.

    `prompt` IS STILL THE ONLY MANDATORY FIELD (Phase 1). `{"prompt": "..."}` on its own means what
    it has always meant: the default profile, no attachments. The two new fields are additive.

    EVERY CHECK RUNS BEFORE THE MODE BRANCH. A body naming a profile that does not exist, or one
    carrying an image that is not one, is refused identically on a laptop with AIPPT_LIVE_MODE unset
    and on one with it set -- so a client bug cannot hide behind mock mode until it reaches
    production. It also means those refusals cost neither the mock's 1.5 s nor a CLI round trip.
    """
    body, err = await _read_json(request)
    if err is not None:
        return err

    prompt = body.get("prompt") if isinstance(body, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        # Refused BEFORE any model call or sleep. No author would have been invoked for an empty body.
        return JSONResponse(
            {"error": "validation", "detail": 'the body must be {"prompt": "<non-empty text>"}'},
            status_code=422,
        )

    profile, err = _resolve_profile(body.get("model"))
    if err is not None:
        return err

    do_review = bool(body.get("review")) if isinstance(body, dict) else False
    raw_reviewer = body.get("reviewer_model") if isinstance(body, dict) else None
    reviewer_model = None
    if raw_reviewer is not None:
        if not isinstance(raw_reviewer, str) or raw_reviewer not in MODEL_PROFILES:
            return JSONResponse(
                {"error": "validation", "detail": f"invalid reviewer_model {raw_reviewer!r}"},
                status_code=422,
            )
        reviewer_model = raw_reviewer

    images, err = _decode_images(body.get("images"))
    if err is not None:
        return err

    pin = request.app.state.pin

    # --- MOCK: AIPPT_LIVE_MODE is not set. The prompt is NOT read; a fixed deck comes back 1.5 s late.
    if not live_mode_enabled():
        # Logged BY LENGTH, never by content: this is an unauthenticated local endpoint and the deck
        # text is the user's, not ours.
        #
        # THE PROFILE AND THE IMAGES WERE VALIDATED AND ARE NOW DELIBERATELY DROPPED. A mock that
        # varied with either would stop being a mock: test_without_a_key_generate_is_still_the_mock
        # requires two different requests to produce byte-identical decks, and that property is the
        # only reason the mock is worth having.
        log.info(
            "mock generate: %d-char prompt, %d image(s), profile %s (none of it is read -- "
            "no model is called)",
            len(prompt), len(images), profile,
        )
        ir = mock_ir(pin)

        # THE MOCK IS VALIDATED BEFORE IT IS SERVED, by the same validator the export path runs. It
        # cannot fail because of anything the caller sent -- so if it fails, it is OUR bug: a 500.
        try:
            validate(ir)
        except CanvasValidationError as exc:
            log.exception("the MOCK payload does not validate -- a server bug, not a user error")
            return JSONResponse({"error": "mock", "detail": str(exc)}, status_code=500)

        if do_review:
            ir["_meta"] = {"review_applied": False}

        await asyncio.sleep(MOCK_LATENCY_S)
        return JSONResponse(ir)

    # --- LIVE: a real CLI-worker call. The prompt IS read now. ---------------------------------------
    cfg = MODEL_PROFILES[profile]
    log.info(
        "live generate: %d-char prompt, %d image(s) (validated, not forwarded -- see "
        "generate_live()), profile %s (%s thinking), review=%s (reviewer=%s) -> backend=%s model=%s",
        len(prompt), len(images), profile, cfg["thinking"], do_review, reviewer_model, cfg["backend"], cfg["model"],
    )
    try:
        ir = await generate_live(
            prompt.strip(), pin, profile=profile, images=images,
            review=do_review, reviewer_model=reviewer_model
        )
    except LiveGenerateError as exc:
        log.warning("live generate failed: %s", exc)
        return JSONResponse({"error": "generate", "detail": str(exc)}, status_code=502)

    # The assembled deck goes through the SAME validator the export path runs. A model can put a box
    # on the logo as easily as a human can; refusing it here means the editor is never handed a draft
    # it could only bounce, and the detail is the same numbered list validate() gives everywhere.
    try:
        validate_target = {k: v for k, v in ir.items() if k != "_meta"}
        validate(validate_target)
    except CanvasValidationError as exc:
        return JSONResponse({"error": "model", "detail": str(exc)}, status_code=502)

    return JSONResponse(ir)


@app.get("/api/designs")
async def api_list_designs() -> dict[str, Any]:
    """Every design saved so far, by name. AI_PPT_v2 Phase 4.

    Sorted so the editor's dropdown does not reorder itself between one load and the next just
    because the filesystem happened to iterate `saved_decks/` in a different order this time.
    """
    names = sorted(p.stem for p in SAVED_DECKS_DIR.glob("*.json") if p.is_file())
    return {"designs": names}


@app.post("/api/designs")
async def api_save_design(request: Request) -> Response:
    """{"name", "ir"} in, the design written to disk. AI_PPT_v2 Phase 4.

    THE ONE ROUTE THAT WRITES A FILE, and it is deliberately narrow: `ir` goes through the SAME
    validate() /api/export runs, so a saved design can never be a deck this server would later
    refuse to load back -- and `name` goes through _validate_design_name()/_design_path(), so the
    write can only ever land inside SAVED_DECKS_DIR under a name matching the allowlist.
    """
    body, err = await _read_json(request)
    if err is not None:
        return err
    if not isinstance(body, dict):
        return _rejected(
            "body_shape", 'the body must be {"name": "<string>", "ir": <canvas-ir/1 object>}'
        )

    name, err = _validate_design_name(body.get("name"))
    if err is not None:
        return err

    ir = body.get("ir")
    if not isinstance(ir, dict):
        return _rejected("body_shape", "'ir' must be a canvas-ir/1 object")
    try:
        validate(ir)
    except CanvasValidationError as exc:
        return JSONResponse({"error": "validation", "detail": str(exc)}, status_code=422)

    try:
        path = _design_path(name)
    except ValueError as exc:
        log.exception("a design name passed validation but _design_path() refused it anyway")
        return JSONResponse({"error": "name", "detail": str(exc)}, status_code=500)

    path.write_text(json.dumps(ir, ensure_ascii=False, indent=2), encoding="utf-8")
    return JSONResponse({"name": name})


@app.get("/api/designs/{name}")
async def api_load_design(name: str) -> Response:
    """A saved design, by name. AI_PPT_v2 Phase 4. 404 if it was never saved, or was deleted."""
    name, err = _validate_design_name(name)
    if err is not None:
        return err
    try:
        path = _design_path(name)
    except ValueError as exc:
        log.exception("a design name passed validation but _design_path() refused it anyway")
        return JSONResponse({"error": "name", "detail": str(exc)}, status_code=500)
    if not path.is_file():
        return JSONResponse(
            {"error": "not_found", "detail": f"no saved design named {name!r}"}, status_code=404
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log.exception("a saved design on disk could not be read back")
        return JSONResponse({"error": "corrupt", "detail": str(exc)}, status_code=500)
    return JSONResponse(data)


@app.delete("/api/designs/{name}")
async def api_delete_design(name: str) -> Response:
    """Deletes a saved design by name."""
    name, err = _validate_design_name(name)
    if err is not None:
        return err
    try:
        path = _design_path(name)
    except ValueError as exc:
        log.exception("a design name passed validation but _design_path() refused it anyway")
        return JSONResponse({"error": "name", "detail": str(exc)}, status_code=500)
    if not path.is_file():
        return JSONResponse(
            {"error": "not_found", "detail": f"no saved design named {name!r}"}, status_code=404
        )
    try:
        path.unlink()
    except OSError as exc:
        log.exception("could not delete saved design")
        return JSONResponse({"error": "delete", "detail": str(exc)}, status_code=500)
    return Response(status_code=204)



async def _read_multipart_ir(request: Request) -> tuple[Any, dict[str, str] | None, JSONResponse | None, str | None]:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return None, None, _too_large(), None

    try:
        form = await request.form(max_part_size=100 * 1024 * 1024)
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


async def _read_json(request: Request) -> tuple[Any, JSONResponse | None]:
    """The body guard every POST route shares. Returns (payload, None) or (None, error).

    Both size checks are needed and both are here: a chunked body declares no Content-Length, so the
    header check alone can be walked straight past, and the real-length check alone would have us
    buffer a megabyte before objecting to it.
    """
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return None, _too_large()

    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:  # chunked bodies declare no length; check the real thing too
        return None, _too_large()

    try:
        return json.loads(raw.decode("utf-8")), None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        # str(exc) is json's own "Expecting ',' delimiter: line 3 column 9" -- useful, and it leaks
        # nothing but the shape of the body the caller just sent us.
        return None, JSONResponse(
            {"error": "malformed", "detail": f"body is not valid UTF-8 JSON: {exc}"},
            status_code=400,
        )


def _too_large() -> JSONResponse:
    return JSONResponse(
        {
            "error": "too_large",
            "detail": f"payload exceeds {MAX_BODY_BYTES} bytes",
        },
        status_code=413,
    )


# --- the request validators (Phase 1) -----------------------------------------------------------
#
# Both return (value, None) or (None, error) -- the same two-tuple shape _read_json() already uses,
# so api_generate() reads as one flat sequence of guards rather than a nest of try blocks. Both run
# BEFORE the mode branch: what the server accepts must not depend on whether a key happens to be set
# on this machine.


def _rejected(code: str, detail: str) -> JSONResponse:
    """A 422 with a machine-readable discriminator.

    `"error": "validation"` is deliberately UNCHANGED -- the editor's existing banner keys on it
    and would go blank if it were renamed. `"code"` is additive, for a client that wants to say
    something more specific than the sentence we wrote.
    """
    return JSONResponse({"error": "validation", "code": code, "detail": detail}, status_code=422)


def _resolve_profile(raw: Any) -> tuple[str | None, JSONResponse | None]:
    """The requested profile, or a 422. Absent means the default -- a legacy body is fine."""
    if raw is None:
        return DEFAULT_PROFILE, None
    if not isinstance(raw, str) or raw not in MODEL_PROFILES:
        return None, _rejected(
            "unknown_model",
            f"{raw!r} is not an available model; choose one of {sorted(MODEL_PROFILES)}",
        )
    return raw, None


def _image_mime(item: dict[str, Any]) -> Any:
    """The MIME field under EITHER spelling, first key in _MIME_KEYS order wins.

    Returns whatever it found, including a non-string: the type check belongs with the other shape
    checks in _decode_images(), so {"mime_type": 7} is refused by the same branch and with the same
    message as {"mime": 7} rather than by a different path that says something else.

    An object carrying BOTH keys takes `mime` and ignores the other. The brief says accept both
    names; it does not say what a self-contradictory object means, and a client that sent both
    almost certainly sent the same value twice. Refusing the conflict would be defensible -- this
    is the one function to change if a reviewer wants that.
    """
    for key in _MIME_KEYS:
        if key in item:
            return item[key]
    return None


def _decode_images(raw: Any) -> tuple[list[dict[str, Any]] | None, JSONResponse | None]:
    """Base64 image objects -> decoded bytes IN MEMORY, or a 422 naming the first thing wrong.

    NOTHING IS WRITTEN TO DISK. The decoded bytes live in the returned list, go into a
    types.Part.from_bytes() and are collected when the request ends. There is no temp file, no
    upload directory and no filename taken from the body -- the same rule /api/export has always
    followed, for the same reason.
    """
    if raw is None:
        return [], None

    if not isinstance(raw, list):
        return None, _rejected(
            "images_shape",
            "'images' must be a list of {\"mime\": \"image/png\", \"data\": \"<base64>\"} objects",
        )
    if len(raw) > MAX_IMAGES:
        return None, _rejected(
            "too_many_images",
            f"{len(raw)} images attached; at most {MAX_IMAGES} are accepted",
        )

    decoded: list[dict[str, Any]] = []
    total = 0
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            return None, _rejected(
                "images_shape", f"images[{i}]: expected an object, got {type(item).__name__}"
            )

        mime = _image_mime(item)
        data = item.get("data")
        if not isinstance(mime, str) or not isinstance(data, str):
            return None, _rejected(
                "images_shape",
                f"images[{i}]: 'mime' (or 'mime_type') and 'data' must both be strings",
            )

        # "image/png; charset=binary" is a browser being thorough, not a different type. Normalise,
        # then match by EXACT membership.
        normalised = mime.split(";")[0].strip().lower()
        if normalised not in IMAGE_MIME_TYPES:
            return None, _rejected(
                "unsupported_mime",
                f"images[{i}]: {mime!r} is not one of {list(IMAGE_MIME_TYPES)}",
            )

        try:
            blob = base64.b64decode(data, validate=True)
        except (binascii.Error, ValueError) as exc:
            # BOTH exception types matter. validate=True governs only binascii's alphabet check; the
            # str -> ASCII coercion that runs BEFORE it raises a plain ValueError for any non-ASCII
            # character. Catching binascii.Error alone lets "한글" through unhandled, and Starlette
            # turns that into a 500 -- a server error for a caller's malformed field.
            return None, _rejected(
                "malformed_base64", f"images[{i}]: 'data' is not valid base64: {exc}"
            )
        if not blob:
            return None, _rejected("images_shape", f"images[{i}]: 'data' decoded to zero bytes")

        total += len(blob)
        if total > MAX_IMAGE_BYTES:
            # Reported on the RUNNING TOTAL, not on the image that crossed it -- naming one file
            # would send someone off to shrink a picture that was never individually the problem.
            return None, _rejected(
                "images_too_large",
                f"the attached images decode to more than {MAX_IMAGE_BYTES} bytes in total",
            )

        decoded.append({"mime": normalised, "data": blob})

    return decoded, None


def _validate_design_name(raw: Any) -> tuple[str | None, JSONResponse | None]:
    """A design name safe to use as a filename stem, or a 422. AI_PPT_v2 Phase 4.

    The SAME two-tuple shape every validator in this section returns. `.` and `..` already pass
    _SAFE_DESIGN_NAME (both are made only of characters the regex allows) and are refused BY NAME
    here instead -- _design_path()'s containment check would also catch either one, but refusing it
    here gives the caller a readable reason instead of a generic 500.

    WINDOWS-RESERVED DEVICE NAMES ARE REFUSED TOO, case-insensitively, extension or not. `CON`,
    `NUL.json`, `com1`, `Lpt3.bak` -- all of these name a device file, not a data file, on Windows;
    writing or reading one either fails outright or silently touches the device instead of the
    saved-decks directory. The check runs after the character-class regex because a reserved word is
    made entirely of characters the regex already allows, so the regex alone would never catch it.
    """
    if not isinstance(raw, str):
        return None, _rejected("name_shape", "'name' must be a string")
    if raw != raw.strip() or not raw:
        return None, _rejected(
            "name_shape", "'name' must be non-empty with no leading or trailing whitespace"
        )
    if raw in (".", ".."):
        return None, _rejected("name_shape", "'name' must not be '.' or '..'")
    if not _SAFE_DESIGN_NAME.match(raw):
        return None, _rejected(
            "name_shape",
            'a design name may not contain control characters or any of / \\ : * ? " < > |',
        )
    if raw.split(".", 1)[0].upper() in _RESERVED_DEVICE_NAMES:
        return None, _rejected(
            "name_shape",
            f"{raw!r} is a reserved Windows device name and cannot be used, even with an extension",
        )
    return raw, None


def _design_path(name: str) -> Path:
    """`name` -> the .json path inside SAVED_DECKS_DIR, or ValueError if it would not resolve there.

    A BELT-AND-BRACES check, not the primary defence -- _validate_design_name() already refused any
    name containing a path separator, so `(SAVED_DECKS_DIR / f"{name}.json").resolve()` should never
    land outside SAVED_DECKS_DIR by the time this runs. It runs anyway: if it ever DID land outside,
    that would mean the allowlist itself had a hole, and that is a 500 worth logging loudly rather
    than a write this function let through silently.
    """
    base = SAVED_DECKS_DIR.resolve()
    path = (base / f"{name}.json").resolve()
    if path.parent != base:
        raise ValueError(f"{name!r} resolved outside the saved-decks directory")
    return path


# --- the live author (Phase 4; repointed at CliWorkerClient by the headless-worker migration) ----
#
# AIPPT_LIVE_MODE picks the mode. Everything here is ordinary, testable code EXCEPT
# CliWorkerClient.complete_json() itself, the one seam that shells out to a claude/codex CLI (see
# aippt.adapters.ai_adapter) -- the mocking test monkeypatches exactly that method and exercises all
# the assembly (schema relaxation, prompt injection, pin injection, validation) around it for real.


def live_mode_enabled() -> bool:
    """True only for the literal value "1" -- not merely truthy. Unset, empty, "0" and "false" all
    mean mock; there is no ambiguous middle value a shell profile could leave behind by accident."""
    return os.environ.get("AIPPT_LIVE_MODE", "").strip() == "1"


def server_mode() -> str:
    """'live' when AIPPT_LIVE_MODE=1, else 'mock'. The editor reads this from /api/context and
    flips its badge; it never infers the mode from behaviour."""
    return "live" if live_mode_enabled() else "mock"


def system_instruction() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise LiveGenerateError(
            f"the system prompt could not be read at {PROMPT_PATH}: {exc}"
        ) from exc


@lru_cache(maxsize=1)
def _relaxed_live_schema() -> dict[str, Any]:
    """canvas/schema.json (the SAME file validate.py enforces at export time) with `target` dropped
    from the top-level `required` list -- everything else, including `target`'s own inner schema for
    when a model DOES include it, stays exactly as strict.

    The model cannot know reference/template_pin.json's current SHA or the pinned layout index --
    both are injected from the LIVE pin by _finalize_live_ir() after the call returns, never
    authored by the model. Relaxing anything beyond this one field would let a model skip work
    _finalize_live_ir() does not do on its behalf.
    """
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    schema["required"] = [name for name in schema["required"] if name != "target"]
    return schema


def _finalize_live_ir(data: Any, pin: dict[str, Any]) -> dict[str, Any]:
    """Overwrite schema, canvas and target from the LIVE PIN -- the model is never trusted with them.

    The system prompt tells the model to omit target entirely (it has no business choosing our
    template SHA) and to fix schema and canvas to constants. We ENFORCE all three here rather than
    hope: a model that ignores the instruction does not get to author the pin. Everything else --
    title and elements -- is the model's, and validate() judges it next.
    """
    if not isinstance(data, dict):
        raise LiveGenerateError(f"the model returned a {type(data).__name__}, not a JSON object")
    ir = dict(data)
    ir["schema"] = "canvas-ir/1"
    ir["canvas"] = dict(CANVAS)
    ir["target"] = {
        "template": pin["renderer_template"]["filename"],
        "template_sha256": pin["renderer_template"]["sha256"],
        "layout_index": pin["layout_signature"]["layout_index"],
    }
    ir.setdefault("title", "")
    if not isinstance(ir.get("elements"), list):
        raise LiveGenerateError("the model response is missing a valid 'elements' list")

    # Robustness fallback: Models often omit `color` on runs that are just whitespace (" ").
    # The schema requires `color` on EVERY run. We inject a default to prevent failing the whole deck.
    for el in ir["elements"]:
        if isinstance(el, dict):
            # Connector arrow fallback: The schema requires `arrow` on connectors.
            # Models sometimes omit it for simple lines. Default to "none".
            if el.get("type") == "connector" and "arrow" not in el:
                el["arrow"] = "none"

            if isinstance(el.get("text"), dict):
                for p in el["text"].get("paragraphs", []):
                    if isinstance(p, dict) and isinstance(p.get("runs"), list):
                        for run in p["runs"]:
                            if isinstance(run, dict) and "color" not in run:
                                run["color"] = "#1A1A1A"

    return ir


async def generate_live(
    prompt: str,
    pin: dict[str, Any],
    profile: str = DEFAULT_PROFILE,
    images: list[dict[str, Any]] | None = None,
    review: bool = False,
    reviewer_model: str | None = None,
) -> dict[str, Any]:
    """prompt (+ profile) -> canvas-ir/1 for the live author with optional review pass."""
    del images  # accepted for signature/contract compatibility only -- see docstring above

    cfg = MODEL_PROFILES[profile]
    track_mode = os.environ.get("AIPPT_TRACK", "b")
    client = CliWorkerClient(track=track_mode, backend=cfg["backend"], model=cfg["model"], timeout_s=900)

    try:
        obj = await asyncio.to_thread(
            client.complete_json,
            system=system_instruction(),
            user=prompt,
            schema=_relaxed_live_schema(),
        )
    except CliWorkerError as exc:
        raise LiveGenerateError(f"the model call failed: {exc}") from exc

    review_applied = False
    if review:
        rev_prof = reviewer_model if (reviewer_model and reviewer_model in MODEL_PROFILES) else profile
        rev_cfg = MODEL_PROFILES[rev_prof]
        rev_client = CliWorkerClient(track=track_mode, backend=rev_cfg["backend"], model=rev_cfg["model"], timeout_s=900)
        review_prompt = (
            "You are an expert presentation reviewer for Vieworks executive presentations.\n"
            "Your goal is to critique and refine the following drafted canvas-ir/1 deck, "
            "improving formatting, conciseness, visual hierarchy, and ensuring ZERO text overflow.\n\n"
            f"Draft IR:\n{json.dumps(obj, ensure_ascii=False, indent=2)}\n\n"
            "Return ONLY a valid JSON object matching the canvas-ir/1 schema. No explanation, no markdown code fences."
        )
        try:
            reviewed_obj = await asyncio.to_thread(
                rev_client.complete_json,
                system=system_instruction(),
                user=review_prompt,
                schema=_relaxed_live_schema(),
            )
            if isinstance(reviewed_obj, dict):
                cand_ir = _finalize_live_ir(reviewed_obj, pin)
                validate(cand_ir)  # Must pass full canvas validation before replacing initial draft
                obj = reviewed_obj
                review_applied = True
        except Exception as rev_exc:
            log.warning("Review pass failed or produced invalid IR (%s); using original draft", rev_exc)

    final_ir = _finalize_live_ir(obj, pin)
    if review:
        final_ir["_meta"] = {"review_applied": review_applied}
    return final_ir


def content_disposition(title: str) -> str:
    """RFC 5987, because the title is Korean often enough that ASCII-only is simply wrong.

    Two filenames go out: a sanitized ASCII `filename=` that ancient clients can read, and a
    percent-encoded UTF-8 `filename*=` that every current browser prefers. A Korean title collapses
    to nothing under ASCII folding, so the fallback degrades to "deck.pptx" rather than to an empty
    or a mangled name.
    """
    stem = _UNSAFE_STEM.sub(" ", title).strip()
    stem = re.sub(r"\s+", " ", stem)[:80].strip() or DEFAULT_STEM

    # NFKD then drop the non-ASCII: "Café" -> "Cafe", "회의 자료" -> "" -> DEFAULT_STEM.
    folded = unicodedata.normalize("NFKD", stem).encode("ascii", "ignore").decode("ascii").strip()
    ascii_stem = folded or DEFAULT_STEM

    encoded = urllib.parse.quote(f"{stem}.pptx", safe="")
    return f"attachment; filename=\"{ascii_stem}.pptx\"; filename*=UTF-8''{encoded}"


# --- the mock author (Phase 3) -----------------------------------------------------------------
#
# Three cards and two arrows, laid out inside BODY_SAFE (45.6, 92 -> 914.4, 500). The numbers are
# stated once, here, so that "why is that card at 656?" has an answer you can read instead of
# arithmetic you have to redo.

_CARD_Y = 232.0
_CARD_W = 244.0
_CARD_H = 116.0
_CARD_X = (60.0, 358.0, 656.0)     # 656 + 244 == 900, clear of BODY_SAFE's right edge (914.4)
_MID_Y = _CARD_Y + _CARD_H / 2.0   # the arrows leave and arrive at the cards' vertical centre

_PAPER = "#FFFFFF"
_INK = "#1A1A1A"
_MUTED = "#6B727C"

_CARDS = (
    ("card_awareness", _CARD_X[0], "Awareness", "신규 채널 3곳 · 브랜드 인지도 +18%"),
    ("card_consider", _CARD_X[1], "Consideration", "데모 요청 1.4k건 · 콘텐츠 체류 2.3배"),
    ("card_convert", _CARD_X[2], "Conversion", "파이프라인 목표 대비 106% 달성"),
)


def _card(eid: str, x: float, heading: str, detail: str) -> dict[str, Any]:
    return {
        "id": eid,
        "type": "rect",
        "x": x,
        "y": _CARD_Y,
        "w": _CARD_W,
        "h": _CARD_H,
        "fill": f"#{BRAND_RED}",
        "text": {
            "align": "CENTER",
            "valign": "MIDDLE",
            "paragraphs": [
                {"runs": [{"t": heading, "size": 18, "bold": True, "color": _PAPER}]},
                {"runs": [{"t": detail, "size": 13, "color": _PAPER}]},
            ],
        },
    }


def _arrow(eid: str, x1: float, x2: float) -> dict[str, Any]:
    return {
        "id": eid,
        "type": "connector",
        "kind": "straight",
        "x1": x1,
        "y1": _MID_Y,
        "x2": x2,
        "y2": _MID_Y,
        "color": f"#{BRAND_RED}",
        "width": 2,
        "arrow": "end",
    }


def mock_ir(pin: dict[str, Any]) -> dict[str, Any]:
    """The hardcoded deck /api/generate answers with. THE PROMPT IS NOT READ.

    Saying that plainly is the point of the function. A mock that appeared to respond to the prompt
    -- by echoing it into the title, say -- would be a mock you could not tell apart from a model,
    and the first thing it would do is carry author-supplied control characters into an IR that
    validate.py then refuses at export time. The real author replaces THIS FUNCTION and nothing else,
    which is why it takes the pin and returns a deck: no request, no app state, no I/O of its own.

    THE TEMPLATE SHA AND THE LAYOUT INDEX ARE INJECTED FROM THE LIVE PIN, never written as literals.
    A literal SHA here would go stale the day the template is re-pinned (Sec 4.3) and would hand
    every user a 409 on a deck they did not author -- the same argument that put /api/context there.

    ARRAY ORDER IS Z-ORDER: the connectors come FIRST, so the lines sit behind the cards they join.
    That is the convention the editor follows when it inserts one.
    """
    return {
        "schema": "canvas-ir/1",
        "canvas": dict(CANVAS),  # a copy -- a caller must not be able to mutate the module constant
        "target": {
            # Informational only; the server never reads a template path out of a payload.
            "template": pin["renderer_template"]["filename"],
            "template_sha256": pin["renderer_template"]["sha256"],
            "layout_index": pin["layout_signature"]["layout_index"],
        },
        "title": "Q3 Marketing Strategy",
        "elements": [
            _arrow("flow_1", _CARD_X[0] + _CARD_W, _CARD_X[1]),
            _arrow("flow_2", _CARD_X[1] + _CARD_W, _CARD_X[2]),
            {
                "id": "subtitle",
                "type": "textbox",
                "x": 60.0,
                "y": 132.0,
                "w": 840.0,
                "h": 64.0,
                # REQUIRED even when null: an omitted fill is exactly how a shape silently inherits
                # theme accent1.
                "fill": None,
                "text": {
                    "align": "LEFT",
                    "valign": "MIDDLE",
                    "paragraphs": [
                        {"runs": [{"t": "세 단계 퍼널 — 인지 → 검토 → 전환", "size": 20, "bold": True, "color": _INK}]},
                        {"runs": [{"t": "Where the Q3 spend actually moved the number.", "size": 14, "color": _MUTED}]},
                    ],
                },
            },
            *(_card(*c) for c in _CARDS),
            {
                # A mock deck that escapes into a real presentation says so ON THE SLIDE. This costs
                # one textbox and it is the difference between a demo and an incident.
                "id": "mock_note",
                "type": "textbox",
                "x": 60.0,
                "y": 392.0,
                "w": 840.0,
                "h": 44.0,
                "fill": None,
                "text": {
                    "align": "LEFT",
                    "valign": "MIDDLE",
                    "paragraphs": [
                        {"runs": [{
                            "t": "MOCK — /api/generate returned a fixed deck. No model was called (Phase 3).",
                            "size": 12,
                            "color": _MUTED,
                        }]}
                    ],
                },
            },
        ],
    }


def main() -> None:
    import uvicorn

    # 127.0.0.1, never 0.0.0.0. This serves an unauthenticated render endpoint; it is a local tool,
    # and binding it to every interface would put it on the corporate LAN.
    uvicorn.run(app, host="127.0.0.1", port=8080)


if __name__ == "__main__":
    main()
