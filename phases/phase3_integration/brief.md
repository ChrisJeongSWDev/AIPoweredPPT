---
target_repo: tasks/AI_Powered_PPT
write_scope:
  - tasks/AI_Powered_PPT/src/aippt/adapters/ai_adapter.py
claude_model: sonnet
change_detail_path: tasks/AI_Powered_PPT/tasks/phase3_integration/change_detail.md
phase: phase3
---
# Phase 3: Integration of Headless Worker Client into Generative Pipeline

## Objective
Implement the four generative functions in `tasks/AI_Powered_PPT/src/aippt/adapters/ai_adapter.py` (`build_system_prompt`, `generate_outline`, `fill_slide`, `generate_deck`) using the `CliWorkerClient` we verified in Phase 2.

## Instructions
1. **`build_system_prompt`**: Read `prompts/00_system_deck_author.md` and replace `{{LAYOUT_CATALOG}}` with `catalog_md`.
2. **`generate_outline`**: 
   - Read `prompts/10_outline_storyboard.md` and substitute `{{TOPIC}}`, `{{SOURCES}}`, and `{{TARGET_SLIDES}}` (using `\n`.join(sources)).
   - Call `client.complete_json(system=system_prompt, user=user_prompt, schema=outline_schema)`.
   - Ensure the outline schema expects an object with `"slides"` and `"rationale"`. Return `slides`.
3. **`fill_slide`**:
   - Extract the placeholder budget for `outline_entry["layout_id"]` from the `manifest`.
   - Format the budget clearly.
   - Read `prompts/20_slide_fill.md` and substitute `{{OUTLINE_ENTRY}}`, `{{LAYOUT_ID}}`, `{{SEMANTIC_ROLE}}`, `{{LAYOUT_BUDGET}}`, `{{SOURCES}}`, and `{{REPAIR_NOTE}}`.
   - Call `client.complete_json` using the IR schema (or load it from `ir.models.load_schema()` wait, we might need a slide schema from `load_schema()["$defs"]["Slide"]` but we can just use the `Slide` object schema).
   - Actually, just use the `ir.models.load_schema()` and maybe wrap it or use the top level `$defs` -> `Slide` definition. (If needed, construct a single schema for `Slide`).
4. **`generate_deck`**:
   - Tie it together: call outline, then loop to fill each slide.
   - Implement the bounded repair loop (`max_repairs=2`). If validation fails, append the error to `{{REPAIR_NOTE}}` and retry `fill_slide`.
   - Return a `GenerationResult` object.

## Repair Instructions (from codex-critic)
The reviewer blocked your previous patch with the following feedback:
> `generate_deck` accepts any manifest-valid `layout_id` returned by `fill_slide`; it never verifies it matches `entry["layout_id"]`. This breaks the stage-1 layout decision and can validate content against one layout’s budget while rendering it with another’s.
> Raise `CliWorkerSchemaError` when the returned slide layout differs from the outline entry, so the existing repair loop retries it.

> `generate_deck` promises a bounded repair loop for content-budget failures, but the diff never checks any slide content against the manifest budgets. `_parse_and_validate_slide` only validates IR structure and layout existence, so overflowing content is accepted and never re-prompted. This contradicts the function contract and leaves the primary rendering failure unhandled.

> `generate_deck()` now unconditionally calls `check_budget()`, but `render/fit.py:check_budget` is still `NotImplementedError`. Thus every otherwise-valid filled slide aborts before a `GenerationResult` can be returned; the retry loop cannot handle it.
> `_check_slide_budget()` never checks `slide.title` for the supplied manifest: all its placeholders have BODY budgets and none contain `max_title_chars_cjk`, so `title_ph` remains `None`. This leaves title overflow unvalidated.
> `_check_slide_budget()` only compares each block’s total character count to `max_bullets * max_chars_per_bullet`. It misses per-item line rounding: e.g., four 11-character bullets in a 6×10-character placeholder total 44 and pass, but each wraps to two lines (8 lines total), so it overflows. This bypasses the repair loop despite the manifest’s “a bullet that wraps consumes another slot” rule.

Please implement these fixes in `generate_deck`. You must implement the budget checking logic LOCALLY in `_check_slide_budget` or similar. DO NOT just sum the characters! You must calculate the number of lines each bullet takes by doing `math.ceil(len(bullet) / max_chars_per_bullet)`, and sum those lines to ensure it is `<= max_bullets`. ALSO, make sure you validate `slide.title` properly.

Please implement these functions by replacing their `NotImplementedError` bodies with robust Python code. Use `pathlib` for file reads. Be careful with json schemas and ensure `client.complete_json` handles the output correctly.
