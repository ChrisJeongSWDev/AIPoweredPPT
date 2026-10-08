#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""canvas/validate.py -- the schema and the six semantic rules.

Two things are being pinned here, and the second matters more than it looks.

1. The rules themselves: reserved regions, slide bounds, the accent1 ban, control characters,
   duplicate ids, and the stale-canvas hard fail.

2. THAT EVERY VIOLATION IS REPORTED AT ONCE, ACROSS EVERY STAGE. A validator that dies on the first
   error turns a 20-element deck into a 20-round debugging session. It is not enough to collect
   within a stage and raise between them: a schema error must not hide a semantic one, and vice
   versa. Every stage runs, and validate() raises exactly once with the lot. Several tests below
   deliberately stack violations from DIFFERENT stages into one payload and assert that all of them
   are named -- that behaviour is a feature with a cost (semantics now runs on payloads the schema
   has already rejected, so it can assume nothing about their shape), so it needs tests that fail
   when someone "simplifies" it back into an early raise.

   The only narrowing is that a stale canvas skips rules 1 and 2 -- reserved regions and slide
   bounds, the two measured in the model space -- because coordinates authored at 1920x1080 mean
   nothing at 960x540 and checking them would MANUFACTURE violations rather than find them. The
   message says so explicitly. Nothing else is suppressed: the schema, accent1, control characters
   and duplicate ids are canvas-independent and still run.

3. And consequently, THAT NOTHING ESCAPES validate() BUT CanvasValidationError. A raw KeyError from
   the semantic pass would be a worse bug than the one collect-all-stages fixes: render_canvas.py
   catches CanvasValidationError for its non-zero exit, so anything else is an unhandled CLI crash.

`target.template_sha256` is NOT checked here -- it is a render-time check, so that this module
stays pure and unit-testable without a 1.2 MB template on disk. test_roundtrip.py covers it.

Non-ASCII characters that matter (U+00A0) are written as chr(0xA0), never as a literal: an
invisible character in a test is a test nobody can review.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from aippt.canvas.pin import load_pin
from aippt.canvas.validate import CanvasValidationError, StalePayloadError, validate

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "canvas"

NBSP = chr(0xA0)

# Fixtures that must render. `edges` is the boundary corpus and it must PASS: an element flush with
# the header at y == 92, one whose bottom edge is exactly y == 500 sitting over the footer's
# x-range, and a full-bleed band that leaves BODY_SAFE but touches neither reserved region.
VALID = ["minimal", "shapes", "connectors", "rotated", "text", "edges"]

# Fixtures that validate() must reject. `reject_sha` is deliberately absent -- it is valid IR whose
# template SHA is stale, which is a RENDER-time failure. See test_roundtrip.py.
REJECT = [
    "reject_header",
    "reject_footer",
    "reject_rotated_into_header",
    "reject_accent1",
    "reject_control_char",
    "reject_extent",
    "reject_duplicate_id",
    "reject_out_of_bounds",
    "reject_canvas",
]


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def violations(ir: dict) -> str:
    """Run validate() expecting failure, and hand back the message."""
    with pytest.raises(CanvasValidationError) as exc:
        validate(ir)
    return str(exc.value)


# --- the corpus ------------------------------------------------------------------------------


@pytest.mark.parametrize("name", VALID)
def test_valid_fixtures_validate(name):
    validate(load(name))  # must not raise


@pytest.mark.parametrize("name", REJECT)
def test_rejection_fixtures_are_rejected(name):
    with pytest.raises(CanvasValidationError):
        validate(load(name))


@pytest.mark.parametrize("name", VALID + ["reject_sha"])
def test_every_fixture_is_well_formed_json_with_the_right_shape(name):
    ir = load(name)
    assert ir["schema"] == "canvas-ir/1"
    assert ir["canvas"] == {"w": 960, "h": 540, "unit": "pt"}
    assert ir["target"]["layout_index"] == 3


@pytest.mark.parametrize("name", VALID)
def test_valid_fixtures_carry_the_pinned_template_sha(name):
    """If this fails after a deliberate re-pin, the fixtures need their template_sha256 updated --
    they are payloads, and a payload authored against the old template IS stale."""
    pin = load_pin()
    assert load(name)["target"]["template_sha256"] == pin["renderer_template"]["sha256"]


