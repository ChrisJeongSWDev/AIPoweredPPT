---
target_repo: c:/Users/2021670/Documents/멀티 에이전트
write_scope:
  - "tasks/AI_Powered_PPT/src/aippt/canvas/static/index.html"
  - "tasks/AI_Powered_PPT/src/aippt/canvas/static/style.css"
read_refs: []
claude_model: sonnet
change_detail_path: "tasks/AI_Powered_PPT/change_detail.md"
---
# Task
You are Claude Sonnet Worker (claude-main). Your task is to update `index.html` and `style.css` based EXACTLY on the Work Order provided by the Codex Critic.

# Work Order (From Codex Critic)

1. Preserve every existing element ID and event-binding target. Limit changes to `index.html` class structure and `style.css`; do not modify JavaScript or stage contract styles.

2. Refactor the AI composer:
   - Return `#ai` to grid flow with `grid-area: composer`.
   - Center it using grid alignment, such as `justify-self: center`.
   - Retain the responsive width cap and solid-white single-container styling.
   - Remove absolute positioning, viewport translation, and unnecessary overlay z-index.
   - Ensure it always occupies reserved space above `#status`.
   - Change the submit button to a 32–36px rounded square with approximately 7–9px radius and `#1e293b` background.
   - Update responsive selectors to target classes that actually exist, especially `.composer-toolbar`, `.toolbar-left`, and `.toolbar-right`.

3. Introduce scoped layout classes, for example:
   - `.action-stack` for vertically stacked 100%-width controls.
   - `.action-grid-2` for equal two-column actions.
   - `.sidebar-action` for normalized dimensions.
   - `.sidebar-action--primary`, `--featured`, and `--danger` modifiers.
   Do not repurpose generic `.row` globally.

4. Refactor JSON & Data:
   - Keep View & Copy JSON first and full-width.
   - Keep Download JSON and Load JSON in a two-column grid.
   - Keep Paste Gem JSON immediately below them and full-width.
   - Remove inline styles.
   - Represent the featured blue treatment with a CSS modifier if it is retained as the checklist’s intended visual exception.

5. Refactor Export Deck:
   - Apply the explicit two-column layout class.
   - Keep both actions equal-width and dark-primary.

6. Rebuild Server Templates in this exact order:
   - Full-width Name label/input.
   - Full-width Save button.
   - Full-width Templates label/select.
   - Full-width Load button.
   - Preserve Delete after Load as a separate full-width danger action.

7. Normalize sidebar action styling:
   - Use consistent font size, weight, padding, and minimum height.
   - Use 5px rounded corners for standard sidebar actions.
   - Use `#1e293b` for dark actions with a coordinated lighter hover state.
   - Add visible `:focus-visible` treatment.
   - Replace `transition: all` with targeted properties.
   - Keep circular controls only where their icon semantics explicitly require circles; the submit control should be rounded-square.

# Instructions
1. Edit `index.html` and `style.css` to implement the layout and styling updates.
2. DO NOT change element IDs.
3. Make sure the CSS changes use the recommended new classes (`.action-stack`, `.action-grid-2`, etc.) and remove inline styles from `index.html`.
