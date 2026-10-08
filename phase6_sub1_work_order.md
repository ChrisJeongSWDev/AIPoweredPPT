---
target_repo: C:/Users/2021670/Documents/멀티 에이전트
claude_model: sonnet
write_scope: tasks/AI_Powered_PPT/src/aippt/canvas/schema.json
change_detail_path: tasks/AI_Powered_PPT/phase6_sub1_change_detail.md
---
# Phase 6 (Sub 1): Schema Update for Transparency and Media

## CRITICAL INSTRUCTION
You MUST apply your edits to `.editwork/tasks/AI_Powered_PPT/src/aippt/canvas/schema.json`. DO NOT edit the real repo directly.

## Task
Update `schema.json` to support Phase 6 features:
1. Find `$defs.color`. Change its `pattern` from `"^#[0-9A-Fa-f]{6}$"` to `"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$"`. Update its description to mention that an 8-character hex indicates an alpha channel (transparency).
2. Find `$defs.stroke`. Update its description to remove the restriction banning alpha (e.g. remove "There is no alpha in Phase 1 (D-4)").
3. Find `$defs.element.oneOf`. Add two new branches: `{"$ref": "#/$defs/image"}` and `{"$ref": "#/$defs/video"}`.
4. Add the new definitions `$defs.image` and `$defs.video`. They should be objects identical to `rect` but with an additional required property `src` (type: string). Remove `text` from them if it exists. Required fields: `id, type, x, y, w, h, src`.
