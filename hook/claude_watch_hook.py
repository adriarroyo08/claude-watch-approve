#!/usr/bin/env python3
"""Claude Code Stop hook: sends a summary notification when Claude finishes responding."""

import json
import os
import sys

import requests

SERVER_URL = os.environ.get("CLAUDE_WATCH_URL", "http://127.0.0.1:8400")
KEY_FILE = os.path.expanduser("~/.config/claude-watch/api-key")


def load_api_key() -> str:
    # The repo is public: the key never lives in code. Env var first, then a
    # private file (600) so it also works when Claude Code wasn't started
    # from a shell that sourced ~/.bashrc.
    key = os.environ.get("CLAUDE_WATCH_API_KEY", "")
    if key:
        return key
    try:
        with open(KEY_FILE) as f:
            return f.read().strip()
    except OSError:
        return ""


def main():
    input_data = json.loads(sys.stdin.read())

    # Stop hook provides stop_hook_active, transcript_summary, etc.
    summary = input_data.get("transcript_summary", "")
    stop_reason = input_data.get("stop_reason", "end_turn")

    if not summary:
        # Fallback: build message from last assistant text
        last_message = input_data.get("last_assistant_message", "Tarea completada")
        summary = last_message[:500]

    api_key = load_api_key()
    if not api_key:
        sys.exit(0)

    try:
        requests.post(
            f"{SERVER_URL}/notify",
            json={
                "tool_name": "Sesion",
                "summary": f"Claude ha terminado ({stop_reason})",
                "result": summary[:500],
            },
            headers={"X-Api-Key": api_key},
            timeout=5,
        )
    except Exception:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
