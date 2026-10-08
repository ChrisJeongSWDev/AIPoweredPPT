#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extract the design truth out of ``Vieworks_R&D_ppt_Template.pptx``.

Deliverable C of the AI_Powered_PPT foundation. This is the *only* component that
is allowed to look inside the template; everything downstream (renderer, prompts,
AI author) consumes the two artifacts this script emits:

    reference/layout_manifest.json   machine contract  (renderer + validators read this)
    reference/layout_catalog.md      prompt context    (pasted into the AI author prompt)

Why both: the renderer needs exact EMU geometry, the LLM needs a short readable menu
of layouts with *content budgets* so it self-limits instead of overflowing boxes.
python-pptx cannot autofit text (PowerPoint computes autofit at render time, not in
the file), so the budget is our only pre-emptive defence against overflow.

Read-only by construction
-------------------------
The template is slurped into memory (``Path.read_bytes``) and handed to python-pptx
as a ``BytesIO``. python-pptx therefore never holds a handle on the real file and
``Presentation.save`` is never called. The ``&`` in ``Vieworks_R&D_ppt_Template.pptx``
is a shell metacharacter, not a Python one -- because we never shell out, it needs no
escaping here. (Quote the path when *you* type it into cmd/PowerShell.)

Usage
-----
    python -m aippt.analyze_pptx_master
    python -m aippt.analyze_pptx_master --template "../Vieworks_R&D_ppt_Template.pptx"
    python -m aippt.analyze_pptx_master --template <path> --out-dir <dir> --quiet

Exit codes: 0 ok | 2 template not found | 3 python-pptx missing | 4 parse failure.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------------------

EMU_PER_INCH = 914400
EMU_PER_PT = 12700

#: DrawingML / PresentationML namespaces, in lxml Clark notation.
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
P = "{http://schemas.openxmlformats.org/presentationml/2006/main}"

#: The Vieworks brand red. We do not assume where it lives -- we go and find it.
BRAND_ACCENT = "DB0032"

#: Ordered theme colour slots as they appear in ``a:clrScheme``.
CLR_SLOTS = (
    "dk1", "lt1", "dk2", "lt2",
    "accent1", "accent2", "accent3", "accent4", "accent5", "accent6",
    "hlink", "folHlink",
)

#: Fallback point sizes when neither the layout, the master placeholder, nor the
#: master ``p:txStyles`` declare one. Only used as a last resort; the manifest records
#: ``font_pt_source`` so you can tell a real value from a guess.
DEFAULT_PT = {"title": 36.0, "body": 18.0, "other": 12.0}

#: Typographic constants for the content-budget model. These are deliberately
#: conservative -- a budget that is slightly too small costs a word, a budget that is
#: too large costs a broken slide.
LATIN_CHAR_WIDTH_RATIO = 0.52   # mean glyph advance / font size, proportional Latin
CJK_CHAR_WIDTH_RATIO = 1.00     # Hangul/Han are full-width by definition
LINE_HEIGHT_RATIO = 1.22        # single line spacing incl. leading
BULLET_GAP_RATIO = 0.35         # space-before between bullets, in font-size units
SAFETY = 0.90                   # trim 10% -- kerning, bold runs, and CJK/Latin mixing
LATIN_CHARS_PER_WORD = 6.0      # 5 letters + 1 space


# --------------------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------------------

def emu_to_in(emu: int | None) -> float | None:
    return None if emu is None else round(emu / EMU_PER_INCH, 4)


def emu_to_pt(emu: int | None) -> float | None:
    return None if emu is None else round(emu / EMU_PER_PT, 2)


def aspect_label(w: int, h: int) -> str:
    """Name the aspect ratio, tolerating the rounding real templates contain."""
    if not w or not h:
        return "unknown"
    r = w / h
    for label, target in (("16:9", 16 / 9), ("16:10", 16 / 10), ("4:3", 4 / 3), ("3:2", 3 / 2)):
        if abs(r - target) < 0.02:
            return label
    return f"{r:.3f}:1"


