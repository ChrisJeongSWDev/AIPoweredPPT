target_repo: tasks/AI_Powered_PPT
phase: phase6_repair
claude_model: sonnet
change_detail_path: workers/phase6_repair/change_detail.md
write_scope:
  - src/aippt/canvas/schema.json
  - src/aippt/canvas/static/index.html
  - src/aippt/canvas/static/editor.js

# Task Overview (Repair Mode: Continuation)
You are in **Repair Mode** for the Phase 6 HTML Export feature. Your previous attempt generated the diff attached below. However, the Codex Critic reviewer blocked your code for two critical security/offline-capability issues. 
Previous diff path (read it using your tools to see what you wrote): `C:\Users\2021670\Documents\멀티 에이전트\tasks\AI_Powered_PPT\artifacts\claude-main-diff-1934939-13128.txt`

## Reviewer Feedback (BLOCK)
- `editor.js:2203-2215` and `editor.js:2269` serialize live `contenteditable` markup through `clone.outerHTML` and `titleField.innerHTML`. Rich pasted content can therefore preserve unsafe tags, event handlers, or nested `javascript:` links, bypassing `sanitizeLink()` and executing when the exported file opens. Reconstruct text from normalized/escaped data or sanitize cloned DOM with strict tag/attribute allowlists.
- (You already fixed the Blob URL and href injection in your previous run, so just keep those fixes and add the fix for `contenteditable` serialization).

## Critical Instruction for Diff Generation
The dispatcher strict-matches your diff paths against `write_scope`. Since `target_repo` is `tasks/AI_Powered_PPT`, the `write_scope` paths are `src/...`.
**Your diff MUST use paths starting with `src/...`, NOT `tasks/AI_Powered_PPT/src/...`.**
To ensure your diff generates correctly, you MUST `cd tasks/AI_Powered_PPT` inside your staged worktree before editing the files! If you edit them from the repo root, your diff will contain `tasks/AI_Powered_PPT/` prefixes and the dispatcher will reject it as a write_scope violation!

## Requirements
Please generate a NEW complete patch (using the same write_scope) that includes your previous work but fixes the XSS issue above:
1. **ContentEditable Sanitization**: When exporting HTML, do not serialize raw `innerHTML` or `outerHTML` of contenteditable elements directly if they might contain pasted rich text. Sanitize them by keeping only allowed tags/attributes, or extract `innerText` and reconstruct safe markup.
