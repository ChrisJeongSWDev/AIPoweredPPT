---
target_repo: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT
write_scope: none
reviewer: none
---

# WorkDirector Brief (Phase B)

## 1. Current Request
- Move the AI Draft UI to the bottom of the editor and convert it into a multi-line auto-resizing textbox (like the AGY input style).
- Add support for pasting images via CTRL+V into the textbox.
- Add a model selection dropdown (Gemini 3.5 Flash / Gemini 3.5 Flash Extended) and integrate it with the backend `/api/generate` endpoint.

## 2. Your Role (WorkDirector)
You are `claude-review` (Opus). You are acting as the WorkDirector. Do NOT make actual code changes.
Your task is to analyze the `target_repo` (specifically `src/aippt/canvas/static/index.html`, `style.css`, `editor.js`, and `src/aippt/canvas/app.py`) using Read/Glob/Grep tools, and return the following two outputs:

1) **Phase Plan (D83)**:
   - Break down the request into logical execution phases.
   - For each phase, specify the `Recommended Worker Model` (Opus or Sonnet), `write_scope`, and whether it is `parallel-group` or `sequential-after`. (Parallel is only allowed for different target_repos, so these phases will likely be sequential).

2) **Reinforced Worker Brief**:
   - Write a detailed instruction set for the `claude-main` worker. Include technical specifics discovered from your code analysis (exact function names, CSS classes, required HTML structure, backend routing logic, etc.) so the worker can implement the changes precisely without needing to do broad codebase discovery again.
   - Ensure the instructions are in English (per D27).

## 3. Output Format
```markdown
# Phase Plan
- Phase 1: [Brief summary of phase]
  - Recommended Model: claude-main Sonnet
  - write_scope: src/aippt/canvas/static/index.html, src/aippt/canvas/static/style.css
  - Execution: sequential
- Phase 2: ...

# Reinforced Worker Brief
(Detailed technical instructions for the worker here...)
```