def _rels_of(part: Any) -> list[Any]:
    """python-pptx has changed the Relationships type across versions; cope with both."""
    rels = part.rels
    try:
        return list(rels.values())
    except AttributeError:
        return [rels[k] for k in rels]


def _element_of(obj: Any) -> Any:
    """Raw lxml element behind a python-pptx object (private API, hence the fallback)."""
    for attr in ("_element", "element"):
        el = getattr(obj, attr, None)
        if el is not None:
            return el
    raise AttributeError(f"cannot reach the XML element of {obj!r}")


# --------------------------------------------------------------------------------------
# Theme
# --------------------------------------------------------------------------------------

@dataclass
class ThemeInfo:
    name: str | None = None
    major_font: dict[str, str | None] = field(default_factory=dict)
    minor_font: dict[str, str | None] = field(default_factory=dict)
    color_map: dict[str, str] = field(default_factory=dict)
    brand_accent_slots: list[str] = field(default_factory=list)


def _typefaces(font_el: Any) -> dict[str, str | None]:
    """latin / ea (East Asian -- the Korean face) / cs typefaces of a font scheme half."""
    if font_el is None:
        return {}
    out: dict[str, str | None] = {}
    for key in ("latin", "ea", "cs"):
        el = font_el.find(f"{A}{key}")
        out[key] = el.get("typeface") if el is not None else None
    return out


def _slot_color(slot_el: Any) -> str | None:
    """Resolve one ``a:clrScheme`` slot to an RRGGBB string."""
    if slot_el is None:
        return None
    srgb = slot_el.find(f"{A}srgbClr")
    if srgb is not None and srgb.get("val"):
        return srgb.get("val").upper()
    sysclr = slot_el.find(f"{A}sysClr")
    if sysclr is not None:
        # sysClr carries the resolved value in @lastClr; @val is a system name (e.g. windowText)
        return (sysclr.get("lastClr") or sysclr.get("val") or "").upper() or None
    return None


def read_theme(master: Any) -> ThemeInfo:
    """Pull the font scheme + colour map off the theme part related to this master.

    python-pptx exposes no theme API, so we walk the OPC relationships by hand.
    Returns an empty-ish ThemeInfo rather than raising if the theme is unreachable --
    a missing theme must not sink the whole analysis.
    """
    info = ThemeInfo()
    theme_el = None
    for rel in _rels_of(master.part):
        if str(rel.reltype).endswith("/theme"):
            try:
                from lxml import etree
                theme_el = etree.fromstring(rel.target_part.blob)
            except Exception:  # pragma: no cover - defensive
                theme_el = None
            break
    if theme_el is None:
        return info

    info.name = theme_el.get("name")
    scheme = theme_el.find(f"{A}themeElements")
    if scheme is None:
        return info

    font_scheme = scheme.find(f"{A}fontScheme")
    if font_scheme is not None:
        info.major_font = _typefaces(font_scheme.find(f"{A}majorFont"))
        info.minor_font = _typefaces(font_scheme.find(f"{A}minorFont"))

    clr_scheme = scheme.find(f"{A}clrScheme")
    if clr_scheme is not None:
        for slot in CLR_SLOTS:
            value = _slot_color(clr_scheme.find(f"{A}{slot}"))
            if value:
                info.color_map[slot] = value
                if value == BRAND_ACCENT:
                    info.brand_accent_slots.append(slot)
    return info


