# Foundation Research — AI-Generated PowerPoint on the Vieworks R&D Template

**Status:** framework + research. Not an implementation.
**Date:** 2026-07-13

---

## ⚠️ Epistemic status — what is verified and what is not

This document distinguishes three grades of claim, and marks them, because the difference
matters enormously to anyone acting on it.

| Grade | Meaning |
|---|---|
| ✅ **VERIFIED** | Measured directly from the source files in this session. |
| 📖 **KNOWN** | Documented behaviour of python-pptx / OOXML. Confident, but not re-tested here. |
| ❌ **UNVERIFIED** | **Depends on opening the `.pptx`, which did not happen.** Treat as an open question. |

**The PoC was never run.** `analyze_pptx_master.py` is written and complete, but the
session that produced it had no code-execution permission — Python was denied through the
shell, through PowerShell, and through a subagent. Consequently *nothing* about the
template's internals is confirmed: not the layout count, not the layout names, not the box
geometry, not the font sizes, and not where `#DB0032` lives.

Every such gap below is marked ❌ and left empty. It would have taken thirty seconds to
fill them with plausible invented numbers, and that would have been the single most
damaging thing this document could do: the layout catalog is injected verbatim into every
AI prompt, so a fabricated one propagates into every generated deck and fails far
downstream, wearing the disguise of a renderer bug.

**Run `python -m aippt.analyze_pptx_master` and fill in §4.** Everything else here holds
regardless of what it prints.

---

## 1. Problem, goals, and the three approaches we reject

### The problem

Vieworks R&D produces technical decks — SDK guides, architecture proposals, test-bench
designs. Today they are authored as hand-built HTML "card" decks (30 slides across three
files, see §3). They look good in a browser, and they are not PowerPoint: they cannot be
handed to a colleague to edit, they do not carry the corporate master, and they cannot be
dropped into a customer-facing deck.

Meanwhile `Vieworks_R&D_ppt_Template.pptx` — the real corporate template, with the real
master, the real fonts and the real brand red — sits unused by this workflow.

### Goals

1. Generate `.pptx` decks that are **indistinguishable from human-authored ones built on
   the corporate template** — because they *are* built on it.
2. Output must be **fully editable**: real text in real placeholders, real shapes. A
   designer must be able to open it and move things.
3. **Two front doors, one engine:** convert the existing HTML decks, *and* author new decks
   from a topic + source material.
4. **Model-agnostic.** Claude, Codex and Gemini are swappable authors behind one interface.

### Rejected: (a) headless-browser screenshot → image slides

Render the HTML in Chrome, screenshot each card, `add_picture` it onto a blank slide.

Seductive because it is a weekend's work and the output looks *pixel-identical* to the
HTML. Rejected because it produces a deck of **pictures of slides**:

- Nothing is editable. Not one word. Fixing a typo means re-rendering the source HTML —
  which most of the audience for these decks does not have and could not run.
- The corporate master is bypassed entirely. The output inherits the *browser's*
  typography, not the template's. It only coincidentally resembles a Vieworks deck.
- No text layer: no search, no screen reader, no copy-paste, no reflow.
- It hard-codes the current HTML CSS as the de facto design system, permanently. The
  designer who owns the master has been written out of the loop.

This approach optimises for the demo and sacrifices the product. It is the one to be most
careful about, precisely because the first screenshot looks so convincing.

### Rejected: (b) the LLM writes DrawingML / OOXML directly

Ask the model for `<p:sp>` elements.

- OOXML is verbose, deeply namespaced, and unforgiving. A single misplaced element yields
  "PowerPoint found unreadable content" — with no indication of which of 4,000 lines is at
  fault.
- The failure mode is *binary and opaque*. There is no partial credit and no useful error,
  so the repair loop has nothing to work with.
- It burns an enormous number of tokens on syntax that a template already encodes perfectly.
- It puts geometry in the hands of the component with the least reliable grasp of it.
  Models are excellent at prose and structure; they are not a layout engine.

### Rejected: (c) build from a blank `Presentation()`

Create an empty deck and restyle it to match the brand.

- `Presentation()` with no argument loads python-pptx's **stock 4:3 Office template**. Not
  the Vieworks master. 📖
