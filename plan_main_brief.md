---
claude_model: opus
---
# Final Plan Writing Task

## Objective
Read the two reviews (`plan_review.md` and `critic_review.md`) which analyzed the HTML Visual Editor to PPTX Pipeline.
Synthesize these findings into a comprehensive, implementation-ready markdown plan named `HTML_to_PPTX_Plan.md`.

## Instructions
1. Incorporate all 12 rules from `critic_review.md` into the plan.
2. Specifically outline the Frontend HTML/JS architecture (canvas sizing, coordinate system 960x540, font rendering, CSS constraints).
3. Outline the Backend Python rendering architecture (Layout 3 adoption instead of cloning, EMU scaling, explicit shape/text styling, overcoming default Office blue).
4. The plan should be structured logically so a developer can immediately start building Phase 1 from it.
5. Make sure the plan clearly states the required cleanup step (creating a clean renderer template without the 23 exemplar slides).
6. State the exact template hashing/pinning mechanism.

Note: Since your sandbox environment might deny file writes, you MUST output the complete, verbatim markdown content of `HTML_to_PPTX_Plan.md` inside a markdown code block (````markdown ... ````) in your response, so the Orchestrator can extract and save it on your behalf.