def find_brand_accent(master: Any, theme: ThemeInfo) -> dict[str, Any]:
    """Answer the brief's question: *where does #DB0032 actually live?*

    Checks, in order of authority:
      1. the theme colour scheme (the answer we want -- means the renderer can just say
         ``MSO_THEME_COLOR.ACCENT_n`` and inherit the brand automatically);
      2. hard-coded ``srgbClr val="DB0032"`` anywhere in the master's own XML.
    """
    hits = {
        "theme_slots": list(theme.brand_accent_slots),
        "hardcoded_in_master_xml": 0,
        "resolution": "not-found",
    }
    try:
        master_el = _element_of(master)
        for el in master_el.iter(f"{A}srgbClr"):
            if (el.get("val") or "").upper() == BRAND_ACCENT:
                hits["hardcoded_in_master_xml"] += 1
    except Exception:  # pragma: no cover - defensive
        pass

    if hits["theme_slots"]:
        slots = ", ".join(hits["theme_slots"])
        hits["resolution"] = (
            f"theme colour slot(s): {slots} -- renderer should reference the theme slot, "
            f"never the literal hex, so a future rebrand stays a one-file change"
        )
    elif hits["hardcoded_in_master_xml"]:
        hits["resolution"] = (
            f"NOT in the theme; hard-coded {hits['hardcoded_in_master_xml']}x in the master XML. "
            f"Renderer must use the literal RGBColor(0xDB, 0x00, 0x32)."
        )
    return hits


# --------------------------------------------------------------------------------------
# Font size resolution
# --------------------------------------------------------------------------------------

TITLE_TYPES = {"TITLE", "CENTER_TITLE", "VERTICAL_TITLE"}
BODY_TYPES = {"BODY", "SUBTITLE", "OBJECT", "VERTICAL_BODY", "VERTICAL_OBJECT"}


def _lvl1_size_pt(el: Any) -> float | None:
    """First ``a:lvl1pPr/a:defRPr@sz`` under ``el``. ``sz`` is in 1/100 pt (4400 == 44pt)."""
    if el is None:
        return None
    for lvl in el.iter(f"{A}lvl1pPr"):
        rpr = lvl.find(f"{A}defRPr")
        if rpr is not None and rpr.get("sz"):
            try:
                return int(rpr.get("sz")) / 100.0
            except ValueError:
                return None
    return None


def _txstyles_size_pt(master: Any, ph_type: str) -> float | None:
    """Master-level ``p:txStyles`` default for this class of placeholder."""
    try:
        master_el = _element_of(master)
    except AttributeError:
        return None
    tx = master_el.find(f"{P}txStyles")
    if tx is None:
        return None
    if ph_type in TITLE_TYPES:
        style = tx.find(f"{P}titleStyle")
    elif ph_type in BODY_TYPES:
        style = tx.find(f"{P}bodyStyle")
    else:
        style = tx.find(f"{P}otherStyle")
    return _lvl1_size_pt(style)


def resolve_font_pt(layout_ph: Any, master_ph: Any, master: Any, ph_type: str) -> tuple[float, str]:
    """Effective lvl-1 font size for a placeholder, plus *where the number came from*.

    Inheritance chain, most specific first -- this mirrors what PowerPoint itself does:
    layout placeholder list-style -> matching master placeholder list-style ->
    master ``p:txStyles`` -> hard default.

    Returns ``(points, source)``. ``source`` is recorded in the manifest so a reader can
    distinguish a real template value from our fallback guess.
    """
    for obj, source in ((layout_ph, "layout"), (master_ph, "master-placeholder")):
        if obj is None:
            continue
        try:
            size = _lvl1_size_pt(_element_of(obj))
        except AttributeError:
            size = None
        if size:
            return size, source

    size = _txstyles_size_pt(master, ph_type)
    if size:
        return size, "master-txStyles"

    if ph_type in TITLE_TYPES:
        return DEFAULT_PT["title"], "default-guess"
    if ph_type in BODY_TYPES:
        return DEFAULT_PT["body"], "default-guess"
    return DEFAULT_PT["other"], "default-guess"


# --------------------------------------------------------------------------------------
# Content budget
# --------------------------------------------------------------------------------------

