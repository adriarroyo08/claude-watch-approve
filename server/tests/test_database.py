import os
import tempfile
import pytest
from server.database import ApprovalDB


@pytest.fixture
def db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    database = ApprovalDB(path)
    yield database
    database.close()
    os.unlink(path)


def test_create_approval(db):
    approval = db.create_approval(
        tool_name="Bash",
        tool_input_summary="npm install express",
        context="Installing dependencies",
    )
    assert approval["id"] is not None
    assert approval["tool_name"] == "Bash"
    assert approval["tool_input_summary"] == "npm install express"
    assert approval["status"] == "pending"


def test_get_approval(db):
    created = db.create_approval("Edit", "src/app.ts", None)
    fetched = db.get_approval(created["id"])
    assert fetched is not None
    assert fetched["id"] == created["id"]
    assert fetched["tool_name"] == "Edit"
    assert fetched["status"] == "pending"


def test_get_approval_not_found(db):
    result = db.get_approval("nonexistent-id")
    assert result is None


def test_resolve_approval_approved(db):
    created = db.create_approval("Bash", "rm -rf node_modules", None)
    result = db.resolve_approval(created["id"], "approved")
    assert result is True
    fetched = db.get_approval(created["id"])
    assert fetched["status"] == "approved"
    assert fetched["resolved_at"] is not None


def test_resolve_approval_denied(db):
    created = db.create_approval("Write", "config.json", None)
    result = db.resolve_approval(created["id"], "denied")
    assert result is True
    fetched = db.get_approval(created["id"])
    assert fetched["status"] == "denied"


def test_resolve_already_resolved(db):
    created = db.create_approval("Bash", "ls", None)
    db.resolve_approval(created["id"], "approved")
    result = db.resolve_approval(created["id"], "denied")
    assert result is False


def test_register_device(db):
    db.register_device("fcm-token-abc123")
    tokens = db.get_device_tokens()
    assert "fcm-token-abc123" in tokens


def test_register_device_updates_existing(db):
    db.register_device("old-token")
    db.register_device("new-token")
    tokens = db.get_device_tokens()
    assert "new-token" in tokens
