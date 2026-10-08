import sys, os, asyncio, json
from pathlib import Path
sys.path.insert(0, str(Path('src').resolve()))
from aippt.adapters.ai_adapter import CliWorkerClient
from aippt.canvas.app import system_instruction, _relaxed_live_schema

async def main():
    client = CliWorkerClient(track='b', backend='claude', model='sonnet', timeout_s=300)
    system = system_instruction()
    schema = _relaxed_live_schema()
    print("Calling complete_json...")
    try:
        res = await asyncio.to_thread(client.complete_json, system=system, user="Topic: Python", schema=schema)
        print("Success, keys:", res.keys())
    except Exception as e:
        print("Error:", type(e), e)

asyncio.run(main())
