/* interactions.js — drag / resize / free-drag on pointer capture.
 *
 * THIS IS THE SANCTIONED FALLBACK, not a vendored interact.js. Plan Sec 5.1 offers exactly two
 * options -- "interact.js (~10 KB) ... or ~150 lines of pointerdown/pointermove/pointerup with
 * pointer capture" -- and this is the second. The reason is recorded in phase1b_change_detail.md;
 * the short version is that a CDN is not reachable at runtime on this network, an npm build step is
 * out of scope, and vendoring a minified blob we cannot fetch is not an option.
 *
 * IT IS DELIBERATELY interact.js-SHAPED. Call sites use `Interactions.draggable(sel, {listeners})`
 * and `.resizable(...)`, and the move event carries `dx`/`dy` and `deltaRect` with interact.js's
 * meanings and interact.js's units. Dropping the real library in later is therefore a rewrite of
 * this one file and nothing else.
 *
 * WHAT IT DOES NOT DO, ON PURPOSE:
 *
 *   - It never hands the caller a MEASURED rectangle. interact.js exposes one on its move event --
 *     a device-pixel box taken straight from the DOM -- and consuming it silently reintroduces
 *     every bug the Prime Directive exists to delete: it breaks the moment zoom != 1. Not offering
 *     it at all is strictly better than offering it and asking people not to touch it. This file
 *     measures nothing; it only ever DIFFERENCES two pointer positions.
 *   - It has no `snap` and no `restrict` modifiers. interact.js's operate in page/device pixels, so
 *     at zoom = 0.5 a 4-unit grid quietly becomes a 2-unit grid and a reserved-region restriction
 *     lands in the wrong place. ALL snapping and ALL constraint enforcement happen in model space,
 *     in editor.js, after the / zoom conversion.
 *
 * Units: dx, dy and every deltaRect field are DEVICE PIXELS -- exactly as interact.js reports them.
 * The caller divides by `zoom`. That division is the caller's job and it is grep-enforced (Gate 1).
 */

(function (global) {
  'use strict';

  // data-h -> which edges of the box this handle moves. Mirrors interact.js's `edges` option.
  var EDGES = {
    nw: { left: true, top: true },
    n: { top: true },
    ne: { right: true, top: true },
    e: { right: true },
    se: { right: true, bottom: true },
    s: { bottom: true },
    sw: { left: true, bottom: true },
    w: { left: true },
  };

  /* The one primitive. Everything below is a thin wrapper on it.
   *
   * Pointer capture is what makes this robust: once the pointer is captured, the moves keep
   * arriving at the captured node even when the cursor outruns the element, leaves the stage, or
   * crosses an iframe. That is the entire reason the plan names pointer capture specifically
   * rather than "mousemove on document".
   */
  function pointerDrag(node, opts) {
    node.addEventListener('pointerdown', function (ev) {
      if (ev.button !== 0) return; // primary button only
      if (opts.filter && !opts.filter(ev)) return;

      ev.preventDefault();
      ev.stopPropagation();

      var last = { x: ev.clientX, y: ev.clientY };
      var ctx = { target: node, pointer: ev, dx: 0, dy: 0 };

      // Capture on the node that received the event, so a re-render of a SIBLING (the <svg>, which
      // editor.js does replace every frame) cannot pull the captured node out from under us.
      node.setPointerCapture(ev.pointerId);

      if (opts.start) opts.start(ctx);

      function onMove(mv) {
        if (mv.pointerId !== ev.pointerId) return;
        ctx.pointer = mv;
        ctx.dx = mv.clientX - last.x; // device px. The caller divides by zoom.
        ctx.dy = mv.clientY - last.y;
        last.x = mv.clientX;
        last.y = mv.clientY;
        if (opts.move) opts.move(ctx);
      }

      function onUp(up) {
        if (up.pointerId !== ev.pointerId) return;
        node.removeEventListener('pointermove', onMove);
        node.removeEventListener('pointerup', onUp);
        node.removeEventListener('pointercancel', onUp);
        if (node.hasPointerCapture(up.pointerId)) node.releasePointerCapture(up.pointerId);
        ctx.pointer = up;
        if (opts.end) opts.end(ctx);
      }

      node.addEventListener('pointermove', onMove);
      node.addEventListener('pointerup', onUp);
      node.addEventListener('pointercancel', onUp);
    });
  }

  var Interactions = {
    pointerDrag: pointerDrag,

    /* Drag the whole element. `ignoreFrom` is a selector: a pointerdown starting inside it is not a
     * drag (the text box, so a click lands the caret; the handles, so they resize instead).
     * `enabled` is handed the triggering pointerdown event (Phase 6: editor.js reads
     * ev.shiftKey off it to let a Shift+Click toggle multi-selection instead of starting a
     * drag) -- existing callers that declared `enabled: function () {...}` and ignore the
     * argument are unaffected. */
    draggable: function (el, opts) {
      pointerDrag(el, {
        filter: function (ev) {
          if (opts.ignoreFrom && ev.target.closest(opts.ignoreFrom)) return false;
          return !opts.enabled || opts.enabled(ev);
        },
        start: opts.start,
        move: opts.move,
        end: opts.end,
      });
    },

    /* Resize from a handle. The move event carries `deltaRect`, in device px, with interact.js's
     * exact semantics: how the box's left/top/width/height changed THIS FRAME. */
    resizable: function (handle, edgeKey, opts) {
      var edges = EDGES[edgeKey] || {};
      pointerDrag(handle, {
        start: opts.start,
        move: function (ctx) {
          ctx.edges = edges;
          ctx.deltaRect = {
            left: edges.left ? ctx.dx : 0,
            top: edges.top ? ctx.dy : 0,
            width: (edges.right ? ctx.dx : 0) - (edges.left ? ctx.dx : 0),
            height: (edges.bottom ? ctx.dy : 0) - (edges.top ? ctx.dy : 0),
          };
          opts.move(ctx);
        },
        end: opts.end,
      });
    },
  };

  global.Interactions = Interactions;
})(window);
