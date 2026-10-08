#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""canvas/geometry.py -- the EMU transform and the reserved-region predicates.

These are the cheapest tests in the suite and they guard the most expensive mistake. Everything
downstream trusts geometry.py: validate.py asks it what an element occupies, style.py asks it where
to put the shape, and the round-trip suite asserts 0 EMU drift against the same emu() it is testing.
So the numbers here are written out longhand rather than derived from the module's own constants --
a test that computes its expectation with the code under test proves only that the code is
self-consistent.
"""

from __future__ import annotations

import math

import pytest

from aippt.canvas.geometry import (
    CANVAS_H,
    CANVAS_W,
    EMU_PER_UNIT,
    FOOTER_RESERVED,
    HEADER_RESERVED,
    element_bbox,
    emu,
    intersects,
    out_of_bounds,
    reserved_violations,
)


def rect(x, y, w, h, rotation=0):
    return {"id": "r", "type": "rect", "x": x, "y": y, "w": w, "h": h, "rotation": rotation}


def conn(x1, y1, x2, y2):
    return {"id": "c", "type": "connector", "x1": x1, "y1": y1, "x2": x2, "y2": y2}


# --- the transform ---------------------------------------------------------------------------


def test_the_unit_is_exact():
    """1 logical unit == 1 pt == 12,700 EMU, three ways. If any of these stops holding, the whole
    0-EMU tolerance downstream is a fiction."""
    assert EMU_PER_UNIT == 12700
    assert 12192000 / CANVAS_W == 12700  # slide width  / 960
    assert 6858000 / CANVAS_H == 12700  # slide height / 540
    assert 914400 / 72 == 12700  # 1 inch / 72 pt


@pytest.mark.parametrize(
    ("units", "expected_emu"),
    [
        (0, 0),
        (1, 12700),
        (72, 914400),  # one inch
        (960, 12192000),  # the full slide width
        (540, 6858000),  # the full slide height
        (45.6, 579120),  # BODY_SAFE left
        (733.6, 9316720),  # FOOTER_RESERVED left
        (92, 1168400),  # HEADER_RESERVED bottom
        (7.2, 91440),  # the text-frame side margin
        (3.6, 45720),  # the text-frame top/bottom margin
    ],
)
def test_emu_is_exact(units, expected_emu):
    assert int(emu(units)) == expected_emu


def test_emu_rounds_to_the_nearest_integer():
    """emu() must return an int -- Emu(float) would raise, and a fractional EMU is not a thing."""
    assert int(emu(0.5)) == 6350
    assert int(emu(1 / 3)) == round(12700 / 3) == 4233
    assert isinstance(int(emu(1.7)), int)


# --- intersects: the half-open rule ----------------------------------------------------------
# This is the single most load-bearing predicate in the module. HEADER_RESERVED ends at y == 92 and
# BODY_SAFE begins at y == 92, so if edge contact counted as intersection then EVERY top-aligned
# element in every deck would be spuriously rejected.


def test_edge_contact_is_not_intersection_at_the_header_boundary():
    assert intersects((0, 92, 100, 200), HEADER_RESERVED) is False


def test_one_unit_of_overlap_at_the_header_boundary_is_intersection():
    assert intersects((0, 91.9, 100, 200), HEADER_RESERVED) is True


def test_edge_contact_is_not_intersection_at_the_footer_boundary():
    # Bottom edge exactly on y == 500, sitting right over the page-number chrome's x-range.
    assert intersects((800, 400, 900, 500), FOOTER_RESERVED) is False


def test_one_unit_of_overlap_at_the_footer_boundary_is_intersection():
    assert intersects((800, 400, 900, 500.1), FOOTER_RESERVED) is True


def test_edge_contact_on_the_footers_left_edge_is_not_intersection():
    # x2 == 733.6 == FOOTER_RESERVED's left edge.
    assert intersects((700, 510, 733.6, 520), FOOTER_RESERVED) is False


def test_intersects_is_symmetric():
    a, b = (0, 0, 10, 10), (5, 5, 15, 15)
    assert intersects(a, b) is True
    assert intersects(b, a) is True


# --- element_bbox ----------------------------------------------------------------------------


def test_unrotated_bbox_is_the_path_box():
    assert element_bbox(rect(45.6, 92, 200, 100)) == (45.6, 92, 245.6, 192)


def test_rotation_360_is_treated_as_unrotated():
    assert element_bbox(rect(10, 20, 30, 40, rotation=360)) == (10, 20, 40, 60)


def test_absent_rotation_is_zero():
    el = {"id": "r", "type": "rect", "x": 10, "y": 20, "w": 30, "h": 40}
    assert element_bbox(el) == (10, 20, 40, 60)


def test_rotating_a_square_45_degrees_gives_its_diagonal():
    # 100x100 at (430,250) -> centre (480,300). Half-diagonal = 100*sqrt(2)/2.
    half = 100 * math.sqrt(2) / 2
    x1, y1, x2, y2 = element_bbox(rect(430, 250, 100, 100, rotation=45))
    assert x1 == pytest.approx(480 - half)
    assert y1 == pytest.approx(300 - half)
    assert x2 == pytest.approx(480 + half)
    assert y2 == pytest.approx(300 + half)


def test_rotating_90_degrees_swaps_the_extents_about_the_centre():
    # 200x100 at the origin -> centre (100,50). At 90 degrees the footprint is 100 wide, 200 tall.
    x1, y1, x2, y2 = element_bbox(rect(0, 0, 200, 100, rotation=90))
    assert (x1, y1, x2, y2) == pytest.approx((50, -50, 150, 150))


def test_the_rotated_bbox_is_symmetric_in_the_sign_of_the_angle():
    """The AABB of a box rotated about its own centre cannot depend on the direction of rotation,
    so this cannot catch a clockwise/anticlockwise slip -- it is here to pin the fact that it
    cannot, which is why geometry.py is free to state the sign for the reader rather than prove it."""
    assert element_bbox(rect(100, 200, 120, 80, rotation=30)) == pytest.approx(
        element_bbox(rect(100, 200, 120, 80, rotation=330))
    )


def test_connector_bbox_normalises_reversed_endpoints():
    assert element_bbox(conn(300, 400, 100, 200)) == (100, 200, 300, 400)


def test_a_horizontal_connector_has_a_zero_height_bbox():
    assert element_bbox(conn(60, 300, 300, 300)) == (60, 300, 300, 300)


# --- reserved_violations ---------------------------------------------------------------------


def test_an_element_flush_with_the_header_at_y_92_is_legal():
    """THE regression guard. BODY_SAFE starts at exactly 92; if this ever fails, every top-aligned
    element in every deck is being rejected."""
    assert reserved_violations(rect(45.6, 92, 300, 60)) == []


def test_an_element_whose_bottom_is_exactly_500_over_the_footer_is_legal():
    assert reserved_violations(rect(800, 440, 100, 60)) == []


def test_an_element_in_the_header_is_rejected():
    assert reserved_violations(rect(100, 50, 200, 100)) == ["HEADER_RESERVED"]


def test_an_element_in_the_footer_is_rejected():
    assert reserved_violations(rect(800, 480, 120, 50)) == ["FOOTER_RESERVED"]


def test_an_element_can_violate_both_regions_at_once():
    assert sorted(reserved_violations(rect(800, 50, 100, 470))) == [
        "FOOTER_RESERVED",
        "HEADER_RESERVED",
    ]


def test_body_safe_is_not_a_rejection_region():
    """A full-bleed band spans x 0..960, which is outside BODY_SAFE (45.6..914.4) -- and legal.
    BODY_SAFE is the editor's snap target, not a constraint. Only the header and the footer reject."""
    assert reserved_violations(rect(0, 200, 960, 40)) == []


