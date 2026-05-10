#!/usr/bin/env python3
"""Claude Code pre_tool_use hook: sends approval requests to Claude Watch Approve server.

Only sends notifications for tools that Claude Code would ask "do you want to proceed?".
Tools that are auto-approved in settings or are read-only skip the notification.
"""

import fnmatch
import json
import os
import re
import sys
import time

import requests

SERVER_URL = os.environ.get("CLAUDE_WATCH_URL", "http://127.0.0.1:8400")
API_KEY = os.environ.get("CLAUDE_WATCH_API_KEY", "IjBMa4QhmTlpZjNLwlksIsjVnSERyXlX6RIs4GnsiNA")
POLL_INTERVAL = int(os.environ.get("CLAUDE_WATCH_POLL_INTERVAL", "2"))
TIMEOUT = int(os.environ.get("CLAUDE_WATCH_TIMEOUT", "300"))

# Tools that never require approval (read-only / passive)
ALWAYS_SAFE_TOOLS = {
    "Read", "Glob", "Grep", "Agent", "WebSearch", "WebFetch",
    "TodoRead", "TaskList", "TaskGet", "TaskOutput",
    "ToolSearch", "Skill", "AskUserQuestion",
    "EnterPlanMode", "ExitPlanMode",
    "ListMcpResourcesTool", "ReadMcpResourceTool",
}

CLAUDE_HOME = os.path.expanduser("~/.claude")


def _load_json(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def get_allowed_tools() -> list[str]:
    """Read allowed tool patterns from Claude Code settings files."""
    patterns = []

    # Global settings
    global_settings = _load_json(os.path.join(CLAUDE_HOME, "settings.json"))
    for rule in global_settings.get("permissions", {}).get("allow", []):
        patterns.append(rule)

    # Local settings
    local_settings = _load_json(os.path.join(CLAUDE_HOME, "settings.local.json"))
    for rule in local_settings.get("permissions", {}).get("allow", []):
        patterns.append(rule)

    # Project-level settings
    cwd = os.getcwd()
    project_settings = _load_json(os.path.join(cwd, ".claude", "settings.local.json"))
    for rule in project_settings.get("permissions", {}).get("allow", []):
        patterns.append(rule)

    # Also check legacy allowedTools in .claude.json
    claude_json = _load_json(os.path.expanduser("~/.claude.json"))
    projects = claude_json.get("projects", {})
    for project_path, project_data in projects.items():
        if cwd.startswith(project_path):
            for rule in project_data.get("allowedTools", []):
                patterns.append(rule)

    return patterns


def _tool_matches_pattern(tool_name: str, tool_input: dict, pattern: str) -> bool:
    """Check if a tool call matches an allowed pattern.

    Patterns can be:
    - "ToolName" — matches any call to that tool
    - "Bash(*)" — matches any Bash call
    - "Bash(command:*)" — matches Bash calls starting with "command"
    - "Bash(exact command here)" — matches exact command
    - "mcp__server__action" — matches exact MCP tool
    """
    # Pattern like "Bash(something:*)" or "Bash(exact)"
    match = re.match(r'^(\w+)\((.+)\)$', pattern)
    if match:
        pattern_tool = match.group(1)
        pattern_arg = match.group(2)

        if tool_name != pattern_tool:
            return False

        # Get the relevant input value to match against
        if tool_name == "Bash":
            value = tool_input.get("command", "")
        elif tool_name in ("Edit", "Write", "NotebookEdit"):
            value = tool_input.get("file_path", "")
        elif tool_name == "Read":
            value = tool_input.get("file_path", "")
        else:
            value = json.dumps(tool_input)

        # Handle wildcard patterns: "cmd:*" means starts with "cmd"
        if pattern_arg.endswith(":*"):
            prefix = pattern_arg[:-2]
            return value.startswith(prefix)
        elif pattern_arg == "*":
            return True
        else:
            # fnmatch for glob-style matching
            return fnmatch.fnmatch(value, pattern_arg)

    # Plain tool name match (e.g., "mcp__github__create_pull_request")
    if pattern == tool_name:
        return True

    # Wildcard tool name (e.g., "mcp__github__*")
    if fnmatch.fnmatch(tool_name, pattern):
        return True

    return False


def is_auto_approved(tool_name: str, tool_input: dict) -> bool:
    """Check if this tool call is auto-approved in Claude Code settings."""
    if tool_name in ALWAYS_SAFE_TOOLS:
        return True

    allowed = get_allowed_tools()
    return any(_tool_matches_pattern(tool_name, tool_input, p) for p in allowed)


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

    if is_auto_approved(tool_name, tool_input):
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