# --- rule 6: the stale canvas ----------------------------------------------------------------


def test_a_wrong_canvas_is_a_stale_payload_not_a_rescale():
    with pytest.raises(StalePayloadError) as exc:
        validate(load("reject_canvas"))
    assert "stale payload" in str(exc.value)
    assert "never rescaled" in str(exc.value).replace("\n", " ")


def test_stale_payload_is_a_canvas_validation_error():
    """A caller that catches CanvasValidationError must catch this too -- both mean 'do not render'."""
    assert issubclass(StalePayloadError, CanvasValidationError)


def test_a_stale_canvas_still_reports_canvas_independent_violations():
    """A stale canvas narrows the report to the two rules that CANNOT survive it, and nothing more.

    Rules 1 and 2 are measured in the model space, so running them against coordinates authored at
    1920x1080 would manufacture violations rather than find them -- `in_header` and `off_slide`
    below are exactly that trap, and neither may be named. But accent1, control characters,
    duplicate ids and the schema are canvas-INDEPENDENT: they are just as wrong in any model space,
    and suppressing them was the defect this test used to lock in. They must all still fire, and the
    message must say which two rules it skipped.
    """
    ir = load("reject_canvas")
    ir["elements"] += [
        # schema (w/h must be > 0) AND semantic (accent1) -- both canvas-independent.
        {"id": "accent", "type": "rect", "x": 0, "y": 0, "w": 0, "h": 0, "fill": "#4472C4"},
        # These two exist ONLY to be skipped. Were geometry to run, the first would hit
        # HEADER_RESERVED and the second would fall off a 960x540 slide.
        {"id": "in_header", "type": "rect", "x": 100, "y": 0, "w": 200, "h": 50, "fill": "#FF0032"},
        {"id": "off_slide", "type": "rect", "x": 1500, "y": 900, "w": 200, "h": 99, "fill": "#FF0032"},
    ]

    with pytest.raises(StalePayloadError) as exc:  # the class contract is unchanged
        validate(ir)
    msg = str(exc.value)

    assert "stale payload" in msg  # rule 6 still fires
    assert "4472C4" in msg.upper()  # and no longer swallows this
    assert "schema violation" in msg  # the schema stage ran too (w: 0, h: 0, canvas.w, canvas.h)

    assert "HEADER_RESERVED" not in msg  # geometry IS still skipped: those coords are meaningless
    assert "outside the 960x540 slide" not in msg
    assert "SKIPPED" in msg  # and the author is TOLD it was skipped, rather than left to guess


# --- rule 1: reserved regions ----------------------------------------------------------------


def test_an_element_in_the_header_names_the_region():
    msg = violations(load("reject_header"))
    assert "HEADER_RESERVED" in msg
    assert "over_the_logo" in msg


def test_an_element_in_the_footer_names_the_region():
    msg = violations(load("reject_footer"))
    assert "FOOTER_RESERVED" in msg
    assert "over_the_page_number" in msg


def test_only_the_rotated_footprint_reaches_the_header():
    """The path box (y 95..115) clears HEADER_RESERVED; the 45-degree footprint does not."""
    ir = load("reject_rotated_into_header")
    assert "HEADER_RESERVED" in violations(ir)

    ir["elements"][0]["rotation"] = 0  # the same box, unspun -- now legal
    validate(ir)


def test_the_edge_cases_at_y_92_and_y_500_pass():
    """The regression guard, at the level the renderer actually sees. If the half-open rule ever
    regresses to inclusive, this fixture is what fails first."""
    validate(load("edges"))


# --- rule 2: slide bounds --------------------------------------------------------------------


def test_out_of_bounds_elements_are_rejected_and_both_are_named():
    msg = violations(load("reject_out_of_bounds"))
    assert "off_the_right_edge" in msg
    assert "negative_x" in msg
    assert "2 semantic violations" in msg


# --- rule 3: the accent1 ban -----------------------------------------------------------------


