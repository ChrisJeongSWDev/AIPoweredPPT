# Phase 2 — Property Panel & Editor UX: Change Detail

**Scope:** `src/aippt/canvas/static/index.html`, `editor.js`, `style.css`, `tests/canvas/test_app.py`
**Nothing else was touched.** The renderer, the IR, the schema, the server and `interactions.js` are
byte-identical to Phase 1B.

---

## 0. READ THIS FIRST — two problems with the brief, and what I did about them

### 0.1 The brief I was handed was corrupted

The worker brief at `/tmp/tmp.BJvXC3Bgw3` had every `.` character replaced by the literal string
`/c/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/.editwork`. So `editor.js` read as
`editor/c/Users/…/.editworkjs`, and `target_repo: .` read as `target_repo: /c/…/.editwork`. This is a
bad substitution in whatever generated the temp copy — almost certainly a `sed 's|\.|$WORKTREE|g'`
that was meant to expand a placeholder.

**I recovered the intact original from `tasks/AI_Powered_PPT/phase2_brief.md`**, which is byte-clean
and carries the same YAML block. I worked from that. `target_repo: .` therefore means the project
directory, not a worktree.

### 0.2 The brief is also *truncated* — and this was not the copy's fault

`phase2_brief.md` **on disk** ends mid-sentence, inside invariant #1:

> `tests/canvas/test_editor_source.py` (Gate 1) is a plain grep over `editor.js` and

…then a `---` and the YAML block. **Invariants #2 onward do not exist**, and §3 — which the
requirements table explicitly forward-references ("**Tighten it** (see §3)") — was never written. The
acceptance criteria are missing too.

I did **not** guess at the missing rules. Instead I took them from the two places that cannot drift:

- **`tests/canvas/test_editor_source.py`** — Gate 1 says of itself that "this file *is* the spec".
  Every banned name, the one-`getBoundingClientRect` rule, the `/ zoom` rule, the 960×540 rule and the
  `#4472C4` rule are read straight from it.
- **`phase2_draft_brief.md`** — the pre-read draft, which survived intact and names the four
  requirements plus the `HEADER_RESERVED`/`FOOTER_RESERVED` and `applyConstraints()` constraints.

**Both files should be regenerated.** The truncation is upstream of me and will bite the next phase.

### 0.3 The `.editwork` worktree was a dead end (and could never have worked)

The brief's task directory contained a `.editwork` git worktree created at the same timestamp as the
brief. It is **empty of this project**, and structurally had to be: `git ls-files tasks/AI_Powered_PPT`
returns **0 files** — the entire AI_Powered_PPT project is untracked. A git worktree can only ever
materialise tracked content, so no worktree will ever contain this project. (The directory has since
been auto-removed; `git worktree list` still lists it as stale.)

**I edited in place** at `tasks/AI_Powered_PPT/`. If the orchestrator expects worktree isolation for
this task, that expectation cannot be met until the project is committed.

### 0.4 I could not run the test suite — this is the one caveat that matters

This sandbox's permission layer **denies all code execution**. `python --version` and `node --version`
are allowed; `python -m pytest …`, `node script.js` and `node -e …` are all refused, and the session is
non-interactive so no approval can be granted. I did not attempt to route around the denial.

So: **`pytest tests/canvas` has NOT been run against this change. Someone must run it.**

What I did instead, and how far it actually goes:

| Gate | How I verified it | Confidence |
|---|---|---|
| **Gate 1** (`test_editor_source.py`) | It *is* a substring grep. I ran every one of its assertions with ripgrep — see §5. | **High** — same mechanism, same strings. |
| **Gate 4b** (import gate, Node) | `loadIR()` and every function the harness lifts are **byte-identical** to Phase 1B (§4.5). The harness cannot see my changes. | **High** — by construction. |
| **New Phase 2 tests** | Written but **never executed**. | **Low** — treat as unrun code. |
| **Runtime behaviour** in a browser | Not exercised at all. | **None.** |

The new tests in §6 are the part most likely to contain a mistake, because they are the only new code
that has never run. I found and fixed three bugs in them by re-reading (a missing `import re`; an
assertion that would have tripped over the word "contenteditable" *in its own explanatory comment*;
and an over-clever string slice). There may be more.

---

## 1. What Phase 2 actually was

The brief's own table is right, and it changed the shape of the work:

| Requirement | State at Phase 1B | What I did |
|---|---|---|
| Property panel | Controls **all existed**, in the **left** toolbar, **always visible** | **Relocated** to a right panel that appears on selection. Added `run.bold` / `run.italic`. |
| Double-click to edit | **Worked**, but `contenteditable="true"` was **permanent** | **Tightened**: the attribute now appears and disappears. |
| Delete / Backspace | **Worked** | **Left alone** — and pinned by a regression test. Made undoable. |
| Undo / Redo | **Did not exist** | **Built.** This was the real work. |

I did not rewrite the three that worked.

---

## 2. Undo / redo — the real work

### 2.1 Snapshots, not inverse commands

