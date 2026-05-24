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


def test_register_device(db):
    db.register_device("fcm-token-abc123")
    tokens = db.get_device_tokens()
    assert "fcm-token-abc123" in tokens


def test_register_device_updates_existing(db):
    db.register_device("old-token")
    db.register_device("new-token")
    tokens = db.get_device_tokens()
    assert "new-token" in tokens


def test_register_device_upsert(db):
    db.register_device("same-token")
    db.register_device("same-token")
    tokens = db.get_device_tokens()
    assert tokens.count("same-token") == 1


def test_get_device_tokens_empty(db):
    tokens = db.get_device_tokens()
    assert tokens == []


def test_get_device_tokens_multiple(db):
    db.register_device("token-1")
    db.register_device("token-2")
    db.register_device("token-3")
    tokens = db.get_device_tokens()
    assert set(tokens) == {"token-1", "token-2", "token-3"}
