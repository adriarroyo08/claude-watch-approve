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
    db._conn.executescript("DELETE FROM devices;")
    db._conn.commit()
    yield


@pytest.fixture
def headers():
    return {"X-Api-Key": "test-api-key"}


@pytest.fixture
def bad_headers():
    return {"X-Api-Key": "wrong-key"}


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
    assert resp.json()["status"] == "registered"


@pytest.mark.anyio
async def test_register_device_unauthorized(bad_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/register-device",
            json={"fcm_token": "token-abc123"},
            headers=bad_headers,
        )
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_notify_no_devices(headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("server.main.send_info_notification", return_value=False) as mock_notify:
            resp = await client.post(
                "/notify",
                json={"tool_name": "Bash", "summary": "Ran npm install"},
                headers=headers,
            )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "sent"
    assert data["devices"] == 0
    mock_notify.assert_called_once()


@pytest.mark.anyio
async def test_notify_with_result(headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Register a device first
        await client.post(
            "/register-device",
            json={"fcm_token": "device-token-xyz"},
            headers=headers,
        )
        with patch("server.main.send_info_notification", return_value=True) as mock_notify:
            resp = await client.post(
                "/notify",
                json={"tool_name": "Edit", "summary": "Edited file", "result": "Done"},
                headers=headers,
            )
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "sent"
    assert data["devices"] == 1
    mock_notify.assert_called_once_with(
        tokens=["device-token-xyz"],
        tool_name="Edit",
        message="Done",
    )


@pytest.mark.anyio
async def test_notify_uses_summary_when_no_result(headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.post(
            "/register-device",
            json={"fcm_token": "device-token-xyz"},
            headers=headers,
        )
        with patch("server.main.send_info_notification", return_value=True) as mock_notify:
            resp = await client.post(
                "/notify",
                json={"tool_name": "Read", "summary": "Read config.py"},
                headers=headers,
            )
    assert resp.status_code == 201
    mock_notify.assert_called_once_with(
        tokens=["device-token-xyz"],
        tool_name="Read",
        message="Read config.py",
    )


@pytest.mark.anyio
async def test_notify_unauthorized(bad_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/notify",
            json={"tool_name": "Bash", "summary": "ls"},
            headers=bad_headers,
        )
    assert resp.status_code == 403
