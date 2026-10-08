#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Connectors and arrowheads. Phase 1A, task 1.4.

Absolute endpoints, NO GLUING. begin_connect()/end_connect() are experimental and their
connection-site indices are unreliable for arbitrary shapes -- notably triangles. Gluing is
genuinely valuable (a glued connector stays attached when the user later drags a box *inside*
PowerPoint), so it is revisited in Phase 2 behind a fixture suite. Phase 1 ships absolute
endpoints, which always work (D-3).

Connectors get the Office drop shadow too, so `shadow.inherit = False` is as necessary here as it
is on a shape -- and so is stripping <p:style>, because <p:cxnSp> carries one for the same reason.
"""

from __future__ import annotations

from typing import Any

from pptx.enum.shapes import MSO_CONNECTOR
from pptx.oxml.ns import qn
from pptx.util import Pt

from aippt.canvas.geometry import emu
from aippt.canvas.style import rgb, strip_style

KIND: dict[str, MSO_CONNECTOR] = {
    "straight": MSO_CONNECTOR.STRAIGHT,
    "elbow": MSO_CONNECTOR.ELBOW,
}

ARROWHEAD = "triangle"


def set_arrowheads(cxn: Any, arrow: str) -> None:
    """Arrowheads are not exposed in the python-pptx API -- there is no `line.end_arrow` -- so this
    drops to lxml.

    THE CHILD ORDER IS NOT OPTIONAL. CT_LineProperties._tag_seq (pptx/oxml/shapes/shared.py) is

        noFill solidFill gradFill pattFill prstDash custDash round bevel miter headEnd tailEnd extLst

    so <a:headEnd> MUST PRECEDE <a:tailEnd>. Plan Sec 6.7 appends tailEnd first and headEnd second,
    which for arrow="both" emits them in reverse schema order: PowerPoint rejects the file and shows
    a repair dialog. That is a corrupt deck, not a cosmetic slip.

    insert_element_before is order-safe whatever order you add them in -- you hand it the element's
    SUCCESSORS and it puts the element in front of the first one present. It APPENDS when it finds
    none of them, which is exactly why each successor list below has to be complete: headEnd's
    successors are tailEnd and extLst; tailEnd's is extLst.

    `start` is the arrowhead at (x1, y1) -- the connector's BEGIN point, which DrawingML calls the
    head. `end` is (x2, y2), the tail.
    """
    if arrow == "none":
        return

    ln = cxn.line._get_or_add_ln()

    if arrow in ("start", "both"):
        head = ln.makeelement(qn("a:headEnd"), {"type": ARROWHEAD})
        ln.insert_element_before(head, "a:tailEnd", "a:extLst")

    if arrow in ("end", "both"):
        tail = ln.makeelement(qn("a:tailEnd"), {"type": ARROWHEAD})
        ln.insert_element_before(tail, "a:extLst")


def draw_connector(slide: Any, el: dict[str, Any]) -> Any:
    """A connector -> a styled <p:cxnSp> on `slide`."""
    cxn = slide.shapes.add_connector(
        KIND[el["kind"]],
        emu(el["x1"]),
        emu(el["y1"]),
        emu(el["x2"]),
        emu(el["y2"]),
    )
    cxn.name = el["id"]  # the round-trip suite finds shapes by NAME, not by position

    cxn.line.color.rgb = rgb(el["color"])
    # Width 0 is a HAIRLINE, not "no line" -- same as for a shape stroke. A connector always has a
    # line (that is all it is), so there is no null case here.
    cxn.line.width = Pt(el["width"])
    cxn.shadow.inherit = False  # connectors get the Office drop shadow too

    set_arrowheads(cxn, el["arrow"])
    strip_style(cxn)
    return cxn
