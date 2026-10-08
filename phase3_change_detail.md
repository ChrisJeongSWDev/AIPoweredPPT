# Phase 3 — `/api/generate`, the mock author: Change Detail

**Status: APPLIED.** All five files in `write_scope` were edited. The code is on disk.

**Status: UNRUN.** `pytest` is denied in this worker, as it was in Phases 0 and 2. Everything below
is reviewed code, not passing code. See §0.2 — this is the one caveat that matters.

---

## 0. READ THIS FIRST

### 0.1 The brief was corrupted again (same failure as Phase 2, same fix)

The brief handed to me (`$TMPDIR/tmp.nUugDixf92`) had **every literal `.` replaced** by the string
`/c/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/.editwork`. So `app.py` arrived as
`app/c/Users/.../.editworkpy`, `1.5` as `1/c/Users/.../.editwork5`, and so on.

It is an unescaped `sed` replacement — something like `sed "s/\./$EDITWORK/g"` — where the dot was
taken as the *pattern* rather than as a literal. The tell is that the injected path's own `.` (in
`.editwork`) survived: `sed` does not re-scan its replacement, so exactly one pass happened, and the
mangling is therefore **losslessly reversible** by substituting back.

I did not need to reverse it by hand. The clean original is on disk as
`tasks/AI_Powered_PPT/phase3_brief.md`, and I diffed my reading against it before touching anything.
**That file, not the temp copy, is what I implemented.** The orchestrator should fix the brief-copy
step; this is now twice.

### 0.2 I could not run the tests — read this before you trust anything below

Every attempt to execute anything was refused by the permission layer (`pytest`, `python`,
`node --check`), and the session is non-interactive, so no approval could be granted. I therefore
**cannot claim Gate 2 passes**. What I did instead, since a claim I cannot back is worse than no
claim:

- Checked every element the mock emits against `schema.json` field-by-field (§2.2).
- Checked every coordinate against `geometry.py`'s real reserved-region boxes, by arithmetic (§2.3).
- Traced each of the 17 new tests against the code it asserts on, including the brace-matching and
  comment-stripping behaviour of the `_js_function` / `_js_code` extractors (§4).
- Re-ran Gate 1 as a grep, which is all Gate 1 is (§5).

**A reviewer's first act should be `pytest tests/canvas/ -q`.** It is the whole of my uncertainty.

### 0.3 The `.editwork` worktree is a dead end (unchanged from Phase 2)

`target_repo: .` in the brief's YAML, plus a freshly-created git worktree at
`tasks/AI_Powered_PPT/.editwork/`, suggests edits belong in the worktree. **They cannot.**
`.editwork` is a worktree of the *multi-agent* repo, and this project is **untracked** there — its
`tasks/` directory contains nothing but `.gitkeep`. There is no `src/aippt` inside it to edit.

I applied to the live tree, `tasks/AI_Powered_PPT/`, which is where Phases 0–2 landed and where the
`write_scope` paths actually resolve. `write_scope` is relative to the project; `change_detail_path`
is relative to the repo root. Those two bases differ, which is worth fixing in the brief template.

---

## 1. What Phase 3 is

One endpoint, `POST /api/generate`, and the editor affordance that drives it. It is a **mock**: no
model, no network, no reading of the prompt. It returns one hardcoded `canvas-ir/1` deck, 1.5 s late.

The deliverable is **the seam**, not the author. The editor's request shape, its loading state, its
failure paths and its hand-off to `loadIR()` are all exercised end to end, so that swapping the mock
for a real author is a change to **one function** (`mock_ir()`) and to nothing else.

Two decisions carry the phase, and both are refusals:

**The prompt is not read, and the mock does not pretend to read it.** The brief said "hardcoded
payload", and the tempting embellishment — echo the prompt into the title so the demo looks alive —
is the one thing that would ruin it. It makes a mock you cannot tell apart from a model, and it
carries author-supplied text (control characters and all) into an IR that `validate.py` then refuses
at *export* time, which is the worst possible place to discover it. `test_the_prompt_is_NOT_read`
posts two different prompts and asserts one deck.

