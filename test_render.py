import json
import os
from pptx import Presentation
from aippt.canvas.render_canvas import render

with open('test_payload.json', 'r', encoding='utf-8') as f:
    payload = json.load(f)

os.chdir('C:/Users/2021670/Documents/멀티 에이전트/tasks/AI_Powered_PPT')
prs = render(payload)
prs.save('test_output.pptx')
print('Rendered to test_output.pptx successfully!')
