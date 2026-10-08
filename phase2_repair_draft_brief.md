# Phase 2 Repair: Codex Critic Rejection

## Context
You (Claude Main) previously implemented Phase 2 (Property panel, double-click to edit, Undo/Redo). The tests passed, but the Codex Critic rejected your implementation.

## Critic Verdict
`VERDICT: REJECT`

`restore()` (or the undo/redo restore logic) clears the stage and sends snapshot geometry directly through `makeEl()`/`appendChild()` without `illegalReason()`. Add an all-or-nothing, non-transforming legality preflight before touching the DOM; also defer the history `pop()` operations until restoration succeeds.

The test at `test_app.py:910` verifies only reconstruction and absence of measurement, so it misses this bypass.

## Requirements for Fix
1. Modify the `restore()` function (or whatever handles the history snapshot restoration in `editor.js`) to run a legality preflight over ALL elements in the snapshot using `illegalReason()`.
2. Do this BEFORE modifying the DOM. If any element is illegal, abort the restoration.
3. Ensure the history stack `pop()` operations are deferred until the preflight passes.
4. Add or update tests in `tests/canvas/test_app.py` to ensure that an invalid snapshot restoration fails without touching the DOM or popping the history stack.

## Rules for claude-review
- Read `editor.js` and `test_app.py` to identify the exact lines of `restore()`.
- Add explicit instructions to fix the vulnerability.
- Do NOT rewrite or disable other working features.
- Append the standard YAML metadata block at the end:
```yaml
---
claude_model: opus
mode: continuation
target_repo: .
change_detail_path: tasks/AI_Powered_PPT/phase2_repair_change_detail.md
write_scope: src/aippt/canvas/static/editor.js, tests/canvas/test_app.py
```