**The mock says "MOCK" on the slide itself.** A canned deck that escapes into a real presentation
announces itself, in a footnote textbox. It costs one element and it is the difference between a
demo and an incident.

---

## 2. `src/aippt/canvas/app.py`

### 2.1 The shared body guard — the reason `api_export` was touched at all

`_read_json(request) -> (payload, error)` now holds the size-and-JSON preamble that `api_export` used
to own inline, and both POST routes call it. This is the only change to an existing code path, and it
is a pure extraction: same two checks, same order, same status codes.

Both size checks survive the move, because both are load-bearing and it is not obvious:

- the **declared** `Content-Length` check refuses a megabyte before we buffer it;
- the **actual** `len(raw)` check exists because a **chunked** body declares no length at all, and
  would otherwise walk straight past the first check.

A second copy of that reasoning in `api_generate` would have been a second thing to forget to update.
`test_generate_shares_the_body_guard_with_export` pins that the new route inherits both (413 on an
oversized body, 400 on truncated JSON, no traceback in either).

### 2.2 `mock_ir(pin)` — a pure function of the pin, which is the seam

It takes the pin and returns a deck. **No request, no app state, no I/O.** That signature is the
entire point: a real author replaces this function and touches nothing else, and
`test_mock_ir_is_a_pure_function_of_the_pin` calls it directly, with no server in the picture, to
hold that shape.

**The template SHA and the layout index are injected from the live pin, never written as literals.**
A literal SHA would go stale the day the template is re-pinned (Sec 4.3) and would then hand every
user a 409 on a deck they did not author. This is the identical argument that put `/api/context`
there for the editor, and `test_the_mock_carries_the_LIVE_sha_and_not_a_literal` asserts *both* that
the payload carries the live SHA **and that the SHA does not appear in `app.py` at all**.

The deck is three cards and two arrows — a diagram, not a wall of text, because a payload that does
not exercise the IR proves only that JSON can be posted over HTTP. Checked against `schema.json`:

| element | required by schema | emitted |
|---|---|---|
| `connector` ×2 | `id, type, kind, x1, y1, x2, y2, color, width, arrow` | all 9, `arrow: "end"` |
| `rect` ×3 | `id, type, x, y, w, h, fill` | all 7, plus optional `text` |
| `textbox` ×2 | `id, type, x, y, w, h, fill` | all 7; **`fill: None` is stated, not omitted** |
| `run` | `t, size, color` | all 3; `color` on every run |

`fill` is required *even when null* precisely because omitting it is how a shape silently inherits
theme `accent1` (Office blue). Stating `None` is the schema encoding that invariant, and both
textboxes state it.

Colours are `#FF0032` (brand red, from `style.BRAND_RED`), `#FFFFFF`, `#1A1A1A`, `#6B727C`. No
`#4472C4` anywhere — that is the banned accent1.

**Array order is z-order**: the two connectors come **first**, so the lines sit *behind* the cards
they join. That is the convention the editor already follows when it inserts one, and
`test_the_mock_is_a_DIAGRAM_and_not_a_wall_of_text` asserts `elements[0]` is a connector.

### 2.3 The geometry clears the reserved regions — checked by arithmetic, not by eye

From `geometry.py`: `HEADER_RESERVED = (0, 0, 960, 92)`, `FOOTER_RESERVED = (733.6, 500, 960, 540)`,
and `intersects()` is **half-open**, so edge contact is not a collision.

| element | box (x1, y1 → x2, y2) | verdict |
|---|---|---|
| `subtitle` | 60, 132 → 900, 196 | top 132 > 92 ✓ |
| `flow_1` | 304, 290 → 358, 290 | ✓ |
| `flow_2` | 602, 290 → 656, 290 | ✓ |
| cards ×3 | 60/358/656, 232 → +244, 348 | rightmost ends at 900 < 914.4 ✓ |
| `mock_note` | 60, 392 → 900, 436 | bottom 436 < 500 ✓ |

