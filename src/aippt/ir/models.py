#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Typed mirror of ``ir/schema.json`` -- the IR contract, in Python.

The JSON Schema is the *normative* contract (it is what the LLM's tool-use call is
validated against, and it is language-neutral). This module is the *ergonomic* one: it
gives the renderer real objects instead of nested dicts, and it enforces the handful of
rules JSON Schema structurally cannot express:

  * every table row has exactly ``len(columns)`` cells;
  * ``layout_id`` names a layout that actually exists in ``layout_manifest.json``;
  * content fits the per-layout budget (delegated to :mod:`aippt.render.fit`).

Design note -- why stdlib dataclasses and not pydantic: the only hard dependency of this
project is python-pptx. The schema is already enforced at the model-output boundary by
``jsonschema``; a second, subtly-different validation dialect in the middle of the
pipeline would be a source of drift, not safety.

Round-trip invariant:  ``Deck.from_dict(d).to_dict() == d``  for any schema-valid ``d``
that has been normalised (i.e. after string-form rich text is expanded into runs).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar

IR_VERSION = "1.0"
SCHEMA_PATH = Path(__file__).with_name("schema.json")


class IRValidationError(ValueError):
    """IR that is structurally wrong. Carries a path so the bounded-retry prompt can
    tell the model *exactly* which field to fix (e.g. ``slides[3].blocks[1].rows[2]``)."""

    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.message = message


# --------------------------------------------------------------------------------------
# Rich text
# --------------------------------------------------------------------------------------

@dataclass
class Run:
    """One styled span. ``code`` is the workhorse: 111 of them in the 30-slide corpus."""

    t: str
    b: bool = False
    i: bool = False
    code: bool = False
    link: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"t": self.t}
        if self.b:
            out["b"] = True
        if self.i:
            out["i"] = True
        if self.code:
            out["code"] = True
        if self.link:
            out["link"] = self.link
        return out


@dataclass
class RichText:
    """A run sequence. Accepts the bare-string shorthand and normalises it.

    The shorthand exists for the LLM's benefit: asking a model to emit
    ``[{"t": "hello"}]`` when it means ``"hello"`` is a reliable source of malformed
    output. We accept both and normalise inward, so the renderer only ever sees runs.
    """

    runs: list[Run] = field(default_factory=list)

    @classmethod
    def parse(cls, raw: Any, path: str) -> RichText:
        if isinstance(raw, str):
            return cls([Run(t=raw)])
        if isinstance(raw, list):
            runs = []
            for i, r in enumerate(raw):
                if not isinstance(r, dict) or "t" not in r:
                    raise IRValidationError(f"{path}[{i}]", "each run needs a 't' field")
                runs.append(Run(t=r["t"], b=bool(r.get("b")), i=bool(r.get("i")),
                                code=bool(r.get("code")), link=r.get("link")))
            return cls(runs)
        raise IRValidationError(path, f"rich text must be a string or run array, got {type(raw).__name__}")

    @property
    def plain(self) -> str:
        """Style-stripped text. This -- not the run count -- is what the budget measures."""
        return "".join(r.t for r in self.runs)

    def to_dict(self) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self.runs]


# --------------------------------------------------------------------------------------
# Blocks
# --------------------------------------------------------------------------------------

@dataclass
class Block:
    """Base class. Subclasses set ``type`` and implement ``parse``/``to_dict``.

    ``text_length`` is the contract every block owes :mod:`aippt.render.fit`: the number
    of *rendered characters* it will consume. fit.py sums it across a slide's blocks and
    compares against the layout's content budget, without knowing what any block is.
    """

    type: ClassVar[str] = ""

    def text_length(self) -> int:
        raise NotImplementedError

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class Heading(Block):
    type: ClassVar[str] = "heading"
    text: str = ""

    def text_length(self) -> int:
        return len(self.text)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text}


@dataclass
class Paragraph(Block):
    type: ClassVar[str] = "paragraph"
    text: RichText = field(default_factory=RichText)

    def text_length(self) -> int:
        return len(self.text.plain)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text.to_dict()}


@dataclass
class BulletItem:
    text: RichText
    level: int = 0


@dataclass
class Bullets(Block):
    type: ClassVar[str] = "bullets"
    items: list[BulletItem] = field(default_factory=list)

    def text_length(self) -> int:
        return sum(len(i.text.plain) for i in self.items)

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type,
                "items": [{"text": i.text.to_dict(), "level": i.level} for i in self.items]}


@dataclass
class Callout(Block):
    type: ClassVar[str] = "callout"
    text: RichText = field(default_factory=RichText)
    variant: str = "info"
    title: str | None = None

    def text_length(self) -> int:
        return len(self.text.plain) + len(self.title or "")

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type, "variant": self.variant,
                               "text": self.text.to_dict()}
        if self.title:
            out["title"] = self.title
        return out


@dataclass
class Table(Block):
    type: ClassVar[str] = "table"
    columns: list[str] = field(default_factory=list)
    rows: list[list[RichText]] = field(default_factory=list)
    caption: str | None = None

    def text_length(self) -> int:
        return (sum(len(c) for c in self.columns)
                + sum(len(cell.plain) for row in self.rows for cell in row))

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "type": self.type,
            "columns": list(self.columns),
            "rows": [[c.to_dict() for c in row] for row in self.rows],
        }
        if self.caption:
            out["caption"] = self.caption
        return out


