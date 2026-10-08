phase: phase_ui_fix
reviewer: claude-review-sonnet
claude_model: sonnet
target_repo: c:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/src/aippt
write_scope:
  - canvas/static/index.html
  - canvas/static/style.css

# UI/UX Fixes for AI PPT Editor

The user has requested a few UI layout changes to the canvas editor.

## Tasks:

1. **Fix the AI Composer HTML Bug**:
   - In `canvas/static/index.html`, the `<!-- THE AI DRAFT ... ` comment at line 287 currently swallows the `<section id="ai" ...>` tag because the `-->` is missing before `<section id="ai">`. The closing `-->` is instead at line 310.
   - Close the comment properly before `<section id="ai">`. Remove the extraneous `-->` at line 310.

2. **Make AI Composer Antigravity-style**:
   - The user wants the AI Composer to look like the "Antigravity" chat window. In `canvas/static/style.css`, update `#ai` to be a floating, elevated panel at the bottom center of the screen (or similar sleek, modern floating chat interface), instead of just a flat grid row. Give it a sleek shadow look and a premium feel. Position it absolutely or fixed over the stage so it feels like a floating chat box.

3. **Server Templates Button Layout**:
   - In `index.html` (`#designs` section), place the "Save Template" and "Load Template" buttons in a single row (`<div class="row">`) to save space. Adjust labels so it fits nicely.

4. **Prominent JSON Viewer**:
   - The user couldn't find the "View JSON" modal. Make the `#b-view-json` button more prominent (e.g., highly visible distinct color, maybe larger) in `style.css` and `index.html`.

Make these edits directly. Ensure the HTML syntax is correct.