def content_budget(width_emu: int | None, height_emu: int | None, font_pt: float,
                   ph_type: str) -> dict[str, Any]:
    """How much text actually fits in this box -- the number we hand to the LLM.

    This is a *typographic estimate*, not a rendering. It exists because python-pptx
    cannot autofit and PowerPoint will happily let text spill off the slide. The model
    is deliberately simple and conservative:

        chars_per_line = box_width_pt / (font_pt * char_width_ratio) * SAFETY
        lines          = box_height_pt / (font_pt * LINE_HEIGHT_RATIO)

    Two character budgets are reported because this corpus is bilingual: a Hangul glyph
    is ~2x the advance width of a Latin one, so a box that holds 60 Latin characters
    holds only ~31 Korean ones. Mixed text should be budgeted against ``cjk``.

    Titles are reported as a flat character cap (they get 1-2 lines). Body placeholders
    are reported as ``max_bullets x max_words_per_bullet``, which is the shape the
    prompt actually needs.
    """
    if not width_emu or not height_emu or not font_pt:
        return {"computable": False,
                "reason": "placeholder has no resolved geometry or font size"}

    w_pt = width_emu / EMU_PER_PT
    h_pt = height_emu / EMU_PER_PT

    latin_cpl = max(1, int(w_pt / (font_pt * LATIN_CHAR_WIDTH_RATIO) * SAFETY))
    cjk_cpl = max(1, int(w_pt / (font_pt * CJK_CHAR_WIDTH_RATIO) * SAFETY))
    max_lines = max(1, int(h_pt / (font_pt * LINE_HEIGHT_RATIO)))

    budget: dict[str, Any] = {
        "computable": True,
        "font_pt": font_pt,
        "chars_per_line_latin": latin_cpl,
        "chars_per_line_cjk": cjk_cpl,
        "max_lines": max_lines,
    }

    if ph_type in TITLE_TYPES:
        # A title that wraps to 3 lines is a design failure; cap the usable lines at 2.
        title_lines = min(2, max_lines)
        budget["max_title_chars_latin"] = latin_cpl * title_lines
        budget["max_title_chars_cjk"] = cjk_cpl * title_lines
        budget["recommended_lines"] = title_lines
    elif ph_type in BODY_TYPES:
        # Each bullet costs its own line plus the space-before gap.
        per_bullet = LINE_HEIGHT_RATIO + BULLET_GAP_RATIO
        max_bullets = max(1, int(h_pt / (font_pt * per_bullet)))
        budget["max_bullets"] = max_bullets
        budget["max_words_per_bullet"] = max(1, int(latin_cpl / LATIN_CHARS_PER_WORD))
        budget["max_chars_per_bullet_latin"] = latin_cpl
        budget["max_chars_per_bullet_cjk"] = cjk_cpl
        budget["note"] = "one line per bullet; a bullet that wraps consumes another slot"
    return budget


# --------------------------------------------------------------------------------------
# Semantic role
# --------------------------------------------------------------------------------------

#: Layout names are authored by humans and this template is Korean; match both languages.
ROLE_NAME_HINTS = (
    ("section-divider", ("section", "divider", "chapter", "구분", "간지", "섹션")),
    ("agenda", ("agenda", "contents", "toc", "목차", "차례", "개요")),
    ("title", ("title slide", "제목", "표지", "cover")),
    ("closing", ("thank", "end", "closing", "감사", "마무리")),
    ("quote", ("quote", "인용")),
    ("comparison", ("comparison", "compare", "비교")),
)