def test_rotation_can_push_a_legal_path_box_into_the_header():
    """The decision the plan left open: a rotated shape is checked by its TRUE footprint.

    The path box is y 95..115, which clears HEADER_RESERVED (0..92) with room to spare. Spun 45
    degrees about its centre the same box reaches y ~= 27 and lands squarely on the Vieworks logo.
    Unrotated it must pass; rotated it must not.
    """
    assert reserved_violations(rect(200, 95, 200, 20, rotation=0)) == []
    assert reserved_violations(rect(200, 95, 200, 20, rotation=45)) == ["HEADER_RESERVED"]


def test_a_connector_lying_in_the_footer_is_rejected():
    assert reserved_violations(conn(760, 520, 940, 520)) == ["FOOTER_RESERVED"]


def test_a_connector_lying_exactly_on_y_500_is_legal():
    assert reserved_violations(conn(740, 500, 950, 500)) == []


# --- out_of_bounds ---------------------------------------------------------------------------


def test_an_element_filling_the_slide_exactly_is_in_bounds():
    assert out_of_bounds(rect(0, 0, 960, 540)) is False


@pytest.mark.parametrize(
    "el",
    [
        rect(900, 200, 200, 100),  # off the right edge
        rect(-20, 200, 100, 100),  # off the left edge
        rect(100, -10, 100, 100),  # off the top
        rect(100, 500, 100, 100),  # off the bottom
    ],
    ids=["right", "left", "top", "bottom"],
)
def test_out_of_bounds_catches_every_edge(el):
    assert out_of_bounds(el) is True


def test_rotation_can_push_a_legal_path_box_off_the_slide():
    # A wide, short box lying near the top edge. Unrotated it is 250 x 20 at y 10..30 and fits.
    # Stood on end about its centre (480, 20) it becomes 20 x 250, reaching y == -105.
    assert out_of_bounds(rect(355, 10, 250, 20, rotation=0)) is False
    assert out_of_bounds(rect(355, 10, 250, 20, rotation=90)) is True


def test_a_connector_off_the_slide_is_out_of_bounds():
    assert out_of_bounds(conn(60, 300, 1000, 300)) is True
