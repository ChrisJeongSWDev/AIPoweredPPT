# Phase 1B Draft Brief: Frontend DOM-to-IR Adapter

## Context
Phase 1A (Canvas Backend) is complete and verified. It strictly enforces the Draft 2020-12 `Canvas IR` JSON schema.
We are now entering Phase 1B: Frontend Architecture (HTML/JS/CSS).

## Objective
Implement Section 5 of `HTML_to_PPTX_Plan.md`.
Build a web-based visual editor that:
1. Presents a 960x540 logical unit stage.
2. Allows users to create/edit shapes (rect, ellipse, triangle, connector) and text (`contenteditable`).
3. Uses `interact.js` for drag/resize/snap, with strict coordinate inversion (`toModel(ev)` logic) as defined in §5.2.
4. Serializes the DOM state exactly into the `Canvas IR` JSON payload.
5. Uses inline `<svg>` for shapes to match DrawingML stroke semantics (§5.4).
6. Prevents intersection with `HEADER_RESERVED` and `FOOTER_RESERVED`, and locks `TITLE_LOCKED` (§5.7).
7. Incorporates Century Gothic font checks, exact CSS text styling (§5.6), and visual pseudo-elements for the red line / locked title box (§5.3).
8. Implements `contenteditable` normalization into paragraph/run models (§5.6).

## Scope
- `src/aippt/canvas/app.py` (FastAPI app to serve the frontend and receive POST /api/export)
- `src/aippt/canvas/static/index.html`
- `src/aippt/canvas/static/editor.js`
- `src/aippt/canvas/static/style.css`

## Instructions for claude-review
Read `HTML_to_PPTX_Plan.md` Section 5 carefully.
Produce `phase1b_brief.md` which will guide `claude-main` (Opus) to implement these files.
Ensure the brief demands adherence to the rule: *No `getBoundingClientRect()` except in `toModel(ev)`.*
Include explicit write scopes.
