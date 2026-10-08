# Draft Brief: Phase 1 Renderer (Slide Cloning Architecture)

## Context
In the previous session, Codex Critic (Q3) blocked the " 빈 레이아웃 추가(add_slide) " architecture because the company's PPTX template uses slide-level freeform shapes for its designs, rather than clean semantic layout placeholders.
The new strategy is **Slide Cloning**: we will copy an existing beautifully designed slide from the template (one of the 23 native slides) and simply swap out the text and images within the cloned shapes.

## Objectives
1. **Slide Cloning Utility**: Implement a reliable way to clone a slide in `python-pptx` (including its shapes and relationships, using `lxml` if necessary).
2. **Content Replacement**: Implement a deterministic mapping that finds the target text boxes/images on the cloned slide and replaces them with the JSON IR content.
3. **Brand Color Enforcement**: Force tables, charts, or specific shapes to use the company red: `RGB(255, 0, 50)`.
4. **IR Schema Pivot**: Update `src/aippt/ir/schema.json` and `models.py` so that a slide specifies a `source_slide_index` (the index of the template slide to clone) rather than a `layout_id`.

## Instructions for claude-review
Analyze the feasibility of this Slide Cloning approach in `python-pptx`.
- `python-pptx` does not have a native `slide.copy()` method. Provide a robust `lxml`-based recipe or strategy for slide cloning that the main worker can implement.
- How will the renderer identify which shape gets which text? (e.g., by shape name, type, or z-order?) Define a robust mapping contract.
- Enhance this draft into a comprehensive `renderer_brief.md` for `claude-main` (Opus) to execute. Provide precise `write_scope` definitions.
