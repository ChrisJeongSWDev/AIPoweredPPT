import sys
from pathlib import Path
from aippt.canvas.render_canvas import render, render_append

ir1 = {
  'version': 1,
  'title': 'Slide 1',
  'target': {
    'template': 'vieworks-layout3',
    'template_sha256': '60fe35466ed2bb477d592603d0eab9d8748521e54ae0632c9f6a94d0b02a855a'
  },
  'elements': []
}

ir2 = {
  'version': 1,
  'title': 'Slide 2',
  'target': {
    'template': 'vieworks-layout3',
    'template_sha256': '60fe35466ed2bb477d592603d0eab9d8748521e54ae0632c9f6a94d0b02a855a'
  },
  'elements': []
}

print('Rendering ir1...')
prs1 = render(ir1)
import io
buf = io.BytesIO()
prs1.save(buf)
target_bytes = buf.getvalue()

print('Appending ir2...')
prs2 = render_append(ir2, target_bytes)
prs2.save('test_output.pptx')
print(f'Done! Number of slides: {len(prs2.slides)}')
