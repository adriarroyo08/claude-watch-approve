import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from server.main import app, db, job_manager
from server.runner import RunResult


@pytest.fixture(autouse=True)
def reset_db():
    db._conn.executescript("DELETE FROM devices; DELETE FROM jobs; DELETE FROM threads;")
    db._conn.commit()
    job_manager._task = None
    job_manager._current_job_id = None
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
