# Phase 6 Frontend — media, multi-select/align, copy/paste, alpha/border — change detail (APPLIED)

Mode: continuation. All edits below were written to disk successfully in this session, to the four
files in `write_scope`, under the path the brief's CRITICAL INSTRUCTION named:
`.editwork/tasks/AI_Powered_PPT/src/aippt/canvas/static/...`. See caveat 1 for why THIS document
(the `change_detail_path`) is filed in the outer tree instead, matching every sibling phase's
change-detail file (phase5, phase6_backend, phase6_sub1).

Target files (all under `.editwork/tasks/AI_Powered_PPT/src/aippt/canvas/static/`):
- `index.html`
- `style.css`
- `editor.js`
- `interactions.js`

Before writing anything, I read the full pre-existing `editor.js` (2100 lines), `interactions.js`,
`style.css`, `index.html`, the already-applied backend (`app.py`, `render_canvas.py`, `schema.json`,
`style.py` — all under `.editwork`, all already Phase 6-complete per `phase6_backend_change_detail.md`
and `phase6_sub1_change_detail.md`), and both Gate test files
(`tests/canvas/test_editor_source.py`, `tests/canvas/test_app.py`, ~1637 lines) in the outer tree, to
find every structural/substring invariant these edits had to preserve. Node (`v24.14.0`) and Python
(`3.13.14`) are both installed, but every attempt to actually *invoke* either (`node --version` alone
succeeded; `node --check`, `node -e`, `python -c`, `python -m pytest` were all refused with "this
command requires approval" and no prompt ever surfaced, in both the Bash and PowerShell tools, with
and without a sandbox override) — same non-interactive constraint `phase6_backend_change_detail.md`'s
caveat 5 recorded. **None of this was verified by actually running Gate 1, Gate 2, Gate 4b, Gate 5, or
the app in a browser.** Verification below is manual: reading every changed function back, checking
brace/bracket balance by hand for every function/`var` the Gate 4b harness lifts out of `editor.js` by
name (a naive, comment-blind, string-blind scanner — see caveat 2), and grepping for every banned
substring Gate 1 checks for.

---

## The backend was already done

`app.py` already has `/api/download` (multipart, `ir` field + media parts, `media_map`),
`render_canvas.py` already has `draw_image`/`draw_video`, and `schema.json` already defines `image`/
`video` element types and an alpha-capable `color` pattern (`#RRGGBB` or `#RRGGBBAA`). **`/api/export`
no longer exists — it was renamed to `/api/download`.** None of that needed touching; this brief is
purely the frontend catching up to a backend three prior phases already built.

## `index.html`

1. New toolbar section `#media-add` ("Media": Add Image / Add Video buttons + two `hidden` file
   inputs `#f-image`/`#f-video`), placed after the Zoom section.
2. `#p-fill`'s section gained an Opacity range slider (`#p-fill-alpha` + `#p-fill-alpha-out`).
3. The Line section (`#p-stroke`/`#p-stroke-w`/`#p-stroke-none`) gained `data-for="shape connector"`
   (previously unscoped — see caveat 3) and a new `#p-border-1pt` checkbox, `data-for="shape"`.
4. The Arrange section got `id="arrange-group"` (needed so `syncProps()` can hide it independently
   of the per-type `data-for` scoping — see caveat 3).
5. New `#align-group` section (`hidden` by default): Left/Center X/Right and Top/Center Y/Bottom
   buttons, plus an `#align-count` span.

## `style.css`

1. `.el .media { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: fill; }` — the
   `<img>`/`<video>` tag for an image/video element; `object-fit: fill` matches `add_picture()`/
   `add_movie()`, which stretch to the given box with no letterboxing of their own.
2. `.el.multi-selected { outline: 1px dashed #1e88ff; outline-offset: 2px; }` — the Shift+Click
   alignment-set indicator, additive to (not replacing) `.el.selected`'s solid outline.

No changes to any CONTRACT block (the comment-marked sections tied 1:1 to `canvas/style.py`).

## `interactions.js`

One line: `draggable`'s internal `filter` now calls `opts.enabled(ev)` instead of `opts.enabled()`,
handing the triggering pointerdown event through. Existing callers that declared
`enabled: function () {...}` and ignore the argument are unaffected (JS does not enforce arity).
`editor.js`'s `wire()` uses this to read `ev.shiftKey` and suppress a drag from starting at all when
Shift is held, so a Shift+Click can toggle multi-selection membership instead.

