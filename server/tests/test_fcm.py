from unittest.mock import patch, MagicMock
from server.fcm import send_approval_notification


def test_send_notification_with_tokens():
    mock_message_class = MagicMock()
    with patch("server.fcm.messaging") as mock_messaging:
        mock_messaging.Message = mock_message_class
        mock_messaging.Notification = MagicMock()
        mock_messaging.send = MagicMock(return_value="projects/test/messages/123")

        result = send_approval_notification(
            tokens=["token-abc"],
            approval_id="abc123",
            tool_name="Bash",
            summary="npm install express",
        )

        assert result is True
        mock_messaging.send.assert_called_once()


def test_send_notification_no_tokens():
    result = send_approval_notification(
        tokens=[],
        approval_id="abc123",
        tool_name="Bash",
        summary="npm install",
    )
    assert result is False
