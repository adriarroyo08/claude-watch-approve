import json
import pytest
from unittest.mock import patch, MagicMock
from hook.claude_watch_hook import should_require_approval, build_summary, request_approval


def test_bash_requires_approval():
    assert should_require_approval("Bash") is True


def test_edit_requires_approval():
    assert should_require_approval("Edit") is True


def test_write_requires_approval():
    assert should_require_approval("Write") is True


def test_notebook_edit_requires_approval():
    assert should_require_approval("NotebookEdit") is True


def test_read_does_not_require_approval():
    assert should_require_approval("Read") is False


def test_glob_does_not_require_approval():
    assert should_require_approval("Glob") is False


def test_grep_does_not_require_approval():
    assert should_require_approval("Grep") is False


def test_agent_does_not_require_approval():
    assert should_require_approval("Agent") is False


def test_mcp_create_requires_approval():
    assert should_require_approval("mcp__github__create_issue") is True


def test_mcp_get_does_not_require_approval():
    assert should_require_approval("mcp__github__get_issue") is False


def test_build_summary_bash():
    tool_input = {"command": "npm install express", "description": "Install express"}
    result = build_summary("Bash", tool_input)
    assert result == "Bash: npm install express"


def test_build_summary_edit():
    tool_input = {"file_path": "/home/ubuntu/src/app.ts", "old_string": "foo", "new_string": "bar"}
    result = build_summary("Edit", tool_input)
    assert result == "Edit: /home/ubuntu/src/app.ts"


def test_build_summary_write():
    tool_input = {"file_path": "/home/ubuntu/config.json", "content": "{}"}
    result = build_summary("Write", tool_input)
    assert result == "Write: /home/ubuntu/config.json"


def test_build_summary_generic():
    tool_input = {"param1": "value1"}
    result = build_summary("mcp__github__create_issue", tool_input)
    assert "mcp__github__create_issue" in result


@patch("hook.claude_watch_hook.requests")
def test_request_approval_approved(mock_requests):
    mock_create_response = MagicMock()
    mock_create_response.status_code = 201
    mock_create_response.json.return_value = {"id": "abc123", "status": "pending"}

    mock_status_response = MagicMock()
    mock_status_response.status_code = 200
    mock_status_response.json.return_value = {"id": "abc123", "status": "approved"}

    mock_requests.post.return_value = mock_create_response
    mock_requests.get.return_value = mock_status_response

    result = request_approval("Bash", "npm install", server_url="http://localhost:8000", api_key="test", poll_interval=0)
    assert result is True


@patch("hook.claude_watch_hook.requests")
def test_request_approval_denied(mock_requests):
    mock_create_response = MagicMock()
    mock_create_response.status_code = 201
    mock_create_response.json.return_value = {"id": "abc123", "status": "pending"}

    mock_status_response = MagicMock()
    mock_status_response.status_code = 200
    mock_status_response.json.return_value = {"id": "abc123", "status": "denied"}

    mock_requests.post.return_value = mock_create_response
    mock_requests.get.return_value = mock_status_response

    result = request_approval("Bash", "rm -rf /", server_url="http://localhost:8000", api_key="test", poll_interval=0)
    assert result is False
