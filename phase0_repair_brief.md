# Phase 0 Repair Brief

## Goal
Fix the architectural violations in `src/aippt/canvas/pin.py` identified by Codex Critic.

## Violations to Fix
Codex Critic rejected `pin.py` because it contained extra helper functions, violating the strict 3-function architecture constraint.

1. Remove `sha256_file()` and inline its logic.
2. Change `load_pin(path=...)` to a parameterless `load_pin()`. Inside the function, directly use a module-level constant for the path (e.g., `PIN_PATH`).
3. Remove `_template_path()` and inline its logic.
4. Remove `_verify_signature()` and inline its logic directly into `verify_pin(pin)`.

Ensure `src/aippt/canvas/pin.py` contains exactly these three functions and nothing else (other than imports and constants):
- `load_pin() -> dict`
- `verify_pin(pin: dict) -> None`
- `open_renderer_template(pin: dict) -> Presentation`

## Write Scope
- `src/aippt/canvas/pin.py`

claude_model: opus
target_repo: .
change_detail_path: tasks/AI_Powered_PPT/phase0_repair_change_detail.md
write_scope: src/aippt/canvas/pin.py
