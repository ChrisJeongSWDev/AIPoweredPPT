# HTML Visual Editor to PPTX Pipeline - Plan Draft

## Context & Objective
The user has proposed a major architectural shift for Phase 1. Instead of the AI filling in existing template layouts directly, the user wants to build an HTML-based Visual Editor (working environment) where a human can design the slide, and then export it to a Python script that renders it onto a cloned Vieworks PPTX slide.

## User's Exact Requirements
1. **Slide Cloning / UI Foundation**: Create an accessible HTML page.
2. **HTML Layout**: Implement a PPT slide structure (Title Header, Body). Below the Title Header, instead of complex gradient lines and logos, just use a thick red line as a boundary. Try to match the position of this line with the `Vieworks_R&D_Template` master slide.
3. **HTML Capabilities**:
   - Write the Title.
   - Add simple shapes (Rectangle, Circle, Triangle) suitable for flow charts or block diagrams, and allow color selection for these shapes.
   - Add Textboxes. Default font: Century Gothic (for both English/Korean). Font size must be adjustable.
   - **Export PPT Button**: Clicking this will cause a Python backend to reconstruct this exact design onto a real Vieworks Slide (PPTX) based on the Python rendering code.

## Instructions for claude-review (Stage 1)
Analyze the technical feasibility and architectural implications of this plan.
1. **Frontend-to-Backend Contract**: How should the HTML pass the visual state to Python? (JSON payload? Absolute coordinates? Percentage-based coordinates?)
2. **Canvas implementation**: What is the best Vanilla JS or lightweight library approach (e.g. Fabric.js) to implement the drag-and-drop shapes/textboxes?
3. **Coordinate Mapping**: How to map HTML canvas pixels to `python-pptx` EMU accurately?
4. **Rendering Strategy**: Can `python-pptx` reliably draw Flow Charts (rectangles with text and lines) onto a blank Vieworks slide while maintaining Century Gothic and shape colors?

Please provide your comprehensive analysis. Your output will be passed to `codex-critic` for a secondary review.
