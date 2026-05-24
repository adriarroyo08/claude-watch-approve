import json
from unittest.mock import patch, MagicMock

import pytest

import hook.claude_watch_hook as mod


def invoke_main(input_data: dict, mock_requests):
    """Call mod.main() with patched stdin and capture the SystemExit code."""
    with patch.object(mod, "requests", mock_requests), \
         patch("sys.stdin") as mock_stdin:
        mock_stdin.read.return_value = json.dumps(input_data)
        with pytest.raises(SystemExit) as exc_info:
            mod.main()
    return exc_info.value.code


def test_sends_post_to_notify():
    """Hook sends a POST to /notify with the correct payload."""
    mock_requests = MagicMock()
    mock_requests.post.return_value = MagicMock(status_code=200)

    input_data = {
        "transcript_summary": "Fixed the bug in app.py",
        "stop_reason": "end_turn",
    }

    invoke_main(input_data, mock_requests)

    mock_requests.post.assert_called_once()
    call_kwargs = mock_requests.post.call_args[1]

    assert "/notify" in mock_requests.post.call_args[0][0]
    assert call_kwargs["json"]["tool_name"] == "Sesion"
    assert "end_turn" in call_kwargs["json"]["summary"]
    assert call_kwargs["json"]["result"] == "Fixed the bug in app.py"


def test_missing_summary_falls_back_to_last_assistant_message():
    """When transcript_summary is absent, the hook uses last_assistant_message."""
    mock_requests = MagicMock()
    mock_requests.post.return_value = MagicMock(status_code=200)

    input_data = {
        "last_assistant_message": "Tarea completada con exito",
        "stop_reason": "end_turn",
    }

    invoke_main(input_data, mock_requests)

    payload = mock_requests.post.call_args[1]["json"]
    assert payload["result"] == "Tarea completada con exito"


def test_missing_summary_and_message_uses_default():
    """When both summary fields are absent, the hook falls back to the default string."""
    mock_requests = MagicMock()
    mock_requests.post.return_value = MagicMock(status_code=200)

    input_data = {"stop_reason": "end_turn"}

    invoke_main(input_data, mock_requests)

    payload = mock_requests.post.call_args[1]["json"]
    assert payload["result"] == "Tarea completada"


def test_server_error_does_not_crash():
    """A network/server error is swallowed and the hook still exits cleanly."""
    mock_requests = MagicMock()
    mock_requests.post.side_effect = Exception("connection refused")

    input_data = {
        "transcript_summary": "Something happened",
        "stop_reason": "end_turn",
    }

    code = invoke_main(input_data, mock_requests)
    assert code == 0


def test_always_exits_with_code_zero():
    """The hook always exits with code 0 on a successful run."""
    mock_requests = MagicMock()
    mock_requests.post.return_value = MagicMock(status_code=200)

    input_data = {
        "transcript_summary": "All done",
        "stop_reason": "end_turn",
    }

    code = invoke_main(input_data, mock_requests)
    assert code == 0
