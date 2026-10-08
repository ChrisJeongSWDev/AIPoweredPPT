---
target_repo: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT
claude_model: sonnet
write_scope: src/aippt/canvas/static/editor.js
change_detail_path: tasks/AI_Powered_PPT/phase5_change_detail.md
---
# Phase 5: PowerPoint-like Editor UX

## CRITICAL INSTRUCTION FOR WORKER
You are running within a dispatcher environment. The dispatcher has created an isolated workspace at `.editwork`. 
You MUST apply your edits to `.editwork/src/aippt/canvas/static/editor.js`.
DO NOT edit `src/aippt/canvas/static/editor.js` directly in the real repo. If you do, the dispatcher will see an empty diff and fail.
Only edit `.editwork/src/aippt/canvas/static/editor.js`.

## Task
Enhance the editor UX to support "click-to-drop" and "auto-focus" for textboxes. Apply the following exact changes:

### Change A — new constants (after `var ZOOM_MAX = 200;`)
```js
  var ZOOM_MIN = 25;
  var ZOOM_MAX = 200;

  // PowerPoint's "click to drop". A creation gesture whose drag is shorter than this on BOTH
  // axes is treated as a click, not a draw-out: the tool drops a default-sized element at the
  // click instead of a sliver the user cannot see. DROP_SIZES is the default footprint per tool;
  // the connector is a fixed diagonal (see the end() handler), so it is not listed here.
  var DROP_THRESHOLD = 5; // model units, on either axis
  var DROP_SIZES = {
    rect: { w: 100, h: 100 },
    ellipse: { w: 100, h: 100 },
    triangle: { w: 100, h: 100 },
    textbox: { w: 200, h: 50 },
  };
```

### Change B — collapse the `dblclick` handler
Replace the current `el.addEventListener('dblclick', ...)` with:
```js
    el.addEventListener('dblclick', function (ev) {
      if (tool !== 'select' || el.dataset.type === 'connector') return;
      ev.preventDefault();
      startEditing(el);
    });
```

### Change C — define `startEditing()` immediately before `function stopEditing() {`
Insert:
```js
  /* Put an element into text-editing mode -- the shared body of the dblclick handler and the
   * auto-focus a freshly created textbox gets (requirement 2). THE ATTRIBUTE, not merely the
   * class: `.el.editing .txt { pointer-events: auto }` decides whether a POINTER can reach the
   * text; contenteditable decides whether the element is editable at all. Only the second one is
   * what editingText() -- and the keyboard, and a screen reader -- actually consults. */
  function startEditing(el) {
    if (el.dataset.type === 'connector') return; // a connector carries no text
    select(el);
    var body = el.querySelector('.txt .body');
    if (!body) return;
    body.setAttribute('contenteditable', 'true');
    el.classList.add('editing');
    beginTx(); // the whole editing session is one step; stopEditing() closes it
    body.focus();
  }

  function stopEditing() {
```

### Change D — gate drag-creation behind the threshold (in the stage `move:` handler)
Replace:
```js
    move: function (ctx) {
      var p = toModel(ctx.pointer);
      var o = ctx.origin;
      var cand;

      if (tool === 'connector') {
```
With:
```js
    move: function (ctx) {
      var p = toModel(ctx.pointer);
      var o = ctx.origin;
      var cand;

      // PowerPoint's click-to-drop: nothing is drawn until the drag clears DROP_THRESHOLD on some
      // axis. A click, or a wobble under the threshold, leaves ctx.made null and is handled as a
      // drop in end(). Once an element exists, every later frame keeps sizing it.
      if (!ctx.made && Math.abs(p.x - o.x) < DROP_THRESHOLD && Math.abs(p.y - o.y) < DROP_THRESHOLD) {
        return;
      }

      if (tool === 'connector') {
```

### Change E — click-to-drop + textbox auto-focus in the stage `end:` handler
Replace:
```js
    end: function (ctx) {
      if (!ctx.made) {
        setStatus('Nothing drawn — drag out a shape rather than clicking.');
        return;
      }
      setTool('select');
      syncProps();
      setStatus('Created ' + ctx.made.dataset.id + '.');
    },
```
With:
```js
    end: function (ctx) {
      // A real draw-out already built and sized its element. Finish it: back to select, and --
      // like PowerPoint -- a fresh textbox opens straight into editing (see finishCreate()).
      if (ctx.made) {
        finishCreate(ctx.made);
        return;
      }

      // CLICK-TO-DROP: the pointer never cleared DROP_THRESHOLD, so treat it as a click and drop a
      // default-sized element at the click. It goes through applyConstraints() just like a
      // draw-out -- alt: true so a deliberate placement is not re-snapped, but it is still CLAMPED
      // into the slide, the clamp that keeps a 100x100 drop near an edge on-stage.
      var o = ctx.origin;
      var cand;
      if (tool === 'connector') {
        var cd = DEFAULTS.connector;
        cand = {
          id: nextId(), type: 'connector',
          x1: o.x, y1: o.y, x2: o.x + 100, y2: o.y + 100, // a fixed diagonal, like a click in PPT
          kind: cd.kind, arrow: cd.arrow, color: cd.color, width: cd.width,
        };
      } else {
        var def = tool === 'textbox' ? DEFAULTS.textbox : DEFAULTS.shape;
        var sz = DROP_SIZES[tool] || DROP_SIZES.rect;
        cand = {
          id: nextId(), type: tool,
          x: o.x, y: o.y, w: sz.w, h: sz.h, rot: 0,
          fill: def.fill, strokeColor: def.strokeColor, strokeWidth: def.strokeWidth,
          size: def.size, color: def.color, align: def.align, valign: def.valign,
          bold: def.bold, italic: def.italic,
        };
      }

      var legal = applyConstraints(cand, { alt: true });
      if (!legal) {
        setStatus('That would not fit legally here — nothing was dropped.');
        return;
      }
      var made = addEl(makeEl(legal));
      select(made);
      pushUndo(ctx.before); // the drop is ONE step; ctx.before was taken at gesture start
      finishCreate(made);
    },
```

### Change F — `finishCreate()` helper right after the stage `pointerDrag` block
Replace:
```js
  });

  stage.addEventListener('pointerdown', function (ev) {
```
With:
```js
  });

  /* The common tail of both creation paths (draw-out and click-to-drop): return to the select
   * tool, refresh the panel, and -- for a textbox -- open it for typing immediately, the way
   * PowerPoint does (requirement 2: a new textbox is editable without a double-click). */
  function finishCreate(el) {
    setTool('select');
    syncProps();
    setStatus('Created ' + el.dataset.id + '.');
    if (el.dataset.type === 'textbox') startEditing(el);
  }

  stage.addEventListener('pointerdown', function (ev) {
```

Make sure the edits are exact and do not break any existing code.
