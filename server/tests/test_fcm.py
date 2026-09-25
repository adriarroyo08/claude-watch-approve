from unittest.mock import patch, MagicMock
from server.fcm import FULL_TEXT_MAX_BYTES, send_full_text, send_info_notification


def test_send_info_notification_with_tokens():
    mock_message_class = MagicMock()
    with patch("server.fcm.messaging") as mock_messaging:
        mock_messaging.Message = mock_message_class
        mock_messaging.Notification = MagicMock()
        mock_messaging.AndroidConfig = MagicMock()
        mock_messaging.AndroidNotification = MagicMock()
        mock_messaging.send = MagicMock(return_value="projects/test/messages/123")

        result = send_info_notification(
            tokens=["token-abc"],
            tool_name="Bash",
            message="npm install finished successfully",
        )

        assert result is True
        mock_messaging.send.assert_called_once()


def test_send_info_notification_no_tokens():
    result = send_info_notification(
        tokens=[],
        tool_name="Bash",
        message="npm install",
    )
    assert result is False


def test_send_info_notification_multiple_tokens():
    with patch("server.fcm.messaging") as mock_messaging:
        mock_messaging.Message = MagicMock()
        mock_messaging.Notification = MagicMock()
        mock_messaging.AndroidConfig = MagicMock()
        mock_messaging.AndroidNotification = MagicMock()
        mock_messaging.send = MagicMock(return_value="projects/test/messages/123")

        result = send_info_notification(
            tokens=["token-1", "token-2", "token-3"],
            tool_name="Edit",
            message="File updated",
        )

        assert result is True
        assert mock_messaging.send.call_count == 3


def test_send_info_notification_truncates_long_message():
    long_message = "x" * 600
    with patch("server.fcm.messaging") as mock_messaging:
        mock_messaging.Message = MagicMock()
        mock_messaging.Notification = MagicMock()
        mock_messaging.AndroidConfig = MagicMock()
        mock_messaging.AndroidNotification = MagicMock()
        mock_messaging.send = MagicMock(return_value="projects/test/messages/123")

        result = send_info_notification(
            tokens=["token-abc"],
            tool_name="Read",
            message=long_message,
        )

        assert result is True
        # Check the Notification was called with a body of max 500 chars
        call_kwargs = mock_messaging.Notification.call_args
        body = call_kwargs.kwargs.get("body") or call_kwargs.args[1] if call_kwargs.args else call_kwargs.kwargs["body"]
        assert len(body) == 500


def test_send_full_text_keeps_long_text_within_fcm_limit():
    text = "ñ" * 3000  # 6000 bytes: pasaria del limite de FCM
    with patch("server.fcm.messaging") as mock_messaging:
        delivered = send_full_text(tokens=["token-abc"], title="Respuesta", text=text)

    assert delivered == 1
    sent = mock_messaging.Message.call_args.kwargs["data"]["message"]
    assert len(sent) > 500
    assert len(sent.encode("utf-8")) <= FULL_TEXT_MAX_BYTES
    assert sent.endswith("…")


def test_send_full_text_keeps_going_after_a_bad_token():
    with patch("server.fcm.messaging") as mock_messaging:
        mock_messaging.send.side_effect = [Exception("caducado"), "ok"]
        delivered = send_full_text(tokens=["viejo", "bueno"], title="Respuesta", text="hola")

    assert delivered == 1
    assert mock_messaging.send.call_count == 2