A command stack needs an inverse per mutation. Move and resize invert easily; **raise/lower** reorder
the DOM, **delete** must remember its z-position, **load** replaces the whole stage, **duplicate**
mints an id. Every inverse that is subtly wrong is a silent corruption that surfaces three undos
later, somewhere else. A snapshot has exactly one inverse and every mutation shares it.

A snapshot is **JS state only**: `read(el)` for each element (dataset), the `.body` `innerHTML` (the
runs live in the DOM — `normalizeText()` reads them back out), **DOM order** (which *is* the z-order),
and the title. Restoring rebuilds through `makeEl()` — back down the same one-way `state → CSS` path
every other write takes.

**This is why undo cannot break the Prime Directive**: it never reads geometry out of the DOM, because
it never had to. It re-runs the writes.

`zoom` and the current tool are **not** in a snapshot. They are view, not document.

### 2.2 Gesture grouping — the thing that makes it usable

A drag commits a frame per `pointermove`. Ungrouped, one drag would be ~100 undo steps.

```
beginTx()   at gesture start  -> ONE snapshot
commit()    on first success  -> pushes it (once)
endTx()     at pointerup      -> drops it if nothing was ever committed
```

The last line is what stops a click-that-merely-selects from costing a history entry.
`interactions.js` already forwarded `end` from both `draggable` and `resizable`, so no change was
needed there.

**Property controls are gestures too.** A colour picker and a range slider fire `input` continuously;
`txControl()` opens the step on `pointerdown`/`keydown` and closes it on `change` (which fires once).
`#p-zoom` is deliberately *not* wired in.

### 2.3 Where each mutation pushes

| Mutation | Where |
|---|---|
| move / resize / rotate / property edit | `commit()` — the one door state changes through |
| create (drag-out) | draw handler, once, at creation (carries its own `before`; see below) |
| delete / duplicate / raise / lower | explicit `pushUndo(snapshot())` **before** mutating |
| text edit | `dblclick` opens the tx, `input` pushes, `stopEditing()` closes it |
| title edit | `focus` / `input` / `blur` |
| **load JSON** | **the caller**, not `loadIR()` — see §4.5 |

**A refused frame costs nothing.** `commit()` takes its snapshot *after* `applyConstraints()` has
returned non-null. Dragging a box against the header does not fill the stack.

**The draw path deliberately does not use a transaction.** It calls `select()` the moment it creates
its element, and `select()` closes any open text session — which would end our transaction and take
the snapshot with it. So it carries `ctx.before` and pushes exactly once.

### 2.4 Keyboard

`Ctrl+Z` undo, `Ctrl+Y` / `Ctrl+Shift+Z` redo — handled **in front of** the `editingText()` guard,
because the property panel is made of `<input>`s and an undo that stopped working while focus was
still in the size box is an undo nobody trusts.

**The one exception is a live `contenteditable`.** Inside the text, the browser's per-keystroke undo
is what a user expects; ours is per-session and would throw away the paragraph. We stand back. The
snapshot taken when the caret went in still makes the whole edit one step from *outside*.

---

## 3. The property panel

`<aside id="props" hidden>`, third grid column (`auto`, so it collapses to zero when hidden).

- **Hidden until something is selected.** In Phase 1B these inputs were live and inert at the same
  time: with an empty selection `patchSelected()` swallowed every edit.
- **Scoped by type** via `data-for="shape"` / `data-for="connector"`. The IR gives a connector no
  fill, no text and no rotation — offering those controls means offering a property that cannot be
  serialized, and the `if (isConnector()) return` guards would eat the edit in silence.
- **Undo/Redo stayed in the left toolbar**, because they are the one pair that must work with
  *nothing* selected — which is exactly the state the panel is hidden in. Undo after a delete is the
  whole point of undo, and after a delete there is no selection.

### The CSS specificity trap (this is a real bug, not a style nit)

`[hidden]` is a UA rule at specificity `(0,0,1,0)`. `#props label { display: flex }` is `(0,1,0,1)` —
**the ID selector wins**. A `hidden` label would be announced as hidden, excluded from the
accessibility tree, and *still painted and still clickable*. The `data-for` scoping would silently do
nothing.

`#props [hidden] { display: none }` is `(0,1,1,0)` and beats it. Both that rule and `#props[hidden]`
are load-bearing, and `test_the_hidden_attribute_actually_hides_inside_the_panel` pins them.

---

## 4. `run.bold` / `run.italic` — the two missing IR properties

Confirmed supported: `schema.json:294-295` (`{"type": "boolean", "default": false}`) and
`style.py:132-133` (`run.font.bold` / `run.font.italic`).

These are **element-level controls over a per-run property**, and that asymmetry is the whole
difficulty.

### 4.1 On

Set `el.dataset.bold = '1'`. `normalizeText()` **ORs it into every run** on the way out — exactly the
relationship `size` and `color` already have with the runs. `style.css` previews it via
`.el[data-bold='1'] .txt { font-weight: 700 }`. Nothing is written into the body.

### 4.2 Off — and why it must also strip tags

`run.bold` comes from `<b>`/`<strong>` **in the body** as well as from the flag —
`paragraphsToHTML()` writes them on import, and a paste or the browser's own `Ctrl+B` will too. An
"off" that merely stopped *adding* bold would leave the text bold on screen and in the `.pptx`, with
the button showing un-pressed. The control would look broken **because it would be broken**.

