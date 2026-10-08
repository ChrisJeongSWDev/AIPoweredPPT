#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""LLM  ->  Slide IR.  Model-agnostic by construction.

STATUS: the generative pipeline (``build_system_prompt``, ``generate_outline``,
``fill_slide``, ``generate_deck``) and ``CliWorkerClient`` (headless claude/codex CLI,
no API key -- see the headless-worker-integration Work Order) are implemented. The
reference API-key clients below (``ClaudeClient``, ``OpenAIClient``, ``GeminiClient``)
still raise NotImplementedError -- out of scope; the user declined that path.

The single invariant this module exists to protect
--------------------------------------------------
**The model never emits PPTX, OOXML, DrawingML, coordinates, fonts or colours.**
It emits schema-valid IR: a ``layout_id`` plus placeholder content. Everything visual
comes from the template and the renderer. If you ever find yourself adding an `x`, `y`,
`rgb` or `font_size` field to the IR to make a slide look right, the bug is in the
renderer or the template -- fix it there.

Why structured output and not free-text-then-parse
--------------------------------------------------
"Return JSON" in a system prompt yields JSON *most* of the time, and the failures are
the expensive kind: a stray markdown fence, a trailing comma, a hallucinated field. Every
supported provider can constrain output to a schema, so we use that and get a hard
guarantee instead of a soft one:

    Claude  -> tool use / `tools=[{input_schema: SCHEMA}]`, force with tool_choice
    OpenAI  -> Structured Outputs / `response_format={type: json_schema, strict: true}`
    Gemini  -> `response_mime_type="application/json"` + `response_schema`

All three consume the *same* ``ir/schema.json``. That is the entire point of having an IR:
the schema is the neutral contract, and the model behind it is a swappable implementation
detail. Adding a provider must not require touching the renderer, the prompts, or the IR.

Two-stage generation (see prompts/)
-----------------------------------
    stage 1  10_outline_storyboard.md  topic + sources -> deck narrative, one line/slide
    stage 2  20_slide_fill.md          one slide's outline entry -> that slide's IR

Stage 2 runs per-slide and is parallelisable. The split exists because a single call that
has to hold the whole deck's narrative *and* respect 30 different per-placeholder
character budgets does neither job well: it drifts on structure and overflows on length.
Separating "what story do we tell" from "what words go in this box" fixes both.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from jsonschema import validators
from jsonschema.exceptions import ValidationError

from ..ir.models import (
    Bullets,
    Callout,
    Cards,
    Deck,
    DeckMeta,
    Heading,
    IR_VERSION,
    IRValidationError,
    Paragraph,
    Slide,
    Steps,
    Table,
    load_schema,
)

#: This module's project root -- ``tasks/AI_Powered_PPT`` -- three levels above
#: ``src/aippt/adapters/ai_adapter.py``. Same convention ``canvas/pin.py`` and
#: ``tools/calibrate.py`` use for the same directory depth. ``prompts/`` and
#: ``reference/`` are data files, not package resources: the repo-root ``.gitignore``
#: keeps them out of a fresh checkout of ``tasks/*``, so this resolves correctly in a
#: full working copy but not inside a staging clone that only carries ``src/``.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _PROJECT_ROOT / "prompts"
_REFERENCE_DIR = _PROJECT_ROOT / "reference"

#: Where ``_run_cli`` mirrors a worker subprocess's live stderr, and where ``app.py``'s
#: ``GET /api/log`` reads it back from -- the same ``_PROJECT_ROOT`` convention as
#: ``_PROMPTS_DIR``/``_REFERENCE_DIR`` above, so both modules agree on the path without
#: either hardcoding the other's.
_ARTIFACTS_DIR = _PROJECT_ROOT / "artifacts"
_LIVE_LOG_PATH = _ARTIFACTS_DIR / "multiagent_live.log"


class LLMClient(Protocol):
    """The seam. Claude, Codex and Gemini are interchangeable *behind this*.

    One method, because one method is all the pipeline needs. Anything provider-specific
    (auth, retries, rate limits, base URLs) lives inside the implementation, never leaks
    into the caller.
    """

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = 8000,
    ) -> dict[str, Any]:
        """Return a dict the provider has *already* constrained to ``schema``.

        Implementations MUST use the provider's native structured-output mechanism.
        An implementation that calls ``json.loads`` on free text is not conforming --
        it silently reintroduces exactly the failure mode this interface removes.
        """
        ...


@dataclass
class GenerationResult:
    deck: Deck
    attempts: int
    repaired: bool          # True if a retry was needed -- track this; a rising rate
                            # means the prompt or the budget has drifted from reality.
    token_usage: dict[str, int]


