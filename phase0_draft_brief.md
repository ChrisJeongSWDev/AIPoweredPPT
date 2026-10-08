# Phase 0: Foundations - Task Brief

## Goal
Execute Phase 0 of the `HTML_to_PPTX_Plan.md`. Create a clean renderer template (0 slides) from the existing 23-slide template, setup template pinning/validation to fail-closed on mismatch, and create a calibration slide generator.

## Requirements
1. **Never modify `Vieworks_R&D_ppt_Template.pptx`**. All output must go to `reference/renderer_template.pptx`.
2. Implement `src/aippt/tools/make_renderer_template.py` (which removes all 23 slides but keeps all 5 layouts and media).
3. Implement `src/aippt/canvas/pin.py` and `reference/template_pin.json` to verify the SHA256 and layout signature at startup.
4. Implement `src/aippt/tools/calibrate.py` to generate a calibration slide.

## Write Scope
- `src/aippt/tools/make_renderer_template.py`
- `reference/template_pin.json`
- `src/aippt/canvas/pin.py`
- `src/aippt/tools/calibrate.py`

## Instructions for claude-review
Review this draft brief against `HTML_to_PPTX_Plan.md` (Phase 0). Ensure all requirements, corner cases (like dropping relationships before deleting slide IDs in the template builder), and verification gates (smoke testing logic) are clearly explained for `claude-main`. Output a strengthened brief to `tasks/AI_Powered_PPT/phase0_brief.md`.
