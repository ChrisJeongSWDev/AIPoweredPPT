---

## 1. `src/aippt/canvas/app.py`

**(a) Docstring — append after the "THE SERVER WRITES NO FILES" paragraph:**

```
/api/generate IS A MOCK, AND IT IS A MOCK ON PURPOSE (Phase 3). It calls no model, reaches no
network, and reads nothing from the prompt: it returns one hardcoded canvas-ir/1 deck, 1.5 s late.
What it is FOR is the wiring -- the editor's request shape, its loading state, its failure paths and
its hand-off to loadIR() are all exercised end to end, so that swapping the mock author for a real
one is a change to ONE function and to nothing else. It goes through validate() before it answers,
because a mock that ships an invalid deck would prove the wiring works while quietly breaking the
only thing the wiring carries.
```

**(b) Imports** — add `import asyncio` above `import io`, and extend the validate import:

```python
from aippt.canvas.validate import CanvasValidationError, StalePayloadError, validate
```

**(c) Constant** — after `DEFAULT_STEM = "deck"`:

```python
# The latency an LLM call would cost, simulated. It is not padding: the editor's loading state is
# real UI with a real failure mode (a button you can press twice), and a mock that answered
# instantly would never exercise it. It is spent ONLY on the success path -- a malformed request is
# refused immediately, because no model would have been called for that one either.
MOCK_LATENCY_S = 1.5
```

**(d) `api_export`** — replace the body-reading preamble (the `declared` / `raw` / `json.loads` block, lines 131-147) with:

```python
    ir, err = await _read_json(request)
    if err is not None:
        return err
```

Everything from `try: prs = render(ir)` onward is unchanged.

**(e) The new route** — immediately after `api_export`:

```python
@app.post("/api/generate")
async def api_generate(request: Request) -> Response:
    """{"prompt": "..."} in, canvas-ir/1 out. A MOCK: no model, no network, no prompt.

    The editor hands what comes back straight to loadIR(), which judges every element before it
    touches the stage -- so from the editor's side this endpoint is already indistinguishable from a
    real author. That is the whole deliverable: the seam is proven before there is anything behind it.
    """
    body, err = await _read_json(request)
    if err is not None:
        return err

    prompt = body.get("prompt") if isinstance(body, dict) else None
    if not isinstance(prompt, str) or not prompt.strip():
        # Refused BEFORE the sleep. No model would have been called for an empty body either, so
        # charging the user 1.5 s to be told so would be simulating the wrong thing.
        return JSONResponse(
            {"error": "validation", "detail": 'the body must be {"prompt": "<non-empty text>"}'},
            status_code=422,
        )

    # Logged BY LENGTH, never by content: this is an unauthenticated local endpoint and the deck text
    # is the user's, not ours.
    log.info("mock generate: %d-char prompt (not read -- no model is called)", len(prompt))

    ir = mock_ir(request.app.state.pin)

    # THE MOCK IS VALIDATED BEFORE IT IS SERVED, by the same validator the export path runs. Nobody
    # eyeballs this payload on its way out, and a mock that failed validation would demonstrate a
    # working pipeline while breaking the only thing the pipeline carries. It cannot fail because of
    # anything the caller sent -- so if it fails, it is OUR bug: a 500, never a 422.
    try:
        validate(ir)
    except CanvasValidationError as exc:
        log.exception("the MOCK payload does not validate -- this is a server bug, not a user error")
        return JSONResponse({"error": "mock", "detail": str(exc)}, status_code=500)

    await asyncio.sleep(MOCK_LATENCY_S)
    return JSONResponse(ir)
```

**(f) The shared body guard** — next to `_too_large()`:

```python
async def _read_json(request: Request) -> tuple[Any, JSONResponse | None]:
    """The body guard both POST routes share. Returns (payload, None) or (None, error).

    Both size checks are needed and both are here: a chunked body declares no Content-Length, so the
    header check alone can be walked straight past, and the real-length check alone would have us
    buffer a megabyte before objecting to it.
    """
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_BODY_BYTES:
        return None, _too_large()

    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:  # chunked bodies declare no length; check the real thing too
        return None, _too_large()

    try:
        return json.loads(raw.decode("utf-8")), None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        # str(exc) is json's own "Expecting ',' delimiter: line 3 column 9" -- useful, and it leaks
        # nothing but the shape of the body the caller just sent us.
        return None, JSONResponse(
            {"error": "malformed", "detail": f"body is not valid UTF-8 JSON: {exc}"},
            status_code=400,
        )
```

