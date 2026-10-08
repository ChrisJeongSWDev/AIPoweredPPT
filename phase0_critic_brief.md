# Codex Critic Review: Phase 0 Implementation

## Context
Claude Main (Opus) has just finished implementing Phase 0 of the PPTX Renderer project.
The goal was to produce a clean renderer template, pinning logic, and a calibration tool, strictly following the rules in `phase0_brief.md` and `HTML_to_PPTX_Plan.md`.

## Files to Review
- `src/aippt/tools/make_renderer_template.py`
- `reference/template_pin.json`
- `src/aippt/canvas/pin.py`
- `src/aippt/tools/calibrate.py`
- `HUMAN_VERIFICATION.md`

## Your Task (codex-critic)
Review the implementation and verify that all constraints were strictly followed:
1. **Landmine Avoidance**: In `make_renderer_template.py`, ensure `prs.slides` is NEVER accessed inside the slide deletion loop (to prevent `rename_slide_parts()` crash).
2. **Dynamic Pinning**: Ensure `make_renderer_template.py` observes and generates `template_pin.json` dynamically from the mutated package, rather than hardcoding guessed layout signatures.
3. **Pin Architecture**: Verify `pin.py` contains exactly the three functions: `load_pin()`, `verify_pin(pin)`, and `open_renderer_template(pin)`.
4. **Phase Isolation**: Verify `calibrate.py` inlines its EMU conversions and overrides, avoiding premature creation of Phase 1 files like `geometry.py`.
5. **XML Correctness**: Verify the `drop_rel` happens BEFORE `sldIdLst.remove(sld_id)` as required by python-pptx internals.

If the implementation meets all requirements and safety constraints, output exactly:
`VERDICT: APPROVE`
Followed by a brief explanation of your verification.
If it fails any constraint, output `VERDICT: REJECT` and detail the exact code lines to fix.

Output your findings to stdout.
