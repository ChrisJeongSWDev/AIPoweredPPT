import sys
import os
from pathlib import Path

# Add src to python path so we can import aippt
sys.path.insert(0, str(Path(__file__).parent / "src"))

from aippt.adapters.ai_adapter import CliWorkerClient

def run_test():
    schema = {
        "type": "object",
        "properties": {
            "test_message": {"type": "string"},
            "success": {"type": "boolean"}
        },
        "required": ["test_message", "success"]
    }

    system = "You are a test assistant. You must respond with the requested JSON schema."
    user = "Return a JSON object with test_message='Hello from the CLI' and success=true."

    # --- CLAUDE TESTS ---
    print("=== Testing CLAUDE: Track B (Direct CLI Wrapper) ===")
    try:
        client_b_claude = CliWorkerClient(track="b", backend="claude", model="sonnet", timeout_s=300)
        result_b_claude = client_b_claude.complete_json(system=system, user=user, schema=schema)
        print("Claude Track B Result:", result_b_claude)
    except Exception as e:
        print(f"Claude Track B failed: {e}")

    print("\n=== Testing CLAUDE: Track A (Dispatcher) ===")
    try:
        os.environ.setdefault("MULTIAGENT_ROOT", "C:/Users/2021670/Documents/멀티 에이전트")
        client_a_claude = CliWorkerClient(track="a", backend="claude", model="sonnet", timeout_s=300)
        result_a_claude = client_a_claude.complete_json(system=system, user=user, schema=schema)
        print("Claude Track A Result:", result_a_claude)
    except Exception as e:
        print(f"Claude Track A failed: {e}")

    # --- CODEX TESTS ---
    print("\n=== Testing CODEX: Track B (Direct CLI Wrapper) ===")
    try:
        client_b_codex = CliWorkerClient(track="b", backend="codex", model="gpt-5.6-terra", timeout_s=300)
        result_b_codex = client_b_codex.complete_json(system=system, user=user, schema=schema)
        print("Codex Track B Result:", result_b_codex)
    except Exception as e:
        print(f"Codex Track B failed: {e}")

    print("\n=== Testing CODEX: Track A (Dispatcher) ===")
    try:
        client_a_codex = CliWorkerClient(track="a", backend="codex", model="gpt-5.6-terra", timeout_s=300)
        result_a_codex = client_a_codex.complete_json(system=system, user=user, schema=schema)
        print("Codex Track A Result:", result_a_codex)
    except Exception as e:
        print(f"Codex Track A failed: {e}")

if __name__ == "__main__":
    run_test()
