# Codex Critic Review — HTML Visual Editor to PPTX Plan

**VERDICT: REVISE.** The proposed architecture is sound, and the prior Q3 block on `add_slide()` can be lifted for this narrowly defined path: create a blank slide from Layout 3, retain only its inherited chrome, fill placeholder idx 10, and draw new content at absolute coordinates. However, `plan_review.md` should not be accepted unchanged. It reverses the identities of the two layout assets, misses a critical 23-existing-slide problem, and understates several preview/export fidelity risks.

## 1. Layout chrome reliance versus slide cloning

### Direct package finding

For the current template SHA-256 `0de7d70cf45197e959d93c31eedd7599c42c23c1153d7b67b18d332141e61442`, zero-based `prs.slide_layouts[3]` maps to `ppt/slideLayouts/slideLayout4.xml`. Its layout shape tree directly contains:

| Layout element | Actual role | Geometry in points | Relationship |
|---|---|---:|---|
| `그림 3` (`p:pic`, shape id 4) | Full-width gradient divider image | x 0.31, y 60.67, w 959.39, h 27.91 | `rId2` → `ppt/media/image5.jpeg` |
| `그래픽 8` (`p:pic`, shape id 9) | Vieworks SVG logo | x 816.76, y 64.00, w 97.14, h 11.92 | SVG extension `rId3` → `ppt/media/image2.svg` |
| `텍스트 개체 틀 2` | BODY placeholder idx 10 used as the title | x 45.55, y 26.75, w 725.29, h 37.25 | layout placeholder |
| `슬라이드 번호 개체 틀 5` | Slide-number field/chrome | x 733.61, y 507.72, w 216.00, h 28.75 | regular layout shape |

This corrects `plan_review.md`: **`그림 3` is the divider and `그래픽 8` is the logo, not the reverse.** The SVG content itself is the red Vieworks wordmark. The JPEG is 2934×85 and contains the visible gradient band. A pixel audit maps its visible non-white region to approximately x 46.41–788.68 pt and y 68.88–75.12 pt; its visual center is y 72.00 pt. The divider geometry was therefore not actually missing, although the JPEG's white padding makes the outer picture box an inaccurate proxy for the visible line.

The exemplar slides using this layout do not contain duplicate slide-level copies of these two assets. Their slide-level shape trees contain their own freeform content plus the cloned idx-10 placeholder; the logo and divider are inherited from the layout. This is materially different from the exemplar compositions discussed in the Q3 review.

### `add_slide()` behavior

`python-pptx` implements `Slides.add_slide()` by creating a slide related to the selected layout and cloning the layout's eligible placeholders. BODY placeholders are cloneable; only date, footer, and slide-number placeholders are excluded. Consequently, idx 10 should be available as `slide.placeholders[10]`, while the logo/divider remain layout-level shapes rather than copies in `slide.shapes`. See the official [`pptx.slide` source](https://python-pptx.readthedocs.io/en/latest/_modules/pptx/slide.html) and [placeholder inheritance explanation](https://github.com/scanny/python-pptx/blob/master/docs/user/placeholders-understanding.rst).

Using `add_slide(layout_3)` therefore brings in the chrome at its native layout coordinates without rescaling or geometric distortion, provided the slide is added to this same template package and master-graphics inheritance is not disabled. Slide cloning is unnecessary for this path.

The old Q3 block is still valid for a different claim: `add_slide(layout_3)` does **not** reproduce any exemplar slide's freeform diagram, table, or card composition. It is safe only because this new plan deliberately draws its own body content.

### Required reliability checks

The final plan must require a smoke test that adds one slide, saves, reopens, and renders it in the target PowerPoint/conversion environment. Assert that:

1. the new slide still relates to `slideLayout4.xml`;
2. the layout still relates to both `image5.jpeg` and `image2.svg`;
3. placeholder idx 10 exists and can be filled;
4. the logo and divider are visible and undistorted in the rendered output; and
5. the SVG logo survives any LibreOffice or server-side conversion path actually used.

## 2. Missing findings and corrections

### Critical — the source template already contains 23 slides

`Presentation("Vieworks_R&D_ppt_Template.pptx")` followed by `add_slide()` appends a 24th slide. It does not produce a one-slide export. This would ship all exemplar slides and make the inherited page number wrong. The public `Slides` API exposes addition but no supported deletion operation.

The backend must use a separately verified **clean renderer template** that retains the master/layout/media parts but contains no exemplar slides, or define and test a deterministic package-preparation step before renderer development. Do not make private slide-deletion code part of each export request. Never overwrite the source template.

### Critical — layout selection must fail closed

Hard-coding layout index `3` is acceptable only while the template hash is pinned. The JSON/backend contract should include the expected template or manifest version, and startup should verify the SHA plus a layout signature: idx 10, slide size 12192000×6858000 EMU, and the two required layout media relationships. A changed or reordered template must fail with a clear error rather than silently selecting a different layout.

### High — inherited chrome is invisible to `slide.shapes` and always behind slide content

Collision checks that inspect only `slide.shapes` will not see the logo, divider, or page-number chrome. New slide-level shapes can cover them, and layout shapes cannot simply be brought above slide content. Maintain explicit locked/protected regions in the canvas manifest. At minimum, keep user elements below the header boundary and away from the footer/page-number region.

The editor's red boundary must remain editor-only CSS/SVG chrome and must not be serializable as a content element. Based on the current asset, a reasonable Phase-1 assumption is a thin `#FF0032` line from about x 46.4 to 788.7 at y 72.0 logical units. Record that as an approximation of the gradient's visible center, not as the divider picture's outer box.

