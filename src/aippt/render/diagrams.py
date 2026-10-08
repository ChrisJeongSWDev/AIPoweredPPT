#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mermaid-ish diagram  ->  something a PowerPoint slide can show.

STATUS: specification only. Every function below raises NotImplementedError.

The corpus: 3 ``.mermaid`` blocks (1 ``sequenceDiagram``, 2 flowcharts) plus 1 hand-drawn
inline ``<svg>``. Small, but diagrams carry the highest information density per slide in
the whole deck -- these are architecture decks, and the architecture *is* the diagram.

Why not SmartArt
----------------
python-pptx cannot create SmartArt. There is no API, and the underlying ``diagramData``
part is a dense, undocumented, version-sensitive format that PowerPoint regenerates on
open. Hand-writing it is not a shortcut, it is a maintenance liability with a hard ceiling.
Ruled out, permanently.

The hybrid (recommended -- see foundation_research.md S7)
--------------------------------------------------------
Neither pure strategy is right, because the two failure modes are different:

    NATIVE autoshapes      editable, on-brand, vector-crisp, no external dependency
                           -- but only tractable for *simple* graphs. A general graph
                           layout engine is a project, not a function.

    RASTERISED (mermaid-cli -> PNG -> add_picture)
                           handles arbitrary mermaid, looks exactly like the HTML deck
                           -- but produces a flat image: not editable, not on-brand, and
                           it goes fuzzy the moment anyone resizes it.

So: **decide per diagram, by complexity.** ``choose_strategy`` draws the line. Simple
linear flowcharts -- which is what most of the corpus actually contains -- render native
and stay editable. Anything genuinely complex rasterises, which is honest: an unreadable
native approximation of a 20-node graph is worse than a clean picture of it.

An escape hatch matters here. The IR's ``render_hint`` lets an author force either path,
because the person who wrote the diagram knows things the node count does not.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

Strategy = Literal["native", "image"]

#: Above this many nodes, a native layout stops being legible and starts being a liability.
#: Tuned from the corpus, not from theory: its flowcharts are 4-7 nodes and lay out cleanly;
#: its sequence diagram is 3 participants x 5 messages. Revisit with real decks.
NATIVE_NODE_LIMIT = 8
NATIVE_EDGE_LIMIT = 10


@dataclass
class Node:
    id: str
    label: str
    shape: str = "rect"          # rect | round | diamond (mermaid [] / () / {})


@dataclass
class Edge:
    src: str
    dst: str
    label: str | None = None
    style: str = "solid"         # solid (-->) | dashed (-.->)


@dataclass
class Graph:
    nodes: list[Node]
    edges: list[Edge]
    direction: str = "TD"        # TD | LR -- mermaid's `graph LR` / `flowchart TD`
    kind: str = "flowchart"      # flowchart | sequence | other


def parse_mermaid(source: str) -> Graph:
    """Parse the mermaid subset the corpus actually uses. Not a general mermaid parser.

    Supported, because it is what the 30 slides contain::

        flowchart TD / graph LR
            A[Rectangle label]  B(Rounded)  C{Diamond}
            A --> B             A -.-> C          A -->|edge label| B

        sequenceDiagram
            participant App as China Client App
            App->>SDK: VEO_Focus_Initialize()
            HW-->>App: Direct Event Callback

    Anything outside that subset must raise :class:`UnsupportedDiagram`, NOT be
    half-parsed. A partially-understood diagram renders as a *wrong* diagram, which is
    strictly worse than an honest fallback to the image path -- a wrong architecture
    diagram in an engineering deck is a real cost.

    Raises:
        UnsupportedDiagram: with the offending line, so the caller can fall back cleanly.
    """
    raise NotImplementedError


class UnsupportedDiagram(ValueError):
    """This mermaid source is outside the native parser's subset. Rasterise it instead."""


def choose_strategy(graph: Graph | None, source: str, hint: str = "auto") -> Strategy:
    """Native shapes, or a rendered picture?

    ``hint`` of ``"native"`` / ``"image"`` is honoured verbatim -- the author overrides us.

    On ``"auto"``:
        * parse failed (``graph is None``)              -> image
        * ``kind == "sequence"``                        -> native (a sequence diagram is
          just lifelines and arrows on a grid -- genuinely easy, and it is 1 of our 3)
        * nodes > NATIVE_NODE_LIMIT or edges > NATIVE_EDGE_LIMIT -> image
        * cyclic graph                                  -> image (layered layout below
          assumes a DAG and will loop forever on a cycle)
        * otherwise                                     -> native
    """
    raise NotImplementedError


def render_native(slide: Any, graph: Graph, box_emu: tuple[int, int, int, int]) -> list[Any]:
    """Draw the graph as real PowerPoint autoshapes. Editable, on-brand, vector.

    Layout: layered (Sugiyama-lite), which is all a DAG this small needs.
        1. longest-path layering -> assign each node a rank (depth from a root);
        2. order nodes within a rank to reduce crossings (one median pass is enough at
           this size; do not build a proper crossing minimiser);
        3. position: rank -> the ``direction`` axis, index-within-rank -> the other axis;
        4. scale the whole thing to fit ``box_emu``, preserving aspect;
        5. nodes via ``shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, ...)``,
           edges via ``shapes.add_connector(MSO_CONNECTOR.ELBOW, ...)``.

    Style from the THEME, never hard-coded: node fill = the theme slot the manifest
    identified as carrying the brand accent, text = the master's minor font. A native
    diagram whose red is a hand-typed ``#DB0032`` will drift the day the brand changes.

    Connectors: ``add_connector`` returns a free-floating line. Bind it to the shapes with
    ``connector.begin_connect(shape, cxn_idx)`` / ``end_connect`` so it stays attached when
    a human drags a box -- that reattachment is most of the value of going native at all.

    Returns the created shapes.
    """
    raise NotImplementedError


def render_image(source: str, out_dir: Path, *, scale: int = 3) -> Path:
    """Rasterise mermaid via mermaid-cli. The fallback path.

        mmdc -i diagram.mmd -o diagram.png -b transparent -s 3

    ``-s 3`` (3x) because a 1x PNG on a 13.3in slide is visibly soft on a projector.
    Transparent background so the master's slide fill shows through -- a white box on a
    non-white master is an instant tell.

    Requires Node + ``@mermaid-js/mermaid-cli``. That is an external, non-Python dependency
    and it WILL be missing on some machine: check for it once at startup and degrade
    loudly (a text-only slide plus a clear warning), never crash mid-deck.

    Returns the PNG path.

    Raises:
        FileNotFoundError: mmdc is not on PATH. Message must say how to install it.
    """
    raise NotImplementedError


def render_diagram(slide: Any, diagram_block: Any, box_emu: tuple[int, int, int, int],
                   work_dir: Path) -> str:
    """Entry point: IR ``diagram`` block -> shapes on the slide. Returns the strategy used.

    Orchestrates: parse (tolerating failure) -> :func:`choose_strategy` -> render.
    If the native path raises for any reason, fall back to the image path rather than
    propagating -- a diagram is never worth failing the whole deck over.
    """
    raise NotImplementedError
