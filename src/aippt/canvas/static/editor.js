/* editor.js — the DOM -> canvas-ir/1 visual editor. Plan Sec 5, tasks 2.1 - 2.8.
 *
 * ============================================================================================
 * THE PRIME DIRECTIVE
 *
 *   The stage's device rect is read EXACTLY ONCE, in toModel(), and only ever to invert a
 *   pointer position. Nothing else in this file measures the DOM. Ever.
 *
 * Geometry lives in JS state (el.dataset) and flows ONE WAY:
 *
 *     state (dataset x/y/w/h/rot)  ──render──>  CSS + SVG attributes
 *                                  ✗ never read back ✗
 *
 * Every measured-geometry API in the browser is BANNED here, as is any percentage width in the IR
 * path and any value read back out of CSS. The enforced list lives in
 * tests/canvas/test_editor_source.py (Gate 1) -- deliberately, so that the test is the spec and
 * this comment cannot drift away from it. Gate 1 is a plain substring grep over this file, which
 * is why the banned names are not spelled out here: naming them would trip the very test that
 * enforces them. That test is the only thing standing between "we agreed on the rule" and "the
 * rule held".
 *
 * The EMU-per-unit constant does not appear here either. The browser never converts to EMU; Python
 * does, once, at the end. We carry floats and round only to kill float noise (round6).
 * ============================================================================================
 */

