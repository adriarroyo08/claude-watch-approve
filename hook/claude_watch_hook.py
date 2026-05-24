#!/usr/bin/env python3
"""Claude Code Stop hook: sends a summary notification when Claude finishes responding."""

import json
import os
import sys

import requests

SERVER_URL = os.environ.get("CLAUDE_WATCH_URL", "http://127.0.0.1:8400")
API_KEY = os.environ.get("CLAUDE_WATCH_API_KEY", "IjBMa4QhmTlpZjNLwlksIsjVnSERyXlX6RIs4GnsiNA")


def main():
    input_data = json.loads(sys.stdin.read())

    # Stop hook provides stop_hook_active, transcript_summary, etc.
    summary = input_data.get("transcript_summary", "")
    stop_reason = input_data.get("stop_reason", "end_turn")

    if not summary:
        # Fallback: build message from last assistant text
        last_message = input_data.get("last_assistant_message", "Tarea completada")
        summary = last_message[:500]

    try:
        requests.post(
            f"{SERVER_URL}/notify",
            json={
                "tool_name": "Sesion",
                "summary": f"Claude ha terminado ({stop_reason})",
                "result": summary[:500],
            },
            headers={"X-Api-Key": API_KEY},
            timeout=5,
        )
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