- Every colour, font, size and position would have to be re-applied by hand — a
  reimplementation of the template in Python, which must then be kept in sync with a
  `.pptx` that a designer will keep editing. It will drift, and the drift will be silent.
- The master, the layouts and the theme are *gone*. A user who opens the deck and picks
  "New Slide" gets nothing that matches.

The template is not a style guide to be imitated. It is the source of truth, and the
correct move is to **open it and add slides to it**.

### What we do instead

Open the real template. Call `add_slide()` with the template's **own** `slide_layouts`. Put
text in placeholders. Let the master do what a master is for.

---

## 2. The pipeline

```
                          reference/layout_manifest.json
                          reference/layout_catalog.md
                                    │  (generated once by analyze_pptx_master.py)
                                    │
                                    ▼
  HTML deck ──> html_adapter ──┐         ┌──> layout_id + content budgets
                               ├─> [ Slide IR ] ─> renderer ─> deck.pptx
  topic + sources ─> ai_adapter┘     (JSON,          │
                          ▲           schema-        │
                          │           validated)     ▼
                          │                    LibreOffice ─> PDF ─> PNG
                          │                          │
                          │                          ▼
                          │                 geometry checks (fit.py)
                          │                          +
                          └───── repair ◄──── vision critique (30_visual_qa.md)
```

Four properties this shape buys, none of which are free:

**The IR is the contract.** Adapters and renderer are coupled only through
`ir/schema.json`. A new input source (Markdown, Confluence, a Word doc) is a new adapter
and nothing else changes. A new output target is a new renderer.

**The AI is confined to one box.** It writes `layout_id` + content. It cannot emit
geometry because the schema has nowhere to put geometry. The invariant is enforced by the
data model, not by asking the model nicely — which is the only kind of enforcement that
survives contact with a model that is having an off day.

**Determinism where determinism is possible.** Layout, geometry and styling are code.
Only *content* is probabilistic. When a deck comes out wrong, the question "is this a
model problem or a code problem?" has a crisp answer.

**Model-agnosticism is structural, not aspirational.** All three providers can constrain
output to a JSON Schema. The schema is the neutral contract; the provider is an
implementation detail behind `LLMClient`.

---

## 3. The Slide IR — and how the corpus reshaped it ✅

The full annotated schema is `src/aippt/ir/schema.json`; the typed mirror is
`src/aippt/ir/models.py`. This section explains *why* it has the shape it has.

### The corpus is the spec

The block taxonomy was not designed in the abstract. It was **counted**, directly, out of
the three existing decks:

| Construct | Occurrences | What it forced |
|---|---:|---|
| `<section class="card">` | **30** | one card = one slide; the whole IR hangs off this |
| `<h2>` | **30** | exactly one title per card — an invariant, not a convention |
| inline `<code>` | **111** | `rich_text` runs are **mandatory** |
| `<h3>` | 28 | `heading` is a first-class block |
| `<ul>` | 22 | `bullets`, with levels |
| `<table>` | 11 | `table` — and this is the block most likely to overflow |
| `.step-badge` | 10 | `steps` |
| `.mini-card` | 9 | `cards` (in `.grid-2` / `.grid-3`) |
| `.tag` | 8 | a field on `cards` |
| `<svg>` | 7 | hand-drawn diagrams — the mermaid path will **not** catch these |
| `.alert-box` | 4 | `callout`, variant `info` |
| base64 `<img>` | **3** | all `image/jpeg` |
| `.mermaid` | 3 | `diagram` |
| `.warn-box` | 2 | `callout`, variant `warn` |
| `<pre>` | 2 | `code` |
| `.ok-box` | 1 | `callout`, variant `ok` |
| `.tabs` | 1 | `code.variants[]` — a tabbed C++/C# pair |

### Four things the corpus contradicted

The brief that scoped this work described the taxonomy from memory. Reading the actual
files corrected it in four ways, each of which changed the schema:

1. **Callouts have three variants, not one.** `.alert-box`, `.warn-box`, `.ok-box`. A
   single `callout` block with a `variant` discriminator, since they differ only in accent
   colour.