(function () {
  'use strict';

  /* ------------------------------------------------------------------ authoritative constants */

  // Echoed into every payload so the backend can reject a STALE deck instead of silently rescaling
  // it. There is exactly one model space and the renderer NEVER rescales.
  var CANVAS = Object.freeze({ w: 960, h: 540, unit: 'pt' });
  var SCHEMA = 'canvas-ir/1';

  // Ported VERBATIM from canvas/geometry.py. Same numbers, same half-open rule, same rotated AABB.
  // If these two ever disagree, the user is looking at a legal-looking stage and a 422 they cannot
  // explain.
  var HEADER_RESERVED = [0, 0, 960, 92];
  var FOOTER_RESERVED = [733.6, 500, 960, 540];
  var BODY_SAFE = [45.6, 92, 914.4, 500]; // SNAP TARGET ONLY -- never a constraint
  var REJECT_REGIONS = [
    { name: 'HEADER_RESERVED', box: HEADER_RESERVED },
    { name: 'FOOTER_RESERVED', box: FOOTER_RESERVED },
  ];
  var EPS = 1e-9; // == geometry.EPS: a rotated corner can land on 960.0000000000001

  var BRAND_RED = '#FF0032';
  // Theme accent1. validate.py REJECTS it, so the colour picker rejects it too -- the user finds
  // out here, in the editor, and not in a 422 they cannot explain. It is referenced ONLY by the
  // colour guard (guardColor, below): never as a default, a palette entry or a fallback.
  var FORBIDDEN_COLOR = '#4472C4';

  var MIN_EXTENT = 4; // schema requires > 0; the editor requires >= 4
  var GRID = 4;
  var SNAP_TOL = 3; // model units
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

  // Snap guides, in MODEL space: the grid, the BODY_SAFE edges, the stage edges, the centre lines.
  var GUIDES_X = [0, BODY_SAFE[0], CANVAS.w / 2, BODY_SAFE[2], CANVAS.w];
  var GUIDES_Y = [0, BODY_SAFE[1], CANVAS.h / 2, BODY_SAFE[3], CANVAS.h];

  // bold/italic are ELEMENT-level defaults for the runs inside, exactly as size and color already
  // are. The IR has no element-level bold -- it has run.bold -- so these are folded into every run
  // by normalizeText() on the way out and summarised back off the runs by stateFromIR() on the way
  // in. See setTextFlag() for why "off" also has to strip <b>/<i> out of the body.
  var DEFAULTS = {
    // fillAlpha is a PERCENT (0-100), never serialized on its own -- toIR() folds it into the
    // trailing hex byte of the fill colour string (Phase 6; schema.json's `color` def already
    // accepts #RRGGBB + an optional AA byte). 100 == opaque == no byte emitted at all.
    shape: { fill: BRAND_RED, fillAlpha: 100, strokeColor: '', strokeWidth: 1, size: 14, color: '#FFFFFF', align: 'CENTER', valign: 'MIDDLE', bold: false, italic: false },
    // A textbox is geometrically a rect; the split is authorial intent. No fill, black ink.
    textbox: { fill: '', fillAlpha: 100, strokeColor: '', strokeWidth: 1, size: 14, color: '#000000', align: 'CENTER', valign: 'MIDDLE', bold: false, italic: false },
    connector: { color: BRAND_RED, width: 1.5, arrow: 'end', kind: 'straight' },
    // Media (Phase 6) is not a drawing TOOL -- it is inserted from a file picker, never dragged out
    // -- so it carries no drag-out default box the way SHAPE_TYPES do; MEDIA_DEFAULT_SIZE (below)
    // is the size a freshly inserted image/video starts at.
  };

  var SHAPE_TYPES = ['rect', 'ellipse', 'triangle', 'textbox'];
  // image/video (Phase 6): geometrically a rect (x/y/w/h), addressed by `src` instead of fill/text.
  // Kept OUT of SHAPE_TYPES -- that list means "drawable with a stage drag-out tool" (DROP_SIZES is
  // keyed by it), and media is inserted from a file picker instead -- but they ARE in ELEMENT_TYPES
  // (below), which is "a type the judge (illegalReason) accepts on the stage at all". Checked by
  // literal string (isMediaType()) everywhere rather than via a shared array, because ELEMENT_TYPES
  // and stateFromIR() are lifted VERBATIM out of this file by name and run in Node
  // (tests/canvas/test_app.py) -- a reference to a var outside that lift is a ReferenceError there.
  var MEDIA_DEFAULT_SIZE = { w: 320, h: 240 };
  function isMediaType(t) { return t === 'image' || t === 'video'; }
  var HANDLES = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];

  /* ---------------------------------------------------------------------------------- the DOM */

  var stage = document.getElementById('stage');
  var stageWrap = document.getElementById('stage-wrap');
  var titleField = document.getElementById('title-field');
  var warnings = document.getElementById('warnings');
  var statusMsg = document.getElementById('status-msg');
  var props = document.getElementById('props'); // the right-hand panel; hidden with nothing selected

  var zoom = 1; // THE single source of truth for scale. --zoom is written FROM it, never read.
  var tool = 'select';
  var selected = null;
  // Phase 6: the ADDITIONAL elements Shift+Click has gathered for alignment, alongside `selected`.
  // Deliberately NOT a rewrite of `selected` into an N-element model: every other piece of this
  // editor (drag, resize, rotate, the property panel, delete, duplicate, undo-per-gesture) is built
  // for exactly one active element, and multi-selection exists here for one purpose -- alignment --
  // so it stays a second, purely additive list rather than a page-one rearchitecture. See
  // selectionSet(), toggleMulti(), clearMulti(), alignSelection().
  var multi = [];
  var CONTEXT = null; // from /api/context. Never a hard-coded SHA.
  var idSeq = 0;

  /* =========================================================================================
   * THE ONLY PLACE A DEVICE COORDINATE BECOMES A MODEL COORDINATE.
   * ========================================================================================= */
  function toModel(ev) {
    var r = stage.getBoundingClientRect(); // used ONLY for pointer inversion
    return { x: (ev.clientX - r.left) / zoom, y: (ev.clientY - r.top) / zoom };
  }

  /* ------------------------------------------------------- geometry: a port of geometry.py */

  // Strict overlap. HALF-OPEN: edge contact is NOT intersection. An element whose top edge is
  // exactly y == 92 is LEGAL -- BODY_SAFE starts at exactly 92. Get this wrong and every
  // top-aligned element the user draws is spuriously blocked. Same at y == 500.
  function intersects(a, b) {
    return a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
  }

  // The ROTATED axis-aligned bounding box -- NOT the path box. A 45-degree box whose unrotated
  // footprint clears the header but whose rotated corners do not is rejected by the backend, so it
  // is rejected here too. y grows DOWNWARD, so this matrix turns CLOCKWISE on screen, which is what
  // DrawingML's a:xfrm/@rot means.
  function elementBBox(s) {
    if (s.type === 'connector') {
      return [
        Math.min(s.x1, s.x2), Math.min(s.y1, s.y2),
        Math.max(s.x1, s.x2), Math.max(s.y1, s.y2),
      ];
    }
    var x = s.x, y = s.y, w = s.w, h = s.h;
    var rot = s.rot || 0;
    if (rot % 360 === 0) return [x, y, x + w, y + h];

    var cx = x + w / 2, cy = y + h / 2;
    var t = (rot * Math.PI) / 180;
    var cos = Math.cos(t), sin = Math.sin(t);
    var corners = [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
    var xs = [], ys = [];
    for (var i = 0; i < corners.length; i++) {
      var dx = corners[i][0] - cx, dy = corners[i][1] - cy;
      xs.push(cx + dx * cos - dy * sin);
      ys.push(cy + dx * sin + dy * cos);
    }
    return [Math.min.apply(null, xs), Math.min.apply(null, ys),
            Math.max.apply(null, xs), Math.max.apply(null, ys)];
  }

  function outOfBounds(s) {
    var b = elementBBox(s);
    return b[0] < -EPS || b[1] < -EPS || b[2] > CANVAS.w + EPS || b[3] > CANVAS.h + EPS;
  }

  function clamp(v, lo, hi) { return Math.min(hi, Math.max(lo, v)); }
  function round6(v) { return Math.round(v * 1e6) / 1e6; }

  /* ------------------------------------------------------------------- snapping (MODEL space) */

  // interact.js's snap/restrict modifiers are NOT used: they operate in device pixels, so at
  // zoom = 0.5 a 4-unit grid quietly becomes a 2-unit grid and a restriction lands in the wrong
  // place. Everything here runs AFTER the / zoom conversion, on model numbers.

  function snapVal(v, guides) {
    for (var i = 0; i < guides.length; i++) {
      if (Math.abs(v - guides[i]) <= SNAP_TOL) return guides[i];
    }
    return Math.round(v / GRID) * GRID;
  }

  // Snap a MOVE: the size is fixed, so the leading, centre and trailing edges are all candidates
  // and the closest wins.
  function snapAxis(v, size, guides) {
    var best = null, bestD = SNAP_TOL;
    var anchors = [[v, 0], [v + size / 2, size / 2], [v + size, size]];
    for (var g = 0; g < guides.length; g++) {
      for (var a = 0; a < anchors.length; a++) {
        var d = Math.abs(anchors[a][0] - guides[g]);
        if (d < bestD) { bestD = d; best = guides[g] - anchors[a][1]; }
      }
    }
    return best !== null ? best : Math.round(v / GRID) * GRID;
  }

  /* ------------------------------------------------------------------ the constraint pipeline */

  /* Every committed frame, in this order:
   *   1. candidate state from the delta (the caller did that)
   *   2. w, h >= 4
   *   3. snap (unless Alt)
   *   4. clamp to the slide
   *   5. rotated AABB vs HEADER_RESERVED / FOOTER_RESERVED
   *   6. legal -> return it. Illegal -> return null, and the caller HOLDS ITS LAST LEGAL STATE.
   *
   * REJECT-AND-HOLD, not push-out. A "clever" push-out under rotation is non-deterministic and it
   * will disagree with geometry.py -- at which point the user is looking at a legal-looking stage
   * and a 422.
   *
   * STEPS 2-4 TRANSFORM A CANDIDATE. STEPS 5-6 JUDGE IT. They are two different jobs, so they are
   * two different functions -- because the JSON import path must reuse the JUDGE and must never
   * reuse the TRANSFORM. Snapping, growing and clamping a file the user hand-authored would
   * silently rewrite their deck on load, which is the same push-out we refused to do for the mouse.
   * illegalReason() below is the judge, and it is the ONLY door into the stage: the mouse goes
   * through it via applyConstraints(), a file goes through it via loadIR(), and the undo stack goes
   * through it via unrestorableReason(). Three writers, one judge. A fourth writer that skips it
   * would not be a new feature with a bug in it -- it would be a hole in requirement 4, and the
   * reserved-region guarantee (the thing the backend returns 422 on) would die inside it, quietly.
   */

  // The geometry a type carries, and the ONLY fields the judge reads.
  var GEOM_FIELDS = {
    connector: ['x1', 'y1', 'x2', 'y2'],
    shape: ['x', 'y', 'w', 'h', 'rot'],
  };

  var ELEMENT_TYPES = SHAPE_TYPES.concat(['connector', 'image', 'video']);

  /* THE NUMERIC GUARD. This is not paranoia -- it is the hole that every geometry check has.
   *
   * EVERY comparison against NaN is false. So if x is NaN then outOfBounds() returns FALSE and
   * intersects() returns FALSE, and a garbage element sails straight through a rule that is
   * otherwise perfectly correct. A missing coordinate becomes +undefined === NaN the moment read()
   * touches it, and a file is allowed to be missing a coordinate. The judge therefore proves the
   * numbers are numbers BEFORE it compares them.
   *
   * typeof also disposes of true and of "100": the payload schema says `number`, so a boolean or a
   * string coordinate is a 422 in waiting, not a coordinate. validate.py::_num draws this exact
   * line on the other side, and for this exact reason.
   */
  function geometryIsReadable(s) {
    var fields = s.type === 'connector' ? GEOM_FIELDS.connector : GEOM_FIELDS.shape;
    for (var i = 0; i < fields.length; i++) {
      var v = s[fields[i]];
      if (typeof v !== 'number' || !isFinite(v)) return false;
    }
    return true;
  }

  /* THE LEGALITY RULE -- the one judge, and the whole of requirement 4.
   *
   * Returns a human reason this state may not exist on the stage, or null when it may. It reads
   * state and it TRANSFORMS NOTHING: a judge that quietly repairs its defendant is not a judge, and
   * the import path can only borrow this half precisely because it is inert.
   *
   * MIN_EXTENT is deliberately NOT enforced here. w >= 4 is drawing ergonomics -- you cannot mouse
   * out a 2-unit box -- whereas the schema's rule, and therefore the legality rule, is w > 0. If
   * this function enforced 4 then loading a legal 2-unit element would have to either reject a deck
   * the backend accepts or resize the user's file. It enforces > 0, which is the rule that is
   * actually true on both sides.
   */
  function illegalReason(s) {
    if (ELEMENT_TYPES.indexOf(s.type) < 0) {
      return 'has an unknown type -- expected one of ' + ELEMENT_TYPES.join(', ');
    }
    if (!geometryIsReadable(s)) {
      return 'has a missing or non-numeric coordinate, so its box cannot be computed at all';
    }
    if (s.type !== 'connector' && (s.w <= 0 || s.h <= 0)) {
      // An inverted box is not a small box. elementBBox() would hand back x2 < x1, and every
      // predicate downstream would then be comparing an interval that runs backwards -- which is a
      // second way to be waved through a correct check. Refuse it before it can lie.
      return 'has a non-positive width or height';
    }
    if (outOfBounds(s)) {
      return 'falls outside the ' + CANVAS.w + 'x' + CANVAS.h + ' slide';
    }
    var box = elementBBox(s);
    for (var i = 0; i < REJECT_REGIONS.length; i++) {
      if (intersects(box, REJECT_REGIONS[i].box)) {
        return 'intersects ' + REJECT_REGIONS[i].name + ' -- that region carries inherited layout ' +
               'chrome (the logo, the divider, the page number) which always renders BEHIND slide ' +
               'content and cannot be raised above it. Move it into the body, y 92 -> 500.';
      }
    }
    return null;
  }

  /* THE THIRD CALLER OF THE JUDGE -- restore(), i.e. the undo stack.
   *
   * A restore must not be TRANSFORMED: not snapped, not clamped, not re-pushed onto the stack it
   * came from. That is true, and it is why restore() calls makeEl() and not commit(). It does not
   * follow that a restore must not be JUDGED. illegalReason() transforms nothing -- that inertness
   * is the entire reason it exists as its own function, apart from applyConstraints() -- so judging
   * a snapshot costs it nothing and takes nothing away from it. Judging is free.
   *
   * ALL OR NOTHING, and in this order: judge every record FIRST, touch the stage SECOND. The same
   * order, for the same reason, as loadIR(). restore() clears the stage before it has looked at a
   * single element, so a per-element check bolted into its loop -- however correct that check was --
   * could only ever leave a half-restored stage behind and the user's own deck already gone.
   * "Refuse the entire restore" is not reachable from inside that loop. It is reachable from here.
   *
   * WHY THIS RUNS AT ALL, given that every element in the DOM was judged on the way in: because that
   * is an INDUCTIVE argument, and it is only as strong as its weakest step. It holds today because
   * commit(), loadIR() and duplicateSelected() are the only three writers of dataset geometry and
   * all three call the judge. The next writer -- a paste handler, an alignment tool, an arrow-key
   * nudge -- inherits an undo stack that will happily reintroduce whatever it wrote, in a function
   * nobody suspects. The claim on line 193 is unconditional. This is what makes it true.
   *
   * It READS AND RETURNS: it mutates nothing and it touches no DOM. (The Gate 4b harness runs it
   * with no `stage` and no `titleField` defined at all, so any DOM access here is a ReferenceError
   * under 'use strict' -- which is how "it touches no DOM" is an assertion and not a hope.)
   *
   * Returns a human reason this snapshot may not be put on the stage, or null when it may.
   */
  function unrestorableReason(snap) {
    if (!snap || typeof snap !== 'object' || !Array.isArray(snap.els) || typeof snap.title !== 'string') {
      return 'that history entry is not a snapshot of a stage';
    }

    var problems = [];
    for (var i = 0; i < snap.els.length; i++) {
      var rec = snap.els[i];
      if (!rec || typeof rec !== 'object' || !rec.state || typeof rec.state !== 'object') {
        problems.push('els[' + i + ']: is not an element record');
        continue;
      }
      var why = illegalReason(rec.state);
      if (why) {
        var id = typeof rec.state.id === 'string' ? rec.state.id : '?';
        problems.push('els[' + i + '] (id "' + id + '"): ' + why);
      }
    }
    if (!problems.length) return null;

    return problems.length + ' element(s) in that history step may not be placed on this stage:\n' +
           problems.map(function (p, n) { return '  ' + (n + 1) + '. ' + p; }).join('\n');
  }

  function applyConstraints(s, opt) {
    opt = opt || {};
    var c = {};
    for (var k in s) c[k] = s[k];

    if (c.type === 'connector') {
      if (!opt.alt) {
        c.x1 = snapVal(c.x1, GUIDES_X); c.y1 = snapVal(c.y1, GUIDES_Y);
        c.x2 = snapVal(c.x2, GUIDES_X); c.y2 = snapVal(c.y2, GUIDES_Y);
      }
      c.x1 = clamp(c.x1, 0, CANVAS.w); c.x2 = clamp(c.x2, 0, CANVAS.w);
      c.y1 = clamp(c.y1, 0, CANVAS.h); c.y2 = clamp(c.y2, 0, CANVAS.h);
    } else {
      // 2. minimum extent
      c.w = Math.max(MIN_EXTENT, c.w);
      c.h = Math.max(MIN_EXTENT, c.h);

      // 3. snap, in model space
      if (!opt.alt) {
        var px = c.x, pw = c.w, py = c.y, ph = c.h;
        if (opt.edges) {
          // A resize or a drag-out: snap only the edges that actually moved. Snapping x during an
          // SE-handle resize would slide the element instead of resizing it.
          var x1 = c.x, x2 = c.x + c.w, y1 = c.y, y2 = c.y + c.h;
          if (opt.edges.left) x1 = snapVal(x1, GUIDES_X);
          if (opt.edges.right) x2 = snapVal(x2, GUIDES_X);
          if (opt.edges.top) y1 = snapVal(y1, GUIDES_Y);
          if (opt.edges.bottom) y2 = snapVal(y2, GUIDES_Y);
          c.x = x1; c.w = x2 - x1; c.y = y1; c.h = y2 - y1;
        } else {
          c.x = snapAxis(c.x, c.w, GUIDES_X);
          c.y = snapAxis(c.y, c.h, GUIDES_Y);
        }
        // Snapping must never talk the box below the minimum. If it did, undo it on that axis --
        // the invariant outranks the convenience.
        if (c.w < MIN_EXTENT) { c.x = px; c.w = pw; }
        if (c.h < MIN_EXTENT) { c.y = py; c.h = ph; }
      }

      // 4. clamp the ROTATED footprint into the slide, by translating.
      var b = elementBBox(c);
      if (b[2] - b[0] > CANVAS.w + EPS || b[3] - b[1] > CANVAS.h + EPS) return null;
      var sx = 0, sy = 0;
      if (b[0] < 0) sx = -b[0]; else if (b[2] > CANVAS.w) sx = CANVAS.w - b[2];
      if (b[1] < 0) sy = -b[1]; else if (b[3] > CANVAS.h) sy = CANVAS.h - b[3];
      c.x += sx; c.y += sy;
    }

    // 5 + 6. THE JUDGE -- slide bounds and the reserved regions, on the rotated AABB. The rule is
    // not written out here: it is illegalReason(), the same function, the same numbers and the same
    // half-open comparisons that a file has to answer to. A second copy of it here is exactly how
    // the mouse and the importer would drift apart.
    return illegalReason(c) ? null : c;
  }

  /* ------------------------------------------------------------------------- state <-> dataset */

  function read(el) {
    var d = el.dataset;
    var s = { id: d.id, type: d.type };
    if (d.type === 'connector') {
      s.x1 = +d.x1; s.y1 = +d.y1; s.x2 = +d.x2; s.y2 = +d.y2;
      s.kind = d.kind; s.arrow = d.arrow; s.color = d.color; s.width = +d.width;
    } else if (isMediaType(d.type)) {
      // image/video: geometry only, plus `src` -- no fill/stroke/text/rotation. The renderer
      // (render_canvas.draw_image/draw_video) never draws those for a picture or a video, so the
      // property panel never offers them (syncProps()'s "media" category) and this editor state
      // never carries them either -- there is nothing here that could silently fail to round-trip.
      s.x = +d.x; s.y = +d.y; s.w = +d.w; s.h = +d.h; s.rot = +d.rot || 0;
      s.src = d.src || '';
    } else {
      s.x = +d.x; s.y = +d.y; s.w = +d.w; s.h = +d.h; s.rot = +d.rot || 0;
      s.fill = d.fill || '';
      // Percent, 100 == opaque. See DEFAULTS's comment: folded into the fill's hex string only at
      // serialization (toIR), never carried as its own IR field.
      s.fillAlpha = d.fillAlpha === undefined || d.fillAlpha === '' ? 100 : +d.fillAlpha;
      s.strokeColor = d.strokeColor || '';
      s.strokeWidth = d.strokeWidth === undefined || d.strokeWidth === '' ? 1 : +d.strokeWidth;
      s.size = +d.size; s.color = d.color; s.align = d.align; s.valign = d.valign;
      // A dataset value is a STRING, so '' and '0' and 'false' are all truthy traps. Compare.
      s.bold = d.bold === '1'; s.italic = d.italic === '1';
    }
    return s;
  }

  function write(el, s) {
    var d = el.dataset;
    d.id = s.id; d.type = s.type;
    if (s.type === 'connector') {
      d.x1 = s.x1; d.y1 = s.y1; d.x2 = s.x2; d.y2 = s.y2;
      d.kind = s.kind; d.arrow = s.arrow; d.color = s.color; d.width = s.width;
    } else if (isMediaType(s.type)) {
      d.x = s.x; d.y = s.y; d.w = s.w; d.h = s.h; d.rot = s.rot || 0;
      d.src = s.src || '';
    } else {
      d.x = s.x; d.y = s.y; d.w = s.w; d.h = s.h; d.rot = s.rot || 0;
      d.fill = s.fill; d.strokeColor = s.strokeColor; d.strokeWidth = s.strokeWidth;
      d.fillAlpha = s.fillAlpha === undefined ? 100 : s.fillAlpha;
      d.size = s.size; d.color = s.color; d.align = s.align; d.valign = s.valign;
      // '1' or '' -- style.css keys off [data-bold='1'], so "off" must not be the string 'false'.
      d.bold = s.bold ? '1' : ''; d.italic = s.italic ? '1' : '';
    }
  }

  /* commit -- the ONE way state changes. Nothing writes dataset geometry except through here.
   *
   * Which is exactly why undo hangs off it: "every mutation is undoable" is only a checkable
   * sentence because there is one door to hang the check on.
   */
  function commit(el, patch, opt) {
    var cur = read(el);
    for (var k in patch) cur[k] = patch[k];
    var legal = applyConstraints(cur, opt);
    if (!legal) { flashBlocked(el); return false; }
    // BEFORE the write, and only when we already know the write will happen: a REFUSED frame must
    // not cost an undo step, or dragging a box into the header would fill the stack with states the
    // user cannot see the difference between. Inside a gesture the snapshot was taken once already,
    // at beginTx() -- taking another one every pointermove frame is the one place this could get
    // expensive.
    var before = txOpen ? null : snapshot();
    write(el, legal);
    renderEl(el);
    noteChange(before);
    return true;
  }

  function flashBlocked(el) {
    // Restart the animation across a frame boundary rather than by poking a layout property --
    // reading one back would measure the DOM, which is the whole thing we do not do.
    el.classList.remove('blocked');
    requestAnimationFrame(function () { el.classList.add('blocked'); });
    setTimeout(function () { el.classList.remove('blocked'); }, 400);
  }

  /* ================================================================================ undo / redo
   *
   * SNAPSHOT-BASED, and that is a decision, not a shortcut.
   *
   * The obvious alternative -- a stack of commands, each with an inverse -- needs an inverse for
   * every mutation the editor has. Move and resize invert easily. Raise/lower reorder the DOM.
   * Delete has to remember where in the z-order the element WAS. Load replaces the entire stage.
   * Duplicate mints an id. Each of those is a separate inverse, and each inverse that is subtly
   * wrong is a silent corruption that surfaces three undos later, somewhere else. A snapshot has
   * exactly ONE inverse and every mutation shares it.
   *
   * A snapshot is JS STATE ONLY -- dataset (via read()), the contenteditable's innerHTML, and DOM
   * ORDER, which IS the z-order. It measures nothing, and restoring one rebuilds the elements
   * through makeEl(), i.e. back down the same one-way state -> CSS path every other write takes.
   * Undo therefore cannot reintroduce a device pixel, which is the one way an undo stack could
   * plausibly have broken the Prime Directive.
   *
   * WHAT IS NOT IN A SNAPSHOT: zoom and the current tool. They are VIEW, not document. Undoing a
   * move and having the zoom jump under you is not undo, it is time travel.
   *
   * GESTURE GROUPING. A drag commits a frame per pointermove, so ungrouped, one drag across the
   * stage would be a hundred undo steps and Ctrl+Z would be useless. beginTx() at the gesture's
   * start takes ONE snapshot; the first successful commit inside the gesture pushes it; endTx() at
   * pointerup throws it away if nothing was ever committed -- so a click that merely SELECTS costs
   * no history at all, which is the case that would otherwise make the stack unreadable.
   */

  var HIST_MAX = 100; // deep enough to be an undo stack, bounded so a long session cannot grow forever

  var past = [];
  var future = [];

  var txOpen = false;   // a gesture is in flight
  var txBefore = null;  // the stage as it was when that gesture began
  var txPushed = false; // ...and whether that snapshot is already on the stack

  function snapshot() {
    return {
      title: titleField.innerHTML,
      // :scope > .el -- the same query the serializer uses, so the snapshot sees exactly what the
      // IR sees: no pseudo-element chrome, no title field, and the array order IS the z-order.
      els: [].slice.call(stage.querySelectorAll(':scope > .el')).map(function (el) {
        var body = el.querySelector('.txt .body');
        return {
          state: read(el),
          html: body ? body.innerHTML : null, // the runs live in the DOM, so they are part of the state
          sel: el === selected,
        };
      }),
    };
  }

  /* Returns TRUE when the stage now holds `snap`, and FALSE when it refused it -- and on false the
   * stage is byte-for-byte as it was. The caller owns the history stacks and may only move `snap`
   * off one of them once this has returned true; see undo() and redo(). */
  function restore(snap) {
    /* PASS 1 -- JUDGE. Nothing above this line has touched the DOM, and nothing below it may run if
     * the snapshot is refused. stopEditing() is DOM mutation (it drops .editing and removes the
     * contenteditable attribute) and it calls endTx(), so it belongs BELOW the preflight, not
     * above: "before touching the DOM" means before stopEditing(), not merely before the clear. */
    var why = unrestorableReason(snap);
    if (why) {
      setStatus('That history step was refused, so nothing changed: ' + why);
      return false;
    }

    /* PASS 2 -- COMMIT. Every record is legal, so this cannot fail half-way through. */
    // The alignment set is about to point at nodes this pass removes wholesale below -- drop it
    // before the new snapshot is applied, or `multi` is left holding detached DOM elements.
    clearMulti();
    stopEditing();
    [].slice.call(stage.querySelectorAll(':scope > .el')).forEach(function (n) { n.remove(); });
    // The node `selected` pointed at has just been removed, so the identity check at the top of
    // select() would short-circuit against a corpse. Clear it before anything can consult it.
    selected = null;
    titleField.innerHTML = snap.title;

    var toSelect = null;
    for (var i = 0; i < snap.els.length; i++) {
      var rec = snap.els[i];
      var el = makeEl(rec.state); // NOT commit(): a restore must not be TRANSFORMED -- not
      stage.appendChild(el);      // re-snapped, not clamped, not pushed back onto the stack it came
                                  // from. It HAS been judged, by unrestorableReason(), above.
      var body = el.querySelector('.txt .body');
      if (body && rec.html !== null) body.innerHTML = rec.html;
      if (rec.sel) toSelect = el;
    }
    select(toSelect);
    syncProps(); // select(null) short-circuits when nothing was selected, so ask for this outright
    return true;
  }

  function pushUndo(before) {
    past.push(before);
    if (past.length > HIST_MAX) past.shift();
    future.length = 0; // a fresh edit forks the timeline -- the redos are unreachable now
    syncHistory();
  }

  function beginTx() {
    if (txOpen) return; // a gesture already owns the step; do not start a second one inside it
    txOpen = true;
    txBefore = snapshot();
    txPushed = false;
  }

  /* Call AFTER a mutation has succeeded, never before. `before` is the pre-mutation snapshot, and
   * it is only needed for changes that happen OUTSIDE a gesture -- inside one, txBefore is it. */
  function noteChange(before) {
    if (txOpen) {
      if (!txPushed) { pushUndo(txBefore); txPushed = true; }
      return;
    }
    if (before) pushUndo(before);
  }

  function endTx() { txOpen = false; txBefore = null; txPushed = false; }

  /* PEEK, THEN POP -- never `restore(past.pop())`.
   *
   * A pop written as the argument is evaluated BEFORE the callee runs, so the entry is off the stack
   * before restore() has done anything with it. If the restore is then refused, or throws on a
   * malformed record, the stage has been cleared AND the only copy of the state that would put it
   * back has been destroyed: the user loses the deck and the undo step in one keystroke. So the
   * entry comes off the stack once the stage actually holds it, and not one statement sooner.
   *
   * A refused entry therefore STAYS on the stack. That is the fail-closed half of the trade: Ctrl+Z
   * declining to move is a bug report, whereas silently discarding the user's only copy of a state
   * is a bug we never hear about because the evidence went with it.
   */
  function undo() {
    if (!past.length) { setStatus('Nothing to undo.'); return; }
    endTx(); // a gesture may not straddle an undo
    var now = snapshot();
    if (!restore(past[past.length - 1])) return; // refused: restore() said why, and nothing moved
    past.pop();
    future.push(now);
    syncHistory();
    setStatus('Undo — ' + past.length + ' step(s) left.');
  }

  function redo() {
    if (!future.length) { setStatus('Nothing to redo.'); return; }
    endTx();
    var now = snapshot();
    if (!restore(future[future.length - 1])) return;
    future.pop();
    past.push(now);
    syncHistory();
    setStatus('Redo — ' + future.length + ' step(s) left.');
  }

  function syncHistory() {
    $('b-undo').disabled = !past.length;
    $('b-redo').disabled = !future.length;
  }

  /* -------------------------------------------------------------------------------- rendering */

  function esc(v) { return String(v).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }

  // No fill => fill="none". No stroke => the stroke attribute is OMITTED ENTIRELY. Never
  // stroke-width="0" to mean "no line": width 0 is a HAIRLINE in PowerPoint, not an absence.
  function shapeMarkup(s) {
    var fill = s.fill ? esc(s.fill) : 'none';
    // Preview-only: SVG's fill-opacity is how this stage shows the alpha byte toIR() will fold
    // into the fill's hex string. It never reaches the IR itself -- fill stays a plain 6-digit
    // colour in dataset, and only toIR() combines it with fillAlpha at serialization time.
    var fillOpacity = (s.fill && typeof s.fillAlpha === 'number' && s.fillAlpha < 100)
      ? ' fill-opacity="' + (clamp(s.fillAlpha, 0, 100) / 100) + '"' : '';
    var stroke = s.strokeColor
      ? ' stroke="' + esc(s.strokeColor) + '" stroke-width="' + esc(s.strokeWidth) + '"'
      : '';
    var w = s.w, h = s.h;
    switch (s.type) {
      case 'rect':
        return '<rect x="0" y="0" width="' + w + '" height="' + h + '" fill="' + fill + '"' + fillOpacity + stroke + '/>';
      case 'ellipse':
        return '<ellipse cx="' + w / 2 + '" cy="' + h / 2 + '" rx="' + w / 2 + '" ry="' + h / 2 +
               '" fill="' + fill + '"' + fillOpacity + stroke + '/>';
      case 'triangle':
        // Apex top-centre, base along the bottom edge -- matches MSO_SHAPE.ISOSCELES_TRIANGLE.
        return '<polygon points="' + w / 2 + ',0 ' + w + ',' + h + ' 0,' + h + '" fill="' + fill + '"' + fillOpacity + stroke + '/>';
      case 'textbox':
        // A textbox carries fill and stroke like any other shape; with neither, it draws nothing.
        if (!s.fill && !s.strokeColor) return '';
        return '<rect x="0" y="0" width="' + w + '" height="' + h + '" fill="' + fill + '"' + fillOpacity + stroke + '/>';
      default:
        return '';
    }
  }

  function connectorMarkup(s, ax, ay, bx, by) {
    var mid = 'm-' + s.id;
    // ONE marker, oriented auto-start-reverse, so it serves marker-start and marker-end both.
    // refX sits on the tip (viewBox x = 10), so the tip lands ON the endpoint -- mirroring
    // DrawingML's <a:headEnd> / <a:tailEnd>.
    var marker =
      '<defs><marker id="' + esc(mid) + '" viewBox="0 0 10 10" refX="10" refY="5" ' +
      'markerWidth="6" markerHeight="6" orient="auto-start-reverse" markerUnits="strokeWidth">' +
      '<path d="M 0 0 L 10 5 L 0 10 z" fill="' + esc(s.color) + '"/></marker></defs>';

    var mk = '';
    if (s.arrow === 'start' || s.arrow === 'both') mk += ' marker-start="url(#' + esc(mid) + ')"';
    if (s.arrow === 'end' || s.arrow === 'both') mk += ' marker-end="url(#' + esc(mid) + ')"';

    var attrs = 'fill="none" stroke="' + esc(s.color) + '" stroke-width="' + esc(s.width) + '"' + mk;

    if (s.kind === 'elbow') {
      // An APPROXIMATION. PowerPoint's MSO_CONNECTOR.ELBOW auto-routes; this polyline does not.
      // This is the one place the preview is knowingly inexact, and the UI says so.
      var mx = (ax + bx) / 2;
      return marker + '<polyline points="' + ax + ',' + ay + ' ' + mx + ',' + ay + ' ' +
             mx + ',' + by + ' ' + bx + ',' + by + '" ' + attrs + '/>';
    }
    return marker + '<line x1="' + ax + '" y1="' + ay + '" x2="' + bx + '" y2="' + by + '" ' + attrs + '/>';
  }

  function renderEl(el) {
    var s = read(el);
    var svg = el.querySelector('svg');

    if (s.type === 'connector') {
      // The wrapper spans the endpoints' AABB. max(..., 1) keeps a perfectly horizontal line's SVG
      // box non-degenerate and NEVER touches the IR, which stores the raw endpoints.
      var minX = Math.min(s.x1, s.x2), minY = Math.min(s.y1, s.y2);
      var w = Math.max(Math.abs(s.x2 - s.x1), 1);
      var h = Math.max(Math.abs(s.y2 - s.y1), 1);
      var ax = s.x1 - minX, ay = s.y1 - minY, bx = s.x2 - minX, by = s.y2 - minY;

      el.style.left = minX + 'px';
      el.style.top = minY + 'px';
      el.style.width = w + 'px';
      el.style.height = h + 'px';
      el.style.setProperty('--rot', '0deg');

      svg.setAttribute('width', w);
      svg.setAttribute('height', h);
      svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
      svg.innerHTML = connectorMarkup(s, ax, ay, bx, by);

      var p1 = el.querySelector('.handle[data-h="p1"]');
      var p2 = el.querySelector('.handle[data-h="p2"]');
      if (p1) { p1.style.left = ax - 4 + 'px'; p1.style.top = ay - 4 + 'px'; }
      if (p2) { p2.style.left = bx - 4 + 'px'; p2.style.top = by - 4 + 'px'; }
      return;
    }

    if (isMediaType(s.type)) {
      el.style.left = s.x + 'px';
      el.style.top = s.y + 'px';
      el.style.width = s.w + 'px';
      el.style.height = s.h + 'px';
      // NEVER rotated: render_canvas.draw_image()/draw_video() apply no xfrm/@rot, and makeEl()
      // withholds the rotate handle for this type, so s.rot is always 0 here -- but writing '0deg'
      // explicitly (rather than trusting that) keeps this branch correct even if that changes.
      el.style.setProperty('--rot', '0deg');
      var media = el.querySelector('.media');
      // Bound once per (element, src) pair, not every render: renderEl() runs on every commit (a
      // resize, a drag frame...), and re-assigning .src on an already-current object URL would
      // needlessly reload the image/restart the video on every frame.
      if (media && media.dataset.boundSrc !== s.src) {
        var entry = window.uploadedMedia && window.uploadedMedia[s.src];
        media.src = entry ? entry.url : '';
        media.dataset.boundSrc = s.src;
      }
      return;
    }

    el.style.left = s.x + 'px';
    el.style.top = s.y + 'px';
    el.style.width = s.w + 'px';
    el.style.height = s.h + 'px';
    // Degrees clockwise about the centre -- identical to shape.rotation. No conversion.
    el.style.setProperty('--rot', (s.rot || 0) + 'deg');

    svg.setAttribute('width', s.w);
    svg.setAttribute('height', s.h);
    svg.setAttribute('viewBox', '0 0 ' + s.w + ' ' + s.h);
    svg.innerHTML = shapeMarkup(s);

    var txt = el.querySelector('.txt');
    txt.dataset.align = s.align;
    txt.dataset.valign = s.valign;
    txt.style.fontSize = s.size + 'px';
    txt.style.color = s.color;
  }

  /* --------------------------------------------------------------------------- element factory */

  function nextId() {
    var id;
    do { idSeq += 1; id = 'el' + idSeq; } while (stage.querySelector('.el[data-id="' + id + '"]'));
    return id;
  }

  function handleHTML(h) { return '<div class="handle" data-h="' + h + '"></div>'; }

  function makeEl(s) {
    var el = document.createElement('div');
    el.className = 'el';
    var html;

    if (s.type === 'connector') {
      html = '<svg xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none"></svg>';
      html += handleHTML('p1') + handleHTML('p2');
    } else if (isMediaType(s.type)) {
      // No <svg>, no .txt -- a picture/video is not drawn, it is embedded. `draggable="false"` on
      // the <img> stops the browser's OWN native image-drag (which would fight the pointer-capture
      // drag in interactions.js and never call commit() at all). NO ROTATE HANDLE: withheld here,
      // not merely hidden, because render_canvas.draw_image()/draw_video() apply no xfrm/@rot, and
      // a handle the renderer cannot honour is worse than no handle.
      html = s.type === 'image'
        ? '<img class="media" draggable="false" alt="">'
        : '<video class="media" muted playsinline preload="metadata"></video>';
      for (var i = 0; i < HANDLES.length; i++) html += handleHTML(HANDLES[i]);
    } else {
      html = '<svg xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none"></svg>';
      // .txt is the flex/anchor box (the Sec 5.6 contract); .body is the text. One flex item, so
      // multiple paragraphs stack instead of laying out side by side.
      //
      // NOTE THE ABSENT contenteditable. It is added by the dblclick handler and removed by
      // stopEditing(). It used to be hard-coded here, with only `pointer-events: none` on .txt
      // keeping the caret out -- which meant the element was, to the keyboard and to every
      // assistive technology, permanently editable, and editingText() could not tell "the caret is
      // in the text" from "the text merely exists".
      html += '<div class="txt"><div class="body"></div></div>';
      for (var j = 0; j < HANDLES.length; j++) html += handleHTML(HANDLES[j]);
      html += handleHTML('rot');
    }
    el.innerHTML = html;
    write(el, s);
    renderEl(el);
    wire(el);
    return el;
  }

  // Z-ORDER IS DOM ORDER AND NOTHING ELSE. No `z` field, no CSS stacking index on .el, no sort key
  // -- any of those would be a second source of truth and would desync. Raise/lower are pure
  // insertBefore/append.
  // New connectors go to the FRONT of the array -- drawn first, therefore BEHIND the boxes they
  // join. Front of array == back of the slide.
  function addEl(el) {
    if (el.dataset.type === 'connector') {
      var firstShape = stage.querySelector(':scope > .el:not([data-type="connector"])');
      stage.insertBefore(el, firstShape); // null => append
    } else {
      stage.appendChild(el);
    }
    return el;
  }

  /* ------------------------------------------------------------------------------ interactions */

  function wire(el) {
    // Drag the body. The text and the handles are excluded: a pointerdown in the text must land a
    // caret, and one on a handle must resize.
    // select() FIRST, then beginTx(): select() closes any open text session, and closing one ends
    // its transaction. Opening ours before that would hand our snapshot straight to endTx().
    Interactions.draggable(el, {
      ignoreFrom: '.txt, .handle',
      // Shift held -> this pointerdown is a multi-select TOGGLE (see the plain pointerdown
      // listener below), not a drag. interactions.js hands the triggering event to `enabled` for
      // exactly this (Phase 6).
      enabled: function (ev) { return tool === 'select' && !(ev && ev.shiftKey); },
      start: function () { select(el); beginTx(); },
      end: endTx,
      move: function (ctx) {
        var s = read(el);
        // Device px -> logical units. ALWAYS. This is the corollary of the Prime Directive.
        var dx = ctx.dx / zoom, dy = ctx.dy / zoom;
        if (s.type === 'connector') {
          commit(el, { x1: s.x1 + dx, y1: s.y1 + dy, x2: s.x2 + dx, y2: s.y2 + dy },
                 { alt: ctx.pointer.altKey });
        } else {
          commit(el, { x: s.x + dx, y: s.y + dy }, { alt: ctx.pointer.altKey });
        }
      },
    });

    if (el.dataset.type === 'connector') {
      ['p1', 'p2'].forEach(function (which) {
        var h = el.querySelector('.handle[data-h="' + which + '"]');
        Interactions.pointerDrag(h, {
          start: function () { select(el); beginTx(); },
          end: endTx,
          move: function (ctx) {
            // Endpoints drag individually. NO GLUING -- begin_connect()/end_connect() are out of
            // Phase 1 (D-3).
            var p = toModel(ctx.pointer);
            var patch = which === 'p1' ? { x1: p.x, y1: p.y } : { x2: p.x, y2: p.y };
            commit(el, patch, { alt: ctx.pointer.altKey });
          },
        });
      });
      return;
    }

    HANDLES.forEach(function (h) {
      var node = el.querySelector('.handle[data-h="' + h + '"]');
      Interactions.resizable(node, h, {
        start: function () { select(el); beginTx(); },
        end: endTx,
        move: function (ctx) {
          var s = read(el);
          // deltaRect is DEVICE PIXELS, exactly as interact.js reports it. Each field is divided
          // by zoom, in the same expression, or the whole thing breaks the moment zoom != 1.
          var nx = s.x + ctx.deltaRect.left / zoom;
          var ny = s.y + ctx.deltaRect.top / zoom;
          var nw = s.w + ctx.deltaRect.width / zoom;
          var nh = s.h + ctx.deltaRect.height / zoom;
          commit(el, { x: nx, y: ny, w: nw, h: nh },
                 { alt: ctx.pointer.altKey, edges: ctx.edges });
        },
      });
    });

    // Withheld entirely for media (makeEl() never builds this handle for an image/video): guard
    // rather than assume, since Interactions.pointerDrag(null, ...) would throw on the missing node.
    var rotHandle = el.querySelector('.handle[data-h="rot"]');
    if (rotHandle) {
      Interactions.pointerDrag(rotHandle, {
        start: function () { select(el); beginTx(); },
        end: endTx,
        move: function (ctx) {
          var s = read(el);
          var p = toModel(ctx.pointer);
          var cx = s.x + s.w / 2, cy = s.y + s.h / 2;
          // +90 so that "handle straight up" reads as 0 degrees.
          var deg = (Math.atan2(p.y - cy, p.x - cx) * 180) / Math.PI + 90;
          if (ctx.pointer.shiftKey) deg = Math.round(deg / 15) * 15;
          deg = ((deg + 180) % 360 + 360) % 360 - 180; // normalize to (-180, 180]
          commit(el, { rot: round6(deg) }, { alt: ctx.pointer.altKey });
          syncProps();
        },
      });
    }

    // Plain click: select (and clear any multi-selection -- a plain click always starts over).
    // Shift+click: TOGGLE this element's membership in the alignment set instead, leaving
    // `selected` (and the property panel) exactly as they were. stopPropagation() keeps it from
    // also reaching the stage's own pointerdown listener, which would otherwise read it as "the
    // background was clicked" and deselect everything.
    el.addEventListener('pointerdown', function (ev) {
      if (tool !== 'select') return;
      if (ev.shiftKey) { ev.stopPropagation(); toggleMulti(el); return; }
      if (multi.length) clearMulti();
      select(el);
    });

    // Typing is a mutation like any other, and it is grouped like any other: the session opened by
    // the dblclick below is ONE undo step, however many keystrokes it holds.
    var textBody = el.querySelector('.txt .body');
    if (textBody) textBody.addEventListener('input', function () { noteChange(); });

    // Click selects and drags; DOUBLE-click opens the text. Without this a no-fill textbox could
    // never be dragged at all -- its .txt covers the whole element and would eat every grab.
    el.addEventListener('dblclick', function (ev) {
      if (tool !== 'select' || el.dataset.type === 'connector') return;
      ev.preventDefault();
      startEditing(el);
    });
  }

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
    var open = stage.querySelectorAll('.el.editing');
    for (var i = 0; i < open.length; i++) {
      open[i].classList.remove('editing');
      // Drop the attribute with the class. An element that is not being edited is not editable --
      // leaving it behind is what made `contenteditable` permanent in the first place.
      var body = open[i].querySelector('.txt .body');
      if (body) body.removeAttribute('contenteditable');
    }
    // The session ends here. If nothing was typed, txPushed is false and the snapshot is simply
    // dropped -- opening the text and closing it again is not an edit.
    endTx();
  }

  /* Creation by drag-out on the stage. Pointer coords via toModel(), then the SAME pipeline -- so
     an illegal shape cannot be drawn in the first place. */
  Interactions.pointerDrag(stage, {
    filter: function (ev) {
      if (tool === 'select') return false;
      // A drawing tool draws, even over an existing element -- the alternative is that the user
      // cannot put a label on top of a box. Only the title field keeps its caret.
      return !ev.target.closest('#title-field');
    },
    start: function (ctx) {
      ctx.origin = toModel(ctx.pointer);
      ctx.made = null;
      // NOT beginTx(). The moment this gesture creates its element it calls select(), and select()
      // closes any open text session -- which would end our transaction and take the snapshot with
      // it. So the draw path carries its own `before` and pushes it exactly once, at creation.
      ctx.before = snapshot();
    },
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
        var d = DEFAULTS.connector;
        cand = {
          id: ctx.made ? ctx.made.dataset.id : nextId(), type: 'connector',
          x1: o.x, y1: o.y, x2: p.x, y2: p.y,
          kind: d.kind, arrow: d.arrow, color: d.color, width: d.width,
        };
      } else {
        var def = tool === 'textbox' ? DEFAULTS.textbox : DEFAULTS.shape;
        cand = {
          id: ctx.made ? ctx.made.dataset.id : nextId(), type: tool,
          x: Math.min(o.x, p.x), y: Math.min(o.y, p.y),
          w: Math.abs(p.x - o.x), h: Math.abs(p.y - o.y), rot: 0,
          fill: def.fill, strokeColor: def.strokeColor, strokeWidth: def.strokeWidth,
          size: def.size, color: def.color, align: def.align, valign: def.valign,
          bold: def.bold, italic: def.italic,
        };
      }

      var edges = { left: true, right: true, top: true, bottom: true };
      var legal = applyConstraints(cand, { alt: ctx.pointer.altKey, edges: edges });
      if (!legal) {
        if (ctx.made) flashBlocked(ctx.made);
        return; // an illegal shape simply does not get drawn
      }

      if (!ctx.made) {
        ctx.made = addEl(makeEl(legal));
        select(ctx.made);
        // ONE step for the whole drag-out: the element and the size it was drawn at are a single
        // act, and undoing it should leave no husk behind. Every later frame of this gesture goes
        // down the write()/renderEl() path below, which pushes nothing.
        pushUndo(ctx.before);
      } else {
        write(ctx.made, legal);
        renderEl(ctx.made);
      }
    },
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

  /* ---------------------------------------------------------------- media insertion (Phase 6) --
   *
   * Not a drag-out tool: a picture/video comes from a file picker, so it is placed centred in the
   * body-safe area at a fixed default size and immediately selected, the way a click-to-drop
   * shape is. window.uploadedMedia is the SESSION's own file store -- {name: {file, url}} -- named
   * on `window` rather than a closure-local var because the export handler (below) needs to read
   * the exact same File objects to build the multipart body it POSTs.
   */
  window.uploadedMedia = window.uploadedMedia || {};

  // Registers `file` under its own name, or a de-duplicated variant of it when that name already
  // names a DIFFERENT File -- two uploads both called "photo.jpg" must not collide, or the second
  // would silently shadow the first and an element still pointing at the first's `src` would
  // export whichever file happened to win the race. Returns the src to store on the element.
  function registerMedia(file) {
    var name = file.name || 'media';
    var n = 1;
    while (window.uploadedMedia[name] && window.uploadedMedia[name].file !== file) {
      var dot = file.name.lastIndexOf('.');
      var stem = dot > 0 ? file.name.slice(0, dot) : file.name;
      var ext = dot > 0 ? file.name.slice(dot) : '';
      name = stem + '-' + (n++) + ext;
    }
    if (!window.uploadedMedia[name]) {
      window.uploadedMedia[name] = { file: file, url: URL.createObjectURL(file) };
    }
    return name;
  }

  function insertMedia(type, file) {
    var src = registerMedia(file);
    var sz = MEDIA_DEFAULT_SIZE;
    var cand = {
      id: nextId(), type: type,
      x: (CANVAS.w - sz.w) / 2, y: (CANVAS.h - sz.h) / 2, w: sz.w, h: sz.h, rot: 0,
      src: src,
    };
    // Goes through the SAME judge as everything else on the stage (alt: true -- a deliberate
    // placement is not re-snapped, but is still clamped on-slide, exactly like click-to-drop).
    var legal = applyConstraints(cand, { alt: true });
    if (!legal) { setStatus('That ' + type + ' would not fit legally here — nothing was added.'); return; }
    var before = snapshot();
    var made = addEl(makeEl(legal));
    if (multi.length) clearMulti();
    select(made);
    pushUndo(before); // one step: the insertion and its placement are a single act
    if (type === 'image') {
      setStatus('Note: Attached images are validated; model generation currently reads text prompt');
    } else {
      setStatus('Added ' + type + ' ' + legal.id + '.');
    }
  }

  function mediaInputHandler(type) {
    return function () {
      var file = this.files && this.files[0];
      this.value = ''; // clears the input so picking the SAME file again still fires `change`
      if (!file) return;
      insertMedia(type, file);
    };
  }
  // Wired further down, in "the toolbar" section -- $() (document.getElementById) is not defined
  // until then, and these are plain statements that run at script-load time, not inside a function.

  stage.addEventListener('pointerdown', function (ev) {
    if (tool === 'select' && !ev.target.closest('.el') && !ev.target.closest('#title-field')) {
      if (multi.length) clearMulti();
      select(null);
    }
  });

  /* ---------------------------------------------------------------------------------- selection */

  function select(el) {
    // Deselecting to nothing always drops the alignment set too -- checked BEFORE the early-return
    // below, since selected and el can both already be null (e.g. multi has members but nothing is
    // PLAIN-selected) and that case must still clear multi, not short-circuit past it.
    if (!el && multi.length) { clearMulti(); syncProps(); }
    if (selected === el) return;
    stopEditing(); // leaving an element always closes its text
    if (selected) selected.classList.remove('selected');
    selected = el;
    if (selected) selected.classList.add('selected');
    syncProps();
  }

  /* --------------------------------------------------------------- multi-selection (Phase 6) --
   *
   * Additive to `selected`, never a replacement for it -- see the comment on `var multi` above.
   * Shift+Click toggles membership here (wire()'s pointerdown listener) and never touches
   * `selected`, so the property panel keeps describing whichever element was last PLAIN-clicked
   * (or shows nothing if none has been, even with a multi-selection in progress). */

  function selectionSet() {
    var set = [];
    if (selected) set.push(selected);
    for (var i = 0; i < multi.length; i++) {
      if (set.indexOf(multi[i]) < 0) set.push(multi[i]);
    }
    return set;
  }

  function toggleMulti(el) {
    var i = multi.indexOf(el);
    if (i >= 0) { multi.splice(i, 1); el.classList.remove('multi-selected'); }
    else { multi.push(el); el.classList.add('multi-selected'); }
    syncProps();
  }

  function clearMulti() {
    multi.forEach(function (el) { el.classList.remove('multi-selected'); });
    multi.length = 0;
  }

  /* --------------------------------------------------------- text: contenteditable -> runs/paras */

  // Strip C0 EXCEPT \t and \n. validate.py rejects them; stripping here means the user never gets a
  // 422 for a character they cannot see. (  is NOT C0 and is preserved verbatim.)
  function stripC0(t) { return t.replace(/[\x00-\x08\x0b-\x1f]/g, ''); }

  var BLOCK_TAGS = { DIV: 1, P: 1, LI: 1, H1: 1, H2: 1, H3: 1, H4: 1, H5: 1, H6: 1, BLOCKQUOTE: 1, PRE: 1 };

  function hex2(n) { return ('0' + n.toString(16)).slice(-2).toUpperCase(); }

  function cssColorToHex(raw) {
    var v = String(raw).trim();
    var m = v.match(/^rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
    if (m) return '#' + hex2(+m[1]) + hex2(+m[2]) + hex2(+m[3]);
    m = v.match(/^#([0-9a-f]{6})$/i);
    if (m) return '#' + m[1].toUpperCase();
    m = v.match(/^#([0-9a-f]{3})$/i);
    if (m) {
      var s = m[1];
      return '#' + (s[0] + s[0] + s[1] + s[1] + s[2] + s[2]).toUpperCase();
    }
    return null; // a named colour or anything exotic: fall back to the element default
  }

  // The INLINE style attribute only -- never the browser's COMPUTED style, which is banned (Gate 1)
  // and would silently bake the CSS default colour into every single run.
  function colorOf(node) {
    var inline = node.style && node.style.color;
    if (inline) { var c = cssColorToHex(inline); if (c) return c; }
    if (node.tagName === 'FONT') {
      var attr = node.getAttribute('color');
      if (attr) { var f = cssColorToHex(attr); if (f) return f; }
    }
    return null;
  }

  /* normalizeText(root) -> [paragraph, ...] | null
   *
   * Every run carries t, size and color -- all three are REQUIRED by the schema. An un-coloured run
   * inherits fontRef -> lt1, which is WHITE, and that is the rule that stops white-on-white text.
   *
   * defBold/defItalic are the ELEMENT's flags, and they are OR-ed into every run -- the same
   * relationship defSize and defColor already have with the runs, just spelled out. The IR has no
   * element-level bold to serialize them into; run.bold is the only place they can land. A <b> or a
   * <strong> INSIDE the body (a paste, or the browser's own Ctrl+B) still bolds its own run on its
   * own, which is why turning the element flag off has to remove those tags -- see setTextFlag().
   */
  function normalizeText(root, defSize, defColor, defBold, defItalic) {
    var paras = [];
    var cur = null;

    function startPara() { cur = []; paras.push(cur); }
    startPara();

    function push(text, fmt) {
      if (!text) return;
      var run = { t: text, size: defSize, color: fmt.color || defColor };
      if (fmt.bold || defBold) run.bold = true;
      if (fmt.italic || defItalic) run.italic = true;
      var last = cur[cur.length - 1];
      // Merge adjacent runs with identical formatting.
      if (last && !!last.bold === !!run.bold && !!last.italic === !!run.italic && last.color === run.color) {
        last.t += run.t;
      } else {
        cur.push(run);
      }
    }

    function walk(node, fmt) {
      var kids = node.childNodes;
      for (var i = 0; i < kids.length; i++) {
        var child = kids[i];

        if (child.nodeType === 3) { // text
          push(stripC0(child.nodeValue), fmt);
          continue;
        }
        if (child.nodeType !== 1) continue; // comments and the rest

        var tag = child.tagName;

        if (tag === 'BR') {
          // A <br> that is the LAST child of its block is the browser's own filler -- Chrome puts
          // one in every empty contenteditable block to give it height. Emitting it would add a
          // phantom trailing line to the PPTX.
          if (child === node.lastChild) continue;
          push('\n', fmt); // style.py splits on \n and emits <a:br/>
          continue;
        }

        var f = { bold: fmt.bold, italic: fmt.italic, color: fmt.color };
        if (tag === 'B' || tag === 'STRONG') f.bold = true;
        if (tag === 'I' || tag === 'EM') f.italic = true;
        var c = colorOf(child);
        if (c) f.color = c;

        if (BLOCK_TAGS[tag]) startPara(); // a block element is a NEW PARAGRAPH
        walk(child, f);
      }
    }

    walk(root, { bold: false, italic: false, color: null });

    // Drop empty runs, then empty paragraphs -- browsers leave trailing empty <div>s behind
    // constantly.
    var out = [];
    for (var p = 0; p < paras.length; p++) {
      var runs = paras[p].filter(function (r) { return r.t !== ''; });
      if (runs.length) out.push({ runs: runs });
    }
    // If nothing survives, the caller emits "text": null -- NOT paragraphs: [], which the schema
    // rejects (minItems: 1).
    return out.length ? out : null;
  }

  // The title is the same walk, flattened to a plain STRING. A "\n" becomes an <a:br/> in
  // placeholder 10.
  function titleString() {
    var out = '';
    (function walk(node) {
      var kids = node.childNodes;
      for (var i = 0; i < kids.length; i++) {
        var child = kids[i];
        if (child.nodeType === 3) { out += child.nodeValue; continue; }
        if (child.nodeType !== 1) continue;
        if (child.tagName === 'BR') {
          if (child !== node.lastChild) out += '\n';
          continue;
        }
        if (BLOCK_TAGS[child.tagName] && out !== '') out += '\n';
        walk(child);
      }
    })(titleField);
    return stripC0(out).replace(/\n+$/, '');
  }

  /* -------------------------------------------------------------------------------- serializer */

  // Folds a 0-100 opacity PERCENT into the trailing AA byte of a #RRGGBB colour, per schema.json's
  // `color` def (#RRGGBB, or #RRGGBBAA where the trailing byte is alpha). 100 (opaque) emits no
  // byte at all -- an unmodified 6-digit colour is the common case and stays exactly what it was
  // before Phase 6, so decks with no transparency are byte-identical to what this editor emitted
  // before this feature existed.
  function withAlpha(hex6, alphaPct) {
    if (typeof alphaPct !== 'number' || alphaPct >= 100) return hex6;
    return hex6 + hex2(Math.round(clamp(alphaPct, 0, 100) / 100 * 255));
  }

  function toIR(el) {
    var s = read(el);

    if (s.type === 'connector') {
      // No w/h. No text. No z. Exactly the schema's keys for this type and NOTHING else --
      // additionalProperties: false means one leaked data-* is a hard rejection.
      return {
        id: s.id, type: 'connector', kind: s.kind,
        x1: round6(s.x1), y1: round6(s.y1), x2: round6(s.x2), y2: round6(s.y2),
        color: s.color, width: round6(s.width), arrow: s.arrow,
      };
    }

    if (isMediaType(s.type)) {
      // No fill, no stroke, no text, no rotation: the properties panel never offers them for this
      // type (see syncProps()'s "media" category) and render_canvas.draw_image()/draw_video()
      // never draw them even when present, so this editor never emits them for media at all --
      // schema.json lists fill/stroke as OPTIONAL for image/video (unlike a rect, where fill is
      // REQUIRED even when null), and omitting an optional key is exactly what "optional" means.
      return {
        id: s.id, type: s.type,
        x: round6(s.x), y: round6(s.y), w: round6(s.w), h: round6(s.h),
        src: s.src,
      };
    }

    var out = {
      id: s.id, type: s.type,
      x: round6(s.x), y: round6(s.y), w: round6(s.w), h: round6(s.h),
      fill: s.fill ? withAlpha(s.fill, s.fillAlpha) : null, // REQUIRED even when null
    };
    if (s.rot) out.rotation = round6(s.rot);
    if (s.strokeColor) out.stroke = { color: s.strokeColor, width: round6(s.strokeWidth) };

    var body = el.querySelector('.txt .body');
    var paragraphs = body ? normalizeText(body, s.size, s.color, s.bold, s.italic) : null;
    out.text = paragraphs ? { align: s.align, valign: s.valign, paragraphs: paragraphs } : null;
    return out;
  }

  function serialize() {
    return {
      schema: SCHEMA,
      canvas: { w: CANVAS.w, h: CANVAS.h, unit: CANVAS.unit },
      target: {
        template: 'reference/renderer_template.pptx', // informational ONLY; the server ignores it
        template_sha256: CONTEXT.template_sha256,     // from /api/context -- NEVER hard-coded
        layout_index: CONTEXT.layout_index,
      },
      title: titleString(),
      // :scope > .el is the whole z-order story AND the whole "chrome cannot be serialized" story:
      // the pseudo-elements have no node, and #title-field has no .el.
      elements: [].slice.call(stage.querySelectorAll(':scope > .el')).map(toIR),
    };
  }

  /* ---------------------------------------------------------------------------------- warnings */

  function clearWarnings() { warnings.hidden = true; warnings.innerHTML = ''; }

  function warn(title, detail) {
    var wrap = document.createElement('div');
    wrap.className = 'w-item';
    var h = document.createElement('div');
    h.className = 'w-title';
    h.textContent = title;
    wrap.appendChild(h);
    if (detail) {
      var d = document.createElement('div');
      d.textContent = detail; // the backend's numbered list, rendered VERBATIM
      wrap.appendChild(d);
    }
    if (!warnings.querySelector('.w-close')) {
      var x = document.createElement('button');
      x.className = 'w-close';
      x.type = 'button';
      x.textContent = '×';
      x.addEventListener('click', clearWarnings);
      warnings.appendChild(x);
    }
    warnings.appendChild(wrap);
    warnings.hidden = false;
  }

  function setStatus(m) { statusMsg.textContent = m; }

  /* ------------------------------------------------------------------------------- the toolbar */

  var $ = function (id) { return document.getElementById(id); };

  function setTool(t) {
    tool = t;
    var btns = document.querySelectorAll('.tool');
    for (var i = 0; i < btns.length; i++) {
      btns[i].setAttribute('aria-pressed', String(btns[i].dataset.tool === t));
    }
    stage.style.cursor = t === 'select' ? 'default' : 'crosshair';
  }

  document.querySelectorAll('.tool').forEach(function (b) {
    b.addEventListener('click', function () { setTool(b.dataset.tool); });
  });

  function setZoom(pct) {
    zoom = clamp(pct, ZOOM_MIN, ZOOM_MAX) / 100;
    // CSS is written FROM the state. It is never read back.
    stage.style.setProperty('--zoom', zoom);
    stageWrap.style.setProperty('--zoom', zoom);
    $('p-zoom-out').textContent = Math.round(zoom * 100) + '%';
  }

  $('p-zoom').addEventListener('input', function () { setZoom(+this.value); });

  // Phase 6: image/video insertion. registerMedia()/insertMedia()/mediaInputHandler() are defined
  // above, alongside finishCreate() (the other "build it, place it, select it" tail); wiring lives
  // here because $() does not exist until this point in the file's top-to-bottom, load-time run.
  $('b-add-image').addEventListener('click', function () { $('f-image').click(); });
  $('b-add-video').addEventListener('click', function () { $('f-video').click(); });
  $('f-image').addEventListener('change', mediaInputHandler('image'));
  $('f-video').addEventListener('change', mediaInputHandler('video'));

  /* The colour guard. #4472C4 is refused in EVERY colour input, with the reason validate.py gives. */
  function guardColor(input, onOK) {
    input.addEventListener('input', function () {
      var v = String(input.value).toUpperCase();
      if (v === FORBIDDEN_COLOR) {
        warn(
          'That colour is not available: ' + FORBIDDEN_COLOR,
          'It is this template\'s theme accent1. It is banned as an explicit author choice so that ' +
          '"no accent1 in any generated shape" stays machine-checkable rather than aspirational — ' +
          'if you could legitimately pick it, that assertion could never be checked. ' +
          'New content defaults to ' + BRAND_RED + '. (canvas/validate.py would reject this with a 422.)'
        );
        input.value = BRAND_RED;
        return;
      }
      onOK(v);
    });
  }

  function patchSelected(patch) {
    if (!selected) return;
    commit(selected, patch, { alt: true }); // a property edit must not be silently re-snapped
  }

  function isConnector() { return !!selected && selected.dataset.type === 'connector'; }
  function isMedia() { return !!selected && isMediaType(selected.dataset.type); }

  /* A PROPERTY CONTROL IS A GESTURE TOO, and forgetting that is how an undo stack becomes useless.
   *
   * A colour picker and a range slider both fire `input` continuously while they are being dragged,
   * so without this, one nudge of the rotation slider would be fifty undo steps and Ctrl+Z would
   * walk back through them one degree at a time. pointerdown/keydown opens the step; `change`, which
   * fires ONCE when the control is done, closes it.
   *
   * #p-zoom is deliberately NOT wired through here. Zoom is VIEW, not document: it is not in a
   * snapshot and it must not be on the stack.
   */
  function txControl(node) {
    node.addEventListener('pointerdown', beginTx);
    node.addEventListener('keydown', beginTx);
    node.addEventListener('change', endTx);
  }

  ['p-fill', 'p-fill-alpha', 'p-stroke', 'p-stroke-w', 'p-color', 'p-size', 'p-align', 'p-valign',
   'p-kind', 'p-arrow', 'p-rot'].forEach(function (id) { txControl($(id)); });

  guardColor($('p-fill'), function (v) {
    if (isConnector()) return; // a connector has no fill -- the schema does not give it one
    patchSelected({ fill: v });
  });

  // Phase 6: opacity. A PERCENT in state; toIR() is the only place it becomes the fill's trailing
  // hex byte, so this handler patches fillAlpha exactly the way p-size patches size -- no colour
  // math happens here at all.
  $('p-fill-alpha').addEventListener('input', function () {
    var pct = +this.value;
    $('p-fill-alpha-out').textContent = pct + '%';
    if (!isConnector() && !isMedia()) patchSelected({ fillAlpha: pct });
  });

  // The stroke input drives a shape's outline AND a connector's line: a connector IS a line, so its
  // colour belongs on the stroke control, not on the text one.
  guardColor($('p-stroke'), function (v) {
    patchSelected(isConnector() ? { color: v } : { strokeColor: v });
  });

  guardColor($('p-color'), function (v) {
    if (isConnector()) return; // a connector carries no text at all (schema: no `text` key)
    patchSelected({ color: v });
  });

  $('p-fill-none').addEventListener('click', function () {
    if (!isConnector()) patchSelected({ fill: '' });
  });

  $('p-stroke-none').addEventListener('click', function () {
    if (isConnector()) return; // a connector cannot have "no line" -- a line is all it is
    patchSelected({ strokeColor: '' });
  });

  // Phase 6: a one-click preset over stroke.color/stroke.width -- NOT a second IR property (the
  // schema has no `border` key). Checked means exactly #000000 @ 1pt; unchecked clears the line
  // entirely, mirroring the "none" button rather than restoring whatever line existed before.
  $('p-border-1pt').addEventListener('change', function () {
    if (isConnector() || isMedia()) return;
    if (this.checked) patchSelected({ strokeColor: '#000000', strokeWidth: 1 });
    else patchSelected({ strokeColor: '' });
  });

  $('p-stroke-w').addEventListener('input', function () {
    var w = +this.value;
    // Width 0 is a HAIRLINE in PowerPoint, not an absence -- a browser draws nothing for it while
    // PowerPoint draws the thinnest line it can. Say so, rather than let it look like "no line".
    if (w === 0 && !isConnector()) {
      warn(
        'Stroke width 0 is a HAIRLINE, not "no line"',
        'A browser draws nothing for width 0; PowerPoint draws the thinnest line it can. To get no ' +
        'line at all, press the stroke "none" button — that serializes as "stroke": null.'
      );
    }
    patchSelected(isConnector() ? { width: w } : { strokeWidth: w });
  });

  $('p-size').addEventListener('input', function () {
    if (!isConnector()) patchSelected({ size: +this.value });
  });

  /* ---------------------------------------------------------------------------- run.bold / run.italic
   *
   * The two IR properties the Phase 1B panel never exposed. They are ELEMENT-level controls over a
   * PER-RUN property, and the asymmetry is the whole difficulty:
   *
   *   ON  -- set the flag. normalizeText() OR-s it into every run on the way out, and style.css
   *          shows it via [data-bold='1']. Nothing is written into the body.
   *   OFF -- clear the flag AND unwrap every <b>/<strong> (resp. <i>/<em>) inside the body.
   *
   * The unwrap is not tidying, it is the difference between working and not. run.bold comes from
   * those tags as well as from the flag -- paragraphsToHTML() writes them on import, and the
   * browser's own Ctrl+B and any paste will too -- so an "off" that merely stopped ADDING bold
   * would leave the text bold on screen and in the .pptx, with the button showing un-pressed. The
   * control would look broken because it would BE broken.
   *
   * The cost is honest and worth stating: turning bold off on an element whose runs were only
   * PARTLY bold flattens that distinction. "Make this element not bold" is what the button says, and
   * it is what the button does.
   */
  function unwrapTags(root, tags) {
    var node;
    // A DOM edit, not a DOM measurement. normalizeText() already reads this very subtree -- it is
    // where runs come from -- so the body is state, not geometry, and the Prime Directive is silent
    // on it. Nested tags terminate: the outermost match is removed each pass.
    while ((node = root.querySelector(tags.join(',')))) {
      var parent = node.parentNode;
      while (node.firstChild) parent.insertBefore(node.firstChild, node);
      parent.removeChild(node);
    }
    root.normalize(); // merge the text nodes the unwrap left adjacent
  }

  function setTextFlag(which, on) {
    if (!selected || isConnector()) return; // a connector carries no text at all (schema: no `text`)
    beginTx(); // the unwrap and the flag are ONE undo step, not two
    var body = selected.querySelector('.txt .body');
    if (!on && body) unwrapTags(body, which === 'bold' ? ['b', 'strong'] : ['i', 'em']);
    var patch = {};
    patch[which] = on;
    patchSelected(patch); // geometry is untouched, so the judge cannot refuse this
    endTx();
    syncProps();
  }

  $('p-bold').addEventListener('click', function () {
    if (selected) setTextFlag('bold', !read(selected).bold);
  });
  $('p-italic').addEventListener('click', function () {
    if (selected) setTextFlag('italic', !read(selected).italic);
  });
  $('p-align').addEventListener('change', function () { patchSelected({ align: this.value }); });
  $('p-valign').addEventListener('change', function () { patchSelected({ valign: this.value }); });
  $('p-kind').addEventListener('change', function () { patchSelected({ kind: this.value }); });
  $('p-arrow').addEventListener('change', function () { patchSelected({ arrow: this.value }); });

  $('p-rot').addEventListener('input', function () {
    var deg = +this.value;
    $('p-rot-out').textContent = deg + '°';
    patchSelected({ rot: deg });
  });

  // Raise/lower reorder the DOM, and DOM order IS z-order -- which a snapshot records as the order
  // of its array. So they are undoable for free, and pushing BEFORE the move is the whole of it.
  $('b-raise').addEventListener('click', function () {
    if (!selected) return;
    var next = selected.nextElementSibling;
    while (next && !next.classList.contains('el')) next = next.nextElementSibling;
    if (!next) return; // already at the front: not a move, so not a step
    pushUndo(snapshot());
    stage.insertBefore(next, selected); // raise == move DOM-later
  });

  $('b-lower').addEventListener('click', function () {
    if (!selected) return;
    var prev = selected.previousElementSibling;
    while (prev && !prev.classList.contains('el')) prev = prev.previousElementSibling;
    if (!prev) return;
    pushUndo(snapshot());
    stage.insertBefore(selected, prev);
  });

  $('b-del').addEventListener('click', deleteSelected);
  $('b-dup').addEventListener('click', duplicateSelected);
  $('b-undo').addEventListener('click', undo);
  $('b-redo').addEventListener('click', redo);

  function deleteSelected() {
    if (!selected) return;
    // BEFORE the removal. The snapshot IS the thing we go back to -- taken afterwards it would
    // record the stage without the element, and Delete would become permanent with extra steps.
    pushUndo(snapshot());
    var el = selected;
    // select(null) drops the alignment set too (see select()) -- if `el` was ALSO a multi member
    // (shift+click toggles independently of `selected`, so the two sets can overlap), this is what
    // keeps the about-to-be-removed node from being left behind in `multi`.
    select(null);
    el.remove();
    setStatus('Deleted. (Ctrl+Z restores it.)');
  }

  function duplicateSelected() {
    if (!selected) return;
    var s = read(selected);
    s.id = nextId(); // a NEW id -- validate.py rejects duplicates
    var OFFSET = 8;
    if (s.type === 'connector') {
      s.x1 += OFFSET; s.y1 += OFFSET; s.x2 += OFFSET; s.y2 += OFFSET;
    } else {
      s.x += OFFSET; s.y += OFFSET;
    }
    var legal = applyConstraints(s, { alt: true });
    if (!legal) { flashBlocked(selected); setStatus('The copy would not fit legally.'); return; }

    // The judge has spoken and the copy WILL land, so only NOW is this a step. Pushing before the
    // legality check would leave a no-op undo behind every refused duplicate.
    pushUndo(snapshot());
    var copy = addEl(makeEl(legal));
    var srcBody = selected.querySelector('.txt .body');
    var dstBody = copy.querySelector('.txt .body');
    if (srcBody && dstBody) dstBody.innerHTML = srcBody.innerHTML;
    select(copy);
    setStatus('Duplicated as ' + legal.id + '.');
  }

  /* --------------------------------------------------------------- alignment (Phase 6) --
   *
   * Operates on selectionSet() -- `selected` plus whatever Shift+Click has added to `multi` -- and
   * on NOTHING ELSE measured: bboxOf() reuses elementBBox(), the exact same rotated-AABB function
   * the judge itself uses, over read()'s state. Not the DOM: this stays on the state -> CSS side of
   * the Prime Directive same as every other mutation here.
   *
   * Translating an element's x/y (or a connector's endpoints) by a fixed (dx, dy) translates its
   * rotated bounding box by the same (dx, dy) -- rotation is about the box's own (also translating)
   * centre, so this is exact for a rotated shape too, not an approximation that only happens to work
   * unrotated.
   */
  function bboxOf(el) { return elementBBox(read(el)); }

  function alignSelection(mode) {
    var set = selectionSet();
    if (set.length < 2) return;
    var boxes = set.map(bboxOf);
    var minX = Math.min.apply(null, boxes.map(function (b) { return b[0]; }));
    var maxX = Math.max.apply(null, boxes.map(function (b) { return b[2]; }));
    var minY = Math.min.apply(null, boxes.map(function (b) { return b[1]; }));
    var maxY = Math.max.apply(null, boxes.map(function (b) { return b[3]; }));

    beginTx(); // one undo step for the whole alignment, exactly like a single drag gesture
    set.forEach(function (el, i) {
      var s = read(el);
      var b = boxes[i];
      var dx = 0, dy = 0;
      switch (mode) {
        case 'left':    dx = minX - b[0]; break;
        case 'right':   dx = maxX - b[2]; break;
        case 'centerX': dx = (minX + maxX) / 2 - (b[0] + b[2]) / 2; break;
        case 'top':     dy = minY - b[1]; break;
        case 'bottom':  dy = maxY - b[3]; break;
        case 'centerY': dy = (minY + maxY) / 2 - (b[1] + b[3]) / 2; break;
      }
      if (!dx && !dy) return;
      // Reject-and-hold, same as a drag: commit() may refuse ONE element (e.g. the shift would
      // cross into a reserved region) without aborting the alignment for the others.
      if (s.type === 'connector') {
        commit(el, { x1: s.x1 + dx, y1: s.y1 + dy, x2: s.x2 + dx, y2: s.y2 + dy }, { alt: true });
      } else {
        commit(el, { x: s.x + dx, y: s.y + dy }, { alt: true });
      }
    });
    endTx();
  }

  [
    ['b-align-left', 'left'], ['b-align-right', 'right'], ['b-align-center-x', 'centerX'],
    ['b-align-top', 'top'], ['b-align-bottom', 'bottom'], ['b-align-center-y', 'centerY'],
  ].forEach(function (pair) {
    $(pair[0]).addEventListener('click', function () { alignSelection(pair[1]); });
  });

  /* Reflect the selection into the property panel -- and, now, decide whether there IS one.
   *
   * The panel is WRITTEN FROM the element's dataset and read back only as an edit. It holds no
   * state of its own, which is why showing and hiding it is safe: there is nothing in it to lose.
   *
   * It is hidden with nothing selected because a panel of controls that patch nothing is a panel
   * that lies -- every one of these inputs was, in Phase 1B, live and inert at the same time.
   */
  function syncProps() {
    var s = selected ? read(selected) : null;

    // Phase 6: the alignment set is independent of `selected` (see `var multi` above) -- it can be
    // non-empty (or even the whole reason the panel is showing) with nothing "selected" at all, so
    // its own group is driven here rather than folded into the data-for scoping below, which only
    // ever runs once a SINGLE element is selected.
    var mset = selectionSet();
    var showAlign = mset.length >= 2;
    $('align-group').hidden = !showAlign;
    if (showAlign) $('align-count').textContent = String(mset.length);

    props.hidden = !s && !showAlign;
    $('p-head').hidden = !s;
    $('arrange-group').hidden = !s;

    if (!s) {
      // Nothing PLAIN-selected: every per-type section is irrelevant (there is no single element's
      // dataset to show), whether or not an alignment-only multi-selection is showing above.
      var noneScoped = props.querySelectorAll('[data-for]');
      for (var n = 0; n < noneScoped.length; n++) noneScoped[n].hidden = true;
      setStatus(showAlign ? mset.length + ' element(s) selected for alignment.' : 'Ready.');
      return;
    }

    var cat = s.type === 'connector' ? 'connector' : isMediaType(s.type) ? 'media' : 'shape';

    /* Show only the controls this type actually HAS. The IR gives a connector no fill, no text and
     * no rotation, and a media element (image/video) no fill/stroke/text/rotation EITHER (the
     * renderer never draws them for a picture or a video) -- offering any of those would be
     * offering a property that cannot be serialized or that silently does nothing, and the JS
     * guards (`if (isConnector() || isMedia()) return`) would eat the edit either way. A control
     * that does nothing when you use it is worse than one that is not there. `data-for` may name
     * more than one category (space-separated, e.g. "shape connector" on the Line group) -- shown
     * whenever the CURRENT category is among them. */
    var scoped = props.querySelectorAll('[data-for]');
    for (var i = 0; i < scoped.length; i++) {
      var want = scoped[i].getAttribute('data-for').split(/\s+/);
      scoped[i].hidden = want.indexOf(cat) < 0;
    }

    $('p-what').textContent = s.type;
    $('p-which').textContent = s.id;

    if (cat === 'connector') {
      $('p-stroke').value = s.color; // a connector's colour lives on the STROKE control
      $('p-stroke-w').value = s.width;
      $('p-kind').value = s.kind;
      $('p-arrow').value = s.arrow;
    } else if (cat === 'media') {
      // No fill/stroke/text/rotation control is visible for this category (scoped away above), so
      // there is nothing of this type's own to populate here.
    } else {
      $('p-fill').value = s.fill || BRAND_RED;
      $('p-fill-alpha').value = s.fillAlpha;
      $('p-fill-alpha-out').textContent = Math.round(s.fillAlpha) + '%';
      $('p-stroke').value = s.strokeColor || '#FFFFFF';
      $('p-stroke-w').value = s.strokeWidth;
      $('p-border-1pt').checked = s.strokeColor === '#000000' && s.strokeWidth === 1;
      $('p-color').value = s.color;
      $('p-size').value = s.size;
      $('p-bold').setAttribute('aria-pressed', String(!!s.bold));
      $('p-italic').setAttribute('aria-pressed', String(!!s.italic));
      $('p-align').value = s.align;
      $('p-valign').value = s.valign;
      $('p-rot').value = Math.round(s.rot || 0);
      $('p-rot-out').textContent = Math.round(s.rot || 0) + '°';
    }
    setStatus(s.id + ' — ' + s.type);
  }

  /* ------------------------------------------------------------------------------ the keyboard */

  function editingText(t) {
    return t && (t.isContentEditable || t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA');
  }

  /* --------------------------------------------------------------------- copy / paste (Phase 6) --
   *
   * An IN-MEMORY clipboard, deliberately separate from the OS clipboard pasteGemJSON() (above)
   * already reads via navigator.clipboard -- that one carries a whole DECK from an external chat UI
   * and goes through loadIR(); this one carries a handful of ELEMENTS between two points in this
   * same tab and is never serialized, so there is no IR round trip to reuse and no reason to ask
   * the browser for clipboard permission over it.
   */
  var clipboard = null; // Array<{state, html}> | null -- never touches navigator.clipboard

  function copySelection() {
    var set = selectionSet();
    if (!set.length) return;
    clipboard = set.map(function (el) {
      var body = el.querySelector('.txt .body');
      return { state: read(el), html: body ? body.innerHTML : null };
    });
    setStatus('Copied ' + clipboard.length + ' element(s).');
  }

  function pasteClipboard() {
    if (!clipboard || !clipboard.length) return;
    var OFFSET = 20; // "x + 20, y + 20"
    var before = snapshot();
    var pasted = [];
    clipboard.forEach(function (rec) {
      var s = {};
      for (var k in rec.state) s[k] = rec.state[k];
      s.id = nextId(); // a NEW id -- validate.py rejects duplicates, same as duplicateSelected()
      if (s.type === 'connector') {
        s.x1 += OFFSET; s.y1 += OFFSET; s.x2 += OFFSET; s.y2 += OFFSET;
      } else {
        s.x += OFFSET; s.y += OFFSET;
      }
      // Best-effort, per element, exactly like duplicateSelected(): a paste that would land one
      // copy on a reserved region skips THAT element rather than refusing the whole paste (unlike
      // loadIR()/restore(), which are all-or-nothing because they replace the ENTIRE stage -- a
      // paste only ever adds to it, so there is no half-imported deck to protect against here).
      var legal = applyConstraints(s, { alt: true });
      if (!legal) return;
      var el = makeEl(legal);
      addEl(el);
      if (rec.html !== null) {
        var body = el.querySelector('.txt .body');
        if (body) body.innerHTML = rec.html;
      }
      pasted.push(el);
    });
    if (!pasted.length) { setStatus('Paste would not fit legally here.'); return; }
    pushUndo(before); // one step for the whole paste
    clearMulti();
    // `multi` populated BEFORE select(): select()'s own syncProps() call is what shows the Align
    // group, and it must see the full set already in place to report the right count immediately.
    for (var i = 0; i < pasted.length - 1; i++) {
      multi.push(pasted[i]);
      pasted[i].classList.add('multi-selected');
    }
    select(pasted[pasted.length - 1]);
    setStatus('Pasted ' + pasted.length + ' element(s).');
  }

  window.addEventListener('keydown', function (ev) {
    /* UNDO/REDO FIRST, and deliberately in FRONT of the editingText() guard.
     *
     * The property panel is made of <input>s, so an undo that stopped working while the focus was
     * still in the size box -- which is exactly where the focus IS, right after the edit you want to
     * undo -- would be an undo nobody trusts.
     *
     * The ONE exception is a live contenteditable. Inside the text, the browser's own undo is
     * per-keystroke and is what a user expects Ctrl+Z to do there; ours is per-session and would
     * throw away the whole paragraph. So we stand back and let it run. The snapshot taken when the
     * caret went in still makes the edit a single step from OUTSIDE, once the text is closed, which
     * is the granularity the stage wants anyway.
     */
    var k = String(ev.key || '').toLowerCase();
    if ((ev.ctrlKey || ev.metaKey) && (k === 'z' || k === 'y') &&
        !(ev.target && ev.target.isContentEditable)) {
      ev.preventDefault();
      if (k === 'y' || ev.shiftKey) redo(); else undo(); // Ctrl+Y and Ctrl+Shift+Z both redo
      return;
    }

    if (editingText(ev.target)) return;

    if (ev.key === 'Delete' || ev.key === 'Backspace') {
      if (selected) { ev.preventDefault(); deleteSelected(); }
      return;
    }
    if ((ev.ctrlKey || ev.metaKey) && (ev.key === 'd' || ev.key === 'D')) {
      ev.preventDefault();
      duplicateSelected();
      return;
    }
    if ((ev.ctrlKey || ev.metaKey) && (ev.key === 'c' || ev.key === 'C')) {
      if (selected || multi.length) { ev.preventDefault(); copySelection(); }
      return;
    }
    if ((ev.ctrlKey || ev.metaKey) && (ev.key === 'v' || ev.key === 'V')) {
      if (clipboard && clipboard.length) { ev.preventDefault(); pasteClipboard(); }
      return;
    }
    if (ev.key === 'Escape') { if (multi.length) clearMulti(); select(null); }
  });

  // Escape closes the text without deselecting -- the caret is inside, so the handler above is not
  // reached (editingText() short-circuits it).
  window.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && editingText(ev.target)) {
      stopEditing();
      if (ev.target.blur) ev.target.blur();
    }
  });

  // Enter in the TITLE inserts a line break, never a new block. The title is a STRING; a <div> in
  // it would be flattened to "\n" anyway, and a <br> keeps the flex box laying out as one line run.
  titleField.addEventListener('keydown', function (ev) {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      document.execCommand('insertLineBreak');
    }
  });

  // The title is part of the deck, so it is part of the snapshot, so it is undoable -- one step per
  // visit to the field, on the same session grouping the element text uses.
  titleField.addEventListener('focus', beginTx);
  titleField.addEventListener('input', function () { noteChange(); });
  titleField.addEventListener('blur', endTx);

  /* ---------------------------------------------------------------------------------- exports */

  function download(blob, filename) {
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function safeStem() {
    var t = titleString().replace(/[\\/:*?"<>|\r\n\t]+/g, ' ').trim();
    return t.slice(0, 60) || 'deck';
  }

  /* View & Copy JSON Notepad Modal */
  function showJsonModal() {
    if (!CONTEXT) return;
    var ir = serialize();
    $('json-modal-text').value = JSON.stringify(ir, null, 2);
    $('json-modal').removeAttribute('hidden');
  }
  function hideJsonModal() {
    $('json-modal').setAttribute('hidden', 'true');
  }
  if ($('b-view-json')) $('b-view-json').addEventListener('click', showJsonModal);
  if ($('b-close-json-modal')) $('b-close-json-modal').addEventListener('click', hideJsonModal);
  if ($('b-close-json-modal-btn')) $('b-close-json-modal-btn').addEventListener('click', hideJsonModal);
  if ($('b-copy-json-modal')) {
    $('b-copy-json-modal').addEventListener('click', function () {
      var text = $('json-modal-text').value;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(function () {
          setStatus('JSON copied to clipboard!');
        }).catch(function () {
          $('json-modal-text').select();
          document.execCommand('copy');
          setStatus('JSON copied to clipboard!');
        });
      } else {
        $('json-modal-text').select();
    document.execCommand('copy');
        setStatus('JSON copied to clipboard!');
      }
    });
  }

  /* Multi-Agent Live Log modal (Phase 2/3). Polls /api/log once a second WHILE OPEN only -- the
     interval is created in showLogModal() and cleared in hideLogModal(), never running in the
     background with the modal hidden. */
  var logPollTimer = null;

  function showLogModal() {
    $('log-modal').removeAttribute('hidden');
    pollLog();
    logPollTimer = setInterval(pollLog, 1000);
  }
  function hideLogModal() {
    $('log-modal').setAttribute('hidden', 'true');
    if (logPollTimer) {
      clearInterval(logPollTimer);
      logPollTimer = null;
    }
  }
  async function pollLog() {
    try {
      var res = await fetch('/api/log');
      if (!res.ok) return;  // a transient server error mid-poll isn't worth a warning banner
      var data = await res.json();
      if ($('log-modal-text')) {
        $('log-modal-text').textContent = data.log || data.error || 'Waiting for logs...';
        $('log-modal-text').scrollTop = $('log-modal-text').scrollHeight;
      }
    } catch (e) {
      // network hiccup between ticks -- next tick tries again
    }
  }
  if ($('b-view-log')) $('b-view-log').addEventListener('click', showLogModal);
  if ($('b-close-log-modal')) $('b-close-log-modal').addEventListener('click', hideLogModal);
  if ($('log-modal')) {
    $('log-modal').addEventListener('click', function (ev) {
      // click-outside-to-close: only the overlay backdrop itself, not a click that bubbled up
      // from something inside .modal-box.
      if (ev.target === $('log-modal')) hideLogModal();
    });
  }

  /* -------------------------------------------------------- Local Save Directories & File System Access API */
  var jsonDirHandle = null;
  var exportDirHandle = null;
  var targetPptxHandle = null;

  async function verifyPermission(fileHandle, readWrite) {
    var options = {};
    if (readWrite) {
      options.mode = 'readwrite';
    }
    if ((await fileHandle.queryPermission(options)) === 'granted') {
      return true;
    }
    if ((await fileHandle.requestPermission(options)) === 'granted') {
      return true;
    }
    return false;
  }

  if ($('b-set-dir-json')) {
    $('b-set-dir-json').addEventListener('click', async function () {
      try {
        jsonDirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
        $('label-dir-json').textContent = jsonDirHandle.name;
        $('label-dir-json').style.color = '#107c10';
      } catch (e) {
        console.warn('Set JSON Dir cancelled or failed', e);
      }
    });
  }

  if ($('b-set-dir-export')) {
    $('b-set-dir-export').addEventListener('click', async function () {
      try {
        exportDirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
        $('label-dir-export').textContent = exportDirHandle.name;
        $('label-dir-export').style.color = '#107c10';
      } catch (e) {
        console.warn('Set Export Dir cancelled or failed', e);
      }
    });
  }

  if ($('b-set-dir-target')) {
    $('b-set-dir-target').addEventListener('click', async function () {
      try {
        var opts = {
          types: [{
            description: 'PowerPoint Presentation',
            accept: {'application/vnd.openxmlformats-officedocument.presentationml.presentation': ['.pptx']}
          }],
          excludeAcceptAllOption: true,
          multiple: false
        };
        var handles = await window.showOpenFilePicker(opts);
        if (handles && handles.length > 0) {
          targetPptxHandle = handles[0];
          $('label-dir-target').textContent = targetPptxHandle.name;
          $('label-dir-target').style.color = '#107c10';
        }
      } catch (e) {
        console.warn('Set Target PPT cancelled or failed', e);
      }
    });
  }

  async function saveToDirectory(blob, filename, dirHandle) {
    if (!dirHandle) return false;
    try {
      if (!(await verifyPermission(dirHandle, true))) {
        return false;
      }
      var fileHandle = await dirHandle.getFileHandle(filename, { create: true });
      var writable = await fileHandle.createWritable();
      await writable.write(blob);
      await writable.close();
      return true;
    } catch (e) {
      console.error('Failed to save to directory', e);
      return false;
    }
  }

  $('b-json').addEventListener('click', async function () {
    if (!CONTEXT) return;
    clearWarnings();
    var ir = serialize();
    var blob = new Blob([JSON.stringify(ir, null, 2)], { type: 'application/json' });
    var filename = safeStem() + '.json';
    if (jsonDirHandle) {
      var success = await saveToDirectory(blob, filename, jsonDirHandle);
      if (!success) download(blob, filename);
    } else {
      download(blob, filename);
    }
    setStatus('Downloaded JSON (' + ir.elements.length + ' element(s)).');
  });

  /* Phase 6: /api/export (JSON in, .pptx out) was renamed to /api/download and now takes
   * multipart/form-data -- an "ir" field carrying the SAME JSON serialize() always produced, plus
   * one form part per distinct image/video `src` the deck references. NO "Content-Type" header is
   * set here: fetch() computes the multipart boundary itself from the FormData body, and a
   * hand-set header would carry no boundary at all and the server would fail to parse the parts. */
  function mediaFor(ir) {
    var names = [];
    ir.elements.forEach(function (el) {
      if ((el.type === 'image' || el.type === 'video') && names.indexOf(el.src) < 0) names.push(el.src);
    });
    return names;
  }

  $('b-export').addEventListener('click', async function () {
    if (!CONTEXT) return;
    clearWarnings();
    var ir = serialize();

    // A src this session has no File for would 500 at the server (draw_image()/draw_video() raise
    // a ValueError app.py does not map to a 4xx) -- caught HERE, before the request, rather than
    // after a round trip to find out. Typically means the tab reloaded, or a loaded/pasted deck
    // named a file nothing here was ever uploaded for.
    var names = mediaFor(ir);
    var missing = names.filter(function (n) { return !window.uploadedMedia || !window.uploadedMedia[n]; });
    if (missing.length) {
      warn(
        'Cannot export — missing media file(s): ' + missing.join(', '),
        'This element references an image/video this browser tab no longer has the bytes for ' +
        '(a reload clears them). Re-add it with the Media buttons in the toolbar, or delete the ' +
        'element, then export again.'
      );
      setStatus('Export failed.');
      return;
    }

    setStatus('Exporting…');
    var form = new FormData();
    form.append('ir', JSON.stringify(ir));
    names.forEach(function (n) { form.append(n, window.uploadedMedia[n].file, n); });

    try {
      var res = await fetch('/api/download', { method: 'POST', body: form });
      if (!res.ok) {
        var data = {};
        try { data = await res.json(); } catch (e) { /* a non-JSON error body */ }
        if (res.status === 409) {
          warn('Stale payload — RELOAD the editor', data.detail ||
            'The template or the model space changed under you. The deck is never rescaled.');
        } else if (res.status === 422) {
          warn('The deck did not validate', data.detail); // the numbered list, verbatim
        } else {
          warn('Export failed (HTTP ' + res.status + ')', data.detail || res.statusText);
        }
        setStatus('Export failed.');
        return;
      }
      var blob = await res.blob();
      var filename = safeStem() + '.pptx';
      if (exportDirHandle) {
        var success = await saveToDirectory(blob, filename, exportDirHandle);
        if (!success) download(blob, filename);
      } else {
        download(blob, filename);
      }
      setStatus('Exported ' + ir.elements.length + ' element(s).');
    } catch (e) {
      warn('Could not reach the server', String(e));
      setStatus('Export failed.');
    }
  });

  if ($('b-export-html')) {
    $('b-export-html').addEventListener('click', async function () {
      if (!CONTEXT) return;
      clearWarnings();
      var ir = serialize();
      var names = mediaFor(ir);
      var missing = names.filter(function (n) { return !window.uploadedMedia || !window.uploadedMedia[n]; });
      if (missing.length) {
        warn('Cannot export HTML — missing media file(s)', 'Please re-add missing media.');
        return;
      }
      setStatus('Exporting HTML…');
      var form = new FormData();
      form.append('ir', JSON.stringify(ir));
      names.forEach(function (n) { form.append(n, window.uploadedMedia[n].file, n); });
      try {
        var res = await fetch('/api/export_html', { method: 'POST', body: form });
        if (!res.ok) {
          setStatus('HTML Export failed.');
          return;
        }
        var blob = await res.blob();
        var filename = safeStem() + '.html';
        if (exportDirHandle) {
          var success = await saveToDirectory(blob, filename, exportDirHandle);
          if (!success) download(blob, filename);
        } else {
          download(blob, filename);
        }
        setStatus('Exported HTML (' + ir.elements.length + ' element(s)).');
      } catch (e) {
        warn('Could not reach the server', String(e));
        setStatus('HTML Export failed.');
      }
    });
  }

  if ($('b-append-slide')) {
    $('b-append-slide').addEventListener('click', async function () {
      if (!CONTEXT) return;
      if (!targetPptxHandle) {
        warn('Target PPTX is not set', 'Please select a Target PPT File (Dir 3) in Local Save Directories first.');
        return;
      }
      clearWarnings();
      var ir = serialize();
      var names = mediaFor(ir);
      var missing = names.filter(function (n) { return !window.uploadedMedia || !window.uploadedMedia[n]; });
      if (missing.length) {
        warn('Cannot append — missing media file(s)', 'Please re-add missing media.');
        return;
      }
      setStatus('Appending slide to Target PPTX…');
      try {
        var file = await targetPptxHandle.getFile();
        var buf = await file.arrayBuffer();
        var base64Bytes = btoa(new Uint8Array(buf).reduce((data, byte) => data + String.fromCharCode(byte), ''));
        if (!ir.target) ir.target = {};
        ir.target.target_pptx_b64 = base64Bytes;

        var form = new FormData();
        form.append('ir', JSON.stringify(ir));
        names.forEach(function (n) { form.append(n, window.uploadedMedia[n].file, n); });

        var res = await fetch('/api/append_slide', { method: 'POST', body: form });
        if (!res.ok) {
          var data = {};
          try { data = await res.json(); } catch (e) { }
          warn('Append failed (HTTP ' + res.status + ')', data.detail || res.statusText);
          setStatus('Append failed.');
          return;
        }
        var blob = await res.blob();
        var writable = await targetPptxHandle.createWritable();
        await writable.write(blob);
        await writable.close();
        setStatus('Appended slide to ' + targetPptxHandle.name + '.');
      } catch (e) {
        warn('Failed to append slide', String(e));
        setStatus('Append failed.');
      }
    });
  }

  /* Load JSON — a stretch goal, and the other half of the Gate 4 round trip. */
  $('b-load').addEventListener('click', function () { $('f-load').click(); });

  $('f-load').addEventListener('change', async function () {
    var file = this.files && this.files[0];
    if (!file) return;
    this.value = '';
    clearWarnings();

    var ir;
    try {
      ir = JSON.parse(await file.text());
    } catch (e) {
      warn('That file is not JSON', String(e));
      return;
    }

    // Taken HERE, and pushed HERE, and not inside loadIR(). loadIR() is lifted out of this file BY
    // NAME and executed in Node by tests/canvas/test_app.py (Gate 4b) against a stubbed stage; a
    // call to snapshot() from inside it would be a ReferenceError in that harness -- a green rule
    // failing in the test that proves it. The import is one undo step either way, and the caller is
    // the honest place to say so: only the caller knows whether loadIR() actually accepted the file.
    var before = snapshot();
    try {
      loadIR(ir);
      pushUndo(before); // it took: replacing the whole deck is ONE step, and it is reversible
    } catch (e) {
      // The stage is UNCHANGED and we may say so, because loadIR() judges the whole file before it
      // touches anything. This message would have been a lie before that was true. Nothing was
      // pushed, either -- a refused import must not cost an undo step.
      warn('That deck was not loaded — the stage is unchanged', String(e.message || e));
      setStatus('Load refused.');
    }
  });

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
  function modelLabel(id) {
    if (!CONTEXT || !CONTEXT.models || !CONTEXT.models.length) return id;
    for (var i = 0; i < CONTEXT.models.length; i++) {
      if (CONTEXT.models[i].id === id) return CONTEXT.models[i].name;
    }
    return id;
  }

  if ($('p-review')) {
    $('p-review').addEventListener('change', function () {
      if ($('reviewer-wrapper')) {
        $('reviewer-wrapper').style.display = this.checked ? 'inline-block' : 'none';
      }
    });
  }

  async function generate() {
    if (!CONTEXT) return;   // the server is unreachable and the button is already disabled

    var prompt = $('p-prompt').value.trim();
    var modelSel = $('p-model');
    var selectedModel = modelSel ? modelSel.value : (CONTEXT && CONTEXT.default_model);
    var isReview = $('p-review') ? $('p-review').checked : false;
    var reviewerModel = $('p-reviewer-model') ? $('p-reviewer-model').value : 'gpt-5.6-terra';

    if (!prompt) {
      setStatus('Type a prompt first.');
      $('p-prompt').focus();
      return;
    }

    clearWarnings();
    setBusy(true);
    setStatus(isReview ? 'Generating & Reviewing…' : 'Generating…');
    try {
      var res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        // #p-model (index.html) is the server's own MODEL_PROFILES allowlist, echoed back into the
        // request. The server, not the client, is the authority on what a profile id maps to
        // downstream. JSON.stringify({ prompt: prompt })
        body: JSON.stringify({
          prompt: prompt,
          model: selectedModel,
          review: isReview,
          reviewer_model: reviewerModel
        }),
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
        var live = CONTEXT && CONTEXT.mode === 'live';
        if (ir._meta && ir._meta.review_applied === false) {
          setStatus('Review pass failed or produced invalid IR; original draft used.');
        } else {
          setStatus('Generated ' + (ir.elements || []).length + ' element(s)' +
                    (live ? ' from ' + modelLabel(selectedModel) + (isReview ? ' (Reviewed by ' + reviewerModel + ')' : '') + '.'
                          : ' — MOCK payload; no model was called.'));
        }
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
    var modelSel = $('p-model');
    if (modelSel) modelSel.disabled = on;
  }

  $('b-generate').addEventListener('click', generate);

  /* Strip a ```json ... ``` fence a Web-Gem paste often carries. The backend tolerates the same
   * wrapper; keeping both lenient means a copy straight out of the chat UI Just Works. */
  function stripFence(text) {
    var t = String(text).trim();
    if (t.indexOf('```') === 0) {
      t = t.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim();
    }
    return t;
  }

  /* WEB GEM WORKFLOW (Phase 4). Read the clipboard, parse it, hand it to loadIR() — the ONE door
   * into the stage, the same judge a file import and the live author go through. No validation of
   * its own. The snapshot/pushUndo pair is the file-import path's, for the same reason: this
   * replaces the whole deck (one undo step) and only the caller knows loadIR() accepted it. */
  async function pasteGemJSON() {
    clearWarnings();
    if (!navigator.clipboard || !navigator.clipboard.readText) {
      warn('The clipboard is not available',
        'This browser will not hand a script the clipboard. Use “Load JSON” to open a file instead.');
      return;
    }
    var text;
    try {
      text = await navigator.clipboard.readText();
    } catch (e) {
      warn('Could not read the clipboard',
        'The browser refused clipboard access — grant this page clipboard permission, or use ' +
        '“Load JSON”.\n\n' + String(e));
      return;
    }
    if (!text || !text.trim()) {
      warn('The clipboard is empty', 'Copy the JSON from your chat first, then press Paste Gem JSON.');
      return;
    }
    var ir;
    try {
      ir = JSON.parse(stripFence(text));
    } catch (e) {
      warn('The clipboard is not JSON',
        'What was copied is not a canvas-ir/1 deck. Copy only the JSON block.\n\n' + String(e));
      return;
    }
    var before = snapshot();
    try {
      loadIR(ir);        // the SAME gate the file import and the live author go through
      pushUndo(before);  // it took: replacing the whole deck is ONE step, and it is reversible
      setStatus('Pasted ' + (ir.elements || []).length + ' element(s) from the clipboard.');
    } catch (e) {
      warn('That deck was refused — the stage is unchanged', String(e.message || e));
      setStatus('Paste refused.');
    }
  }

  $('b-paste').addEventListener('click', pasteGemJSON);

  /* The mock/live badge. The MODE comes from /api/context, never inferred from behaviour. */
  function applyMode(mode, model) {
    var tag = $('ai-mode');
    var hint = $('ai-hint');
    if (mode === 'live') {
      if (tag) {
        tag.textContent = 'live';
        tag.classList.add('live');
        tag.title = model ? ('Model: ' + model) : 'A live model is called';
      }
      if (hint) {
        hint.innerHTML = 'Calls the configured model and <strong>replaces the stage</strong> with ' +
          'its draft (Ctrl+Z brings yours back). The draft is judged like any import.';
      }
    } else if (tag) {
      tag.textContent = 'mock';
      tag.classList.remove('live');
      tag.title = 'No model is called';
    }
  }

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

  /* An IR element -> editor state.
   *
   * It NEVER throws and it NEVER repairs, and both halves of that are load-bearing.
   *
   * Not throwing is what lets the gate judge the WHOLE file and report every bad element at once,
   * instead of dying on the first one. `text`, `paragraphs`, `runs` and the first run are each
   * optional AND each hand-editable, so `text.paragraphs[0].runs[0]` -- which is what this used to
   * be -- is a TypeError in any file someone deleted a line from.
   *
   * Not repairing is what keeps the judge honest: a missing coordinate must arrive at
   * illegalReason() still missing, so that it is REFUSED, rather than quietly defaulted to 0 and
   * drawn somewhere the user never put it.
   */
  function stateFromIR(e) {
    if (!e || typeof e !== 'object') return { id: undefined, type: undefined };

    if (e.type === 'connector') {
      var cd = DEFAULTS.connector;
      return {
        id: e.id, type: 'connector',
        x1: e.x1, y1: e.y1, x2: e.x2, y2: e.y2,
        kind: e.kind || cd.kind,
        arrow: e.arrow || cd.arrow,
        color: e.color || cd.color,
        width: typeof e.width === 'number' ? e.width : cd.width,
      };
    }

    // Media (Phase 6): geometry + src, nothing else -- no fill/stroke/text/rotation round-trips
    // for an image/video (see toIR()). Checked by literal string, not isMediaType(): this function
    // is lifted out of this file BY NAME and run in Node (tests/canvas/test_app.py), and a call out
    // to a helper the harness does not also lift is a ReferenceError in the gate, not in the code.
    if (e.type === 'image' || e.type === 'video') {
      return {
        id: e.id, type: e.type,
        x: e.x, y: e.y, w: e.w, h: e.h,
        rot: e.rotation === undefined || e.rotation === null ? 0 : e.rotation,
        src: typeof e.src === 'string' ? e.src : '',
      };
    }

    var text = e.text && typeof e.text === 'object' ? e.text : {};
    var paras = Array.isArray(text.paragraphs) ? text.paragraphs : [];
    var runs0 = paras[0] && Array.isArray(paras[0].runs) ? paras[0].runs : [];
    var first = runs0[0] && typeof runs0[0] === 'object' ? runs0[0] : {};
    var def = e.type === 'textbox' ? DEFAULTS.textbox : DEFAULTS.shape;
    var stroke = e.stroke && typeof e.stroke === 'object' ? e.stroke : null;

    /* The element's bold/italic flags are a SUMMARY of the runs: on only when EVERY run is bold.
     *
     * Reading them off the FIRST run -- the way size and color are read -- would be wrong here, and
     * destructively so. The flag is OR-ed into every run on the way back out (normalizeText), so
     * "the first run is bold" would mean a deck with one bold word in a plain sentence reloads with
     * the flag on, and re-exports with the WHOLE sentence bold. A round trip must not change the
     * deck. Mixed runs therefore summarise to OFF, and their own <b>/<i> tags -- which
     * paragraphsToHTML() writes -- carry the per-run bold instead. Nothing is lost either way.
     *
     * Inlined rather than factored into a helper on purpose: this function is lifted out by name and
     * run in Node by tests/canvas/test_app.py, and a call to a helper that the harness does not also
     * lift is a ReferenceError in the gate rather than a failure in the code.
     */
    var nRuns = 0, nBold = 0, nItalic = 0;
    for (var pi = 0; pi < paras.length; pi++) {
      var prs = paras[pi] && Array.isArray(paras[pi].runs) ? paras[pi].runs : [];
      for (var ri = 0; ri < prs.length; ri++) {
        var r = prs[ri];
        if (!r || typeof r !== 'object') continue;
        nRuns += 1;
        if (r.bold) nBold += 1;
        if (r.italic) nItalic += 1;
      }
    }

    // Phase 6: split a #RRGGBBAA fill into its opaque colour and its alpha PERCENT (the inverse of
    // withAlpha() in toIR()) -- inlined rather than a shared helper for the same reason the
    // bold/italic summary above is: stateFromIR() is lifted by name into a harness that does not
    // also lift withAlpha()/hex2(), and a call out to either would be a ReferenceError there, not a
    // failure in the code. A plain #RRGGBB (or no fill at all) is unaffected: fillAlpha is 100.
    var fillRaw = typeof e.fill === 'string' ? e.fill : '';
    var fillColor = fillRaw;
    var fillAlpha = 100;
    if (/^#[0-9A-Fa-f]{8}$/.test(fillRaw)) {
      fillColor = fillRaw.slice(0, 7);
      fillAlpha = Math.round((parseInt(fillRaw.slice(7, 9), 16) / 255) * 100);
    }

    return {
      id: e.id, type: e.type,
      x: e.x, y: e.y, w: e.w, h: e.h,
      // Absent or null rotation is 0. A rotation of "45" is NOT 45: it stays a string, and the judge
      // refuses it -- exactly as validate.py::_has_readable_geometry does on the other side.
      rot: e.rotation === undefined || e.rotation === null ? 0 : e.rotation,
      fill: fillColor,
      fillAlpha: fillAlpha,
      strokeColor: (stroke && stroke.color) || '',
      strokeWidth: stroke && typeof stroke.width === 'number' ? stroke.width : 1,
      // A textless element carries no run to learn from, so fall back to the DEFAULT FOR ITS
      // TYPE -- black for a textbox, white for a shape. Defaulting both to white would hand a
      // reloaded textbox white-on-nothing text.
      size: first.size || def.size,
      color: first.color || def.color,
      align: text.align || def.align,
      valign: text.valign || def.valign,
      bold: nRuns > 0 && nBold === nRuns,
      italic: nRuns > 0 && nItalic === nRuns,
    };
  }

  /* THE SECOND CALLER OF THE JUDGE, and the reason the judge exists as its own function.
   *
   * ALL OR NOTHING, and in this order: judge every element FIRST, touch the stage SECOND.
   *
   * A file is not a trusted input just because this editor may have written it -- it is a
   * hand-editable text file, and the moment one of its elements could come to rest on the logo,
   * "the reserved regions are strictly enforced" stopped being a true sentence. They were enforced
   * against the mouse and not against a file.
   *
   * The ORDER is the other half of the fix, and it is not cosmetic. This function used to clear the
   * stage and overwrite the title before it had looked at a single element, so a per-element check
   * bolted into the loop -- however correct that check was -- could only ever leave a half-imported
   * stage behind and the user's own deck already gone. "Reject the entire import" is not reachable
   * from inside that loop. It is reachable from here.
   */
  function loadIR(ir) {
    if (!ir || typeof ir !== 'object') throw new Error('that file does not contain a deck');
    if (ir.schema !== SCHEMA) throw new Error('schema is ' + ir.schema + ', expected ' + SCHEMA);
    if (!ir.canvas || ir.canvas.w !== CANVAS.w || ir.canvas.h !== CANVAS.h) {
      throw new Error('that deck was authored in a different model space; it is never rescaled');
    }
    var raw = ir.elements === undefined || ir.elements === null ? [] : ir.elements;
    if (!Array.isArray(raw)) throw new Error('elements is not a list');

    /* PASS 1 -- JUDGE. Nothing below this line has touched the stage, and nothing above it may. */
    var states = [];
    var problems = [];
    var seen = Object.create(null); // no prototype, so an id of "__proto__" is just a key
    for (var i = 0; i < raw.length; i++) {
      var s = stateFromIR(raw[i]);
      states.push(s);

      // The same label validate.py prints, so the editor's refusal and the backend's 422 read as
      // one voice rather than as two tools that happen to disagree with your file.
      var at = 'elements[' + i + '] (id "' + (typeof s.id === 'string' ? s.id : '?') +
               '", type "' + (typeof s.type === 'string' ? s.type : '?') + '")';

      var why = illegalReason(s);
      if (why) problems.push(at + ': ' + why);

      // Ids become shape NAMES in the .pptx and the round-trip suite finds shapes by name, so two
      // elements sharing one makes one of them unfindable. validate.py rejects it; so do we.
      if (typeof s.id !== 'string' || !s.id) {
        problems.push(at + ': has no id -- an id becomes the shape name in the .pptx');
      } else if (s.id in seen) {
        problems.push(at + ': duplicate id -- already used by elements[' + seen[s.id] + ']');
      } else {
        seen[s.id] = i;
      }
    }

    if (problems.length) {
      throw new Error(
        problems.length + ' element(s) in that file may not be placed on this stage, so NOTHING ' +
        'was loaded and the deck you had is untouched:\n' +
        problems.map(function (p, n) { return '  ' + (n + 1) + '. ' + p; }).join('\n')
      );
    }

    /* PASS 2 -- COMMIT. Every state is legal, so this cannot fail half-way through. */
    [].slice.call(stage.querySelectorAll(':scope > .el')).forEach(function (n) { n.remove(); });
    select(null);
    titleField.textContent = ir.title || '';

    for (var j = 0; j < states.length; j++) {
      var el = makeEl(states[j]);
      stage.appendChild(el); // array order IS z-order -- preserve the file's order exactly
      var body = el.querySelector('.txt .body');
      var txt = raw[j] && typeof raw[j].text === 'object' ? raw[j].text : null;
      if (body && txt) body.innerHTML = paragraphsToHTML(txt.paragraphs, states[j].color);
    }
    setStatus('Loaded ' + states.length + ' element(s).');
  }

  /* Runs are hand-editable too. A paragraph with no `runs`, or a run with no `t`, is a file someone
   * edited -- not a file we wrote -- and it must not be a TypeError. It used to be one, and it was
   * thrown AFTER the stage had already been cleared.
   */
  function paragraphsToHTML(paragraphs, defColor) {
    var list = Array.isArray(paragraphs) ? paragraphs : [];
    return list.map(function (p) {
      var runs = p && Array.isArray(p.runs) ? p.runs : [];
      var inner = runs.map(function (r) {
        if (!r || typeof r !== 'object') return '';
        var raw = r.t === undefined || r.t === null ? '' : r.t;
        var t = esc(raw).replace(/\n/g, '<br>');
        if (r.bold) t = '<b>' + t + '</b>';
        if (r.italic) t = '<i>' + t + '</i>';
        // A run with no colour inherits the element's, and it does so EXPLICITLY: normalizeText()
        // reads the colour back off this span on the way out, so leaving it empty would round-trip
        // the colour as the string "undefined" and lose it.
        return '<span style="color: ' + esc(r.color || defColor) + '">' + t + '</span>';
      }).join('');
      return '<div>' + inner + '</div>';
    }).join('');
  }

  /* -------------------------------------------------------------------------------- start-up */

  function disableExports(why) {
    $('b-export').disabled = true;
    $('b-json').disabled = true;
    if ($('b-view-json')) $('b-view-json').disabled = true;
    // The draft comes from the same server. Leaving it live would offer a button whose only possible
    // outcome is the banner the user is already reading.
    $('b-generate').disabled = true;
    setStatus(why);
  }

  async function loadContext() {
    try {
      var res = await fetch('/api/context');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      CONTEXT = await res.json();
      applyMode(CONTEXT.mode, CONTEXT.model);
    } catch (e) {
      CONTEXT = null;
      disableExports('Offline — export disabled.');
      warn(
        'Cannot reach the server — Export and Download JSON are disabled',
        'The template SHA comes from /api/context and is NEVER hard-coded here: a payload carrying ' +
        'a fabricated SHA is worse than no payload (the renderer would reject it with a 409, or ' +
        'worse, accept it against a template it was not authored for). Start the server with ' +
        '`python -m aippt.canvas.app` and reload.\n\n' + String(e)
      );
      return;
    }

    // The server is the authority on the model space too. If it disagrees with us, we are the
    // stale one, and we must not author a payload it will only reject.
    var c = CONTEXT.canvas || {};
    if (c.w !== CANVAS.w || c.h !== CANVAS.h || c.unit !== CANVAS.unit) {
      CONTEXT = null;
      disableExports('Model space mismatch — export disabled.');
      warn(
        'This editor and the server disagree about the model space',
        'The editor speaks ' + JSON.stringify(CANVAS) + ' and the server speaks ' +
        JSON.stringify(c) + '. A payload is NEVER rescaled. Hard-refresh the page; if it persists, ' +
        'the editor build is stale.'
      );
    }
  }

  async function checkFont() {
    await document.fonts.ready;
    if (!document.fonts.check('14pt "Century Gothic"')) {
      warn(
        'Century Gothic is not installed. This preview does NOT match what PowerPoint will render.',
        'Text metrics, wrapping and overflow on this stage are being measured in a substitute ' +
        'typeface. The exported deck will still ask for Century Gothic (latin) and 맑은 고딕 (EA), ' +
        'so what you see here is not what your audience will see. A preview that lies silently is ' +
        'worse than no preview.'
      );
    }
  }


  /* -------------------------------------------------------- Server Templates / Designs */

  async function fetchDesigns() {
    var select = $('p-designs');
    if (!select) return;
    try {
      var res = await fetch('/api/designs');
      if (!res.ok) return;
      var data = await res.json();
      var designs = data.designs || [];
      select.innerHTML = '';
      if (!designs.length) {
        var opt = document.createElement('option');
        opt.value = '';
        opt.textContent = '(none saved)';
        select.appendChild(opt);
      } else {
        var defaultOpt = document.createElement('option');
        defaultOpt.value = '';
        defaultOpt.textContent = 'Select a template...';
        select.appendChild(defaultOpt);
        designs.forEach(function (name) {
          var opt = document.createElement('option');
          opt.value = name;
          opt.textContent = name;
          select.appendChild(opt);
        });
      }
    } catch (e) {
      console.warn('Failed to fetch designs', e);
    }
  }

  async function saveDesign() {
    if (!CONTEXT) return;
    var nameInput = $('p-design-name');
    var name = nameInput ? nameInput.value.trim() : '';
    if (!name) {
      setStatus('Type a design name first.');
      if (nameInput) nameInput.focus();
      return;
    }
    clearWarnings();
    var ir = serialize();
    setStatus('Saving design "' + name + '"…');
    try {
      var res = await fetch('/api/designs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, ir: ir }),
      });
      if (!res.ok) {
        var data = {};
        try { data = await res.json(); } catch (e) { }
        warn('Save design failed (HTTP ' + res.status + ')', data.detail || res.statusText);
        setStatus('Save design failed.');
        return;
      }
      setStatus('Saved design "' + name + '".');
      if (nameInput) nameInput.value = '';
      await fetchDesigns();
    } catch (e) {
      warn('Could not reach the server', String(e));
      setStatus('Save design failed.');
    }
  }

  async function loadDesign() {
    if (!CONTEXT) return;
    var select = $('p-designs');
    var name = select ? select.value : '';
    if (!name) {
      setStatus('Select a template to load.');
      return;
    }
    clearWarnings();
    setStatus('Loading design "' + name + '"…');
    try {
      var res = await fetch('/api/designs/' + encodeURIComponent(name));
      if (!res.ok) {
        var data = {};
        try { data = await res.json(); } catch (e) { }
        warn('Load design failed (HTTP ' + res.status + ')', data.detail || res.statusText);
        setStatus('Load design failed.');
        return;
      }
      var ir = await res.json();
      var before = snapshot();
      try {
        loadIR(ir);
        pushUndo(before);
        setStatus('Loaded design "' + name + '".');
      } catch (e) {
        warn('That design was not loaded — the stage is unchanged', String(e.message || e));
        setStatus('Load refused.');
      }
    } catch (e) {
      warn('Could not reach the server', String(e));
      setStatus('Load design failed.');
    }
  }

  async function deleteDesign() {
    if (!CONTEXT) return;
    var select = $('p-designs');
    var name = select ? select.value : '';
    if (!name) {
      setStatus('Select a template to delete.');
      return;
    }
    clearWarnings();
    setStatus('Deleting design "' + name + '"…');
    try {
      var res = await fetch('/api/designs/' + encodeURIComponent(name), { method: 'DELETE' });
      if (!res.ok) {
        var data = {};
        try { data = await res.json(); } catch (e) { }
        warn('Delete design failed (HTTP ' + res.status + ')', data.detail || res.statusText);
        setStatus('Delete design failed.');
        return;
      }
      setStatus('Deleted design "' + name + '".');
      await fetchDesigns();
    } catch (e) {
      warn('Could not reach the server', String(e));
      setStatus('Delete design failed.');
    }
  }

  if ($('b-save-design')) $('b-save-design').addEventListener('click', saveDesign);
  if ($('b-load-design')) $('b-load-design').addEventListener('click', loadDesign);
  if ($('b-delete-design')) $('b-delete-design').addEventListener('click', deleteDesign);

  async function init() {
    // Emit <b>/<i> rather than styled spans. We handle both anyway, but tags are what the run model
    // actually wants.
    try { document.execCommand('styleWithCSS', false, false); } catch (e) { /* not fatal */ }

    setTool('select');
    setZoom(100);
    syncProps();    // nothing is selected, so this HIDES the panel rather than filling it
    syncHistory();  // ...and an empty stack disables Undo and Redo
    await loadContext();
    await checkFont();
    await fetchDesigns();
  }

  init();
})();

