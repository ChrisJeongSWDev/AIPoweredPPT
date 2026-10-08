# Phase 1A Repair Brief ??`validate()` must accumulate ALL violations

## Why this is coming back to you

Phase 1A landed with 240 tests green, but Codex Critic **REJECTED** it on a requirement it treats as
load-bearing:

> `validate.py` must raise `CanvasValidationError` accumulating **ALL** violations.

Your implementation accumulates violations *within* a stage but raises *between* stages, so the
first failing stage hides every later one:

| Site | What it does |
|---|---|
| `src/aippt/canvas/validate.py:80-89` | Canvas mismatch ??immediate `raise`; then `_check_schema(ir)` and `_check_semantics(ir)` are called in sequence, each of which raises. |
| `src/aippt/canvas/validate.py:95-100` | `_check_schema` raises, so semantics never runs. |
| `src/aippt/canvas/validate.py:231-232` | `_check_semantics` raises separately. |
| `tests/canvas/test_validate.py:114-125` | `test_the_canvas_check_short_circuits` **asserts the suppression** (`assert "4472C4" not in msg.upper()`), which locks the defect in. |

The critic's reproduction: a **zero-width element** plus a **separate `#4472C4` element** reports
only the schema error. The accent1 violation is real, detectable, and independent of the extent
error ??the author should be told about it in the same pass. The module docstring
(`validate.py:7-9`) already promises exactly this behaviour and the code does not deliver it.

**This is a real defect, not a critic nitpick.** Fix it properly. Do not paper over it by deleting
the test assertion.

---

## What you must build

### 1. Restructure the stages to *return* problems, not *raise* them

```python
def validate(ir: Any) -> None:
    if not isinstance(ir, dict):
        raise CanvasValidationError(f"payload must be a JSON object, got {type(ir).__name__}")
    # ^ this early raise STAYS. It is a precondition, not a violation-suppressing short-circuit:
    #   there is literally nothing to inspect on a list or a string.

    canvas_problems  = _check_canvas(ir)      # -> list[str]
    schema_problems  = _check_schema(ir)      # -> list[str]   (never raises)
    semantic_problems = _check_semantics(ir, canvas_ok=not canvas_problems)  # -> list[str]

    if not (canvas_problems or schema_problems or semantic_problems):
        return

    sections = []
    if canvas_problems:
        sections.append(_format(canvas_problems, "payload"))
    if schema_problems:
        sections.append(_format(schema_problems, "schema"))
    if semantic_problems:
        sections.append(_format(semantic_problems, "semantic"))

    exc = StalePayloadError if canvas_problems else CanvasValidationError
    raise exc("\n".join(sections))
```

Every stage runs **unconditionally**. Schema failure must not prevent semantic checks, and semantic
failure must not prevent schema checks. One `raise`, one message, every violation.

`StalePayloadError` remains a subclass of `CanvasValidationError` and remains the class raised when
the canvas is stale ??that contract is tested at `test_validate.py:109-111` and must not change.
What changes is that the stale payload no longer *swallows* the rest of the report.

### 2. Keep the message format so the existing count assertions survive

Reuse `_format(problems, kind)` **as it is**, once per non-empty section, joined with `"\n"`. That
means a payload with only semantic violations produces **byte-for-byte the message it produces
today**, and these assertions keep passing untouched:

- `test_validate.py:164` ??`"2 semantic violations"`
- `test_validate.py:174` ??`"4 semantic violations"`
- `test_validate.py:196` ??`"3 semantic violations"`
- `test_validate.py:339` ??`"4 semantic violations"`

Do **not** replace the per-section counts with a single grand total. Those four assertions are the
only proof that the collect-all behaviour is per-rule and not merely per-stage; breaking them to
make the header prettier trades a tested invariant for cosmetics.

### 3. THE HARD PART ??`_check_semantics` must survive a structurally invalid payload

This is where a naive fix explodes, and it is the reason this brief is long.

`_check_semantics` currently opens with:

> *"The IR is already structurally valid here, so every field this touches is guaranteed to exist
> and to have the right type."*

**That guarantee is exactly what you are removing.** The moment semantics runs after a failed
schema check, every one of these becomes a live crash:

| Line | Crash on |
|---|---|
| `ir["title"]`, `ir["elements"]` (`:175`, `:178`) | `KeyError` when the key is absent; `TypeError` when `elements` is not a list |
| `el["id"]`, `el["type"]` (`:179-180`) | `KeyError`; also `TypeError` if an element is not a dict at all |
| `reserved_violations(el)` / `out_of_bounds(el)` / `element_bbox(el)` (`:194`, `:204`) | `geometry.py:94-100` does `float(el["x"])` etc. ??`KeyError` on a missing coordinate, `ValueError`/`TypeError` on a string or `None` |
| `float(el.get("rotation") or 0.0)` (`:212`) | `ValueError` if `rotation` is a string |
| `_colours_of` (`:247-264`) | `stroke["color"]`, `el["color"]`, `text["paragraphs"]`, `para["runs"]`, `run["color"]` ??all unguarded |
| `_texts_of` (`:267-276`) | `text["paragraphs"]`, `para["runs"]`, `run["t"]` ??all unguarded; and a `title` that is a dict falls into the dict branch |