2. **The embedded images are JPEG, not PNG.** Harmless for `add_picture` (it sniffs the
   header), but the data-URI parser must not hard-code `image/png`.
3. **`.tabs` exists and nothing in the brief mentioned it.** Slide Template.html slide 4 is
   a tabbed C++/C# code pair. PowerPoint has no tab control, so `code` carries a
   `variants[]` array and the *renderer* decides how to realise it — side-by-side, or two
   slides. Content decision, not a styling one, hence it lives in the IR.
4. **Inline `<code>` is the dominant inline mark — 111 of them.** This is the finding with
   the largest downstream consequence. It rules out the tempting simplification of
   modelling text as plain strings: a deck of API documentation that renders
   `VEO_Focus_Initialize()` as ordinary body prose looks broken to exactly the audience
   these decks are for. Hence `rich_text` with run-level styling.

`rich_text` accepts **either** a bare string **or** a run array. That is a concession to
the LLM, and a deliberate one: asking a model to emit `[{"t": "hello"}]` when it means
`"hello"` is a reliable generator of malformed output. `models.py` normalises the string
form inward, so the renderer only ever sees runs.

### What the IR deliberately refuses to model

- **`sim-*` interactive panels** (sliders, control panels — 3D Logic deck). There is no
  static representation of an interactive simulator. The adapter must emit a **lossy
  warning**, not silently drop it. A slide whose entire point was the simulator becoming a
  blank slide, quietly, is the failure mode we are guarding against.
- **`<svg>` hand-drawn diagrams** (7 of them). Not mermaid, so `diagrams.py` cannot parse
  them. They must be rasterised or re-authored. Also a lossy warning.
- **Geometry, colour, fonts, sizes.** There is nowhere in the schema to put them. That is
  the invariant, expressed as a data structure.

---

## 4. Master and layout handling

### ❌ The actual inventory — NOT AVAILABLE

**This is the hole in this document.** The PoC never ran (see the top of this file), so the
following are all unknown:

- slide size (EMU / inches / aspect ratio) — ❌
- number of masters — ❌
- number of layouts, and their **names** (the legal `layout_id` values) — ❌
- every placeholder's `idx`, type, and box geometry — ❌
- the theme's font scheme, in particular the **East-Asian (`ea`) face** — this template is
  Korean, and the `ea` typeface is the one that will actually be used for most of the text — ❌
- **where `#DB0032` lives** — ❌ and this one has teeth. Two possibilities, and they demand
  different renderer code:
  - *In the theme's colour scheme* (e.g. `accent1`) → the renderer references
    `MSO_THEME_COLOR.ACCENT_1` and the brand is inherited automatically. A future rebrand
    is a one-file change.
  - *Hard-coded in the master XML* → the renderer must use a literal
    `RGBColor(0xDB, 0x00, 0x32)` and the brand is now duplicated in our code.

  `analyze_pptx_master.py` checks both and prints the answer as
  `brand_accent.resolution`. **Read that line first.**

**To fill this section in:**

```bash
pip install -e .
python -m aippt.analyze_pptx_master
```

and paste the stdout summary here, replacing this block.

> ```
> ┌──────────────────────────────────────────────────────────────────┐
> │  PASTE THE REAL analyze_pptx_master.py OUTPUT HERE.              │
> │  Until then, every ❌ above is an open question and the AI path   │
> │  cannot be run at all — there is no layout catalog to inject.    │
> └──────────────────────────────────────────────────────────────────┘
> ```

### 📖 python-pptx gotchas the renderer must absorb

These are documented library behaviours. They are not speculative, and each has already
been written into `renderer.py`'s contract.

**1. `add_slide()` must use the template's own layouts.**
```python
prs = Presentation("Vieworks_R&D_ppt_Template.pptx")
layout = prs.slide_layouts[N]          # the TEMPLATE's layout
slide = prs.slides.add_slide(layout)   # inherits master, theme, fonts, brand
```

**2. `prs.slide_layouts` only exposes the *first* master's layouts.** If the template has
more than one master, layouts on masters 2+ are invisible through that property. Iterate
`prs.slide_masters[i].slide_layouts` instead. `resolve_layout()` searches all masters for
exactly this reason.

