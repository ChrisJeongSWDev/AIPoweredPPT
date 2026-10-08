# Phase 1B Repair — change detail

The JSON import path now goes through the **same judge as the mouse**, and it judges the **whole
file before it touches the stage**. There is one door into the stage and it is locked.

---

## ⚠️ BLOCKER FIRST: the suite is written but UN-RUN

**I am not claiming the suite is green. I could not run it.**

This session denied every form of code execution:

| Attempted | Result |
|---|---|
| `python -m pytest tests -q` (Bash and PowerShell, several path forms) | `This command requires approval` |
| `python -m pytest --version` | `This command requires approval` |
| `python -m py_compile tests/canvas/test_app.py` | `This command requires approval` |
| `python -c "import pytest, fastapi"` | `This command requires approval` |
| `node -e "console.log(1+1)"` | `This command requires approval` |

`python --version` (3.13.14) and `node --version` (v24.14.0) *were* allowed, so both runtimes are
present — only execution is blocked. The session is non-interactive, so nothing can approve the
prompt, and the brief forbids asking the user.

**This is the same wall every previous phase hit** — `phase1a_repair_change_detail.md:7-24` opens
with the identical banner, and `phase1a_change_detail.md` and `phase0_change_detail.md` before it.
The "302 tests green" figure in the repair brief therefore came from *outside* a worker session, and
this change detail cannot add to it.

**First action for whoever picks this up — this is the acceptance gate, not a formality:**

```
cd tasks/AI_Powered_PPT && python -m pytest tests -q
```

Two things to know before you run it:

1. **The new tests execute JavaScript in Node.** `node` is on PATH in this environment (v24.14.0).
   If it is missing on yours, the 18 behavioural tests SKIP (by design — `pytest tests/` must stay
   green for someone who installed only the renderer) and the 4 structural tests still run. If the
   summary says SKIPPED for the `test_import_*` tests, you have not run the gate.
2. **The riskiest thing I shipped un-run is the Node harness**, not the fix. The harness lifts
   functions out of `editor.js` by name and brace-matching. If I have miscounted a brace it fails as
   a *broken test*, loudly (`the harness itself failed to run`), not as a false pass. I hand-traced
   every extracted function for braces-inside-strings; see "What I hand-verified" below.

In place of a test run I hand-traced the arithmetic of every geometry assertion against
`geometry.py`. That trace is below so a reviewer can check my reasoning cheaply — it is **not** a
substitute for running it. Expect green; verify it, do not trust it.

---

## Files changed (write scope respected)

- `src/aippt/canvas/static/editor.js`
- `tests/canvas/test_app.py`

Nothing else was touched. In particular `geometry.py`, `validate.py` and `app.py` were **not**
modified: this was never a backend defect. The backend was already right, which is exactly why the
imported element came back as a 422.

---

## The four defects, and where each one is closed

| # | Defect (from the brief) | Closed by |
|---|---|---|
| 1 | `makeEl(s)` with no geometry check | `loadIR()` pass 1 runs `illegalReason()` — the mouse's own judge — over every element before `makeEl()` is reachable |
| 2 | Stage cleared/title overwritten *before* the elements are looked at | `loadIR()` is now two passes: judge everything, then commit. Pass 2 cannot fail half-way |
| 3 | `x: e.x` with no numeric guard → `NaN` → every comparison false → passes a *correct* check | `geometryIsReadable()` runs FIRST inside the judge: the numbers must be numbers before they are compared |
| 4 | `text.paragraphs[0].runs[0]` and `p.runs.map()` unguarded → `TypeError` mid-import | `stateFromIR()` and `paragraphsToHTML()` never throw; every optional level is guarded |

---

## 1. The legality rule came out of `applyConstraints()`

`applyConstraints()` did two jobs. It **transformed** a candidate (min-extent → snap → clamp) and
then it **judged** it (bounds + reserved regions). Only the judging half may be reused by the import
path, so only the judging half moved out:

```js
function illegalReason(s) { ... }   // returns a human reason, or null when the state is legal
```

`applyConstraints()` step 5+6 is now one line:

```js
return illegalReason(c) ? null : c;
```

There is now exactly **one** copy of the reserved-region check in the file, and both callers reach
it: the mouse via `applyConstraints()`, a file via `loadIR()`. Two copies is precisely how the mouse
and the importer would drift apart — and a drift here is a legal-looking stage and an unexplainable
422.

### What the judge deliberately does NOT do