A `KeyError` escaping `validate()` is a **worse** bug than the one you are fixing: the caller catches
`CanvasValidationError`, so a raw `KeyError` becomes an unhandled crash in the CLI.

**The rule to implement ??per-rule input guards, not per-element skipping:**

> Each semantic rule runs on each element **iff the specific fields that rule needs are present and
> of the right type**. A rule is never skipped because some *other* field of the same element failed
> schema.

Concretely:

- A **non-dict element**, or one with a missing/non-string `id` ??skip *that element's* rules that
  need an id (the duplicate check), but still report what you can. Label it by index:
  `elements[3] (id "?", type "rect")`.
- **Geometry rules** (reserved regions, slide bounds) run only when the coordinates that
  `element_bbox` will read are numeric: `x1/y1/x2/y2` for a `connector`, `x/y/w/h` otherwise, plus
  `rotation` being absent, `None`, or numeric. Add a small `_num(v) -> float | None` helper that
  rejects `bool` (a `bool` is an `int` in Python and `True` is not a coordinate) and non-numbers.
  A value that is numeric but out of range ??`w: 0`, `h: -5` ??**is** numeric, so geometry still
  runs on it. That is fine and intended: it produces no spurious complaint on the `reject_extent`
  fixture (check it ??I did).
- **Colour and text rules** walk `_colours_of` / `_texts_of` defensively: `isinstance` guards at
  every hop, `.get()` instead of `[]`, and silently skip any run/paragraph/stroke whose shape is
  wrong. The schema section already names those; a second complaint about the same field is noise.
- **Skipping is silent by design** for fields the schema already flagged ??but see the next section
  for the one case where it must NOT be silent.

`geometry.py` is **not in your write scope** and must not be touched. Do the guarding on the
`validate.py` side, before you call into it.

### 4. The stale canvas ??narrowed, and made explicit

Do **not** simply delete the canvas rule's special status. The module docstring's reasoning at
`validate.py:11-14` is correct and worth keeping: a payload authored in a 1920×1080 model space has
coordinates that mean nothing in a 960×540 one. If you run geometry against it, a 20-element deck
comes back with 20 bogus "outside the 960x540 slide" lines that drown the one violation that
matters. That is not "accumulating all violations", it is manufacturing false ones.

**But the critic is right that the current code goes too far.** `#4472C4`, control characters, and
duplicate ids are *canvas-independent* ??they are just as wrong in any model space, and suppressing
them is indefensible.

So, narrow the suppression to precisely the rules that depend on the coordinate system:

- Canvas mismatch ??a problem in the `payload` section (message text unchanged; it must still
  contain **`stale payload`** and **`never rescaled`** ??asserted at `test_validate.py:105-106`).
- **Skip only** rule 1 (reserved regions) and rule 2 (slide bounds) when the canvas is stale.
- **Still run** the schema check, rule 3 (accent1), rule 4 (control chars), rule 5 (duplicate ids).
- **Say so in the message.** Append an explicit line to the `payload` section, e.g.
  *"Reserved-region and slide-bounds checks were SKIPPED: they are measured in the 960x540 model
  space this payload was not authored in. Fix the canvas and re-validate to see them."*

Nothing is silently suppressed. The author is told exactly what was not checked and why, which is
the property the critic actually cares about.

Rewrite the module docstring (`validate.py:7-18`) to state this narrowed rule. The current text
promises a blanket short-circuit and would be a lie after this change.

---

## Tests you must change (`tests/canvas/test_validate.py`)

**`test_the_canvas_check_short_circuits` (`:114-125`) ??rewrite it, do not delete it.**

Rename to something like `test_a_stale_canvas_still_reports_canvas_independent_violations`. Its
payload is already an ideal mixed case: `reject_canvas.json` (canvas `1920×1080`, which is *also* a
schema `const` failure on `canvas.w`/`canvas.h`) plus an appended element carrying **`w: 0, h: 0`**
(schema) and **`fill: "#4472C4"`** (semantic). Assert:

```python
msg = violations(ir)
assert "stale payload" in msg              # rule 6 still fires, and still raises StalePayloadError
assert "4472C4" in msg.upper()             # <-- INVERTED. The suppression the critic flagged is gone.
assert "HEADER_RESERVED" not in msg        # geometry IS still skipped: those coords are meaningless
assert "outside the 960x540 slide" not in msg
assert "schema violation" in msg           # the schema stage ran too
```

Also assert `pytest.raises(StalePayloadError)` still holds for this payload.

**Add the critic's exact reproduction ??a new test, and the one the gate is really about:**