def test_accent1_is_rejected_everywhere_it_can_hide():
    """fill, stroke.color, a run colour and a connector colour -- four places, four violations, one
    raise. The lowercase '#4472c4' must be caught too."""
    msg = violations(load("reject_accent1"))
    assert "4 semantic violations" in msg
    for eid in ("bad_fill", "bad_stroke", "bad_run", "bad_connector"):
        assert eid in msg


def test_the_accent1_error_explains_why_a_legal_looking_colour_is_banned():
    msg = violations(load("reject_accent1"))
    assert "accent1" in msg
    assert "#FF0032" in msg  # it points the author at the brand default


def test_the_brand_red_is_not_banned():
    validate(load("minimal"))  # its only fill is #FF0032


# --- rule 4: control characters ---------------------------------------------------------------


def test_c0_control_characters_are_rejected():
    """The fixture carries U+0008, U+000C and U+000D, plus a fourth element whose text uses only tab
    and newline. Three violations, and the legal element is not among them."""
    msg = violations(load("reject_control_char"))
    assert "3 semantic violations" in msg
    for eid in ("backspace_u0008", "formfeed_u000c", "carriage_return_u000d"):
        assert eid in msg
    assert "tab_and_newline_are_legal" not in msg


@pytest.mark.parametrize("codepoint", [0x00, 0x07, 0x08, 0x0B, 0x0C, 0x0D, 0x1F])
def test_every_forbidden_c0_character_is_rejected(codepoint):
    ir = load("minimal")
    ir["elements"][0]["text"] = {
        "paragraphs": [{"runs": [{"t": "a" + chr(codepoint) + "b", "size": 14, "color": "#000000"}]}]
    }
    assert "control character" in violations(ir)


@pytest.mark.parametrize("codepoint", [0x09, 0x0A])
def test_tab_and_newline_are_permitted(codepoint):
    ir = load("minimal")
    ir["elements"][0]["text"] = {
        "paragraphs": [{"runs": [{"t": "a" + chr(codepoint) + "b", "size": 14, "color": "#000000"}]}]
    }
    validate(ir)  # must not raise -- \n becomes <a:br/>, \t stays a tab


def test_a_control_character_in_the_title_is_rejected():
    ir = load("minimal")
    ir["title"] = "bad" + chr(0x07) + "title"
    assert "control character" in violations(ir)


def test_nbsp_is_not_a_control_character():
    """U+00A0 must survive untouched -- it is how an author asks for a space that will not break."""
    ir = load("text")
    runs = ir["elements"][0]["text"]["paragraphs"][3]["runs"]
    assert NBSP in runs[0]["t"], "the text fixture is supposed to carry a real U+00A0"
    validate(ir)


# --- rule 5: duplicate ids --------------------------------------------------------------------


def test_duplicate_ids_are_rejected():
    msg = violations(load("reject_duplicate_id"))
    assert "duplicate id" in msg
    assert "elements[0]" in msg  # it points at the FIRST use, not merely the second


# --- the schema ------------------------------------------------------------------------------


def test_non_positive_extents_are_rejected():
    msg = violations(load("reject_extent"))
    assert "zero_width" in msg
    assert "negative_height" in msg


def test_a_bad_element_type_gets_a_precise_error_not_a_oneof_dump():
    """The whole point of discriminating on a `type` const: the author must be told 'unknown element
    type', not 'is not valid under any of the given schemas'."""
    ir = load("minimal")
    ir["elements"][0]["type"] = "hexagon"
    msg = violations(ir)
    assert "unknown element type" in msg
    assert "hexagon" in msg
    assert "not valid under any of the given schemas" not in msg


def test_a_missing_type_says_so():
    ir = load("minimal")
    del ir["elements"][0]["type"]
    assert "missing required field 'type'" in violations(ir)


def test_a_bad_field_on_a_known_type_reports_that_types_error():
    """A rect with a broken `w` must be told about `w`. The four other branches' complaints about
    `type` are noise and must be dropped."""
    ir = load("minimal")
    ir["elements"][0]["w"] = -1
    msg = violations(ir)
    assert "elements[0]" in msg
    assert "unknown element type" not in msg


def test_there_is_no_z_field():
    """Array order IS z-order. A `z` must be a hard error, not a silently ignored extra key --
    otherwise it becomes a second source of truth and desyncs."""
    ir = load("minimal")
    ir["elements"][0]["z"] = 3
    assert "'z'" in violations(ir)


