#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""canvas-ir/1 validation. Phase 1A, task 1.1.

jsonschema first, then the semantic rules the schema cannot express.

EVERY VIOLATION IS COLLECTED AND RAISED ONCE. A validator that dies on the first error turns a
20-element deck into a 20-round debugging session, and the person paying for that is the human in
the editor, not the renderer. That applies ACROSS the stages, not merely within one: a schema
failure does not stop the semantic pass, and a semantic failure does not stop the schema pass.
Every stage runs, every stage returns its problems, and validate() raises exactly once.

The price of that is paid here: _check_semantics runs on payloads the schema has already rejected,
so it can assume NOTHING about the shape of what it is reading. Every rule guards the specific
fields it needs and silently declines to run when they are absent or of the wrong type -- silently,
because the schema section of the same message already names them, and a second complaint about the
same field is noise. A rule is never skipped because some OTHER field of the same element is broken.

There is exactly one narrowing, and it is announced in the message rather than hidden:

    A stale canvas skips rule 1 (reserved regions) and rule 2 (slide bounds), and NOTHING else.

Those two rules are the only ones measured in the model space. A payload authored at 1920x1080 has
coordinates that mean nothing at 960x540, so running them would report 20 bogus "outside the 960x540
slide" lines on a 20-element deck -- manufacturing false violations, not surfacing real ones. The
accent1 ban, control characters, duplicate ids and the whole schema are canvas-INDEPENDENT: they are
just as wrong in any model space, so they still run, and suppressing them would be indefensible. The
payload section says in so many words which two rules were skipped and why. The payload is still
NEVER rescaled -- rescaling yields a plausible-looking, subtly wrong deck, which is far worse than a
hard failure.

THIS MODULE IS PURE. No filesystem beyond reading its own schema.json, no pin, no template. That is
deliberate: `target.template_sha256` is checked against the pin in render_canvas.py, so validate()
can be unit-tested without a 1.2 MB template on disk.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from jsonschema import Draft202012Validator

from aippt.canvas.geometry import (
    CANVAS,
    CANVAS_H,
    CANVAS_W,
    REJECT_REGIONS,
    element_bbox,
    out_of_bounds,
    reserved_violations,
)

SCHEMA_PATH = Path(__file__).with_name("schema.json")

FORBIDDEN = "4472C4"  # theme accent1
BRAND_RED = "#FF0032"

ELEMENT_TYPES = ("rect", "ellipse", "triangle", "textbox", "connector")

# C0 minus the two we permit: \t (\x09) and \n (\x0a). Note this catches \r and \x0b (vertical
# tab) -- both of which python-pptx would otherwise treat as meaningful, and neither of which a
# visual editor has any legitimate way to produce.
C0_FORBIDDEN = re.compile(r"[\x00-\x08\x0b-\x1f]")

# Appended to the payload section when the canvas is stale. Nothing is suppressed in silence: the
# author is told exactly which rules did not run and how to get them to run.
STALE_SKIP_NOTE = (
    "  NOTE: rule 1 (reserved regions) and rule 2 (slide bounds) were SKIPPED for every element. "
    f"They are the only two rules measured in the {CANVAS_W}x{CANVAS_H} model space -- the one "
    "this payload was not authored in -- so running them here would manufacture false violations "
    "rather than find real ones. Everything else WAS checked: the schema, the accent1 ban, "
    "control characters and duplicate ids are all canvas-independent. Fix the canvas and "
    "re-validate to see the two skipped rules."
)


class CanvasValidationError(ValueError):
    """One raise, every violation. `str(exc)` is a numbered list, ready to print."""


class StalePayloadError(CanvasValidationError):
    """The payload was authored against a different canvas or a different template.

    A subclass, so that a caller catching CanvasValidationError catches this too -- both mean "do
    not render this" -- while a caller that wants to say "reload the editor" can catch it alone.
    """


@lru_cache(maxsize=1)
def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)  # the schema itself is an artifact; check it once
    return Draft202012Validator(schema)