```python
def test_schema_and_semantic_violations_are_reported_together():
    """A zero-width element (SCHEMA) and a separate #4472C4 element (SEMANTIC) must BOTH be named.
    Raising the schema errors before the semantic pass runs is what got Phase 1A rejected."""
    ir = load("minimal")
    ir["elements"] = [
        {"id": "zero_width", "type": "rect", "x": 100, "y": 120, "w": 0, "h": 100, "fill": "#FF0032"},
        {"id": "accent1",    "type": "rect", "x": 300, "y": 120, "w": 100, "h": 50, "fill": "#4472C4"},
    ]
    msg = violations(ir)
    assert "zero_width" in msg
    assert "schema violation" in msg
    assert "accent1" in msg
    assert "4472C4" in msg.upper()
    assert "semantic violation" in msg
```

**Add a robustness test ??the one that catches the crash this refactor invites:**

```python
def test_a_structurally_broken_element_does_not_crash_the_semantic_pass():
    """Semantics now runs even when the schema failed, so it can no longer assume its fields exist.
    A missing coordinate must degrade to 'skip the geometry rules for that element', never KeyError."""
    ir = load("minimal")
    ir["elements"] = [
        {"id": "no_width", "type": "rect", "x": 100, "y": 120, "h": 100, "fill": "#4472C4"},  # no `w`
        {"id": "no_width", "type": "rect", "x": 300, "y": 120, "w": 100, "h": 50, "fill": "#FF0032"},
    ]
    msg = violations(ir)          # must raise CanvasValidationError, NOT KeyError/TypeError
    assert "4472C4" in msg.upper()   # canvas-independent rule still ran on the broken element
    assert "duplicate id" in msg     # and so did the id rule
```

Consider one more parametrised guard covering a non-dict element, a non-list `elements`, a missing
`title`, a `rotation` that is a string, and a `stroke` missing its `color` ??each must produce a
`CanvasValidationError`, never an uncaught exception. Cheap to write, and it is the whole failure
mode of this refactor.

**Update the test-module docstring (`:10-14`).** It currently describes the stage boundary as the
design. State the new contract: *every* stage runs, *every* violation is reported in one raise, and
the only narrowing is the two coordinate-dependent rules under a stale canvas.

---

## Before you change the message format ??check who else reads it

`render_canvas.py` catches `CanvasValidationError` for the CLI's non-zero exit, and
`tests/canvas/test_roundtrip.py` may assert on validation output. **Grep the whole test suite for
`CanvasValidationError`, `StalePayloadError`, `semantic violation`, and `schema violation` before
you touch `_format`.** Reusing `_format` per-section (as specified above) is designed so that no
existing message changes unless the payload actually has violations in more than one section ??but
verify it, do not assume it.

**If a file outside your write scope needs to change to make the suite pass, STOP and say so in the
change detail. Do not edit it.**

---

## Acceptance criteria

1. `validate()` raises **exactly once**, with a message containing every detected violation across
   the payload, schema, and semantic stages.
2. The critic's reproduction (zero-width element + separate `#4472C4` element) names **both**.
3. A stale canvas still raises `StalePayloadError`, still says `stale payload` / `never rescaled`,
   **and** now also reports schema errors, accent1, control characters, and duplicate ids ??while
   explicitly announcing which two rules it skipped and why.
4. No payload, however malformed, escapes `validate()` as anything other than a
   `CanvasValidationError`. No `KeyError`, no `TypeError`, no `ValueError` from `float()`.
5. `validate()` still does not mutate the payload (`test_validate.py:342-346`).
6. **The full suite is green** ??all 240 pre-existing tests plus the new ones. Run
   `pytest tests/ -q` and paste the tail into the change detail. "The validate tests pass" is not
   the bar; the whole suite is.
7. Only the two files in `write_scope` are modified.

---

## Assumptions and caveats (flag in your change detail if you disagree)

- **The narrowed stale-canvas rule is a judgement call.** A maximally literal reading of the critic
  ("ALL violations") would have geometry run against a foreign coordinate system too. I have judged
  that reporting `x2 > 960` on a payload the author drew at 1920 wide is a *false* violation, not a
  suppressed one, and that announcing the skip in the message satisfies the critic's real
  objection ??which was silent suppression of *detectable* violations. If the critic rejects again
  on this specific point, the fallback is to run geometry unconditionally and drop the skip note;
  everything else in this brief is unaffected. Do not pre-emptively make that change.
- `reject_canvas.json` fails the schema `const` on `canvas.w`/`canvas.h` as well as rule 6, so its
  aggregated message will now carry both. That redundancy is acceptable; do not add logic to
  de-duplicate it.
- The frontmatter below follows the trailing `key: value` block convention used by
  `phase0_repair_brief.md` and `phase1a_brief.md`, which is what the orchestrator parses.

---

claude_model: opus
mode: continuation
target_repo: .
change_detail_path: tasks/AI_Powered_PPT/phase1a_repair_change_detail.md
write_scope: src/aippt/canvas/validate.py, tests/canvas/test_validate.py
````