def test_alpha_is_accepted_in_a_colour_phase_6():
    ir = load("minimal")
    ir["elements"][0]["fill"] = "#FF003280"  # 8-digit RGBA -- Phase 6 lifts Phase 1 restriction
    validate(ir)  # Should pass without raising CanvasValidationError


def test_invalid_hex_length_is_rejected():
    ir = load("minimal")
    ir["elements"][0]["fill"] = "#FF00328"  # 7-digit hex -- invalid
    assert violations(ir)



def test_a_colour_must_carry_its_hash():
    ir = load("minimal")
    ir["elements"][0]["fill"] = "FF0032"
    assert violations(ir)


def test_a_run_must_state_its_colour():
    """An un-coloured run inherits fontRef -> lt1, and lt1 is WHITE. Stating the colour is what
    stops white-on-white text."""
    ir = load("minimal")
    ir["elements"][0]["text"] = {"paragraphs": [{"runs": [{"t": "hi", "size": 14}]}]}
    assert violations(ir)


def test_an_unknown_schema_version_is_refused():
    ir = load("minimal")
    ir["schema"] = "canvas-ir/2"
    assert violations(ir)


def test_a_connector_may_not_carry_text():
    ir = load("connectors")
    ir["elements"][0]["text"] = {
        "paragraphs": [{"runs": [{"t": "x", "size": 14, "color": "#000000"}]}]
    }
    assert violations(ir)


# --- collect-all -----------------------------------------------------------------------------


def test_every_violation_is_reported_in_a_single_raise():
    """Four elements, four DIFFERENT semantic rules, one exception. If someone reintroduces an early
    return, this is the test that catches it."""
    ir = load("minimal")
    ir["elements"] = [
        {"id": "a", "type": "rect", "x": 100, "y": 10, "w": 100, "h": 50, "fill": "#FF0032"},
        {"id": "b", "type": "rect", "x": 900, "y": 200, "w": 200, "h": 50, "fill": "#FF0032"},
        {"id": "c", "type": "rect", "x": 100, "y": 200, "w": 100, "h": 50, "fill": "#4472C4"},
        {"id": "c", "type": "rect", "x": 300, "y": 200, "w": 100, "h": 50, "fill": "#FF0032"},
    ]
    msg = violations(ir)
    assert "HEADER_RESERVED" in msg  # a
    assert "outside the 960x540 slide" in msg  # b
    assert "4472C4" in msg.upper()  # c
    assert "duplicate id" in msg  # c, again
    assert "4 semantic violations" in msg


def test_schema_and_semantic_violations_are_reported_together():
    """A zero-width element (SCHEMA) and a separate #4472C4 element (SEMANTIC) must BOTH be named.

    Raising the schema errors before the semantic pass runs is what got Phase 1A rejected: the two
    elements are independent, both violations are real and detectable, and the author is entitled to
    hear about both in one pass rather than fix one and rediscover the other."""
    ir = load("minimal")
    ir["elements"] = [
        {"id": "zero_width", "type": "rect", "x": 100, "y": 120, "w": 0, "h": 100, "fill": "#FF0032"},
        {"id": "accent1", "type": "rect", "x": 300, "y": 120, "w": 100, "h": 50, "fill": "#4472C4"},
    ]
    msg = violations(ir)
    assert "zero_width" in msg
    assert "schema violation" in msg
    assert "accent1" in msg
    assert "4472C4" in msg.upper()
    assert "semantic violation" in msg


def test_a_structurally_broken_element_does_not_crash_the_semantic_pass():
    """Semantics now runs even when the schema failed, so it can no longer assume its fields exist.
    A missing coordinate must degrade to 'skip the geometry rules FOR THAT ELEMENT' -- not skip the
    element, and never KeyError."""
    ir = load("minimal")
    ir["elements"] = [
        {"id": "no_width", "type": "rect", "x": 100, "y": 120, "h": 100, "fill": "#4472C4"},  # no `w`
        {"id": "no_width", "type": "rect", "x": 300, "y": 120, "w": 100, "h": 50, "fill": "#FF0032"},
    ]
    msg = violations(ir)  # must raise CanvasValidationError, NOT KeyError/TypeError
    assert "4472C4" in msg.upper()  # a canvas-independent rule still ran ON the broken element
    assert "duplicate id" in msg  # and so did the id rule