**(g) The mock author** — before `main()`:

```python
# --- the mock author (Phase 3) -----------------------------------------------------------------
#
# Three cards and two arrows, laid out inside BODY_SAFE (45.6, 92 -> 914.4, 500). The numbers are
# stated once, here, so that "why is that card at 656?" has an answer you can read instead of
# arithmetic you have to redo.

_CARD_Y = 232.0
_CARD_W = 244.0
_CARD_H = 116.0
_CARD_X = (60.0, 358.0, 656.0)     # 656 + 244 == 900, clear of BODY_SAFE's right edge (914.4)
_MID_Y = _CARD_Y + _CARD_H / 2.0   # the arrows leave and arrive at the cards' vertical centre

_PAPER = "#FFFFFF"
_INK = "#1A1A1A"
_MUTED = "#6B727C"

_CARDS = (
    ("card_awareness", _CARD_X[0], "Awareness", "신규 채널 3곳 · 브랜드 인지도 +18%"),
    ("card_consider", _CARD_X[1], "Consideration", "데모 요청 1.4k건 · 콘텐츠 체류 2.3배"),
    ("card_convert", _CARD_X[2], "Conversion", "파이프라인 목표 대비 106% 달성"),
)


def _card(eid: str, x: float, heading: str, detail: str) -> dict[str, Any]:
    return {
        "id": eid,
        "type": "rect",
        "x": x,
        "y": _CARD_Y,
        "w": _CARD_W,
        "h": _CARD_H,
        "fill": f"#{BRAND_RED}",
        "text": {
            "align": "CENTER",
            "valign": "MIDDLE",
            "paragraphs": [
                {"runs": [{"t": heading, "size": 18, "bold": True, "color": _PAPER}]},
                {"runs": [{"t": detail, "size": 13, "color": _PAPER}]},
            ],
        },
    }


def _arrow(eid: str, x1: float, x2: float) -> dict[str, Any]:
    return {
        "id": eid,
        "type": "connector",
        "kind": "straight",
        "x1": x1,
        "y1": _MID_Y,
        "x2": x2,
        "y2": _MID_Y,
        "color": f"#{BRAND_RED}",
        "width": 2,
        "arrow": "end",
    }


def mock_ir(pin: dict[str, Any]) -> dict[str, Any]:
    """The hardcoded deck /api/generate answers with. THE PROMPT IS NOT READ.

    Saying that plainly is the point of the function. A mock that appeared to respond to the prompt
    -- by echoing it into the title, say -- would be a mock you could not tell apart from a model,
    and the first thing it would do is carry author-supplied control characters into an IR that
    validate.py then refuses at export time. The real author replaces THIS FUNCTION and nothing else,
    which is why it takes the pin and returns a deck: no request, no app state, no I/O of its own.

    THE TEMPLATE SHA AND THE LAYOUT INDEX ARE INJECTED FROM THE LIVE PIN, never written as literals.
    A literal SHA here would go stale the day the template is re-pinned (Sec 4.3) and would hand
    every user a 409 on a deck they did not author -- the same argument that put /api/context there.

    ARRAY ORDER IS Z-ORDER: the connectors come FIRST, so the lines sit behind the cards they join.
    That is the convention the editor follows when it inserts one.
    """
    return {
        "schema": "canvas-ir/1",
        "canvas": dict(CANVAS),  # a copy -- a caller must not be able to mutate the module constant
        "target": {
            # Informational only; the server never reads a template path out of a payload.
            "template": pin["renderer_template"]["filename"],
            "template_sha256": pin["renderer_template"]["sha256"],
            "layout_index": pin["layout_signature"]["layout_index"],
        },
        "title": "Q3 Marketing Strategy",
        "elements": [
            _arrow("flow_1", _CARD_X[0] + _CARD_W, _CARD_X[1]),
            _arrow("flow_2", _CARD_X[1] + _CARD_W, _CARD_X[2]),
            {
                "id": "subtitle",
                "type": "textbox",
                "x": 60.0,
                "y": 132.0,
                "w": 840.0,
                "h": 64.0,
                # REQUIRED even when null: an omitted fill is exactly how a shape silently inherits
                # theme accent1.
                "fill": None,
                "text": {
                    "align": "LEFT",
                    "valign": "MIDDLE",
                    "paragraphs": [
                        {"runs": [{"t": "세 단계 퍼널 — 인지 → 검토 → 전환", "size": 20, "bold": True, "color": _INK}]},
                        {"runs": [{"t": "Where the Q3 spend actually moved the number.", "size": 14, "color": _MUTED}]},
                    ],
                },
            },
            *(_card(*c) for c in _CARDS),
            {
                # A mock deck that escapes into a real presentation says so ON THE SLIDE. This costs
                # one textbox and it is the difference between a demo and an incident.
                "id": "mock_note",
                "type": "textbox",
                "x": 60.0,
                "y": 392.0,
                "w": 840.0,
                "h": 44.0,
                "fill": None,
                "text": {
                    "align": "LEFT",
                    "valign": "MIDDLE",
                    "paragraphs": [
                        {"runs": [{
                            "t": "MOCK — /api/generate returned a fixed deck. No model was called (Phase 3).",
                            "size": 12,
                            "color": _MUTED,
                        }]}
                    ],
                },
            },
        ],
    }
```

