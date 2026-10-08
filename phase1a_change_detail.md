# Phase 1A — Change Detail

**Scope:** the files in the brief's `write_scope`, and nothing else.
**Delivers:** plan §9 Phase 1A, tasks 1.1 – 1.7 — the Canvas IR → PPTX renderer, its validator, and
the round-trip assertion suite.

---

## ⚠ The two things to read first

### 1. The test suite has not been executed

The environment this ran in **denied all Python execution** (`python -c`, `python -m pytest`,
`pytest` — all auto-denied, non-interactive, and the brief forbids asking the user). `python
--version` is permitted; nothing that runs code is.

So the round-trip suite is **written but un-run**. The claim "Phase 1A is green" is *not* made here
and must not be inferred. The first action for whoever picks this up is:

```
python -m pytest tests/canvas -q
```

This is the same wall Phase 0 hit (`phase0_change_detail.md` opens with the identical banner), and
it was later cleared — `reference/calibration.json` now reports `"roundtrip_problems": []` across 12
shapes, which means Python *does* run in this project, just not from this session. Expect the suite
to run cleanly; verify it, do not trust it.

### 2. The six `src/aippt/canvas/*` modules already existed when I arrived

An earlier attempt at this same brief had already written `schema.json`, `geometry.py`,
`validate.py`, `style.py`, `connectors.py` and `render_canvas.py` (file mtimes 13:43–13:47, well
after `pin.py` at 12:38), and had already applied correction 4 to `pyproject.toml`. It stopped
before task 1.7: **there were no tests and no fixtures at all.**

I **reviewed** those six modules line-by-line against the brief and against the installed
python-pptx source, and **left all six unchanged** — they are correct, and rewriting working code to
put my own fingerprints on it is not a service to anyone. `pyproject.toml` is likewise unchanged.

**What I actually wrote is the entire test half of Phase 1A**: three test modules and a 16-file
fixture corpus. That is the honest division of labour, and it means the modules carry a review, not
an authorship, from me.

---

## What compensates for not running it

Since I could not execute the library, I read it. Every python-pptx API this change depends on was
checked against `…/site-packages/pptx/` rather than recalled:

| Claim the code depends on | Verified at |
|---|---|
| `CT_LineProperties._tag_seq` is `… round, bevel, miter, headEnd, tailEnd, extLst` — so `<a:headEnd>` **must precede** `<a:tailEnd>` | `oxml/shapes/shared.py:242` |
| `insert_element_before` **appends** when it finds none of its successors — hence an incomplete successor list silently misplaces `<a:ea>` | `oxml/xmlchemy.py:685-691` |
| `CT_TextParagraph.r` and `.br` share one successor (`a:endParaRPr`), so `add_run`/`add_line_break` interleave in document order — the `\n` split really does emit `r, br, r` | `oxml/text.py:408-409` |
| `new_autoshape_sp` hard-codes `<p:style>` → `lnRef`/`fillRef`/`effectRef` = `schemeClr accent1`, `fontRef` = `lt1` | `oxml/shapes/autoshape.py:249-283` |
| `CT_Connector._tag_seq` **also** contains `p:style` (with `lnRef` → `accent1`) — so override 5 is required on `<p:cxnSp>`, not just `<p:sp>` | `oxml/shapes/connector.py:30, 68-71` |
| `new_textbox_sp` ships `<a:noFill/>`, `wrap="none"` and `<a:spAutoFit/>` — and carries **no** `<p:style>` | `oxml/shapes/autoshape.py:414-441` |
| `BaseShape.shadow` is `ShadowFormat(self._element.spPr)` → works for `Shape` **and** `Connector` | `shapes/base.py:175` |
| `ShadowFormat.inherit = False` writes an empty `<a:effectLst>`; the getter returns `False` iff one is present | `dml/effect.py:29-41` |
| `MSO_CONNECTOR.STRAIGHT` → `line`, `.ELBOW` → `bentConnector3`; both are real presets | `enum/shapes.py:742-755` |
| `ST_Angle` stores `round(deg × 60000) mod 360°` — so 0/30/45/315 round-trip **exactly** | `oxml/simpletypes.py:221-243` |
| `OptionalAttribute` setter **deletes** the attribute when the value equals the default — so `line.width = Pt(0)` removes `w`, and the getter reads back `Emu(0)` | `oxml/xmlchemy.py:218-226` |
| `LineFormat.width` getter uses `self._ln` (read-only), but `LineFormat.color` **mutates** — its getter sets the line fill type to `SOLID` | `dml/line.py:22-27, 71-82` |

That last row changed the tests: **colours and no-line states are asserted straight out of the XML,
never through `LineFormat.color`.** Asserting through a property whose getter documents a
side-effect would mutate the very thing under test, and a `stroke: null` shape would come back
looking solid because the assertion made it so.

### The fixtures were verified by independent computation

I could not run `validate.py`, so I recomputed its inputs with `jq` — a different tool, a different
implementation of the same arithmetic — and checked the answers against the fixtures the tests
assert on:

| Check | Result |
|---|---|
| All 16 fixtures + `schema.json` parse as JSON | ✅ (`jq` exit 0 on every file) |
| Every unrotated element in the 6 valid fixtures clears both reserved regions and the slide bounds | ✅ empty violation list for all 6 |
| Rotated AABBs in `rotated.json` | `rot_30` → (233.64, 115.36, 377.56, 244.64); `rot_45` → (409.29, 229.29, 550.71, 370.71); `rot_315` → (689.29, 169.29, 830.71, 310.71) — all clear |
| `reject_rotated_into_header` — path box y 95..115 clears the header, the 45° footprint does not | AABB (222.22, **27.22**, 377.78, 182.78) → **exactly one** `HEADER_RESERVED` hit |
| `reject_accent1` carries exactly 4 forbidden colours, one per hiding place | `fill`, `stroke.color`, run `color`, connector `color` — incl. the lowercase `#4472c4` |
| `reject_control_char` decodes to exactly the intended codepoints | `[8]`, `[12]`, `[13,10]`, and `[9,10]` — the last is **legal** and must not be reported |
| `reject_out_of_bounds` produces exactly 2 violations and no region hits | ✅ |

Those numbers are what the `"N semantic violations"` assertions in `test_validate.py` are pinned to,
so they are not guesses.

---

## The corrections (brief §*Corrections to the plan*)

| # | Correction | Status |
|---|---|---|
| 1 | `<a:headEnd>` must precede `<a:tailEnd>`; the plan's `ln.append()` order corrupts `arrow: "both"` | **Already correct** in `connectors.py` (uses `insert_element_before`). I added the test that proves it *on the re-opened file* — see below. |
| 2 | `verify_pin()` returns `None`; use `open_renderer_template(pin)` | **Already correct** in `render_canvas.py:98`. |
| 3 | There are **five** `add_shape` overrides, not four — `<p:style>` must be stripped | **Already correct** in `style.py:171` (`strip_style`), and applied to connectors too. |
| 4 | `jsonschema` belongs in core `dependencies`, not the `html` extra | **Already correct** in `pyproject.toml:17`. Unchanged by me. |

All four were carried by the earlier attempt. My contribution is that **correction 1 is now
machine-checked rather than merely implemented**: `test_head_end_precedes_tail_end_in_the_serialised_xml`
renders `arrow: "both"`, **saves the file, re-opens it**, and asserts `children.index(headEnd) <
children.index(tailEnd)`. Asserting on the in-memory tree would have proved nothing — the bug the
correction guards against is a *serialisation-order* bug, and PowerPoint's repair dialog is the only
other thing that catches it.

That re-open-before-asserting discipline is why the `decks` fixture saves to disk and reloads rather
than asserting on the `Presentation` object `render()` returns.

---

## What I wrote

### `tests/fixtures/canvas/` — 16 hand-written decks

**Six that must render** (`minimal`, `shapes`, `connectors`, `rotated`, `text`, `edges`):

- `shapes` — every shape type, plus the two traps: a **stroke of width 0** (a HAIRLINE in
  PowerPoint, not "no line") and a `fill: null` (`<a:noFill/>`).
- `connectors` — all **8** `kind × arrow` combinations. `arrow: "both"` is the corrupt-file case.
- `rotated` — 0°, 30°, 45°, 315°.
- `text` — multi-paragraph, multi-run, bold/italic, per-run colour, every `align`/`valign`, mixed
  KO/EN, a `\n` line break, and a real U+00A0.
- `edges` — **the regression corpus.** An element flush with the header at exactly `y == 92`; one
  whose bottom edge is exactly `y == 500` sitting over the footer's x-range; a full-bleed band that
  leaves `BODY_SAFE` but touches neither reserved region; a connector lying exactly on `y == 500`.
  Every one of these **must pass**. If the half-open rule ever regresses to inclusive, this is the
  file that fails first.

**Ten that must be rejected** — one per rule, plus two the brief did not ask for and that I think
earn their place:

- `reject_rotated_into_header` — the path box clears the header; **only the rotated footprint does
  not**. This is the fixture that pins the brief's rotated-AABB decision. Without it, someone
  "simplifying" `element_bbox` back to the path box would break nothing visible.
- `reject_sha` — **valid IR with a stale template SHA.** It is deliberately *not* in the validator's
  rejection list: it must **pass** `validate()` (which is pure and knows nothing about the pin) and
  fail at `render()`. That split is load-bearing — it is what keeps `validate.py` unit-testable
  without a 1.2 MB template on disk — and a test that did not distinguish them would let someone
  quietly move the SHA check into `validate.py` and break that property.

### `tests/canvas/test_geometry.py`

The EMU transform and the reserved-region predicates. Expected values are written **longhand**
(`emu(45.6) == 579120`), never derived by calling the code under test — a test that computes its
expectation with the function it is testing proves only that the function agrees with itself.

The load-bearing cases: edge contact at `y == 92` and `y == 500` is **not** intersection; one unit of
overlap **is**; `BODY_SAFE` is not a rejection region; and rotation can push a legal path box both
into the header and off the slide.

