# Brief — claude-main / ui-tweaks

## Execution Context

```yaml
target_repo: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT
write_scope: src/aippt/canvas/static/index.html, src/aippt/canvas/static/editor.js, src/aippt/canvas/static/style.css
claude_model: sonnet
change_detail_path: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/workers/claude-main/01-ui-tweaks/change_detail.md
read_refs: N/A
```

## Worker Conduct Rules

- Keep the requested scope minimal. Do not add speculative abstractions or extra features.
- Make surgical changes only. Preserve existing style and do not touch unrelated code.
- Modify ONLY the files listed in `write_scope`.
- Change Detail Log goes ONLY to `change_detail_path`.

## Normalized English Request

```text
User request:
1. Implement "View & Copy JSON" feature to copy current live design JSON and display it in a notepad-like modal.
2. Optimize AI Draft layout space (reduce padding/margins), rename title to "Gemini AI Slide Builder", and remove small hint text.
3. In prompt textarea, pressing Enter submits prompt generation.
4. Shift + Enter in prompt textarea inserts a newline.
5. Rename "Save to Server" to "Save Template", and add "Load Template" button to load selected template from server.
6. Support pasting images from clipboard (Ctrl + V) directly onto the slide stage using Snipping Tool / Ctrl+C.
```

## Objective

Verify, refine, and finalize the implementation of these 6 UI/UX requirements across index.html, editor.js, and style.css in the target repo.

## Output Format

- File path: `tasks/AI_Powered_PPT/workers/claude-main/01-ui-tweaks/result.md`
- Format: Markdown
