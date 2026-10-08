---
target_repo: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT
write_scope:
  - src/aippt/canvas/static/index.html
  - src/aippt/canvas/static/editor.js
claude_model: sonnet
read_refs: N/A
change_detail_path: C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT/scratch/change_detail_phase2.md
---

# Phase 2: UI Updates (Remove '+' Button and Add View Log feature)

The user wants two UI changes in the Prompt Composer:
1. Remove the '+' button (`<button class="icon-btn plus-btn">`).
2. Add a 'View Log' button next to the model selector. Clicking it should open a modal that displays the multi-agent execution log fetched from `/api/log`.

## Instructions
Please strictly follow these changes to edit the target files:

1. **In `src/aippt/canvas/static/index.html`**:
   - Find `<button class="icon-btn plus-btn" title="Add attachment"><svg...></button>` inside the `.prompt-bar` and completely REMOVE IT.
   - Find `<select id="p-model">`. Immediately after this select box, add a new button: `<button type="button" id="b-view-log" class="sidebar-action" style="margin-left: 8px; font-size: 11px;">View Log</button>`.
   - Add a modal container somewhere at the bottom of the body (e.g., right before `</body>`):
     ```html
     <!-- Multi-Agent Log Viewer Modal -->
     <div id="log-modal" class="modal-overlay" style="display: none;">
       <div class="modal-content" style="max-width: 800px; width: 90%; height: 80%; display: flex; flex-direction: column;">
         <div class="modal-header">
           <h2>Multi-Agent Workflow Log</h2>
           <button class="close-btn" id="close-log-modal">&times;</button>
         </div>
         <pre id="log-modal-text" style="flex: 1; overflow-y: auto; background: #1e1e1e; color: #d4d4d4; padding: 10px; font-family: monospace; font-size: 12px; margin-top: 10px; white-space: pre-wrap; word-wrap: break-word;">Waiting for logs...</pre>
       </div>
     </div>
     ```

2. **In `src/aippt/canvas/static/editor.js`**:
   - At the end of the file, add logic for the log modal:
     ```javascript
     // Log Modal logic
     const bViewLog = document.getElementById('b-view-log');
     const logModal = document.getElementById('log-modal');
     const closeLogModal = document.getElementById('close-log-modal');
     const logModalText = document.getElementById('log-modal-text');
     let logInterval = null;

     if (bViewLog && logModal && closeLogModal && logModalText) {
         bViewLog.addEventListener('click', () => {
             logModal.style.display = 'flex';
             fetchLog(); // fetch immediately
             logInterval = setInterval(fetchLog, 1000); // poll every 1 second
         });

         closeLogModal.addEventListener('click', () => {
             logModal.style.display = 'none';
             if (logInterval) {
                 clearInterval(logInterval);
                 logInterval = null;
             }
         });
         
         // Close if clicking outside
         logModal.addEventListener('click', (e) => {
             if (e.target === logModal) {
                 closeLogModal.click();
             }
         });
     }

     function fetchLog() {
         fetch('/api/log')
             .then(res => res.json())
             .then(data => {
                 if (data.log) {
                     logModalText.textContent = data.log;
                     logModalText.scrollTop = logModalText.scrollHeight; // Auto scroll to bottom
                 } else if (data.error) {
                     logModalText.textContent = 'Error fetching logs: ' + data.detail;
                 }
             })
             .catch(err => {
                 logModalText.textContent = 'Failed to fetch logs. Is the server running?';
             });
     }
     ```

Output ONLY the required edits in your envelope.