### `tests/canvas/test_validate.py`

The schema and the six semantic rules — and, more importantly, **that every violation is reported at
once**. `test_every_violation_is_reported_in_a_single_raise` stacks four *different* rules into one
payload and asserts all four are named. Collect-and-raise-once is a feature with a cost (you have to
keep collecting instead of returning early), so it needs a test that fails when someone "simplifies"
it away.

Control characters are exercised via `chr(0x07)` etc., never as literals: **an invisible character
in a test is a test nobody can review.** (This bit me while authoring — see *Assumptions* below.)

### `tests/canvas/test_roundtrip.py`

Plan §7.3's assertion table, checked against the **re-opened** `.pptx`. All 11 rows are covered, plus
z-order (`array order IS z-order` — asserted on the exported shape sequence), the text-frame margins
(7.2 / 3.6, the trap that "presents as a coordinate bug"), `\n` → `<a:br/>`, U+00A0 survival, Korean
survival, the title placeholder's explicitly-stated run properties, and the CLI's four exit paths
(0 / 1 validation / 1 stale SHA / 2 missing file).

The reserved-region check is **re-derived from the exported EMU geometry**, not read back from the
input IR. Checking the input would only prove that `validate()` agrees with itself; the question the
assertion is supposed to answer is *where the shapes actually landed*.

---

## Assumptions and caveats

1. **The suite is un-run.** Stated above; it is the single most important line in this document.

2. **No `conftest.py` was added.** `aippt` is installed editable
   (`site-packages/__editable__.aippt-0.1.0.pth` → this checkout's `src`), so `import aippt.canvas.*`
   resolves from any cwd and no `sys.path` bootstrap is needed. If a future checkout is *not*
   installed, the tests will fail at import and a `conftest.py` is the fix — I did not add one
   speculatively because it is outside the brief's `write_scope`.

3. **Authoring hazard, fixed but worth knowing.** My editor kept emitting `\uXXXX` escapes as *raw
   bytes*. A raw C0 byte inside a JSON string is **invalid JSON**, so `reject_control_char.json`
   would have failed with `JSONDecodeError` instead of the `CanvasValidationError` under test — a
   green-looking test asserting the wrong thing. The fixture now uses JSON's *named* escapes
   (`\b` = U+0008, `\f` = U+000C, `\r` = U+000D), which are plain two-character sequences that
   survive. `jq … | explode` confirms it decodes to `[8]`, `[12]`, `[13,10]`. The U+00A0 in
   `text.json` is a genuine literal (confirmed: codepoints `160, 160`); the *test* refers to it as
   `chr(0xA0)`.

4. **Fixtures hard-code the pinned template SHA.** A deliberate re-pin will fail
   `test_valid_fixtures_carry_the_pinned_template_sha` on all six valid fixtures. That is the
   intended signal, not a bug — a payload authored against the old template *is* stale — but it means
   re-pinning is a 7-file edit. The test says so in its docstring.

5. **`shapes.json` has no `align`/`valign` on the triangle** (it carries no text at all), so the
   `DEFAULT_ALIGN`/`DEFAULT_VALIGN` path in `style_text_frame` is exercised but not asserted against
   a rendered result. The defaults are asserted where text exists.

---

## Deferred — noted, not done

1. **De-duplicating `tools/calibrate.py` against `geometry.py` / `style.py`.** It still inlines its
   own `emu()`, `set_run_fonts()`, `style_text_frame()` and the overrides. The brief puts this out of
   scope and it should stay there until Phase 1A is green: `calibrate.py` is a **passing Phase-0
   gate**, and de-duping it re-opens one. It is a separate, reviewed change.

2. **D-1 is still open, and this is the cheap moment.** Century Gothic is **not** the Vieworks brand
   font — the template's real design fonts are **뷰웍스 B / 뷰웍스 M**, set at run level on every
   exemplar slide. Century Gothic body text will sit next to inherited 뷰웍스 chrome and look subtly
   off-brand. We ship it because the user asked for it. **Today it is one constant**
   (`style.py:44`, `LATIN`) plus one CSS declaration in the not-yet-written Phase 1B editor. After
   the editor ships it is an expensive discovery. Raise it before Phase 1 closes.

3. **`schema.json` is not declared as package data.** `validate.py` loads it via
   `Path(__file__).with_name("schema.json")`, which works under the editable install and will keep
   working. But `[tool.setuptools]` sets no `package-data` / `include-package-data`, so a **wheel**
   build would ship the package without `schema.json` and `validate()` would die on first call.
   `src/aippt/ir/schema.json` has the identical exposure. I did not fix it: the brief permits exactly
   one edit to `pyproject.toml` (the `jsonschema` move), and this is not it. It is a one-line fix
   whenever packaging becomes real.

4. **The human/raster gates remain un-run.** `HUMAN_VERIFICATION.md` is untouched and out of scope.
   Coordinate equality proves the transform, not the render (critic rule 12) — a rendered-QA pass in
   actual PowerPoint is still owed, and `arrow: "both"` opening clean is the specific thing to look
   at first.
