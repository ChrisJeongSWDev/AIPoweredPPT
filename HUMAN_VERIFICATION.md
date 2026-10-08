# Phase 0 — Human Verification

Phase 0 is **blocking**: nothing in Phase 1 starts until every box below is ticked. The machine
can prove the transform; it cannot prove the render. That is the whole point of this file
(critic rule 12 — *do not claim WYSIWYG from coordinate equality alone*).

> ## ⚠ Nothing here has been run yet
>
> The Phase 0 code was written in an environment where Python execution was not available, so
> **every gate below — including the automated ones — is un-run**. `reference/renderer_template.pptx`
> **does not exist yet**, and `reference/template_pin.json` is deliberately **unpinned**
> (`sha256` is still the placeholder), so `pin.py` currently fails closed by design.
>
> Run step 0 first. If it fails, the rest of this checklist is moot.

---

## 0. Build and pin (do this first)

```bash
cd tasks/AI_Powered_PPT
python src/aippt/tools/make_renderer_template.py --write-pin
```

Close PowerPoint first — the builder warns if `~$Vieworks_R&D_ppt_Template.pptx` (an Office lock
file) is present, which means the template is probably open.

This builds `reference/renderer_template.pptx` and rewrites `reference/template_pin.json` from
the **observed** package. It refuses to write anything if the source template's SHA has changed,
if slides survived deletion, if layout 3 is not `/ppt/slideLayouts/slideLayout4.xml`, if the
divider/logo media are gone, or if the package has dangling relationships.

- [ ] The builder exits 0 and prints an observed `layout_signature`.
- [ ] `reference/template_pin.json` now has a real `renderer_template.sha256` (not the placeholder).
- [ ] `python src/aippt/canvas/pin.py` prints `pin OK: ...`.
- [ ] `reference/renderer_template.pptx` is committed. (Rebuilds are **not** byte-reproducible —
      ZIP entries carry timestamps — so we pin the committed artifact, not a rebuild. Re-pinning
      is a deliberate, reviewed act: plan §4.3.)

### Already machine-checked by the builder (§2.3 gates 1–4, 6)

You do not need to re-check these by hand; you only need the builder to have exited 0.

| Gate | Check |
|---|---|
| 1 | `len(prs.slides) == 0` |
| 2 | 5 layouts; layout 3 is `2_사용자 지정 레이아웃` → `/ppt/slideLayouts/slideLayout4.xml` |
| 3 | `image5.jpeg` + `image2.svg` present **and** related to slideLayout4 |
| 4 | No surviving `ppt/slides/` or `ppt/notesSlides/` parts; no dangling relationships |
| 6 | `add_slide(layout 3)` → save → reopen → exactly 1 slide, relating to slideLayout4, carrying placeholder idx 10 |

---

## 1. PowerPoint opens it clean

Open `reference/renderer_template.pptx` in **real PowerPoint** (not a viewer, not LibreOffice).

- [ ] It opens with **no repair dialog** and no "PowerPoint found a problem with content" warning.
- [ ] The deck is **empty** — zero slides in the thumbnail pane.
- [ ] The 5 layouts are all present under *View → Slide Master*, and layout 3
      (`2_사용자 지정 레이아웃`) still shows its gradient divider, logo and page-number chrome.

> A repair dialog here means the slide-deletion step left the package inconsistent. Do not "let
> PowerPoint fix it" and re-save — that silently rewrites the package and invalidates the pin.
> Report it instead.

---

## 2. Page number on an added layout-3 slide reads "1"

The builder proves the new slide is the **only** slide, at index 0. It cannot prove what the
page-number *field* renders as, because that glyph is produced by PowerPoint, not by python-pptx.
That is this check.

```bash
python src/aippt/tools/calibrate.py      # -> reference/calibration.pptx
```

Open `reference/calibration.pptx` in PowerPoint.

- [ ] The deck has **exactly one slide**.
- [ ] The page-number chrome in the bottom-right reads **1** — **not 24**.