def suggest_role(layout_name: str, ph_types: list[str]) -> str:
    """Best guess at what a layout is *for*, so the AI can pick one by intent.

    Name hints win when present (a human named it), otherwise fall back to placeholder
    composition. This is a suggestion, not a contract -- a human should sanity-check the
    catalog once and correct any row that is wrong.
    """
    lname = (layout_name or "").strip().lower()
    for role, needles in ROLE_NAME_HINTS:
        if any(n in lname for n in needles):
            return role

    content = [t for t in ph_types if t not in ("SLIDE_NUMBER", "FOOTER", "DATE", "HEADER")]
    titles = [t for t in content if t in TITLE_TYPES]
    bodies = [t for t in content if t in BODY_TYPES]

    if not content:
        return "blank"
    if "PICTURE" in content or "BITMAP" in content:
        return "picture"
    if "TABLE" in content:
        return "table"
    if "CHART" in content:
        return "chart"
    if "CENTER_TITLE" in content or "SUBTITLE" in content:
        return "title"
    if titles and not bodies:
        return "title-only"
    if titles and len(bodies) >= 3:
        return "multi-content"
    if titles and len(bodies) == 2:
        return "two-content"
    if titles and len(bodies) == 1:
        return "bullets"
    return "custom"


# --------------------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------------------

def _ph_type_name(ph: Any) -> str:
    try:
        t = ph.placeholder_format.type
    except Exception:  # pragma: no cover - defensive
        return "UNKNOWN"
    if t is None:
        return "UNKNOWN"
    # PP_PLACEHOLDER enum members stringify as e.g. "BODY (2)" depending on version.
    return getattr(t, "name", None) or str(t).split()[0]


def _master_ph_for(master: Any, idx: int, ph_type: str) -> Any:
    """The master placeholder a layout placeholder inherits from: match idx, then type."""
    candidates = list(master.placeholders)
    for ph in candidates:
        if ph.placeholder_format.idx == idx:
            return ph
    for ph in candidates:
        if _ph_type_name(ph) == ph_type:
            return ph
    return None


def extract_placeholder(layout_ph: Any, master: Any) -> dict[str, Any]:
    """One placeholder -> its manifest row, geometry resolved and budget computed."""
    fmt = layout_ph.placeholder_format
    idx = fmt.idx
    ph_type = _ph_type_name(layout_ph)
    master_ph = _master_ph_for(master, idx, ph_type)

    # Geometry may be absent on the layout and inherited from the master. python-pptx
    # surfaces that as None rather than resolving it, so resolve it ourselves.
    geom: dict[str, int | None] = {}
    inherited = False
    for key in ("left", "top", "width", "height"):
        value = getattr(layout_ph, key, None)
        if value is None and master_ph is not None:
            value = getattr(master_ph, key, None)
            if value is not None:
                inherited = True
        geom[key] = None if value is None else int(value)

    font_pt, font_src = resolve_font_pt(layout_ph, master_ph, master, ph_type)

    return {
        "idx": idx,
        "type": ph_type,
        "name": layout_ph.name,
        "geometry_inherited_from_master": inherited,
        "emu": dict(geom),
        "inches": {k: emu_to_in(v) for k, v in geom.items()},
        "font_pt": font_pt,
        "font_pt_source": font_src,
        "content_budget": content_budget(geom["width"], geom["height"], font_pt, ph_type),
    }


def extract_layout(index: int, layout: Any, master: Any) -> dict[str, Any]:
    placeholders = [extract_placeholder(ph, master) for ph in layout.placeholders]
    # A None idx would make a plain (is None, idx) key compare None < None -> TypeError.
    placeholders.sort(key=lambda p: (p["idx"] is None, p["idx"] if p["idx"] is not None else -1))
    ph_types = [p["type"] for p in placeholders]

    # Shapes the template itself draws (logo bars, rules). They render on every slide
    # using this layout and are NOT ours to fill -- but they DO eat visual space.
    decorations = [s.name for s in layout.shapes if not s.is_placeholder]

    return {
        "index": index,
        "layout_id": layout.name,
        "name": layout.name,
        "semantic_role": suggest_role(layout.name, ph_types),
        "placeholder_count": len(placeholders),
        "decoration_shapes": decorations,
        "placeholders": placeholders,
    }