Every coordinate clears `HEADER_RESERVED` (ends y=92; the highest element starts at y=132) and `FOOTER_RESERVED` (starts y=500; the lowest ends at y=436), and the x range 60→900 sits inside `BODY_SAFE`.

---

## 2. `src/aippt/canvas/static/index.html`

Insert a section in `<aside id="toolbar">`, between **View** and **Export**:

```html
    <!-- THE AI DRAFT — a MOCK, and it says so on the tin.
         /api/generate returns a FIXED canvas-ir/1 deck 1.5 s late; nothing reads the prompt and no
         model is called. What is real is the wiring: the request, the loading state, the failure
         paths, and the hand-off to loadIR() — which judges the payload exactly as it judges a file
         the user opened, because a deck a model wrote is no more trusted than one a human
         hand-edited. It is, in fact, the author most likely to put a box on the Vieworks logo.
         GENERATE REPLACES THE WHOLE STAGE. That is one undo step, and the caller pushes it. -->
    <section class="group" id="ai">
      <h2>AI draft <span class="tag">mock</span></h2>
      <label class="stacked" for="p-prompt">Prompt</label>
      <textarea id="p-prompt" rows="4" spellcheck="false"
                placeholder="예: Q3 마케팅 전략을 3단계 퍼널로 요약해줘"></textarea>
      <button type="button" id="b-generate" class="primary">Generate (✨)</button>
      <p class="hint">No model is called. The server returns a fixed deck after 1.5 s, and it
        <strong>replaces the stage</strong> (Ctrl+Z brings yours back).</p>
    </section>
```

---

## 3. `src/aippt/canvas/static/style.css`

Append to the app-chrome region (after the `#status` block, before `CONTRACT: the stage`):