### High — title access and styling must be explicit

Layout 3 has no semantic TITLE placeholder, so `slide.shapes.title` remains `None`. Use `slide.placeholders[10]` by placeholder idx, not by collection position. After assigning text, explicitly set all title run/paragraph formatting required by the product; do not assume the BODY placeholder's inherited style equals the editor's Century Gothic default.

### High — 960×540 is exact, but the browser contract is not yet complete

The factor `1 logical unit = 1 pt = 12,700 EMU` is exact for this 12192000×6858000 EMU slide. Preserve that benefit, but add these rules:

- Store and serialize only 960×540 logical coordinates. DOM client pixels, responsive widths, zoomed `getBoundingClientRect()` values, and `devicePixelRatio` must never enter the IR. Pointer coordinates must be transformed back through the single stage scale.
- Define `x/y/w/h` as the shape's unrotated outer geometry. Use center-origin rotation in both HTML and PowerPoint.
- Define whether stroke is included in `w/h`. CSS `box-sizing`, inward CSS borders, and PowerPoint's centered line stroke otherwise produce visible edge drift. Include stroke-width cases in the calibration slide.
- Clamp all geometry to the slide and protected regions, reject non-positive dimensions, and round only at the final `logical × 12700` conversion.

### High — browser text is a preview, not proof of PowerPoint fit

The visual editor reduces text-overflow risk but does not eliminate it. Browser and PowerPoint can differ in font fallback, kerning, line breaking, paragraph spacing, and vertical metrics. The renderer and CSS must explicitly align:

- left/right/top/bottom margins;
- word wrap and no-auto-resize behavior;
- horizontal and vertical alignment;
- paragraph `space_before`, `space_after`, and line spacing/line-height;
- font family, size, weight, and mixed Korean/Latin fallback; and
- normalization of `contenteditable` markup (`div`, `br`, non-breaking spaces) into explicit paragraphs, breaks, and runs.

Century Gothic should be treated as the Latin default. Use an explicit installed Hangul fallback in both CSS and DrawingML (`a:ea`), and detect/warn when Century Gothic is unavailable in the browser or export environment. `python-pptx`'s public `Font.name` does not by itself establish the East-Asian font.

`plan_review.md` also says "there is no autofit" too absolutely. [`TextFrame.fit_text()` exists](https://python-pptx.readthedocs.io/en/latest/api/text.html), but it is not a PowerPoint rendering engine and is a poor foundation for mixed-font CJK fidelity. The plan should say **no guaranteed headless PowerPoint-equivalent autofit** and keep deterministic render QA as the authority.

The claim that XML-illegal controls necessarily corrupt output is also overstated for `python-pptx` 1.0.x: its text API escapes unsupported control characters. Input sanitization is still sensible for interoperability, but it should be described as a validation policy, not as an inevitable corruption fix.

### Medium — shape and connector defaults must never leak through

The previous analysis correctly identified theme-blue fills/effects. The implementation rules should require every generated shape to set fill, line fill/color/width, shadow/effects, text color, fonts, margins, wrapping, and alignment explicitly. Use opaque `#RRGGBB` in Phase 1 unless transparency semantics are separately specified. New content defaults to `#FF0032`; inherited template chrome keeps its native branding.

Flowcharts also need a connector/arrow primitive. Decide it in the Phase-1 schema rather than after the toolbar is built. If included, define endpoints in logical units, render connectors behind nodes, add arrowheads explicitly in DrawingML, and treat shape gluing as optional/tested behavior. `begin_connect()`/`end_connect()` are experimental and should not be assumed reliable for arbitrary triangles or connection-site indices. Save, reopen, and render every connector fixture.

## 3. Rules the main worker should carry into the final plan

1. **Adopt Layout 3 chrome; do not clone exemplar slides** for the visual-editor path.
2. **Correct the asset map:** `그림 3`/`image5.jpeg` is the divider; `그래픽 8`/`image2.svg` is the logo.
3. **Create and verify a clean renderer template before feature work** so exports do not include the 23 exemplars.
4. **Pin the template SHA and layout signature** and fail closed on any mismatch.
5. **Fill BODY placeholder idx 10 directly**; never use `slide.shapes.title` for this layout.
6. **Keep editor chrome out of Canvas IR** and lock header/footer exclusion zones.
7. **Keep the 960×540 logical model**, with a single exact 12,700-EMU conversion and explicit zoom inversion.
8. **Specify border, rotation, text-margin, paragraph, fallback-font, and contenteditable normalization semantics** before implementing serialization.
9. **Make all PPTX styling explicit**, including removing inherited Office effects and setting both Latin and East-Asian fonts.
10. **Add a connector schema/tool or explicitly declare arrows out of scope.** Do not claim "flowchart" support with nodes only.
11. **Run calibration and round-trip QA first:** corners, strokes, rotated shapes, known text wraps, mixed KO/EN, logo/divider visibility, save/reopen, and render comparison.
12. **Do not claim WYSIWYG from coordinate equality alone.** Acceptance should use tolerances and rendered evidence from the actual target consumer.

## Assumptions and caveats

- This review is based on read-only OPC/XML and media inspection of the exact template hash above. No deck was modified or generated.
- No local PowerPoint or LibreOffice executable was available for an end-to-end render, so visual inheritance is structurally proven but still requires the smoke test described above.
- The suggested editor-line geometry is an evidence-based approximation of the visible pixels in the current gradient JPEG. The final plan may choose a simpler line treatment as long as it remains non-exportable and the approximation is documented.
