import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from server.main import app, db, job_manager
from server.runner import RunResult


@pytest.fixture(autouse=True)
def reset_db():
    task = job_manager._task
    if task is not None and not task.done():
        task.cancel()
    job_manager._task = None
    job_manager._current_job_id = None
    db._conn.executescript("DELETE FROM devices; DELETE FROM jobs; DELETE FROM threads;")
    db._conn.commit()
    yield


@pytest.fixture
def watch_headers():
    return {"X-Api-Key": "watch-key"}


@pytest.fixture
def hook_headers():
    return {"X-Api-Key": "test-api-key"}


def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.anyio
async def test_projects_lists_the_whitelist(watch_headers):
    async with client() as http:
        resp = await http.get("/projects", headers=watch_headers)
    assert resp.status_code == 200
    ids = [project["id"] for project in resp.json()["projects"]]
    assert ids == ["ahorrapp", "petwatch"]


@pytest.mark.anyio
async def test_projects_never_leaks_paths(watch_headers):
    """El reloj recibe id y nombre. La ruta no sale de aqui."""
    async with client() as http:
        resp = await http.get("/projects", headers=watch_headers)
    for project in resp.json()["projects"]:
        assert set(project) == {"id", "name"}
    assert "/tmp" not in resp.text


@pytest.mark.anyio
async def test_projects_rejects_the_hook_key(hook_headers):
    """La clave del hook no debe abrir los endpoints del reloj."""
    async with client() as http:
        resp = await http.get("/projects", headers=hook_headers)
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_notify_still_rejects_the_watch_key(watch_headers):
    """Y la del reloj no debe abrir los del hook."""
    async with client() as http:
        resp = await http.post(
            "/notify",
            json={"tool_name": "Bash", "summary": "ls"},
            headers=watch_headers,
        )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_ask_returns_job_id(watch_headers):
    async def fake_runner(cmd, cwd, timeout):
        return RunResult(ok=True, short="Corto.", full="Corto.\n\nLargo.", session_id="s-1")

    with patch.object(job_manager, "_runner", fake_runner):
        async with client() as http:
            resp = await http.post(
                "/ask",
                json={"project_id": "ahorrapp", "prompt": "que tal", "mode": "read", "thread": "new"},
                headers=watch_headers,
            )
            assert resp.status_code == 202
            job_id = resp.json()["job_id"]
            await job_manager.wait_idle()
            status = await http.get(f"/ask/{job_id}", headers=watch_headers)

    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "done"
    assert body["short"] == "Corto."
    assert body["full"] == "Corto.\n\nLargo."


@pytest.mark.anyio
async def test_ask_runs_in_the_right_directory(watch_headers):
    seen = {}

    async def fake_runner(cmd, cwd, timeout):
        seen["cwd"] = cwd
        return RunResult(ok=True, short="ok", full="ok")

    with patch.object(job_manager, "_runner", fake_runner):
        async with client() as http:
            await http.post(
                "/ask",
                json={"project_id": "ahorrapp", "prompt": "que tal", "mode": "read", "thread": "new"},
                headers=watch_headers,
            )
            await job_manager.wait_idle()
    assert seen["cwd"] == "/tmp"


@pytest.mark.anyio
async def test_ask_rejects_unknown_project(watch_headers):
    async with client() as http:
        resp = await http.post(
            "/ask",
            json={"project_id": "no-existe", "prompt": "que tal", "mode": "read", "thread": "new"},
            headers=watch_headers,
        )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_ask_rejects_path_traversal_as_project_id(watch_headers):
    async with client() as http:
        resp = await http.post(
            "/ask",
            json={"project_id": "../../etc", "prompt": "que tal", "mode": "read", "thread": "new"},
            headers=watch_headers,
        )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_ask_rejects_an_absolute_path_as_project_id(watch_headers):
    async with client() as http:
        resp = await http.post(
            "/ask",
            json={"project_id": "/etc/passwd", "prompt": "x", "mode": "read", "thread": "new"},
            headers=watch_headers,
        )
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_ask_rejects_too_long_prompt(watch_headers):
    async with client() as http:
        resp = await http.post(
            "/ask",
            json={"project_id": "ahorrapp", "prompt": "x" * 1001, "mode": "read", "thread": "new"},
            headers=watch_headers,
        )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_ask_rejects_empty_prompt(watch_headers):
    async with client() as http:
        resp = await http.post(
            "/ask",
            json={"project_id": "ahorrapp", "prompt": "", "mode": "read", "thread": "new"},
            headers=watch_headers,
        )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_ask_rejects_unknown_mode(watch_headers):
    async with client() as http:
        resp = await http.post(
            "/ask",
            json={"project_id": "ahorrapp", "prompt": "hola", "mode": "root", "thread": "new"},
            headers=watch_headers,
        )
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_ask_without_a_key_is_rejected():
    async with client() as http:
        resp = await http.post(
            "/ask",
            json={"project_id": "ahorrapp", "prompt": "hola", "mode": "read", "thread": "new"},
        )
    assert resp.status_code in (401, 403, 422)