# Each of these breaks a field the semantic pass reads. Every one used to be unreachable -- the
# schema stage raised first -- and every one is now a live crash site. `float(el["x"])` in
# geometry.py raises KeyError on a missing coordinate and ValueError on a string one; `run["color"]`
# and `text["paragraphs"]` were unguarded subscripts. A raw KeyError escaping validate() is WORSE
# than the bug this refactor fixes: render_canvas.py catches only CanvasValidationError, so anything
# else is an unhandled traceback in the CLI.
STRUCTURALLY_BROKEN = {
    "elements_is_not_a_list": {"elements": "not a list"},
    "element_is_not_a_dict": {"elements": ["not a dict", 7, None]},
    "element_has_no_id": {"elements": [{"type": "rect", "x": 1, "y": 1, "w": 1, "h": 1, "fill": None}]},
    "element_has_no_coords": {"elements": [{"id": "e", "type": "rect", "fill": "#FF0032"}]},
    "coord_is_a_string": {
        "elements": [{"id": "e", "type": "rect", "x": "100", "y": 1, "w": 1, "h": 1, "fill": None}]
    },
    "coord_is_a_bool": {
        "elements": [{"id": "e", "type": "rect", "x": True, "y": 1, "w": 1, "h": 1, "fill": None}]
    },
    "coord_is_none": {
        "elements": [{"id": "e", "type": "rect", "x": None, "y": 1, "w": 1, "h": 1, "fill": None}]
    },
    "rotation_is_a_string": {
        "elements": [
            {"id": "e", "type": "rect", "x": 1, "y": 1, "w": 1, "h": 1, "fill": None, "rotation": "45"}
        ]
    },
    "connector_has_no_endpoints": {
        "elements": [{"id": "e", "type": "connector", "kind": "straight", "color": "#4472C4"}]
    },
    "stroke_has_no_colour": {
        "elements": [
            {"id": "e", "type": "rect", "x": 1, "y": 1, "w": 1, "h": 1, "fill": None, "stroke": {}}
        ]
    },
    "text_has_no_paragraphs": {
        "elements": [{"id": "e", "type": "rect", "x": 1, "y": 1, "w": 1, "h": 1, "fill": None, "text": {}}]
    },
    "paragraphs_is_not_a_list": {
        "elements": [
            {
                "id": "e", "type": "rect", "x": 1, "y": 1, "w": 1, "h": 1, "fill": None,
                "text": {"paragraphs": "nope"},
            }
        ]
    },
    "a_run_is_not_a_dict": {
        "elements": [
            {
                "id": "e", "type": "rect", "x": 1, "y": 1, "w": 1, "h": 1, "fill": None,
                "text": {"paragraphs": [{"runs": ["nope"]}]},
            }
        ]
    },
    "a_run_states_no_colour": {
        "elements": [
            {
                "id": "e", "type": "rect", "x": 1, "y": 1, "w": 1, "h": 1, "fill": None,
                "text": {"paragraphs": [{"runs": [{"t": "hi", "size": 14}]}]},
            }
        ]
    },
    "title_is_missing": {"title": None},
    "title_is_a_dict": {"title": {"paragraphs": [{"runs": [{"t": "hi", "size": 14, "color": "#000000"}]}]}},
}


@pytest.mark.parametrize("name", sorted(STRUCTURALLY_BROKEN))
def test_no_malformed_payload_escapes_as_anything_but_a_validation_error(name):
    ir = load("minimal")
    ir.update(STRUCTURALLY_BROKEN[name])
    if ir.get("title") is None:
        del ir["title"]

    with pytest.raises(CanvasValidationError):  # never KeyError, TypeError or ValueError
        validate(ir)


def test_validate_does_not_mutate_the_payload():
    ir = load("shapes")
    before = copy.deepcopy(ir)
    validate(ir)
    assert ir == before


def test_a_non_dict_payload_is_refused_without_crashing():
    with pytest.raises(CanvasValidationError):
        validate([])  # type: ignore[arg-type]
