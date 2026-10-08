# Phase 0: Foundations - Strengthened Task Brief

## Goal
Execute Phase 0 of the `HTML_to_PPTX_Plan.md`. Create a clean renderer template (0 slides) from the existing 23-slide template, setup template pinning/validation to fail-closed on mismatch, and create a calibration slide generator.

## Requirements

1. **Never modify `Vieworks_R&D_ppt_Template.pptx`**. All output must go to `reference/renderer_template.pptx`.
2. **`make_renderer_template.py` Landmine:** Do NOT touch `prs.slides` inside the slide deletion loop! Calling `prs.slides` triggers `rename_slide_parts()`, which will throw a `KeyError` if the package is transiently inconsistent. Bind `sld_id_lst = prs.slides._sldIdLst` once, iterate over it, call `drop_rel(rId)` and `sld_id_lst.remove(sld_id)`, and never access `prs.slides` again until the loop is done.
3. **Pin Generation:** Do not hardcode the `layout_signature` (e.g. `placeholder_idxs: [10]`) in `pin.json` by guessing. The builder `make_renderer_template.py` MUST inspect the final `prs` and emit the observed signature to stdout or directly to `template_pin.json` so we pin the reality.
4. **`pin.py` Architecture:** Split `pin.py` into three functions:
   - `load_pin() -> dict`
   - `verify_pin(pin: dict) -> None`
   - `open_renderer_template(pin: dict) -> Presentation`
5. **Phase 0 Isolation (`calibrate.py`):** `calibrate.py` requires EMU conversion and shape overrides. Do not create `canvas/geometry.py` or `canvas/style.py` yet (those are Phase 1). **Inline** the required `add_shape` overrides and EMU conversions directly into `calibrate.py` to keep Phase 0 strictly isolated.
6. **Smoke Testing & Human Verification:** Output a checklist to `HUMAN_VERIFICATION.md` for the following manual checks:
   - PowerPoint opens clean
   - Page number on added layout 3 reads "1"
   - SVG logo survives conversion
   - Raster diff is <= 2px

## Write Scope
- `src/aippt/tools/make_renderer_template.py`
- `reference/template_pin.json`
- `src/aippt/canvas/pin.py`
- `src/aippt/tools/calibrate.py`
- `HUMAN_VERIFICATION.md`

## Instructions for claude-main (Opus)
Read this brief and `HTML_to_PPTX_Plan.md`. Implement the scope above. Do not proceed to Phase 1. When done, Codex Critic will review your work.

claude_model: opus
target_repo: .
change_detail_path: tasks/AI_Powered_PPT/phase0_change_detail.md
write_scope: src/aippt/tools/make_renderer_template.py, reference/template_pin.json, src/aippt/canvas/pin.py, src/aippt/tools/calibrate.py, HUMAN_VERIFICATION.md
