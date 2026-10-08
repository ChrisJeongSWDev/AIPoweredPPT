# Phase 1B Repair Brief — the JSON import path must go through the SAME gate as the mouse

## Why this is coming back to you

Phase 1B landed with 302 tests green, and Codex Critic confirmed requirements 1, 2, 3, 5 and 6 pass
and that the reserved-region constants are ported correctly. It **REJECTED** on requirement 4 —
*enforcement* — because there is exactly one way into the stage that skips the constraint pipeline:

> - `editor.js:1111` loads JSON elements without validating their geometry.
> - `editor.js:1145` calls `makeEl(s)` directly, bypassing `applyConstraints()`. Thus imported
>   elements can intersect `HEADER_RESERVED` or `FOOTER_RESERVED`, enter the DOM, and be
>   reserialized.
>
> Fix lines 1111–1146 by validating every imported element with the same bounds, rotated-AABB, and
> reserved-region checks before modifying the stage. Reject the entire import if any element is
> illegal, and add header/footer import regression tests.

The critic is right, and it is worse than it looks. **Four** defects live in `loadIR()`:

| # | Site | Defect |
|---|---|---|
| 1 | `editor.js:1145` | `makeEl(s)` with no geometry check at all. An element sitting on the logo imports, renders, serializes, and comes back as a 422 the user cannot explain — from a file the editor itself may have written before someone hand-edited it. |
| 2 | `editor.js:1116-1118` | The stage is **cleared and the title overwritten before the elements are looked at**. Even a correct per-element check bolted into the loop would leave a half-imported stage behind on the first bad element. The critic's "reject the entire import" is not achievable inside that loop. |
| 3 | `editor.js:1132` | `x: e.x` with no numeric guard. A missing or non-numeric coordinate becomes `+undefined` → `NaN` in `read()`, and **every comparison against `NaN` is `false`** — so `outOfBounds()` returns `false`, `intersects()` returns `false`, and the element passes a *correct* geometry check. This is the trap: fix defect 1 without fixing this one and the gate still has a hole you can drive a deck through. |
| 4 | `editor.js:1129`, `:1155` | `text.paragraphs[0].runs[0]` and `p.runs.map(...)` are unguarded. A paragraph without `runs` is a `TypeError` mid-import — thrown *after* the stage was already cleared (defect 2), so the user loses their deck to a malformed file. |

Requirement 4 says the reserved regions are **strictly enforced in the JS**. Right now they are
enforced against the mouse and not against a file. Close it so that there is exactly **one** door
into the stage and it is locked.

---

## The design: one legality rule, two callers

### Step 1 — extract the legality rule out of `applyConstraints()`

`applyConstraints()` today does two different jobs in one function: it **transforms** a candidate
(min-extent, snap, clamp-into-slide) and then it **judges** it (bounds + reserved regions, lines
232-237). Only the judging half may be reused by the import path. Split it:


---

claude_model: opus
mode: continuation
target_repo: .
change_detail_path: tasks/AI_Powered_PPT/phase1b_repair_change_detail.md
write_scope: src/aippt/canvas/static/editor.js, tests/canvas/test_app.py