**3. Unused placeholders still render.** A layout placeholder that is never filled shows
its prompt text ("Click to add text") to anyone who opens the deck to edit it. Every
placeholder a slide does not use must be explicitly removed:
```python
ph._element.getparent().remove(ph._element)
```
Exempt `FOOTER`, `SLIDE_NUMBER` and `DATE` — those are template furniture and are supposed
to stay.

**4. There is no `slides.remove()`.** To strip the template's own example slides you must
drop the relationship *and* unlink the `sldIdLst` entry — both, in that order. Doing only
the second leaves an orphaned relationship and PowerPoint declares the file corrupt.

**5. Placeholder geometry may be `None` on the layout**, inherited from the master.
python-pptx surfaces the `None` rather than resolving it. The analyzer resolves it against
the master and records `geometry_inherited_from_master`; downstream code reads the manifest
and never re-derives this.

**6. No SmartArt.** No API, and the `diagramData` part is undocumented and regenerated by
PowerPoint on open. Permanently ruled out. See §7.

**7. No autofit.** Big enough to be its own section. See §5.

**8. `text_frame.text = "..."` destroys run formatting.** It collapses the frame to a
single unstyled run. Since 111 inline `<code>` spans depend on run formatting, the renderer
must build paragraphs and runs explicitly, never assign `.text` on a frame that needs
styling.

---

## 5. Text overflow — the #1 design risk

**This is the thing most likely to sink the project, and it deserves to be read twice.**

### The mechanism

PowerPoint's "shrink text on overflow" is not a *result* stored in the file. It is an
*instruction* — `<a:normAutofit fontScale="..."/>` — that PowerPoint's layout engine
evaluates when it opens the document.

python-pptx can write the instruction. It **cannot evaluate it**. It has no font metrics,
no line breaker, and no layout engine. So:

```python
tf.word_wrap = True
tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE   # sets a flag. Fits nothing.
```

Overflowing text does not raise, does not warn, and is not visible in the XML. It simply
renders **off the bottom edge of the slide**. 📖

The consequence is stark: **every deck this project generates is one verbose LLM sentence
away from a broken slide, and nothing in the stack will tell you.** An LLM writing to a
length that reads well in chat will overflow a 4-inch box essentially every time.

### The Korean multiplier ✅

The corpus is Korean. A Hangul syllable is a **full-width** glyph — roughly **twice** the
advance width of a proportional Latin character. A width model built on Latin metrics
underestimates a Korean line by about 2×.

That single oversight would make every number in the layout catalog wrong, in the dangerous
direction, for most of the actual content. So the budget model carries **two** character
counts (`chars_per_line_latin`, `chars_per_line_cjk`), the prompt states both, and mixed
text is budgeted against the CJK figure. Wrapping differs too: Latin wraps at spaces,
Korean wraps at **any character** — there are no spaces inside a Hangul clause.

### The three-layer defence

**Layer 1 — PREVENT.** The only layer that scales. Inject the per-placeholder content
budget into the author prompt: *"max 6 bullets × 9 words; title ≤ 42 Korean characters."*
A model told a concrete number mostly complies. This is why `analyze_pptx_master.py`
computes content budgets at all — they exist to be put in a prompt, not to be admired.

**Layer 2 — MEASURE and DEGRADE** (`render/fit.py`). Before writing, estimate the rendered
height. If it exceeds the box, degrade in a fixed order:

1. fits → write it;
2. **shrink** (≤3 steps of 2pt, floor 12pt body / 20pt title — below that it is unreadable
   from the back of a room, and a legible slide with less on it beats a full slide nobody
   can read);
3. **tighten** paragraph spacing (buys about one line);
4. **split** onto a continuation slide — the *correct* answer for genuinely long content,
   and what a human would do;
5. **truncate** — last resort, recorded as a defect, never silent.

Explicitly **not** in the ladder: asking an LLM to shorten the text here. That is layer 1's
job, upstream, where the model still has the source material and the intent. Doing it at
render time — with only the rendered string in hand — produces a summary of a summary, and
it reads like one.

