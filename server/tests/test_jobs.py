import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest

from server.database import ApprovalDB
from server.jobs import Busy, JobManager, NotApprovable, RateLimited
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
    """Devuelve (manager, calls) — calls registra lo que recibio el runner falso."""
    calls = []

    async def fake_runner(cmd, cwd, timeout):
        calls.append({"cmd": cmd, "cwd": cwd, "timeout": timeout})
        if gate is not None:
            await gate.wait()
        return results.pop(0)

    return JobManager(db=db, runner=fake_runner), calls


@pytest.mark.anyio
async def test_read_job_finishes_done(db):
    manager, calls = make_manager(db, [RunResult(ok=True, short="Corto.", full="Corto.\n\nLargo.", session_id="s-1")])
    job_id = await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    job = db.get_job(job_id)
    assert job["status"] == "done"
    assert job["short_text"] == "Corto."
    assert job["full_text"] == "Corto.\n\nLargo."


@pytest.mark.anyio
async def test_read_job_runs_in_project_directory(db):
    manager, calls = make_manager(db, [RunResult(ok=True, short="ok", full="ok")])
    await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    assert calls[0]["cwd"] == "/tmp"


@pytest.mark.anyio
async def test_read_job_uses_the_read_timeout(db):
    manager, calls = make_manager(db, [RunResult(ok=True, short="ok", full="ok")])
    await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    assert calls[0]["timeout"] == 180


@pytest.mark.anyio
async def test_failed_run_becomes_error(db):
    manager, calls = make_manager(db, [RunResult(ok=False, error="Tardo demasiado")])
    job_id = await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    job = db.get_job(job_id)
    assert job["status"] == "error"
    assert job["error"] == "Tardo demasiado"


@pytest.mark.anyio
async def test_second_submit_while_running_raises_busy(db):
    gate = asyncio.Event()
    manager, calls = make_manager(db, [RunResult(ok=True, short="ok", full="ok")], gate=gate)
    await manager.submit(PROJECT, "primera", mode="read", thread="new")
    with pytest.raises(Busy):
        await manager.submit(PROJECT, "segunda", mode="read", thread="new")
    gate.set()
    await manager.wait_idle()


