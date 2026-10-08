# Phase 1A: Canvas Backend — Task Brief

## Goal

Build the **Canvas IR → PPTX renderer**, driven by hand-written JSON. No editor, no server. When
this is done, `python -m aippt.canvas.render_canvas deck.json -o out.pptx` produces a one-slide
deck on the Vieworks layout 3 chrome, and a round-trip suite proves it.

This implements plan `HTML_to_PPTX_Plan.md` §9 → **Phase 1A**, tasks 1.1 – 1.7. Read §5, §6, §9
and §11 of the plan before writing a line. **This brief is authoritative where it corrects the
plan** — see *Corrections to the plan* below; three of the plan's code snippets are wrong and one
of them ships a corrupt file.

---

## Context: what Phase 0 already gives you (do not rebuild it)

| Artifact | State |
|---|---|
| `reference/renderer_template.pptx` | Built. 0 slides, 5 layouts. SHA `60fe35466ed2bb477d592603d0eab9d8748521e54ae0632c9f6a94d0b02a855a`, 1,212,639 B |
| `reference/template_pin.json` | **Really pinned** (not the placeholder). `layout_index: 3` → `/ppt/slideLayouts/slideLayout4.xml` |
| `src/aippt/canvas/pin.py` | Working. Exports `TemplatePinError`, `load_pin()`, `verify_pin()`, `open_renderer_template()`, `TITLE_PH_IDX`, `PROJECT_ROOT` |
| `src/aippt/tools/make_renderer_template.py` | Build tool. **Never import it from the request path.** |
| `src/aippt/tools/calibrate.py` | Working. Round-trip ran **clean: 0 EMU drift** across 11 shapes (`reference/calibration.json` → `"roundtrip_problems": []`) |

**Phase 0's automated gates passed.** The human/raster gates in `HUMAN_VERIFICATION.md` (PowerPoint
opens clean, page number reads "1", SVG logo survives conversion, raster diff ≤ 2 px) are **still
un-run**. That file's "⚠ Nothing here has been run yet" banner is now stale for the automated half
and accurate for the manual half. **Do not edit `HUMAN_VERIFICATION.md`; it is out of scope.**

### `calibrate.py` is your working reference implementation

It already contains, **inlined and proven at runtime**, the exact code you are being asked to
extract into modules: `emu()`, `set_run_fonts()` (with the `<a:ea>` lxml insertion),
`style_text_frame()`, and the `add_shape` overrides. Its own docstring says these move out when
Phase 1 lands.

> **Read `src/aippt/tools/calibrate.py` first. It is the single best specification of what
> `geometry.py` and `style.py` must do, and unlike the plan's snippets it has actually executed.**

**`calibrate.py` is NOT in your write scope — do not refactor it to import your new modules.** The
duplication is deliberate and stays for now: Phase 0's gates must keep passing standalone. De-duping
it is a follow-up, listed under *Deferred* below.

---

## Authoritative constants

```
1 logical unit ≡ 1 pt ≡ exactly 12,700 EMU     (12192000/960 == 6858000/540 == 914400/72)
canvas         = 960 × 540 logical units, 16:9
emu(u)         = round(u * 12700)              # integer, exact — tolerance is 0, not "close"
font size      = 1:1. A size-14 run is Pt(14). NO scale factor anywhere.

LATIN     = "Century Gothic"
EA        = "맑은 고딕"          # Century Gothic ships NO Hangul glyphs. Not optional.
BRAND_RED = "#FF0032"           # default for new content
FORBIDDEN = "#4472C4"           # theme accent1 — Office blue. MUST NOT reach the output.
layout_index = 3
```

### Reserved regions (plan §3.2), logical units

| Region | Box (x, y, w, h) | Extent | Rule |
|---|---|---|---|
| `HEADER_RESERVED` | 0, 0, 960, 92 | y 0 → 92 | **Reject** any element that intersects |
| `FOOTER_RESERVED` | 733.6, 500, 226.4, 40 | x 733.6 → 960, y 500 → 540 | **Reject** any element that intersects |
| `BODY_SAFE` | 45.6, 92, 868.8, 408 | x 45.6 → 914.4, y 92 → 500 | The drawable region |
| `TITLE_LOCKED` | 45.55, 26.75, 725.29, 37.25 | — | Not an element. Its text is the `title` field → placeholder idx 10 |