**Layer 3 — VERIFY.** Layers 1 and 2 both rest on an *estimate* (`LATIN_CHAR_WIDTH_RATIO
= 0.52` is a decent guess, not a measurement). The only ground truth is a render: PPTX →
LibreOffice → PDF → PNG → check for ink where ink should not be. This is the authoritative
check and the only thing that will ever catch a bad font-metric assumption. See §9.

The honest summary: layers 1 and 2 are heuristics, and they will be wrong sometimes. Layer
3 is why that is survivable.

---

## 6. Images ✅

Three in the corpus, all `image/jpeg` data-URIs (**not** PNG — verified), nested inside
`.photo-desc` → `.photo-placeholder` → `.photo-grid`. That nesting is why the adapter uses
BeautifulSoup and not a regex.

```python
header, b64 = data_uri.split(",", 1)     # 'data:image/jpeg;base64'
blob = base64.b64decode(b64)
pic = slide.shapes.add_picture(io.BytesIO(blob), left, top, width=w)
```

`add_picture` accepts any file-like object and sniffs the format from the header, so JPEG
vs PNG needs no branching.

**Aspect-fit, never stretch.** This is the part that goes wrong:

> Passing **both** `width` and `height` to `add_picture` **distorts the image.**

Pass one, let python-pptx derive the other from the intrinsic size, then centre it:

```python
box_ar = box_w / box_h
img_ar = pic.image.size[0] / pic.image.size[1]      # needs Pillow
# img wider than box -> constrain width;  taller -> constrain height
```

`pic.image.size` requires **Pillow**. Without it python-pptx will still place the picture
but cannot read its intrinsic dimensions, so aspect-fit degrades silently into stretch —
and stretched photographs of hardware and people look *wrong* in a way everyone notices and
nobody can immediately name. That is why Pillow is a hard dependency, not an optional one.

**Size.** A 619 KB HTML file is ~600 KB of base64, and the IR keeps the data URI verbatim,
so the IR is large but still a single self-contained text file — no sidecar asset directory
to keep in sync, which matters because the IR is passed to an LLM and round-tripped through
a QA loop. If it ever becomes a problem, `source.kind` already supports `"path"` and
nothing else has to change.

---

## 7. Diagrams — a hybrid, and why neither pure option wins

The corpus has 3 `.mermaid` blocks (1 `sequenceDiagram`, 2 flowcharts) and 7 `<svg>`
elements. Small in count, but diagrams carry the highest information density per slide in
the whole corpus — these are architecture decks, and the architecture *is* the diagram.

**SmartArt is out.** No python-pptx API; the `diagramData` part is undocumented,
version-sensitive, and regenerated by PowerPoint on open. Hand-writing it is not a shortcut,
it is a permanent maintenance liability. 📖

The two viable options fail in *different* ways, which is exactly why the answer is neither:

| | Native autoshapes | Rasterised (mermaid-cli → PNG) |
|---|---|---|
| Editable | ✅ | ❌ flat image |
| On-brand (theme colours) | ✅ | ❌ mermaid's palette |
| Crisp when resized | ✅ vector | ❌ goes soft |
| Handles arbitrary graphs | ❌ needs a layout engine | ✅ |
| External dependency | none | Node + `mmdc` |

### Recommendation: decide per diagram, by complexity

- **≤ 8 nodes, ≤ 10 edges, acyclic → native.** Layered (Sugiyama-lite) layout, rounded
  rectangles, elbow connectors bound to the shapes with `begin_connect`/`end_connect` so
  they stay attached when a human drags a box. That reattachment is most of the value of
  going native at all.
- **Anything else → rasterise.** And this is honest, not a cop-out: an unreadable native
  approximation of a 20-node graph is strictly worse than a clean picture of it.
- **Parse failure → rasterise.** `parse_mermaid` handles the subset the corpus actually
  uses and raises `UnsupportedDiagram` on anything else. It must never *half*-parse: a
  partially-understood diagram renders as a **wrong** diagram, and a wrong architecture
  diagram in an engineering deck is a real cost — worse than an honest fallback.
- **Author override.** `render_hint: native | image | auto` in the IR. The person who wrote
  the diagram knows things a node count does not.

The corpus's own diagrams are 4–7 nodes and one 3-participant sequence diagram — so in
practice **most of them go native**, and the raster path is the safety net rather than the
default.

