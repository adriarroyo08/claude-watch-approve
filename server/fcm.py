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


def send_approval_notification(
    tokens: list[str],
    approval_id: str,
    tool_name: str,
    summary: str,
) -> bool:
    if not tokens:
        return False

    _ensure_init()

    for token in tokens:
        message = messaging.Message(
            notification=messaging.Notification(
                title=f"Claude: {tool_name}",
                body=summary,
            ),
            data={
                "approval_id": approval_id,
                "tool_name": tool_name,
                "summary": summary,
            },
            token=token,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="claude_approvals",
                    sound="approval_sound",
                    default_vibrate_timings=False,
                    vibrate_timings=[0, 100, 200, 300],
                ),
            ),
        )
        messaging.send(message)

    return True