**Intersection is strict overlap, not edge contact.** Use the half-open rule:

```python
def intersects(a, b) -> bool:           # a, b = (x1, y1, x2, y2)
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]
```

An element whose top edge is exactly `y = 92` does **not** intersect `HEADER_RESERVED` (which ends
at 92). `BODY_SAFE` starts at exactly 92, so it **must** be legal — get this wrong and every
top-aligned element is spuriously rejected. Write a test for `y == 92` and `y == 500` specifically.

---

## Module specifications

Build under `src/aippt/canvas/`. Keep it **strictly separate** from the existing semantic IR in
`src/aippt/ir/` (plan §8 — there are two IRs; they must not merge, they must not import each other).

### 1.1 — `canvas/schema.json` (`canvas-ir/1`)

The normative IR. Transcribe plan §11 into a real JSON Schema, **draft 2020-12**, matching the
house style of `src/aippt/ir/schema.json` (`$schema` + `$id` + `additionalProperties: false`
everywhere + a `description` on every property that carries a non-obvious rule).

`$id`: `https://vieworks.com/aippt/canvas-ir/1/schema.json`

Required top level: `schema` (const `"canvas-ir/1"`), `canvas`, `target`, `title`, `elements`.

- `canvas` — `{w: 960, h: 540, unit: "pt"}`, all `const`. The backend hard-fails on mismatch, so
  encode it as consts and let the schema do the work.
- `target` — `template_sha256` (required, `^[0-9a-f]{64}$`), `layout_index` (const `3`),
  `template` (optional, informational only — **the server never reads a path from the payload**).
- `title` — string. Goes to placeholder idx 10. **Not** an element.
- `elements` — array. **Array order IS z-order. There is no `z` field** and you must not add one.
  Discriminate on `type` via `oneOf` + `"type": {"const": ...}` per branch, so a bad element gets a
  precise error rather than "failed to match any of 4 subschemas".

Element types: `rect` | `ellipse` | `triangle` | `textbox` | `connector`.

Shape/textbox branch (`rect`/`ellipse`/`triangle`/`textbox`):
`id`, `type`, `x`, `y`, `w`, `h` (w, h `exclusiveMinimum: 0`), `rotation` (default 0),
`fill`, `stroke` (`{color, width}`, nullable/absent = no line), `text` (nullable).

Connector branch: `id`, `type`, `kind` (`straight` | `elbow`), `x1`, `y1`, `x2`, `y2`, `color`,
`width`, `arrow` (`none` | `start` | `end` | `both`).

Colour: `"pattern": "^#[0-9A-Fa-f]{6}$"`. Opaque `#RRGGBB` only — **no alpha in Phase 1** (D-4).

Text object: `{align: LEFT|CENTER|RIGHT, valign: TOP|MIDDLE|BOTTOM, paragraphs: [{runs: [...]}]}`;
run = `{t, size, bold, italic, color}`.

> **Schema gap you must close — line breaks.** Plan §5.6 says `<br>` → `<a:br/>` "line break within
> a paragraph", but the §11 appendix gives no way to express one. **Decision: permit `\n` inside a
> run's `t`.** `style.py` splits the run on `\n` and emits `<a:br/>` between the pieces, carrying the
> run's formatting across the break. This needs no schema change beyond allowing `\n`, and keeps the
> run model flat. Document it in the schema's `t` description.

### 1.2 — `canvas/geometry.py`

Pure functions, **no python-pptx imports beyond `Emu`**, no I/O. This is the module everything else
trusts, so it must be trivially testable.

- `EMU_PER_UNIT = 12700`, `CANVAS_W = 960`, `CANVAS_H = 540`
- `emu(u: float) -> Emu` — `Emu(round(u * EMU_PER_UNIT))`
- The four reserved-region boxes as module constants
- `intersects(a, b) -> bool` — the half-open rule above
- `element_bbox(el) -> tuple` — the axis-aligned box an element actually occupies:
  - shapes/textboxes: the **rotated AABB** of the path box (see below)
  - connectors: `(min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2))`