Nothing touches the header, nothing touches the footer, nothing leaves 960×540. The arrows leave and
arrive at the cards' vertical centre (`_MID_Y = 232 + 116/2 = 290`), which is derived, not typed.

### 2.4 The mock is validated before it is served

`validate(ir)` runs on the way out, by **the same validator the export path runs**. Nobody eyeballs
this payload, and a mock that failed validation would demonstrate a working pipeline while breaking
the only thing the pipeline carries.

It cannot fail because of anything the caller sent — so if it fails, **it is our bug: a 500, never a
422.** That distinction is deliberate and it is in the code.

### 2.5 The 1.5 s is spent on the success path only

`MOCK_LATENCY_S = 1.5`, and it is not padding: the editor's loading state is real UI with a real
failure mode (a button you can press twice), and a mock that answered instantly would never exercise
it.

A malformed request is refused **before** the sleep, because no model would have been called for that
one either — charging the user 1.5 s to be told their body was empty simulates the wrong thing. Two
tests pin it in both directions: the success path must cost ≥ 1.2 s, the 422 must cost < 1.0 s.

---

## 3. The editor (`index.html`, `style.css`, `editor.js`)

### 3.1 It is a mock and the UI says so at rest

A `mock` tag next to the heading, and a hint line under the button: *"No model is called. The server
returns a fixed deck after 1.5 s, and it replaces the stage (Ctrl+Z brings yours back)."* An "AI"
affordance that looks production-ready while returning a canned deck is the one thing this panel must
not be — and saying so only in the change log means saying it to nobody.

### 3.2 `generate()` does not validate, and that is the design

It POSTs, then hands what comes back **straight to `loadIR()`**. There is no second judge here.

`loadIR()` is the one door into the stage: it judges every element *before* it clears anything, and
it refuses the whole deck if one element is illegal. A payload from `/api/generate` is **no more
trusted than a file the user opened** — today it is a fixed mock, tomorrow it is a model, and a model
is exactly the author most likely to put a box on the Vieworks logo. A second copy of the judge in
`generate()` would be a second source of truth, and the first thing to drift.
`test_generate_hands_the_payload_to_the_SAME_gate_the_file_import_uses` asserts `loadIR(ir)` is
called and that `illegalReason` is **not** mentioned.

### 3.3 One draft is one undo step, and the caller pushes it

`snapshot()` / `pushUndo(before)` straddle the `loadIR()` call, lifted from the file-import path for
the same reason it lives there:

- Generate **replaces the whole deck**. That is one undo step.
- `pushUndo` comes **after** `loadIR()` returns, so a **refused draft costs no undo step** — nothing
  was pushed, and the stage is untouched. `test_a_refused_draft_costs_no_undo_step` asserts that
  ordering against the *comment-stripped* source, so prose cannot satisfy it.
- `loadIR()` must **not** push for itself: it is lifted out by name and executed in Node against a
  stubbed stage, where `snapshot()` does not exist. Calling it from inside would turn a green rule
  into a `ReferenceError` in the very harness that proves the rule.

### 3.4 The loading state always clears

`setBusy(false)` is in a `finally`, because every path above it returns from somewhere, and the one
thing worse than a slow button is a button that never comes back.

`disabled` is what actually stops a second POST (a double press would race two `loadIR()`s and push
two undo steps for one draft). `aria-busy` is the **state**; the CSS pulse is only its costume, so
what the eye is told, a screen reader is told too.

### 3.5 Ctrl+Z in the prompt box is the browser's, not ours

The global key handler deliberately runs undo/redo **in front of** its `editingText()` guard, so that
undo still works with the focus in the size box — which is exactly where the focus is right after the
edit you want to undo.

