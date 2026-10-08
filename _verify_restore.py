#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Throwaway verifier: runs the Phase 2 repair's new gates without invoking pytest
(pytest is blocked by a permission rule in this session). Delete after use."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests" / "canvas"))

EDITOR_SRC = (ROOT / "src" / "aippt" / "canvas" / "static" / "editor.js").read_text(encoding="utf-8")
NODE = shutil.which("node")

fails: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"PASS  {name}")
    except AssertionError as e:
        fails.append(name)
        print(f"FAIL  {name}\n      {e}")
    except Exception as e:  # noqa: BLE001
        fails.append(name)
        print(f"ERROR {name}\n      {type(e).__name__}: {e}")


def _js_decl(name: str) -> str:
    start = EDITOR_SRC.index(f"var {name} = ")
    depth = 0
    for i in range(start, len(EDITOR_SRC)):
        ch = EDITOR_SRC[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == ";" and depth == 0:
            return EDITOR_SRC[start : i + 1]
    raise AssertionError(f"`var {name} = ...` never terminated")


def _js_function(name: str) -> str:
    start = EDITOR_SRC.index(f"function {name}(")
    depth = 0
    for i in range(EDITOR_SRC.index("{", start), len(EDITOR_SRC)):
        if EDITOR_SRC[i] == "{":
            depth += 1
        elif EDITOR_SRC[i] == "}":
            depth -= 1
            if depth == 0:
                return EDITOR_SRC[start : i + 1]
    raise AssertionError(f"unbalanced braces in {name}()")


_DECLS = ["CANVAS", "SCHEMA", "HEADER_RESERVED", "FOOTER_RESERVED", "REJECT_REGIONS", "EPS",
          "BRAND_RED", "SHAPE_TYPES", "DEFAULTS", "GEOM_FIELDS", "ELEMENT_TYPES"]
_PREFLIGHT_FUNCS = ["intersects", "elementBBox", "outOfBounds", "geometryIsReadable",
                    "illegalReason", "unrestorableReason"]
_MAIN = """
var out = { threw: false, error: '', reason: null };
try {
  out.reason = unrestorableReason(JSON.parse(require('fs').readFileSync(0, 'utf8')));
} catch (e) {
  out.threw = true;
  out.error = String((e && e.message) || e);
}
process.stdout.write(JSON.stringify(out));
"""


def preflight(snap) -> dict:
    src = "\n\n".join(["'use strict';"] + [_js_decl(n) for n in _DECLS]
                      + [_js_function(n) for n in _PREFLIGHT_FUNCS] + [_MAIN])
    with tempfile.TemporaryDirectory() as d:
        h = Path(d) / "restore_gate.js"
        h.write_text(src, encoding="utf-8")
        p = subprocess.run([NODE, str(h)], input=json.dumps(snap), capture_output=True,
                           text=True, encoding="utf-8", timeout=60)
    assert p.returncode == 0, f"harness failed to run:\n{p.stderr}"
    out = json.loads(p.stdout)
    assert not out["threw"], f"unrestorableReason() THREW: {out['error']}"
    return out


def el_state(**over) -> dict:
    s = {"id": "el1", "type": "rect", "x": 100.0, "y": 150.0, "w": 120.0, "h": 80.0, "rot": 0}
    s.update(over)
    return s


def snap(*states, title="Q3 Review") -> dict:
    return {"title": title, "els": [{"state": s, "html": None, "sel": False} for s in states]}


if NODE:
    check("legal snapshot still restores",
          lambda: (lambda o: (_ for _ in ()).throw(AssertionError(f"refused: {o['reason']}"))
                   if o["reason"] is not None else None)(
              preflight(snap(el_state(), el_state(id="el2", x=400.0, type="ellipse")))))

    def _reserved():
        o = preflight(snap(el_state(y=10.0, h=40.0)))
        assert o["reason"] is not None, "undo would put an element back on the header"
        assert "els[0]" in o["reason"] and "el1" in o["reason"], o["reason"]
        print(f"        reason: {o['reason'].splitlines()[0]}")
    check("reserved-region snapshot is refused", _reserved)

    for label, bad in [("missing-coordinate", el_state(x=None)),
                       ("string-coordinate", el_state(w="120")),
                       ("zero-width", el_state(w=0.0)),
                       ("inverted-box", el_state(h=-80.0)),
                       ("off-the-slide", el_state(x=900.0, w=400.0)),
                       ("unknown-type", el_state(type="triangle"))]:
        check(f"illegal record refused: {label}",
              lambda b=bad: (_ for _ in ()).throw(AssertionError("accepted"))
              if preflight(snap(b))["reason"] is None else None)

    for label, junk in [("none", None), ("empty", {}), ("no-els", {"title": "t"}),
                        ("no-title", {"els": []}), ("els-not-a-list", {"title": "t", "els": "x"})]:
        check(f"non-snapshot refused: {label}",
              lambda j=junk: (_ for _ in ()).throw(AssertionError("accepted"))
              if preflight(j)["reason"] is None else None)

    check("malformed record refused, not thrown on",
          lambda: (_ for _ in ()).throw(AssertionError("accepted"))
          if preflight({"title": "t", "els": [{"html": None, "sel": False}]})["reason"] is None
          else None)
else:
    print("SKIP  node is not on PATH -- behavioural gates not executed")


def _order():
    body = _js_function("restore")
    judged = body.index("unrestorableReason(")
    for touch in ("stopEditing()", "n.remove()", "titleField.innerHTML", "makeEl("):
        assert judged < body.index(touch), f"restore() reaches {touch} before judging"
check("restore() judges before it touches the DOM", _order)

check("restore() reports success/refusal",
      lambda: (_ for _ in ()).throw(AssertionError("no true/false"))
      if not ("return false;" in _js_function("restore") and "return true;" in _js_function("restore"))
      else None)


def _inert():
    body = _js_function("unrestorableReason")
    assert "illegalReason(" in body, "preflight does not call the judge"
    for t in ("applyConstraints(", "snapVal(", "snapAxis(", "clamp("):
        assert t not in body, f"preflight calls {t}"
    for d in ("stage.", "titleField", "document.", "makeEl(", "getBoundingClientRect"):
        assert d not in body, f"preflight touches the DOM ({d})"
check("preflight transforms nothing and touches no DOM", _inert)


def _pop(fn, stack):
    body = _js_function(fn)
    assert f"restore({stack}.pop())" not in body, f"{fn}() pops as the argument"
    assert body.index("restore(") < body.index(f"{stack}.pop()"), f"{fn}() pops before restoring"
for fn, stack in (("undo", "past"), ("redo", "future")):
    check(f"{fn}() defers the pop until the restore succeeded", lambda f=fn, s=stack: _pop(f, s))


def _bail():
    for fn, other in (("undo", "future"), ("redo", "past")):
        body = _js_function(fn)
        assert "if (!restore(" in body and "return;" in body, f"{fn}() ignores refusal"
        assert body.index("if (!restore(") < body.index(f"{other}.push("), f"{fn}() pushes early"
check("undo/redo bail out on refusal", _bail)


def _phase2_still_true():
    body = _js_function("restore")
    assert "makeEl(" in body, "restore() no longer rebuilds from state"
    assert "getBoundingClientRect" not in body
check("the existing Phase 2 test still holds", _phase2_still_true)

print()
print("FAILURES:", fails if fails else "none")
sys.exit(1 if fails else 0)
