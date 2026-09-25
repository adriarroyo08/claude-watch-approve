import logging

from firebase_admin import messaging

logger = logging.getLogger(__name__)

# FCM rechaza mensajes de mas de 4096 bytes; el resto queda para las claves.
FULL_TEXT_MAX_BYTES = 3500

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


def _truncate_utf8(text: str, max_bytes: int) -> str:
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    # "…" ocupa 3 bytes; errors="ignore" descarta un caracter partido.
    return encoded[: max_bytes - 3].decode("utf-8", errors="ignore") + "…"


def send_full_text(tokens: list[str], title: str, text: str) -> int:
    """Manda una respuesta larga al movil. Devuelve a cuantos llego.

    Solo datos, sin bloque notification: asi la app del movil siempre recibe
    onMessageReceived y pinta el texto entero, tambien en segundo plano, y el
    texto no va dos veces contra el limite de 4096 bytes. Un token caducado
    no corta el envio a los demas.
    """
    if not tokens:
        return 0

    _ensure_init()
    body = _truncate_utf8(text, FULL_TEXT_MAX_BYTES)

    delivered = 0
    for token in tokens:
        msg = messaging.Message(
            data={"type": "info", "tool_name": title, "message": body},
            token=token,
            android=messaging.AndroidConfig(priority="high"),
        )
        try:
            messaging.send(msg)
            delivered += 1
        except Exception:
            logger.exception("No se pudo enviar al token %s...", token[:12])
    return delivered
