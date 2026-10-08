import sys, os
from pathlib import Path
sys.path.insert(0, str(Path('src').resolve()))
from aippt.adapters.ai_adapter import CliWorkerClient
client = CliWorkerClient(track='b', backend='claude', model='sonnet', timeout_s=30)
schema = {'type': 'object', 'properties': {'hello': {'type': 'string'}}, 'required': ['hello']}
print('Calling...')
try:
    print(client.complete_json(system='Return JSON', user='Say hello', schema=schema))
except Exception as e:
    print('Error:', type(e), e)