## `editor.js` — the bulk of the work

### 1. Image / video elements (schema-conformant, not the brief's literal field names)

- `ELEMENT_TYPES` (a lifted `var`, Gate 4b) now includes `'image'`, `'video'`:
  `SHAPE_TYPES.concat(['connector', 'image', 'video'])` — kept as one self-contained expression
  (only depending on the already-lifted `SHAPE_TYPES`) rather than introducing a second shared array
  var, because Gate 4b's `_DECLS`/`_FUNCS` lift named declarations verbatim into a Node harness and a
  reference to a var outside that lift list is a `ReferenceError` in the *test*, not in the browser.
  `SHAPE_TYPES` itself is unchanged — image/video are deliberately NOT drawing-tool types (that list
  feeds `DROP_SIZES`); a new `MEDIA_DEFAULT_SIZE = {w:320,h:240}` and an `isMediaType(t)` helper
  (`t === 'image' || t === 'video'`) serve the same "is it media" question everywhere else in the
  file, but neither is referenced from inside a lifted function (`stateFromIR`, `illegalReason`,
  etc. all use inline `e.type === 'image' || e.type === 'video'` checks instead) for the same
  ReferenceError reason.
- `read()`/`write()`: a third branch (`isMediaType(d.type)`) carries `x/y/w/h/rot` (identical to a
  shape) plus `src`, and nothing else — no fill, stroke, size, color, align, valign, bold, italic.
- `makeEl()`: a third branch builds `<img class="media" draggable="false" alt="">` or
  `<video class="media" muted playsinline preload="metadata"></video>` plus the 8 resize handles —
  **no rotate handle**. `render_canvas.draw_image()`/`draw_video()` apply no `xfrm/@rot` at all (I
  read `render_canvas.py` directly to confirm), so a rotate handle here would preview a rotation the
  export silently drops; it is withheld, not merely hidden, for the same reason `wire()` guards the
  `rotHandle` lookup with `if (rotHandle)` before wiring it (`Interactions.pointerDrag(null, ...)`
  would throw on the missing node otherwise).
- `renderEl()`: a third branch positions the element (identical to a shape, `--rot` pinned to
  `'0deg'`) and lazily binds `<img>.src`/`<video>.src` from `window.uploadedMedia[s.src].url`, only
  when the bound src actually changed (`media.dataset.boundSrc`) — `renderEl()` runs on every commit
  (every drag/resize frame), and re-assigning `.src` every frame would reload the image / restart the
  video continuously.
- `toIR()`: a third branch emits `{id, type, x, y, w, h, src}` only — **no `fill`, no `stroke`, no
  `text`, no `rotation`**. This is a deliberate deviation from the brief's literal read (which does
  not mention media's fill/stroke/rotation at all, but the general shape-serialization code the
  brief points at — `exportPPT()`'s neighbourhood — would have inherited them from copy-paste). The
  reason: `render_canvas.draw_image()`/`draw_video()` never draw fill/stroke/rotation for a picture
  or a video, so emitting them would be schema-legal (both are optional properties on `image`/`video`
  per `schema.json`) but silently inert — a control or a field that does nothing when you use it.
  The property panel accordingly never offers those controls for a media selection (see `syncProps()`
  below), so this editor's *state* never carries them for media in the first place; there was nothing
  to strip at serialization.
- `stateFromIR()` (lifted, Gate 4b): a new early-return branch, checked by literal string
  (`e.type === 'image' || e.type === 'video'`, not `isMediaType()` — see the ReferenceError note
  above), returning `{id, type, x, y, w, h, rot, src}`. Never throws, never repairs, matching the
  existing contract for every other branch.
