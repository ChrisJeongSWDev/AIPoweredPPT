import os
import json
import traceback

# Inject the API Key for Live Mode
os.environ.setdefault("GEMINI_API_KEY", "placeholder_for_test")

from aippt.canvas.app import app
from fastapi.testclient import TestClient

# Mock the state initialized by main()
app.state.pin = None

client = TestClient(app)

print("Starting Live Test...")
try:
    response = client.post("/api/generate", json={
        "prompt": "Create a 3 slide presentation about the future of AI. Make it short.",
        "model": "flash"
    })
    print(f"Status Code: {response.status_code}")
    print(f"Response Body (truncated): {str(response.text)[:500]}")
    if response.status_code == 200:
        print("\n=== SUCCESS: Live model generated the canvas-ir/1 JSON. ===")
except Exception as e:
    print(f"Exception during Live Test: {e}")
    traceback.print_exc()