```css
/* ---------------------------------------------------------------- the AI draft box (Phase 3) */

/* It is a mock and the UI says so AT REST, not only in the change log. An "AI" affordance that
   looks production-ready while returning a canned deck is the one thing this panel must not be. */
#ai h2 .tag {
  margin-left: 6px;
  padding: 1px 5px;
  border-radius: 3px;
  background: #eceef1;
  color: #6b727c;
  font-size: 10px;
  letter-spacing: 0;
}

/* #toolbar label is a flex ROW (label left, control right); a textarea in one would be squeezed to
   a slit. This is the only stacked control in the toolbar, and it opts in by name. */
#toolbar label.stacked { display: block; margin-bottom: 4px; }

#p-prompt {
  width: 100%;
  margin-bottom: 6px;
  padding: 6px 8px;
  border: 1px solid #c3c9d1;
  border-radius: 4px;
  font: inherit;
  line-height: 1.4;
  resize: vertical;
}
#p-prompt:disabled { background: #f2f4f7; color: #6b727c; }

#ai .hint { margin: 0; color: #6b727c; font-size: 11px; line-height: 1.45; }

/* THE LOADING STATE. `aria-busy` is the state; this animation is only its costume, so a screen
   reader is told what the eye is told. `disabled` is what actually stops a second POST — the pulse
   just makes 1.5 s look like work rather than a hang. */
#b-generate[aria-busy='true'] { animation: busy 1.1s ease-in-out infinite; }
@keyframes busy { 50% { opacity: .5; } }
```

---

## 4. `src/aippt/canvas/static/editor.js`

Insert after the `$('f-load')` handler (i.e. after the file-import block, before `stateFromIR`), and amend `disableExports`:

```js
  /* -------------------------------------------------------- the AI draft (Phase 3, MOCK) */

  /* POST the prompt, hand what comes back to loadIR(), and nothing else.
   *
   * THERE IS NO VALIDATION HERE, AND THAT IS THE DESIGN. loadIR() is the one door into the stage: it
   * judges every element BEFORE it clears anything, and it refuses the whole deck if one element is
   * illegal. A payload from /api/generate is no more trusted than a file the user opened — today it
   * is a fixed mock, tomorrow it is a model, and a model is exactly the author most likely to put a
   * box on the Vieworks logo. A second copy of the judge here would be a second source of truth, and
   * the first thing to drift.
   *
   * The snapshot/pushUndo pair is lifted from the file-import path for the same reason it lives
   * there: this REPLACES THE WHOLE DECK, that is one undo step, and only the caller knows whether
   * loadIR() actually accepted the payload. loadIR() must not push for itself — it is lifted out by
   * name and executed in Node against a stubbed stage, where snapshot() does not exist.
   */
  async function generate() {
    if (!CONTEXT) return;   // the server is unreachable and the button is already disabled

    var prompt = $('p-prompt').value.trim();
    if (!prompt) {
      setStatus('Type a prompt first.');
      $('p-prompt').focus();
      return;
    }

    clearWarnings();
    setBusy(true);
    setStatus('Generating…');
    try {
      var res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: prompt }),
      });
      if (!res.ok) {
        var data = {};
        try { data = await res.json(); } catch (e) { /* a non-JSON error body */ }
        warn('Generate failed (HTTP ' + res.status + ')', data.detail || res.statusText);
        setStatus('Generate failed.');
        return;
      }

      var ir = await res.json();
      var before = snapshot();
      try {
        loadIR(ir);        // the SAME gate the file import goes through: it judges, then it commits
        pushUndo(before);  // it took: replacing the whole deck is ONE step, and it is reversible
        setStatus('Generated ' + (ir.elements || []).length +
                  ' element(s) — MOCK payload; no model was called.');
      } catch (e) {
        // The stage is UNCHANGED — loadIR() judges the whole payload before it touches anything —
        // and nothing was pushed, so a refused draft costs no undo step either.
        warn('That draft was refused — the stage is unchanged', String(e.message || e));
        setStatus('Generate refused.');
      }
    } catch (e) {
      warn('Could not reach the server', String(e));
      setStatus('Generate failed.');
    } finally {
      // In a `finally`, because every path above returns from somewhere, and the one thing worse
      // than a slow button is a button that never comes back.
      setBusy(false);
    }
  }

  /* aria-busy is the STATE; the CSS pulse is only its costume. `disabled` is what actually stops a
   * second POST — a double press would race two loadIR()s and push two undo steps for one draft. */
  function setBusy(on) {
    var b = $('b-generate');
    b.disabled = on;
    b.setAttribute('aria-busy', String(on));
    $('p-prompt').disabled = on;
  }

  $('b-generate').addEventListener('click', generate);

  /* Ctrl+Z inside the PROMPT is the browser's undo, not ours.
   *
   * The global handler runs undo/redo in FRONT of its editingText() guard on purpose — so that undo
   * still works with the focus in the size box, which is exactly where the focus is right after the
   * edit you want to undo. This textarea is the one control where that is wrong: the user is typing
   * prose, they expect their keystrokes back, and what they would get instead is their whole deck
   * rolled back. Stop the event here rather than widen the global exception: the exception belongs
   * to this box, not to <input> at large. */
  $('p-prompt').addEventListener('keydown', function (ev) {
    var k = String(ev.key || '').toLowerCase();
    if ((ev.ctrlKey || ev.metaKey) && (k === 'z' || k === 'y')) ev.stopPropagation();
  });
```

