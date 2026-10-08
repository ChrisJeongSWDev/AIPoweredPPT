# Phase 1B: The Editor (DOM → Canvas IR) — Task Brief

## Goal

Build the **web visual editor** and the **same-origin server** that carries its payload to the
Phase 1A renderer. When this is done a human opens `http://127.0.0.1:8000`, draws boxes and arrows
on a 960 × 540 stage, presses **Export PPT**, and gets back the one-slide `.pptx` that
`render_canvas.render()` already knows how to produce — and presses **Download JSON** to get a file
that `python -m aippt.canvas.render_canvas deck.json -o out.pptx` renders identically.

This implements `HTML_to_PPTX_Plan.md` §5 (tasks 2.1 – 2.8) and pulls §9's **Phase 1C tasks 3.1–3.3**
(`app.py`) forward, because the source brief scopes `app.py` into this phase. Read plan **§5 in full,
§3.2, §6.6, §6.7 and §11** before writing a line.

**The backend is already done, verified, and frozen. You are writing an adapter to it, not a partner
for it.** Every rule below that looks like a nagging detail is a rule the backend will enforce
anyway — the only question is whether the user finds out in the editor or in a 422.

---

## Context: what Phase 1A already gives you (do not rebuild, do not modify)

| Artifact | State | What it means for you |
|---|---|---|
| `src/aippt/canvas/schema.json` | **Frozen.** `canvas-ir/1`, Draft 2020-12, `additionalProperties: false` everywhere | Your serializer's output is checked against this. One stray key = rejection |
| `src/aippt/canvas/validate.py` | **Frozen.** Collects *every* violation and raises once | Your client-side checks must **mirror** it, never contradict it |
| `src/aippt/canvas/geometry.py` | **Frozen.** `HEADER_RESERVED`, `FOOTER_RESERVED`, `intersects()` (half-open), `element_bbox()` (rotated AABB) | Port this maths to JS **exactly**: same numbers, same half-open rule, same rotated AABB |
| `src/aippt/canvas/render_canvas.py` | **Frozen.** `render(ir: dict) -> Presentation` | `app.py` calls this and nothing else. It validates internally |
| `src/aippt/canvas/pin.py` | **Frozen.** `load_pin()`, `verify_pin()`, `open_renderer_template()` | `app.py` calls `load_pin()` + `verify_pin()` **once at startup** |
| `reference/renderer_template.pptx` | Pinned. SHA `60fe35466ed2bb477d592603d0eab9d8748521e54ae0632c9f6a94d0b02a855a`, 1,212,639 B | The editor **must not hard-code this SHA** — see `/api/context` below |
| `tests/fixtures/canvas/*.json` | 16 fixtures, incl. `minimal.json`, `reject_header.json`, `reject_accent1.json` | Reuse them as `app.py` test inputs |

> **Read `src/aippt/canvas/schema.json` first, top to bottom, including the `description` strings.**
> It is the specification of your serializer's output, and its descriptions explain *why* each field
> is shaped the way it is. Reading it will save you a debugging cycle per element type.

---

## Authoritative constants

```
model space   = 960 × 540 logical units.  1 unit ≡ 1 pt ≡ 12,700 EMU exactly.
                NOTHING ELSE ever enters the IR. No px, no %, no EMU (the browser never sees 12700).
font size     = 1:1 with the unit. A size-14 run is `font-size: 14px` on the stage and Pt(14) in PPTX.

BRAND_RED     = #FF0032     default fill for new shapes / connectors
FORBIDDEN     = #4472C4     theme accent1 — validate.py REJECTS it. The colour picker must too.
LATIN font    = 'Century Gothic'
EA font       = 'Malgun Gothic' / 맑은 고딕   (Century Gothic ships no Hangul glyphs)

text insets   = left/right 7.2 units, top/bottom 3.6 units.  Hard-coded on BOTH sides (§5.6/§6.6).
line-height   = 1.2       (== renderer line_spacing)
min extent    = 4 logical units for w and h  (schema requires > 0; the editor requires ≥ 4)
```

### Reserved regions — port these numbers verbatim from `geometry.py`