def build_system_prompt(manifest: dict[str, Any], catalog_md: str) -> str:
    """Assemble the system prompt from ``prompts/00_system_deck_author.md`` + the catalog.

    The catalog (``reference/layout_catalog.md``) is injected *whole*. It carries the two
    things the model cannot guess and must not invent:

      * the exact set of legal ``layout_id`` values, and
      * the per-placeholder **content budget** ("max 6 bullets x 9 words", "title <= 42
        Korean chars").

    Injecting the budget is what makes the model self-limit. Without it the model writes
    to a length that reads well in chat and overflows a 4-inch box every time -- and since
    python-pptx cannot autofit, that overflow is permanent and invisible until render.

    Note the budget is stated in BOTH Latin and Korean character counts, because a Hangul
    glyph is roughly twice the advance width of a Latin one. A model told "60 characters"
    with no script qualifier will happily overflow a Korean slide by 2x.
    """
    del manifest  # the caller already rendered catalog_md from this manifest; see _load_catalog_md
    template = (_PROMPTS_DIR / "00_system_deck_author.md").read_text(encoding="utf-8")
    return template.replace("{{LAYOUT_CATALOG}}", catalog_md)


def _load_catalog_md() -> str:
    """The pre-rendered ``reference/layout_catalog.md`` -- read from disk rather than
    regenerated via ``analyze_pptx_master.render_catalog(manifest)``, so this module never
    needs a ``python-pptx`` dependency of its own."""
    return (_REFERENCE_DIR / "layout_catalog.md").read_text(encoding="utf-8")


def _outline_schema(manifest: dict[str, Any]) -> dict[str, Any]:
    """The stage-1 structured-output schema. ``layout_id`` is a closed ``enum`` built from
    the manifest's own layouts -- an invented layout is rejected by the provider's own
    structured-output mechanism, before it ever reaches ``validate_against_manifest``.
    """
    layout_ids = sorted({
        lay["layout_id"]
        for master in manifest.get("masters", [])
        for lay in master.get("layouts", [])
    })
    slide_entry = {
        "type": "object",
        "required": ["id", "layout_id", "title", "intent", "key_points"],
        "additionalProperties": False,
        "properties": {
            "id": {"type": "string", "minLength": 1},
            "layout_id": {"type": "string", "enum": layout_ids},
            "title": {"type": "string", "minLength": 1, "maxLength": 200},
            "intent": {"type": "string", "minLength": 1},
            "key_points": {"type": "array", "items": {"type": "string"}},
            "source_refs": {"type": "array", "items": {"type": "string"}},
        },
    }
    return {
        "type": "object",
        "required": ["slides", "rationale"],
        "additionalProperties": False,
        "properties": {
            "slides": {"type": "array", "minItems": 1, "items": slide_entry},
            "rationale": {"type": "string"},
        },
    }


def generate_outline(client: LLMClient, topic: str, sources: list[str],
                     manifest: dict[str, Any], target_slides: int = 12) -> list[dict[str, Any]]:
    """Stage 1: topic + source material -> a storyboard.

    Returns one entry per slide::

        {"id": "slide-03", "layout_id": "...", "title": "...",
         "intent": "why this slide exists, one line",
         "key_points": ["...", "..."]}

    The outline is deliberately NOT full IR: no blocks, no prose. Its job is narrative
    arc and layout selection -- deciding that slide 3 is a section divider and slide 4 is
    a comparison table. Cheap to generate, cheap to review, cheap to regenerate.

    ``layout_id`` is chosen here, at deck level, where the model can see the whole shape
    and avoid emitting nine consecutive bullet slides.
    """
    system_prompt = build_system_prompt(manifest, _load_catalog_md())
    template = (_PROMPTS_DIR / "10_outline_storyboard.md").read_text(encoding="utf-8")
    user_prompt = (
        template.replace("{{TOPIC}}", topic)
                .replace("{{SOURCES}}", "\n".join(sources))
                .replace("{{TARGET_SLIDES}}", str(target_slides))
    )
    result = client.complete_json(system=system_prompt, user=user_prompt,
                                  schema=_outline_schema(manifest))
    return result["slides"]


def _find_layout(manifest: dict[str, Any], layout_id: str) -> dict[str, Any]:
    """``layout_id`` -> its full manifest entry. Raises plain ``CliWorkerError`` (not
    ``CliWorkerSchemaError``) when the name doesn't exist at all: that is a structural
    defect no repair prompt can fix, since the outline schema's own ``enum`` should have
    made it unreachable in the first place.
    """
    for master in manifest.get("masters", []):
        for lay in master.get("layouts", []):
            if lay["layout_id"] == layout_id:
                return lay
    raise CliWorkerError(
        f"layout_id {layout_id!r} does not exist in this manifest's layouts -- "
        "no repair prompt can fix a layout the template does not have."
    )


def _format_layout_budget(layout: dict[str, Any]) -> str:
    """One layout's placeholder budgets, in the same per-placeholder shape
    ``analyze_pptx_master.render_catalog`` uses for the full catalog -- but scoped to just
    THIS layout, which is the point of stage 2's narrower prompt (see module docstring).
    """
    lines = [f"Layout `{layout['layout_id']}` ({layout['semantic_role']}):"]
    placeholders = layout.get("placeholders") or []
    if not placeholders:
        lines.append("- this layout has no fillable placeholders (decoration only)")
        return "\n".join(lines)
    for ph in placeholders:
        b = ph.get("content_budget") or {}
        head = f"- `idx {ph['idx']}` {ph['type']}"
        if not b.get("computable"):
            lines.append(f"{head} -- budget unavailable ({b.get('reason')})")
        elif "max_title_chars_cjk" in b:
            lines.append(
                f"{head} -- max {b['max_title_chars_latin']} latin / "
                f"{b['max_title_chars_cjk']} korean chars, <= {b['recommended_lines']} lines"
            )
        elif "max_bullets" in b:
            lines.append(
                f"{head} -- max {b['max_bullets']} bullets x {b['max_words_per_bullet']} "
                f"words ({b['max_chars_per_bullet_latin']} latin / "
                f"{b['max_chars_per_bullet_cjk']} korean chars per bullet)"
            )
        else:
            lines.append(f"{head} -- {b.get('chars_per_line_latin')} latin chars/line, "
                         f"{b.get('max_lines')} lines")
    return "\n".join(lines)


