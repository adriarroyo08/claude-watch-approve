import os
import tempfile
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

# Set test DB path before importing app
_fd, _test_db = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["CLAUDE_WATCH_DB_PATH"] = _test_db
os.environ["CLAUDE_WATCH_API_KEY"] = "test-api-key"

from server.main import app


@pytest.fixture(autouse=True)
def reset_db():
    """Reset database between tests."""
    from server.main import db
    db._conn.executescript("DELETE FROM approvals; DELETE FROM devices;")
    db._conn.commit()
    yield


@pytest.fixture
def headers():
    return {"X-Api-Key": "test-api-key"}


@pytest.fixture
def bad_headers():
    return {"X-Api-Key": "wrong-key"}


@pytest.mark.anyio
async def test_create_approval(headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("server.main.send_approval_notification", return_value=True):
            resp = await client.post(
                "/approval-request",
                json={"tool_name": "Bash", "tool_input_summary": "npm install", "context": "Installing deps"},
                headers=headers,
            )
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] is not None
    assert data["status"] == "pending"


@pytest.mark.anyio
async def test_create_approval_unauthorized():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/approval-request",
            json={"tool_name": "Bash", "tool_input_summary": "ls"},
            headers={"X-Api-Key": "wrong"},
        )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_get_approval_status(headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("server.main.send_approval_notification", return_value=True):
            create_resp = await client.post(
                "/approval-request",
                json={"tool_name": "Edit", "tool_input_summary": "src/app.ts"},
                headers=headers,
            )
        approval_id = create_resp.json()["id"]

        resp = await client.get(f"/approval-status/{approval_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


@pytest.mark.anyio
async def test_get_approval_status_not_found(headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/approval-status/nonexistent", headers=headers)
    assert resp.status_code == 404


@pytest.mark.anyio
async def test_approve_request(headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("server.main.send_approval_notification", return_value=True):
            create_resp = await client.post(
                "/approval-request",
                json={"tool_name": "Bash", "tool_input_summary": "rm -rf node_modules"},
                headers=headers,
            )
        approval_id = create_resp.json()["id"]

        resp = await client.post(
            f"/approval-response/{approval_id}",
            json={"approved": True},
            headers=headers,
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


@pytest.mark.anyio
async def test_deny_request(headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("server.main.send_approval_notification", return_value=True):
            create_resp = await client.post(
                "/approval-request",
                json={"tool_name": "Write", "tool_input_summary": "secrets.env"},
                headers=headers,
            )
        approval_id = create_resp.json()["id"]

        resp = await client.post(
            f"/approval-response/{approval_id}",
            json={"approved": False},
            headers=headers,
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "denied"


@pytest.mark.anyio
async def test_register_device(headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/register-device",
            json={"fcm_token": "token-abc123"},
            headers=headers,
        )
    assert resp.status_code == 200