**It does not enforce `MIN_EXTENT`.** `w >= 4` is *drawing ergonomics* — you cannot mouse out a
2-unit box — whereas the schema's rule, and therefore the legality rule, is `w > 0`. If the judge
enforced 4, then importing a legal 2-unit element would have to either reject a deck the backend
happily accepts, or silently resize the user's file. It enforces `> 0`, which is the rule that is
actually true on both sides. This is the whole reason the transform and the judge had to be split
rather than the import simply calling `applyConstraints()`: **snapping and clamping a hand-authored
file would rewrite the user's deck on load**, which is the same push-out we refused to do for the
mouse.

**It does not transform anything at all.** A judge that quietly repairs its defendant is not a
judge, and the import path can only borrow this half *because* it is inert.

---

## 2. The numeric guard — the trap the brief warned about

This is the one that matters, and it is invisible:

```js
function geometryIsReadable(s) {
  var fields = s.type === 'connector' ? GEOM_FIELDS.connector : GEOM_FIELDS.shape;
  for (var i = 0; i < fields.length; i++) {
    var v = s[fields[i]];
    if (typeof v !== 'number' || !isFinite(v)) return false;
  }
  return true;
}
```

Every comparison against `NaN` is `false`. A missing `x` becomes `+undefined === NaN`, so
`outOfBounds()` returns **false** and `intersects()` returns **false**, and the element passes a
*perfectly correct* reserved-region check. Fix defect 1 without this and the gate still has a hole
you can drive a deck through.

`typeof` also disposes of `true` and of `"100"`: the payload schema says `number`, so a boolean or a
string coordinate is a 422 in waiting, not a coordinate. **`validate.py::_num` draws this exact line
on the other side, and gives this exact reason** (it rejects `bool` explicitly because `True` is an
`int` in Python). The two sides now agree about what a coordinate *is*, not just about where it may
sit.

I added one guard the brief did not name, for the same class of reason: **a non-positive `w`/`h` is
refused.** An inverted box is not a small box — `elementBBox()` hands back `x2 < x1`, and every
predicate downstream is then comparing an interval that runs backwards. That is a second way to be
waved through a correct check.

---

## 3. `loadIR()` is two passes, and the order is the fix

```js
function loadIR(ir) {
  ...header checks...

  /* PASS 1 -- JUDGE. Nothing below this line has touched the stage, and nothing above it may. */
  for (...) { states.push(stateFromIR(raw[i])); ...collect problems... }
  if (problems.length) throw new Error(<numbered list>);

  /* PASS 2 -- COMMIT. Every state is legal, so this cannot fail half-way through. */
  ...clear stage, set title, makeEl + appendChild...
}
```

The old function cleared the stage and overwrote the title **before it had looked at a single
element**. That is why the critic's "reject the entire import" was not reachable from inside that
loop: even a correct per-element check bolted in there would leave a half-imported stage behind on
the first bad element, with the user's own deck already gone. It is reachable from here.

The failure message names **every** bad element, numbered, using the same
`elements[i] (id "x", type "y")` label `validate.py` prints — so the editor's refusal and the
backend's 422 read as one voice rather than as two tools that happen to disagree with your file. And
the warning now says *"the stage is unchanged"*, which it may say, because it is now true.

`loadIR()` also rejects a **duplicate id** (ids become shape names in the .pptx; `validate.py`
rejects them — rule 5) and an **unknown type** (the judge has to know whether to read `x/y/w/h` or
`x1/y1/x2/y2`; an unknown type also renders as an invisible, unexportable element today).

---

## 4. `stateFromIR()` and `paragraphsToHTML()` never throw

`text`, `paragraphs`, `runs` and the first run are each optional **and** each hand-editable, so
`text.paragraphs[0].runs[0]` is a `TypeError` in any file someone deleted a line from — and it was
thrown *after* the stage had been cleared, so a malformed file cost the user the deck they had open.

Both functions now guard every level. `stateFromIR()` **never throws and never repairs**: not
throwing is what lets pass 1 report every bad element at once instead of dying on the first; not
repairing is what keeps the judge honest — a missing coordinate must arrive at `illegalReason()`
still missing, so that it is *refused* rather than quietly defaulted to `0` and drawn somewhere the
user never put it.

One behaviour change worth naming: `paragraphsToHTML()` now takes the element's colour as a
fallback, so a run with no `color` round-trips as the element's colour instead of the string
`"undefined"` (`normalizeText()` reads the colour back off the span on the way out).

---

## The tests (`tests/canvas/test_app.py`, new section "GATE 4b")

**22 tests** (18 behavioural in Node + 4 structural). They **execute the shipped rule** rather than
grepping for it — Gate 1 is deliberately
a grep and says so, but a grep cannot tell you that an element on the header is actually *refused*.
The functions are lifted verbatim out of `editor.js` by name and run in Node with only the DOM
stubbed (`stage`, `makeEl`, `titleField`, …), because the DOM is not what is under test.

