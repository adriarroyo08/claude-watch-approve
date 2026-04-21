import os
from pathlib import Path

API_KEY = os.environ.get("CLAUDE_WATCH_API_KEY", "change-me-in-production")
DB_PATH = os.environ.get("CLAUDE_WATCH_DB_PATH", str(Path(__file__).parent / "approvals.db"))
FCM_CREDENTIALS_PATH = os.environ.get("CLAUDE_WATCH_FCM_CREDENTIALS", str(Path(__file__).parent / "firebase-credentials.json"))
APPROVAL_TIMEOUT_SECONDS = int(os.environ.get("CLAUDE_WATCH_TIMEOUT", "300"))
