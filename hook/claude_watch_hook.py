#!/usr/bin/env python3
"""Claude Code pre_tool_use hook: sends approval requests to Claude Watch Approve server."""

import json
import os
import sys
import time

import requests

SERVER_URL = os.environ.get("CLAUDE_WATCH_URL", "https://claude-watch.automatito.win")
API_KEY = os.environ.get("CLAUDE_WATCH_API_KEY", "change-me-in-production")
POLL_INTERVAL = int(os.environ.get("CLAUDE_WATCH_POLL_INTERVAL", "2"))
TIMEOUT = int(os.environ.get("CLAUDE_WATCH_TIMEOUT", "300"))

SAFE_TOOLS = {"Read", "Glob", "Grep", "Agent", "WebSearch", "WebFetch", "TodoRead", "TodoWrite", "TaskList", "TaskGet", "ToolSearch", "Skill"}
MCP_SAFE_PREFIXES = ("get", "list", "search", "read", "fetch", "find", "check", "validate")


def should_require_approval(tool_name: str) -> bool:
    if tool_name in SAFE_TOOLS:
        return False
    if tool_name.startswith("mcp__"):
        action = tool_name.split("__")[-1].lower()
        return not any(action.startswith(prefix) for prefix in MCP_SAFE_PREFIXES)
    return True


def build_summary(tool_name: str, tool_input: dict) -> str:
    if tool_name == "Bash":
        return f"Bash: {tool_input.get('command', '?')}"
    if tool_name == "Edit":
        return f"Edit: {tool_input.get('file_path', '?')}"
    if tool_name == "Write":
        return f"Write: {tool_input.get('file_path', '?')}"
    if tool_name == "NotebookEdit":
        return f"NotebookEdit: {tool_input.get('file_path', '?')}"
    return f"{tool_name}: {json.dumps(tool_input)[:100]}"


def request_approval(
    tool_name: str,
    summary: str,
    server_url: str = SERVER_URL,
    api_key: str = API_KEY,
    poll_interval: int = POLL_INTERVAL,
    timeout: int = TIMEOUT,
) -> bool:
    headers = {"X-Api-Key": api_key}

    resp = requests.post(
        f"{server_url}/approval-request",
        json={"tool_name": tool_name, "tool_input_summary": summary},
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    approval_id = resp.json()["id"]

    start = time.time()
    while time.time() - start < timeout:
        status_resp = requests.get(
            f"{server_url}/approval-status/{approval_id}",
            headers=headers,
            timeout=10,
        )
        status_resp.raise_for_status()
        status = status_resp.json()["status"]

        if status == "approved":
            return True
        if status == "denied":
            return False

        time.sleep(poll_interval)

    return False  # Timeout = deny


def main():
    input_data = json.loads(sys.stdin.read())
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if not should_require_approval(tool_name):
        sys.exit(0)

    summary = build_summary(tool_name, tool_input)

    try:
        approved = request_approval(tool_name, summary)
    except Exception as e:
        print(f"Claude Watch error: {e}", file=sys.stderr)
        sys.exit(0)  # Fail open: if server is down, allow execution

    if approved:
        sys.exit(0)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
