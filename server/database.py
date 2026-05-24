import sqlite3
from datetime import datetime, timezone


class ApprovalDB:
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fcm_token TEXT NOT NULL UNIQUE,
                updated_at TEXT NOT NULL
            );
        """)
        self._conn.commit()

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
