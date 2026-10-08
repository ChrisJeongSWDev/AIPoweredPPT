# Phase 2: Property Panel & Editor UX — Task Brief

## Goal

Give the Phase 1B editor a **right-side property panel that appears when an element is selected**, and
finish the UX contract: **double-click to edit**, **Delete/Backspace to remove**, and — the one thing
that genuinely does not exist yet — **Undo / Redo**.

The renderer, the IR, the server and the existing acceptance gates are **frozen and green**. You are
polishing the editor's front end inside a set of rules that already have machine-checked teeth. Every
rule below that reads like nagging is a rule a test will enforce anyway; the only question is whether
you find out in `pytest` or in a code review.

---

## READ THIS FIRST: three of the four requirements are already implemented

The draft brief was written from the plan, not from the shipped code. I read the shipped code. Here is
the truth, and it changes what you should do:

| Requirement (draft) | Actual state in `editor.js` @ Phase 1B | What Phase 2 actually is |
|---|---|---|
| Property panel | The controls **all exist** — `#p-fill`, `#p-stroke`, `#p-stroke-w`, `#p-color`, `#p-size`, `#p-align`, `#p-valign`, `#p-kind`, `#p-arrow`, `#p-rot` — wired through `patchSelected()` and reflected by `syncProps()` (editor.js:945–1067). They sit in the **left** `#toolbar` and are **always visible**, even with nothing selected. | **Relocate**, don't rebuild. Move them into a right-side panel that shows on selection. **Add the two missing IR properties: `run.bold` and `run.italic`.** |
| Double-click to edit | **Already done.** `el.addEventListener('dblclick', …)` adds `.editing` (editor.js:593–600); `style.css:285-287` keeps `.txt { pointer-events: none }` until `.el.editing`. A single click selects and drags. | **Tighten it** (see §3): `.body` currently carries `contenteditable="true"` **at all times** — only CSS is stopping the caret. Make the attribute itself appear on double-click and disappear on exit. |
| Delete / Backspace | **Already done.** editor.js:1078–1081, guarded by `editingText()` so it does not fire while typing. | **Keep it, and make it undoable.** Do not rewrite it. |
| Undo / Redo | **Does not exist.** Phase 1B explicitly deferred it ("Undo/redo is out of scope (deferred)"). | **This is the real work of Phase 2.** |

**Do not "reimplement" the three that work.** A regression in double-click or Delete costs you a whole
phase and buys nothing. Read `editor.js` end to end before you touch a line of it.

---

## The invariants you are working inside (all machine-checked — none of them are advice)

### 1. THE PRIME DIRECTIVE

> `getBoundingClientRect()` appears **exactly once** in `editor.js`, inside `toModel(ev)`.
> Nothing else may measure the DOM. Ever.

Geometry lives in JS state (`el.dataset`) and flows **one way** into CSS and SVG attributes. It is
never read back. `tests/canvas/test_editor_source.py` (Gate 1) is a plain grep over `editor.js` and

---

claude_model: opus
mode: continuation
target_repo: .
change_detail_path: tasks/AI_Powered_PPT/phase2_change_detail.md
write_scope: src/aippt/canvas/static/index.html, src/aippt/canvas/static/editor.js, src/aippt/canvas/static/style.css, tests/canvas/test_app.py