The prompt textarea is the one control where that is wrong: the user is typing prose, expects their
keystrokes back, and would instead get **their whole deck rolled back**. So the textarea stops the
event locally (`stopPropagation`) rather than widening the global exception — the exception belongs
to this box, not to `<input>` at large.

(`editingText()` already treats `TEXTAREA` as text entry, so `Delete` will not eat a selected element
while you type a prompt. That was already true; I checked rather than assumed.)

### 3.6 Generate dies with the server

`disableExports()` now also disables `b-generate`. The draft comes from the same server as the
export; leaving the button live would offer an action whose only possible outcome is the banner the
user is already reading.

### 3.7 CSS — the one non-obvious rule

`#toolbar label` is a flex **row** (label left, control right), and a textarea in one would be
squeezed to a slit. `#toolbar label.stacked` opts this single control out, by name — specificity
(1,1,1) beats (1,0,1), so it wins cleanly rather than by accident of order.

---

## 4. Tests added (`tests/canvas/test_app.py`) — 17, **not yet run**

Every test is written to survive the endpoint **ceasing to be a mock**. What is under test is the
*contract*: valid `canvas-ir/1`, live SHA, survives the editor's own gate, costs what a model call
would. A real author replaces `mock_ir()` and nothing else — if that swap breaks one of these, it
broke the contract, not the test.

**The one that matters most is `test_the_generated_deck_EXPORTS`**: it feeds what `/api/generate` said
straight into `/api/export`. That closes the loop through the real validator, the real pin check and
the real renderer, and it is the only assertion here that a merely plausible-looking payload could
not satisfy.

Server side: valid payload · exports · live SHA and no literal · is a diagram · prompt not read ·
costs 1.5 s · bad request refused immediately · 6 shapes of missing prompt all 422 · shares the body
guard · writes nothing to disk · imports no network library (greps **every** import line, including
the lazy `import uvicorn` inside `main()`).

Editor side: prompt and button are in the toolbar and **not** in the property panel (which is hidden
whenever nothing is selected — exactly the state you write a prompt in) · posts to `/api/generate` ·
hands off to the same gate · one undo step, pushed by the caller · a refusal costs no undo step · the
loading state always clears · generate dies with the server.

The extractors these lean on (`_js_function`, `_js_code`, `_toolbar`, `_panel`) already exist. I
checked my new JS against their two standing assumptions: **no braces inside any string or comment**
in `generate()` / `setBusy()` (brace-matching would desync), and **no `//` or `/*` inside a string
literal** (comment-stripping would eat code). Both hold.

---

## 5. Gate 1, re-run by hand (it is a grep, so this is the same check)

`test_editor_source.py` scans `editor.js` and `interactions.js` only. Grepped the whole of `editor.js`
after my edit for: the 10 measured-geometry APIs (`offsetWidth`, `clientWidth`, `getComputedStyle`,
`getBBox`, …), `12700`, `zIndex`, `4472C4`, and the banned canvas sizes `1920/1080/1280/720/1440/810`.

**Two hits, both pre-existing and both in the rejection path** (`var FORBIDDEN_COLOR = '#4472C4';` and
the comment above the colour guard) — which is precisely what
`test_accent1_appears_only_in_the_rejection_path` allows. **My additions introduce zero banned
tokens.** `getBoundingClientRect` still appears exactly once, still inside `toModel()`.

---

## 6. What a reviewer should check first

1. **Run `pytest tests/canvas/ -q`.** I could not. Everything else is secondary to this.
2. `test_the_generated_deck_EXPORTS` — if the mock's geometry or a required field is wrong, this is
   where it surfaces, and it surfaces through the real renderer.
3. Open the editor, type anything, press **Generate**, then press **Ctrl+Z**. Your deck should come
   back in one step, and the button should re-enable even if the server 500s.
4. The extraction in `api_export` — it is the only pre-existing code path I touched. It should be
   behaviour-identical (same checks, same order, same codes); confirm the Phase 1B export tests still
   pass, since they are what actually prove that.