@pytest.mark.anyio
async def test_submit_allowed_again_after_finishing(db):
    manager, calls = make_manager(db, [
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
    manager, calls = make_manager(db, [RunResult(ok=True, short="ok", full="ok", session_id="s-nueva")])
    await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    assert "--resume" not in calls[0]["cmd"]
    assert db.get_thread("ahorrapp")["session_id"] == "s-nueva"


@pytest.mark.anyio
async def test_thread_continue_resumes_stored_session(db):
    db.set_thread("ahorrapp", "session-vieja")
    manager, calls = make_manager(db, [RunResult(ok=True, short="ok", full="ok", session_id="session-vieja")])
    await manager.submit(PROJECT, "y eso por que", mode="read", thread="continue")
    await manager.wait_idle()
    cmd = calls[0]["cmd"]
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

    manager, calls = make_manager(db, [RunResult(ok=True, short="ok", full="ok", session_id="s-nueva")])
    await manager.submit(PROJECT, "y eso por que", mode="read", thread="continue")
    # _session_for no espera a nada: para cuando submit() devuelve el
    # control, la fila caducada ya se ha borrado, antes de que el job
    # arranque y escriba una fila nueva.
    assert db.get_thread("ahorrapp") is None

    await manager.wait_idle()

    assert "--resume" not in calls[0]["cmd"]
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
async def test_write_job_reaches_awaiting_approval(db):
    manager, calls = make_manager(db, [
        RunResult(ok=True, short="Tocare 3 archivos.",
                  full="Tocare 3 archivos.\n\nDetalle.", session_id="s-1"),
    ])
    job_id = await manager.submit(PROJECT, "arregla el typo", mode="write", thread="new")
    await manager.wait_idle()
    job = db.get_job(job_id)
    assert job["status"] == "awaiting_approval"
    assert job["plan"] == "Tocare 3 archivos."
    assert job["session_id"] == "s-1"
    assert job["short_text"] is None          # el contrato: plan si, short no
    assert calls[0]["timeout"] == 600         # WRITE_TIMEOUT, no READ_TIMEOUT
    assert calls[0]["cmd"][calls[0]["cmd"].index("--permission-mode") + 1] == "plan"


@pytest.mark.anyio
async def test_plan_without_session_is_an_error_not_approvable(db):
    manager, _ = make_manager(db, [RunResult(ok=True, short="plan", full="plan")])
    job_id = await manager.submit(PROJECT, "arregla el typo", mode="write", thread="new")
    await manager.wait_idle()
    job = db.get_job(job_id)
    assert job["status"] == "error"
    with pytest.raises(NotApprovable):
        await manager.approve(job_id, PROJECT)


@pytest.mark.anyio
async def test_rate_limit_blocks_after_max(db, monkeypatch):
    monkeypatch.setattr("server.jobs.MAX_ASKS_PER_HOUR", 2)
    manager, calls = make_manager(db, [
        RunResult(ok=True, short="a", full="a"),
        RunResult(ok=True, short="b", full="b"),
    ])
    await manager.submit(PROJECT, "una", mode="read", thread="new")
    await manager.wait_idle()
    await manager.submit(PROJECT, "dos", mode="read", thread="new")
    await manager.wait_idle()
    with pytest.raises(RateLimited):
        await manager.submit(PROJECT, "tres", mode="read", thread="new")


@pytest.mark.anyio
async def test_approve_runs_exec_phase_resuming_the_session(db):
    manager, calls = make_manager(db, [
        RunResult(ok=True, short="plan", full="plan", session_id="s-1"),
        RunResult(ok=True, short="Hecho.", full="Hecho.", session_id="s-1"),
    ])
    job_id = await manager.submit(PROJECT, "arregla el typo", mode="write", thread="new")
    await manager.wait_idle()
    await manager.approve(job_id, PROJECT)
    await manager.wait_idle()
    job = db.get_job(job_id)
    assert job["status"] == "done"
    assert job["short_text"] == "Hecho."
    exec_cmd = calls[1]["cmd"]
    assert exec_cmd[exec_cmd.index("--permission-mode") + 1] == "acceptEdits"
    assert exec_cmd[exec_cmd.index("--resume") + 1] == "s-1"


@pytest.mark.anyio
async def test_nothing_runs_before_approving(db):
    """El plan se queda quieto: un solo comando hasta que apruebas."""
    manager, calls = make_manager(db, [
        RunResult(ok=True, short="plan", full="plan", session_id="s-1"),
        RunResult(ok=True, short="Hecho.", full="Hecho.", session_id="s-1"),
    ])
    await manager.submit(PROJECT, "arregla el typo", mode="write", thread="new")
    await manager.wait_idle()
    assert len(calls) == 1
    assert calls[0]["cmd"][calls[0]["cmd"].index("--permission-mode") + 1] == "plan"
    assert "acceptEdits" not in calls[0]["cmd"]


@pytest.mark.anyio
async def test_approve_rejects_job_that_is_not_awaiting(db):
    manager, _ = make_manager(db, [RunResult(ok=True, short="ok", full="ok")])
    job_id = await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    with pytest.raises(NotApprovable):
        await manager.approve(job_id, PROJECT)


@pytest.mark.anyio
async def test_approve_rejects_unknown_job(db):
    manager, _ = make_manager(db, [])
    with pytest.raises(NotApprovable):
        await manager.approve("no-existe", PROJECT)


@pytest.mark.anyio
async def test_approve_expires_after_ttl(db, monkeypatch):
    monkeypatch.setattr("server.jobs.APPROVAL_TTL_SECONDS", 0)
    manager, _ = make_manager(db, [RunResult(ok=True, short="plan", full="plan", session_id="s-1")])
    job_id = await manager.submit(PROJECT, "arregla el typo", mode="write", thread="new")
    await manager.wait_idle()
    await asyncio.sleep(0.01)
    with pytest.raises(NotApprovable):
        await manager.approve(job_id, PROJECT)
    assert db.get_job(job_id)["status"] == "cancelled"


@pytest.mark.anyio
async def test_expired_approval_runs_nothing(db, monkeypatch):
    """Caducar no debe ejecutar el plan por accidente."""
    monkeypatch.setattr("server.jobs.APPROVAL_TTL_SECONDS", 0)
    manager, calls = make_manager(db, [
        RunResult(ok=True, short="plan", full="plan", session_id="s-1"),
        RunResult(ok=True, short="NO DEBERIA CORRER", full="x", session_id="s-1"),
    ])
    job_id = await manager.submit(PROJECT, "arregla el typo", mode="write", thread="new")
    await manager.wait_idle()
    await asyncio.sleep(0.01)
    with pytest.raises(NotApprovable):
        await manager.approve(job_id, PROJECT)
    assert len(calls) == 1


@pytest.mark.anyio
async def test_cancel_stops_a_run_that_is_really_in_flight(db):
    gate = asyncio.Event()
    manager, calls = make_manager(db, [RunResult(ok=True, short="ok", full="ok")], gate=gate)
    job_id = await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await asyncio.sleep(0)   # deja que la task arranque de verdad
    assert calls, "el runner no arranco: sin esto el test no prueba nada"
    assert manager.busy is True
    await manager.cancel(job_id)
    gate.set()
    await asyncio.sleep(0)
    assert db.get_job(job_id)["status"] == "cancelled"
    assert manager.busy is False


@pytest.mark.anyio
async def test_cancel_frees_the_slot(db):
    gate = asyncio.Event()
    manager, calls = make_manager(db, [
        RunResult(ok=True, short="a", full="a"),
        RunResult(ok=True, short="b", full="b"),
    ], gate=gate)
    first = await manager.submit(PROJECT, "primera", mode="read", thread="new")
    await asyncio.sleep(0)
    assert calls, "el runner no arranco"
    await manager.cancel(first)
    gate.set()
    second = await manager.submit(PROJECT, "segunda", mode="read", thread="new")
    await manager.wait_idle()
    assert db.get_job(second)["status"] == "done"


@pytest.mark.anyio
async def test_cancel_does_not_clobber_a_finished_job(db):
    """Lo peor que puede hacer esto: decir 'cancelado' de algo ya hecho."""
    manager, _ = make_manager(db, [RunResult(ok=True, short="Hecho.", full="Hecho.")])
    job_id = await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    assert db.get_job(job_id)["status"] == "done"
    assert await manager.cancel(job_id) == "done"
    job = db.get_job(job_id)
    assert job["status"] == "done"
    assert job["short_text"] == "Hecho."


@pytest.mark.anyio
async def test_cancel_of_unknown_job_returns_none(db):
    manager, _ = make_manager(db, [])
    assert await manager.cancel("no-existe") is None


@pytest.mark.anyio
async def test_approve_rejects_a_different_project(db):
    """Un plan de un repo no se ejecuta en el directorio de otro."""
    otro = Project(id="petwatch", name="PetWatch1", path="/tmp")
    manager, calls = make_manager(db, [
        RunResult(ok=True, short="plan", full="plan", session_id="s-1"),
        RunResult(ok=True, short="NO DEBERIA CORRER", full="x", session_id="s-1"),
    ])
    job_id = await manager.submit(PROJECT, "arregla el typo", mode="write", thread="new")
    await manager.wait_idle()
    with pytest.raises(NotApprovable):
        await manager.approve(job_id, otro)
    assert len(calls) == 1


@pytest.mark.anyio
async def test_cancelling_an_old_plan_does_not_kill_the_running_job(db):
    """Cancelar un plan sin aprobar no debe tumbar el job que corre ahora.

    _current_job_id no se resetea al terminar un job, asi que apunta al
    ultimo. Esta es la prueba de que la guarda lo tiene en cuenta.
    """
    gate = asyncio.Event()
    calls = []

    async def runner(cmd, cwd, timeout):
        calls.append(cmd)
        if len(calls) > 1:          # solo el segundo se queda esperando
            await gate.wait()
        return RunResult(ok=True, short="ok", full="ok", session_id="s-1")

    manager = JobManager(db=db, runner=runner)

    plan_id = await manager.submit(PROJECT, "arregla el typo", mode="write", thread="new")
    await manager.wait_idle()
    assert db.get_job(plan_id)["status"] == "awaiting_approval"

    running_id = await manager.submit(PROJECT, "otra cosa", mode="read", thread="new")
    await asyncio.sleep(0)
    assert manager.busy is True, "el segundo job no arranco: el test no probaria nada"

    assert await manager.cancel(plan_id) == "cancelled"
    assert manager.busy is True, "cancelar el plan viejo tumbo el job en curso"

    gate.set()
    await manager.wait_idle()
    assert db.get_job(plan_id)["status"] == "cancelled"
    assert db.get_job(running_id)["status"] == "done"