| Region | Box `(x1, y1, x2, y2)` | Rule in the editor |
|---|---|---|
| `HEADER_RESERVED` | `(0, 0, 960, 92)` | An element may **never** be committed intersecting it |
| `FOOTER_RESERVED` | `(733.6, 500, 960, 540)` | Same |
| `BODY_SAFE` | `(45.6, 92, 914.4, 500)` | **Snap target only, not a constraint.** An element may legally sit outside it |
| `TITLE_LOCKED` | `(45.55, 26.75, 770.84, 64.0)` | The title field. Not movable, not resizable, **never an element** |
| slide bounds | `(0, 0, 960, 540)` | Nothing may fall outside |

**Intersection is strict overlap, not edge contact:**

```js
const intersects = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
```

An element whose top edge is exactly `y = 92` is **legal** — `BODY_SAFE` starts at exactly 92. Get
this wrong and every top-aligned element the user draws is spuriously blocked. Same at `y = 500`.

**Bounds and reserved checks use the ROTATED AABB**, not the path box (`geometry.element_bbox()`).
A 45°-rotated box whose unrotated footprint clears the header but whose rotated corners do not is
**rejected by the backend** — so the editor must block it too, or the user meets a 422 they cannot
explain. Port the rotation maths exactly (y grows downward, so the standard matrix turns *clockwise*
on screen, which is what DrawingML's `a:xfrm/@rot` means).

---

## THE PRIME DIRECTIVE

> ### `getBoundingClientRect()` appears **exactly once** in `editor.js`, inside `toModel(ev)`.
> ### Nothing else may measure the DOM. Ever.

```js
// The ONLY place a device coordinate becomes a model coordinate.
function toModel(ev) {
  const r = stage.getBoundingClientRect();          // used ONLY for pointer inversion
  return { x: (ev.clientX - r.left) / zoom,
           y: (ev.clientY - r.top)  / zoom };
}
```

**Banned outright in `editor.js`** — grep-enforced by a test (Gate 1):

`offsetWidth` · `offsetHeight` · `clientWidth` · `clientHeight` · `offsetLeft` · `offsetTop` ·
`devicePixelRatio` · `getComputedStyle` · `getBBox` · interact.js's `event.rect` · any percentage or
responsive width in the IR path · any value read back out of CSS.

**Geometry lives in JS state and flows one way:**

```
state (el.dataset.x/y/w/h/rot)  ──render──>  CSS + SVG attributes
                               ✗ never read back ✗
```

`12700` must **not appear in `editor.js` at all.** The browser never converts to EMU; Python does,
once, at the end. Carry floats in the IR; round only to kill float noise (`Math.round(v * 1e6) / 1e6`).

### The interact.js corollary (this is where people get it wrong)

interact.js hands you `event.rect` — a **measured, device-pixel** rectangle straight out of
`getBoundingClientRect()`. Consuming it silently reintroduces every bug this rule exists to delete,
and it breaks the moment zoom ≠ 1.

**Consume only deltas, and divide them by `zoom`:**

```js
interact('.el').draggable({
  modifiers: [],                                   // NO interact snap/restrict modifiers — see below
  listeners: {
    move(ev) {
      const el = ev.target;
      const dx = ev.dx / zoom, dy = ev.dy / zoom;  // device px -> logical units. Always.
      commit(el, { x: S(el).x + dx, y: S(el).y + dy });
    },
  },
});
```

Resize is the same shape: take `ev.deltaRect.left/top/width/height`, divide **each** by `zoom`, apply
to state. **Never** assign from `ev.rect`.

**Do not use interact.js's `snap` or `restrict` modifiers.** They operate in page/device pixels, so
at zoom = 0.5 an 8-unit grid becomes a 4-unit grid and the reserved-region restriction lands in the
wrong place. **All snapping and all constraint enforcement happen in model space, in your code,**
after the `/zoom` conversion.

---

## Write scope

**Create:**

```
src/aippt/canvas/app.py
src/aippt/canvas/static/index.html
src/aippt/canvas/static/editor.js
src/aippt/canvas/static/style.css
src/aippt/canvas/static/vendor/interact.min.js     (if vendoring — see below)
tests/canvas/test_app.py
tests/canvas/test_editor_source.py
phase1b_change_detail.md                            (your report; same conventions as phase1a)
```

**Append to (surgical edits only, no reformatting):**

```
pyproject.toml       — an `editor` optional-dependency group + package-data for static/
requirements.txt     — a Phase 1B section, in the file's existing commented style
```

**DO NOT TOUCH — frozen, out of scope:**

```
src/aippt/canvas/{schema.json, validate.py, geometry.py, style.py, connectors.py,
                  render_canvas.py, pin.py}
src/aippt/tools/{calibrate.py, make_renderer_template.py}
src/aippt/ir/**            (the OTHER IR — plan §8: they must not merge, must not import each other)
src/aippt/render/**, src/aippt/adapters/**
reference/**               (re-pinning is a deliberate, reviewed act — §4.3)
HUMAN_VERIFICATION.md      (out of scope, as in Phase 1A)
tests/fixtures/canvas/**   (read them; do not edit them)
tests/canvas/test_{geometry,validate,roundtrip}.py
```

If you believe a frozen file has a bug, **write it up in `phase1b_change_detail.md` under "Backend
defects found" — do not fix it.** A silent edit to `validate.py` to make your serializer pass is the
single worst outcome available in this phase.

---

## File specifications

### 1 — `static/index.html`

Static shell only. No inline geometry logic, no framework, no build step.

- `<meta charset="utf-8">`. The stage carries Korean text.
- Layout: a left **toolbar** (tools + properties), a **stage-wrap** (scrolls), a **status bar**.
- The stage, and the two structurally-unserializable pieces of chrome:

```html
<div id="stage-wrap">
  <div id="stage" style="--zoom: 1">
    <!-- #stage::before = TITLE_LOCKED outline,  #stage::after = the red divider line.
         CSS pseudo-elements: they have NO DOM node, so the serializer CANNOT emit them
         even by accident (critic rule 6). Do not "improve" them into real divs. -->
    <div id="title-field" contenteditable="true" spellcheck="false"></div>
    <!-- user elements are appended here, class="el" -->
  </div>
</div>
```

- **`#title-field` is deliberately NOT `.el`.** It is the `title` string field (→ placeholder idx 10),
  positioned over `TITLE_LOCKED` so the user sees it in place. Not draggable, not resizable, no
  handles, no `data-type` — and the serializer's `:scope > .el` selector structurally cannot pick it
  up.
- Toolbar controls (task 2.6): tool buttons (select / rect / ellipse / triangle / textbox /
  connector), **fill colour**, **stroke colour + width**, **text colour**, **font size**,
  **align / valign**, **arrow** (none/start/end/both), **kind** (straight/elbow), **rotation**,
  **zoom**, **Download JSON**, **Load JSON** (optional), **Export PPT**.
- A `#warnings` banner region — the Century Gothic warning, the server-unreachable banner and the
  backend's numbered violation list land here. Loud, not a `console.warn` nobody reads.

### 2 — `static/style.css`

**Copy §5.2, §5.3 and §5.6 literally.** These declarations are a *contract with the renderer*, not
styling preferences — every one has a counterpart in `style.py` / §6.6, and they change together or
not at all. Do not tidy them, do not switch to `rem`, do not add a CSS reset that alters them.

- `#stage`: `position: relative; width: 960px; height: 540px; transform: scale(var(--zoom));
  transform-origin: 0 0; background: #FFFFFF; overflow: hidden;`
- `#stage-wrap`: size it *from* the zoom variable (`width: calc(960px * var(--zoom))`) so scrollbars
  behave. CSS derived from state is fine; reading it back is not.
- `#stage::after` (red line) and `#stage::before` (title outline): exactly the geometry in §5.3 —
  `left: 46.4px; top: 71px; width: 742.3px; height: 2px; background: #FF0032` and
  `left: 45.55px; top: 26.75px; width: 725.29px; height: 37.25px; outline: 1px dashed rgba(0,0,0,.25)`
  — both `pointer-events: none`. **The header is deliberately not WYSIWYG**: the editor shows a flat
  red line, PowerPoint shows the real gradient. Say so in the UI (a one-line note under the stage).
- `.el`: `position: absolute; transform: rotate(var(--rot)); transform-origin: 50% 50%;` —
  centre-origin, degrees clockwise, identical to `shape.rotation` in python-pptx (§5.5). No
  conversion anywhere.
- `.el .txt`: **the §5.6 block, verbatim** — the 7.2/3.6 insets, `box-sizing: border-box`,
  `font-family: 'Century Gothic', 'Malgun Gothic', sans-serif`, `font-size: 14px`,
  `line-height: 1.2`, `white-space: pre-wrap`, `overflow-wrap: break-word`, `word-break: keep-all`,
  the flex centring, and **`overflow: visible`**. Overflow is *shown*, never clipped: that visibility
  is the entire text-overflow defence (§5.6, §7.4).
- Editor-only affordances (selection outline, handles, `.blocked` flash) must not alter layout: use
  `outline`, never `border` — a border changes the box model and drifts your geometry by `border/2`.

### 3 — `static/editor.js`

One file, plain ES module or a single IIFE. No bundler, no npm at runtime.

#### 3.1 State — the element *is* the model

One `.el` div per element; geometry and style live in `dataset`:

| `data-*` | Types | Meaning |
|---|---|---|
| `id` | all | unique; becomes `shp.name` in the PPTX. `validate.py` rejects duplicates |
| `type` | all | `rect` \| `ellipse` \| `triangle` \| `textbox` \| `connector` |
| `x`, `y`, `w`, `h` | shapes | unrotated **path box**, logical units. Stroke NOT included (§5.4) |
| `rot` | shapes | degrees CW about the centre |
| `fill` | shapes | `#RRGGBB`, or `""` meaning **no fill** → serialized as `null` |
| `strokeColor`, `strokeWidth` | shapes | absent/empty ⇒ `stroke: null` |
| `x1`, `y1`, `x2`, `y2` | connector | absolute endpoints |
| `kind`, `arrow`, `color`, `width` | connector | `straight`\|`elbow`; `none`\|`start`\|`end`\|`both` |
| `size`, `color`, `align`, `valign` | shapes | the element's default run size/colour + paragraph align |

**Defaults for new content:** shapes → `fill: #FF0032`, `stroke: null`, `size: 14`, `color: #FFFFFF`,
`align: CENTER`, `valign: MIDDLE`. **`textbox` → `fill: ""` (no fill), `color: #000000`.**
Connector → `color: #FF0032`, `width: 1.5`, `arrow: end`, `kind: straight`.

**Z-order is DOM order and nothing else.** No `z` field, no `z-index` on `.el`, no sort key. Raise =
`insertBefore` / `append`. A `z-index` on `.el` is a second source of truth and is grep-banned by
Gate 1.

#### 3.2 Shapes: inline SVG with a 1:1 viewBox (§5.4)

```html
<div class="el" data-type="rect" style="left:100px; top:120px; width:180px; height:60px">
  <svg width="180" height="60" viewBox="0 0 180 60" preserveAspectRatio="none"
       style="overflow:visible; position:absolute; inset:0">
    <rect x="0" y="0" width="180" height="60" fill="#FF0032" stroke="#FFFFFF" stroke-width="1"/>
  </svg>
  <div class="txt" contenteditable="true">Capture</div>
</div>
```

**Never use a CSS `border` for the stroke.** SVG strokes are *centred on the path* and bleed
`width/2` outward — exactly like DrawingML `<a:ln>`. CSS borders draw *inward* (`box-sizing`), which
puts a `stroke/2` drift on every shape and presents as a coordinate bug. That is the entire reason
§5.4 mandates SVG. `overflow: visible` is what lets the outer half of the stroke draw.

- rect → `<rect>` · ellipse → `<ellipse cx="w/2" cy="h/2" rx="w/2" ry="h/2">` ·
  triangle → `<polygon points="w/2,0 w,h 0,h">` (apex top-centre; matches
  `MSO_SHAPE.ISOSCELES_TRIANGLE`) · textbox → a `<rect>` so it can still carry fill/stroke, or no SVG
  when it has neither.
- No fill ⇒ `fill="none"`. No stroke ⇒ omit the `stroke` attribute entirely. **Never emit
  `stroke-width="0"`** to mean "no line": width 0 is a *hairline* in PowerPoint, not an absence (see
  the schema's `line_width` note). No line = `"stroke": null`.

#### 3.3 Connectors (§6.7, task 2.5)

- The `.el` wrapper spans the endpoints' AABB: `left = min(x1,x2)`, `top = min(y1,y2)`,
  `width = max(|dx|, 1)`, `height = max(|dy|, 1)`. The `max(…, 1)` keeps a perfectly horizontal
  line's SVG box non-degenerate and **never touches the IR**, which stores the raw endpoints.
  `overflow: visible` lets the stroke and arrowheads draw outside the box.
- `straight` → `<line>` in local coords. `elbow` → `<polyline>` routed
  `(x1,y1) → (mx,y1) → (mx,y2) → (x2,y2)` with `mx = (x1+x2)/2`.
  **⚠ Caveat, and put it in the UI:** PowerPoint's `MSO_CONNECTOR.ELBOW` auto-routes; our polyline is
  an *approximation*, and elbow is the one place the preview is knowingly inexact. Default new
  connectors to `straight`.
- Arrowheads: an SVG `<marker>` per connector (id-scoped), `fill` = the connector's colour, sized so
  the tip lands **on** the endpoint. `arrow: start` → `marker-start`, `end` → `marker-end`, `both` →
  both. This mirrors DrawingML `<a:headEnd>` / `<a:tailEnd>`.
- **New connectors are inserted at the FRONT of the elements array** — `stage.insertBefore(el,
  firstNonConnector)` — so they are drawn *first* and therefore sit **behind** the boxes they join.
  Array order is z-order; front of array = back of the slide. (The plan says this twice, in two
  directions; this is what it means.)
- Endpoints drag individually (two endpoint handles). **No gluing** — `begin_connect()` /
  `end_connect()` are explicitly out of Phase 1 (D-3).

#### 3.4 Interactions, zoom, snapping, constraints (tasks 2.1, 2.3, 2.8)

- `zoom` is a single JS number and the single source of truth; `#stage`'s `--zoom` is written *from*
  it. Zoom range 25 %–200 %.
- Drag / resize via interact.js, **deltas only, `/zoom`** (see the Prime Directive corollary). Resize
  from 8 handles; rotate from one handle (Shift → snap to 15°).
- **Snapping happens in model space**, after the `/zoom` conversion: a 4-unit grid, plus the
  `BODY_SAFE` edges (`x 45.6 / 914.4`, `y 92 / 500`) and the stage centre lines. Hold **Alt** to
  suspend snapping.
- **Constraint pipeline — every committed frame, in this order:**

  1. compute the candidate state from the delta;
  2. enforce `w, h ≥ 4`;
  3. snap (unless Alt);
  4. clamp to the slide (`0 ≤ bbox ≤ 960 × 540`);
  5. compute the **rotated AABB** and test `intersects()` against `HEADER_RESERVED` and
     `FOOTER_RESERVED`;
  6. legal → **commit**. Illegal → **do not commit this frame** (the element holds its last legal
     state) and flash `.blocked` on it.

  Reject-and-hold is deterministic and honest. A "clever" push-out under rotation is neither, and it
  will disagree with `geometry.py` — at which point the user is looking at a legal-looking stage and
  a 422.
- Creation by drag-out on the stage: pointer coords via `toModel(ev)`, then the *same* pipeline — an
  illegal shape cannot be drawn in the first place.
- Delete (`Del`/`Backspace` when not editing text), duplicate (`Ctrl+D`, **new id**), raise / lower.
  Undo/redo is **out of scope** (deferred).

#### 3.5 Text: `contenteditable` → paragraphs / runs (task 2.4, §5.6)

Call `document.execCommand('styleWithCSS', false, false)` once at init so bold/italic emit `<b>` /
`<i>` tags rather than styled spans. Handle both anyway.

`normalizeText(root) -> IR text | null` — walk the DOM, carry a format stack, emit runs:

| DOM | IR |
|---|---|
| block-level `<div>` / `<p>` | **new paragraph** |
| `<br>` | `"\n"` inside the current run (`style.py` splits on it and emits `<a:br/>`) |
| `&nbsp;` (U+00A0) | **preserved verbatim.** Never collapse it to a space |
| `<b>` / `<strong>`, `<i>` / `<em>` | run-level `bold` / `italic` |
| inline `style="color: …"` / `<font color>` | run-level `color` (`rgb(r,g,b)` → `#RRGGBB`, upper-case) |
| everything else | flattened to plain text |

Rules:

- Read the **inline `style` attribute** (`node.style.color`), **never `getComputedStyle`** — banned,
  and it would silently bake the CSS default into every run.
- **Strip C0 control characters except `\t` and `\n`** at serialization time. `validate.py` rejects
  them; strip them here so the user never gets a 422 for a character they cannot see.
- Merge adjacent runs with identical formatting. Drop empty runs, then empty paragraphs — browsers
  leave a trailing empty `<div>` behind constantly.
- Every run carries `t`, `size`, `color` — **all three are required by the schema.** `size` and
  `color` come from the element's `data-size` / `data-color` unless a span overrides the colour. (An
  un-coloured run inherits `fontRef → lt1`, which is **white**: this is the rule that stops
  white-on-white text.)
- **If nothing survives, emit `"text": null`** — not `paragraphs: []`; the schema requires
  `minItems: 1`.
- `title`: the same walk flattened to a plain **string**; `<div>` / `<br>` → `"\n"`; strip C0 except
  `\t` / `\n`; trim trailing newlines. A `"\n"` in the title becomes an `<a:br/>` in placeholder 10.

#### 3.6 Font and colour guards (§5.7, task 2.6)

```js
await document.fonts.ready;
if (!document.fonts.check('14pt "Century Gothic"')) {
  warn("Century Gothic is not installed. This preview does NOT match what PowerPoint will render.");
}
```

Render that into `#warnings`, visibly. A preview that lies silently is worse than no preview.

Refuse `#4472C4` in every colour input (fill, stroke, text, connector), with the reason
`validate.py` gives: it is this template's theme accent1, and banning it as an explicit author choice
is what keeps "no accent1 in any generated shape" machine-checkable rather than aspirational.

#### 3.7 The serializer (task 2.7)

```js
function serialize() {
  return {
    schema: "canvas-ir/1",
    canvas: { w: 960, h: 540, unit: "pt" },
    target: {
      template: "reference/renderer_template.pptx",   // informational only
      template_sha256: CONTEXT.template_sha256,       // from /api/context — NEVER hard-coded
      layout_index: 3,
    },
    title: titleString(),
    elements: [...stage.querySelectorAll(":scope > .el")].map(toIR),  // DOM order IS z-order
  };
}
```

- `:scope > .el` is the whole z-order story *and* the whole "chrome cannot be serialized" story: the
  pseudo-elements have no node, and `#title-field` has no `.el`.
- `toIR(el)` emits **exactly** the schema's keys for that `type` and **nothing else**
  (`additionalProperties: false` — one leaked `data-*` is a hard rejection). No `z`. No `w`/`h` on a
  connector. No `text` on a connector. `fill` is **required even when null**.
- Numbers: `round6(v) = Math.round(v * 1e6) / 1e6`. Floats in the IR; the EMU rounding is Python's
  job and happens once.
- **Download JSON** writes this object with `JSON.stringify(ir, null, 2)` via a Blob. That file must
  render through the CLI unchanged — Gate 4.

---

### 4 — `src/aippt/canvas/app.py` (plan §9 tasks 3.1–3.3, pulled forward)

FastAPI. Serves the editor **same-origin**; renders in memory.

```
GET  /                → static/index.html
GET  /static/*        → StaticFiles(directory=Path(__file__).with_name("static"))
GET  /api/context     → 200 {"template_sha256", "layout_index": 3, "canvas": {...},
                             "brand": {"red": "#FF0032", "forbidden": "#4472C4"},
                             "fonts": {"latin": "Century Gothic", "ea": "맑은 고딕"}}
POST /api/export      → 200 application/vnd.openxmlformats-officedocument.presentationml.presentation
```

- **Startup (lifespan), once — not per request:** `pin = load_pin(); verify_pin(pin)`. On
  `TemplatePinError`, **let it propagate: the process must refuse to start.** Fail closed; never fall
  back to another layout. Cache the SHA for `/api/context`.
- **`/api/context` exists so the editor never hard-codes a SHA.** A hard-coded SHA turns "re-pin the
  template" into a silent 409 for every user; serving it keeps the pin the single source of truth. If
  the fetch fails, the editor shows a banner and **disables Export and Download JSON** — a payload
  carrying a fabricated SHA is worse than no payload.
- **`POST /api/export`:** take the raw JSON body, call `render_canvas.render(ir)`, `prs.save(buf)`
  into a `BytesIO`, return the bytes with
  `Content-Disposition: attachment; filename="deck.pptx"; filename*=UTF-8''<pct-encoded title>` — the
  title is Korean often enough that the RFC 5987 form is not optional. Sanitize the ASCII fallback;
  the title never reaches the filesystem.
- **Errors, mapped honestly:**

  | Raised | Status | Body |
  |---|---|---|
  | `StalePayloadError` (stale canvas **or** stale SHA) | **409** | `{"error": "stale", "detail": str(exc)}` → the editor says **reload** |
  | `CanvasValidationError` | **422** | `{"error": "validation", "detail": str(exc)}` → the numbered list, rendered verbatim into `#warnings` |
  | malformed JSON | **400** | — |
  | `TemplatePinError` at request time | **500** | unreachable if the startup gate ran; log it |

  `StalePayloadError` **subclasses** `CanvasValidationError` — **catch it first**, or every stale
  payload reports as a 422 and the user is told to fix a deck that is fine.
- **Security (task 3.2):** the template path is fixed server-side and **never read from the payload**
  — `target.template` is informational and must be ignored. Bind `127.0.0.1` by default. Reject
  bodies over ~2 MB. No CORS middleware (same-origin only). The server writes **no files**; the
  `.pptx` exists only in memory.
- **The CLI keeps working (task 3.3).** `app.py` adds a path; it does not replace one. Corporate IT
  blocks localhost servers often enough that the CLI is the fallback that always works — so nothing
  under `canvas/` may import `app.py`.
- `python -m aippt.canvas.app` → uvicorn on `127.0.0.1:8000`.

### 5 — `pyproject.toml` / `requirements.txt`

Web deps are **optional**: the renderer and the CLI must keep working without a web stack installed.

```toml
[project.optional-dependencies]
editor = ["fastapi>=0.115", "uvicorn[standard]>=0.30"]
```

Add `httpx` to the `dev` group (FastAPI's `TestClient` needs it). Add
`[tool.setuptools.package-data]` → `"aippt.canvas" = ["schema.json", "static/*", "static/vendor/*"]`
so the static files ship with the package. Mirror both in `requirements.txt` under a new
`# --- Phase 1B: the editor ---` heading.

---

## interact.js: how to source it

The plan mandates interact.js (~10 KB) **or** "~150 lines of `pointerdown`/`pointermove`/`pointerup`
with pointer capture" (§5.1). This is a corporate network: do not assume a CDN is reachable at
runtime, and do not add an npm build step.

1. **Vendor it.** Fetch `interact.min.js` (MIT) once into `static/vendor/interact.min.js`; load it
   with a plain `<script src>`. Offline-safe, no SRI question, no build step.
2. If you cannot fetch it, **write the fallback**: pointer capture, ~150 lines, behind the *same
   internal interface* your call sites use (`Interactions.draggable(...)`, `.resizable(...)`), so
   swapping interact.js in later is a one-file change.

**Either way the Prime Directive is unchanged: deltas only, divided by `zoom`, no measured rects.**
Record which option you took, and why, in `phase1b_change_detail.md`. Do **not** load from a CDN at
runtime — the editor must work with the network off.

---

## Acceptance gates

All four. Run `pytest` from the task root and paste the real output — do not paraphrase it.

### Gate 1 — `tests/canvas/test_editor_source.py` (the Prime Directive, machine-checked)

Static source assertions over `static/editor.js`. Cheap, and the only thing standing between "we
agreed on the rule" and "the rule held":

- `getBoundingClientRect` occurs **exactly once**, and that occurrence is inside `toModel`.
- **Zero** occurrences of `offsetWidth`, `offsetHeight`, `clientWidth`, `clientHeight`, `offsetLeft`,
  `offsetTop`, `devicePixelRatio`, `getComputedStyle`, `getBBox`, `event.rect` / `ev.rect`.
- Every `deltaRect` read is divided by `zoom` in the same expression.
- **Zero** occurrences of `12700` (no EMU maths in the browser) and of `zIndex` / `z-index` on `.el`
  (z-order is DOM order).
- `"canvas-ir/1"` and `w: 960, h: 540, unit: "pt"` appear; **no other canvas size does**.
- `#4472C4` appears **only** in the rejection path.

### Gate 2 — `tests/canvas/test_app.py` (FastAPI `TestClient`, no browser)

- `GET /` → 200, contains `id="stage"`.
- `GET /api/context` → `template_sha256` **equals** `load_pin()["renderer_template"]["sha256"]`.
- `POST /api/export` with `tests/fixtures/canvas/minimal.json` → 200; body starts with `PK`;
  `Presentation(BytesIO(body))` has **exactly 1 slide**.
- `POST` `reject_header.json` → **422**, `HEADER_RESERVED` in `detail`.
- `POST` `reject_accent1.json` → **422**, `4472C4` in `detail`.
- `POST` a payload with a wrong `template_sha256` → **409**.
- `POST` a payload with `canvas: {"w": 1920, "h": 1080, "unit": "pt"}` → **409** (stale — never
  rescaled).
- `POST` malformed JSON → 400/422, no traceback leaked.
- The export writes **no file to disk**.

### Gate 3 — the existing suite stays green

`python -m pytest tests/ -q` — every Phase 1A test still passes. You changed no backend file, so any
red here comes from your packaging edit and is yours to fix.

### Gate 4 — the editor ↔ CLI contract (manual; do it, paste the output)

Draw two boxes and a connector in the browser → **Download JSON** →
`python -m aippt.canvas.render_canvas <downloaded>.json -o out.pptx` → exit 0, prints
`1 slide, 3 element(s)`. If **Export PPT** and the CLI disagree on the same payload, the bug is in
`app.py`, not in the renderer.

### Human gates — list them as un-run; do not edit `HUMAN_VERIFICATION.md`

In `phase1b_change_detail.md`, record as still un-run: PowerPoint opens the export clean; logo,
gradient divider and page number inherited and undistorted; Korean and English each in their intended
typeface; raster diff vs. the stage screenshot at zoom 1 ≤ 2 px (§7.5). **Do not write "WYSIWYG"
anywhere without pointing at that evidence** (§7.5).

---

## Decisions I am making for you (and why)

| # | Decision | Why |
|---|---|---|
| 1 | **`app.py` ships in 1B**, not 1C | The source brief scopes it here. The CLI path stays first-class (task 3.3) |
| 2 | **`/api/context` serves the template SHA**; the editor never hard-codes it | A hard-coded SHA makes every future re-pin a silent 409 for every user |
| 3 | **Reject-and-hold** on constraint violation, not push-out | Deterministic, and it cannot disagree with `geometry.py` under rotation |
| 4 | **All snapping in model space**; interact.js modifiers disabled | interact's modifiers snap in device px and drift with zoom |
| 5 | **Title is an in-stage `#title-field`, not `.el`** | WYSIWYG placement, and `:scope > .el` makes it structurally unserializable |
| 6 | **Elbow connectors are not the default**; the SVG polyline is an approximation | PowerPoint auto-routes elbows; this is the one knowingly-inexact preview |
| 7 | **`textbox` defaults to `fill: null` + black text**; shapes default to brand red + white text | Matches the schema's stated authorial intent for the type split |
| 8 | Undo/redo, multi-select, copy-paste, Load JSON: **stretch, not gates** | Not in §5 or §9's task list. Ship the contract first |

## Deferred — name them in your report, do not build them

Layout-3 PNG stage background (**D-2** — makes the header genuinely WYSIWYG and moots the red-line
approximation) · connector gluing (D-3) · alpha (D-4) · autofit · multi-slide · images · undo/redo ·
de-duplicating `calibrate.py` against `geometry.py` / `style.py`.

## Deliverable

`phase1b_change_detail.md` — files created, the interact.js decision, gate output pasted verbatim,
every assumption, every caveat, any backend defect found (**written up, not fixed**), and the un-run
human gates. Assumptions are not a failure; unstated assumptions are.
```

---

**Assumptions and caveats** (as the brief instructed me to state rather than ask about):

1. `app.py` is plan §9 **Phase 1C**, not 1B. The draft brief scopes it into 1B anyway, so I wrote it into 1B and said so explicitly. Task 3.3 ("keep the CLI working") comes along with it, since the CLI is the fallback when corporate IT blocks localhost.
2. FastAPI, uvicorn and httpx are **not** currently in `pyproject.toml` or `requirements.txt`. Adding them means the write scope must extend past the four files the draft brief listed — so I put those two files in scope as append-only edits, with the web stack as an *optional* dependency group so the frozen renderer and CLI still install and run without it.
3. interact.js is not vendored anywhere in the repo and there is no npm setup. I could not verify network reachability from this sandbox, so the brief gives an ordered fallback (vendor the file; failing that, the ~150-line pointer-capture implementation the plan itself sanctions) behind one interface, and requires the implementer to record which path they took.
4. I did **not** verify that `fastapi`/`uvicorn` are importable in the current interpreter — the permission layer blocked the `python -c` probe. If they are missing, `pip install -e ".[editor,dev]"` is the first step of Gate 2.
5. The plan's §6.7 snippet appends `<a:tailEnd>` before `<a:headEnd>`, which the schema says is backwards and would produce a file PowerPoint calls corrupt. Phase 1A's `connectors.py` is frozen and presumably already handles this; I flagged it only as "do not touch, report if broken" rather than sending the implementer to fix it.


---

claude_model: opus
mode: continuation
target_repo: .
change_detail_path: tasks/AI_Powered_PPT/phase1b_change_detail.md
write_scope: src/aippt/canvas/app.py, src/aippt/canvas/static/index.html, src/aippt/canvas/static/editor.js, src/aippt/canvas/static/style.css, pyproject.toml, requirements.txt