def validate(ir: Any) -> None:
    """Raise CanvasValidationError listing every violation, or return None.

    Nothing escapes this function but CanvasValidationError. The stages below run on payloads that
    have already failed the schema, so they are written to degrade -- never to raise -- on anything
    they cannot read.
    """
    if not isinstance(ir, dict):
        # A precondition, not a violation-suppressing short-circuit: there is literally nothing to
        # inspect on a list or a string.
        raise CanvasValidationError(f"payload must be a JSON object, got {type(ir).__name__}")

    canvas_problems = _check_canvas(ir)
    schema_problems = _check_schema(ir)
    semantic_problems = _check_semantics(ir, canvas_ok=not canvas_problems)

    if not (canvas_problems or schema_problems or semantic_problems):
        return

    sections: list[str] = []
    if canvas_problems:
        sections.append(_format(canvas_problems, "payload") + "\n" + STALE_SKIP_NOTE)
    if schema_problems:
        sections.append(_format(schema_problems, "schema"))
    if semantic_problems:
        sections.append(_format(semantic_problems, "semantic"))

    # A stale canvas is still a StalePayloadError -- a caller that wants to say "reload the editor"
    # rather than "fix your deck" keys off the class. It no longer swallows the rest of the report.
    exc = StalePayloadError if canvas_problems else CanvasValidationError
    raise exc("\n".join(sections))


# --- rule 6: the canvas ------------------------------------------------------------------------


def _check_canvas(ir: dict[str, Any]) -> list[str]:
    if ir.get("canvas") == CANVAS:
        return []
    return [
        f"stale payload: canvas is {ir.get('canvas')!r}, but this renderer speaks only "
        f"{CANVAS!r}. The payload was authored against a different model space. It is never "
        f"rescaled -- reload the editor and re-export."
    ]


# --- schema ----------------------------------------------------------------------------------


