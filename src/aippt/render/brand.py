#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The brand palette, and the single pass that enforces it. One module, one constant.

BRAND_RED is #FF0032. This is a USER OVERRIDE and it is deliberately not the colour the
template contains: every piece of evidence says the template's red is #DB0032 (Q3 F-03 found
the literal in slideLayout3.xml and slide2.xml; it is the CSS variable in all three corpus
decks). The user specified #FF0032 and instructed the renderer to forcefully override.

So LEGACY_TEMPLATE_RED exists ONLY so enforce_brand() can recognise the old colour and
replace it -- a cloned exemplar arrives carrying #DB0032 in its run properties and fills, and
a deck that mixes the two reds looks like a rendering bug, because it is one.

Why a literal RGBColor and not MSO_THEME_COLOR: the accent is not in the theme.
layout_manifest.json reports brand_accent.resolution "not-found"; the six accent slots are
stock Office blue/orange/grey. MSO_THEME_COLOR.ACCENT_n would paint the wrong colour, silently.
(renderer.py's current docstring says to prefer the theme slot. It was written before the
analyzer ran and it is wrong for this template. Delete that line.)
"""

from __future__ import annotations

from typing import Any

from pptx.dml.color import RGBColor
from pptx.oxml.ns import qn

BRAND_RED = RGBColor(0xFF, 0x00, 0x32)             # USER OVERRIDE. The only brand red.
LEGACY_TEMPLATE_RED = RGBColor(0xDB, 0x00, 0x32)   # Referenced ONLY by rewrite_legacy_red().

CALLOUT_ACCENT = {                                 # .alert-box x4 / .warn-box x2 / .ok-box x1
    "info": BRAND_RED,
    "warn": RGBColor(0xE8, 0x8B, 0x00),
    "ok": RGBColor(0x1E, 0x8E, 0x3E),
}
ON_BRAND_TEXT = RGBColor(0xFF, 0xFF, 0xFF)         # black on #FF0032 fails contrast
CODE_FONT = "Consolas"


class BrandViolation(RuntimeError):
    """A shape the exemplar nominates as a brand shape could not be branded. A bug in the
    block writer or a stale manifest -- not something to paper over here."""


def rewrite_legacy_red(element: Any) -> int:
    """Repoint every literal DB0032 in a subtree at BRAND_RED. Returns the count rewritten.

    Operates on raw XML, not the typed colour API, on purpose: the colour can sit in a run's
    <a:solidFill>, a shape's <a:ln>, a gradient stop, or a table cell fill, and no single
    typed accessor reaches all four.
    """
    legacy, replacement = str(LEGACY_TEMPLATE_RED), str(BRAND_RED)
    count = 0
    for clr in element.iter(qn("a:srgbClr")):
        if (clr.get("val") or "").upper() == legacy:
            clr.set("val", replacement)
            count += 1
    return count


def paint_solid(shape: Any, color: RGBColor) -> None:
    """solid() first -- fore_color raises if there is no fill type to take a colour."""
    shape.fill.solid()
    shape.fill.fore_color.rgb = color


def enforce_brand(slide: Any, exemplar: Any, *, strict: bool = True) -> dict[str, int]:
    """Runs LAST on every slide (renderer §4.1). The single choke point for colour.

    After fill, so nothing a block writer does can leave an off-brand run behind. After
    unbound-slot removal, so we don't rebrand shapes we are about to delete.

    Charts are out of scope in Phase 1 and that is deliberate: cloning shares the chart part
    between source and clone, so recolouring one would recolour the other. analyze_exemplars
    refuses chart-bearing slides, and there is no chart path here to test. Phase 2, with
    charts we create ourselves, is where that belongs.
    """
    stats = {"legacy_red_rewritten": 0, "brand_shapes_painted": 0, "table_headers_branded": 0}

    # Sweep the whole <p:sld>, not just spTree -- <p:bg> lives outside spTree and can be red.
    stats["legacy_red_rewritten"] = rewrite_legacy_red(slide._element)

    by_id = {sh.shape_id: sh for sh in slide.shapes}
    for shape_id in exemplar.brand_shapes:
        shape = by_id.get(shape_id)
        if shape is None:
            if strict:
                raise BrandViolation(
                    f"exemplar {exemplar.exemplar_id!r} nominates shape_id {shape_id} as a "
                    f"brand shape but no such shape is on the cloned slide -- the exemplar "
                    f"manifest is stale. Re-run analyze_exemplars.py."
                )
            continue
        try:
            paint_solid(shape, BRAND_RED)
            stats["brand_shapes_painted"] += 1
        except (AttributeError, TypeError):
            if strict:
                raise BrandViolation(
                    f"exemplar {exemplar.exemplar_id!r} nominates shape_id {shape_id}, but a "
                    f"{type(shape).__name__} has no fill. Remove it from brand_shapes."
                ) from None

    for shape in slide.shapes:
        if getattr(shape, "has_table", False):
            brand_table_header(shape.table)
            stats["table_headers_branded"] += 1

    return stats


def brand_table_header(table: Any) -> None:
    """Row 0 -> brand fill + white bold text. first_row=True stops the table style from
    banding row 0 as a body row and fighting our explicit fill."""
    table.first_row = True
    for cell in table.rows[0].cells:
        paint_solid(cell, BRAND_RED)
        for para in cell.text_frame.paragraphs:
            for run in para.runs:
                run.font.bold = True
                run.font.color.rgb = ON_BRAND_TEXT


def style_code_run(run: Any) -> None:
    """Inline <code> -- monospace + brand red. The ONE sanctioned exception to "styling comes
    from the exemplar's <a:rPr>". 111 of them in the corpus; rendering VEO_Focus_Initialize()
    as body prose on an API slide reads as a bug.

    Note it does NOT set font.size: the run keeps the size it inherited from the prototype.
    fit.py is the only module allowed to change a size.
    """
    run.font.name = CODE_FONT
    run.font.color.rgb = BRAND_RED