---

## 8. Prompt engineering for decks

Four decisions, in `prompts/`.

**The invariant is stated first, and as a rule about the model's job**, not a formatting
preference: *"You produce structured content. You never produce design."* It is also
enforced structurally — the schema has nowhere to put a coordinate — but a model that
understands *why* complies more consistently than one merely blocked from misbehaving.

**Budgets are injected, and framed as physics.** The catalog goes into the system prompt
verbatim, carrying the legal `layout_id` values and the per-placeholder budgets. The prompt
tells the model *why* the ceiling is hard: **there is no autofit; text that overflows is
silently lost.** And it asks for **80% of budget**, because bold runs, inline code and wide
punctuation all eat width the estimate does not model.

**Two stages, because one call cannot do both jobs.** A single call that must hold the
deck's narrative arc *and* respect 30 per-placeholder character budgets does neither well —
it drifts on structure and overflows on length.

- Stage 1 (`10_outline_storyboard.md`): topic + sources → storyboard. Decides *the story*
  and picks the layouts, at deck level, where the model can see the whole shape and avoid
  emitting nine consecutive bullet slides.
- Stage 2 (`20_slide_fill.md`): one outline entry → one slide's IR. Runs per-slide, in
  parallel, and is injected with **only that layout's budget** — narrowing the context
  measurably improves adherence, because the model is no longer choosing a layout, it is
  filling a box whose exact dimensions it has just been told.

**Structured output, not free-text-then-parse.** "Return JSON" yields JSON *most* of the
time, and the failures are the expensive kind — a stray markdown fence, a trailing comma, a
hallucinated field. All three providers can constrain output to a schema natively (Claude:
tool use with `input_schema` + forced `tool_choice`; OpenAI: Structured Outputs with
`strict: true`; Gemini: `response_schema`). Use it, and get a hard guarantee instead of a
soft one.

Two provider caveats that *will* bite, documented in `ai_adapter.py`: OpenAI's `strict`
mode rejects `oneOf`, `default` and `format: uri`, and Gemini accepts only an OpenAPI-3
subset with no `$ref`. Both need a **derived** variant of the schema, generated by a tested
transform — never a second hand-maintained copy, which will drift from the canonical one and
do so invisibly.

**Repairs are bounded and specific.** On validation failure, re-prompt once with the exact
error — `slides[3].blocks[1].rows[2]: row has 3 cells but the table declares 4 columns`.
A precise, machine-generated message repairs on the first retry the overwhelming majority
of the time; "invalid JSON" does not. After `max_repairs`, **fail loud**. Never silently
drop a slide: an 11-slide deck that was asked for 12 is a defect nobody will notice.

---

## 9. The quality loop

```
deck.pptx ─> soffice --headless --convert-to pdf ─> pdftoppm -png ─> slide-NN.png
                                                                          │
                          ┌───────────────────────────────────────────────┤
                          ▼                                               ▼
              deterministic geometry checks                    vision critique
              (fit.detect_overflow_in_png)                     (30_visual_qa.md)
                          │                                               │
                          └──────────────► verdict ◄──────────────────────┘
                                    pass / fix / regenerate
```

**Note:** LibreOffice's `--convert-to png` renders only the *first* slide. Go via PDF.

**The division of labour is the point.** Geometry is checked with **arithmetic**: ink near
a slide edge, an ink bounding box taller than its declared placeholder, two placeholders'
ink overlapping. A vision model will confidently miss a 3-pixel overhang; arithmetic will
not. The vision model is then asked only to judge what arithmetic cannot name — legibility
at projection distance, density, whether a diagram's edge labels have collapsed into each
other, whether an image is subtly stretched.

Three verdicts, with sharply different costs:

- **`pass`** — ships. Minor defects still pass; perfection is not the bar.
- **`fix`** — deterministic repair (shrink / split / re-fit). No model call. `fit.py` does it.
- **`regenerate`** — the *content* is wrong: too much of it, or the wrong block type. This
  is the only verdict that costs another generation call, so the prompt reserves it.

The critic is explicitly instructed that **when in doubt, pass** — a false positive costs a
pointless regeneration cycle, and a critic that flags everything is indistinguishable from
one that flags nothing.

