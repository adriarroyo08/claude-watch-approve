import os
import tempfile
import time
import pytest
from server.database import ApprovalDB, to_utc_iso


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


from datetime import datetime, timedelta, timezone


def test_create_and_get_job(db):
    db.create_job("job-1", project_id="ahorrapp", mode="read", prompt="que tal")
    job = db.get_job("job-1")
    assert job["status"] == "running"
    assert job["project_id"] == "ahorrapp"
    assert job["prompt"] == "que tal"


def test_get_job_missing_returns_none(db):
    assert db.get_job("no-existe") is None


def test_update_job_sets_fields(db):
    db.create_job("job-1", project_id="ahorrapp", mode="read", prompt="que tal")
    db.update_job("job-1", status="done", short_text="corto", full_text="corto\n\nlargo")
    job = db.get_job("job-1")
    assert job["status"] == "done"
    assert job["short_text"] == "corto"
    assert job["full_text"] == "corto\n\nlargo"


def test_orphan_running_jobs_marks_them_error(db):
    db.create_job("job-1", project_id="ahorrapp", mode="read", prompt="que tal")
    db.create_job("job-2", project_id="ahorrapp", mode="read", prompt="otra")
    db.update_job("job-2", status="done")
    db.orphan_running_jobs()
    assert db.get_job("job-1")["status"] == "error"
    assert db.get_job("job-1")["error"] == "Se interrumpio al reiniciar el servidor"
    assert db.get_job("job-2")["status"] == "done"


def test_count_jobs_since(db):
    db.create_job("job-1", project_id="ahorrapp", mode="read", prompt="una")
    db.create_job("job-2", project_id="ahorrapp", mode="read", prompt="otra")
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    assert db.count_jobs_since(past.isoformat()) == 2
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    assert db.count_jobs_since(future.isoformat()) == 0


def test_count_jobs_since_normalises_other_offsets(db):
    db.create_job("job-1", project_id="ahorrapp", mode="read", prompt="una")
    # El mismo instante que "hace una hora", escrito en +02:00
    past_utc = datetime.now(timezone.utc) - timedelta(hours=1)
    past_in_madrid = past_utc.astimezone(timezone(timedelta(hours=2)))
    assert past_in_madrid.isoformat() != past_utc.isoformat()
    assert db.count_jobs_since(past_in_madrid.isoformat()) == 1


def test_to_utc_iso_converts_other_offsets():
    assert to_utc_iso("2026-09-20T15:42:53+02:00") == "2026-09-20T13:42:53+00:00"


@pytest.fixture
def local_time_in_madrid():
    """Pone el huso del sistema en UTC+2 mientras dura el test.

    En una maquina en UTC, `naive.astimezone(utc)` da el mismo resultado
    que tratar la marca como UTC, asi que el test no podria distinguir si
    el guard de to_utc_iso existe. Con el reloj local en Madrid las dos
    lecturas difieren y el test si muerde.
    """
    previous = os.environ.get("TZ")
    os.environ["TZ"] = "Europe/Madrid"
    time.tzset()
    yield
    if previous is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = previous
    time.tzset()


def test_to_utc_iso_treats_naive_as_utc(local_time_in_madrid):
    assert to_utc_iso("2026-09-20T13:42:53") == "2026-09-20T13:42:53+00:00"


def test_to_utc_iso_leaves_utc_untouched():
    assert to_utc_iso("2026-09-20T13:42:53+00:00") == "2026-09-20T13:42:53+00:00"


def test_update_job_rejects_unknown_field(db):
    db.create_job("job-1", project_id="ahorrapp", mode="read", prompt="que tal")
    with pytest.raises(ValueError):
        db.update_job("job-1", bogus_column="x")


def test_update_job_rejects_sql_shaped_field_name(db):
    db.create_job("job-1", project_id="ahorrapp", mode="read", prompt="que tal")
    with pytest.raises(ValueError):
        db.update_job("job-1", **{"status = 'pwned' --": "x"})
    assert db.get_job("job-1")["status"] == "running"


def test_thread_roundtrip(db):
    assert db.get_thread("ahorrapp") is None
    db.set_thread("ahorrapp", "session-abc")
    assert db.get_thread("ahorrapp")["session_id"] == "session-abc"
    db.clear_thread("ahorrapp")
    assert db.get_thread("ahorrapp") is None


def test_set_thread_overwrites(db):
    db.set_thread("ahorrapp", "session-vieja")
    db.set_thread("ahorrapp", "session-nueva")
    assert db.get_thread("ahorrapp")["session_id"] == "session-nueva"