def _slide_schema() -> dict[str, Any]:
    """``ir/schema.json``'s ``$defs.slide`` lifted to the document root, with the full
    ``$defs`` carried alongside so its internal ``#/$defs/...`` refs still resolve -- a
    JSON Schema ``$ref`` is resolved against the root of whatever document is actually
    being validated, and stage 2 validates one slide, not a whole deck.
    """
    full = load_schema()
    schema = dict(full["$defs"]["slide"])
    schema["$schema"] = full.get("$schema", "https://json-schema.org/draft/2020-12/schema")
    schema["$defs"] = full["$defs"]
    return schema


def fill_slide(client: LLMClient, outline_entry: dict[str, Any],
               manifest: dict[str, Any], sources: list[str], *,
               repair_note: str = "") -> dict[str, Any]:
    """Stage 2: one outline entry -> one schema-valid slide object.

    The prompt injects ONLY the budget for the layout this slide actually uses -- not the
    whole catalog. Narrowing the context measurably improves adherence: the model is not
    picking a layout any more, it is filling a box whose exact dimensions it has been told.

    ``repair_note``, keyword-only and additive to the original signature: when
    ``generate_deck``'s bounded repair loop re-prompts after a validation failure, the
    specific error goes here and is substituted into ``{{REPAIR_NOTE}}``.
    """
    layout = _find_layout(manifest, outline_entry["layout_id"])
    system_prompt = build_system_prompt(manifest, _load_catalog_md())
    template = (_PROMPTS_DIR / "20_slide_fill.md").read_text(encoding="utf-8")
    repair_block = (
        f"## This slide was rejected -- fix it\n\n{repair_note}" if repair_note else ""
    )
    user_prompt = (
        template.replace("{{OUTLINE_ENTRY}}",
                         json.dumps(outline_entry, ensure_ascii=False, indent=2))
                .replace("{{LAYOUT_ID}}", layout["layout_id"])
                .replace("{{SEMANTIC_ROLE}}", layout["semantic_role"])
                .replace("{{LAYOUT_BUDGET}}", _format_layout_budget(layout))
                .replace("{{SOURCES}}", "\n".join(sources))
                .replace("{{REPAIR_NOTE}}", repair_block)
    )
    return client.complete_json(system=system_prompt, user=user_prompt, schema=_slide_schema())


def review_slide(reviewer_client: LLMClient, slide_dict: dict[str, Any],
                 manifest: dict[str, Any]) -> dict[str, Any]:
    """Stage 2.5: Review and refine a filled slide object using a secondary reviewer model."""
    layout = _find_layout(manifest, slide_dict["layout_id"])
    system_prompt = build_system_prompt(manifest, _load_catalog_md())
    template = (_PROMPTS_DIR / "25_slide_review.md").read_text(encoding="utf-8")
    user_prompt = (
        template.replace("{{DRAFT_SLIDE_IR}}", json.dumps(slide_dict, ensure_ascii=False, indent=2))
                .replace("{{LAYOUT_ID}}", layout["layout_id"])
                .replace("{{SEMANTIC_ROLE}}", layout["semantic_role"])
                .replace("{{LAYOUT_BUDGET}}", _format_layout_budget(layout))
    )
    return reviewer_client.complete_json(system=system_prompt, user=user_prompt, schema=_slide_schema())



def _check_layout_matches_entry(slide_dict: dict[str, Any], entry: dict[str, Any]) -> None:
    """The outline's layout decision is final. ``fill_slide`` is prompted with exactly one
    layout, but nothing stops the model from answering with a different one -- and content
    validated against one layout's budget, rendered through another's placeholders, is
    exactly the corrupted-but-plausible deck this whole module exists to prevent.
    """
    got = slide_dict.get("layout_id")
    want = entry["layout_id"]
    if got != want:
        raise CliWorkerSchemaError(
            f"slide {entry.get('id')!r}: the outline assigned layout_id {want!r}, but the "
            f"filled slide used {got!r}. Content must be written for the layout it was "
            "assigned -- re-fill it for the correct layout."
        )


def _parse_and_validate_slide(slide_dict: dict[str, Any], manifest: dict[str, Any]) -> Slide:
    """Structural validation JSON Schema cannot express: wraps the slide in a throwaway
    one-slide deck and reuses ``Deck.from_dict`` (ragged table rows, malformed rich text)
    plus ``validate_against_manifest`` (unknown ``layout_id`` -- belt-and-suspenders with
    ``_check_layout_matches_entry``, which catches the same defect earlier and by name).
    """
    throwaway = {
        "ir_version": IR_VERSION,
        "deck": {"title": slide_dict.get("title") or "untitled"},
        "slides": [slide_dict],
    }
    deck = Deck.from_dict(throwaway)
    errors = deck.validate_against_manifest(manifest)
    if errors:
        raise IRValidationError("slides[0].layout_id", "; ".join(errors))
    return deck.slides[0]


def _line_count(text: str, max_chars_per_line: int) -> int:
    """How many line-slots ``text`` costs against a placeholder's per-line character cap --
    the manifest's own rule ("a bullet that wraps consumes another slot"), applied
    literally rather than approximated by a raw character-count sum.
    """
    if not text:
        return 0
    return max(1, math.ceil(len(text) / max_chars_per_line))


def _block_text_items(block: Any) -> list[str]:
    """The text units a line-budget check measures one at a time. Each item consumes at
    least one line slot; a long item consumes ``ceil(len(item) / max_chars_per_line)``.

    ``code``, ``image`` and ``diagram`` blocks are deliberately excluded (empty list):
    they are not budgeted by character count (monospace/fixed-width, area, and Mermaid
    source respectively) -- that is real ``render/fit.py`` geometry work, still
    ``NotImplementedError`` there, and not something this bullet-shaped estimate should
    pretend to check.
    """
    if isinstance(block, Bullets):
        return [item.text.plain for item in block.items]
    if isinstance(block, Steps):
        return [f"{item.title} {item.text.plain if item.text else ''}".strip()
                for item in block.items]
    if isinstance(block, Cards):
        return [f"{item.title} {item.text.plain if item.text else ''}".strip()
                for item in block.items]
    if isinstance(block, Table):
        return [cell.plain for row in block.rows for cell in row]
    if isinstance(block, Paragraph):
        return [block.text.plain]
    if isinstance(block, Callout):
        return [f"{block.title or ''} {block.text.plain}".strip()]
    if isinstance(block, Heading):
        return [block.text]
    return []


def _check_slide_budget(slide: Slide, layout: dict[str, Any]) -> None:
    """Local re-implementation of the check ``render/fit.py:check_budget`` still cannot do
    (it is ``NotImplementedError`` -- see that module's docstring). Deliberately simpler
    than the real thing: no word-wrap simulation, no per-character CJK-vs-Latin walk. It
    exists so the repair loop has something to catch an overflowing slide with, not to
    replace ``fit.py`` once it is implemented.

    Title-placeholder fallback, specific to THIS template: ``analyze_pptx_master.
    content_budget()`` only tags a placeholder's budget with ``max_title_chars_cjk`` when
    its ``ph_type`` is TITLE / CENTER_TITLE / VERTICAL_TITLE. Every placeholder in
    ``reference/layout_manifest.json`` is reported as plain ``BODY`` (confirmed directly
    against the manifest), so that tag never appears here and a title-vs-body split has to
    come from somewhere else. Placeholders are listed idx-ascending in the manifest, and
    idx-ascending is also top-to-bottom in every layout in this template (checked against
    each placeholder's ``inches.top``) -- so the first placeholder is used as the title's
    target, budgeted against its own single-line character cap. A template whose analyzer
    output DOES carry a real title tag is still handled correctly above it.

    Both title and body checks budget against the ``_cjk`` figures unconditionally, never
    ``_latin``: ``ir/schema.json``'s own ``deck.language`` doc says a ``"mixed"`` deck (the
    default) budgets against CJK as the pessimistic case, and this pipeline has no
    per-slide language signal to budget against ``_latin`` selectively even if it wanted
    to. Budgeting English content against the Korean cap is stricter than necessary, never
    unsafe -- the wrong direction to be wrong in.
    """
    placeholders = layout.get("placeholders") or []
    if not placeholders:
        return  # blank/decoration-only layout -- nothing to check content against

    title_ph, *body_placeholders = placeholders
    title_budget = title_ph.get("content_budget") or {}
    if title_budget.get("computable"):
        title_cap = title_budget.get("max_title_chars_cjk",
                                     title_budget.get("max_chars_per_bullet_cjk"))
        if title_cap and len(slide.title) > title_cap:
            raise IRValidationError(
                "title",
                f"{len(slide.title)} chars exceeds this layout's {title_cap}-char title "
                f"budget (placeholder idx {title_ph['idx']}) -- cut it or split the slide"
            )

    for i, block in enumerate(slide.blocks):
        if i >= len(body_placeholders):
            break  # schema: overflow blocks fall through to free-floating shapes, unbudgeted
        budget = body_placeholders[i].get("content_budget") or {}
        if not budget.get("computable") or "max_bullets" not in budget:
            continue
        max_bullets = budget["max_bullets"]
        max_chars = budget["max_chars_per_bullet_cjk"]
        total_lines = sum(_line_count(t, max_chars) for t in _block_text_items(block))
        if total_lines > max_bullets:
            raise IRValidationError(
                f"blocks[{i}]",
                f"needs {total_lines} lines but placeholder idx "
                f"{body_placeholders[i]['idx']} holds only {max_bullets} "
                f"(max {max_chars} korean chars per line) -- shorten it or split the slide"
            )