- `reserved_violations(el) -> list[str]` — which reserved regions this element hits
- `out_of_bounds(el) -> bool` — anything outside 0,0 → 960,540

**Rotation and the reserved-region check.** The plan does not say whether a rotated shape is checked
by its unrotated path box or its true footprint. **Decision: check the rotated AABB** — rotate the
four corners about the box centre by `rotation` degrees clockwise, take min/max. When `rotation == 0`
this is exactly the path box, so the common case is unchanged and free. Rationale: a 45°-rotated box
that visually collides with the Vieworks logo is a real defect, and the user-visible outcome is what
the region exists to protect.

**Known, accepted caveat: stroke bleed is NOT included in the bbox.** `x/y/w/h` is the *path box*;
the stroke is centred on it and bleeds `stroke/2` outward (plan §5.4 — SVG and DrawingML agree here,
which is exactly why we use SVG in the editor). So an element flush against `HEADER_RESERVED` with an
8-unit stroke bleeds 4 units into it and will pass validation. Document this in the module docstring.
Do not "fix" it by inflating the box — that would break the 0-EMU round-trip identity, which is the
more valuable invariant.

### 1.3 — `canvas/validate.py`

`jsonschema` first, then the semantic rules the schema cannot express.

```python
class CanvasValidationError(ValueError): ...

def validate(ir: dict) -> None:   # raises CanvasValidationError, listing EVERY violation
```

**Collect all violations and raise once**, with element `id` and a human-readable reason per line.
A validator that dies on the first error makes a 20-element deck a 20-round debugging session.

Semantic rules (schema cannot do these):
1. **Reserved regions** — `geometry.reserved_violations(el)` non-empty → reject. Import the
   predicates from `geometry.py`; **do not reimplement the box maths here.**
2. **Slide bounds** — reject anything outside 960 × 540.
3. **`#4472C4` is rejected as an explicit `fill`, `stroke.color`, `color` or run colour.**
   Plan §7.3 asserts `4472C4` is *absent* from every renderer-created `<p:sp>`. If a user could
   legitimately pick it, that assertion could never be machine-checked. Banning it in validation is
   what keeps the invariant checkable instead of aspirational. Say so in the error message.
4. **Control characters** — reject C0 except `\t` and `\n` in any run text. (Plan §5.6: this is an
   interoperability policy, not a corruption fix — `python-pptx` 1.0.x escapes them. Reject anyway;
   they have no legitimate source in a visual editor.) **U+00A0 (nbsp) is preserved, never collapsed
   to a space.**
5. **Duplicate `id`s** — reject. The round-trip suite finds shapes by name.
6. `canvas` != `{w:960, h:540, unit:"pt"}` → **hard fail, "stale payload"**. Never rescale.

**`target.template_sha256` vs the pin is checked in `render_canvas.py`, not here** — `validate.py`
must stay pure (no filesystem, no pin), so it can be unit-tested without a template on disk.

### 1.4 — `canvas/style.py`

Extract from `calibrate.py`, then extend to the full IR (multi-paragraph, multi-run, bold/italic,
per-run colour, align/valign).

- `set_run_fonts(run, latin=LATIN, ea=EA)` — **copy `calibrate.py`'s version verbatim.** It is
  correct and it has run. `python-pptx` cannot express an East-Asian typeface at all: `Font.name`
  writes only `<a:latin>`, and `CT_TextCharacterProperties` declares no `ea` child. You must drop to
  lxml. **The successor list in `insert_element_before` must stay complete** —
  `("a:cs", "a:sym", "a:hlinkClick", "a:hlinkMouseOver", "a:rtl", "a:extLst")` — because
  `insert_element_before` **appends** when it finds none of its successors. A merely-plausible list
  puts `<a:ea>` in the wrong place and PowerPoint calls the file corrupt.