@dataclass
class CodeVariant:
    code: str
    label: str | None = None
    language: str | None = None


@dataclass
class Code(Block):
    type: ClassVar[str] = "code"
    variants: list[CodeVariant] = field(default_factory=list)

    def text_length(self) -> int:
        # Only the widest variant is ever shown at once, so budget against that one.
        return max((len(v.code) for v in self.variants), default=0)

    def to_dict(self) -> dict[str, Any]:
        items = []
        for v in self.variants:
            d: dict[str, Any] = {"code": v.code}
            if v.label:
                d["label"] = v.label
            if v.language:
                d["language"] = v.language
            items.append(d)
        return {"type": self.type, "variants": items}


@dataclass
class ImageSource:
    kind: str          # "data_uri" | "path"
    value: str


@dataclass
class Image(Block):
    type: ClassVar[str] = "image"
    source: ImageSource = field(default_factory=lambda: ImageSource("path", ""))
    alt: str = ""
    caption: str | None = None

    def text_length(self) -> int:
        # An image occupies area, not characters. It is budgeted by fit.py as an area
        # claim on the placeholder, not a character count.
        return len(self.caption or "")

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "type": self.type,
            "source": {"kind": self.source.kind, "value": self.source.value},
            "alt": self.alt,
        }
        if self.caption:
            out["caption"] = self.caption
        return out


@dataclass
class Diagram(Block):
    type: ClassVar[str] = "diagram"
    source: str = ""
    syntax: str = "mermaid"
    kind: str | None = None
    render_hint: str = "auto"

    def text_length(self) -> int:
        return 0

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type, "syntax": self.syntax,
                               "source": self.source, "render_hint": self.render_hint}
        if self.kind:
            out["kind"] = self.kind
        return out


@dataclass
class StepItem:
    title: str
    text: RichText | None = None


@dataclass
class Steps(Block):
    type: ClassVar[str] = "steps"
    items: list[StepItem] = field(default_factory=list)

    def text_length(self) -> int:
        return sum(len(i.title) + (len(i.text.plain) if i.text else 0) for i in self.items)

    def to_dict(self) -> dict[str, Any]:
        items = []
        for i in self.items:
            d: dict[str, Any] = {"title": i.title}
            if i.text:
                d["text"] = i.text.to_dict()
            items.append(d)
        return {"type": self.type, "items": items}


@dataclass
class CardItem:
    title: str
    text: RichText | None = None
    tag: str | None = None


@dataclass
class Cards(Block):
    type: ClassVar[str] = "cards"
    items: list[CardItem] = field(default_factory=list)
    columns: int = 2

    def text_length(self) -> int:
        return sum(len(i.title) + (len(i.text.plain) if i.text else 0) for i in self.items)

    def to_dict(self) -> dict[str, Any]:
        items = []
        for i in self.items:
            d: dict[str, Any] = {"title": i.title}
            if i.text:
                d["text"] = i.text.to_dict()
            if i.tag:
                d["tag"] = i.tag
            items.append(d)
        return {"type": self.type, "columns": self.columns, "items": items}


# --------------------------------------------------------------------------------------
# Block dispatch
# --------------------------------------------------------------------------------------

def _parse_block(raw: Any, path: str) -> Block:
    if not isinstance(raw, dict):
        raise IRValidationError(path, "block must be an object")
    btype = raw.get("type")

    if btype == "heading":
        return Heading(text=raw["text"])

    if btype == "paragraph":
        return Paragraph(text=RichText.parse(raw["text"], f"{path}.text"))

    if btype == "bullets":
        items = [BulletItem(text=RichText.parse(it["text"], f"{path}.items[{i}].text"),
                            level=int(it.get("level", 0)))
                 for i, it in enumerate(raw.get("items", []))]
        if not items:
            raise IRValidationError(path, "bullets block has no items")
        return Bullets(items=items)

    if btype == "callout":
        return Callout(text=RichText.parse(raw["text"], f"{path}.text"),
                       variant=raw.get("variant", "info"),
                       title=raw.get("title"))

    if btype == "table":
        columns = list(raw.get("columns", []))
        if not columns:
            raise IRValidationError(path, "table has no columns")
        rows: list[list[RichText]] = []
        for r, row in enumerate(raw.get("rows", [])):
            # The one rule JSON Schema cannot state: cell count must match column count.
            # A ragged row does not raise in python-pptx -- it silently drops cells or
            # throws deep in the XML layer, so we catch it here where the message is useful.
            if len(row) != len(columns):
                raise IRValidationError(
                    f"{path}.rows[{r}]",
                    f"row has {len(row)} cells but the table declares {len(columns)} columns")
            rows.append([RichText.parse(c, f"{path}.rows[{r}][{c_i}]")
                         for c_i, c in enumerate(row)])
        if not rows:
            raise IRValidationError(path, "table has no rows")
        return Table(columns=columns, rows=rows, caption=raw.get("caption"))

    if btype == "code":
        variants = [CodeVariant(code=v["code"], label=v.get("label"), language=v.get("language"))
                    for v in raw.get("variants", [])]
        if not variants:
            raise IRValidationError(path, "code block has no variants")
        return Code(variants=variants)

    if btype == "image":
        src = raw.get("source") or {}
        if src.get("kind") not in ("data_uri", "path"):
            raise IRValidationError(f"{path}.source.kind", "must be 'data_uri' or 'path'")
        return Image(source=ImageSource(kind=src["kind"], value=src["value"]),
                     alt=raw.get("alt", ""), caption=raw.get("caption"))

    if btype == "diagram":
        return Diagram(source=raw["source"], syntax=raw.get("syntax", "mermaid"),
                       kind=raw.get("kind"), render_hint=raw.get("render_hint", "auto"))

    if btype == "steps":
        items = [StepItem(title=it["title"],
                          text=RichText.parse(it["text"], f"{path}.items[{i}].text")
                          if "text" in it else None)
                 for i, it in enumerate(raw.get("items", []))]
        return Steps(items=items)

    if btype == "cards":
        items = [CardItem(title=it["title"],
                          text=RichText.parse(it["text"], f"{path}.items[{i}].text")
                          if "text" in it else None,
                          tag=it.get("tag"))
                 for i, it in enumerate(raw.get("items", []))]
        return Cards(items=items, columns=int(raw.get("columns", 2)))

    raise IRValidationError(f"{path}.type", f"unknown block type {btype!r}")


