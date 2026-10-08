# Stage 3 — Visual QA

> Sent to a **vision-capable** model with the rendered slide PNG attached.
> `deck.pptx → LibreOffice → PDF → pdftoppm → slide-NN.png`.
>
> This is the only stage that sees what the audience will see. Stages 1 and 2 reason about
> *estimated* text metrics; `fit.py` reasons about *estimated* heights. This stage is the
> ground truth, and it is the only thing that will ever catch a wrong font-metric
> assumption.
>
> Runs **after** the deterministic geometry checks in `fit.detect_overflow_in_png()`.
> Division of labour: arithmetic finds overhangs and collisions far more reliably than a
> vision model does; a vision model finds the things arithmetic cannot name. Do not ask
> this prompt to measure — ask it to judge.

---

## Task

You are reviewing one rendered slide from a Vieworks engineering deck. The image attached
is exactly what the audience will see, projected.

## What the slide was supposed to contain

```json
{{SLIDE_IR}}
```

## Geometry defects already found automatically

{{DETERMINISTIC_FINDINGS}}

Take these as given — confirm them, do not re-derive them, and do not waste your judgement
re-measuring what has already been measured.

## What to judge

Look for the failures that only a viewer can see:

1. **Truncation and overflow.** Text running off any edge, clipped mid-word, or colliding
   with the template's own furniture (logo bar, footer, page number). Note that overflow
   can be *invisible* — text rendered off the bottom simply is not there. If the IR lists
   five bullets and you can count four, say so.
2. **Legibility at range.** This is projected in a meeting room. Anything under ~12pt
   effective size, low-contrast text on a coloured fill, or a diagram whose edge labels
   have collapsed into each other, fails.
3. **Density.** Does the slide read in under 15 seconds? A slide that is technically
   correct and visually unreadable is a failed slide.
4. **Diagram integrity.** Overlapping nodes, crossing edges that obscure labels, arrows
   pointing at nothing, a rasterised diagram gone soft or pixelated.
5. **Image handling.** Stretched or squashed aspect ratio (people and hardware look
   *wrong* and it is immediately obvious), or an image cropping something important.
6. **Brand consistency.** Does it look like it belongs to the same deck as the others?
   Off-template colours, an accent that is not the Vieworks red, a stray white box on a
   coloured master.

## What NOT to flag

- Wording, tone or content accuracy — not your job here, and you cannot see the sources.
- Aesthetic preferences about the template itself. The master is owned by a designer and
  is not up for review.
- Anything you are merely *unsure* about. A false positive costs a pointless regeneration
  cycle. **When in doubt, pass it.**

## Output

```json
{
  "verdict": "pass" | "fix" | "regenerate",
  "defects": [
    {
      "severity": "critical" | "major" | "minor",
      "kind": "overflow" | "legibility" | "density" | "diagram" | "image" | "brand",
      "description": "<what is wrong, and where on the slide>",
      "suggested_fix": "<a concrete, actionable change — 'cut bullets 4 and 5 and move them to a continuation slide', not 'make it shorter'>"
    }
  ]
}
```

Verdict rules:

- **`pass`** — ships as-is. Minor defects alone still pass; perfection is not the bar.
- **`fix`** — a deterministic repair will do it: shrink, split, re-fit. No new content
  needed. `fit.py` handles it, no model call required.
- **`regenerate`** — the slide's *content* is the problem: too much of it, or the wrong
  block type for it. Only this verdict costs another generation call, so reserve it for
  when one is genuinely required.