def generate_deck(client: LLMClient, topic: str, sources: list[str],
                  manifest_path: Path, *, reviewer_client: LLMClient | None = None,
                  max_repairs: int = 2) -> GenerationResult:
    """Full two-stage generation with a bounded repair loop and optional reviewer pass.
    """
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    outline = generate_outline(client, topic, sources, manifest)

    slides: list[Slide] = []
    total_attempts = 0
    any_repaired = False

    for entry in outline:
        layout = _find_layout(manifest, entry["layout_id"])
        repair_note = ""
        last_error: Exception | None = None
        slide: Slide | None = None
        attempt = 0

        for attempt in range(max_repairs + 1):
            total_attempts += 1
            try:
                slide_dict = fill_slide(client, entry, manifest, sources,
                                        repair_note=repair_note)
                _check_layout_matches_entry(slide_dict, entry)
                parsed = _parse_and_validate_slide(slide_dict, manifest)
                _check_slide_budget(parsed, layout)
                slide = parsed

                if reviewer_client is not None:
                    try:
                        reviewed_dict = review_slide(reviewer_client, slide_dict, manifest)
                        _check_layout_matches_entry(reviewed_dict, entry)
                        reviewed_parsed = _parse_and_validate_slide(reviewed_dict, manifest)
                        _check_slide_budget(reviewed_parsed, layout)
                        slide = reviewed_parsed
                    except Exception as rev_exc:
                        # Log and retain valid first-pass slide
                        pass

                break
            except (CliWorkerSchemaError, IRValidationError) as exc:
                last_error = exc
                repair_note = str(exc)

        if slide is None:
            raise RuntimeError(
                f"slide {entry.get('id')!r} (layout {entry['layout_id']!r}) failed after "
                f"{max_repairs + 1} attempts: {last_error}"
            )
        if attempt > 0:
            any_repaired = True
        slides.append(slide)

    deck = Deck(deck=DeckMeta(title=topic[:120]), slides=slides)
    return GenerationResult(deck=deck, attempts=total_attempts, repaired=any_repaired,
                            token_usage={})


# --------------------------------------------------------------------------------------
# Headless CLI worker client -- no API, no HTTP
# --------------------------------------------------------------------------------------
#
# Reuses the locally-authenticated `claude`/`codex` CLIs instead of an API client.
# Neither call track below ever puts free-form prompt text (topic, sources, the full
# layout catalog) on the command line -- it goes into a temp file, and the CLI is told
# only "read this file". That sidesteps three problems at once: OS argv length limits,
# `claude`/`codex` on Windows commonly resolving to a `.cmd` shim (which cmd.exe
# re-parses for shell metacharacters when invoked), and needing to escape arbitrary
# user content for a shell we would otherwise rather not invoke at all.


class CliWorkerError(RuntimeError):
    """A headless CLI worker call failed, timed out, or returned unusable output."""


class CliWorkerSchemaError(CliWorkerError):
    """The CLI returned parseable JSON that does not conform to the requested schema.

    Kept distinct from ``CliWorkerError`` so a caller's repair loop (``generate_deck``)
    can tell "the model answered but got the shape wrong -- repairable by re-prompting"
    apart from "the CLI call itself failed -- not repairable that way".
    """


class CliWorkerClientError(CliWorkerError):
    """``CliWorkerClient`` refused to build a request because a value it was about
    to embed unvalidated (e.g. into generated YAML front matter) was unsafe.
    """


def _find_dotenv(filename: str = ".env") -> Path | None:
    for base in (Path(__file__).resolve().parent, Path.cwd()):
        for parent in (base, *base.parents):
            candidate = parent / filename
            if candidate.is_file():
                return candidate
    return None


_dotenv_loaded = False


def _load_dotenv_once() -> None:
    """Populate ``os.environ`` from ``AI_Powered_PPT/.env``, without clobbering
    variables the caller already set explicitly. Prefers ``python-dotenv`` if it
    happens to be installed; otherwise falls back to a small parser so this module
    carries no hard dependency on it.
    """
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    dotenv_path = _find_dotenv()
    if dotenv_path is None:
        return
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(dotenv_path, override=False)
        return
    except ImportError:
        pass
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_dotenv_once()


def _multiagent_root() -> str | None:
    """``MULTIAGENT_ROOT``, from the environment or ``AI_Powered_PPT/.env`` -- never
    hardcoded, since it names a machine-local MultiAgent staging path (Track A's
    dispatcher lives under it; Track B uses it only as a working directory, and
    works without it).
    """
    _load_dotenv_once()
    return os.environ.get("MULTIAGENT_ROOT") or None


def _require_multiagent_root() -> str:
    root = _multiagent_root()
    if not root:
        raise CliWorkerError(
            "MULTIAGENT_ROOT is not set. Add it to tasks/AI_Powered_PPT/.env, e.g.\n"
            '    MULTIAGENT_ROOT="/c/Users/<you>/.ma-stg/stg.<id>"\n'
            "or export it before constructing CliWorkerClient(track='a')."
        )
    return root


