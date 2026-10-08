#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Slide cloning. The naive recipe produces a file PowerPoint offers to repair.

The Stack Overflow version -- deepcopy the spTree children into a new slide -- is wrong in
two ways that do not show up until someone opens the file:

  C-1  r:embed / r:id / r:link inside the copied XML point at rels on the SOURCE part.
       Deep-copied into a new part they dangle. -> repair prompt, or a missing image.
  C-2  <p:bg> and <p:clrMapOvr> are NOT inside spTree. An spTree-only copy silently drops
       a custom background and a colour-map override.

Both are fixed here. package_audit.py is the test that proves it.
"""

from __future__ import annotations

import copy
from typing import Any

from pptx.oxml.ns import qn

_R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def clone_slide(prs: Any, src_slide: Any) -> Any:
    """Append a self-contained copy of ``src_slide`` to ``prs``. Returns the new Slide.

    Self-contained means: it survives deletion of ``src_slide`` (§2.5), because every
    relationship it needs has been re-registered on its own slide part.
    """
    # Same layout => the layout's decoration (logo, page-number graphic) and its layout-level
    # run styling are INHERITED, not copied. This is why cloning beats recipe-extraction.
    dst = prs.slides.add_slide(src_slide.slide_layout)

    # add_slide() cloned the layout's placeholders in. We don't want them -- the source slide
    # carries its own copies of whatever it uses. Iterate slide.shapes, NOT spTree children:
    # spTree also holds <p:nvGrpSpPr> and <p:grpSpPr>, which are structural.
    for shape in list(dst.shapes):
        shape._element.getparent().remove(shape._element)

    _copy_background(src_slide, dst)          # C-2
    _copy_clr_map_ovr(src_slide, dst)         # C-2

    dst_spTree = dst.shapes._spTree
    for shape in src_slide.shapes:
        element = copy.deepcopy(shape._element)
        _remap_rels(src_slide.part, dst.part, element)     # C-1 -- BEFORE append
        dst_spTree.append(element)

    return dst


def _remap_rels(src_part: Any, dst_part: Any, element: Any) -> int:
    """Re-point every r:id / r:embed / r:link in ``element`` at a rel on ``dst_part``.

    Swept generically rather than by element type. A whitelist would eventually miss one:
    a:blip/@r:embed (pictures), asvg:svgBlip/@r:embed (the SVG fallback inside a modern
    picture), a:hlinkClick/@r:id (hyperlinks -- including ones on individual text runs),
    c:chart/@r:id, p:oleObj/@r:id, p:videoFile/@r:link. Every attribute in the relationships
    namespace IS a relationship id, so the sweep is exhaustive by construction.

    relate_to() is idempotent on (target, reltype): two pictures sharing one image part
    collapse to one rel, as they should.

    The part-sharing hazard: relate_to(rel.target_part, ...) makes the clone point at the
    SAME part object as the source. Correct for parts we only READ (images, media) -- keeps
    the file small. WRONG for parts we MUTATE (a chart part and its embedded workbook), which
    is why analyze_exemplars.py refuses chart- and OLE-bearing slides outright. Tables are
    safe: <a:tbl> is inline XML inside the graphicFrame, not a separate part.
    """
    remapped = 0
    for el in element.iter():
        for attr, rid in list(el.attrib.items()):
            if not attr.startswith("{%s}" % _R_NS) or not rid:
                continue
            rel = src_part.rels[rid]
            if rel.is_external:
                new_rid = dst_part.relate_to(rel.target_ref, rel.reltype, is_external=True)
            else:
                new_rid = dst_part.relate_to(rel.target_part, rel.reltype)
            el.set(attr, new_rid)
            remapped += 1
    return remapped


def _copy_background(src: Any, dst: Any) -> None:
    """<p:bg> is a child of <p:cSld> and must be its FIRST child, before <p:spTree>."""
    src_bg = src._element.find(qn("p:cSld")).find(qn("p:bg"))
    if src_bg is None:
        return
    dst_cSld = dst._element.find(qn("p:cSld"))
    existing = dst_cSld.find(qn("p:bg"))
    if existing is not None:
        dst_cSld.remove(existing)
    new_bg = copy.deepcopy(src_bg)
    _remap_rels(src.part, dst.part, new_bg)   # a picture-fill background carries an r:embed
    dst_cSld.insert(0, new_bg)


def _copy_clr_map_ovr(src: Any, dst: Any) -> None:
    """<p:clrMapOvr> is a child of <p:sld> and must come AFTER <p:cSld>."""
    src_ovr = src._element.find(qn("p:clrMapOvr"))
    if src_ovr is None:
        return
    dst_sld = dst._element
    existing = dst_sld.find(qn("p:clrMapOvr"))
    if existing is not None:
        dst_sld.remove(existing)
    cSld_pos = list(dst_sld).index(dst_sld.find(qn("p:cSld")))
    dst_sld.insert(cSld_pos + 1, copy.deepcopy(src_ovr))


# <p:transition> and <p:timing> are deliberately NOT copied: presentation behaviour, not
# design, and the IR does not model them. Speaker notes are not cloned either -- the IR
# supplies its own, and touching slide.notes_slide CREATES a notes slide as a side effect
# (Q3 F-17). Only touch it when ir_slide.notes is non-empty, and guard notes_text_frame is None.


def drop_slides(prs: Any, count: int) -> int:
    """Delete the first ``count`` slides. Call this AFTER every clone exists.

    Ordering is the whole trick and the failure is silent until someone opens the file:

        1. clone each exemplar (appends at index 23, 24, 25 ...)
        2. THEN delete the original 23
        => len(prs.slides) == len(ir.slides), in IR order, with no reorder code.

    Deleting the sources is safe only after every clone has re-registered its own rels: the
    image parts then stay reachable through the clones and survive serialisation.

    Both halves, in this order. Dropping the sldIdLst entry WITHOUT drop_rel leaves an
    orphaned relationship and PowerPoint calls the file corrupt.
    """
    sld_id_lst = prs.slides._sldIdLst
    for sld_id in list(sld_id_lst)[:count]:
        prs.part.drop_rel(sld_id.get(qn("r:id")))
        sld_id_lst.remove(sld_id)
    return count