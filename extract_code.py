import re
import os

with open(r'tasks\AI_Powered_PPT\artifacts\claude-main-stdout-313-5532.txt', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r'###\s+`([^`]+)`.*?\n```(?:python)?\n(.*?)\n```'
matches = re.findall(pattern, text, re.DOTALL)

if not matches:
    print('No code blocks found.')
else:
    for filepath, code in matches:
        filepath = filepath.strip()
        full_path = os.path.join(r'tasks\AI_Powered_PPT', filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(code)
        print(f'Wrote {filepath}')
