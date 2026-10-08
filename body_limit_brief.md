---
mode: edit
claude_model: sonnet
target_repo: c:/Users/2021670/Documents/멀티 에이전트
write_scope: tasks/AI_Powered_PPT/src/aippt/canvas/app.py
change_detail_path: tasks/AI_Powered_PPT/body_limit_change_detail.md
approved_write_manifest: tasks/AI_Powered_PPT/body_limit_write_manifest.txt
---

# Task Description
The user encountered an HTTP 413 "payload exceeds 2097152 bytes" error when exporting a deck with images.
Currently, `MAX_BODY_BYTES` in `app.py` is set to `2 * 1024 * 1024` (2MB). However, now that images are embedded as Base64 strings in the JSON payload, a deck with multiple images can easily exceed this limit. `MAX_IMAGES` is 4 and `MAX_IMAGE_BYTES` is 1.4MB, meaning a maximum valid payload with 4 images could be up to ~7.5MB in Base64 encoding.

Please increase `MAX_BODY_BYTES` to 10MB (`10 * 1024 * 1024`) to accommodate decks with images.

## Instructions
1. Open `tasks/AI_Powered_PPT/src/aippt/canvas/app.py`.
2. Locate `MAX_BODY_BYTES = 2 * 1024 * 1024`.
3. Update the value to `10 * 1024 * 1024`.
4. Update the preceding comment to explain that 10MB is needed to accommodate up to 4 Base64-encoded images.

Document the change in `tasks/AI_Powered_PPT/body_limit_change_detail.md`.
