# Phase 0 — Change Detail

**Scope:** the 5 files in `approved_write_manifest.txt`, and nothing else.
**Not started:** Phase 1. No `canvas/geometry.py`, no `canvas/style.py`, no `canvas/schema.json`.

## ⚠ The one thing to read first

**No code in this change has been executed.** The environment this ran in denied all Python
execution (`python -c`, `python file.py` — both auto-denied, non-interactive, and the brief
forbids asking the user). So:

- `reference/renderer_template.pptx` **was not built** — it does not exist.
- `reference/template_pin.json` is therefore **deliberately unpinned**: `renderer_template.sha256`
  is still the `<FILL FROM ...>` placeholder, and `pin.py` **fails closed on it by design**. I did
  not invent a SHA to make the file look finished.
- Every acceptance gate in `HUMAN_VERIFICATION.md` — including the automated ones — is **un-run**.

Everything below is therefore *written and reviewed against the installed python-pptx 1.0.2
source*, not *proven by running it*. That is a weaker claim and it should be read as one. The
first action for whoever picks this up is `make_renderer_template.py --write-pin`.

## What compensates for that

Since I could not run the library, I read it. Every private/underdocumented API this change leans
on was checked against
`…/site-packages/pptx/` rather than recalled:

| Claim | Verified at |
|---|---|
| `Presentation.slides` calls `rename_slide_parts()` on **every** evaluation, which does a `related_part(rId)` lookup per `sldId` → `KeyError` on a transiently inconsistent package | `presentation.py:108-113`, `parts/presentation.py:94-104` |
| `Slides._sldIdLst` is the bindable element; `CT_SlideId.rId` exists | `slide.py:247-249`, `presentation.py:112` |
| `XmlPart.drop_rel(rId)` pops only when ref-count < 2 — and it is exactly 1 while the `<p:sldId>` still carries the `r:id`, so drop-then-remove works | `opc/package.py:409-430` |
| Unreachable parts are simply not serialized (`iter_parts` walks the rel graph) — hence `drop_rel` really is required, not belt-and-braces | `opc/package.py:88-97` |
| `ShadowFormat.inherit = False` exists and writes an empty `<a:effectLst>` | `dml/effect.py:34-40` |
| `CT_TextCharacterProperties` declares **no** `ea` child (so `<a:ea>` must go in by lxml), and the plan's successor list is exactly the schema's child order | `oxml/text.py:268-312` |
| `_Relationships` is a `Mapping` → `.values()` is valid | `opc/package.py:493` |

## Two bugs found in the plan, and corrected here

**1. `layout.placeholders[10]` (plan §4.2) would raise `IndexError`.** The two placeholder
collections are exact opposites, and the plan's pin code gets it backwards:

| | `layout.placeholders` | `slide.placeholders` |
|---|---|---|
| class | `LayoutPlaceholders(BasePlaceholders)` | `SlidePlaceholders(ParentedElementProxy)` |
| `[10]` | **positional** (`_BaseShapes.__getitem__`, `shapetree.py:88`) → `IndexError` | **idx-keyed** (`shapetree.py:782`) → `KeyError` |
| `.get(10)` | ✅ by idx (`shapetree.py:723`) | ❌ **does not exist** |

Layout 3 has exactly one placeholder, so `layout.placeholders[10]` indexes past the end and
`verify_pin` dies with `IndexError` instead of performing its check. Plan §6.3's
`slide.placeholders[10]` **is** correct — the asymmetry is the trap. `pin.py` uses
`layout.placeholders.get(10)`; `calibrate.py` uses `slide.placeholders[10]` inside a
`try/except KeyError`.

**2. Plan §7.3's "`accent1` absent from every renderer-created `<p:sp>`" assertion could never
pass.** The four overrides in §6.4 win at *render* time — an explicit `<a:solidFill>` / `<a:ln>` /
`<a:effectLst>` in `spPr` beats the style ref — but they do not **delete** the `<p:style>` block
that `new_autoshape_sp` hard-codes, so `<a:schemeClr val="accent1"/>` is still sitting in the
shape's XML afterwards. The assertion would fail on a deck that renders perfectly. `calibrate.py`
adds a **fifth override**: strip `<p:style>` (it is optional in `CT_Shape`, so this is
schema-valid). The invariant becomes checkable rather than aspirational.

**Phase 1 must carry this fifth override into `canvas/style.py`.** It is not optional.

## The files

### `src/aippt/tools/make_renderer_template.py`
Builds `reference/renderer_template.pptx` (0 slides) from the 23-slide source, which is opened
read-only and never saved back (the destination is asserted to differ from the source). The
deletion loop obeys the landmine: bind `sld_id_lst = prs.slides._sldIdLst` **once**, iterate a
`list()` copy, `drop_rel(sld_id.rId)` then `sld_id_lst.remove(sld_id)`, and never touch
`prs.slides` until it is done.