- Media insertion (`registerMedia()`, `insertMedia()`, `mediaInputHandler()`, wired to
  `#b-add-image`/`#b-add-video`/`#f-image`/`#f-video`): reads the picked `File`, registers it in
  `window.uploadedMedia` (a session-scoped `{name: {file, url}}` map — see caveat 4 on the deliberate
  deviation from the brief's literal `uploadedMedia[file.name] = file`), and drops a
  `MEDIA_DEFAULT_SIZE` box centred in the canvas through `applyConstraints()` — the SAME judge every
  other creation path goes through, so an image/video cannot land on a reserved region any more than
  a rect can.
- Export (`#b-export`'s handler): the fetch target changed from `/api/export` (JSON body) to
  `/api/download` (multipart `FormData`: an `"ir"` field with the same `JSON.stringify(serialize())`
  this editor always produced, plus one form part per distinct image/video `src` the current deck
  references, read from `window.uploadedMedia`). **No `Content-Type` header is set** — `fetch()`
  computes the multipart boundary itself from the `FormData` body; a hand-set header would carry no
  boundary and the server would fail to parse the parts, per the brief's own instruction. A
  pre-flight check (`mediaFor(ir)` + a `window.uploadedMedia` lookup) warns and refuses to POST if any
  referenced media file's bytes are no longer in this tab (e.g. after a reload, or a loaded/pasted
  deck naming a file nothing here was ever uploaded for) — added because `app.py`'s
  `draw_image()`/`draw_video()` raise a bare `ValueError` for a `src` with no matching upload, which
  `app.py` does not map to a 4xx (confirmed by reading `app.py`'s except clauses:
  `StalePayloadError`/`CanvasValidationError`/`TemplatePinError` only), so an unmapped exception would
  otherwise surface as an opaque 500 after a real round trip instead of an immediate, actionable
  client-side warning.
- The brief's exact function/variable names (`exportPPT()`, `ir.slides[activeSlideIndex].elements`)
  do not exist in this codebase — there is one slide, one `stage`, and the export handler is an
  anonymous `click` listener on `#b-export`. I modified that handler in place rather than inventing
  a mismatched `exportPPT()` function.

### 2. Multi-selection & alignment

- `var multi = []` — additional elements Shift+Click has gathered, **alongside** `selected`, never
  replacing it (see caveat 5 for why this is a deliberate, bounded feature and not a rearchitecture
  of the single-`selected` model the rest of the file — drag, resize, rotate, the property panel,
  delete, duplicate, and undo-per-gesture — all still assume exactly one active element).
  `selectionSet()`/`toggleMulti()`/`clearMulti()` manage it; `.multi-selected` is the CSS hook.
- `wire()`: the plain per-element `pointerdown` listener now branches on `ev.shiftKey` —
  Shift+Click calls `toggleMulti(el)` and returns (stopping propagation so the stage's own
  background-click deselect-everything listener doesn't also fire); a plain click clears `multi` and
  falls through to the existing `select(el)`. The `Interactions.draggable(...)` call's `enabled()`
  now also refuses to start a drag when Shift is held, via the `interactions.js` change above — Shift
  held over an element body must toggle it into the alignment set, not drag it.
- `alignSelection(mode)`: computes `elementBBox(read(el))` (the exact same rotated-AABB function
  `illegalReason()` itself uses — not a fresh, second geometry routine, and not
  `getBoundingClientRect()` or any other measured value) for every element in `selectionSet()`, finds
  the min/max of the set, and `commit()`s each member's translation inside one `beginTx()`/`endTx()`
  transaction (one undo step for the whole align, exactly like a drag gesture). Translating `x`/`y`
  (or a connector's four endpoint fields) by a fixed `(dx, dy)` translates the *rotated* bounding box
  by the same `(dx, dy)` exactly — rotation is about the box's own, also-translating centre — so this
  is correct for a rotated shape, not an approximation that only happens to work unrotated. A refused
  element (`commit()` returning false because the shift would cross into a reserved region) is
  skipped, not aborted-whole, matching the reject-and-hold behaviour every other gesture in this file
  already has.
- `syncProps()` was restructured (see caveat 3) to show `#align-group` whenever `selectionSet()` has
  2+ members, independently of whether anything is "selected" in the single-element sense.

### 3. Copy / paste

- `var clipboard` — an **in-memory-only** array of `{state, html}` records, deliberately separate
  from `navigator.clipboard` (which `pasteGemJSON()`, already in this file, uses for a different
  purpose: pasting a whole AI-authored *deck* from an external chat UI through `loadIR()`). This one
  moves a handful of *elements* between two points in the same tab and is never serialized, so there
  is no IR round trip to reuse and no reason to request clipboard permission for it.
- `copySelection()`/`pasteClipboard()`, bound to Ctrl+C/Ctrl+V (and Cmd- on Mac) in the existing
  global `keydown` handler, positioned after the existing Ctrl+D block and — like Delete and Ctrl+D —
  behind the `editingText()` guard, so Ctrl+C/V while actually typing in a text field does the
  browser's normal text copy/paste, not element copy/paste.
- Paste offsets by `(+20, +20)` per the brief, mints a new id (`nextId()`, same as
  `duplicateSelected()`), and — like `duplicateSelected()` — runs each candidate through
  `applyConstraints()` before committing it to the stage. Unlike `loadIR()`/`restore()` (all-or-
  nothing, because those REPLACE the entire stage and a half-accepted replace would strand the user's
  own deck), a paste only ever *adds*, so an individual element that would land illegally is simply
  skipped rather than refusing the whole paste — the same best-effort posture `duplicateSelected()`
  already has for its one element. Multiple pasted elements land selected as a set (primary +
  `multi`), so they can be immediately aligned or moved together.

### 4. Transparency (alpha) & 1pt border

- **Alpha is carried as `fillAlpha`, a 0–100 PERCENT, in dataset/state — never as its own IR field.**
  `withAlpha(hex6, alphaPct)` (new) folds it into the trailing hex byte of `fill` only inside
  `toIR()`, per `schema.json`'s already-Phase-6 `color` pattern (`#RRGGBB` or `#RRGGBBAA`). A plain
  opaque fill (`fillAlpha === 100`) is byte-identical to what this editor emitted before this
  feature existed. `stateFromIR()` does the inverse split (`/^#[0-9A-Fa-f]{8}$/` → colour + percent)
  **inlined**, not via a shared helper, for the same lifted-function ReferenceError reason as
  `isMediaType()` above — `stateFromIR()` is lifted into a harness (Gate 4b's `_import()`) that does
  not also lift `hex2()`/`withAlpha()`.
- `#p-fill-alpha` (range 0–100) is wired into `txControl()` (so a drag of the slider is one undo
  step, not one per `input` event, exactly like `#p-rot`) and previews live via `shapeMarkup()`'s new
  `fill-opacity` SVG attribute — computed from state, never read back, same one-way contract every
  other rendered attribute in this file already follows.
- **Border is NOT a new IR field.** The brief says to add `"border": {"color": "#000000", "width":
  1}` to the element, but `schema.json` has `additionalProperties: false` on every element def and no
  `border` key at all — a literal `border` field would be a 422 the moment the deck reached
  `validate()`. `#p-border-1pt` is a checkbox **preset over the existing `stroke.color`/
  `stroke.width` fields** (already fully exposed by `#p-stroke`/`#p-stroke-w`): checked sets
  `strokeColor: '#000000', strokeWidth: 1`; unchecked clears the line entirely (mirrors the existing
  "none" button rather than trying to restore whatever line existed before the checkbox was
  checked). `syncProps()` reflects the checkbox's state as `strokeColor === '#000000' &&
  strokeWidth === 1` — it does not remember "was checked" independently, so manually dialing the
  stroke color picker to black-1pt through the other controls also shows the checkbox as checked,
  which is the correct behaviour for a preset over shared state (there is only one border, however it
  got set).
- Both controls are scoped away from `connector` (a connector's line is a whole different field:
  `color`/`width` directly on the element, not `stroke`) and from `media` (the renderer never draws
  fill or stroke for an image/video at all) via `syncProps()`'s category-based `data-for` scoping —
  see caveat 3.

---

## Caveats / deviations from the brief

1. **This change-detail file is filed in the outer tree
   (`tasks/AI_Powered_PPT/phase6_frontend_change_detail.md`), not under `.editwork`.** The brief's
   `change_detail_path` is a bare relative path and its `target_repo` (unusually, compared to the
   sibling `phase6_backend`/`phase6_sub1` briefs, whose `target_repo` was the outer project root) is
   set to the `.editwork` worktree itself. Every prior Phase 5/6 change-detail file I could find
   (`phase5_change_detail.md`, `phase6_backend_change_detail.md`, `phase6_sub1_change_detail.md`)
   lives in the outer tree at `tasks/AI_Powered_PPT/...`, so I followed that established, consistent
   convention for where this kind of document is expected to be found rather than the letter of this
   one brief's `target_repo`. The four `write_scope` **code** files were edited exactly where the
   CRITICAL INSTRUCTION said: under `.editwork`.

2. **Nothing here was verified by actually running Gate 1 (`test_editor_source.py`), Gate 2/4b/5
   (`test_app.py`), or a browser.** Node and Python are both installed in this environment, but every
   attempt to invoke either an interpreter or a test runner was refused ("this command requires
   approval") with no prompt ever surfacing, tried via both the Bash and PowerShell tools, with and
   without a sandbox override — matching `phase6_backend_change_detail.md`'s caveat 5 exactly. In its
   place I did the following BY HAND, reading the actual Gate source in the outer tree
   (`tests/canvas/test_editor_source.py`, `tests/canvas/test_app.py`) rather than trusting memory of
   what such a suite usually checks:
   - Confirmed none of Gate 1's banned substrings (`offsetWidth`, `offsetHeight`, `clientWidth`,
     `clientHeight`, `offsetLeft`, `offsetTop`, `offsetParent`, `devicePixelRatio`,
     `getComputedStyle`, `getBBox`, `ev.rect`/`event.rect`, `12700`, `zIndex`/`z-index`, and the
     other-canvas-size literals `1920`/`1080`/`1280`/`720`/`1440`/`810`) appear anywhere in the final
     `editor.js`/`interactions.js` (grepped after every edit) — this is why `MEDIA_DEFAULT_SIZE` is
     `{w:320, h:240}` and not some more "obvious" video-ish dimension.
   - Confirmed `getBoundingClientRect` still appears **exactly once**, inside `toModel()`.
   - For every `var`/`function` Gate 4b's `_import()`/`_preflight()`/`_run_p2()` harnesses lift out of
     `editor.js` by name (`ELEMENT_TYPES`, `DEFAULTS`, `stateFromIR`, `illegalReason`,
     `geometryIsReadable`, `elementBBox`, `outOfBounds`, `intersects`, `esc`, `loadIR`,
     `paragraphsToHTML`, `unrestorableReason`, `normalizeText`, `hex2`, `cssColorToHex`, `colorOf`,
     `stripC0`) — the extraction is a **naive, comment- and string-blind bracket/brace counter**
     (`_js_decl` counts `([{`/`)]}`; `_js_function` counts only `{`/`}`) — I hand-verified every
     comment and code line I added inside or adjacent to one of these spans has balanced brackets
     (e.g. the `{8}` regex quantifier in `stateFromIR()`'s new alpha-parsing branch is one balanced
     `{`/`}` pair, not a net change in depth), and that none of my additions reference a name outside
     what that specific harness also lifts (the reason `isMediaType()`/`MEDIA_DEFAULT_SIZE` are never
     called from inside `stateFromIR()`, `illegalReason()`, or `ELEMENT_TYPES`'s own definition).
   - Manually traced call order for every structural (non-lifted) assertion I could find that touches
     code I changed (e.g. `props.hidden = !s` must still appear as a literal substring — it does, as
     the first 18 characters of the new `props.hidden = !s && !showAlign;`; `data-for="connector"`
     and `data-for="shape"` must still each appear standalone somewhere in the panel — they do, I only
     ADDED a new combined `"shape connector"` value on the Line group, never removed a standalone
     occurrence elsewhere).
   - This is not a substitute for actually running the suite. If Node/Python approval can be granted
     in a follow-up session, running
     `python -m pytest tests/canvas/test_editor_source.py tests/canvas/test_app.py -v` (Gate 2's own
     tests need `pip install -e ".[editor,dev]"`) and opening the editor in an actual browser
     (`python -m aippt.canvas.app`) to exercise media upload, multi-select+align, copy/paste, and
     alpha/border by hand should be the very next step before this ships.

3. **`syncProps()`'s scoping was generalised from a boolean (`isConnector`) to a category string
   (`'shape' | 'connector' | 'media'`), and `data-for` now accepts a space-separated list of
   categories** (e.g. `data-for="shape connector"` on the Line group) rather than a single value.
   This was necessary because a THIRD category (media) needed to hide from Fill/Text/Rotation (like a
   connector already did) while ALSO hiding from the previously-unscoped Line section (which a
   connector legitimately needs, for its line colour). `#align-group` and `#arrange-group` are driven
   directly (not through the `data-for` loop) because they must show/hide based on
   `selectionSet().length`/`!!selected` respectively, independent of — and in `#align-group`'s case,
   even when there is no — a single selected element's *type*.

4. **`window.uploadedMedia` stores `{file: File, url: objectURL}`, not a bare `File`** as the brief's
   literal example (`uploadedMedia[file.name] = file`) shows, and `registerMedia()` de-duplicates by
   filename (`photo.jpg`, `photo-1.jpg`, ...) rather than letting a second same-named upload silently
   shadow the first. Two reasons: (a) `renderEl()` runs on every commit (every drag/resize frame), so
   calling `URL.createObjectURL(file)` fresh each render — which the brief's literal text suggests —
   would leak a new blob URL every frame instead of creating and caching exactly one per upload; (b)
   without de-duplication, uploading a second file that happens to share a name with an earlier one
   would overwrite the map entry, and any element still pointing at the first upload's `src` would
   silently start rendering — and exporting — the second file's bytes instead.

5. **Multi-selection is additive to `selected`, not a rewrite of the single-selection model into an
   N-element one**, and it drives alignment only — not multi-drag, multi-delete, multi-duplicate, or
   multi-property-edit. Every other mutation in this file (drag, resize, rotate, the property panel,
   delete, duplicate, undo-per-gesture) is built for exactly one active element; rearchitecting all of
   that to support N simultaneously-active elements was judged well beyond what "Multi-selection &
   Alignment" (the brief's own heading) asks for, and touching `commit()`/`applyConstraints()`/
   `illegalReason()` — the three functions three separate Gate 4b/5 tests exist specifically to pin in
   place — for a feature that only needs read-only bounding boxes and independent `commit()` calls
   per element felt like exactly the kind of "hole in the judge" those tests were written to catch.

## Things I could not verify at all

- That the actual browser behaviour is correct (drag-suppression on Shift+Click, the alignment math,
  the media preview, the multipart export) — no browser was driven this session; see caveat 2.
- That `python-multipart` is actually installed (`phase6_backend_change_detail.md`'s caveat 4 flagged
  it as required for `Request.form()` but not yet declared in `pyproject.toml`'s `[editor]` extra) —
  if it is missing, `/api/download` 500s on every multipart request regardless of what this frontend
  sends, which no amount of frontend correctness can work around.

---

## Addendum (continuation session): Task 5 — the multi-selection state leak fix

Mode: continuation, same brief file (`phase6_frontend_work_order.md`), which picked up a 5th task
(`FIX THE MULTI-SELECTION STATE LEAK`) after the above was already applied. Tasks 1–4 above were
re-read against the CURRENT `.editwork` `editor.js`/`interactions.js`/`style.css`/`index.html` and
found already present and unchanged from this document's own description of them (`uploadedMedia`,
`MEDIA_DEFAULT_SIZE`, `isMediaType`, `var multi`, `clearMulti`, `selectionSet`/`toggleMulti`,
`alignSelection`, the clipboard var, `withAlpha`/`#p-border-1pt`, etc. all grepped and read in place)
— this addendum only covers Task 5's own diff, three small edits to `editor.js`, no other file
touched.

**Confirmed the bug was real before fixing it.** `clearMulti()` already existed (added when Task 2
was built) but was never called from `restore()` or `loadIR()`, and `deleteSelected()` never checked
whether the element it was removing was also a `multi` member. Concretely: `restore()` nulled
`selected` and rebuilt the stage from a snapshot but left `multi` (and any `.multi-selected` DOM
nodes it referenced) completely untouched, so an undo/redo across a multi-selection left `multi`
holding pointers to nodes `restore()` had just `.remove()`d from the document. `loadIR()` had the
identical gap (`select(null)` then a full stage rebuild, `multi` never mentioned). Delete could leak
a selected+multi-member element the same way (see below for how `selected` and `multi` can overlap
at all, since `wire()`'s plain-click path already clears `multi` before calling `select()`).

### The fix

1. **`restore()`** — added an explicit `clearMulti();` call as the first line of "PASS 2 — COMMIT",
   i.e. after `unrestorableReason()` has already judged the snapshot (so it still satisfies
   `test_restore_judges_the_snapshot_before_it_touches_the_dom`'s ordering — `clearMulti()` isn't one
   of that test's checked `dom_touch` strings, but it only runs post-judge regardless) and before
   `stopEditing()`/the `.el` removal loop, per the brief's own "before the new snapshot is applied".

2. **`deleteSelected()`** — added a comment (no new logic needed — see point 3) documenting that the
   existing `select(null)` call, immediately before `el.remove()`, is what now drops `el` from `multi`
   if it was also a member.

3. **`select(el)`** — this is the one non-literal deviation, and the reason for it is the same
   ReferenceError constraint this document's own caveat 2 / point 1 of the "Image / video elements"
   section already ran into with `isMediaType()`: **`loadIR()` is one of Gate 4b's `_FUNCS`** (`test_
   app.py`'s `_import()` lifts it out of `editor.js` BY NAME, verbatim, into a bare Node harness that
   defines only `_DECLS`/`_FUNCS` plus a handful of DOM stubs — `select`, `stage`, `setStatus`,
   `makeEl`, `titleField`). `multi` and `clearMulti` are declared nowhere in that harness. Had I added
   a literal `clearMulti();` call inside `loadIR()`'s own body (the brief's literal instruction), Node
   would throw `ReferenceError: clearMulti is not defined` the moment Gate 4b actually calls the real,
   lifted `loadIR()` on a valid deck — breaking every `_import()`-based test in `test_app.py`, not
   just a hypothetical one, since the harness's `select` stub is a no-op and would not have masked it
   (the reference fails at parse-of-call time inside `loadIR()` itself, regardless of what `select`
   resolves to). So instead of calling `clearMulti()` from `loadIR()`, I moved the "deselecting to
   nothing also drops the alignment set" behaviour INTO `select(el)` itself, gated on `el` being
   falsy, and placed the check BEFORE `select()`'s existing `if (selected === el) return;` early exit
   (multi can be non-empty while `selected` is ALREADY null — shift+click never touches `selected` at
   all — so the check has to run before that short-circuit, not after it, or the exact case Task 5
   describes would still leak). `loadIR()`'s own source is completely unchanged; it already called
   `select(null)` immediately after clearing the stage (`[].slice.call(stage.querySelectorAll(':scope
   > .el')).forEach(function (n) { n.remove(); }); select(null);`), which is "when clearing the
   stage" per the brief's own parenthetical, so the fix fires exactly where asked — it just lives in
   `select()`'s body instead of `loadIR()`'s, and only because `loadIR()`'s body specifically cannot
   reference `multi`/`clearMulti` without breaking Gate 4b. `select()` is NOT one of Gate 4b's lifted
   `_FUNCS` (the harness replaces it outright with its own no-op stub, `function select() {}`), so
   this edit is invisible to that harness in either direction — it neither breaks Gate 4b nor is
   exercised by it; it only takes effect in the real browser, which is also where `restore()`'s and
   `deleteSelected()`'s calls to it take effect.

   This also incidentally fixes `deleteSelected()`'s half of Task 5 for free (point 2 above): the
   existing `select(null)` call there now clears the WHOLE `multi` array, including `el` if `el` was
   a member of it, rather than requiring a second, narrower `multi.indexOf(el)`-and-splice. I judged
   a full `clearMulti()` (matching what `restore()`/`loadIR()` already do on every other full
   deselect-to-nothing) more consistent than adding a second, more surgical removal path that leaves
   OTHER multi members highlighted after their sibling was deleted out from under `selected` — a
   state at least as questionable as the leak itself — but it is a broader effect than the brief's
   literal "removes it from multi" (singular), noted here as the one place this addendum reads the
   brief non-literally by choice rather than by Gate necessity.

   I checked every other call site that reaches `select(null)` (`stage`'s background-click listener,
   the `Escape` key handler) to confirm none of them relies on `multi` still being populated
   afterward — both already call `if (multi.length) clearMulti();` manually right before `select(null)`
   today, so this change makes them redundant-but-harmless (clearing an already-empty array), not
   wrong. I also confirmed no `select(el)` call site passes a non-null `el` while relying on `multi`
   being preserved AFTER that call completes — `pasteClipboard()` is the one place `multi` is
   deliberately populated immediately before a `select(pasted[...])` call with a NON-null argument
   (see its own comment, "`multi` populated BEFORE select()"), and the new check in `select()` only
   fires when `el` is falsy, so that path is untouched.

### Not verified this session either

Same constraint as caveat 2 above, worse this time because I actively tried and confirmed it again:
`node --check editor.js` was refused ("this command requires approval") via both the Bash and
PowerShell tools, so the syntax/brace-balance claims above are hand-verification only — I re-read
`select()`, `restore()`'s Pass 2 opening, and `deleteSelected()` back from disk after every edit and
counted braces by eye. No browser exercised undo-across-a-multi-selection, load-a-file-with-a-stale-
multi-selection, or delete-a-shift-clicked-selected-element to confirm the fix actually behaves as
described; only the three functions' text was inspected.