def analyze(template: Path) -> dict[str, Any]:
    """Open the template read-only and return the full manifest dict."""
    from pptx import Presentation

    raw = template.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    # BytesIO => python-pptx never touches the file on disk. Read-only, guaranteed.
    prs = Presentation(io.BytesIO(raw))

    width, height = int(prs.slide_width), int(prs.slide_height)

    masters: list[dict[str, Any]] = []
    for mi, master in enumerate(prs.slide_masters):
        theme = read_theme(master)
        masters.append({
            "index": mi,
            "name": master.name,
            "theme_name": theme.name,
            "font_scheme": {"major": theme.major_font, "minor": theme.minor_font},
            "color_map": theme.color_map,
            "brand_accent": find_brand_accent(master, theme),
            "layout_count": len(master.slide_layouts),
            "layouts": [extract_layout(li, lay, master)
                        for li, lay in enumerate(master.slide_layouts)],
        })

    existing = [{"index": i, "layout": s.slide_layout.name, "shape_count": len(s.shapes)}
                for i, s in enumerate(prs.slides)]

    return {
        "schema_version": "1.0",
        "generated_by": "aippt.analyze_pptx_master",
        "source": {
            "filename": template.name,
            "sha256": digest,
            "bytes": len(raw),
        },
        "deck": {
            "slide_width_emu": width,
            "slide_height_emu": height,
            "slide_width_in": emu_to_in(width),
            "slide_height_in": emu_to_in(height),
            "aspect_ratio": aspect_label(width, height),
            "master_count": len(prs.slide_masters),
            "layout_count_first_master": len(prs.slide_layouts),
            "existing_slide_count": len(prs.slides),
        },
        "masters": masters,
        "existing_slides": existing,
        "budget_model": {
            "latin_char_width_ratio": LATIN_CHAR_WIDTH_RATIO,
            "cjk_char_width_ratio": CJK_CHAR_WIDTH_RATIO,
            "line_height_ratio": LINE_HEIGHT_RATIO,
            "safety_factor": SAFETY,
            "caveat": "typographic estimate, not a render; the render->PNG check is authoritative",
        },
    }


# --------------------------------------------------------------------------------------
# Rendering the artifacts
# --------------------------------------------------------------------------------------

