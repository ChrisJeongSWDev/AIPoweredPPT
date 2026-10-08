---
task_id: "AI_Powered_PPT"
mode: "fresh"
target_repo: "C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT"
---

# Task Description
Analyze the provided HTML samples and the `Vieworks_R&D_ppt_Template.pptx` file.
The user wants to establish a framework and foundational research on how to use AI (Claude, Codex, Gemini) to automatically generate and populate PowerPoint presentations based on the company's PPT template (`Vieworks_R&D_ppt_Template.pptx`).

The AI-powered solution should seamlessly allow adding:
- Images
- Tables
- Concluding text
- Diagrams
All while maintaining a highly intuitive, precise, and clean design.

Key Considerations:
1. The master slide of `Vieworks_R&D_ppt_Template.pptx` must be the core template. How can we analyze its slide layouts and map them to AI prompts?
2. What technical stack is best? (e.g., parsing HTML scripts to PPT, or using `python-pptx` directly).
3. How to structure the `AI_Powered_PPT` project repository to accumulate prompts, python scripts, and reference data.

# Orchestrator Request (B Stage: claude-review)
As `claude-review` (Opus), you are not to write the final research document yourself. Instead:
1. Analyze the requirements and strategize the best approach for AI-powered PPT creation (e.g., Python-pptx vs. HTML-based mapping).
2. Formulate an enhanced, highly detailed task brief for the `claude-main` worker.
3. The enhanced brief must instruct the main worker to:
   - Create a proposed directory structure inside `AI_Powered_PPT/`.
   - Write a detailed `foundation_research.md` covering the pipeline, technical stack, prompt engineering techniques for PPT generation, and how to handle master slides.
   - If applicable, write a small PoC script (e.g., `analyze_pptx_master.py`) to extract layout info from the template to aid AI prompt generation.
4. Output the enhanced brief in your result.