**It does not re-implement the rule in Python.** A Python copy of `illegalReason()` would be a third
source of truth, and the entire bug being fixed here is what happens when the rule lives in more than
one place.

Refusals (each also asserts the stage was **not** cleared, nothing was made, the title survived):

- header, footer, **rotated footprint** entering the header (unrotated it clears by 3 units),
  connector across the header, off-slide
- **missing coordinate** (the NaN trap — and the element is *also* in the header, so a NaN-blind
  gate would admit a header element), string coordinate, boolean rotation, inverted box
- one illegal element refuses the **whole** import; the message names **every** bad element;
  duplicate id; unknown type

Acceptances — because a gate that refuses everything passes all of the above and is useless:

- a legal deck imports (and the stage *is* cleared, and the title *is* set)
- an element flush at `y == 92` is **legal** (half-open; get this wrong and honest decks are refused)
- a 2-unit element imports (`MIN_EXTENT` is not a legality rule)
- a paragraph with no `runs`, and a run with no `t`, do not crash the import

Structural (these **never skip**, node or no node):

- `applyConstraints()` contains no `REJECT_REGIONS` of its own — one copy of the rule
- `loadIR()` calls the same `illegalReason()`
- inside `loadIR()`, the judge and the throw both appear **before** any stage mutation
  (`.remove()`, `titleField.textContent =`, `makeEl(`, `appendChild(`)
- every `makeEl()` call site is downstream of a verdict

---

## What I hand-verified (in place of a test run)

**The rotated-AABB fixture**, against `geometry.py`'s maths. Box `x=400, y=95, w=200, h=20`,
`rotation=45`. Centre `(500, 105)`; corners rotate to y-extents `27.22 … 182.78`, x-extents
`422.22 … 577.78`. So: in bounds, and `27.22 < 92` ⇒ intersects `HEADER_RESERVED`. Unrotated it is
`y 95..115` and legal. The fixture therefore tests the *footprint*, not the path box.

**The half-open boundary.** `y=92, h=100` ⇒ box `(100, 92, 220, 192)`. `intersects()` needs
`a[1] < b[3]` ⇒ `92 < 92` is **false** ⇒ legal. Matches `geometry.py::intersects` exactly.

**The mouse path did not regress.** The numeric guard could plausibly have blocked every newly drawn
element, so I checked all three `applyConstraints()` callers: the draw path builds its candidate with
an explicit `rot: 0` (`editor.js:638`), `commit()` builds from `read()` which coerces every geometry
field with `+`, and `p-rot` is `+this.value`. No legitimate path supplies a non-number. Where a
property edit *could* previously write `NaN` into the dataset, it is now rejected and the element
holds its last legal state — an improvement, not a regression.

**Gate 1 (`test_editor_source.py`) still passes.** Its bans are substring greps over `editor.js`, so
new prose can break it. I grepped my additions: no banned measurement API, no `12700`, no `zIndex`,
no other canvas size (`1920/1080/1280/720/1440/810` — the judge's message builds `960x540` from
`CANVAS.w`/`CANVAS.h` rather than literals), and `4472C4` still appears only on its two pre-existing
rejection-path lines.

**No existing test references** `loadIR`, `paragraphsToHTML`, `applyConstraints` or `makeEl`, so the
blast radius on the other 302 is limited to the Gate 1 greps above.

**The temp harness is written under `tempfile.TemporaryDirectory()`**, i.e. *not* under
`PROJECT_ROOT` — `test_the_export_writes_nothing_to_disk()` walks the project tree and would
otherwise have failed.

---

## Scope boundaries I did NOT cross (and why)

**The forbidden colour is still not checked on import.** An imported `#4472C4` fill will import and
then 422 on export. This is deliberate: `applyConstraints()` — *the mouse's judge* — does not check
colour either. Colour is guarded at the input widget (`guardColor`), not at commit, so adding it to
`illegalReason()` would make the file path *stricter* than the mouse path and would no longer be
"the same gate". The export path already renders the backend's numbered list verbatim, so that 422
is explained. If the reviewer wants it enforced at import, the right fix is to add it to the judge
**and** to `commit()` together, which is a policy change to Phase 1B and not this repair.

**The brief is truncated.** `phase1b_repair_brief.md` ends mid-sentence at "Split it:" (line 39-40)
— Steps 2+ of the intended design were never written. The split above is my reconstruction from
Step 1's stated intent plus the critic's four defects. If the author had a different decomposition in
mind, this is the place it would differ.
