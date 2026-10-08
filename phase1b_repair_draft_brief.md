# Phase 1B Repair Draft Brief

## Context
Claude Main implemented Phase 1B, but Codex Critic rejected it due to a validation bypass during JSON import.
Codex Critic output:

```
VERDICT: REJECT

Requirements 1, 2, 3, 5, and 6 pass. The reserved-region constants are also correct, but enforcement has one bypass:

- editor.js:1111 loads JSON elements without validating their geometry.
- editor.js:1145 calls `makeEl(s)` directly, bypassing `applyConstraints()`. Thus imported elements can intersect `HEADER_RESERVED` or `FOOTER_RESERVED`, enter the DOM, and be reserialized.

Fix lines 1111–1146 by validating every imported element with the same bounds, rotated-AABB, and reserved-region checks before modifying the stage. Reject the entire import if any element is illegal, and add header/footer import regression tests.
```

## Instructions for claude-review
Read the Codex Critic output above and the current `editor.js` and `test_editor_source.py` / `test_app.py`.
Produce a detailed `phase1b_repair_brief.md` for `claude-main` (Opus) that ensures this validation hole is closed tightly exactly as Codex Critic expects.
Ensure the `write_scope` covers `src/aippt/canvas/static/editor.js` and the relevant test file.