def render_catalog(manifest: dict[str, Any]) -> str:
    """The prompt-context artifact: everything the AI author needs, nothing it doesn't.

    Kept deliberately compact -- this text is pasted into every generation call, so every
    token in it is paid for on every slide.
    """
    deck = manifest["deck"]
    out: list[str] = []
    w = out.append

    w("# Layout Catalog")
    w("")
    w(f"Generated from `{manifest['source']['filename']}` "
      f"(sha256 `{manifest['source']['sha256'][:12]}...`) by `analyze_pptx_master.py`.")
    w("**Do not hand-edit** -- re-run the analyzer instead.")
    w("")
    w(f"- Slide size: **{deck['slide_width_in']}in x {deck['slide_height_in']}in** "
      f"({deck['aspect_ratio']}), {deck['slide_width_emu']} x {deck['slide_height_emu']} EMU")
    w(f"- Masters: **{deck['master_count']}** | "
      f"Layouts (first master): **{deck['layout_count_first_master']}** | "
      f"Existing slides: **{deck['existing_slide_count']}**")
    w("")

    for master in manifest["masters"]:
        w(f"## Master {master['index']}: {master['name']}")
        w("")
        major = master["font_scheme"].get("major") or {}
        minor = master["font_scheme"].get("minor") or {}
        w(f"- Theme: `{master['theme_name']}`")
        w(f"- Major font (headings): latin `{major.get('latin')}` / east-asian `{major.get('ea')}`")
        w(f"- Minor font (body): latin `{minor.get('latin')}` / east-asian `{minor.get('ea')}`")
        w(f"- Brand accent `#{BRAND_ACCENT}`: {master['brand_accent']['resolution']}")
        if master["color_map"]:
            pairs = ", ".join(f"{k}=#{v}" for k, v in master["color_map"].items())
            w(f"- Colour map: {pairs}")
        w("")
        w("### Layouts")
        w("")
        w("| # | layout_id | role | placeholders |")
        w("|---|-----------|------|--------------|")
        for lay in master["layouts"]:
            types = ", ".join(f"{p['type']}(idx {p['idx']})" for p in lay["placeholders"]) or "-none-"
            w(f"| {lay['index']} | `{lay['layout_id']}` | {lay['semantic_role']} | {types} |")
        w("")

        w("### Content budgets")
        w("")
        w("The AI author MUST respect these. `cjk` applies to Korean text, `latin` to English;")
        w("for mixed text, budget against `cjk`.")
        w("")
        for lay in master["layouts"]:
            if not lay["placeholders"]:
                continue
            w(f"**`{lay['layout_id']}`** ({lay['semantic_role']})")
            w("")
            for ph in lay["placeholders"]:
                b = ph["content_budget"]
                head = f"- `idx {ph['idx']}` {ph['type']} -- {ph['inches']['width']}x{ph['inches']['height']}in @ {ph['font_pt']}pt"
                if not b.get("computable"):
                    w(head + f" -- budget unavailable ({b.get('reason')})")
                    continue
                if "max_title_chars_cjk" in b:
                    w(head + f" -- max **{b['max_title_chars_latin']} latin chars** "
                             f"/ **{b['max_title_chars_cjk']} korean chars**, "
                             f"<= {b['recommended_lines']} lines")
                elif "max_bullets" in b:
                    w(head + f" -- max **{b['max_bullets']} bullets** x "
                             f"**{b['max_words_per_bullet']} words** "
                             f"({b['max_chars_per_bullet_latin']} latin / "
                             f"{b['max_chars_per_bullet_cjk']} korean chars per bullet)")
                else:
                    w(head + f" -- {b['chars_per_line_latin']} latin chars/line, "
                             f"{b['max_lines']} lines")
            w("")

    w("---")
    w("")
    w("## Allowed `layout_id` values")
    w("")
    w("The IR `layout_id` field MUST be exactly one of:")
    w("")
    for master in manifest["masters"]:
        for lay in master["layouts"]:
            w(f"- `{lay['layout_id']}`  ({lay['semantic_role']})")
    w("")
    return "\n".join(out) + "\n"


