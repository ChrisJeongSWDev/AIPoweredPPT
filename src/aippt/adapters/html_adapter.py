#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HTML card deck  ->  Slide IR.

STATUS: specification only. Every function below raises NotImplementedError.
This is Phase 1 of the roadmap and it is deliberately the *first* thing built, because
it exercises the whole IR -> renderer -> PPTX path with zero AI in the loop. If a
30-slide deck we already have cannot survive the round trip, no amount of prompt
engineering will save the AI path.

Corpus (the fixtures this must handle -- all three verified, see foundation_research.md S3):
    Slide Template.html                            4 cards
    Vieworks_MatroxSDK_Example_UserManual.html    17 cards
    3D Logic 개발 테스트벤치 설계안_Ver2.html        9 cards
                                                  -- 30 cards total

The convention, identical across all three
------------------------------------------
    <div class="hero"> <h1>DECK TITLE</h1> <p>subtitle</p> </div>   <- deck meta, NOT a slide
    <section class="card" data-slide="N"> ... </section>            <- exactly one slide
        <h2>          slide title       (exactly 1 per card, all 30 verified)
        <p>           lead paragraph
        <h3>          sub-heading
        <ul><li>      bullets
        <table>       table
        <div class="alert-box"|"warn-box"|"ok-box">   callout, 3 variants
        <div class="mermaid">                          diagram
        <pre><code>   code block
        <div class="tabs">   tabbed code -> ONE `code` block with multiple variants
        <img src="data:image/jpeg;base64,...">         image (jpeg, not png)
        <span class="step-badge">  numbered step
        <div class="mini-card"> in .grid-2/.grid-3     peer cards
        <code>        inline code -- 111 occurrences, MUST become Run(code=True)

`data-slide` is 0-based and, in this corpus, always equals the card's document order.
Do NOT trust it as an ordering key: order by document position and use `data-slide`
only to build the slide `id`. (If they ever disagree, that is a bug in the source deck
and the adapter should warn, not silently reorder.)

Ignore entirely (chrome, not content)
-------------------------------------
    .mode-toggle  .slide-nav  .page-info  .container  <script>  <style>
    .sim-control-panel  .sim-slider  .sim-control-group

The `sim-*` family is an interactive simulator in the 3D Logic deck. It has no static
representation at all. Dropping it silently would quietly lose a slide's entire point,
so :func:`parse_deck` MUST emit a LOSSY warning for it (see `ConversionReport`), and the
slide should fall back to its `<h3>`/`<p>` prose.

Dependencies: BeautifulSoup4 + lxml. Do NOT use a regex; the corpus nests
(`<img>` lives *inside* `.photo-desc` inside `.photo-placeholder` inside `.photo-grid`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..ir.models import Block, Deck


@dataclass
class ConversionReport:
    """What the adapter could not faithfully carry across.

    Exists because the failure mode we care about is *silent* loss. A slide that renders
    beautifully but has quietly dropped its only diagram is worse than a loud failure.
    ``lossy`` is printed by the CLI and asserted-empty by the round-trip test.
    """

    slides_in: int = 0
    slides_out: int = 0
    lossy: list[str] = field(default_factory=list)      # "slide 6: .sim-control-panel dropped"
    unmapped_classes: set[str] = field(default_factory=set)

    def warn(self, slide_idx: int, message: str) -> None:
        self.lossy.append(f"slide {slide_idx}: {message}")


def parse_deck(html_path: Path, *, strict: bool = False) -> tuple[Deck, ConversionReport]:
    """Parse one HTML card deck into a validated :class:`Deck`.

    Args:
        html_path: the .html file. Read with ``encoding='utf-8'`` -- the corpus is
            Korean and cp949 will mangle it.
        strict: if True, raise on the first unmapped construct instead of degrading.
            The round-trip test runs with ``strict=False`` and asserts the report is
            clean, which gives a better error message than an exception would.

    Returns:
        ``(deck, report)``. ``deck`` is schema-valid IR. ``report`` lists everything
        that was dropped or degraded.

    Raises:
        FileNotFoundError, IRValidationError; and any construct error when ``strict``.

    Invariants:
        * ``len(deck.slides) == report.slides_in == number of section.card elements``
          -- the adapter never invents or merges slides. One card in, one slide out.
        * Every ``slide.title`` comes from that card's single ``<h2>``; a card with zero
          or two ``<h2>`` elements is a hard error (never seen in the corpus, so if it
          fires, the source deck broke its own convention).
        * ``deck.deck.title`` comes from ``.hero h1``, NOT from any card.
        * No block is ever emitted with empty text.
    """
    raise NotImplementedError


def choose_layout(blocks: list[Block], manifest: dict[str, Any]) -> str:
    """Pick the template layout that best fits a slide's content. The crux of the adapter.

    The HTML has no notion of a PowerPoint layout, so this is where the mapping is
    *invented* -- and it is the single place where a bad decision produces an ugly deck.
    Rule-based, in priority order (first match wins):

        image blocks present            -> a 'picture' role layout
        table is the dominant block     -> 'table' role, else 'bullets' (a table is
                                           just a wide body placeholder)
        diagram present                 -> 'picture' role (we place a rendered/native
                                           diagram into the picture box)
        cards / steps present           -> 'two-content' or 'multi-content' by item count
        bullets + heading only          -> 'bullets'
        lead paragraph only, no bullets -> 'title-only'  (a statement slide)
        nothing but the title           -> 'section-divider'

    Args:
        blocks: the slide's parsed blocks, in order.
        manifest: the parsed ``reference/layout_manifest.json``. ``semantic_role`` on each
            layout is what this function matches against -- never a hard-coded layout name,
            because the template can be re-authored and the names will change.

    Returns:
        A ``layout_id`` guaranteed to exist in ``manifest``.

    Raises:
        LookupError: if the manifest has no layout for a required role. This is a real
            possibility (a minimal template may have no 'picture' layout) and the caller
            should fall back to 'bullets' + a free-floating picture rather than crash.
    """
    raise NotImplementedError


def parse_rich_text(el: Any) -> Any:
    """One inline HTML element -> :class:`~aippt.ir.models.RichText`.

    Walks the element's children and maps: ``<strong>/<b>`` -> ``b``, ``<em>/<i>`` -> ``i``,
    ``<code>`` -> ``code``, ``<a href>`` -> ``link``. Everything else contributes its text
    with no styling. Whitespace is collapsed (the source is pretty-printed HTML, so raw
    ``.text`` is full of newlines and indentation).

    Getting ``<code>`` right is the whole point: it is the most common inline mark in the
    corpus by an order of magnitude, and a deck of API documentation that renders
    ``VEO_Focus_Initialize()`` in body prose instead of monospace looks broken.
    """
    raise NotImplementedError


def extract_image(img_el: Any, report: ConversionReport, slide_idx: int) -> Any:
    """``<img src="data:image/jpeg;base64,...">`` -> an ``image`` block.

    The data URI is kept *verbatim* in the IR (``source.kind == "data_uri"``). The IR
    stays a single self-contained JSON file -- no sidecar asset directory to keep in sync,
    which matters because the IR gets passed to an LLM and round-tripped through a QA loop.
    Decoding happens once, late, in ``render/renderer.py``.

    A 619 KB HTML file is ~600 KB of base64. The resulting IR is big but still text.
    If that ever becomes a problem, switch ``kind`` to ``"path"`` and spill to disk --
    the schema already supports it and nothing else needs to change.

    Malformed / truncated base64 must be reported as lossy, never allowed to raise here:
    a broken image should cost one picture, not the whole deck.
    """
    raise NotImplementedError