---

## 10. Roadmap

| Phase | Scope | Gate |
|---|---|---|
| **0 — Ground truth** | Run `analyze_pptx_master.py`. Fill in §4. | `layout_manifest.json` has real data |
| **1 — HTML → IR → PPTX** | `html_adapter` + `renderer` + `fit`. **No AI.** | All 30 corpus slides round-trip; `ConversionReport.lossy` is empty except for the known `sim-*` / `<svg>` cases |
| **2 — AI author** | `ai_adapter`, both prompt stages, structured output, bounded retry | A deck generated from a topic opens in PowerPoint, is on-brand, and nothing overflows |
| **3 — Visual QA loop** | Render → PNG → geometry checks → vision critique → repair | The loop converges without a human |

**Phase 1 has no AI in it, on purpose.** It is the highest-value phase and the cheapest to
debug. If a deck we *already have* cannot survive the round trip, no amount of prompt
engineering will save the AI path. And a Phase 1 failure is debuggable in a way that "the
model wrote something odd" never is.

It also produces something immediately useful on its own: a converter for 30 slides of
existing content that currently cannot be handed to anyone in PowerPoint form.

---

## 11. Open questions and risks

### Blocking

**R1. The PoC has never run.** ❌ Nothing about the template is confirmed, and — worse —
the analyzer has never had a Python interpreter look at it, so it may not even import.
Expect to fix a bug or two. *Mitigation: run it. It is two seconds and one command.*

**R2. Where does `#DB0032` live?** ❌ Theme slot or hard-coded in the master? Changes what
the renderer does for every inline `code` run, every callout, and every native diagram
node. `analyze_pptx_master.py` answers this directly. *Read `brand_accent.resolution` first.*

**R3. Does the template have usable layouts at all?** ❌ A corporate template with only
"Title" and "Blank" would break the layout-driven design and force a fallback to
free-floating shapes on a blank layout — losing most of the master's benefit. Unlikely,
but it is the assumption the whole architecture rests on, and it is unverified.

### Structural

**R4. Text overflow.** The #1 risk. See §5. Mitigated in three layers, none of which is
airtight on its own.

**R5. The font-metric model is a guess.** `LATIN_CHAR_WIDTH_RATIO = 0.52` is a reasonable
constant, not a measurement of the template's actual typeface. The 10% safety margin is a
cushion, not a proof. *Mitigation: layer 3 (render → PNG) is the ground truth; calibrate
the constants against a real render once and revisit.*

**R6. `analyze_pptx_master.py` and `fit.py` must agree.** If the two width models diverge,
the budget the LLM is given stops matching the budget the renderer enforces, and layer 1
silently stops working. *Mitigation: `fit.py` imports the constants from the analyzer rather
than restating them. Do not "clean this up" by re-declaring them.*

**R7. HTML → layout mapping is invented, not derived.** The HTML has no notion of a
PowerPoint layout, so `choose_layout()` guesses from content shape. It will get some slides
wrong. *Mitigation: rule-based and inspectable; `ConversionReport` surfaces every decision;
tune against the 30-slide corpus, which is exactly what a corpus is for.*

**R8. Lossy constructs.** `sim-*` interactive panels and the 7 hand-drawn `<svg>` diagrams
have no faithful PPTX representation. *Mitigation: warn loudly, never drop silently. A
slide that renders beautifully having quietly lost its only diagram is worse than a loud
failure.*

### Open questions

- **Does the deck ship the template's example slides?** `strip_existing=True` by default —
  they are the template's *examples*, not our content — but this should be confirmed with
  whoever owns the template.
- **What is the review workflow?** A generated deck is a draft. Who approves it, and does
  the QA loop's verdict gate anything, or merely advise?
- **Speaker notes.** The IR carries them and they are free of any budget. Should the AI
  author populate them by default? Argument for: it is the natural home for the nuance that
  had to be cut from the slide, and it costs little. *Recommendation: yes, by default.*
- **Which model for which stage?** The outline stage rewards reasoning about narrative arc;
  the fill stage rewards instruction-following against a hard budget. They may not want the
  same model. Worth measuring rather than assuming.