def print_summary(manifest: dict[str, Any]) -> None:
    deck = manifest["deck"]
    print("=" * 78)
    print(f"  {manifest['source']['filename']}")
    print("=" * 78)
    print(f"  slide size : {deck['slide_width_in']}in x {deck['slide_height_in']}in  "
          f"({deck['aspect_ratio']})  [{deck['slide_width_emu']} x {deck['slide_height_emu']} EMU]")
    print(f"  masters    : {deck['master_count']}")
    print(f"  layouts    : {deck['layout_count_first_master']} (first master)")
    print(f"  slides     : {deck['existing_slide_count']} already in the template")
    print()

    for master in manifest["masters"]:
        print(f"MASTER {master['index']}: {master['name']}  (theme: {master['theme_name']})")
        major = master["font_scheme"].get("major") or {}
        minor = master["font_scheme"].get("minor") or {}
        print(f"  fonts  : major latin={major.get('latin')} ea={major.get('ea')} | "
              f"minor latin={minor.get('latin')} ea={minor.get('ea')}")
        print(f"  #{BRAND_ACCENT}: {master['brand_accent']['resolution']}")
        if master["color_map"]:
            print("  colors : " + ", ".join(f"{k}=#{v}" for k, v in master["color_map"].items()))
        print()
        for lay in master["layouts"]:
            print(f"  [{lay['index']:>2}] {lay['layout_id']!r}  "
                  f"role={lay['semantic_role']}  placeholders={lay['placeholder_count']}")
            for ph in lay["placeholders"]:
                inch = ph["inches"]
                mark = " (inherited)" if ph["geometry_inherited_from_master"] else ""
                print(f"        idx={ph['idx']:<3} {ph['type']:<14} {ph['name']!r}")
                print(f"          box  : L={inch['left']} T={inch['top']} "
                      f"W={inch['width']} H={inch['height']} in{mark}")
                print(f"          font : {ph['font_pt']}pt  (from {ph['font_pt_source']})")
                b = ph["content_budget"]
                if not b.get("computable"):
                    print(f"          budget: n/a - {b.get('reason')}")
                elif "max_title_chars_cjk" in b:
                    print(f"          budget: title <= {b['max_title_chars_latin']} latin "
                          f"/ {b['max_title_chars_cjk']} korean chars")
                elif "max_bullets" in b:
                    print(f"          budget: {b['max_bullets']} bullets x "
                          f"{b['max_words_per_bullet']} words "
                          f"({b['max_chars_per_bullet_cjk']} korean chars/bullet)")
                else:
                    print(f"          budget: {b['chars_per_line_latin']} latin chars/line "
                          f"x {b['max_lines']} lines")
            if lay["decoration_shapes"]:
                print(f"        decoration (drawn by the template, not fillable): "
                      f"{', '.join(lay['decoration_shapes'])}")
            print()

    if manifest["existing_slides"]:
        print("EXISTING SLIDES IN TEMPLATE")
        for s in manifest["existing_slides"]:
            print(f"  [{s['index']:>2}] layout={s['layout']!r} shapes={s['shape_count']}")
        print()


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------

DEFAULT_TEMPLATE_NAME = "Vieworks_R&D_ppt_Template.pptx"


def find_default_template(start: Path) -> Path | None:
    """Look for the template beside the repo, then walk up. Keeps the no-arg case working."""
    for base in (start, *start.parents):
        candidate = base / DEFAULT_TEMPLATE_NAME
        if candidate.is_file():
            return candidate
    return None


def main(argv: list[str] | None = None) -> int:
    here = Path(__file__).resolve()
    repo_root = here.parents[2]          # .../src/aippt/x.py -> repo root

    parser = argparse.ArgumentParser(
        description="Extract layouts, theme and content budgets from the PPTX master.")
    parser.add_argument("--template", type=Path, default=None,
                        help=f"path to the .pptx (default: nearest {DEFAULT_TEMPLATE_NAME})")
    parser.add_argument("--out-dir", type=Path, default=repo_root / "reference",
                        help="where to write layout_manifest.json / layout_catalog.md")
    parser.add_argument("--quiet", action="store_true", help="suppress the stdout summary")
    args = parser.parse_args(argv)

    # Korean layout names and Hangul in the summary must survive a Windows console.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - very old / redirected stdout
        pass

    template = args.template or find_default_template(repo_root)
    if template is None:
        print(f"ERROR: could not find {DEFAULT_TEMPLATE_NAME}. Pass --template <path>.",
              file=sys.stderr)
        return 2
    template = Path(template).expanduser().resolve()
    if not template.is_file():
        print(f"ERROR: template not found: {template}", file=sys.stderr)
        return 2

    try:
        import pptx  # noqa: F401
    except ImportError:
        print("ERROR: python-pptx is not installed.  pip install -r requirements.txt",
              file=sys.stderr)
        return 3

    try:
        manifest = analyze(template)
    except Exception as exc:  # noqa: BLE001 - top-level CLI guard, we want the message
        print(f"ERROR: failed to parse {template.name}: {exc!r}", file=sys.stderr)
        return 4

    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "layout_manifest.json"
    md_path = out_dir / "layout_catalog.md"
    json_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_catalog(manifest), encoding="utf-8")

    if not args.quiet:
        print_summary(manifest)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
