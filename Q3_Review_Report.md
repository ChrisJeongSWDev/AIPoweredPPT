# Q3 Post-Worker Review Report

**Verdict: BLOCK**

The scaffold is a useful design exploration, and the generated manifest is byte-linked to the current template, but the proposed `layout_id + ordered blocks -> placeholders` architecture is not implementable against this template as currently analyzed. The template's visual grammar lives primarily in its 23 example slides and their slide-level freeform shapes, not in a set of semantic, fillable slide layouts. The IR, analyzer, renderer contract, and prompts currently assume the opposite.

The project should not enter Phase 1 implementation until the layout strategy is explicitly changed and the IR is normalized around that strategy.

## Scope and evidence

Reviewed:

- `src/aippt/ir/schema.json` and `src/aippt/ir/models.py`
- `src/aippt/analyze_pptx_master.py`
- renderer/adapter/fit/diagram contracts and authoring prompts
- `foundation_research.md`, `README.md`, `reference/layout_manifest.json`, and `reference/layout_catalog.md`
- the current `Vieworks_R&D_ppt_Template.pptx` package, using read-only OPC/XML inspection
- the three HTML corpus files for block-count and limit checks

The manifest source SHA-256 (`0de7d70cf45197e959d93c31eedd7599c42c23c1153d7b67b18d332141e61442`) and byte count (`1,881,082`) both match the current PPTX. The generated outputs are therefore tied to the checked-in template even though several extracted conclusions are incomplete or misleading.

## Blocking findings

### F-01 — The catalog exposes no layout roles that the adapter requires

**Severity: Critical**

`html_adapter.choose_layout()` requires roles such as `picture`, `table`, `bullets`, `two-content`, `multi-content`, `title-only`, and `section-divider` (`src/aippt/adapters/html_adapter.py:110-139`). The generated catalog contains only:

- `title`
- `blank`
- `custom`

See `reference/layout_catalog.md:17-25`.

The documented fallback also fails: a missing role is supposed to fall back to `bullets`, but no `bullets` layout exists. As a result, nearly every non-title corpus slide will fail layout selection before rendering.

More importantly, the five layouts are not general content layouts:

- two layouts have no placeholders;
- the title layout has two short `BODY` placeholders;
- `1_사용자 지정 레이아웃` has three short `BODY` placeholders clustered in the left half;
- `2_사용자 지정 레이아웃`, used by most example slides, has only one short top-of-slide `BODY` placeholder.

Meanwhile existing slides based on `2_사용자 지정 레이아웃` contain between 2 and 51 top-level shapes (`reference/layout_manifest.json:347-426`). Direct package inspection also found large numbers of slide-level groups and connectors. Those slide-level objects do not become part of a new slide created with `add_slide(layout)`.

**Required decision:** choose one of these designs before renderer implementation:

1. Refactor the PPTX template so its layouts contain real title/body/picture/table regions. This best preserves the current invariant.
2. Extract deterministic layout recipes from selected example slides, then create new slides from those recipes. Geometry still comes from the template analysis, not from the model.
3. Clone designated exemplar slides and replace named content slots. This preserves the current appearance most closely but requires a tested slide-cloning/relationship strategy.

The current design—adding a layout and expecting the example slide's freeform composition to appear—will not work.

### F-02 — The title contract is incompatible with every analyzed layout

**Severity: Critical**

The schema says `slide.title` fills a `TITLE` placeholder (`src/aippt/ir/schema.json:61-65`), and `fill_title()` is specified to use `slide.shapes.title` (`src/aippt/render/renderer.py:119-127`). However, every extracted placeholder is type `BODY`; the title layout itself has `BODY` idx 10 and idx 11 (`reference/layout_manifest.json:59-130`).

`slide.shapes.title` returns `None` when a slide has no title placeholder, as documented by python-pptx. Therefore the specified renderer cannot fill a title on this template. The catalog also reports these title/subtitle boxes as one-bullet body budgets (`reference/layout_catalog.md:32-35`), which is semantically wrong and will confuse both the model and the fitter.

**Required change:** the manifest needs explicit semantic slot metadata independent of `PP_PLACEHOLDER_TYPE`, for example `slot_id: title`, `slot_id: subtitle`, `slot_id: body-main`, with a concrete placeholder idx or deterministic recipe region behind each slot. The IR should target semantic slots, not assume that `TITLE` exists.

### F-03 — Brand accent and font extraction misses the actual layout-level design

**Severity: Critical**

The manifest reports `#DB0032` as `not-found` (`reference/layout_manifest.json:50-53`) because `find_brand_accent()` checks only the theme and slide-master XML (`src/aippt/analyze_pptx_master.py:202-234`). A read-only scan of the PPTX package found `DB0032` in:

- `ppt/slideLayouts/slideLayout3.xml` — layout-level text styling;
- `ppt/slides/slide2.xml` — slide-level text styling;
- `ppt/presProps.xml` — the recent-colour list, which is not itself authoritative design evidence.

The first hit is load-bearing: the accent exists in a layout even though it is absent from the theme and master. The renderer contract has no branch for this state; it only describes theme-slot or master-hardcoded colour resolution (`src/aippt/render/renderer.py:143-146`). Inline code, callouts, and native diagrams therefore have no valid brand-colour source under the current manifest.

Font extraction has the same scope problem. The catalog lists `맑은 고딕` and an empty East-Asian face (`reference/layout_catalog.md:11-15`), but package inspection found layout-level `뷰웍스 B` and `뷰웍스 M` typefaces. The theme also declares the Korean font through `<a:font script="Hang" typeface="맑은 고딕">`; `_typefaces()` reads only `latin`, `ea`, and `cs`, so it incorrectly treats the Korean mapping as absent (`src/aippt/analyze_pptx_master.py:136-144`).

**Required change:** extract effective style per semantic slot, including direct layout run properties, paragraph/list style, theme script-specific fonts, and all relevant colour sources. Record provenance and precedence, not just one guessed value. Scan layout XML for hardcoded brand colours; scan slides only as evidence for exemplar-recipe extraction, not as a global default.

### F-04 — The generated budgets measure header boxes, not usable slide content

**Severity: Critical**

Because most layouts expose only a title-like short `BODY` placeholder, the catalog has no budget for the large body region where tables, diagrams, cards, steps, images, and prose would actually be drawn. Yet the author prompts claim that the catalog measures the target boxes (`prompts/20_slide_fill.md:26-35`). This makes the preventive overflow layer unusable for nearly all block types.

Even for real text placeholders, `content_budget()` uses the full outer width and height (`src/aippt/analyze_pptx_master.py:312-365`) and does not subtract or model:

- text-frame left/right/top/bottom margins;
- bullet indentation and hanging indent;
- inherited `space_before`, `space_after`, and line spacing;
- vertical anchor, rotation, columns, or explicit line breaks;
- level-specific font sizes and paragraph styles;
- neighbouring layout decoration geometry and z-order.

The 10% safety factor is not a substitute for these deterministic measurements. python-pptx exposes text-frame margins and paragraph spacing directly.

**Required change:** compute budgets for normalized semantic regions, using effective inner text extents and level-specific paragraph properties. Heavyweight blocks need area/layout constraints rather than character totals. Keep render-to-image verification as the final authority.

## IR and pipeline findings

### F-05 — Slide cardinality and identity are internally contradictory

**Severity: High**

Three contracts conflict:

- deck metadata says the renderer turns `deck.title` into a title slide (`src/aippt/ir/schema.json:16-33`);
- renderer output must have exactly `len(ir.slides)` slides (`src/aippt/render/renderer.py:76-80`);
- code variants and overflow handling may emit continuation slides (`src/aippt/render/renderer.py:166-170`, `src/aippt/render/fit.py:136-150`).

The HTML adapter also promises one card in -> one slide out (`src/aippt/adapters/html_adapter.py:98-105`). An implicit title slide or renderer-created continuation breaks slide count, stable IDs, source mapping, visual-QA mapping, and deterministic re-runs.

**Required change:** rendering must be one normalized slide in -> one PPTX slide out. Any title slide, code-variant expansion, or continuation split should occur in a deterministic normalization/planning stage that emits a new validated IR with final IDs before rendering.

### F-06 — Ordered blocks cannot be mapped safely to real targets

**Severity: High**

The schema says blocks are assigned to non-title placeholders in order and then to free-floating shapes (`src/aippt/ir/schema.json:72-76`). That is ambiguous when:

- no title placeholder exists;
- multiple `BODY` placeholders have different semantic purposes;
- a block needs a compound region rather than one placeholder;
- a recipe uses slide-level shapes instead of placeholders.

**Required change:** add semantic slot binding. Each block needs a stable `id` and either a `slot_id` or a renderer-resolved placement role. A slot identifier is not geometry and does not violate the “AI never emits coordinates” invariant.

### F-07 — The verified corpus is not fully representable by the schema

**Severity: High**

The corpus contains one ordered process with ten `.step-badge` items (`Vieworks_MatroxSDK_Example_UserManual.html:350-359`), while `steps.items` is capped at six (`src/aippt/ir/schema.json:262-283`). The schema therefore rejects a construct it claims was derived from the corpus.

The seven SVGs are intentionally declared lossy (`foundation_research.md:209-218`), but that means the stated editable 30-slide round-trip goal cannot be clean unless the acceptance criteria explicitly allow those losses or an SVG/raster asset path is added. At least one SVG is substantive architecture/optics content, not decorative chrome.