- `style_text_frame(tf, text)` — the margin trap. `margin_left/right = Pt(7.2)`,
  `margin_top/bottom = Pt(3.6)`, `word_wrap = True`, `auto_size = MSO_AUTO_SIZE.NONE`,
  `vertical_anchor` from `text.valign`. These mirror the CSS in §5.6 **exactly** and must only ever
  be changed together with it. Per paragraph: `alignment`, `space_before = Pt(0)`,
  `space_after = Pt(0)`, `line_spacing = 1.2`. Per run: `size`, `bold`, `italic`, `color`,
  `set_run_fonts`.
- `draw_shape(slide, el)` — the **five** overrides (see *Corrections* — the plan says four).
- Map `align`/`valign` strings with an **explicit dict**, not `PP_ALIGN[str]`. Enum-member-name
  indexing happens to work in python-pptx 1.0.x, but it couples the IR's public vocabulary to an
  upstream enum's member names and yields an ugly `KeyError` instead of a validation error.

**On autofit: `auto_size = NONE`, always.** `TextFrame.fit_text()` exists but needs a TTF path, is
not a PowerPoint rendering engine, and is a poor foundation for mixed-font CJK. Do not build on it.
The human sizes the box; rendered QA is the authority (plan §6.6, §7).

### 1.5 — `canvas/connectors.py`

`draw_connector(slide, el)`. Absolute endpoints, **no gluing** — `begin_connect()`/`end_connect()`
are experimental and their connection-site indices are unreliable for arbitrary shapes (notably
triangles). Phase 1 ships absolute endpoints, which always work (D-3).

`cxn.shadow.inherit = False` — **connectors get the Office drop shadow too.**

Arrowheads are not exposed in the python-pptx API (there is no `line.end_arrow`); drop to lxml. **See
*Corrections* #1 — the plan's snippet emits schema-invalid XML for `arrow: "both"`.**

### 1.6 — `canvas/render_canvas.py` + CLI

```python
def render(ir: dict) -> Presentation:
    validate(ir)                                    # every violation, up front
    pin = load_pin()
    prs = open_renderer_template(pin)               # verify_pin runs inside; fails closed

    if ir["target"]["template_sha256"] != pin["renderer_template"]["sha256"]:
        raise StalePayloadError(...)                # never rescale a stale payload

    layout = prs.slide_layouts[pin["layout_signature"]["layout_index"]]
    slide = prs.slides.add_slide(layout)            # logo + divider + page number, inherited, free

    set_title(slide, ir["title"])                   # placeholder idx 10, BY IDX
    for el in ir["elements"]:                       # array order IS z-order
        draw(slide, el)
    return prs
```

- **`add_slide()`, not lxml cloning.** The Q3 objection to `add_slide()` was an objection to
  *reusing hand-designed slides*; it does not bind here, because we draw our own body content and
  inherit only chrome (plan §6.2). The cloning engine in `renderer_draft_brief.md` is **out of
  scope — do not build it.**
- **`shp.name = el["id"]`** on every shape and connector, exactly as `calibrate.py` does. The
  round-trip suite finds shapes by name, not by position.
- CLI: `python -m aippt.canvas.render_canvas deck.json -o out.pptx`. Exit non-zero with the full
  violation list on validation failure. **The CLI is what you will actually use to debug the
  renderer** — build it first and lean on it.

`set_title` — on a **slide**, `placeholders[10]` is keyed by **idx** and raises `KeyError`. Catch it
and raise `TemplatePinError("layout 3 did not clone placeholder idx 10")`. It must never fire
silently. Then set every run property explicitly — `set_run_fonts`, `Pt(30)`, `bold = False`,
colour `000000`, `PP_ALIGN.LEFT`. **Do not trust the inherited placeholder style** to match the
editor's default.

### 1.7 — Round-trip assertion suite

`pytest`, over hand-written fixtures. Re-open the exported `.pptx` and assert (plan §7.3):