And in `disableExports()`:

```js
  function disableExports(why) {
    $('b-export').disabled = true;
    $('b-json').disabled = true;
    // The draft comes from the same server. Leaving it live would offer a button whose only possible
    // outcome is the banner the user is already reading.
    $('b-generate').disabled = true;
    setStatus(why);
  }
```

Gate 1 compliance: no measured-geometry API, no `12700`, no `zIndex`, no `4472C4`, and none of the banned canvas sizes (`1920/1080/1280/720/1440/810`) appear in the added text. `editingText()` already treats `TEXTAREA` as text entry, so the Delete key won't eat a selected element while you type a prompt.

---

## 5. `tests/canvas/test_app.py`

Add `import time` to the stdlib block; change the two imports to:

```python
from aippt.canvas.app import MOCK_LATENCY_S, app, mock_ir  # noqa: E402
from aippt.canvas.pin import load_pin  # noqa: E402
from aippt.canvas.validate import validate  # noqa: E402
```

Then append the Phase 3 section at the **end** of the file (it uses `_js_function`, `_js_code`, `_toolbar`, `_panel`, `EDITOR_SRC`, all defined above):

```python
# ===============================================================================================
# PHASE 3 -- /api/generate: THE MOCK AUTHOR, AND THE SEAM A REAL ONE SLOTS INTO
# ===============================================================================================
#
# The endpoint is a mock, and every test here is written to survive it ceasing to be one. What is
# under test is the CONTRACT: the payload is a valid canvas-ir/1 deck, it carries the LIVE pin's SHA
# rather than a literal, it survives the editor's own gate, and it costs what a model call would.
# A real author replaces mock_ir() and nothing else -- if that swap breaks anything below, it broke
# the contract, not the test.
#
# THE ONE THAT MATTERS MOST is test_the_generated_deck_EXPORTS: it feeds what /api/generate said
# straight into /api/export. That closes the loop through the real validator, the real pin check and
# the real renderer, and it is the only assertion here a merely plausible-looking payload could not
# satisfy.

APP_PY = (PROJECT_ROOT / "src" / "aippt" / "canvas" / "app.py").read_text(encoding="utf-8")

# "Do not use external APIs", checked against EVERY import line in app.py -- including the lazy ones
# (uvicorn is imported inside main()). A grep is crude and it is exactly right: there is no
# legitimate reason for any of these names to appear, and the day one does, this fails.
NETWORK_LIBS = ["httpx", "aiohttp", "openai", "anthropic", "urllib.request", "socket", "requests"]


@pytest.fixture(scope="module")
def generated(client: TestClient) -> dict:
    """ONE call, reused: every assertion below is about the same payload, and it costs 1.5 s."""
    r = client.post("/api/generate", json={"prompt": "Q3 마케팅 전략을 3단계 퍼널로 요약해줘"})
    assert r.status_code == 200, r.text
    return r.json()


def test_generate_returns_a_valid_canvas_ir_payload(generated: dict):
    validate(generated)  # the real validator, not a re-implementation of it
    assert generated["schema"] == "canvas-ir/1"
    assert generated["canvas"] == {"w": 960, "h": 540, "unit": "pt"}
    assert generated["target"]["layout_index"] == 3


def test_the_generated_deck_EXPORTS(client: TestClient, generated: dict):
    """The whole point. What the mock author says, the real renderer has to be able to draw."""
    r = client.post("/api/export", json=generated)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == PPTX_MIME
    assert len(Presentation(BytesIO(r.content)).slides) == 1


def test_the_mock_carries_the_LIVE_sha_and_not_a_literal(generated: dict):
    """A literal SHA in app.py goes stale the day the template is re-pinned, and then hands every
    user a 409 on a deck they did not author. Same argument that put /api/context there."""
    sha = load_pin()["renderer_template"]["sha256"]
    assert generated["target"]["template_sha256"] == sha
    assert sha not in APP_PY, "app.py hard-codes the template SHA; it must come from the pin"


def test_the_mock_is_a_DIAGRAM_and_not_a_wall_of_text(generated: dict):
    """3-4 shapes and connecting arrows. A payload that does not exercise the IR proves only that
    JSON can be posted over HTTP."""
    els = generated["elements"]
    assert len([e for e in els if e["type"] != "connector"]) >= 3
    arrows = [e for e in els if e["type"] == "connector"]
    assert arrows, "the mock draws no connectors"
    assert all(a["arrow"] != "none" for a in arrows), "a connecting arrow with no arrowhead"
    assert els[0]["type"] == "connector", (
        "ARRAY ORDER IS Z-ORDER: the connectors must come first so the lines sit BEHIND the cards "
        "they join -- the convention the editor follows when it inserts one."
    )
    assert len({e["id"] for e in els}) == len(els), "duplicate ids -- ids become shape names"


def test_the_prompt_is_NOT_read(client: TestClient):
    """It is a mock and it must not look like anything else. Two prompts, one deck."""
    a = client.post("/api/generate", json={"prompt": "a"}).json()
    b = client.post("/api/generate", json={"prompt": "완전히 다른 요청"}).json()
    assert a == b


def test_generate_costs_what_a_model_call_would_cost(client: TestClient):
    assert MOCK_LATENCY_S == 1.5
    assert "asyncio.sleep(MOCK_LATENCY_S)" in APP_PY
    t0 = time.perf_counter()
    assert client.post("/api/generate", json={"prompt": "x"}).status_code == 200
    # asyncio.sleep never returns early; the slack is for timer granularity, not for correctness.
    assert time.perf_counter() - t0 >= 1.2


def test_a_bad_request_is_refused_IMMEDIATELY_and_never_pays_the_latency(client: TestClient):
    t0 = time.perf_counter()
    r = client.post("/api/generate", json={"prompt": "   "})
    elapsed = time.perf_counter() - t0
    assert r.status_code == 422
    assert r.json()["error"] == "validation"
    assert elapsed < 1.0, f"the refusal slept anyway ({elapsed:.2f}s); no model would have been called"


@pytest.mark.parametrize("body", [{}, {"prompt": ""}, {"prompt": 3}, {"prompt": None}, [], "x"])
def test_generate_refuses_every_shape_of_missing_prompt(client: TestClient, body):
    assert client.post("/api/generate", json=body).status_code == 422


def test_generate_shares_the_body_guard_with_export(client: TestClient):
    """One guard, two routes. A second copy is a second thing to forget to update."""
    from aippt.canvas.app import MAX_BODY_BYTES

    big = client.post(
        "/api/generate",
        content=b"x" * (MAX_BODY_BYTES + 1),
        headers={"Content-Type": "application/json"},
    )
    assert big.status_code == 413

    bad = client.post(
        "/api/generate", content=b'{"prompt": ', headers={"Content-Type": "application/json"}
    )
    assert bad.status_code == 400
    assert "Traceback" not in bad.text


def test_generate_writes_nothing_to_disk(client: TestClient):
    before = _tree(PROJECT_ROOT)
    assert client.post("/api/generate", json={"prompt": "x"}).status_code == 200
    assert _tree(PROJECT_ROOT) == before


@pytest.mark.parametrize("lib", NETWORK_LIBS)
def test_the_mock_author_reaches_no_external_api(lib: str):
    imports = [ln for ln in APP_PY.splitlines() if re.match(r"\s*(import|from)\s", ln)]
    assert not any(lib in ln for ln in imports), f"app.py imports {lib}; the mock calls nothing"


def test_mock_ir_is_a_pure_function_of_the_pin():
    """The seam. A real author replaces THIS function -- so it takes the pin and returns a deck, with
    no request, no app state and no I/O of its own."""
    ir = mock_ir(load_pin())
    validate(ir)
    assert ir["target"]["template_sha256"] == load_pin()["renderer_template"]["sha256"]


# --- the editor's half of the seam ---------------------------------------------------------------


def test_the_prompt_and_the_generate_button_live_in_the_toolbar():
    tb = _toolbar()
    assert 'id="p-prompt"' in tb and 'id="b-generate"' in tb
    assert 'id="p-prompt"' not in _panel(), (
        "the prompt is not a property of the SELECTION. The property panel is hidden whenever "
        "nothing is selected -- which is exactly the state you write a prompt in."
    )


def test_generate_posts_the_prompt_to_the_mock_endpoint():
    body = _js_function("generate")
    assert "'/api/generate'" in body
    assert "JSON.stringify({ prompt: prompt })" in body
    assert "$('b-generate').addEventListener('click', generate)" in EDITOR_SRC


def test_generate_hands_the_payload_to_the_SAME_gate_the_file_import_uses():
    """No second copy of the judge. A deck a model wrote is no more trusted than a file a human
    hand-edited -- and it is the author most likely to put a box on the Vieworks logo."""
    body = _js_function("generate")
    assert "loadIR(ir)" in body
    assert "illegalReason" not in body, "generate() re-implements the judge; loadIR() IS the judge"


def test_generate_is_one_undo_step_and_the_CALLER_pushes_it():
    """It replaces the whole deck. loadIR() must not push for itself: it is lifted out by name and
    run in Node against a stubbed stage, where snapshot() does not exist."""
    body = _js_function("generate")
    assert "snapshot()" in body and "pushUndo(before)" in body
    assert "pushUndo" not in _js_function("loadIR")


def test_a_refused_draft_costs_no_undo_step():
    body = _js_code("generate")
    assert body.index("loadIR(ir)") < body.index("pushUndo(before)"), (
        "generate() pushes the undo step before it knows loadIR() accepted the draft"
    )


def test_the_loading_state_is_always_cleared():
    """The one thing worse than a slow button is a button that never comes back."""
    body = _js_code("generate")
    assert "setBusy(true)" in body and "finally" in body
    busy = _js_function("setBusy")
    assert "disabled = on" in busy, "the button is not disabled -- a double press posts twice"
    assert "aria-busy" in busy, "the loading state is invisible to a screen reader"


def test_generate_is_disabled_when_the_server_is_unreachable():
    assert "b-generate" in _js_function("disableExports"), (
        "the draft comes from the same server as the export; leaving the button live offers an "
        "action whose only possible outcome is the banner the user is already reading."
    )
```