So `setTextFlag(…, false)` also unwraps `<b>`/`<strong>` (resp. `<i>`/`<em>`) from the body.
`<strong>`/`<em>` are included because that is what several editors and pastes produce.

**Honest cost:** turning bold off on an element whose runs were only *partly* bold flattens that
distinction. "Make this element not bold" is what the button says and what it does.

### 4.3 The round-trip trap — why `stateFromIR()` counts instead of peeking

`size` and `color` are read off the **first** run. **Reading `bold` the same way would be actively
destructive.** The flag is OR-ed back into *every* run on export, so a deck with one bold word in a
plain sentence would reload with the flag ON and **re-export with the whole sentence bold**. A round
trip must not change the deck.

So the flag is a **summary**: on only when *every* run is bold. Mixed runs summarise to OFF and their
own `<b>`/`<i>` tags carry the per-run bold instead. Nothing is lost either way, and the round trip is
stable. `nRuns > 0` is load-bearing: without it, a textless rect gives `0 === 0` and comes back
**bold**.

### 4.4 No regression to per-run bold

A `<b>` inside the body still bolds its own run with the flag off. The flag is *additive*, never a
replacement. Pinned by
`test_a_b_tag_inside_the_body_still_bolds_its_own_run_with_the_flag_off`.

### 4.5 `loadIR()` and friends are byte-identical — on purpose

`test_app.py` (Gate 4b) **lifts `loadIR()` out of `editor.js` by name and runs it in Node** against a
stubbed stage. A call to `snapshot()` or `pushUndo()` from inside it would be a `ReferenceError` **in
the harness** — a green rule failing in the very test that proves it.

So the import pushes its undo step **from the caller** (`#f-load`'s change handler), which is also the
only place that knows whether `loadIR()` actually *accepted* the file. A refused import costs no step.

For the same reason, `stateFromIR()`'s new run-summary loop is **inlined** rather than factored into a
helper: the harness lifts `stateFromIR` but would not lift the helper.

`paragraphsToHTML()` is untouched — `test_a_run_with_no_text_does_not_crash_the_import` asserts its
output byte-for-byte.

---

## 5. Gate 1, re-run by hand (it is a grep, so this is the same check)

| Assertion | Result |
|---|---|
| `getBoundingClientRect` appears exactly once | ✅ 1, at `editor.js:98`, inside `toModel()` |
| 10 banned measurement APIs absent | ✅ 0 hits |
| `ev.rect` / `event.rect` absent | ✅ 0 hits |
| every `deltaRect.*` read divided by `/ zoom` on the same line | ✅ 4 reads (718–721), all divided |
| no `12700`, no `zIndex`, no `z-index` | ✅ 0 hits |
| `canvas-ir/1`, `{w: 960, h: 540, unit: 'pt'}`, `#FF0032` present | ✅ |
| no other canvas size (`1920/1080/1280/720/1440/810`) | ✅ 0 hits |
| `#4472C4` only in the rejection path | ✅ 2 hits — `FORBIDDEN_COLOR` (53), "is refused" (1111) |
| `interactions.js` measures nothing | ✅ unmodified |

I kept the new code clear of those digit strings deliberately (`HIST_MAX = 100`).

---

## 6. Tests added (`tests/canvas/test_app.py`, Gate 5) — **not yet run**

Structural (never skip): panel exists and ships `hidden`; every IR property has a control **and it is
in the panel**; no control left behind in the toolbar; undo/redo in the toolbar; the CSS specificity
override exists; `data-for` scoping is acted on; `contenteditable` is not hard-coded in `makeEl()`;
dblclick adds it and `stopEditing()` removes it; `.txt` is still pointer-transparent until `.editing`
(the single-click-drag regression); **Delete/Backspace still works and is still behind
`editingText()`**; undo is wired through `commit()`; delete/duplicate push their own step; a refused
frame pushes nothing; `restore()` goes through `makeEl()` and measures nothing; `loadIR()` contains no
history calls; zoom is not undoable.

Node-executed (skip without node): the element flag folds into every run; a `<b>` still bolds its run
with the flag off; a plain run stays plain; **the flag is a summary of all runs, not the first**
(mixed → OFF, both orders); italic likewise; a textless element is neither; `setTextFlag` unwraps
`<strong>`/`<em>` as well as `<b>`/`<i>`.

---

## 7. What a reviewer should check first

1. **Run `pytest tests/canvas`.** I could not. This is the top item by a distance.
2. **Open the editor and drag something.** No browser ever loaded this code.
   Specifically: does one drag produce exactly one undo step? Does a click-that-selects produce none?
3. The **`change`-listener ordering** on `<select>` controls: `txControl`'s `endTx` is registered
   before the `patchSelected` handler, so `endTx` runs first and `commit()` falls back to its own
   `before` snapshot. I traced this and it yields exactly one correct step — but it is the subtlest
   thing in the diff and it deserves a second pair of eyes.
4. Regenerate `phase2_brief.md` (§0.2) — it is truncated at source.
