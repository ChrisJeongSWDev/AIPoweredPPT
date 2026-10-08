# Phase 2 Repair Brief — `restore()` is the third door into the stage, and it is unlocked

## Why this is coming back to you

Phase 2 landed green and Codex Critic **REJECTED** it:

> `restore()` (or the undo/redo restore logic) clears the stage and sends snapshot geometry directly
> through `makeEl()`/`appendChild()` without `illegalReason()`. Add an all-or-nothing,
> non-transforming legality preflight before touching the DOM; also defer the history `pop()`
> operations until restoration succeeds.
>
> The test at `test_app.py:910` verifies only reconstruction and absence of measurement, so it misses
> this bypass.

The critic is right, and you already know the shape of the fix because **you wrote it last phase**.
This is the Phase 1B `loadIR()` bug, in a new function. Read `loadIR()` (editor.js:1625–1682) before
you touch anything: it is the reference implementation, and your repair must look like it.

You also wrote the sentence that this bug makes false. `editor.js:193–194`:

> `illegalReason()` below is the judge, and it is the **ONLY door** into the stage: the mouse goes
> through it via `applyConstraints()`, and a file goes through it via `loadIR()`.

There is a third door. It is `restore()`, and it has no lock on it.

---

## The defects, exactly

`restore()` is `editor.js:437–456`. Its only two callers are `undo()` (`editor.js:488`) and `redo()`
(`editor.js:498`).

| # | Site | Defect |
|---|---|---|
| 1 | `editor.js:448–449` | `makeEl(rec.state)` + `stage.appendChild(el)` with **no call to `illegalReason()`**. Snapshot geometry is trusted absolutely. The comment on line 448 — *"a restore is not an edit and must not be judged"* — conflates two different things: a restore must not be **transformed** (not snapped, not clamped, not re-pushed onto the stack), and that is correct. It does not follow that it must not be **judged**. `illegalReason()` transforms nothing; that inertness is the entire reason it exists as its own function. Judging is free. Delete that half of the comment. |
| 2 | `editor.js:439–443` | The stage is **cleared and the title overwritten before a single element has been looked at**. Identical to the Phase 1B `loadIR()` defect. A per-element check bolted into the loop at 446 cannot produce "abort the restoration" — by the time the loop runs, the user's deck is already gone. All-or-nothing is not reachable from inside that loop. It is reachable from above it. |
| 3 | `editor.js:488`, `editor.js:498` | `restore(past.pop())` and `restore(future.pop())`. The `pop()` is evaluated **as the argument** — the entry is off the stack before `restore()` has done anything. If the restore aborts (your new preflight) or throws (`makeEl()` on a malformed record), the stage is cleared *and* the snapshot that would put it back has been destroyed. The user loses the deck and the undo step in one keystroke. |
| 4 | `editor.js:438` | `stopEditing()` is the first statement, and it **mutates the DOM** (drops `.editing`, removes the `contenteditable` attribute) and calls `endTx()`. Your preflight must run **above** it. "Before touching the DOM" means before line 438, not before line 439. |

### Be honest with yourself about reachability, then fix it anyway

Trace it and you will find that every element currently in the DOM was judged on the way in —
`commit()`, `loadIR()`, and `duplicateSelected()` (which routes through `applyConstraints()` at
`editor.js:1306`) are the three writers, and all three call the judge. So a snapshot taken by
`snapshot()` off a legal stage is itself legal, and you will **not** find a click-by-click repro
where an illegal element gets restored today.

That argument is exactly as strong as its weakest inductive step, and it is not the argument the code
makes — the code makes an *unconditional* claim on line 193 that `illegalReason()` is the only door.
Right now that claim survives only because nobody has yet added a fourth writer. The next feature that
writes `dataset` (a paste handler, an alignment tool, an arrow-key nudge) inherits a stage where undo
will happily reintroduce whatever it wrote, and the reserved-region guarantee — the thing the backend
returns 422 on — dies quietly, three phases from now, in a function nobody suspects.

Defect 3 needs no induction at all: it is a live, unconditional data-loss path the moment anything
inside `restore()` throws.

Fail closed. That is the whole job.

---

## The design

### Step 1 — one preflight function, next to the judge

Add it directly below `illegalReason()` (i.e. after `editor.js:263`), so the rule and its second
caller sit in one place. It **reads and returns; it mutates nothing and it touches no DOM**.



---

claude_model: opus
mode: continuation
target_repo: .
change_detail_path: tasks/AI_Powered_PPT/phase2_repair_change_detail.md
write_scope: src/aippt/canvas/static/editor.js, tests/canvas/test_app.py