> 24 means the 23 template slides were not actually removed and you are looking at an append, not
> a clean render. Stop; the pin is wrong.

---

## 3. The SVG logo survives the conversion path

**This is the single most likely inheritance surprise** (plan §7.1, assertion 5), and it is the
reason this check is a gate rather than a footnote. An SVG in OOXML carries a **raster fallback**
alongside it via the `svgBlip` extension. Converters vary in which of the two they honour — and
the fallback may be a low-resolution PNG that looks fine at thumbnail size and mushy at full size.

Render `reference/calibration.pptx` through **the actual consumer you will ship** (PowerPoint,
and the LibreOffice → PNG/PDF path if that is what the server uses):

- [ ] The Vieworks logo (red wordmark, top-right) is **present**.
- [ ] It is **sharp**, not a blurry raster upscale — i.e. the SVG was honoured, not the fallback.
- [ ] It is **undistorted** — correct aspect ratio, not stretched.
- [ ] The gradient divider (the full-width band under the title) is present and undistorted.

> If the logo degrades only in the LibreOffice path, that is a **finding, not a failure** — record
> which renderer honoured which, and decide before Phase 1 closes. Do not assume; test.

---

## 4. Raster diff ≤ 2 px

The measured error bar for the coordinate mapping (plan §7.2, §7.5). This is the number that
Phase 0 exists to produce.

1. Export `reference/calibration.pptx` → PNG at **960 × 540** via the actual target consumer.
2. Screenshot the HTML stage at **zoom 1** (Phase 1B; if the editor does not exist yet, this step
   is deferred — say so explicitly rather than ticking it).
3. Diff the two.

- [ ] Every shape edge is within **≤ 2 px** of the HTML stage screenshot.
- [ ] **Corners:** all four corner rectangles touch the exact slide corners — no 1-px inset or
      overhang, which would mean an origin off-by-one.
- [ ] **Strokes:** the 0 / 1 / 4 / 8 ladder — the shapes' **outer** edges must not drift as the
      stroke thickens. (Drift here is box-model mismatch: PowerPoint centres the stroke on the
      path; CSS `border` grows outward unless `box-sizing: border-box`.) Note that stroke width 0
      is a **hairline** in PowerPoint, not "no line" — the browser draws nothing. Record the
      difference; do not treat it as a bug to be papered over.
- [ ] **Rotation:** the 30° and 45° shapes rotate about their **centres**, matching the browser's
      `transform-origin: center`.
- [ ] **Wrap:** the `wrap_14pt` box has the **same number of lines** in the render as in the
      browser, and no text overflows the box **in the rendered output** (not in the browser —
      the browser is a preview, not a proof).
- [ ] **Mixed KO/EN:** in `mixed_ko_en`, the Latin runs are **Century Gothic** and the Hangul runs
      are **맑은 고딕**. If the Hangul renders in a serif or a default face, the `<a:ea>` split did
      not take.
- [ ] **No Office blue:** `#4472C4` appears nowhere. (`calibrate.py` also asserts this against the
      slide XML, but look anyway — a drop shadow is the tell that `shadow.inherit = False` was
      missed.)

**Record the measured number**, even when it passes. "≤ 2 px" is the gate; the actual figure is
the thing Phase 1 gets to rely on.

    Measured max edge error: ______ px   (consumer: ______________, date: __________)

---

## Open decisions this checklist will surface (plan §10, D-1)

Neither blocks Phase 0, but both get cheaper to change now than later:

- [ ] **Century Gothic is not the Vieworks brand font.** The template's real design fonts are
      **뷰웍스 B / 뷰웍스 M**, set at run level on every exemplar slide. Century Gothic body text
      will sit next to inherited 뷰웍스 chrome and look subtly off-brand. Ship it (the user asked
      for it) — but decide it, do not discover it. It is one constant in `calibrate.py` today and
      one constant in `style.py` tomorrow.
- [ ] **Century Gothic may not be installed on the opening machine.** PowerPoint substitutes and
      the geometry shifts. `python-pptx` cannot embed fonts. Invisible until someone else opens
      the deck.