# --------------------------------------------------------------------------------------
# Slide / Deck
# --------------------------------------------------------------------------------------

@dataclass
class Slide:
    layout_id: str
    title: str
    blocks: list[Block] = field(default_factory=list)
    id: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"layout_id": self.layout_id, "title": self.title,
                               "blocks": [b.to_dict() for b in self.blocks]}
        if self.id:
            out["id"] = self.id
        if self.notes:
            out["notes"] = self.notes
        return out


@dataclass
class DeckMeta:
    title: str
    subtitle: str | None = None
    language: str = "mixed"
    source: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"title": self.title, "language": self.language}
        if self.subtitle:
            out["subtitle"] = self.subtitle
        if self.source:
            out["source"] = self.source
        return out


@dataclass
class Deck:
    deck: DeckMeta
    slides: list[Slide] = field(default_factory=list)
    ir_version: str = IR_VERSION

    # -- parsing -----------------------------------------------------------------------

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> Deck:
        """Structural parse. Does NOT check ``layout_id`` or budgets -- those need the
        manifest, so they live in :meth:`validate_against_manifest` and in fit.py."""
        version = raw.get("ir_version")
        if version != IR_VERSION:
            raise IRValidationError("ir_version",
                                    f"expected {IR_VERSION!r}, got {version!r}")
        d = raw.get("deck") or {}
        if not d.get("title"):
            raise IRValidationError("deck.title", "required")
        meta = DeckMeta(title=d["title"], subtitle=d.get("subtitle"),
                        language=d.get("language", "mixed"), source=d.get("source"))

        slides = []
        for i, s in enumerate(raw.get("slides", [])):
            path = f"slides[{i}]"
            if not s.get("layout_id"):
                raise IRValidationError(f"{path}.layout_id", "required")
            if not s.get("title"):
                raise IRValidationError(f"{path}.title", "required")
            blocks = [_parse_block(b, f"{path}.blocks[{j}]")
                      for j, b in enumerate(s.get("blocks", []))]
            slides.append(Slide(layout_id=s["layout_id"], title=s["title"], blocks=blocks,
                                id=s.get("id"), notes=s.get("notes")))
        if not slides:
            raise IRValidationError("slides", "a deck needs at least one slide")
        return cls(deck=meta, slides=slides, ir_version=version)

    @classmethod
    def from_json(cls, text: str) -> Deck:
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path: Path) -> Deck:
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    # -- serialising -------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {"ir_version": self.ir_version,
                "deck": self.deck.to_dict(),
                "slides": [s.to_dict() for s in self.slides]}

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save(self, path: Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    # -- validation --------------------------------------------------------------------

    def validate_against_manifest(self, manifest: dict[str, Any]) -> list[str]:
        """Cross-check every ``layout_id`` against the real template.

        Returns a list of human-readable errors (empty == valid). Returning rather than
        raising is deliberate: the AI-adapter's retry prompt wants *all* the problems at
        once, not just the first one.
        """
        known: set[str] = set()
        for master in manifest.get("masters", []):
            for lay in master.get("layouts", []):
                known.add(lay["layout_id"])

        errors: list[str] = []
        for i, slide in enumerate(self.slides):
            if slide.layout_id not in known:
                nearest = sorted(known)[:5]
                errors.append(
                    f"slides[{i}].layout_id: {slide.layout_id!r} is not a layout in this "
                    f"template. Valid ids include: {', '.join(repr(k) for k in nearest)}"
                )
        return errors


def load_schema() -> dict[str, Any]:
    """The normative JSON Schema, for the model's tool-use definition and for jsonschema."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
