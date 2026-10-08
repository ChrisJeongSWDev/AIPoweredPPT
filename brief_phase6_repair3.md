target_repo: tasks/AI_Powered_PPT
phase: phase6_repair3
claude_model: sonnet
change_detail_path: workers/phase6_repair3/change_detail.md
write_scope:
  - tasks/AI_Powered_PPT/src/aippt/canvas/schema.json
  - tasks/AI_Powered_PPT/src/aippt/canvas/static/index.html
  - tasks/AI_Powered_PPT/src/aippt/canvas/static/editor.js

# Task Overview (Repair Mode: Continuation)
You are in **Repair Mode** for the Phase 6 HTML Export feature. Your previous attempt generated the diff attached below. However, the Codex Critic reviewer blocked your code for two critical security/offline-capability issues. 
Previous diff path (read it using your tools to see what you wrote): `C:\Users\2021670\Documents\멀티 에이전트\tasks\AI_Powered_PPT\artifacts\claude-main-diff-1989583-17592.txt`

## Reviewer Feedback (BLOCK)
- `editor.js:2203-2215` and `editor.js:2269` serialize live `contenteditable` markup through `clone.outerHTML` and `titleField.innerHTML`. Rich pasted content can therefore preserve unsafe tags, event handlers, or nested `javascript:` links, bypassing `sanitizeLink()` and executing when the exported file opens. Reconstruct text from normalized/escaped data or sanitize cloned DOM with strict tag/attribute allowlists.
- (You already fixed the Blob URL and href injection in your previous run, so just keep those fixes and add the fix for `contenteditable` serialization).

## Requirements
Please generate a NEW complete patch (using the same write_scope) that includes your previous work but fixes the XSS issue above:
1. **ContentEditable Sanitization**: When exporting HTML, do not serialize raw `innerHTML` or `outerHTML` of contenteditable elements directly if they might contain pasted rich text. Sanitize them by keeping only allowed tags/attributes, or extract `innerText` and reconstruct safe markup.
