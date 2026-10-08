# Phase 0 Repair — Change Detail

Repairs the architectural violations Codex Critic raised against `src/aippt/canvas/pin.py`
(critic brief rule 3: "Verify `pin.py` contains exactly the three functions").

## Scope

Exactly one file was written:

- `src/aippt/canvas/pin.py`

No other file was touched. `calibrate.py`, `make_renderer_template.py`, `reference/template_pin.json`
and `HUMAN_VERIFICATION.md` are unchanged.

## The four fixes

### 1. `sha256_file()` removed, inlined into `verify_pin`

The chunked SHA-256 read now happens directly inside gate 1. The old body used
`iter(lambda: f.read(1 << 20), b"")`; the inlined version uses a walrus loop instead:

```python
digest = hashlib.sha256()
with tpl.open("rb") as f:
    while chunk := f.read(1 << 20):
        digest.update(chunk)
actual = digest.hexdigest()
```

This is deliberate. A `lambda` is a function object, and the constraint is "exactly three
functions and nothing else". Swapping the sentinel-`iter` idiom for `while chunk := ...` keeps
the streaming behaviour (1 MiB chunks, no whole-file read) while leaving literally no callable in
the module other than the three required ones.

### 2. `load_pin(path=PIN_PATH)` → `load_pin()`

Parameterless, reading the module-level `PIN_PATH` constant directly. The two error messages that
interpolated `path` now interpolate `PIN_PATH`.

Safe for the one existing caller: `calibrate.py:280` already calls `load_pin()` with no argument.

### 3. `_template_path()` removed, inlined at both call sites

`PROJECT_ROOT / pin["renderer_template"]["filename"]` is now written out in `verify_pin` and in
`open_renderer_template`. One duplicated expression, which is the price the three-function
constraint asks for.

### 4. `_verify_signature()` removed, inlined into `verify_pin`

The whole gate-2 body (slide/layout counts, slide dimensions, layout partname, placeholder idx
set, required media, and the placeholder-10 geometry check) now lives under the
`# --- Gate 2` banner inside `verify_pin`. Logic is byte-for-byte the same, including the
`layout.placeholders.get(TITLE_PH_IDX)` subtlety — on a *layout*, `placeholders[10]` is positional
and would raise `IndexError` (plan §6.3). That comment was carried over so the next reader does
not "simplify" it back into a bug.

## Resulting surface

```
class TemplatePinError(RuntimeError)     # not a function; calibrate.py imports it
def load_pin() -> dict[str, Any]
def verify_pin(pin: dict[str, Any]) -> None
def open_renderer_template(pin: dict[str, Any]) -> Presentation
```

plus imports, constants (`PROJECT_ROOT`, `PIN_PATH`, `PIN_VERSION`, `TITLE_PH_IDX`, `UNPINNED`,
`_REBUILD`), and the existing `if __name__ == "__main__"` self-check block that
`HUMAN_VERIFICATION.md:35` depends on (`python src/aippt/canvas/pin.py` → `pin OK: ...`). Neither
the class nor the `__main__` block defines a function, so both are consistent with the constraint.

## Behaviour preserved

No behavioural change was intended or made. Both gates still run in the same order, all
`TemplatePinError` messages are identical, and the module still never reads the source template.
`open_renderer_template` still calls `verify_pin` and still opens the package a second time to
hand it back, keeping `verify_pin() -> None` honest.

## Compatibility check performed

`calibrate.py:49-54` imports `TITLE_PH_IDX`, `TemplatePinError`, `load_pin`,
`open_renderer_template` from this module — all four survive the repair. Nothing anywhere imports
`sha256_file` from `pin.py`; `make_renderer_template.py:75` defines its own copy, so removing
pin's did not break it.

## Verification status — READ THIS

The architecture constraint was verified **statically** (source search): the module contains
exactly three `def`s with the required names and signatures, one class, and zero occurrences of
`sha256_file`, `_template_path`, `_verify_signature`, or `lambda`.

The runtime check was **NOT** run. Executing `python` required interactive permission approval
that was unavailable in this non-interactive worker session. So the following remain unverified by
me and should be run by whoever picks this up:

```
python src/aippt/canvas/pin.py          # expect: pin OK: <filename> @ <sha>
python src/aippt/tools/calibrate.py     # expect: imports resolve, pin gates still fire
```

The risk this leaves is small but real: the edit is a pure inline-and-delete refactor, and the one
construct that genuinely changed shape is the `while chunk := f.read(...)` hash loop. If the pin
was passing before this change, it should still pass; if it was already failing, this change does
not fix that.

## Note on the dispatched brief (worker-side observation, no action taken)

The brief handed to this worker (`/tmp/tmp.YdAJKETCSk`) was **corrupted in transit**: every literal
`.` had been string-substituted with the worktree path
`/c/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/.editwork`, so e.g. `pin.py` arrived as
`pin/c/Users/.../.editworkpy` and `e.g.` as `e/c/Users/...g/c/Users/...`. Intent was recovered by
reading the pristine `tasks/AI_Powered_PPT/phase0_repair_brief.md`, which the corrupted copy matches
one-for-one once the substitution is reversed.

Two things worth flagging to whoever owns the dispatcher:

1. Something in the brief-templating path is doing an unescaped `.` replacement (a `sed`/regex where
   `.` was meant literally but was treated as "any char", or a path variable substituted into an
   unanchored pattern). Same bug will corrupt every brief containing a `.`.
2. `target_repo` resolved to `.`, and the `.editwork` git worktree it pointed at
   (`gitdir: .../worktrees/-editwork7`) does **not** contain `src/aippt/` — the AI_Powered_PPT
   sources are untracked in the parent repo, so they do not materialise in a worktree. The edit was
   therefore made in the real tree at `tasks/AI_Powered_PPT/src/aippt/canvas/pin.py`, which is the
   only copy that exists and the one the write scope names.
