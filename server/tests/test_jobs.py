import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from server.database import ApprovalDB
from server.jobs import Busy, JobManager, RateLimited
from server.projects import Project
from server.runner import RunResult


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database = ApprovalDB(path)
    yield database
    database.close()
    os.unlink(path)


PROJECT = Project(id="ahorrapp", name="AhorrApp", path="/tmp")


def make_manager(db, results, gate=None):
    """results: lista de RunResult que el runner falso ira devolviendo."""
    calls = []

    async def fake_runner(cmd, cwd, timeout):
        calls.append({"cmd": cmd, "cwd": cwd, "timeout": timeout})
        if gate is not None:
            await gate.wait()
        return results.pop(0)

    manager = JobManager(db=db, runner=fake_runner)
    manager.calls = calls
    return manager


@pytest.mark.anyio
async def test_read_job_finishes_done(db):
    manager = make_manager(db, [RunResult(ok=True, short="Corto.", full="Corto.\n\nLargo.", session_id="s-1")])
    job_id = await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    job = db.get_job(job_id)
    assert job["status"] == "done"
    assert job["short_text"] == "Corto."
    assert job["full_text"] == "Corto.\n\nLargo."


@pytest.mark.anyio
async def test_read_job_runs_in_project_directory(db):
    manager = make_manager(db, [RunResult(ok=True, short="ok", full="ok")])
    await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    assert manager.calls[0]["cwd"] == "/tmp"


@pytest.mark.anyio
async def test_read_job_uses_the_read_timeout(db):
    manager = make_manager(db, [RunResult(ok=True, short="ok", full="ok")])
    await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    assert manager.calls[0]["timeout"] == 180


@pytest.mark.anyio
async def test_failed_run_becomes_error(db):
    manager = make_manager(db, [RunResult(ok=False, error="Tardo demasiado")])
    job_id = await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    job = db.get_job(job_id)
    assert job["status"] == "error"
    assert job["error"] == "Tardo demasiado"


@pytest.mark.anyio
async def test_second_submit_while_running_raises_busy(db):
    gate = asyncio.Event()
    manager = make_manager(db, [RunResult(ok=True, short="ok", full="ok")], gate=gate)
    await manager.submit(PROJECT, "primera", mode="read", thread="new")
    with pytest.raises(Busy):
        await manager.submit(PROJECT, "segunda", mode="read", thread="new")
    gate.set()
    await manager.wait_idle()


@pytest.mark.anyio
async def test_submit_allowed_again_after_finishing(db):
    manager = make_manager(db, [
        RunResult(ok=True, short="una", full="una"),
        RunResult(ok=True, short="dos", full="dos"),
    ])
    await manager.submit(PROJECT, "primera", mode="read", thread="new")
    await manager.wait_idle()
    job_id = await manager.submit(PROJECT, "segunda", mode="read", thread="new")
    await manager.wait_idle()
    assert db.get_job(job_id)["status"] == "done"


@pytest.mark.anyio
async def test_thread_new_ignores_stored_session(db):
    db.set_thread("ahorrapp", "session-vieja")
    manager = make_manager(db, [RunResult(ok=True, short="ok", full="ok", session_id="s-nueva")])
    await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    assert "--resume" not in manager.calls[0]["cmd"]
    assert db.get_thread("ahorrapp")["session_id"] == "s-nueva"


@pytest.mark.anyio
async def test_thread_continue_resumes_stored_session(db):
    db.set_thread("ahorrapp", "session-vieja")
    manager = make_manager(db, [RunResult(ok=True, short="ok", full="ok", session_id="session-vieja")])
    await manager.submit(PROJECT, "y eso por que", mode="read", thread="continue")
    await manager.wait_idle()
    cmd = manager.calls[0]["cmd"]
    assert cmd[cmd.index("--resume") + 1] == "session-vieja"


@pytest.mark.anyio
async def test_thread_continue_ignores_expired_session(db):
    db.set_thread("ahorrapp", "session-vieja")
    seven_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=7)).isoformat()
    db._conn.execute(
        "UPDATE threads SET updated_at = ? WHERE project_id = ?",
        (seven_hours_ago, "ahorrapp"),
    )
    db._conn.commit()

    manager = make_manager(db, [RunResult(ok=True, short="ok", full="ok", session_id="s-nueva")])
    await manager.submit(PROJECT, "y eso por que", mode="read", thread="continue")
    # _session_for no espera a nada: para cuando submit() devuelve el
    # control, la fila caducada ya se ha borrado, antes de que el job
    # arranque y escriba una fila nueva.
    assert db.get_thread("ahorrapp") is None

    await manager.wait_idle()

    assert "--resume" not in manager.calls[0]["cmd"]
    assert db.get_thread("ahorrapp")["session_id"] == "s-nueva"


@pytest.mark.anyio
async def test_unexpected_failure_marks_the_job_error(db):
    async def runner_que_revienta(cmd, cwd, timeout):
        raise RuntimeError("algo inesperado")

    manager = JobManager(db=db, runner=runner_que_revienta)
    job_id = await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    job = db.get_job(job_id)
    assert job["status"] == "error"
    assert "inesperado" in job["error"]


@pytest.mark.anyio
async def test_rate_limit_blocks_after_max(db, monkeypatch):
    monkeypatch.setattr("server.jobs.MAX_ASKS_PER_HOUR", 2)
    manager = make_manager(db, [
        RunResult(ok=True, short="a", full="a"),
        RunResult(ok=True, short="b", full="b"),
    ])
    await manager.submit(PROJECT, "una", mode="read", thread="new")
    await manager.wait_idle()
    await manager.submit(PROJECT, "dos", mode="read", thread="new")
    await manager.wait_idle()
    with pytest.raises(RateLimited):
        await manager.submit(PROJECT, "tres", mode="read", thread="new")
