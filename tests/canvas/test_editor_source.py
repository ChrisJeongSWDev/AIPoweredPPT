#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GATE 1 -- the Prime Directive, machine-checked. Phase 1B.

Static source assertions over static/editor.js and static/interactions.js. No browser, no node, no
DOM: this is a grep, and that is the point. It is the only thing standing between "we agreed on the
rule" and "the rule held", and it costs milliseconds.

THE RULE
--------
Geometry lives in JS state and flows ONE WAY into CSS. It is never read back out of the DOM. A
device coordinate becomes a model coordinate in exactly ONE place -- toModel() -- and everything
else works in model units.

Break it and the editor develops a class of bug that only appears at zoom != 1, presents as a
coordinate error, and disagrees with canvas/geometry.py -- at which point the user is looking at a
legal-looking stage and an unexplainable 422.

WHY THESE ARE SUBSTRING CHECKS AND NOT AST CHECKS
-------------------------------------------------
Because a substring check cannot be argued with, needs no JS toolchain in a Python test suite, and
fails loudly the moment someone reaches for the convenient thing. The cost is that the banned names
must not appear in editor.js AT ALL -- not even in a comment explaining why they are banned. That
is why editor.js's own header points HERE for the list rather than reciting it: this file is the
spec, and it cannot drift away from itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STATIC = Path(__file__).resolve().parents[2] / "src" / "aippt" / "canvas" / "static"

EDITOR_PATH = STATIC / "editor.js"
INTERACTIONS_PATH = STATIC / "interactions.js"

EDITOR = EDITOR_PATH.read_text(encoding="utf-8")
INTERACTIONS = INTERACTIONS_PATH.read_text(encoding="utf-8")

# Every way a browser will hand you a MEASURED number. Each one silently reintroduces device pixels
# into the model and breaks the moment zoom != 1.
BANNED_MEASUREMENT = [
    "offsetWidth",
    "offsetHeight",
    "clientWidth",
    "clientHeight",
    "offsetLeft",
    "offsetTop",
    "offsetParent",
    "devicePixelRatio",
    "getComputedStyle",
    "getBBox",
]

# interact.js's move event exposes a measured, device-pixel rect. Consuming it is the single most
# common way this rule dies. (Our own engine never emits one -- see interactions.js -- but the ban
# has to survive someone swapping the real library back in.)
BANNED_RECT = [r"\bev\.rect\b", r"\bevent\.rect\b"]

# Canvas sizes that are NOT the model space. 1280x720 divides exactly too, but then every font size
# needs a x0.75 factor -- which is precisely the bug 960x540 exists to delete.
OTHER_CANVAS_SIZES = ["1920", "1080", "1280", "720", "1440", "810"]


