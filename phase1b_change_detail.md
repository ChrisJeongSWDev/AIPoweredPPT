# Phase 1B — The Editor (DOM → Canvas IR): change detail

**Status: code complete; gates NOT run.** The permission layer in this session denies Python
execution (`python -m pytest`, `python -m py_compile` — everything but `python --version`), so
**Gates 2, 3 and 4 are un-run and I am not claiming them.** Gate 1 is a static grep, so I verified
it by hand with ripgrep and the evidence is pasted verbatim below. Read
[§ Gates](#acceptance-gates) before you trust any of this.

---

## Files created

| File | Lines | What it is |
|---|---|---|
| `src/aippt/canvas/app.py` | 209 | FastAPI. Serves the editor same-origin, renders in memory. Plan §9 tasks 3.1–3.3. |
| `src/aippt/canvas/static/index.html` | 168 | The shell. Toolbar, stage, `#title-field`, `#warnings`, status bar. |
| `src/aippt/canvas/static/style.css` | 309 | The CSS **contract** with `style.py` (§5.2, §5.3, §5.6 copied literally) plus app chrome. |
| `src/aippt/canvas/static/editor.js` | 1231 | The editor. State → CSS one-way, model-space constraints, serializer. |
| `src/aippt/canvas/static/interactions.js` | 134 | Pointer-capture drag/resize engine, interact.js-shaped. See [the decision](#the-interactjs-decision). |
| `tests/canvas/test_editor_source.py` | 205 | **Gate 1** — the Prime Directive, machine-checked. |
| `tests/canvas/test_app.py` | 249 | **Gate 2** — FastAPI `TestClient`. |

## Files appended to (surgical, no reformatting)

- **`pyproject.toml`** — added the `editor` optional-dependency group (`fastapi>=0.115`,
  `uvicorn[standard]>=0.30`); added `httpx>=0.27` to `dev` (FastAPI's `TestClient` needs it); added
  `[tool.setuptools.package-data]` so `schema.json` and `static/` ship with the wheel. Without that
  last one an installed copy fails at import (schema) and 404s (editor).
- **`requirements.txt`** — a `# --- Phase 1B: the editor ---` section in the file's existing
  commented style, kept commented-out because the web stack is optional.

**Nothing frozen was touched.** No edits to `schema.json`, `validate.py`, `geometry.py`, `style.py`,
`connectors.py`, `render_canvas.py`, `pin.py`, `src/aippt/ir/**`, `reference/**`,
`HUMAN_VERIFICATION.md`, the fixtures, or the Phase 1A tests.

---

## The interact.js decision

**I wrote the fallback (plan §5.1 option 2), not a vendored interact.js.**
`static/interactions.js`, ~130 lines of `pointerdown`/`pointermove`/`pointerup` with pointer
capture, behind the interface the call sites use (`Interactions.draggable`, `.resizable`,
`.pointerDrag`).

Why:

1. **I could not fetch it.** This session is sandboxed to the working directory and cannot reach a
   network. The brief's own instruction covers exactly this: *"If you cannot fetch it, write the
   fallback."*
2. **It makes the Prime Directive structural rather than merely obeyed.** interact.js hands you
   `event.rect` — a measured, device-pixel rectangle straight out of the DOM. Our engine **never
   emits one**. There is no measured rect to misuse, so the most common way this rule dies is not
   available. It differences two pointer positions and nothing else.
3. No CDN at runtime, no npm build step, works with the network off — all three requirements met.

It is **deliberately interact.js-shaped**: the move event carries `dx`/`dy` and `deltaRect` with
interact.js's exact meanings and **its exact units (device pixels)**, so the call sites already do
the `/ zoom` division the real library would demand. Swapping interact.js back in is a rewrite of
that one file and nothing else.

It has **no `snap` and no `restrict` modifiers**, on purpose — interact.js's operate in device
pixels, so at zoom 0.5 a 4-unit grid silently becomes a 2-unit grid and a reserved-region
restriction lands in the wrong place. All snapping and all constraint enforcement happen in **model
space**, in `editor.js`, after the `/ zoom` conversion.

---

## Acceptance gates

### Gate 1 — the Prime Directive — **verified by hand, PASSING**

I could not run pytest, but Gate 1 *is* a substring grep, so I ran the equivalent greps directly.
Verbatim output:

```
$ rg -n "getBoundingClientRect|offsetWidth|offsetHeight|clientWidth|clientHeight|offsetLeft|
         offsetTop|offsetParent|devicePixelRatio|getComputedStyle|getBBox|ev\.rect|event\.rect|
         12700|zIndex|z-index|1920|1080|1280|720|1440|810"  src/aippt/canvas/static/*.js

editor.js:92:    var r = stage.getBoundingClientRect(); // used ONLY for pointer inversion
```

One hit. It is the call inside `toModel()`. Every banned token — every measured-geometry API, the
EMU constant, the stacking index, every non-960×540 canvas size — is absent from **both** JS files.

```
$ rg -n "deltaRect\.\w+" src/aippt/canvas/static/editor.js
488:          var nx = s.x + ctx.deltaRect.left / zoom;
489:          var ny = s.y + ctx.deltaRect.top / zoom;
490:          var nw = s.w + ctx.deltaRect.width / zoom;
491:          var nh = s.h + ctx.deltaRect.height / zoom;

$ rg -n "4472C4" src/aippt/canvas/static/editor.js
52:  var FORBIDDEN_COLOR = '#4472C4';
844:  /* The colour guard. #4472C4 is refused in EVERY colour input, with the reason validate.py gives. */
```

All four `deltaRect` fields are divided by `zoom` **in the same expression**. `#4472C4` appears only
in the rejection path (the constant and the guard that refuses it).

> **A design note Gate 1 forced, and it is worth knowing.** Gate 1 is a plain substring grep, so the
> banned names must not appear in `editor.js` **even in a comment explaining why they are banned**.
> Rather than add a comment-stripper (fragile — a naive one truncates the line holding
> `"http://www.w3.org/2000/svg"`) or an exemption marker (an escape hatch that erodes the rule),
> `editor.js`'s header **points at the test for the list** instead of reciting it. The test is the
> spec, and it cannot drift away from itself.

### Gate 2 — `tests/canvas/test_app.py` — **NOT RUN**

Written, not executed. 15 tests covering every bullet the brief lists: `GET /` contains `id="stage"`;
`/api/context` SHA equals `load_pin()["renderer_template"]["sha256"]`; `minimal.json` → 200, body
starts `PK`, exactly 1 slide; `reject_header.json` → 422 with `HEADER_RESERVED` in `detail`;
`reject_accent1.json` → 422 with `4472C4`; wrong SHA → 409; `canvas: 1920×1080` → 409; malformed
JSON → 400 with no traceback; the export writes **no file to disk** (asserted by diffing a recursive
listing of the project root across the request). Plus: RFC 5987 filename, `target.template` ignored,
no CORS middleware, oversized body → 413.

> ⚠️ **`test_app.py` SKIPS rather than fails when the editor extra is absent** (`pytest.importorskip`
> on `fastapi` and `httpx`). That is deliberate — the CLI is a first-class path and `pytest tests/`
> must stay green for someone who installed only the renderer. **It also means Gate 2 can look green
> while having checked nothing.** When you run it, confirm the summary says **passed**, not
> **skipped**.

### Gate 3 — the existing suite stays green — **NOT RUN**

I changed no backend file, so the only plausible source of red is my packaging edit. Un-verified.

### Gate 4 — the editor ↔ CLI contract — **NOT RUN**

Requires a browser. Un-verified.

### To run all four

```bash
cd tasks/AI_Powered_PPT
pip install -e ".[editor,dev]"
python -m pytest tests/ -q                       # Gates 1 + 2 + 3
python -m aippt.canvas.app                       # -> http://127.0.0.1:8000
# draw two boxes and a connector, press Download JSON, then:
python -m aippt.canvas.render_canvas <downloaded>.json -o out.pptx
# expect: exit 0, "wrote out.pptx -- 1 slide, 3 element(s) on layout 3"
```

---

## Backend defects found

**None.** Two things I checked specifically, because the brief flagged them:

1. **The plan's §6.7 arrowhead ordering bug is already fixed.** The plan appends `<a:tailEnd>` before
   `<a:headEnd>`, which for `arrow: "both"` emits them in reverse `CT_LineProperties._tag_seq` order
   and makes PowerPoint declare the file corrupt. `connectors.py:34-65` uses `insert_element_before`
   with complete successor lists and gets the order right, and its docstring calls the plan's snippet
   out by name. Nothing to report and nothing to fix.
2. **`geometry.py`'s stroke-bleed caveat is a deliberate, documented accepted risk**, not a defect. An
   element flush against `HEADER_RESERVED` with an 8-unit stroke bleeds 4 units into it and still
   passes validation. I mirrored the behaviour exactly rather than "improving" on it — the editor
   must not disagree with the backend, and the 2 px raster diff (§7.5) is what is supposed to catch
   real bleed.

---

## Assumptions, and the caveats that matter

### Things I could not verify — read these first

1. **No gate was executed.** The permission layer denied every Python invocation except
   `python --version` (`python -m pytest`, `python -m py_compile`, even with the sandbox override).
   The Phase 1A brief author hit the same wall and recorded it as their assumption 4. **The Python
   files have therefore never been syntax-checked, let alone run.** Gate 1 I verified by grep because
   grep was available; everything else is un-run. Treat the first `pytest` run as the real gate.
2. **`fastapi`, `uvicorn` and `httpx` may not be installed.** I could not probe the interpreter or
   read `site-packages` (sandboxed to the working directory). `pip install -e ".[editor,dev]"` is
   step one of Gate 2.
3. **The brief I was handed was corrupted in transit.** Every literal `.` in
   `C:\Users\...\Temp\tmp.CxhiJOLHer` had been string-replaced with the absolute path
   `/c/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/.editwork` — so `app.py` read as
   `app/c/Users/…/.editworkpy`, and so on. I decoded it (the substitution is mechanical and
   reversible) and cross-checked against the clean `phase1b_brief.md` in the project root, which is
   identical in substance. **If any requirement below looks misread, that is the first place to
   look.** The dispatcher's substitution is worth fixing.
4. **I worked in `tasks/AI_Powered_PPT/`, not the `.editwork` git worktree.** The brief's footer said
   `target_repo: .` (post-decode). `.editwork` is a worktree of the *orchestrator* repo, and its
   `tasks/` directory is **empty** — `tasks/AI_Powered_PPT` is not tracked in git, so the worktree
   structurally cannot hold this project. Writing there would have produced nothing. I wrote to the
   real project tree.

### Decisions I made, and why

5. **`.txt` is the anchor box; `.body` is the contenteditable.** The §5.6 CSS contract puts
   `display: flex` on `.el .txt` and maps `align-items` → valign, `justify-content` → align. **That
   mapping is only correct when there is exactly one flex item.** A contenteditable holding several
   paragraphs produces several block children, which as direct flex items would lay out **side by
   side in a row**. So `.txt` keeps the §5.6 declarations *verbatim* and holds a single `.body` child
   that is the editable surface. The contract is preserved exactly as written; multi-paragraph text
   works. This is the one structural departure from the brief's HTML sketch, and it is forced.
6. **Double-click to edit text.** `.txt` is `pointer-events: none` until the element is double-clicked
   (`.editing`). Without this a **no-fill textbox could never be dragged** — its text box covers the
   whole element and every grab would land a caret instead of moving it.
7. **A connector's colour lives on the *stroke* control, not the text control.** A connector is a
   line; the schema gives it `color`/`width` and no `text` and no `fill`. The fill, text-colour and
   size inputs are inert while one is selected.
8. **A trailing `<br>` that is the last child of its block is dropped.** Chrome inserts one into every
   empty contenteditable block to give it height. Emitting it would add a phantom trailing line to
   the PPTX. Consequence: a Shift+Enter at the very end of a text box does not survive the round
   trip. I judged the phantom line the worse bug; it is a judgement call and it is reversible.
9. **`w`/`h` ≥ 4 is re-enforced after snapping.** The brief's pipeline order is min-extent → snap, but
   snapping an edge can pull a box back under the minimum. If it does, that axis's snap is undone —
   the invariant outranks the convenience.
10. **Clamping is silent; a reserved-region hit is a hard reject.** Per the brief's pipeline: step 4
    (clamp to the slide) quietly adjusts, step 5–6 (reserved regions) refuses to commit the frame and
    flashes `.blocked`. Reject-and-hold, never push-out.
11. **Stroke width 0 warns.** It is a *hairline* in PowerPoint and *nothing* in a browser — the one
    place the preview lies by construction. The UI says so and points at the stroke `none` button,
    which serializes as `"stroke": null`.
12. **`Load JSON` shipped** (brief decision 8 called it a stretch). It is the other half of the Gate 4
    round trip and it was cheap. Undo/redo, multi-select and copy-paste did **not** ship.
13. **`static/vendor/` does not exist.** The brief's write-scope listed
    `static/vendor/interact.min.js` *"(if vendoring)"*. I did not vendor, so I did not create a
    `vendor/` directory holding a file that is not interact.js. The `package-data` glob still lists
    `static/vendor/*`, harmlessly, so vendoring later needs no packaging change.

---

## Un-run human gates (§7.5)

Recorded as **still un-run**. I did not touch `HUMAN_VERIFICATION.md` (out of scope).

- [ ] PowerPoint opens the export **clean** — no repair dialog.
- [ ] Logo, gradient divider and page number are **inherited and undistorted** (they come from
      layout 3; we draw none of them).
- [ ] Korean renders in 맑은 고딕 and English in Century Gothic — **each in its intended typeface**.
- [ ] Raster diff of the export against a stage screenshot at zoom 1 is **≤ 2 px** (§7.5).

**The word "WYSIWYG" does not appear anywhere in what I shipped, and must not until that raster
diff exists.** Two places where the preview is *known* to differ, both stated in the UI:

- **The header is deliberately not WYSIWYG.** The editor draws a flat red line at the audited centre
  of the gradient band; PowerPoint draws the real gradient and the logo. (D-2, the layout-3 PNG stage
  background, moots this entirely.)
- **Elbow connectors are an approximation.** PowerPoint's `MSO_CONNECTOR.ELBOW` auto-routes; our SVG
  polyline routes `(x1,y1) → (mx,y1) → (mx,y2) → (x2,y2)`. New connectors default to `straight`.

A third, which the editor detects at runtime and shouts about: **if Century Gothic is not installed,
the preview's text metrics are a lie** and `#warnings` says so on load. A preview that lies silently
is worse than no preview.

---

## Deferred — named, not built

Layout-3 PNG stage background (**D-2** — makes the header genuinely WYSIWYG and moots the red-line
approximation) · connector gluing (**D-3**) · alpha (**D-4**) · autofit · multi-slide · images ·
undo/redo · multi-select · copy-paste · de-duplicating `calibrate.py` against `geometry.py` /
`style.py`.

**D-1 is still open and it is getting more expensive.** `style.py:50` says it plainly: Century Gothic
is *not* the Vieworks brand font — the template's real design fonts are 뷰웍스 B / 뷰웍스 M, set at run
level on every exemplar slide. Century Gothic body text will sit next to inherited 뷰웍스 chrome and
look subtly off-brand. As of today it is **one constant in `style.py` and one CSS declaration in
`style.css`**. After the editor ships and people have authored decks, it is an expensive discovery.
**Raise it before Phase 1 closes.**