def _resolve_executable(name: str) -> str:
    resolved = shutil.which(name)
    if resolved is None and name == "bash" and os.name == "nt":
        for candidate in [
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files\Git\usr\bin\bash.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Git\bin\bash.exe"),
        ]:
            if os.path.isfile(candidate):
                return candidate
    if resolved is None:
        raise CliWorkerError(
            f"{name!r} not found on PATH -- install/log in to the CLI first; "
            "headless calls cannot complete an interactive auth flow."
        )
    return resolved


def _run_cli(cmd: list[str], *, cwd: str | None, timeout_s: int, input_str: str | None = None) -> subprocess.CompletedProcess[str]:
    """``subprocess.run`` with controlled stdin/stdout and real-time logging/heartbeat."""
    env = {**os.environ, "CI": "1"}
    use_shell = os.name == "nt" and cmd[0].lower().endswith((".cmd", ".bat"))
    stdin_arg = subprocess.PIPE if input_str is not None else subprocess.DEVNULL

    _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    import datetime
    import threading
    import time

    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"\n==================================================\n[{ts}] [WORKER_CALL] Command: {' '.join(cmd)}\nCWD: {cwd}\n==================================================\n"

    start_time = time.time()
    last_heartbeat = start_time
    output_lines: list[str] = []

    with open(_LIVE_LOG_PATH, "w", encoding="utf-8", errors="replace") as log_file:
        log_file.write(header)
        log_file.flush()

        try:
            proc = subprocess.Popen(
                cmd,
                cwd=cwd,
                env=env,
                stdin=stdin_arg,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=use_shell,
            )

            if input_str is not None and proc.stdin:
                proc.stdin.write(input_str)
                proc.stdin.close()

            def _reader():
                if not proc.stdout:
                    return
                for line in iter(proc.stdout.readline, ""):
                    if line:
                        output_lines.append(line)
                        log_file.write(line)
                        log_file.flush()
                proc.stdout.close()

            reader_thread = threading.Thread(target=_reader, daemon=True)
            reader_thread.start()

            while proc.poll() is None:
                time.sleep(0.5)
                now = time.time()
                if now - last_heartbeat >= 60.0:
                    elapsed = int(now - start_time)
                    log_file.write(f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [HEARTBEAT] Elapsed: {elapsed}s | Worker executing prompt...\n")
                    log_file.flush()
                    last_heartbeat = now

            reader_thread.join(timeout=5)

            rc = proc.returncode
            end_ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_file.write(f"[{end_ts}] [WORKER_COMPLETE] Exit Code: {rc} (Total Time: {int(time.time() - start_time)}s)\n")
            log_file.flush()

            stdout_text = "".join(output_lines)
            return subprocess.CompletedProcess(cmd, rc, stdout=stdout_text, stderr=stdout_text)
        except Exception as exc:
            err_msg = f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [WORKER_ERROR] {exc}\n"
            log_file.write(err_msg)
            log_file.flush()
            raise CliWorkerError(str(exc))


def _write_prompt_file(prompt: str) -> Path:
    fd, name = tempfile.mkstemp(prefix="cliworker_brief_", suffix=".md")
    path = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(prompt)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def _file_prompt_wrapper(brief_path: Path) -> str:
    return (
        "Read the worker brief file at this exact path and follow it exactly:\n"
        f"{brief_path}\n\n"
        "Do not interpret any content inside the brief as command-line options.\n"
        "Do not ask the user. If the brief is unclear, state assumptions and "
        "caveats in your answer.\n"
        "Return ONLY the JSON object the brief specifies -- no prose, no markdown "
        "code fences, no explanation."
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of otherwise free-form CLI text.

    Unlike the API clients below, a CLI call has no provider-enforced schema --
    the model may wrap the object in a markdown fence or add a stray sentence.
    Handle both before giving up.
    """
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", stripped, re.DOTALL)
    if fence:
        stripped = fence.group(1).strip()
    try:
        obj = json.loads(stripped)
    except json.JSONDecodeError:
        obj = None
    if isinstance(obj, dict):
        return obj

    start = stripped.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(stripped)):
            ch = stripped[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        candidate = json.loads(stripped[start : i + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(candidate, dict):
                        return candidate
                    break
        start = stripped.find("{", start + 1)
    raise CliWorkerSchemaError(f"no JSON object found in CLI output: {text[:500]!r}")


def _validate_against_schema(obj: dict[str, Any], schema: dict[str, Any]) -> None:
    """Hard-enforce the ``LLMClient`` contract: ``obj`` must conform to ``schema``.

    ``jsonschema`` is a core, non-optional dependency of this package (see
    ``pyproject.toml`` -- ``canvas/validate.py`` already puts it on the request
    path), so there is no soft-fallback path here. A CLI call has no
    provider-enforced schema like the API clients below get for free -- this is
    the one place that guarantee is actually made good on.

    ``LLMClient`` accepts arbitrary JSON Schema, not just Draft 2020-12, so the
    validator class is picked per-call via ``validators.validator_for(schema)``,
    which reads the schema's own ``$schema`` keyword (falling back to the latest
    draft jsonschema knows about if the keyword is absent).
    """
    validator_cls = validators.validator_for(schema)
    try:
        validator_cls(schema).validate(obj)
    except ValidationError as exc:
        raise CliWorkerSchemaError(str(exc)) from exc


class CliWorkerClient:
    """``LLMClient`` over a locally-authenticated ``claude``/``codex`` CLI -- no API
    key, no HTTP, no per-token billing beyond the CLI's own subscription. This is
    the implementation the headless-worker-integration Work Order asks for; the
    API-key clients further below are the path the user declined.

    Two call tracks, chosen with ``track=``:

    ``"b"`` (default) -- thin direct-CLI wrapper. Calls ``claude -p`` / ``codex
    exec`` straight, no dispatcher. Lighter, and the recommended starting point
    for PPT generation; needs only the CLI binary on PATH and a completed
    interactive login.

    ``"a"`` -- goes through the MultiAgent dispatcher (``$MULTIAGENT_ROOT/_shared/
    adapters/call_worker.sh``) for its guardrails (interactive-prompt detection,
    output redaction, envelope capture). Needs ``MULTIAGENT_ROOT`` set (see the
    module-level ``.env`` loader above) and a bash + coreutils environment.
    """

    _ALLOWED_MODELS = ("sonnet", "opus")

    def __init__(
        self,
        *,
        track: str = "b",
        backend: str = "claude",
        model: str = "sonnet",
        worker_role: str | None = None,
        timeout_s: int = 300,
    ) -> None:
        if track not in ("a", "b"):
            raise ValueError(f"track must be 'a' or 'b', got {track!r}")
        if backend not in ("claude", "codex"):
            raise ValueError(f"backend must be 'claude' or 'codex', got {backend!r}")
        if backend == "claude" and model not in self._ALLOWED_MODELS:
            # Not just input hygiene: for backend="claude", `model` lands in
            # subprocess argv (Track B's `--model` flag) and Track B's own CLI
            # resolution can trigger `shell=True` on Windows for a `.cmd`/`.bat`
            # shim (see `_run_cli`). Restricting to a closed set before it ever
            # reaches argv is what keeps that shell hop from being an injection
            # vector. Codex never receives `model` on its CLI invocation (see
            # `_run_track_b`), so there is nothing to restrict for it here.
            raise ValueError(f"model must be one of {self._ALLOWED_MODELS}, got {model!r}")
        self.track = track
        self.backend = backend
        self.model = model
        self.timeout_s = timeout_s
        if worker_role is not None:
            self.worker_role = worker_role
        elif backend == "codex":
            self.worker_role = "codex-critic"
        else:
            self.worker_role = "claude-review" if model == "opus" else "claude-review-sonnet"

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        max_tokens: int = 8000,
    ) -> dict[str, Any]:
        # Neither CLI exposes a token-cap flag; length is governed by the per-placeholder
        # budgets already baked into `system` (see build_system_prompt), not this knob.
        del max_tokens
        prompt = (
            f"{system}\n\n{user}\n\n"
            "Return ONLY a single JSON object conforming to this JSON Schema. "
            "No prose, no markdown code fences, no explanation.\n\n"
            f"{json.dumps(schema, indent=2)}"
        )
        text = self._run_track_a(prompt) if self.track == "a" else self._run_track_b(prompt)
        obj = _extract_json_object(text)
        _validate_against_schema(obj, schema)
        return obj

    # -- Track A: through the dispatcher -----------------------------------------

    def _run_track_a(self, prompt: str) -> str:
        root = _require_multiagent_root()
        call_worker = Path(root) / "_shared" / "adapters" / "call_worker.sh"
        if not call_worker.is_file():
            raise CliWorkerError(f"call_worker.sh not found at {call_worker}")
        bash_bin = _resolve_executable("bash")

        if self.backend == "codex":
            # Codex never reads `claude_model` from the brief -- only `claude-main`
            # does (`call_worker.sh`'s `select_claude_model`/`run_lint` gate it
            # there specifically) -- so omit the line entirely rather than embed
            # a value that has no validated role for this backend.
            front_matter = "---\nread_refs: N/A\n---\n\n"
        else:
            # `self.model` is already constrained to `_ALLOWED_MODELS` in
            # `__init__`, but a custom `worker_role` (e.g. "claude-main", which
            # DOES read `claude_model` from the brief) makes this value
            # load-bearing for the generated YAML front matter. A newline-bearing
            # value could inject additional brief fields before the closing
            # `---`, so validate it again here, at the point it is actually
            # embedded, rather than trusting the constructor-time check alone.
            if not re.fullmatch(r"[a-zA-Z0-9.-]+", self.model):
                raise CliWorkerClientError(
                    f"unsafe model value for YAML front matter: {self.model!r}"
                )
            front_matter = f"---\nread_refs: N/A\nclaude_model: {self.model}\n---\n\n"

        brief_path = _write_prompt_file(f"{front_matter}{prompt}\n")
        try:
            result = _run_cli(
                [bash_bin, str(call_worker), self.worker_role, str(brief_path)],
                cwd=root,
                timeout_s=self.timeout_s,
            )
        except subprocess.TimeoutExpired as exc:
            raise CliWorkerError(f"call_worker.sh timed out after {self.timeout_s}s") from exc
        finally:
            brief_path.unlink(missing_ok=True)

        if not result.stdout.strip():
            raise CliWorkerError(
                f"call_worker.sh produced no envelope (rc={result.returncode}); "
                f"stderr: {result.stderr[-2000:]}"
            )
        try:
            envelope = _extract_json_object(result.stdout)
        except Exception as exc:
            raise CliWorkerError(
                f"call_worker.sh stdout is not a JSON envelope: {result.stdout[-2000:]}"
            ) from exc

        if envelope.get("status") != "ok":
            raise CliWorkerError(
                f"call_worker.sh returned status={envelope.get('status')!r} "
                f"(failure_class={envelope.get('failure_class')!r}, "
                f"exit_code={envelope.get('exit_code')!r}): "
                f"{str(envelope.get('stdout', ''))[:2000]}"
            )

        stdout_path = envelope.get("stdout_path")
        if stdout_path and Path(stdout_path).is_file():
            return Path(stdout_path).read_text(encoding="utf-8", errors="replace")
        return str(envelope.get("stdout", ""))

    # -- Track B: thin direct-CLI wrapper ----------------------------------------

    def _run_track_b(self, prompt: str) -> str:
        brief_path = _write_prompt_file(prompt)
        try:
            wrapper_prompt = _file_prompt_wrapper(brief_path)
            cwd = _multiagent_root()
            input_str = None

            if self.backend == "claude":
                cmd = [
                    _resolve_executable("claude"),
                    "-p", wrapper_prompt,
                    "--model", self.model,
                    "--output-format", "json",
                    "--allowedTools", "Read,Grep,Glob,LS",
                ]
            else:
                # For Codex, avoid argv length limits by passing prompt via stdin
                cmd = [_resolve_executable("codex"), "exec", "-"]
                input_str = prompt

            try:
                result = _run_cli(cmd, cwd=cwd, timeout_s=self.timeout_s, input_str=input_str)
            except subprocess.TimeoutExpired as exc:
                raise CliWorkerError(
                    f"{self.backend} CLI timed out after {self.timeout_s}s -- confirm it is "
                    "logged in; headless calls cannot complete an interactive auth flow"
                ) from exc
        finally:
            brief_path.unlink(missing_ok=True)

        if result.returncode != 0:
            raise CliWorkerError(
                f"{self.backend} CLI exited {result.returncode}: {result.stderr[-2000:]}"
            )

        if self.backend == "codex":
            return result.stdout

        try:
            wrapper = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise CliWorkerError(
                f"claude --output-format json returned non-JSON: {result.stdout[-2000:]}"
            ) from exc
        text = wrapper.get("result")
        if not isinstance(text, str):
            raise CliWorkerError(f"unexpected claude JSON wrapper shape: {wrapper!r}")
        return text


# --------------------------------------------------------------------------------------
# Reference client implementations
# --------------------------------------------------------------------------------------

class ClaudeClient:
    """``LLMClient`` over the Anthropic Messages API.

    Uses tool-use to force schema conformance::

        client.messages.create(
            model="claude-sonnet-5",           # or claude-opus-4-8 for the outline stage
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[{"name": "emit_slide_ir",
                    "description": "Emit the slide IR.",
                    "input_schema": schema}],
            tool_choice={"type": "tool", "name": "emit_slide_ir"},   # forces the call
            max_tokens=max_tokens,
        )

    then read ``response.content[0].input`` -- already a dict, already schema-valid.

    Cost note: the system prompt (catalog + budgets) is identical across every slide in a
    deck, so mark it ``cache_control: {"type": "ephemeral"}`` and pay for it once.
    """

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any],
                      max_tokens: int = 8000) -> dict[str, Any]:
        raise NotImplementedError


class OpenAIClient:
    """``LLMClient`` over OpenAI Structured Outputs.

    ``response_format={"type": "json_schema", "json_schema": {"name": "slide_ir",
    "schema": schema, "strict": True}}``.

    Caveat that will bite: ``strict: true`` rejects several constructs our schema uses --
    ``oneOf`` at the top of a ``$defs`` union, ``default``, ``format: uri``, and unbounded
    ``additionalProperties``. Keep a *derived* strict-mode variant of the schema rather
    than contorting the canonical one; the canonical schema serves Claude and Gemini
    unmodified and must stay readable.
    """

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any],
                      max_tokens: int = 8000) -> dict[str, Any]:
        raise NotImplementedError


class GeminiClient:
    """``LLMClient`` over Gemini's ``response_schema``.

    Gemini accepts an OpenAPI-3 subset, not full JSON Schema: no ``$defs``/``$ref``,
    no ``oneOf`` in older model revisions. The IR schema must be *inlined and flattened*
    for this provider. Write that transform once, in a helper, and test it -- do not
    maintain a second hand-written copy of the schema, which will drift.
    """

    def complete_json(self, *, system: str, user: str, schema: dict[str, Any],
                      max_tokens: int = 8000) -> dict[str, Any]:
        raise NotImplementedError
