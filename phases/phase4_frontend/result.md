# Worker Result
status: error | model: N/A | applied: N/A | verdict: N/A
stdout_path: N/A
stderr_path: N/A

=== EMPTY DIFF — EDIT CAPTURED NO REVIEWABLE CHANGES (dispatcher hard stop) ===
The edit worker returned but the staging diff (/c/Users/2021670/.ma-stg/stg.m3litLa9 vs HEAD, bin/obj/.vs/packages/settings.local.json excluded) is EMPTY.
Classification: empty_diff_no_capture

Actions taken:
- Did NOT default the verdict to APPROVE and did NOT apply anything (applied:false).
- Did NOT invoke the review gate on an empty diff.
- PRESERVED the staging worktree for inspection (not cleaned up), so any worker output is not destroyed: /c/Users/2021670/.ma-stg/stg.m3litLa9

Likely causes (check in this order):
- A stale .editwork left by a CANCELED prior run of the same slug (worktree add collides / falls back). Use a FRESH slug and do not cancel mid-run.
- The worker edited a location outside the diffed worktree (wrong working root).
- The worker genuinely had nothing to change (then re-scope or confirm the task is a no-op).

Do NOT re-call the worker blindly and do NOT mark this done/applied. Diagnose why the diff is empty first (inspect the preserved worktree above).
