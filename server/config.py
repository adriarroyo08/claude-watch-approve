import os
from pathlib import Path

from server.projects import parse_projects

API_KEY = os.environ.get("CLAUDE_WATCH_API_KEY", "change-me-in-production")
DB_PATH = os.environ.get("CLAUDE_WATCH_DB_PATH", str(Path(__file__).parent / "approvals.db"))
FCM_CREDENTIALS_PATH = os.environ.get("CLAUDE_WATCH_FCM_CREDENTIALS", str(Path(__file__).parent / "firebase-credentials.json"))

ASK_KEY = os.environ.get("CLAUDE_WATCH_ASK_KEY", "change-me-in-production")
ASK_MODEL = os.environ.get("CLAUDE_WATCH_ASK_MODEL", "sonnet")
CLAUDE_BIN = os.environ.get("CLAUDE_WATCH_CLAUDE_BIN", "claude")
READ_TIMEOUT = int(os.environ.get("CLAUDE_WATCH_READ_TIMEOUT", "180"))
WRITE_TIMEOUT = int(os.environ.get("CLAUDE_WATCH_WRITE_TIMEOUT", "600"))
MAX_ASKS_PER_HOUR = int(os.environ.get("CLAUDE_WATCH_MAX_ASKS_PER_HOUR", "20"))
THREAD_TTL_HOURS = int(os.environ.get("CLAUDE_WATCH_THREAD_TTL_HOURS", "6"))
APPROVAL_TTL_SECONDS = int(os.environ.get("CLAUDE_WATCH_APPROVAL_TTL", "300"))
PROJECTS = parse_projects(os.environ.get("CLAUDE_WATCH_PROJECTS", ""))