---

## Assumptions and caveats

- **Nothing was applied and nothing was run.** `pytest` was never executed (code execution is denied here, as in Phase 0 and Phase 2), so treat every line above as unrun code. The tests I wrote are also unrun.
- **The prompt is deliberately not echoed into the payload.** The brief says "hardcoded payload"; echoing author text into the title would carry control characters into an IR that `validate.py` then rejects at export time, and would make the mock indistinguishable from a real author. I chose the honest mock and put the reasoning in `mock_ir()`'s docstring.
- **The 1.5 s sleep is on the success path only.** A malformed request is refused immediately — no model would have been called for it. A test pins that behaviour both ways.
- **The mock says "MOCK" on the slide itself** (a footnote textbox), so a canned deck that escapes into a real presentation announces itself.
- **`phase3_change_detail.md` was not written.** Its content is essentially this message; whoever re-runs this with write permission should save it to `tasks/AI_Powered_PPT/phase3_change_detail.md` as the brief's YAML block requires.

---
claude_model: opus
mode: continuation
target_repo: .
change_detail_path: tasks/AI_Powered_PPT/phase3_change_detail.md
write_scope: src/aippt/canvas/static/index.html, src/aippt/canvas/static/editor.js, src/aippt/canvas/static/style.css, src/aippt/canvas/app.py, tests/canvas/test_app.py
