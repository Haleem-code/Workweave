"""Store an Ollama Cloud key in Workweave's local Docker vault; never edit .env."""
import argparse
import getpass
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compose", choices=("docker-compose.cloud.yml", "docker-compose.yml"), default="docker-compose.cloud.yml")
    args = parser.parse_args()
    if not sys.stdin.isatty():
        raise SystemExit("Run this helper in your own interactive terminal so the key can be hidden.")
    key = getpass.getpass("Ollama Cloud API key (hidden): ").strip()
    if not key or len(key) > 500 or any(ord(c) < 33 or ord(c) > 126 for c in key):
        raise SystemExit("No key saved. Enter a non-empty API key without spaces or control characters.")
    # The secret travels through stdin, never command arguments, logs, or .env.
    code = "import json,sys; from workweave_api.config import settings; from workweave_api.providers import Vault; Vault(settings.data_dir).set('ollama_cloud', json.load(sys.stdin)['key'])"
    command = ["docker", "compose", "-f", args.compose, "exec", "-T", "api", "python", "-c", code]
    try:
        result = subprocess.run(command, input=json.dumps({"key": key}), text=True, capture_output=True,
                                cwd=Path(__file__).resolve().parents[1], timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        raise SystemExit("No success confirmed. Check that Docker and the Workweave API are running, then retry.")
    if result.returncode:
        raise SystemExit("No success confirmed. Check the Workweave API container, then retry. Diagnostic output was withheld to protect the key.")
    print("Key saved in the encrypted backend vault. Your .env was not changed.")
    print("In Settings > AI answers, choose Ollama Cloud and save preferences. New workspaces already select it by default.")
    print("To use it exclusively, turn off the other answer providers. No live API request has been made yet.")
    print("If replacing a rejected key, restart only the API to clear its authentication-failure state:")
    print("docker compose -f " + args.compose + " restart api")


if __name__ == "__main__":
    main()
