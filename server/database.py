import sqlite3
import uuid
from datetime import datetime, timezone


class ApprovalDB:
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS approvals (
                id TEXT PRIMARY KEY,
                tool_name TEXT NOT NULL,
                tool_input_summary TEXT NOT NULL,
                context TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                created_at TEXT NOT NULL,
                resolved_at TEXT
            );
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fcm_token TEXT NOT NULL UNIQUE,
                updated_at TEXT NOT NULL
            );
        """)
        self._conn.commit()

    def create_approval(self, tool_name: str, tool_input_summary: str, context: str | None) -> dict:
        approval_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO approvals (id, tool_name, tool_input_summary, context, status, created_at) VALUES (?, ?, ?, ?, 'pending', ?)",
            (approval_id, tool_name, tool_input_summary, context, now),
        )
        self._conn.commit()
        return self.get_approval(approval_id)

    def get_approval(self, approval_id: str) -> dict | None:
        row = self._conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if row is None:
            return None
        return dict(row)

    def resolve_approval(self, approval_id: str, status: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            "UPDATE approvals SET status = ?, resolved_at = ? WHERE id = ? AND status = 'pending'",
            (status, now, approval_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def register_device(self, fcm_token: str):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO devices (fcm_token, updated_at) VALUES (?, ?) ON CONFLICT(fcm_token) DO UPDATE SET updated_at = ?",
            (fcm_token, now, now),
        )
        self._conn.commit()

    def get_device_tokens(self) -> list[str]:
        rows = self._conn.execute("SELECT fcm_token FROM devices").fetchall()
        return [row["fcm_token"] for row in rows]

    def close(self):
        self._conn.close()
