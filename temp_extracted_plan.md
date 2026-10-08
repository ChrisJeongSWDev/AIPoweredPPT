# HTML Visual Editor → PPTX — Implementation Plan

**Status:** implementation-ready. Phase 0 can start immediately.
**Supersedes:** the slide-cloning workstream in `renderer_draft_brief.md` for the visual-editor path.
**Sources:** `plan_review.md` (claude-review) + `critic_review.md` (codex-critic). Where the two disagree, **`critic_review.md` wins** — it inspected the actual OPC package; `plan_review.md` inferred from the manifest.

---

## 0. Executive summary

A human draws a slide in a browser at **960 × 540 logical units**. The browser serializes a **Canvas IR** (JSON, absolute coordinates). A deterministic Python renderer opens a **pinned, slide-free renderer template**, calls `add_slide(layout_3)` to inherit the Vieworks chrome (logo, gradient divider, page number), fills **BODY placeholder idx 10** with the title, and draws the user's shapes at absolute EMU.

Three facts make this cheap and exact:

1. **1 logical unit ≡ 1 pt ≡ exactly 12,700 EMU.** The slide is 12,192,000 × 6,858,000 EMU; `12192000/960 = 6858000/540 = 12700`. Integer, exact, zero drift — and **font sizes map 1:1** (a 14-unit font is a 14 pt font, no scale factor anywhere).
2. **The chrome lives in the layout, not the slides.** `add_slide()` inherits it for free at native coordinates. No lxml slide-cloning engine is needed — the highest-risk module in the project is deleted, not built.
3. **A human sizes the text box and sees the text in it.** `foundation_research.md` called text overflow the #1 project risk *because an LLM had to guess a character budget*. That risk is now structurally reduced — though **not eliminated** (§7.4).

Three things will silently produce a wrong deck if not handled, and all three are handled below:

- The source template **already contains 23 slides** — `add_slide()` on it appends a *24th* (§2).
- `add_shape()` hands you **Office blue `#4472C4` with a drop shadow**, not your colour (§6.4).
- **Century Gothic has no Hangul glyphs.** Latin/EA font split is mandatory (§6.5).

---

## 1. The 12 rules, and where each is discharged

Every rule from `critic_review.md` §3 is normative. This table is the compliance index — a reviewer should be able to check the plan against it line by line.

| # | Rule | Discharged in |
|---|---|---|
| 1 | Adopt Layout 3 chrome; do not clone exemplar slides | §3, §6.2 |
| 2 | Correct asset map: `그림 3`/`image5.jpeg` = **divider**; `그래픽 8`/`image2.svg` = **logo** | §3.1 |
| 3 | Create and verify a **clean renderer template** before feature work | §2 |
| 4 | **Pin the template SHA + layout signature**, fail closed | §4 |
| 5 | Fill **BODY placeholder idx 10** directly; never `slide.shapes.title` | §6.3 |
| 6 | Keep editor chrome out of the Canvas IR; lock header/footer exclusion zones | §3.2, §5.3, §5.7 |
| 7 | Keep 960×540 logical model; single exact 12,700-EMU conversion; explicit zoom inversion | §5.2, §6.1 |
| 8 | Specify border, rotation, text-margin, paragraph, fallback-font, `contenteditable` normalization **before** implementing serialization | §5.4–§5.6, §6.5–§6.6 |
| 9 | Make all PPTX styling explicit (remove inherited Office effects; set Latin **and** East-Asian fonts) | §6.4, §6.5 |
| 10 | Add a connector schema/tool **or** declare arrows out of scope | §6.7 — **connectors are IN scope** |
| 11 | Run calibration + round-trip QA **first** | §7 |
| 12 | Do not claim WYSIWYG from coordinate equality alone; use tolerances + rendered evidence | §7.5, §9 |

---

## 2. Phase 0, Step 1 — the clean renderer template (blocking; do this first)

### 2.1 The problem

`Presentation("Vieworks_R&D_ppt_Template.pptx")` opens a deck that **already has 23 slides** (`layout_manifest.json` → `deck.existing_slide_count: 23`). `add_slide()` appends a **24th**. Every export would ship all 23 exemplar slides, and the inherited page-number field on the new slide would read 24. The public `Slides` API has **no deletion operation**.

### 2.2 The fix

Build a **one-off, committed artifact**: `reference/renderer_template.pptx` — same master, same 5 layouts, same theme, same `image5.jpeg` / `image2.svg` media, **zero slides**.

Slide deletion needs private API. That is acceptable **exactly once, in a build script**, and is forbidden in the request path (critic rule 3: *"Do not make private slide-deletion code part of each export request"*).

`src/aippt/tools/make_renderer_template.py`:

