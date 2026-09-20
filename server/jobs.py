import asyncio
import uuid
from datetime import datetime, timedelta, timezone

from server.config import (
    MAX_ASKS_PER_HOUR,
    READ_TIMEOUT,
    THREAD_TTL_HOURS,
    WRITE_TIMEOUT,
)
from server.projects import Project
from server.runner import build_command, run_claude


class Busy(Exception):
    """Ya hay una consulta en marcha."""


class RateLimited(Exception):
    """Se han gastado las consultas de esta hora."""


class JobManager:
    """Cola de profundidad 1 sobre el runner.

    No sabe nada de HTTP ni de como se construyen los comandos de Claude mas
    alla de pedirselos a runner.build_command. El runner se inyecta para que
    los tests puedan sustituirlo.
    """

    def __init__(self, db, runner=run_claude):
        self._db = db
        self._runner = runner
        self._task: asyncio.Task | None = None
        self._current_job_id: str | None = None

    @property
    def busy(self) -> bool:
        return self._task is not None and not self._task.done()

    async def submit(self, project: Project, prompt: str, mode: str, thread: str) -> str:
        if self.busy:
            raise Busy()

        one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        if self._db.count_jobs_since(one_hour_ago) >= MAX_ASKS_PER_HOUR:
            raise RateLimited()

        job_id = uuid.uuid4().hex
        self._db.create_job(job_id, project_id=project.id, mode=mode, prompt=prompt)
        self._current_job_id = job_id

        phase = "read" if mode == "read" else "plan"
        session_id = self._session_for(project.id) if thread == "continue" else None
        if thread == "new":
            self._db.clear_thread(project.id)

        self._task = asyncio.create_task(
            self._run(job_id, project, phase, prompt, session_id)
        )
        return job_id

    async def wait_idle(self):
        """Solo para tests y apagado: espera a que el job en curso termine."""
        if self._task is not None:
            await asyncio.shield(self._task)

    def _session_for(self, project_id: str) -> str | None:
        row = self._db.get_thread(project_id)
        if row is None:
            return None
        updated = datetime.fromisoformat(row["updated_at"])
        if datetime.now(timezone.utc) - updated > timedelta(hours=THREAD_TTL_HOURS):
            self._db.clear_thread(project_id)
            return None
        return row["session_id"]

    async def _run(self, job_id, project, phase, prompt, session_id):
        timeout = READ_TIMEOUT if phase == "read" else WRITE_TIMEOUT
        cmd = build_command(phase, prompt, session_id=session_id)
        result = await self._runner(cmd, project.path, timeout)

        if result.session_id:
            self._db.set_thread(project.id, result.session_id)

        if not result.ok:
            self._db.update_job(job_id, status="error", error=result.error)
            return

        if phase == "plan":
            self._db.update_job(
                job_id,
                status="awaiting_approval",
                plan=result.short,
                full_text=result.full,
                session_id=result.session_id,
            )
            return

        self._db.update_job(
            job_id,
            status="done",
            short_text=result.short,
            full_text=result.full,
            session_id=result.session_id,
        )