def _check_schema(ir: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for err in sorted(_validator().iter_errors(ir), key=lambda e: list(map(str, e.absolute_path))):
        problems.extend(_explain(err, ir))
    return problems


def _explain(err: Any, ir: dict[str, Any]) -> list[str]:
    """Turn one jsonschema error into human-readable lines.

    jsonschema reports a failed `oneOf` as a single useless line -- "is not valid under any of the
    given schemas" -- and buries the real reason in err.context. Every element branch is
    discriminated by a `type` const, so exactly one branch is the one the author MEANT: the branch
    that did NOT complain about `type`. Report that branch's errors and drop the other four.
    """
    if not err.context:
        return [f"{_where(err, ir)}: {err.message}"]

    by_branch: dict[Any, list[Any]] = {}
    for sub in err.context:
        by_branch.setdefault(sub.schema_path[0], []).append(sub)

    intended = {
        branch: subs
        for branch, subs in by_branch.items()
        if not any(_is_type_discriminator(s) for s in subs)
    }

    if len(intended) != 1:
        # Either every branch rejected the `type` (so the type itself is the error), or -- which a
        # closed const discriminator makes impossible -- more than one branch matched. Report the
        # type, because that is the field that has to change.
        got = err.instance.get("type") if isinstance(err.instance, dict) else None
        where = _where(err, ir)
        if got is None:
            return [f"{where}: missing required field 'type' (one of {list(ELEMENT_TYPES)})"]
        return [f"{where}: unknown element type {got!r} (expected one of {list(ELEMENT_TYPES)})"]

    (subs,) = intended.values()
    return [
        f"{_where(sub, ir)}: {sub.message}"
        for sub in sorted(subs, key=lambda e: list(map(str, e.absolute_path)))
    ]


def _is_type_discriminator(sub: Any) -> bool:
    """Is this sub-error the branch saying 'wrong `type`, not my element'?"""
    path = list(sub.absolute_path)
    return bool(path) and path[-1] == "type" and sub.validator in ("const", "enum")


def _where(err: Any, ir: dict[str, Any]) -> str:
    """'elements[2] (id "box1")' -- a JSON path, plus the element id when one can be resolved."""
    path = list(err.absolute_path)
    if not path:
        return "<root>"

    out = str(path[0])
    for part in path[1:]:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"

    if len(path) >= 2 and path[0] == "elements" and isinstance(path[1], int):
        elements = ir.get("elements")
        if isinstance(elements, list) and path[1] < len(elements):
            el = elements[path[1]]
            if isinstance(el, dict) and isinstance(el.get("id"), str):
                out += f' (id "{el["id"]}")'
    return out


# --- semantics -------------------------------------------------------------------------------


def _check_semantics(ir: dict[str, Any], *, canvas_ok: bool) -> list[str]:
    """The rules the schema cannot express.

    The IR is NOT known to be structurally valid here -- this runs even when _check_schema found
    problems, because a schema error must not hide a semantic one. So every rule below checks the
    fields IT needs and declines to run when they are missing or of the wrong type. It never skips
    an element wholesale just because one unrelated field is broken.
    """
    problems: list[str] = []
    seen: dict[str, int] = {}

    for field, text in _texts_of(ir.get("title"), "title"):
        problems.extend(_control_char_problems("<root>", field, text))

    elements = ir.get("elements")
    if not isinstance(elements, list):
        return problems  # the schema names it; there is nothing here to iterate

    for i, el in enumerate(elements):
        if not isinstance(el, dict):
            continue  # nothing to inspect and nothing to report that the schema has not said

        eid = el.get("id")
        etype = el.get("type")
        # An element whose id or type the schema has already rejected still gets a label, so that
        # the rules that DO apply to it have somewhere to point. The index always identifies it.
        shown_id = eid if isinstance(eid, str) else "?"
        shown_type = etype if isinstance(etype, str) else "?"
        at = f'elements[{i}] (id "{shown_id}", type "{shown_type}")'

        # 5. Duplicate ids. The id becomes the shape's NAME, and the round-trip suite finds shapes
        #    by name -- two shapes sharing one makes one unfindable and the other unverifiable.
        #    Needs a string id; an element without one is not a duplicate of anything.
        if isinstance(eid, str):
            if eid in seen:
                problems.append(
                    f"{at}: duplicate id -- already used by elements[{seen[eid]}]. Ids become "
                    f"shape names in the PPTX and must be unique."
                )
            else:
                seen[eid] = i

        # 1 and 2. The geometry rules -- the ONLY two measured in the model space. They need a
        #    readable box, and they need the payload to have been drawn in this model space at all.
        if canvas_ok and _has_readable_geometry(el):
            # 1. Reserved regions. The box maths lives in geometry.py and is not reimplemented here.
            for region in reserved_violations(el):
                x1, y1, x2, y2 = element_bbox(el)
                problems.append(
                    f"{at}: intersects {region} {REJECT_REGIONS[region]} -- its bounding box is "
                    f"({x1:g}, {y1:g}, {x2:g}, {y2:g}). That region carries inherited layout "
                    f"chrome (the Vieworks logo, the gradient divider, the page number), which "
                    f"always renders BEHIND slide content and cannot be raised above it. Move the "
                    f"element into the body (y 92 -> 500)."
                )

            # 2. Slide bounds.
            if out_of_bounds(el):
                x1, y1, x2, y2 = element_bbox(el)
                problems.append(
                    f"{at}: falls outside the {CANVAS_W}x{CANVAS_H} slide -- its bounding box is "
                    f"({x1:g}, {y1:g}, {x2:g}, {y2:g})."
                    + (
                        "  (This is the ROTATED footprint; the unrotated path box would fit.)"
                        if (_num(el.get("rotation")) or 0.0) % 360.0
                        else ""
                    )
                )

        # 3. The forbidden colour. Canvas-independent: accent1 is accent1 in any model space.
        for field, value in _colours_of(el):
            if value.lstrip("#").upper() == FORBIDDEN:
                problems.append(
                    f"{at}: {field} is {value} -- this template's theme accent1. It is banned as "
                    f"an explicit author choice so that 'no accent1 in any renderer-created shape' "
                    f"(plan Sec 7.3) stays a machine-checkable invariant instead of an aspiration: "
                    f"if a user could legitimately pick it, that assertion could never be checked. "
                    f"Pick another colour -- new content defaults to {BRAND_RED}."
                )

        # 4. Control characters. Canvas-independent too.
        for field, text in _texts_of(el.get("text"), "text"):
            problems.extend(_control_char_problems(at, field, text))

    return problems


def _num(v: Any) -> float | None:
    """v as a float, or None if it is not a number.

    `bool` is rejected explicitly: it is an `int` in Python, and `True` is not a coordinate. The
    schema rejects it too (jsonschema does not count a bool as a number), so a payload carrying one
    is already being reported -- this just stops geometry.py's float() from quietly accepting 1.0.
    """
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def _has_readable_geometry(el: dict[str, Any]) -> bool:
    """Can element_bbox() read this element without raising?

    It does `float(el["x"])` and friends, so a missing coordinate is a KeyError and a string one is
    a ValueError. geometry.py is not in scope to change and should not be: the guarding belongs on
    the caller, which is the side that knows the payload may be malformed.

    A coordinate that is numeric but out of RANGE -- `w: 0`, `h: -5` -- is still numeric, so
    geometry still runs on it. That is intended: it is the schema's job to complain about the range,
    and a degenerate box produces no spurious geometry violation anyway.
    """
    keys = ("x1", "y1", "x2", "y2") if el.get("type") == "connector" else ("x", "y", "w", "h")
    if any(_num(el.get(k)) is None for k in keys):
        return False
    rotation = el.get("rotation")  # absent or null is 0; anything else must be a number
    return rotation is None or _num(rotation) is not None


def _control_char_problems(at: str, field: str, text: str) -> list[str]:
    m = C0_FORBIDDEN.search(text)
    if m is None:
        return []
    return [
        f"{at}: {field} contains the control character U+{ord(m.group()):04X} at index {m.start()}. "
        f"Only \\t and \\n are permitted (\\n becomes a DrawingML <a:br/>). python-pptx 1.0.x would "
        f"escape it to _x00XX_ rather than corrupt the file, so this is an interoperability policy, "
        f"not a corruption fix -- but a visual editor has no legitimate source for one."
    ]


def _runs_of(text: Any) -> Iterator[tuple[int, int, dict[str, Any]]]:
    """(paragraph index, run index, run) for every run that is shaped like one.

    Anything mis-shaped -- a `paragraphs` that is not a list, a run that is not a dict -- is skipped
    without comment. The schema section of the same message already names it.
    """
    if not isinstance(text, dict):
        return
    paragraphs = text.get("paragraphs")
    if not isinstance(paragraphs, list):
        return
    for pi, para in enumerate(paragraphs):
        if not isinstance(para, dict):
            continue
        runs = para.get("runs")
        if not isinstance(runs, list):
            continue
        for ri, run in enumerate(runs):
            if isinstance(run, dict):
                yield pi, ri, run


def _colours_of(el: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Every colour an element states explicitly, with a path to it. Non-string colours are the
    schema's problem, not rule 3's -- rule 3 only asks whether a stated colour is accent1."""
    fill = el.get("fill")
    if isinstance(fill, str):
        yield "fill", fill

    stroke = el.get("stroke")
    if isinstance(stroke, dict) and isinstance(stroke.get("color"), str):
        yield "stroke.color", stroke["color"]

    if el.get("type") == "connector" and isinstance(el.get("color"), str):
        yield "color", el["color"]

    for pi, ri, run in _runs_of(el.get("text")):
        colour = run.get("color")
        if isinstance(colour, str):
            yield f"text.paragraphs[{pi}].runs[{ri}].color", colour


def _texts_of(text: Any, label: str) -> Iterator[tuple[str, str]]:
    """Every author-supplied string that ends up inside an <a:t>, with a path to it."""
    if isinstance(text, str):  # the `title` field
        yield label, text
        return
    for pi, ri, run in _runs_of(text):
        t = run.get("t")
        if isinstance(t, str):
            yield f"{label}.paragraphs[{pi}].runs[{ri}].t", t


def _format(problems: list[str], kind: str) -> str:
    head = f"{len(problems)} {kind} violation{'s' if len(problems) != 1 else ''}:"
    return "\n".join([head, *(f"  {i}. {p}" for i, p in enumerate(problems, 1))])
