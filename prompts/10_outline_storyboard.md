# Stage 1 — Outline / Storyboard

> `user` message for the first generation call. Paired with `00_system_deck_author.md`.
> Output is **not** full IR — it is the storyboard that stage 2 fills in.
>
> Split from stage 2 deliberately: one call that must hold both the deck's narrative arc
> *and* 30 per-placeholder character budgets does neither job well. It drifts on structure
> and overflows on length. This call decides the *story*; stage 2 writes the *words*.

---

## Task

Design the narrative arc of a deck. Do not write slide content yet — decide what slides
exist, why each one exists, and which layout each one uses.

**Topic**

{{TOPIC}}

**Source material** — this is your only permitted source of fact. Everything in the deck
must be traceable to it.

{{SOURCES}}

**Target length:** approximately {{TARGET_SLIDES}} slides. Deviate if the material demands
it, but say so in `rationale`.

## How to build the arc

1. **Open with the answer, not the agenda.** An executive-summary slide that states the
   conclusion. The audience decides in 30 seconds whether to pay attention.
2. **Then the agenda**, only if the deck is longer than ~8 slides.
3. **Body**, in sections. Insert a `section-divider` layout between sections — it gives
   the audience a breath and it makes the deck skimmable after the fact.
4. **Vary the layout.** Nine consecutive bullet slides is a failure of authorship, not of
   the template. Look at the available `semantic_role` values and use them: a comparison
   becomes a table, a process becomes `steps`, an architecture becomes a `diagram`, peer
   concepts become `cards`.
5. **Close with what happens next** — decisions needed, owners, dates. Not "Thank you".

## Judgement you are expected to exercise

- If the source material does not contain enough substance for {{TARGET_SLIDES}} slides,
  produce fewer. Padding is worse than brevity.
- If a single slide's `key_points` list is running past ~6 entries, that is two slides.
- Every slide must survive the question **"what would be lost if we cut this?"** If the
  answer is "nothing", cut it yourself.

## Output

One object per slide, in presentation order:

```json
{
  "slides": [
    {
      "id": "slide-01",
      "layout_id": "<exactly one of the layout_id values in the catalog>",
      "title": "<the claim this slide makes, within the title budget>",
      "intent": "<one line: why this slide exists and what the audience takes away>",
      "key_points": ["<bare fragments — stage 2 turns these into prose>"],
      "source_refs": ["<which part of the source material backs this>"]
    }
  ],
  "rationale": "<2-3 sentences on the arc, and on any deviation from the target length>"
}
```

`layout_id` **must** be copied exactly from the catalog in the system prompt. A layout that
is not in that list does not exist in the template, and the build will fail hard rather
than silently substitute one.
