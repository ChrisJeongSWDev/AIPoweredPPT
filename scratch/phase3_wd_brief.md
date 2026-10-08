---
target_repo: C:\Users\2021670\Documents\멀티 에이전트\tasks\AI_Powered_PPT
read_refs: N/A
---

# Phase 3: Backend Multi-Agent Log Streaming

The user wants to view the live Multi-Agent logs while the worker is generating a presentation. Currently, i_adapter.py's _run_cli uses capture_output=True, which buffers all output until the worker finishes, preventing live streaming.

## Instructions for WorkDirector
Analyze src/aippt/adapters/ai_adapter.py and src/aippt/canvas/app.py.
We need to:
- Modify _run_cli (or how _run_track_a calls it) to redirect stderr to rtifacts/multiagent_live.log in real-time, while still capturing stdout via PIPE. After the process ends, it should read the log file back into esult.stderr so existing error handling doesn't break.
- In pp.py, add a new GET /api/log endpoint that reads and returns the contents of rtifacts/multiagent_live.log.

Please strengthen this brief and output the enhanced instructions and context. Do NOT make file edits yourself (you are a read-only director). Ensure the target files for the next edit phase are i_adapter.py and pp.py.