def _function_body(src: str, name: str) -> str:
    """The text of `function <name>(...) { ... }`, braces balanced."""
    start = src.index(f"function {name}(")
    open_brace = src.index("{", start)
    depth = 0
    for i in range(open_brace, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[open_brace : i + 1]
    raise AssertionError(f"unbalanced braces in {name}()")


# --- the one measurement ---------------------------------------------------------------------


def test_bounding_rect_appears_exactly_once():
    """It is read ONCE, to invert a pointer. A second reader is a second source of truth."""
    n = EDITOR.count("getBoundingClientRect")
    assert n == 1, (
        f"getBoundingClientRect appears {n} times in editor.js; it may appear exactly once, "
        f"inside toModel(). Every other measurement of the DOM is banned."
    )


def test_the_one_bounding_rect_is_inside_to_model():
    body = _function_body(EDITOR, "toModel")
    assert "getBoundingClientRect" in body, (
        "the single getBoundingClientRect call is not inside toModel() -- which means something "
        "else in editor.js is measuring the DOM."
    )


def test_interactions_engine_measures_nothing():
    """The drag engine differences pointer positions. It must never measure a node.

    This is the file people reach for when they want "just the element's real size", and it is the
    file that would then hand device pixels to every call site at once.
    """
    assert "getBoundingClientRect" not in INTERACTIONS
    for name in BANNED_MEASUREMENT:
        assert name not in INTERACTIONS, f"interactions.js measures the DOM via {name}"


# --- the banned list -------------------------------------------------------------------------


@pytest.mark.parametrize("name", BANNED_MEASUREMENT)
def test_no_measured_geometry_api(name: str):
    assert name not in EDITOR, (
        f"editor.js reads {name}. Geometry flows state -> CSS and is NEVER read back: "
        f"{name} returns a device pixel and is wrong at every zoom but 1."
    )


@pytest.mark.parametrize("pattern", BANNED_RECT)
def test_no_measured_rect_from_the_drag_library(pattern: str):
    assert re.search(pattern, EDITOR) is None, (
        f"editor.js consumes {pattern} -- a measured, device-pixel rectangle. Consume DELTAS only, "
        f"and divide them by zoom."
    )


def test_every_delta_rect_read_is_divided_by_zoom():
    """`deltaRect` is device pixels, exactly as interact.js reports it. Every read is converted."""
    reads = 0
    for i, line in enumerate(EDITOR.splitlines(), 1):
        if re.search(r"deltaRect\.\w+", line):
            reads += 1
            assert "/ zoom" in line, (
                f"editor.js:{i} reads deltaRect without dividing by zoom in the same expression:\n"
                f"    {line.strip()}"
            )
    assert reads >= 4, (
        f"expected the four deltaRect fields (left/top/width/height) to be read; found {reads}. "
        f"If resize stopped consuming deltaRect, this gate is no longer checking anything."
    )


def test_no_emu_arithmetic_in_the_browser():
    """The browser never converts to EMU. Python does, once, at the end."""
    assert "12700" not in EDITOR, (
        "editor.js contains 12700. The IR carries LOGICAL UNITS as floats; canvas/geometry.py does "
        "the single, exact EMU conversion. A browser-side conversion is a second rounding site."
    )


def test_z_order_is_dom_order():
    """No `z` field, no CSS stacking index. A second source of truth would desync."""
    assert "zIndex" not in EDITOR
    assert "z-index" not in EDITOR


# --- the model space -------------------------------------------------------------------------


def test_schema_version_is_stated():
    assert "canvas-ir/1" in EDITOR


def test_the_model_space_is_960x540_pt():
    assert re.search(r"w:\s*960,\s*h:\s*540,\s*unit:\s*['\"]pt['\"]", EDITOR), (
        "editor.js must echo the canvas as {w: 960, h: 540, unit: 'pt'} so the backend can reject "
        "a STALE payload rather than silently rescaling it."
    )


@pytest.mark.parametrize("size", OTHER_CANVAS_SIZES)
def test_no_other_canvas_size_appears(size: str):
    assert size not in EDITOR, (
        f"editor.js mentions {size}. There is exactly ONE model space (960x540) and the renderer "
        f"NEVER rescales; a second size in the editor is either dead code or a coming bug."
    )


# --- the forbidden colour --------------------------------------------------------------------


def test_accent1_appears_only_in_the_rejection_path():
    """#4472C4 is the template's theme accent1. validate.py rejects it, so the picker must too.

    It is allowed to appear ONLY where it is being refused -- never as a default, a palette entry
    or a fallback.
    """
    hits = [(i, line) for i, line in enumerate(EDITOR.splitlines(), 1) if "4472C4" in line]
    assert hits, "editor.js does not mention #4472C4 at all -- the colour guard is missing."
    for lineno, text in hits:
        assert re.search(r"FORBIDDEN|reject|refus", text, re.IGNORECASE), (
            f"editor.js:{lineno} mentions #4472C4 outside the rejection path:\n    {text.strip()}\n"
            f"It is theme accent1 and is banned as an explicit author choice -- that ban is what "
            f"keeps 'no accent1 in any generated shape' machine-checkable."
        )


def test_brand_red_is_the_default():
    assert "#FF0032" in EDITOR