*(Note: `slides` is a `@lazyproperty` in 1.0.2, so the cache happens to hide the `KeyError` today.
That is one version's implementation detail, not a contract, and the code does not rely on it.)*

Then it re-opens the artifact and **observes** the signature off the package — layout name,
partname, slide size, layout count, placeholder idx set, placeholder-10 geometry, media,
theme `accent1`. `--write-pin` writes that observed signature to `template_pin.json`. Nothing is
copied from a hand-typed literal. It refuses to pin (`BuildError`) if slides survived, the layout
count moved, layout 3 is not `slideLayout4.xml`, the divider/logo media are gone, or the package
has dangling rels. Gates §2.3 1–4 and 6 all run; gate 5 (PowerPoint opens it) is human.

The source-SHA guard has **no `--force`**: §4.3 says re-pinning is deliberate, so there is no
escape hatch to add.

### `reference/template_pin.json`
Unpinned, as above. `source_template` and `layout_signature` are **machine-extracted facts, not
guesses** — they come from `reference/layout_manifest.json` (written by `analyze_pptx_master`
against the real template) and are corroborated by `critic_review.md`. The builder overwrites all
of them from observation anyway, so a wrong value here cannot survive a build.

One expected change on first build: `required_media` is seeded with the two documented files
(`image5.jpeg`, `image2.svg`) but will likely come back with a **third** — the raster fallback the
logo's SVG carries via its `svgBlip` extension. That is the file §7.1 assertion 5 is actually
about.

### `src/aippt/canvas/pin.py`
`load_pin()` / `verify_pin() -> None` / `open_renderer_template() -> Presentation`, exactly as the
brief specifies. `load_pin` validates the pin *as a document* (version, required keys, and that
`built_from_sha256` matches `source_template.sha256` — catching a hand-edited file) and is kept
separate from `verify_pin`, which validates the *package on disk* — so "your pin file is
malformed" reports differently from "your template drifted". Gate 1 is size + SHA. Gate 2 is the
structural signature, and it exists for the mistake we actually expect: someone rebuilds, sees
the SHA error, pastes the new SHA in to make it go away, and never notices layout 3 changed.

It never reads the source template — that is a build-time input, and the request path should not
depend on a 1.8 MB deck it does not use.

### `src/aippt/tools/calibrate.py`
The §7.2 fixture: four rectangles at the exact slide corners, a 0/1/4/8 stroke ladder, 30° and 45°
rotations, a known string in a known 300-unit box at 14 pt, a mixed KO/EN string, and the divider
+ logo inherited free from layout 3. Emits `reference/calibration.pptx` plus a `.json` sidecar of
the ground-truth EMU, then re-opens the export and asserts **0 EMU drift** (§7.3) and no
accent1/`4472C4` in any shape it created.

**Phase 0 isolation held:** `geometry.py` and `style.py` are Phase 1, so the EMU conversion, the
`add_shape` overrides, `set_run_fonts` (latin + `<a:ea>` via lxml) and `style_text_frame` are all
**inlined** here. The duplication is deliberate and flagged in the docstring.

The corner rectangles deliberately sit inside `HEADER_RESERVED` / `FOOTER_RESERVED`. The renderer
will reject elements there and that is correct — but this fixture's whole job is to measure the
mapping *at the true slide corners*. The calibration deck is a ruler, not a document, and is
explicitly exempt.

### `HUMAN_VERIFICATION.md`
The four requested checks (PowerPoint opens clean; page number reads **1**, not 24; SVG logo
survives the conversion path; raster diff ≤ 2 px), each with the failure mode that makes it worth
doing, plus a build-and-pin step 0 and a table of what the builder already machine-checks so
nobody re-does it by hand. Has a space to **record the measured pixel error**, because "≤ 2 px" is
the gate but the actual number is what Phase 1 relies on.

## Assumptions

- **Write location.** `target_repo: .` with a `.editwork` git worktree, but `tasks/AI_Powered_PPT`
  is **untracked**, so the worktree contains no copy of it (`.editwork/tasks/` is empty) and
  writing there would have produced files with no template, no `src/`, and no manifest. Prior
  phases wrote to the main tree (`src/aippt/render/*` is there), so I did too. All five paths in
  the manifest are relative to `tasks/AI_Powered_PPT/`.
- **No `__init__.py` added.** The package has none anywhere and relies on PEP 420 namespace
  packages; adding them would also have been outside the write scope. `calibrate.py` falls back to
  putting `src/` on `sys.path` when run as a plain script.
- `calibrate.py` writes `reference/calibration.pptx` (+ `.json`). Generating an artifact is the
  point of the tool; the write scope governs the source files I authored.