@pytest.mark.anyio
async def test_ask_returns_409_when_busy(watch_headers):
    import asyncio
    gate = asyncio.Event()

    async def slow_runner(cmd, cwd, timeout):
        await gate.wait()
        return RunResult(ok=True, short="ok", full="ok")

    with patch.object(job_manager, "_runner", slow_runner):
        async with client() as http:
            first = await http.post(
                "/ask",
                json={"project_id": "ahorrapp", "prompt": "una", "mode": "read", "thread": "new"},
                headers=watch_headers,
            )
            assert first.status_code == 202
            second = await http.post(
                "/ask",
                json={"project_id": "ahorrapp", "prompt": "otra", "mode": "read", "thread": "new"},
                headers=watch_headers,
            )
            assert second.status_code == 409
        gate.set()
        await job_manager.wait_idle()


@pytest.mark.anyio
async def test_get_unknown_job_is_404(watch_headers):
    async with client() as http:
        resp = await http.get("/ask/no-existe", headers=watch_headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_watch_endpoints_refuse_the_default_key(monkeypatch):
    """Sin CLAUDE_WATCH_ASK_KEY puesta, no se abre: se rompe."""
    monkeypatch.setattr("server.main.ASK_KEY", "change-me-in-production")
    async with client() as http:
        resp = await http.get(
            "/projects", headers={"X-Api-Key": "change-me-in-production"}
        )
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_ask_refuses_the_default_key_too(monkeypatch):
    monkeypatch.setattr("server.main.ASK_KEY", "change-me-in-production")
    async with client() as http:
        resp = await http.post(
            "/ask",
            json={"project_id": "ahorrapp", "prompt": "hola", "mode": "read", "thread": "new"},
            headers={"X-Api-Key": "change-me-in-production"},
        )
    assert resp.status_code == 503


@pytest.mark.anyio
async def test_notify_still_works_with_the_hook_key(hook_headers):
    """El guard es solo del reloj: la via de notificaciones no se toca."""
    async with client() as http:
        with patch("server.main.send_info_notification", return_value=False):
            resp = await http.post(
                "/notify",
                json={"tool_name": "Bash", "summary": "ls"},
                headers=hook_headers,
            )
    assert resp.status_code == 201


@pytest.mark.anyio
async def test_a_non_ascii_key_is_rejected_not_a_crash():
    """Una cabecera con acentos no debe reventar la comparacion.

    httpx exige ascii puro para valores de cabecera str, asi que para
    simular al cliente real que manda bytes no-ascii se pasan los bytes
    ya codificados: eso es lo que de verdad le llega a Starlette.
    """
    async with client() as http:
        resp = await http.get(
            "/projects", headers=[(b"X-Api-Key", "café".encode("utf-8"))]
        )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_a_non_ascii_key_is_rejected_on_the_hook_path_too():
    async with client() as http:
        resp = await http.post(
            "/notify",
            json={"tool_name": "Bash", "summary": "ls"},
            headers=[(b"X-Api-Key", "café".encode("utf-8"))],
        )
    assert resp.status_code == 403


def test_every_route_declares_an_auth_dependency():
    """Ningun endpoint nuevo puede quedarse sin guardia por despiste."""
    from server.main import app, verify_api_key, verify_ask_key
    guards = {verify_api_key, verify_ask_key}
    sin_guardia = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if path in ("/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"):
            continue
        dependencias = {
            d.dependency for d in getattr(route, "dependencies", [])
        }
        if not (dependencias & guards):
            sin_guardia.append(path)
    assert sin_guardia == [], f"endpoints sin autenticacion: {sin_guardia}"


def test_startup_marks_orphaned_jobs_as_error():
    from server.main import _on_startup
    db.create_job("huerfano", project_id="ahorrapp", mode="read", prompt="x")
    assert db.get_job("huerfano")["status"] == "running"
    _on_startup()
    assert db.get_job("huerfano")["status"] == "error"


async def _submit_write_job(http, watch_headers, plan_result):
    async def fake_runner(cmd, cwd, timeout):
        return plan_result

    with patch.object(job_manager, "_runner", fake_runner):
        resp = await http.post(
            "/ask",
            json={"project_id": "ahorrapp", "prompt": "arregla el typo",
                  "mode": "write", "thread": "new"},
            headers=watch_headers,
        )
        await job_manager.wait_idle()
    return resp.json()["job_id"]


@pytest.mark.anyio
async def test_write_job_reports_plan(watch_headers):
    plan = RunResult(ok=True, short="Tocare 3 archivos.",
                     full="Tocare 3 archivos.\n\nDetalle.", session_id="s-1")
    async with client() as http:
        job_id = await _submit_write_job(http, watch_headers, plan)
        resp = await http.get(f"/ask/{job_id}", headers=watch_headers)
    assert resp.json()["status"] == "awaiting_approval"
    assert resp.json()["plan"] == "Tocare 3 archivos."


@pytest.mark.anyio
async def test_approve_runs_the_plan(watch_headers):
    plan = RunResult(ok=True, short="Tocare 3 archivos.", full="Detalle.", session_id="s-1")

    async def done_runner(cmd, cwd, timeout):
        return RunResult(ok=True, short="Hecho.", full="Hecho.", session_id="s-1")

    async with client() as http:
        job_id = await _submit_write_job(http, watch_headers, plan)
        with patch.object(job_manager, "_runner", done_runner):
            resp = await http.post(f"/ask/{job_id}/approve", headers=watch_headers)
            await job_manager.wait_idle()
            final = await http.get(f"/ask/{job_id}", headers=watch_headers)

    assert resp.status_code == 200
    assert final.json()["status"] == "done"
    assert final.json()["short"] == "Hecho."


@pytest.mark.anyio
async def test_approve_on_a_read_job_is_409(watch_headers):
    async def fake_runner(cmd, cwd, timeout):
        return RunResult(ok=True, short="ok", full="ok")

    with patch.object(job_manager, "_runner", fake_runner):
        async with client() as http:
            resp = await http.post(
                "/ask",
                json={"project_id": "ahorrapp", "prompt": "que tal", "mode": "read", "thread": "new"},
                headers=watch_headers,
            )
            job_id = resp.json()["job_id"]
            await job_manager.wait_idle()
            approve = await http.post(f"/ask/{job_id}/approve", headers=watch_headers)
    assert approve.status_code == 409


@pytest.mark.anyio
async def test_approve_of_unknown_job_is_404(watch_headers):
    async with client() as http:
        resp = await http.post("/ask/no-existe/approve", headers=watch_headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_approve_says_why_it_refused(watch_headers):
    """En un reloj no puedes ir a mirar un log: el motivo tiene que viajar."""
    async def fake_runner(cmd, cwd, timeout):
        return RunResult(ok=True, short="ok", full="ok")

    with patch.object(job_manager, "_runner", fake_runner):
        async with client() as http:
            resp = await http.post(
                "/ask",
                json={"project_id": "ahorrapp", "prompt": "que tal", "mode": "read", "thread": "new"},
                headers=watch_headers,
            )
            job_id = resp.json()["job_id"]
            await job_manager.wait_idle()
            approve = await http.post(f"/ask/{job_id}/approve", headers=watch_headers)
    assert "esperando aprobacion" in approve.json()["detail"]


@pytest.mark.anyio
async def test_approve_needs_the_watch_key(hook_headers):
    async with client() as http:
        resp = await http.post("/ask/cualquiera/approve", headers=hook_headers)
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_cancel_marks_it_cancelled(watch_headers):
    import asyncio
    gate = asyncio.Event()

    async def slow_runner(cmd, cwd, timeout):
        await gate.wait()
        return RunResult(ok=True, short="ok", full="ok")

    with patch.object(job_manager, "_runner", slow_runner):
        async with client() as http:
            resp = await http.post(
                "/ask",
                json={"project_id": "ahorrapp", "prompt": "que tal", "mode": "read", "thread": "new"},
                headers=watch_headers,
            )
            job_id = resp.json()["job_id"]
            await asyncio.sleep(0)
            cancel = await http.post(f"/ask/{job_id}/cancel", headers=watch_headers)
            assert cancel.status_code == 200
            assert cancel.json()["status"] == "cancelled"
            gate.set()
            final = await http.get(f"/ask/{job_id}", headers=watch_headers)
    assert final.json()["status"] == "cancelled"


@pytest.mark.anyio
async def test_cancel_does_not_lie_about_a_finished_job(watch_headers):
    """Lo peor que puede decir esto: 'cancelado' de algo ya hecho en disco."""
    async def fake_runner(cmd, cwd, timeout):
        return RunResult(ok=True, short="Hecho.", full="Hecho.")

    with patch.object(job_manager, "_runner", fake_runner):
        async with client() as http:
            resp = await http.post(
                "/ask",
                json={"project_id": "ahorrapp", "prompt": "que tal", "mode": "read", "thread": "new"},
                headers=watch_headers,
            )
            job_id = resp.json()["job_id"]
            await job_manager.wait_idle()
            cancel = await http.post(f"/ask/{job_id}/cancel", headers=watch_headers)
            final = await http.get(f"/ask/{job_id}", headers=watch_headers)

    assert cancel.status_code == 200
    assert cancel.json()["status"] == "done"
    assert final.json()["status"] == "done"
    assert final.json()["short"] == "Hecho."


@pytest.mark.anyio
async def test_cancel_of_unknown_job_is_404(watch_headers):
    async with client() as http:
        resp = await http.post("/ask/no-existe/cancel", headers=watch_headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_to_phone_sends_the_full_text(watch_headers, hook_headers):
    async def fake_runner(cmd, cwd, timeout):
        return RunResult(ok=True, short="Corto.", full="Corto.\n\nTodo el detalle.")

    with patch.object(job_manager, "_runner", fake_runner):
        async with client() as http:
            await http.post(
                "/register-device",
                json={"fcm_token": "device-token-xyz"},
                headers=hook_headers,
            )
            resp = await http.post(
                "/ask",
                json={"project_id": "ahorrapp", "prompt": "que tal", "mode": "read", "thread": "new"},
                headers=watch_headers,
            )
            job_id = resp.json()["job_id"]
            await job_manager.wait_idle()
            with patch("server.main.send_full_text", return_value=1) as mock_send:
                sent = await http.post(f"/ask/{job_id}/to-phone", headers=watch_headers)

    assert sent.status_code == 200
    mock_send.assert_called_once_with(
        tokens=["device-token-xyz"],
        title="Respuesta",
        text="Corto.\n\nTodo el detalle.",
    )


@pytest.mark.anyio
async def test_to_phone_reports_failure_when_nothing_was_delivered(watch_headers, hook_headers):
    async def fake_runner(cmd, cwd, timeout):
        return RunResult(ok=True, short="Corto.", full="Corto.\n\nTodo el detalle.")

    with patch.object(job_manager, "_runner", fake_runner):
        async with client() as http:
            await http.post(
                "/register-device",
                json={"fcm_token": "device-token-xyz"},
                headers=hook_headers,
            )
            resp = await http.post(
                "/ask",
                json={"project_id": "ahorrapp", "prompt": "que tal", "mode": "read", "thread": "new"},
                headers=watch_headers,
            )
            job_id = resp.json()["job_id"]
            await job_manager.wait_idle()
            with patch("server.main.send_full_text", return_value=0):
                sent = await http.post(f"/ask/{job_id}/to-phone", headers=watch_headers)

    assert sent.status_code == 502


@pytest.mark.anyio
async def test_to_phone_on_unfinished_job_is_409(watch_headers):
    import asyncio
    gate = asyncio.Event()

    async def slow_runner(cmd, cwd, timeout):
        await gate.wait()
        return RunResult(ok=True, short="ok", full="ok")

    with patch.object(job_manager, "_runner", slow_runner):
        async with client() as http:
            resp = await http.post(
                "/ask",
                json={"project_id": "ahorrapp", "prompt": "que tal", "mode": "read", "thread": "new"},
                headers=watch_headers,
            )
            job_id = resp.json()["job_id"]
            sent = await http.post(f"/ask/{job_id}/to-phone", headers=watch_headers)
            assert sent.status_code == 409
        gate.set()
        await job_manager.wait_idle()


@pytest.mark.anyio
async def test_to_phone_of_unknown_job_is_404(watch_headers):
    async with client() as http:
        resp = await http.post("/ask/no-existe/to-phone", headers=watch_headers)
    assert resp.status_code == 404