| Assertion | Tolerance |
|---|---|
| `shape.left/top/width/height` == `round(u * 12700)` | **0 EMU** — exact, by construction |
| `shape.rotation` == `el.rotation` | 0° |
| Fill RGB == `el.fill`; line RGB/width == `el.stroke` | exact |
| `<a:latin typeface="Century Gothic"/>` on every run | present |
| `<a:ea typeface="맑은 고딕"/>` on every run | present |
| `accent1` / `4472C4` anywhere in a renderer-created `<p:sp>` | **absent** |
| Inherited shadow on any renderer-created shape | **absent** |
| Slide count | exactly 1 |
| Slide relates to `slideLayout4.xml` | true |
| No element intersects `HEADER_RESERVED` / `FOOTER_RESERVED` | true |
| Every connector with `arrow != none` has `<a:headEnd>`/`<a:tailEnd>` | present |
| `<a:headEnd>` precedes `<a:tailEnd>` when both are present | true — schema order |

Fixture corpus (`tests/fixtures/canvas/*.json`): a minimal valid deck; every shape type; every
connector `kind` × `arrow` combination; a rotated shape; a multi-paragraph multi-run text box; mixed
KO/EN; a `\n` line break. Plus **rejection fixtures** that must fail validation: an element in
`HEADER_RESERVED`, one in `FOOTER_RESERVED`, one at exactly `y == 92` that must **pass**, a
`#4472C4` fill, a control character, `w <= 0`, a duplicate `id`, a wrong `template_sha256`, a wrong
`canvas`.

---

## Corrections to the plan (this brief wins)

These are not nitpicks. Two of them ship a broken file.

**1. `connectors.py` — the plan's arrowhead snippet produces a corrupt PPTX for `arrow: "both"`.**

Plan §6.7 appends `<a:tailEnd>` first, then `<a:headEnd>`. But `CT_LineProperties._tag_seq` in the
installed python-pptx 1.0.2 (`pptx/oxml/shapes/shared.py:242`) is:

```
noFill, solidFill, gradFill, pattFill, prstDash, custDash, round, bevel, miter, headEnd, tailEnd, extLst
```

`<a:headEnd>` **must precede** `<a:tailEnd>`. The plan's `ln.append()` order violates DrawingML
schema order and PowerPoint will show a repair dialog. Use `insert_element_before`, which is
order-safe regardless of the sequence you happen to add them in:

```python
ln = cxn.line._get_or_add_ln()
if el["arrow"] in ("start", "both"):
    head = ln.makeelement(qn("a:headEnd"), {"type": "triangle"})
    ln.insert_element_before(head, "a:tailEnd", "a:extLst")
if el["arrow"] in ("end", "both"):
    tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle"})
    ln.insert_element_before(tail, "a:extLst")
```

Assert the resulting child order in the round-trip suite. A fixture with `arrow: "both"` that opens
clean in PowerPoint is the proof.

**2. `render_canvas.py` — `verify_pin()` does not return a `Presentation`.**

Plan §6.2 writes `prs = verify_pin(pin)`. The **shipped** `pin.py` has `verify_pin(pin) -> None`, and
the sanctioned way to get the deck is `open_renderer_template(pin)` (which calls `verify_pin`
internally). Follow the code, not the plan. Copying the plan's line gives you `prs = None` and an
`AttributeError` three lines later.

**3. `style.py` — there are FIVE `add_shape` overrides, not four.**

Phase 0 discovered the fifth (`phase0_change_detail.md:57`). Overrides 1–3 (`fill.solid()`,
`line`, `shadow.inherit = False`) win at **render** time — an explicit `<a:solidFill>`/`<a:ln>`/
`<a:effectLst>` in `spPr` beats the style ref — but they do **not delete** the `<p:style>` block, so
`schemeClr val="accent1"` is still sitting in the shape's XML afterwards. Plan §7.3 asserts
`accent1` is *absent* from every renderer-created `<p:sp>`; with `<p:style>` left in place **that
assertion can never pass, on a deck that is in fact rendering correctly.**

```python
# 5. Strip <p:style>. It is optional in CT_Shape, so removing it is schema-valid.
style_el = shp._element.find(qn("p:style"))
if style_el is not None:
    shp._element.remove(style_el)
```

Apply this to **connectors too** (`<p:cxnSp>` carries a `<p:style>` block for the same reason).
`calibrate.py:168` has the shape half of this, working.

**4. `pyproject.toml` — `jsonschema` is in the wrong dependency group.**

