# Stage 2 — Slide Fill

> `user` message, called **once per slide**, in parallel. Paired with
> `00_system_deck_author.md`.
>
> Critical: inject only **this slide's** layout budget, not the whole catalog. Narrowing
> the context measurably improves budget adherence — the model is no longer choosing a
> layout, it is filling a box whose exact dimensions it has just been told.
>
> Output is validated against `ir/schema.json` by the provider's structured-output
> mechanism, then against the budget by `render/fit.py`. On failure, this prompt is
> re-sent once with `{{REPAIR_NOTE}}` populated.

---

## Task

Write the full content of **one** slide.

## The slide

```json
{{OUTLINE_ENTRY}}
```

## The layout you are filling — `{{LAYOUT_ID}}` ({{SEMANTIC_ROLE}})

{{LAYOUT_BUDGET}}

These numbers come from measuring the actual placeholder boxes in the template. They are
not guidance. Text over budget renders off the edge of the slide — there is no autofit,
and nothing downstream will catch it.

**Aim for 80% of every number above.** The estimate does not account for bold runs, inline
code, or wide punctuation.

## Source material

{{SOURCES}}

Every factual claim must be traceable to this. Do not import knowledge from outside it —
not about the product, not about the APIs, not about the numbers. If the sources are thin,
write a thinner slide.

## Block selection

Pick the block types that fit the *content*, not the ones that fill the space:

| The content is… | Use |
|---|---|
| a single framing statement | `paragraph` |
| a list of peer facts | `bullets` |
| the one thing they must remember | `callout` (`info`), risk → `warn`, confirmation → `ok` |
| N things compared on M axes | `table` |
| an ordered process | `steps` |
| peer concepts, side by side | `cards` |
| a call sequence or an architecture | `diagram` (Mermaid source) |
| an actual API call | `code` |
| a photograph or a screenshot | `image` |

At most **one** heavyweight block (`table`, `diagram`, `code`, `image`) per slide. Two
compete for the same box and both lose.

## Reminders that are load-bearing

- Every API name, type, filename, flag and identifier gets an inline `code` run.
- Bullets are fragments. No terminal periods. Parallel grammar.
- Write in the language of the source material.
- Speaker `notes` are free of any budget — put the detail there that will not fit on the
  slide. That is what they are for, and it is where the nuance you had to cut should go.

{{REPAIR_NOTE}}

## Output

The slide object only, conforming to the schema. No wrapper, no commentary.