**Required change:** raise the step cap to cover the measured corpus and let layout budgets decide whether to split. Define an explicit policy for SVG: supported raster/vector asset, pre-authoring conversion, or accepted loss with a testable exception list.

### F-08 — Provenance and repair addressing disappear between outline and IR

**Severity: High**

The outline carries `source_refs` (`prompts/10_outline_storyboard.md:52-67`), but the Slide IR has nowhere to store them. The system prompt requires every factual claim to be traceable, yet the final artifact discards that traceability. Also, `slide.id` is optional and unconstrained, and blocks have no IDs, despite the QA loop relying on stable targeting.

**Required change:** require a patterned, deck-unique slide ID; add block IDs; retain slide/block-level source references and optional source footnotes. Enforce uniqueness in the Python model because JSON Schema cannot express uniqueness by object property.

### F-09 — `models.py` is not a safe validation boundary

**Severity: High**

`Deck.from_dict()` explicitly does not execute JSON Schema validation (`src/aippt/ir/models.py:467-494`). Its manual parsing accepts or mishandles several schema-invalid values: extra properties, invalid enums, excessive item counts, invalid lengths, empty run arrays, and some missing keys. `_parse_block()` also does not enforce all schema limits (`src/aippt/ir/models.py:342-418`). Depending on which adapter constructs a `Deck`, the “normative contract” can be bypassed.

**Required change:** provide one public parse entrypoint that first runs the canonical schema, then performs cross-field/model checks. Keep unchecked construction private or clearly named. Add schema/model conformance tests so both layers reject the same negative fixtures.

### F-10 — `layout_id` is not a stable or unambiguous layout reference

**Severity: Medium**

The analyzer aggregates all masters, while the IR stores only a layout name. Different masters can contain the same layout name. The IR also does not pin the template/manifest SHA, so a regenerated template can silently change geometry under an existing IR while keeping the same names.

**Required change:** identify layouts with at least `master_index + layout_id`, and pin the manifest/template SHA in deck metadata. Prefer a generated stable `layout_key` over a human-editable name.

### F-11 — Asset inputs are under-constrained

**Severity: Medium**

`image.source.value` has no maximum length or media validation; `path` is described as relative but is not constrained (`src/aippt/ir/schema.json:214-235`). This permits oversized base64 payloads and path traversal if a renderer resolves paths naively. Mermaid rendering similarly needs subprocess timeout, input-size limits, and a fixed working directory.

**Required change:** constrain media type and size at runtime, resolve paths under an approved asset root, reject traversal/absolute paths unless explicitly allowed, and isolate/timeout `mmdc`.

## python-pptx gotchas missing or misstated

### F-12 — Table placeholders can be filled directly

**Severity: Medium**

The renderer contract says a `TABLE` placeholder cannot be filled directly and must be deleted after `shapes.add_table()` (`src/aippt/render/renderer.py:161-165`). python-pptx provides `TablePlaceholder.insert_table(rows, cols)`, which replaces the placeholder with a placeholder graphic frame and preserves its relationship/position semantics. The current template has no TABLE placeholder, but the generic renderer contract is still wrong. See the official [placeholder documentation](https://python-pptx.readthedocs.io/en/latest/user/placeholders-using.html) and [table documentation](https://python-pptx.readthedocs.io/en/latest/user/table.html).

### F-13 — Autofit is described too absolutely; `fit_text()` exists

**Severity: Medium**

The research says `TEXT_TO_FIT_SHAPE` “sets a flag. Fits nothing” (`foundation_research.md:316-329`). It is correct that python-pptx does not provide PowerPoint's layout engine and that a flag alone is not a headless proof of fit. However, the API defines `TEXT_TO_FIT_SHAPE` as a consumer-applied shrink strategy, and `TextFrame.fit_text()` performs a local best-fit calculation using a font file or installed font. See the official [text API](https://python-pptx.readthedocs.io/en/latest/api/text.html) and [autofit analysis](https://python-pptx.readthedocs.io/en/latest/dev/analysis/txt-fit-text.html).

`fit_text()` has serious constraints—uniform font assumptions, font discovery, mixed styles, and Korean font availability—so render verification remains mandatory. The design should evaluate it as one deterministic fallback rather than state that no fitting API exists.

### F-14 — Layout-to-master placeholder inheritance is type-based, not idx-first

**Severity: Medium**

`_master_ph_for()` matches master placeholders by idx before type (`src/aippt/analyze_pptx_master.py:435-444`). python-pptx's layout-placeholder implementation maps layout types to a corresponding master placeholder type. An idx collision with a different type can therefore produce incorrect geometry/font inheritance in other templates. See the official [placeholder implementation](https://python-pptx.readthedocs.io/en/latest/_modules/pptx/shapes/placeholder.html).

The current master appears to have no master placeholders, so this did not cause the present output, but it is a generic analyzer defect.

### F-15 — Connector binding is experimental and can produce load errors

**Severity: Medium**

The diagram contract treats `begin_connect()` / `end_connect()` as straightforward (`src/aippt/render/diagrams.py:124-146`). The official [Connector API](https://python-pptx.readthedocs.io/en/latest/api/shapes.html) marks both methods experimental, reliable primarily for rectangular shapes, and warns that invalid connection-point indices can cause a load error.

**Required change:** restrict native diagram nodes to tested rectangular types, map connection points explicitly, save/reopen every generated deck, and render it before acceptance.

### F-16 — Rich-content placeholder replacement invalidates the old object

**Severity: Medium**

`PicturePlaceholder.insert_picture()` and `TablePlaceholder.insert_table()` replace the underlying XML element; the old placeholder proxy becomes invalid. Picture insertion also crops proportionally to fill the placeholder, whereas `shapes.add_picture()` preserves aspect only when one dimension is omitted. The renderer must choose fit versus fill deliberately and retain the returned replacement proxy. See the official [placeholder guide](https://python-pptx.readthedocs.io/en/latest/user/placeholders-using.html) and [shape API](https://python-pptx.readthedocs.io/en/latest/api/shapes.html).

### F-17 — Speaker-notes creation has side effects and can lack a body placeholder

**Severity: Low**

The IR carries notes, but the renderer contract does not define their implementation. Accessing `slide.notes_slide` creates a notes slide if absent; `notes_text_frame` can still be `None` if the notes body placeholder is missing. See the official [Slides/NotesSlide API](https://python-pptx.readthedocs.io/en/latest/api/slides.html). Notes creation and missing-placeholder behavior need explicit tests.

## Documentation and status drift

### F-18 — Repository status documents contradict the generated artifacts

**Severity: Medium**

`README.md:27-59`, `README.md:108-110`, `foundation_research.md:8-32`, `foundation_research.md:222-260`, and `result.md:6-14` all say the analyzer has never run and the layout files are placeholders. The checked-in layout files are now generated and match the current template hash.

This stale status obscures the more important conclusion: the analyzer ran, and its real output disproves the assumed semantic-layout architecture. Refresh the documents after the design decision above; do not merely replace “not run” with “passed.”

## Recommended remediation order

1. **Select the layout strategy**: real semantic layouts, deterministic recipes derived from exemplars, or exemplar cloning.
2. **Extend the analyzer/manifest** for semantic slots, effective style, decoration geometry, template identity, and correct accent/font resolution.
3. **Normalize the IR** so every final slide and block has stable IDs, slot bindings, provenance, and one-to-one render cardinality.
4. **Fix corpus coverage and validation**: ten-step process, explicit SVG policy, schema-first parsing, uniqueness/cross-field checks.
5. **Rewrite the renderer contracts** around the chosen strategy and correct the python-pptx API assumptions.
6. **Regenerate the manifest/catalog and update prompts** only after the manifest semantics are trustworthy.
7. **Implement and run the verification matrix** below before claiming Phase 1 readiness.

## Minimum verification matrix

- Analyzer golden test against this exact template SHA:
  - 1 master, 5 layouts, 23 existing slides;
  - semantic slots correctly identify title/subtitle/body regions despite `BODY` placeholder types;
  - layout-level `DB0032` is found with correct provenance;
  - `script="Hang"` and layout-level `뷰웍스 B` / `뷰웍스 M` are captured.
- Layout/recipe smoke test: materialize every supported semantic role, fill every slot, save, reopen with python-pptx, and verify shape/relationship counts.
- HTML round-trip tests for all 30 cards, including the 10-step slide, tabbed code, three images, tables, and the explicit SVG/simulator loss policy.
- IR negative tests for unknown/duplicate IDs, ambiguous slots, extra properties, invalid enum values, ragged tables, unsafe paths, and oversized payloads.
- Cardinality test proving normalized IR slide count and IDs exactly match output PPTX and rendered PNG order.
- PowerPoint/LibreOffice render verification for every generated slide; no acceptance based solely on XML or estimated budgets.
- Reopen/save integrity test after slide removal, rich-content placeholder replacement, notes creation, connector binding, and relationship-heavy exemplar cloning (if selected).

## Assumptions and caveats

- The brief's POSIX-style `target_repo` value was mojibake; this review treats the directory containing `review_brief.md` as the target repository.
- Python execution was unavailable in this review session, so the analyzer was not re-run and no Python unit tests were executed. Manifest/PPTX identity and the additional template facts above were verified with read-only PowerShell and OPC/XML inspection.
- No slide rendering or visual comparison was performed. The verdict is based on structural contracts, generated manifest data, corpus inspection, and PPTX package contents.
- Line numbers refer to the reviewed working-tree versions on 2026-07-13.