It currently sits under the optional `html` extra. `canvas/validate.py` puts it on the **request
path**, so it must move to core `dependencies`. Keep the pin: `jsonschema==4.23.0`. This is the only
edit permitted to `pyproject.toml`.

---

## Landmines (each of these has already cost someone a day)

- **`layout.placeholders[10]` raises `IndexError`; `slide.placeholders[10]` raises `KeyError`.**
  The two collections key differently: on a **layout** it is **positional**
  (`shapetree.py:88`); on a **slide** it is **idx-keyed** (`shapetree.py:782`). Layout 3 has exactly
  one placeholder, so `layout.placeholders[10]` blows up. `pin.py` already handles this with
  `.get(TITLE_PH_IDX)`; your `set_title` works on a **slide**, so it wants `try/except KeyError`.
- **Stroke width 0 is a HAIRLINE in PowerPoint, not "no line."** The browser draws nothing. To get
  no line you must call `shp.line.fill.background()` explicitly. Never rely on inheritance.
- **`#4472C4` is this template's `accent1`** (`layout_manifest.json:42`) — stock Office blue. Every
  un-overridden shape arrives blue-filled, blue-outlined, drop-shadowed, with white theme-font text.
- **Text-frame margins are 7.2 / 3.6 logical units, not 0.** If you leave them at PowerPoint's
  default while the browser div has `padding: 0`, text wraps at a *different width* and you get an
  off-by-one-line overflow **that presents as a coordinate bug.**
- **The red line and the title outline are CSS pseudo-elements with no DOM node** and there is **no
  element type for them in the IR.** The layout already draws the real gradient divider — if the
  renderer ever emitted a red line, the deck would ship **two stacked dividers**. There is nothing
  to do here except never add such an element type.
- **Colour policy:** new content defaults to `#FF0032`. Inherited template chrome keeps its native
  branding and is **never** recoloured. (`#DB0032` is a legacy value in inherited content only —
  not your concern, and not to be "fixed".)

---

## Out of scope — do not build

- The editor (Phase 1B), the FastAPI server / `app.py` (Phase 1C), the raster-diff harness (Phase 1D).
- The lxml **slide-cloning** engine from `renderer_draft_brief.md`. Explicitly dropped (plan §6.2).
- Connector **gluing** (`begin_connect`/`end_connect`) — Phase 2, behind a fixture suite (D-3).
- **Transparency / alpha** in fills — opaque `#RRGGBB` only (D-4).
- `TextFrame.fit_text()` / autofit of any kind (plan §6.6).
- Touching the semantic IR in `src/aippt/ir/` or `html_adapter.py`. **Two IRs, kept apart** (plan §8).
- Editing `HUMAN_VERIFICATION.md`, `calibrate.py`, `pin.py`, `make_renderer_template.py`, or
  `reference/*`.

## Deferred (note in the change detail; do not do now)

- De-duplicating `calibrate.py` against the new `geometry.py` / `style.py`. Its Phase-0 isolation is
  deliberate. Once Phase 1A is green, `calibrate.py` should import them — that is a separate,
  reviewed change, because it re-opens a passing gate.
- **D-1 is still open and this is the cheap moment to raise it:** Century Gothic is **not** the
  Vieworks brand font. The template's real design fonts are **뷰웍스 B / 뷰웍스 M**, set at run level
  on every exemplar slide. Century Gothic body text will sit next to inherited 뷰웍스 chrome and look
  subtly off-brand. Ship Century Gothic (the user asked for it), but it is **one constant in
  `style.py`** today and an expensive discovery later. Flag it in your change detail.

---

claude_model: opus
target_repo: .
change_detail_path: tasks/AI_Powered_PPT/phase1a_change_detail.md
write_scope: src/aippt/canvas/schema.json, src/aippt/canvas/validate.py, src/aippt/canvas/geometry.py, src/aippt/canvas/style.py, src/aippt/canvas/connectors.py, src/aippt/canvas/render_canvas.py, tests/canvas/test_roundtrip.py, tests/canvas/test_validate.py, tests/canvas/test_geometry.py, tests/fixtures/canvas/, pyproject.toml
