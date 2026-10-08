target_repo: .
phase: phase6_repair5
claude_model: sonnet
change_detail_path: workers/phase6_repair5/change_detail.md
write_scope:
  - tasks/AI_Powered_PPT/src/aippt/canvas/schema.json
  - tasks/AI_Powered_PPT/src/aippt/canvas/static/index.html
  - tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js

# Task Overview (Repair Mode: Dispatcher Bug & Codex API Crash Bypass)
You have already successfully fixed the XSS and Blob URL issues.
However, the previous run failed because the `codex-critic` reviewer crashed with a 401 Unauthorized OpenAI API error.
We have now switched the reviewer to `claude-review-sonnet` to bypass the OpenAI outage.
The `target_repo` is still `.` to bypass the dispatcher path bug.
Please generate the EXACT SAME PATCH you generated in the previous run.
You must modify the files in `tasks/AI_Powered_PPT/src/...`.
