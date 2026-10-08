target_repo: .
phase: phase6_repair4
claude_model: sonnet
change_detail_path: workers/phase6_repair4/change_detail.md
write_scope:
  - tasks/AI_Powered_PPT/src/aippt/canvas/schema.json
  - tasks/AI_Powered_PPT/src/aippt/canvas/static/index.html
  - tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js

# Task Overview (Repair Mode: Dispatcher Bug Bypass)
You have already successfully fixed the XSS and Blob URL issues, and the reviewer approved them (with only a WARNING about minor filename/CSS discrepancies which the user accepted).
However, due to a bug in the multi-agent dispatcher's path resolution (the `write_scope` vs `target_repo` double-prefix filecopy bug), your previous approved patch could not be automatically applied to the main repository.

To bypass this bug, the `target_repo` has been changed to `.` (workspace root).
Please generate the EXACT SAME PATCH you generated in the previous run. 
You can also optionally fix the minor WARNINGs from the reviewer if you want:
1. `editor.js:2298` downloads `<title>.html`, but the requirement explicitly specifies `presentation.html`.
2. `EXPORT_CSS` omits the canvas’s visible `#stage::after` red divider.

You must modify the files in `tasks/AI_Powered_PPT/src/...`.
