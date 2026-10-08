import sys, os, asyncio, json
from pathlib import Path
sys.path.insert(0, str(Path('src').resolve()))
from aippt.canvas.app import api_generate
class MockApp:
    def __init__(self):
        self.state = type('State', (), {'pin': None})()
class MockRequest:
    def __init__(self, json_data):
        self.json_data = json_data
        self.app = MockApp()
        self.headers = {'content-type': 'application/json'}
    async def json(self):
        return self.json_data
    async def body(self):
        return json.dumps(self.json_data).encode('utf-8')
async def main():
    os.environ['AIPPT_LIVE_MODE'] = '1'
    req = MockRequest({'prompt': 'Make a presentation about Python programming.', 'model': 'sonnet'})
    try:
        res = await api_generate(req)
        print('Response status:', res.status_code)
        print('Response body:', res.body.decode('utf-8')[:200])
    except Exception as e:
        print('Error:', type(e), e)
asyncio.run(main())
