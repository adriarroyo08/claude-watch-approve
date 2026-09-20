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

            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT NOT NULL,
                short_text TEXT,
                full_text TEXT,
                plan TEXT,
                error TEXT,
                session_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS threads (
                project_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
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

    _JOB_FIELDS = (
        "status", "short_text", "full_text", "plan", "error", "session_id",
    )

    def create_job(self, job_id: str, project_id: str, mode: str, prompt: str):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO jobs (id, project_id, mode, prompt, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'running', ?, ?)",
            (job_id, project_id, mode, prompt, now, now),
        )
        self._conn.commit()

    def get_job(self, job_id: str):
        return self._conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()

    def update_job(self, job_id: str, **fields):
        unknown = set(fields) - set(self._JOB_FIELDS)
        if unknown:
            raise ValueError(f"campos desconocidos: {sorted(unknown)}")
        if not fields:
            return
        assignments = ", ".join(f"{name} = ?" for name in fields)
        values = [*fields.values(), datetime.now(timezone.utc).isoformat(), job_id]
        self._conn.execute(
            f"UPDATE jobs SET {assignments}, updated_at = ? WHERE id = ?", values
        )
        self._conn.commit()

    def orphan_running_jobs(self):
        """Al arrancar, los jobs que quedaron corriendo ya no tienen proceso."""
        self._conn.execute(
            "UPDATE jobs SET status = 'error', error = ?, updated_at = ? "
            "WHERE status IN ('running', 'awaiting_approval')",
            ("Se interrumpio al reiniciar el servidor",
             datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def count_jobs_since(self, iso_timestamp: str) -> int:
        """Cuenta los jobs creados desde ese instante.

        Normaliza a UTC antes de comparar: las marcas se guardan como texto
        y una comparacion de cadenas con otro huso daria un resultado
        silenciosamente equivocado.
        """
        since = datetime.fromisoformat(iso_timestamp)
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE created_at >= ?",
            (since.astimezone(timezone.utc).isoformat(),),
        ).fetchone()
        return row["n"]

    def get_thread(self, project_id: str):
        return self._conn.execute(
            "SELECT * FROM threads WHERE project_id = ?", (project_id,)
        ).fetchone()

    def set_thread(self, project_id: str, session_id: str):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO threads (project_id, session_id, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(project_id) DO UPDATE SET session_id = ?, updated_at = ?",
            (project_id, session_id, now, session_id, now),
        )
        self._conn.commit()

    def clear_thread(self, project_id: str):
        self._conn.execute("DELETE FROM threads WHERE project_id = ?", (project_id,))
        self._conn.commit()

    def close(self):
        self._conn.close()
