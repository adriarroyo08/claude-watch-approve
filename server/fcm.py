from firebase_admin import messaging

_INITIALIZED = False


def _ensure_init():
    global _INITIALIZED
    if not _INITIALIZED:
        import firebase_admin
        from server.config import FCM_CREDENTIALS_PATH
        from pathlib import Path

        creds_path = Path(FCM_CREDENTIALS_PATH)
        if creds_path.exists():
            cred = firebase_admin.credentials.Certificate(str(creds_path))
            firebase_admin.initialize_app(cred)
        _INITIALIZED = True


def send_info_notification(
    tokens: list[str],
    tool_name: str,
    message: str,
) -> bool:
    if not tokens:
        return False

    _ensure_init()

    # Truncate message for push notification
    body = message[:500] if len(message) > 500 else message

    for token in tokens:
        msg = messaging.Message(
            notification=messaging.Notification(
                title=f"Claude: {tool_name}",
                body=body,
            ),
            data={
                "type": "info",
                "tool_name": tool_name,
                "message": body,
            },
            token=token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="claude_summary",
                ),
            ),
        )
        messaging.send(msg)

    return True
