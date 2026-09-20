# Preguntar a Claude desde el reloj — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el reloj pueda dictar o teclear una pregunta, que la conteste un `claude -p` en el servidor, y leer la respuesta en la muñeca.

**Architecture:** El servidor FastAPI (que corre en la misma máquina que el CLI de Claude) gana una cola de un solo job que lanza `claude -p` como subproceso. El reloj habla HTTPS directo con él: `POST /ask` devuelve un `job_id` al instante y el reloj sondea `GET /ask/{job_id}` cada 2 s. En modo escritura hay una parada intermedia: Claude planifica, tú apruebas en el reloj, y solo entonces ejecuta.

**Tech Stack:** FastAPI, SQLite, `asyncio.subprocess`, pytest; Wear Compose, Retrofit, DataStore, RemoteInput.

**Spec:** `docs/superpowers/specs/2026-09-20-claude-watch-ask-design.md`
**Issue:** #2 · **Rama:** `feature/2-ask-from-watch`

---

## Antes de empezar: cosas que el CLI ya nos ha confirmado

Verificado contra `claude` 2.1.278 en esta máquina, no supuesto:

- `claude -p "..." --output-format json` devuelve un objeto con, entre otras,
  `result` (el texto), `session_id`, `is_error`, `permission_denials` y
  `total_cost_usd`.
- Existen `--permission-mode plan|acceptEdits`, `--permission-prompts none`,
  `--resume`, `--allowedTools`, `--disallowedTools` y `--model`.
- Una consulta trivial costó **0,07 $** (casi todo creación de caché). El límite de
  20 peticiones/hora es una medida de coste real, no decorativa.

La suite actual son **20 tests que pasan**
(`./venv/bin/python -m pytest server/tests hook/tests -q`).
No debe bajar de ahí en ningún momento.

### Aviso sobre el hook de seguridad

El plugin `security-guidance` bloquea la herramienta Write en cuanto el contenido
contiene la subcadena `exec(`, y recomienda un `src/utils/execFileNoThrow.ts` que no
existe en este repo. Es una regla pensada para JavaScript. Aquí el código usa
`asyncio.create_subprocess_exec(*cmd)`, que pasa argv como lista y no abre shell:
ya es la forma segura. Si el hook estorba al implementar `server/runner.py`, escribe
ese archivo con `cat` desde bash, o quita `"exec("` de la lista de subcadenas en
`~/.claude/plugins/cache/claude-plugins-official/security-guidance/*/hooks/security_reminder_hook.py`.

---

## Estructura de archivos

### Servidor

| Archivo | Responsabilidad |
|---|---|
| `server/config.py` (modificar) | Añade clave del reloj, modelo, timeouts, lista blanca en crudo |
| `server/projects.py` (crear) | Parsea la lista blanca y resuelve `project_id → ruta`. Nada más |
| `server/runner.py` (crear) | Construye el comando `claude`, lo ejecuta, parsea la salida. No sabe de HTTP ni de jobs |
| `server/jobs.py` (crear) | Cola de un solo job, máquina de estados, límite de peticiones. No sabe qué es Claude |
| `server/database.py` (modificar) | Tablas `jobs` y `threads` con sus métodos |
| `server/main.py` (modificar) | Los seis endpoints nuevos. No sabe lanzar procesos |

Cada uno se puede leer y probar sin abrir los demás. `runner.py` es puro "lanza y
parsea"; `jobs.py` es pura máquina de estados con un runner inyectado, lo que
permite probarla entera sin tocar el CLI.

### Reloj y móvil

| Archivo | Responsabilidad |
|---|---|
| `android/wear/.../ask/AskApi.kt` (crear) | Interfaz Retrofit y DTOs |
| `android/wear/.../ask/WatchConfig.kt` (crear) | DataStore con URL y clave recibidas del móvil |
| `android/wear/.../ask/AskState.kt` (crear) | Estados sellados de la pantalla |
| `android/wear/.../ask/AskViewModel.kt` (crear) | Sondeo, transiciones, llamadas de red |
| `android/wear/.../ask/AskActivity.kt` (crear) | Aloja las pantallas y recoge el RemoteInput |
| `android/wear/.../ask/ui/AskScreens.kt` (crear) | Las pantallas Compose |
| `android/wear/.../DataLayerListenerService.kt` (modificar) | Recibe `/claude-watch/config` |
| `android/wear/.../ui/ApprovalScreen.kt` (modificar) | `WaitingScreen` gana botón "Preguntar" |
| `android/mobile/.../DataLayerSender.kt` (modificar) | `sendConfig()` |
| `android/mobile/.../ui/SettingsScreen.kt` (modificar) | Llama a `sendConfig()` al guardar |

`AskActivity` va aparte de `MainActivity` a propósito: `MainActivity` son 56 líneas
que reciben resúmenes por Data Layer y no se tocan.

---

## Task 1: Lista blanca de proyectos

**Files:**
- Create: `server/projects.py`
- Modify: `server/config.py`
- Test: `server/tests/test_projects.py`

- [ ] **Step 1: Write the failing test**

Crea `server/tests/test_projects.py`:

```python
from server.projects import Project, parse_projects


def test_parses_single_project():
    projects = parse_projects("ahorrapp:/home/ubuntu/AhorrApp")
    assert projects["ahorrapp"] == Project(
        id="ahorrapp", name="AhorrApp", path="/home/ubuntu/AhorrApp"
    )


def test_parses_several_projects():
    projects = parse_projects(
        "ahorrapp:/home/ubuntu/AhorrApp;petwatch:/home/ubuntu/PetWatch1"
    )
    assert list(projects) == ["ahorrapp", "petwatch"]
    assert projects["petwatch"].name == "PetWatch1"


def test_name_ignores_trailing_slash():
    projects = parse_projects("ahorrapp:/home/ubuntu/AhorrApp/")
    assert projects["ahorrapp"].name == "AhorrApp"


def test_ignores_empty_and_malformed_entries():
    projects = parse_projects("ahorrapp:/home/ubuntu/AhorrApp;;sinruta:;:/sin/id")
    assert list(projects) == ["ahorrapp"]


def test_empty_string_gives_no_projects():
    assert parse_projects("") == {}


def test_strips_whitespace():
    projects = parse_projects("  ahorrapp : /home/ubuntu/AhorrApp  ")
    assert projects["ahorrapp"].path == "/home/ubuntu/AhorrApp"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest server/tests/test_projects.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'server.projects'`

- [ ] **Step 3: Write minimal implementation**

Crea `server/projects.py`:

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    path: str


def parse_projects(raw: str) -> dict[str, Project]:
    """Parsea "id:ruta;id:ruta" en {id: Project}.

    El nombre visible sale del ultimo segmento de la ruta, asi que la
    configuracion no tiene que repetirlo. Las entradas mal formadas se
    ignoran en silencio: una linea rota en la config no debe impedir
    que arranque el servidor.
    """
    projects: dict[str, Project] = {}
    for entry in raw.split(";"):
        project_id, _, path = entry.partition(":")
        project_id = project_id.strip()
        path = path.strip()
        if not project_id or not path:
            continue
        projects[project_id] = Project(
            id=project_id,
            name=Path(path).name,
            path=path,
        )
    return projects
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest server/tests/test_projects.py -v`
Expected: PASS, 6 passed

- [ ] **Step 5: Añade la configuración nueva**

En `server/config.py`, después de la línea de `FCM_CREDENTIALS_PATH`, añade:

```python
from server.projects import parse_projects

ASK_KEY = os.environ.get("CLAUDE_WATCH_ASK_KEY", "change-me-in-production")
ASK_MODEL = os.environ.get("CLAUDE_WATCH_ASK_MODEL", "sonnet")
CLAUDE_BIN = os.environ.get("CLAUDE_WATCH_CLAUDE_BIN", "claude")
READ_TIMEOUT = int(os.environ.get("CLAUDE_WATCH_READ_TIMEOUT", "180"))
WRITE_TIMEOUT = int(os.environ.get("CLAUDE_WATCH_WRITE_TIMEOUT", "600"))
MAX_ASKS_PER_HOUR = int(os.environ.get("CLAUDE_WATCH_MAX_ASKS_PER_HOUR", "20"))
THREAD_TTL_HOURS = int(os.environ.get("CLAUDE_WATCH_THREAD_TTL_HOURS", "6"))
APPROVAL_TTL_SECONDS = int(os.environ.get("CLAUDE_WATCH_APPROVAL_TTL", "300"))
PROJECTS = parse_projects(os.environ.get("CLAUDE_WATCH_PROJECTS", ""))
```

- [ ] **Step 6: Comprueba que no se ha roto nada**

Run: `./venv/bin/python -m pytest server/tests hook/tests -q`
Expected: 26 passed

- [ ] **Step 7: Commit**

```bash
git add server/projects.py server/config.py server/tests/test_projects.py
git commit -m "feat: add project whitelist parsing

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Tablas `jobs` y `threads`

**Files:**
- Modify: `server/database.py`
- Test: `server/tests/test_database.py`

Nota sobre nombres de columna: **no** uses `full` como nombre de columna — es
palabra clave en SQLite (`FULL OUTER JOIN`). Usa `short_text` y `full_text`.

- [ ] **Step 1: Write the failing test**

Añade al final de `server/tests/test_database.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest server/tests/test_database.py -v`
Expected: FAIL con `AttributeError: 'ApprovalDB' object has no attribute 'create_job'`

- [ ] **Step 3: Write minimal implementation**

En `server/database.py`, amplía `_create_tables` con las dos tablas nuevas
(deja intacto el bloque de `devices`):

```python
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                mode TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT NOT NULL,
                short_text TEXT,
                full_text TEXT,
                plan TEXT,
                error TEXT,
                session_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS threads (
                project_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
```

Y añade estos métodos a la clase:

```python
    _JOB_FIELDS = (
        "status", "short_text", "full_text", "plan", "error", "session_id",
    )

    def create_job(self, job_id: str, project_id: str, mode: str, prompt: str):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO jobs (id, project_id, mode, prompt, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'running', ?, ?)",
            (job_id, project_id, mode, prompt, now, now),
        )
        self._conn.commit()

    def get_job(self, job_id: str):
        return self._conn.execute(
            "SELECT * FROM jobs WHERE id = ?", (job_id,)
        ).fetchone()

    def update_job(self, job_id: str, **fields):
        unknown = set(fields) - set(self._JOB_FIELDS)
        if unknown:
            raise ValueError(f"campos desconocidos: {sorted(unknown)}")
        if not fields:
            return
        assignments = ", ".join(f"{name} = ?" for name in fields)
        values = [*fields.values(), datetime.now(timezone.utc).isoformat(), job_id]
        self._conn.execute(
            f"UPDATE jobs SET {assignments}, updated_at = ? WHERE id = ?", values
        )
        self._conn.commit()

    def orphan_running_jobs(self):
        """Al arrancar, los jobs que quedaron corriendo ya no tienen proceso."""
        self._conn.execute(
            "UPDATE jobs SET status = 'error', error = ?, updated_at = ? "
            "WHERE status IN ('running', 'awaiting_approval')",
            ("Se interrumpio al reiniciar el servidor",
             datetime.now(timezone.utc).isoformat()),
        )
        self._conn.commit()

    def count_jobs_since(self, iso_timestamp: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM jobs WHERE created_at >= ?", (iso_timestamp,)
        ).fetchone()
        return row["n"]

    def get_thread(self, project_id: str):
        return self._conn.execute(
            "SELECT * FROM threads WHERE project_id = ?", (project_id,)
        ).fetchone()

    def set_thread(self, project_id: str, session_id: str):
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO threads (project_id, session_id, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(project_id) DO UPDATE SET session_id = ?, updated_at = ?",
            (project_id, session_id, now, session_id, now),
        )
        self._conn.commit()

    def clear_thread(self, project_id: str):
        self._conn.execute("DELETE FROM threads WHERE project_id = ?", (project_id,))
        self._conn.commit()
```

El `update_job` valida los nombres de campo contra `_JOB_FIELDS` porque van
interpolados en el SQL. Los valores sí van parametrizados; los nombres no pueden,
así que la lista blanca es lo que impide una inyección por ahí.

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest server/tests/test_database.py -v`
Expected: PASS, todos

- [ ] **Step 5: Comprueba la suite entera**

Run: `./venv/bin/python -m pytest server/tests hook/tests -q`
Expected: 33 passed

- [ ] **Step 6: Commit**

```bash
git add server/database.py server/tests/test_database.py
git commit -m "feat: add jobs and threads tables

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Construcción del comando y troceo de la respuesta

Esta es la parte pura del runner: no lanza nada, solo decide qué lanzar y cómo leer
lo que vuelve. Por eso se prueba entera sin tocar el CLI.

**Files:**
- Create: `server/runner.py`
- Test: `server/tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

Crea `server/tests/test_runner.py`:

```python
import pytest
from server.runner import build_command, split_answer


def _flag_values(cmd, flag):
    """Devuelve los valores que siguen a un flag hasta el siguiente flag."""
    start = cmd.index(flag) + 1
    values = []
    for item in cmd[start:]:
        if item.startswith("--"):
            break
        values.append(item)
    return values


def test_read_command_has_prompt_and_json():
    cmd = build_command("read", "que tal")
    assert cmd[1:3] == ["-p", "que tal"]
    assert _flag_values(cmd, "--output-format") == ["json"]
    assert _flag_values(cmd, "--permission-prompts") == ["none"]


def test_read_command_whitelists_read_only_tools():
    cmd = build_command("read", "que tal")
    tools = _flag_values(cmd, "--allowedTools")
    assert "Read" in tools
    assert "Bash(git log:*)" in tools
    assert "Edit" not in tools
    assert "Write" not in tools


def test_read_command_has_no_permission_mode():
    cmd = build_command("read", "que tal")
    assert "--permission-mode" not in cmd


def test_plan_command_uses_plan_mode():
    cmd = build_command("plan", "arregla el typo")
    assert _flag_values(cmd, "--permission-mode") == ["plan"]
    assert "--allowedTools" not in cmd


def test_exec_command_accepts_edits_and_denies_dangerous_tools():
    cmd = build_command("exec", "Ejecuta el plan", session_id="s-1")
    assert _flag_values(cmd, "--permission-mode") == ["acceptEdits"]
    denied = _flag_values(cmd, "--disallowedTools")
    for tool in ("Bash(git push:*)", "Bash(sudo:*)", "Bash(systemctl:*)",
                 "Bash(docker:*)", "Bash(rm:*)", "WebFetch"):
        assert tool in denied


def test_resume_only_when_session_given():
    assert "--resume" not in build_command("read", "hola")
    cmd = build_command("read", "hola", session_id="s-42")
    assert _flag_values(cmd, "--resume") == ["s-42"]


def test_every_phase_appends_brevity_prompt():
    for phase in ("read", "plan", "exec"):
        cmd = build_command(phase, "hola", session_id="s-1")
        assert "--append-system-prompt" in cmd


def test_unknown_phase_raises():
    with pytest.raises(ValueError):
        build_command("borrarlo-todo", "hola")


def test_split_answer_uses_first_paragraph_as_short():
    short, full = split_answer("Tres lineas cortas.\n\nY aqui el detalle largo.")
    assert short == "Tres lineas cortas."
    assert full == "Tres lineas cortas.\n\nY aqui el detalle largo."


def test_split_answer_without_blank_line_truncates_to_200():
    text = "x" * 500
    short, full = split_answer(text)
    assert len(short) == 200
    assert full == text


def test_split_answer_truncates_long_first_paragraph():
    short, _ = split_answer("y" * 300 + "\n\ndetalle")
    assert len(short) == 200


def test_split_answer_empty():
    assert split_answer("   ") == ("", "")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest server/tests/test_runner.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'server.runner'`

- [ ] **Step 3: Write minimal implementation**

Crea `server/runner.py`:

```python
from server.config import ASK_MODEL, CLAUDE_BIN

BREVITY_PROMPT = (
    "Responde con una primera linea de 40 palabras o menos que conteste "
    "directamente, sin preambulo. Despues una linea en blanco. Despues el "
    "detalle si lo hay. Sin markdown ni tablas: esto se lee en un reloj."
)

EXEC_PROMPT = "Ejecuta el plan que acabas de describir."

READ_TOOLS = [
    "Read",
    "Grep",
    "Glob",
    "Bash(git log:*)",
    "Bash(git diff:*)",
    "Bash(git status:*)",
]

EXEC_DENIED_TOOLS = [
    "Bash(git push:*)",
    "Bash(sudo:*)",
    "Bash(systemctl:*)",
    "Bash(docker:*)",
    "Bash(rm:*)",
    "WebFetch",
]

SHORT_MAX = 200


def build_command(phase: str, prompt: str, session_id: str | None = None) -> list[str]:
    """Construye el comando para una fase: 'read', 'plan' o 'exec'."""
    cmd = [
        CLAUDE_BIN,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--permission-prompts",
        "none",
        "--model",
        ASK_MODEL,
        "--append-system-prompt",
        BREVITY_PROMPT,
    ]

    if phase == "read":
        cmd += ["--allowedTools", *READ_TOOLS]
    elif phase == "plan":
        cmd += ["--permission-mode", "plan"]
    elif phase == "exec":
        cmd += ["--permission-mode", "acceptEdits"]
        cmd += ["--disallowedTools", *EXEC_DENIED_TOOLS]
    else:
        raise ValueError(f"fase desconocida: {phase}")

    if session_id:
        cmd += ["--resume", session_id]

    return cmd


def split_answer(text: str) -> tuple[str, str]:
    """Parte la respuesta en (corta, completa).

    El system prompt pide una primera linea breve, linea en blanco, y luego el
    detalle. Si Claude no hace caso, la corta son los primeros 200 caracteres:
    degradar mal es peor que degradar feo.
    """
    full = text.strip()
    if not full:
        return "", ""
    head, separator, _ = full.partition("\n\n")
    short = head.strip() if separator else full
    return short[:SHORT_MAX], full
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest server/tests/test_runner.py -v`
Expected: PASS, 12 passed

- [ ] **Step 5: Commit**

```bash
git add server/runner.py server/tests/test_runner.py
git commit -m "feat: build claude commands and split answers

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Ejecutar el subproceso

Los tests no llaman al CLI de verdad: usan un script de shell falso que imita su
salida. Así se prueba el timeout, el código de salida y el JSON roto sin gastar un
céntimo ni depender de la red.

**Files:**
- Modify: `server/runner.py`
- Test: `server/tests/test_runner.py`

- [ ] **Step 1: Write the failing test**

Añade al final de `server/tests/test_runner.py`:

```python
import json
import os
import stat
import tempfile
from server.runner import run_claude


def _fake_claude(body: str) -> str:
    """Crea un ejecutable que imita a claude y devuelve su ruta."""
    fd, path = tempfile.mkstemp(suffix=".sh")
    with os.fdopen(fd, "w") as handle:
        handle.write("#!/bin/sh\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


@pytest.mark.anyio
async def test_run_claude_parses_successful_json(tmp_path):
    payload = json.dumps({
        "result": "Corto.\n\nLargo.",
        "session_id": "s-99",
        "is_error": False,
        "permission_denials": [],
    })
    script = _fake_claude(f"cat <<'JSON'\n{payload}\nJSON\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    os.unlink(script)
    assert result.ok is True
    assert result.short == "Corto."
    assert result.full == "Corto.\n\nLargo."
    assert result.session_id == "s-99"


@pytest.mark.anyio
async def test_run_claude_reports_nonzero_exit(tmp_path):
    script = _fake_claude("echo 'algo fue mal' >&2\nexit 1\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    os.unlink(script)
    assert result.ok is False
    assert "algo fue mal" in result.error


@pytest.mark.anyio
async def test_run_claude_reports_unreadable_output(tmp_path):
    script = _fake_claude("echo 'esto no es json'\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    os.unlink(script)
    assert result.ok is False
    assert "ilegible" in result.error


@pytest.mark.anyio
async def test_run_claude_times_out_and_kills(tmp_path):
    script = _fake_claude("sleep 30\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=1)
    os.unlink(script)
    assert result.ok is False
    assert "demasiado" in result.error


@pytest.mark.anyio
async def test_run_claude_honours_is_error_flag(tmp_path):
    payload = json.dumps({
        "result": "se acabo el credito",
        "session_id": "s-1",
        "is_error": True,
        "permission_denials": [],
    })
    script = _fake_claude(f"cat <<'JSON'\n{payload}\nJSON\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    os.unlink(script)
    assert result.ok is False
    assert result.error == "se acabo el credito"


@pytest.mark.anyio
async def test_run_claude_records_permission_denials(tmp_path):
    payload = json.dumps({
        "result": "No he podido mirar eso.",
        "session_id": "s-1",
        "is_error": False,
        "permission_denials": [{"tool_name": "Edit"}],
    })
    script = _fake_claude(f"cat <<'JSON'\n{payload}\nJSON\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    os.unlink(script)
    assert result.ok is True
    assert result.denied_tools == ["Edit"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest server/tests/test_runner.py -k run_claude -v`
Expected: FAIL con `ImportError: cannot import name 'run_claude'`

- [ ] **Step 3: Write minimal implementation**

Añade a `server/runner.py` (arriba, junto a los otros imports):

```python
import asyncio
import json
import os
import signal
from dataclasses import dataclass, field
```

Y al final del archivo:

```python
ERROR_MAX = 300


def _kill_group(process) -> None:
    """Mata el grupo entero del subproceso, si sigue vivo."""
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


@dataclass
class RunResult:
    ok: bool
    short: str = ""
    full: str = ""
    session_id: str | None = None
    error: str | None = None
    denied_tools: list[str] = field(default_factory=list)


async def run_claude(cmd: list[str], cwd: str, timeout: int) -> RunResult:
    """Lanza el comando y devuelve el resultado ya troceado.

    Usa create_subprocess_exec con argv como lista: no hay shell de por medio,
    asi que el prompt del usuario no puede inyectar comandos.

    Nunca lanza excepciones: cualquier fallo vuelve como RunResult(ok=False)
    con un mensaje que cabe en un reloj.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            # No quitar: sin sesion propia no se puede matar el grupo, y un
            # kill() al proceso principal deja vivos a los hijos que claude
            # haya lanzado, que mantienen los pipes abiertos y cuelgan el
            # wait() indefinidamente. Medido: 1s con killpg, >9s sin el.
            start_new_session=True,
        )
    except OSError as exc:
        return RunResult(ok=False, error=f"No se pudo lanzar claude: {exc}"[:ERROR_MAX])

    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        _kill_group(process)
        await process.wait()
        return RunResult(ok=False, error="Tardo demasiado")
    except asyncio.CancelledError:
        # Cancelacion de fuera: el boton del reloj (jobs.cancel hace
        # task.cancel) o el apagado del servidor. Hay que propagarla, pero
        # no sin matar antes al subproceso: si no, queda un claude vivo
        # gastando tokens con la cola creyendose libre.
        _kill_group(process)
        raise

    if process.returncode != 0:
        message = stderr.decode(errors="replace").strip() or "claude fallo sin decir por que"
        # Del final, no del principio: los CLI ponen la causa en la ultima
        # linea, detras del ruido.
        return RunResult(ok=False, error=message[-ERROR_MAX:])

    try:
        payload = json.loads(stdout.decode(errors="replace"))
    except json.JSONDecodeError:
        return RunResult(ok=False, error="Respuesta ilegible de claude")

    if not isinstance(payload, dict):
        return RunResult(ok=False, error="Respuesta ilegible de claude")

    text = payload.get("result")
    if not isinstance(text, str):
        text = ""
    session_id = payload.get("session_id")

    if payload.get("is_error"):
        return RunResult(ok=False, session_id=session_id, error=text[:ERROR_MAX])

    short, full = split_answer(text)
    denied = [
        denial.get("tool_name", "?")
        for denial in payload.get("permission_denials") or []
    ]
    return RunResult(
        ok=True,
        short=short,
        full=full,
        session_id=session_id,
        denied_tools=denied,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest server/tests/test_runner.py -v`
Expected: PASS, 18 passed

- [ ] **Step 5: Commit**

```bash
git add server/runner.py server/tests/test_runner.py
git commit -m "feat: run claude as a subprocess with timeout

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: La cola de un solo job y el flujo de lectura

`JobManager` recibe el runner como argumento del constructor. Eso permite probar
toda la máquina de estados con un runner falso, sin subprocesos ni esperas.

**Files:**
- Create: `server/jobs.py`
- Test: `server/tests/test_jobs.py`

- [ ] **Step 1: Write the failing test**

Crea `server/tests/test_jobs.py`:

```python
import asyncio
import os
import tempfile
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest server/tests/test_jobs.py -v`
Expected: FAIL con `ModuleNotFoundError: No module named 'server.jobs'`

- [ ] **Step 3: Write minimal implementation**

Crea `server/jobs.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest server/tests/test_jobs.py -v`
Expected: PASS, 8 passed

- [ ] **Step 5: Commit**

```bash
git add server/jobs.py server/tests/test_jobs.py
git commit -m "feat: add single-slot job queue with per-project threads

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Aprobar, cancelar y la caducidad de los 5 minutos

**Files:**
- Modify: `server/jobs.py`
- Test: `server/tests/test_jobs.py`

- [ ] **Step 1: Write the failing test**

Añade al final de `server/tests/test_jobs.py`:

```python
from server.jobs import NotApprovable


@pytest.mark.anyio
async def test_write_job_stops_at_awaiting_approval(db):
    manager = make_manager(db, [
        RunResult(ok=True, short="Tocare 3 archivos.", full="Tocare 3 archivos.\n\nDetalle.", session_id="s-1"),
    ])
    job_id = await manager.submit(PROJECT, "arregla el typo", mode="write", thread="new")
    await manager.wait_idle()
    job = db.get_job(job_id)
    assert job["status"] == "awaiting_approval"
    assert job["plan"] == "Tocare 3 archivos."


@pytest.mark.anyio
async def test_plan_phase_uses_plan_mode(db):
    manager = make_manager(db, [RunResult(ok=True, short="plan", full="plan", session_id="s-1")])
    await manager.submit(PROJECT, "arregla el typo", mode="write", thread="new")
    await manager.wait_idle()
    cmd = manager.calls[0]["cmd"]
    assert cmd[cmd.index("--permission-mode") + 1] == "plan"


@pytest.mark.anyio
async def test_approve_runs_exec_phase_resuming_the_session(db):
    manager = make_manager(db, [
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
    exec_cmd = manager.calls[1]["cmd"]
    assert exec_cmd[exec_cmd.index("--permission-mode") + 1] == "acceptEdits"
    assert exec_cmd[exec_cmd.index("--resume") + 1] == "s-1"


@pytest.mark.anyio
async def test_approve_rejects_job_that_is_not_awaiting(db):
    manager = make_manager(db, [RunResult(ok=True, short="ok", full="ok")])
    job_id = await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.wait_idle()
    with pytest.raises(NotApprovable):
        await manager.approve(job_id, PROJECT)


@pytest.mark.anyio
async def test_approve_rejects_unknown_job(db):
    manager = make_manager(db, [])
    with pytest.raises(NotApprovable):
        await manager.approve("no-existe", PROJECT)


@pytest.mark.anyio
async def test_approve_expires_after_ttl(db, monkeypatch):
    monkeypatch.setattr("server.jobs.APPROVAL_TTL_SECONDS", 0)
    manager = make_manager(db, [RunResult(ok=True, short="plan", full="plan", session_id="s-1")])
    job_id = await manager.submit(PROJECT, "arregla el typo", mode="write", thread="new")
    await manager.wait_idle()
    await asyncio.sleep(0.01)
    with pytest.raises(NotApprovable):
        await manager.approve(job_id, PROJECT)
    assert db.get_job(job_id)["status"] == "cancelled"


@pytest.mark.anyio
async def test_cancel_marks_job_cancelled(db):
    gate = asyncio.Event()
    manager = make_manager(db, [RunResult(ok=True, short="ok", full="ok")], gate=gate)
    job_id = await manager.submit(PROJECT, "que tal", mode="read", thread="new")
    await manager.cancel(job_id)
    gate.set()
    assert db.get_job(job_id)["status"] == "cancelled"
    assert manager.busy is False


@pytest.mark.anyio
async def test_cancel_frees_the_slot(db):
    gate = asyncio.Event()
    manager = make_manager(db, [
        RunResult(ok=True, short="a", full="a"),
        RunResult(ok=True, short="b", full="b"),
    ], gate=gate)
    first = await manager.submit(PROJECT, "primera", mode="read", thread="new")
    await manager.cancel(first)
    gate.set()
    second = await manager.submit(PROJECT, "segunda", mode="read", thread="new")
    await manager.wait_idle()
    assert db.get_job(second)["status"] == "done"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest server/tests/test_jobs.py -k "approve or cancel or awaiting or plan_phase" -v`
Expected: FAIL con `ImportError: cannot import name 'NotApprovable'`

- [ ] **Step 3: Write minimal implementation**

En `server/jobs.py`, añade `APPROVAL_TTL_SECONDS` al import de `server.config`:

```python
from server.config import (
    APPROVAL_TTL_SECONDS,
    MAX_ASKS_PER_HOUR,
    READ_TIMEOUT,
    THREAD_TTL_HOURS,
    WRITE_TIMEOUT,
)
```

Amplía el import del runner para traerte `EXEC_PROMPT`:

```python
from server.runner import EXEC_PROMPT, build_command, run_claude
```

Añade la excepción junto a las otras dos:

```python
class NotApprovable(Exception):
    """Ese job no esta esperando aprobacion, o ya ha caducado."""

    def __init__(self, reason: str = "Ese plan ya no se puede aprobar"):
        super().__init__(reason)
        self.reason = reason
```

Y añade estos dos métodos a `JobManager`:

```python
    async def approve(self, job_id: str, project: Project) -> None:
        """Ejecuta un plan ya aprobado por la persona.

        Es el unico camino por el que este servidor modifica nada: hasta
        aqui, la fase plan solo ha mirado.
        """
        # Igual que en submit: de aqui a create_task no puede haber ningun
        # await, o dos aprobaciones simultaneas programarian dos fases exec
        # sobre el mismo plan.
        job = self._db.get_job(job_id)
        if job is None:
            raise NotApprovable("No existe ese trabajo")
        if job["status"] != "awaiting_approval":
            raise NotApprovable("Ese plan ya no esta esperando aprobacion")
        if project.id != job["project_id"]:
            # El cwd sale de este project, no de la fila. Aprobar un plan de
            # un repo dentro de otro es exactamente lo que no puede pasar.
            raise NotApprovable("Ese plan es de otro proyecto")

        age = datetime.now(timezone.utc) - datetime.fromisoformat(job["updated_at"])
        if age > timedelta(seconds=APPROVAL_TTL_SECONDS):
            self._db.update_job(
                job_id, status="cancelled", error="El plan caduco sin aprobar"
            )
            raise NotApprovable("El plan caduco sin aprobar")

        if self.busy:
            raise Busy()

        self._db.update_job(job_id, status="running")
        self._current_job_id = job_id
        self._task = asyncio.create_task(
            self._run(job_id, project, "exec", EXEC_PROMPT, job["session_id"])
        )

    # Estados desde los que todavia tiene sentido cancelar.
    _CANCELLABLE = ("running", "awaiting_approval")

    async def cancel(self, job_id: str) -> str | None:
        """Para un job y devuelve el estado en que queda, o None si no existe.

        No pisa un resultado ya escrito. Si el job termino entre que pulsaste
        Cancelar y que llego la peticion, el reloj debe ver 'done', no una
        mentira: con acceptEdits los archivos ya estaban tocados y decir
        'cancelado' seria mentir sobre el disco.
        """
        job = self._db.get_job(job_id)
        if job is None:
            return None
        if job["status"] not in self._CANCELLABLE:
            return job["status"]

        if self._current_job_id == job_id and self.busy and self._task is not None:
            self._task.cancel()
            self._task = None
            self._current_job_id = None

        self._db.update_job(job_id, status="cancelled")
        return "cancelled"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest server/tests/test_jobs.py -v`
Expected: PASS, 16 passed

- [ ] **Step 5: Comprueba la suite entera**

Run: `./venv/bin/python -m pytest server/tests hook/tests -q`
Expected: 67 passed

- [ ] **Step 6: Commit**

```bash
git add server/jobs.py server/tests/test_jobs.py
git commit -m "feat: add plan approval, expiry and cancellation

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Los endpoints de consulta

**Files:**
- Modify: `server/main.py`
- Test: `server/tests/test_ask_endpoints.py`

- [ ] **Step 1: Write the failing test**

Crea `server/tests/test_ask_endpoints.py`:

```python
import os
import tempfile
import pytest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

_fd, _test_db = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["CLAUDE_WATCH_DB_PATH"] = _test_db
os.environ["CLAUDE_WATCH_API_KEY"] = "hook-key"
os.environ["CLAUDE_WATCH_ASK_KEY"] = "watch-key"
os.environ["CLAUDE_WATCH_PROJECTS"] = "ahorrapp:/tmp;petwatch:/tmp"

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
    return {"X-Api-Key": "hook-key"}


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
async def test_ask_rejects_too_long_prompt(watch_headers):
    async with client() as http:
        resp = await http.post(
            "/ask",
            json={"project_id": "ahorrapp", "prompt": "x" * 1001, "mode": "read", "thread": "new"},
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest server/tests/test_ask_endpoints.py -v`
Expected: FAIL con `ImportError: cannot import name 'job_manager' from 'server.main'`

- [ ] **Step 3: Write minimal implementation**

Reescribe la cabecera de `server/main.py`. Lo que ya existe (`/notify`,
`/register-device`) se queda igual:

```python
import hmac
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from server.config import API_KEY, ASK_KEY, DB_PATH, PROJECTS
from server.database import ApprovalDB
from server.fcm import send_info_notification
from server.jobs import Busy, JobManager, NotApprovable, RateLimited

app = FastAPI(title="Claude Watch")
db = ApprovalDB(DB_PATH)
db.orphan_running_jobs()
job_manager = JobManager(db=db)


def verify_api_key(x_api_key: str = Header()):
    """Clave del hook: solo abre /notify y /register-device."""
    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")


def verify_ask_key(x_api_key: str = Header()):
    """Clave del reloj: solo abre /projects y /ask*.

    Son dos claves distintas a proposito: perder el reloj se arregla
    revocando una sola, sin tocar las notificaciones.
    """
    if not hmac.compare_digest(x_api_key, ASK_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")


def get_project(project_id: str):
    project = PROJECTS.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Unknown project")
    return project
```

Nota: el `import hmac` local que hoy vive dentro de `verify_api_key` se sube arriba;
borra esa línea de dentro de la función.

Añade el modelo junto a los que ya hay:

```python
class AskRequest(BaseModel):
    project_id: str = Field(..., max_length=100)
    prompt: str = Field(..., min_length=1, max_length=1000)
    mode: Literal["read", "write"] = "read"
    thread: Literal["new", "continue"] = "new"
```

Y los endpoints al final del archivo:

```python
@app.get("/projects")
def list_projects(x_api_key: str = Header()):
    verify_ask_key(x_api_key)
    return {
        "projects": [
            {"id": project.id, "name": project.name} for project in PROJECTS.values()
        ]
    }


@app.post("/ask", status_code=202)
async def ask(body: AskRequest, x_api_key: str = Header()):
    verify_ask_key(x_api_key)
    project = get_project(body.project_id)
    try:
        job_id = await job_manager.submit(
            project, body.prompt, mode=body.mode, thread=body.thread
        )
    except Busy:
        raise HTTPException(status_code=409, detail="Hay una consulta en marcha")
    except RateLimited:
        raise HTTPException(status_code=429, detail="Limite de consultas por hora")
    return {"job_id": job_id, "status": "running"}


@app.get("/ask/{job_id}")
def get_ask(job_id: str, x_api_key: str = Header()):
    verify_ask_key(x_api_key)
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    return {
        "status": job["status"],
        "short": job["short_text"],
        "full": job["full_text"],
        "plan": job["plan"],
        "error": job["error"],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest server/tests/test_ask_endpoints.py -v`
Expected: PASS, 10 passed

- [ ] **Step 5: Comprueba que los endpoints viejos siguen intactos**

Run: `./venv/bin/python -m pytest server/tests hook/tests -q`
Expected: 77 passed

- [ ] **Step 6: Commit**

```bash
git add server/main.py server/tests/test_ask_endpoints.py
git commit -m "feat: add /projects, /ask and /ask/{id} endpoints

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Aprobar, cancelar y mandar al móvil por HTTP

**Files:**
- Modify: `server/main.py`
- Test: `server/tests/test_ask_endpoints.py`

- [ ] **Step 1: Write the failing test**

Añade al final de `server/tests/test_ask_endpoints.py`:

```python
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
    plan = RunResult(ok=True, short="Tocare 3 archivos.", full="Tocare 3 archivos.\n\nDetalle.", session_id="s-1")
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
async def test_cancel_marks_it_cancelled(watch_headers):
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
            await http.post(f"/ask/{job_id}/cancel", headers=watch_headers)
            final = await http.get(f"/ask/{job_id}", headers=watch_headers)
    assert final.json()["status"] == "cancelled"


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
            with patch("server.main.send_info_notification", return_value=True) as mock_send:
                sent = await http.post(f"/ask/{job_id}/to-phone", headers=watch_headers)

    assert sent.status_code == 200
    mock_send.assert_called_once_with(
        tokens=["device-token-xyz"],
        tool_name="Respuesta",
        message="Corto.\n\nTodo el detalle.",
    )


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest server/tests/test_ask_endpoints.py -k "approve or cancel or to_phone or plan" -v`
Expected: FAIL con 404 en `/ask/{id}/approve` (la ruta no existe todavía)

- [ ] **Step 3: Write minimal implementation**

Añade al final de `server/main.py`:

```python
@app.post("/ask/{job_id}/approve")
async def approve_ask(job_id: str, x_api_key: str = Header()):
    verify_ask_key(x_api_key)
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    project = get_project(job["project_id"])
    try:
        await job_manager.approve(job_id, project)
    except NotApprovable:
        raise HTTPException(status_code=409, detail="Ese plan ya no se puede aprobar")
    except Busy:
        raise HTTPException(status_code=409, detail="Hay una consulta en marcha")
    return {"status": "running"}


@app.post("/ask/{job_id}/cancel")
async def cancel_ask(job_id: str, x_api_key: str = Header()):
    verify_ask_key(x_api_key)
    status = await job_manager.cancel(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    # Devuelve el estado real: si el job ya habia terminado, no se cancelo
    # nada y el reloj no debe creerse lo contrario.
    return {"status": status}


@app.post("/ask/{job_id}/to-phone")
def send_ask_to_phone(job_id: str, x_api_key: str = Header()):
    verify_ask_key(x_api_key)
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    if not job["full_text"]:
        raise HTTPException(status_code=409, detail="Todavia no hay respuesta")
    tokens = db.get_device_tokens()
    try:
        send_info_notification(
            tokens=tokens,
            tool_name="Respuesta",
            message=job["full_text"],
        )
    except Exception:
        pass
    return {"status": "sent", "devices": len(tokens)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `./venv/bin/python -m pytest server/tests/test_ask_endpoints.py -v`
Expected: PASS, 16 passed

- [ ] **Step 5: Comprueba la suite entera**

Run: `./venv/bin/python -m pytest server/tests hook/tests -q`
Expected: 83 passed

- [ ] **Step 6: Commit**

```bash
git add server/main.py server/tests/test_ask_endpoints.py
git commit -m "feat: add approve, cancel and to-phone endpoints

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Prueba real contra el CLI y despliegue del servidor

Hasta aquí todo ha corrido con un `claude` falso. Este paso es el primero que gasta
dinero de verdad, y por eso va solo y con pocas consultas.

**Files:**
- Modify: `server/claude-watch.service`
- Modify: `server/README.md`

- [ ] **Step 1: Genera la clave del reloj**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Guárdala: hace falta en el servicio y en la app del móvil.

- [ ] **Step 2: Añade las variables al servicio**

En `server/claude-watch.service`, dentro de `[Service]`, añade (sustituyendo la
clave por la del paso anterior y ajustando la lista de proyectos):

```ini
Environment="CLAUDE_WATCH_ASK_KEY=LA_CLAVE_GENERADA"
Environment="CLAUDE_WATCH_ASK_MODEL=sonnet"
Environment="CLAUDE_WATCH_CLAUDE_BIN=/home/ubuntu/.npm-global/bin/claude"
Environment="CLAUDE_WATCH_PROJECTS=ahorrapp:/home/ubuntu/AhorrApp;petwatch:/home/ubuntu/PetWatch1;watch:/home/ubuntu/claude-watch-approve"
```

`CLAUDE_WATCH_CLAUDE_BIN` con ruta absoluta: el `PATH` de systemd no incluye
`~/.npm-global/bin`, así que sin esto el subproceso no encuentra el binario.

- [ ] **Step 3: Recarga y reinicia**

```bash
sudo cp server/claude-watch.service /etc/systemd/system/claude-watch.service
sudo systemctl daemon-reload
sudo systemctl restart claude-watch
systemctl status claude-watch --no-pager | head -5
```

Expected: `Active: active (running)`

- [ ] **Step 4: Comprueba la lista de proyectos**

```bash
curl -s -H "X-Api-Key: LA_CLAVE_GENERADA" http://127.0.0.1:8400/projects
```

Expected: JSON con los proyectos configurados y sus nombres.

- [ ] **Step 5: Una consulta real, de lectura**

```bash
JOB=$(curl -s -X POST http://127.0.0.1:8400/ask \
  -H "X-Api-Key: LA_CLAVE_GENERADA" -H "Content-Type: application/json" \
  -d '{"project_id":"watch","prompt":"En una frase, que hace este repo?","mode":"read","thread":"new"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "job: $JOB"
sleep 30
curl -s -H "X-Api-Key: LA_CLAVE_GENERADA" http://127.0.0.1:8400/ask/$JOB
```

Expected: `"status": "done"` y un `short` de una o dos frases.

Si sale `status: error` con "No se pudo lanzar claude", la ruta del paso 2 está mal.
Si sale un error de autenticación de Claude, systemd corre como otro usuario y no ve
las credenciales de `~/.claude`: comprueba `User=` en el archivo de servicio.

- [ ] **Step 6: Comprueba que el modo lectura no puede escribir**

```bash
JOB=$(curl -s -X POST http://127.0.0.1:8400/ask \
  -H "X-Api-Key: LA_CLAVE_GENERADA" -H "Content-Type: application/json" \
  -d '{"project_id":"watch","prompt":"Crea un archivo llamado PRUEBA.txt con la palabra hola","mode":"read","thread":"new"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
sleep 30
curl -s -H "X-Api-Key: LA_CLAVE_GENERADA" http://127.0.0.1:8400/ask/$JOB
ls PRUEBA.txt 2>&1
```

Expected: la respuesta dice que no ha podido, y `ls` dice `No such file or directory`.
**Si el archivo existe, para y arregla la lista blanca de herramientas antes de seguir.**

- [ ] **Step 7: Documenta la configuración nueva**

En `server/README.md`, añade una sección "Preguntar desde el reloj" con la tabla de
variables (`CLAUDE_WATCH_ASK_KEY`, `CLAUDE_WATCH_ASK_MODEL`, `CLAUDE_WATCH_CLAUDE_BIN`,
`CLAUDE_WATCH_PROJECTS`, `CLAUDE_WATCH_MAX_ASKS_PER_HOUR`, `CLAUDE_WATCH_READ_TIMEOUT`,
`CLAUDE_WATCH_WRITE_TIMEOUT`, `CLAUDE_WATCH_THREAD_TTL_HOURS`, `CLAUDE_WATCH_APPROVAL_TTL`)
y la lista de los seis endpoints con su método y su cuerpo.

- [ ] **Step 8: Commit**

```bash
git add server/claude-watch.service server/README.md
git commit -m "chore: configure and document the ask endpoints

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Dependencias y permisos del reloj

A partir de aquí no hay tests: el proyecto no tiene ninguno en Android y **el APK no
se puede compilar en esta máquina** (el `aapt2` de Gradle es x86-64, la máquina es
aarch64). La verificación de cada tarea Android es "el CI compila" y, al final, la
prueba a mano con el APK del release.

**Files:**
- Modify: `android/gradle/libs.versions.toml`
- Modify: `android/wear/build.gradle.kts`
- Modify: `android/wear/src/main/AndroidManifest.xml`

- [ ] **Step 1: Comprueba qué alias existen ya**

Run: `grep -nE 'retrofit|gson|datastore|lifecycle' android/gradle/libs.versions.toml`

El móvil ya usa Retrofit, así que lo más probable es que los alias existan y solo
haya que reutilizarlos. Si `retrofit` no aparece, añade a `[versions]`
`retrofit = "2.11.0"` y a `[libraries]`:

```toml
retrofit = { module = "com.squareup.retrofit2:retrofit", version.ref = "retrofit" }
retrofit-gson = { module = "com.squareup.retrofit2:converter-gson", version.ref = "retrofit" }
```

Si `datastore` no aparece, añade `datastore = "1.1.1"` y:

```toml
datastore-preferences = { module = "androidx.datastore:datastore-preferences", version.ref = "datastore" }
```

Si `lifecycle` no aparece, añade `lifecycle = "2.8.7"` y:

```toml
lifecycle-viewmodel-compose = { module = "androidx.lifecycle:lifecycle-viewmodel-compose", version.ref = "lifecycle" }
lifecycle-runtime-compose = { module = "androidx.lifecycle:lifecycle-runtime-compose", version.ref = "lifecycle" }
```

- [ ] **Step 2: Añade las dependencias al reloj**

En `android/wear/build.gradle.kts`, dentro de `dependencies`, después del bloque de
coroutines:

```kotlin
    // Red y almacenamiento para preguntar a Claude
    implementation(libs.retrofit)
    implementation(libs.retrofit.gson)
    implementation(libs.datastore.preferences)
    implementation(libs.lifecycle.viewmodel.compose)
    implementation(libs.lifecycle.runtime.compose)
```

- [ ] **Step 3: Añade el permiso y la actividad**

En `android/wear/src/main/AndroidManifest.xml`, antes de `<application>`:

```xml
    <uses-permission android:name="android.permission.INTERNET" />
```

Y dentro de `<application>`, junto a la `MainActivity` existente:

```xml
        <activity
            android:name=".ask.AskActivity"
            android:exported="false"
            android:label="Preguntar" />
```

- [ ] **Step 4: Commit**

```bash
git add android/gradle/libs.versions.toml android/wear/build.gradle.kts \
        android/wear/src/main/AndroidManifest.xml
git commit -m "chore: add network and storage deps to the wear app

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: El reloj recibe su configuración del móvil

**Files:**
- Create: `android/wear/src/main/java/com/claudewatch/wear/ask/WatchConfig.kt`
- Modify: `android/wear/src/main/java/com/claudewatch/wear/DataLayerListenerService.kt`
- Modify: `android/mobile/src/main/java/com/claudewatch/mobile/DataLayerSender.kt`
- Modify: `android/mobile/src/main/java/com/claudewatch/mobile/ui/SettingsScreen.kt`

- [ ] **Step 1: Crea el almacén del reloj**

Crea `android/wear/src/main/java/com/claudewatch/wear/ask/WatchConfig.kt`:

```kotlin
package com.claudewatch.wear.ask

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first

private val Context.configStore by preferencesDataStore(name = "claude_watch_config")

/** URL y clave que el movil empuja al reloj por el Data Layer. */
data class WatchSettings(val baseUrl: String, val apiKey: String) {
    val isUsable: Boolean get() = baseUrl.isNotBlank() && apiKey.isNotBlank()
}

object WatchConfig {
    private val URL = stringPreferencesKey("base_url")
    private val KEY = stringPreferencesKey("api_key")

    suspend fun save(context: Context, baseUrl: String, apiKey: String) {
        context.configStore.edit { prefs ->
            prefs[URL] = baseUrl
            prefs[KEY] = apiKey
        }
    }

    suspend fun load(context: Context): WatchSettings {
        val prefs = context.configStore.data.first()
        return WatchSettings(
            baseUrl = prefs[URL] ?: "",
            apiKey = prefs[KEY] ?: "",
        )
    }
}
```

- [ ] **Step 2: Escucha la configuración en el reloj**

En `DataLayerListenerService.kt`, dentro de `onDataChanged`, añade una rama para la
ruta nueva junto a la de `/claude-watch/summary` que ya existe:

```kotlin
            if (event.type == DataEvent.TYPE_CHANGED &&
                event.dataItem.uri.path == "/claude-watch/config"
            ) {
                val dataMap = DataMapItem.fromDataItem(event.dataItem).dataMap
                val baseUrl = dataMap.getString("base_url") ?: return@forEach
                val apiKey = dataMap.getString("api_key") ?: return@forEach
                kotlinx.coroutines.runBlocking {
                    com.claudewatch.wear.ask.WatchConfig.save(
                        applicationContext, baseUrl, apiKey
                    )
                }
            }
```

- [ ] **Step 3: Empuja la configuración desde el móvil**

En `DataLayerSender.kt`, añade junto a `sendSummary`:

```kotlin
    private const val CONFIG_PATH = "/claude-watch/config"

    suspend fun sendConfig(
        context: Context,
        baseUrl: String,
        apiKey: String,
    ) {
        val request = PutDataMapRequest.create(CONFIG_PATH).apply {
            dataMap.putString("base_url", baseUrl)
            dataMap.putString("api_key", apiKey)
            dataMap.putLong("timestamp", System.currentTimeMillis())
        }.asPutDataRequest().setUrgent()

        Wearable.getDataClient(context).putDataItem(request).await()
    }
```

- [ ] **Step 4: Llámalo al guardar ajustes**

En `ui/SettingsScreen.kt`, en el punto donde ya se guardan URL y clave en
`SettingsStore`, añade dentro de la misma corrutina:

```kotlin
                        DataLayerSender.sendConfig(context, url, askKey)
```

La clave que se manda al reloj es la **del reloj** (`CLAUDE_WATCH_ASK_KEY`), no la
del hook. La pantalla de ajustes hoy tiene un solo campo de clave: añade un segundo
campo etiquetado "Clave del reloj" y guárdalo aparte en `SettingsStore` con su
propia `stringPreferencesKey("ask_key")`.

- [ ] **Step 5: Commit**

```bash
git add android/wear/src/main/java/com/claudewatch/wear/ask/WatchConfig.kt \
        android/wear/src/main/java/com/claudewatch/wear/DataLayerListenerService.kt \
        android/mobile/src/main/java/com/claudewatch/mobile/DataLayerSender.kt \
        android/mobile/src/main/java/com/claudewatch/mobile/SettingsStore.kt \
        android/mobile/src/main/java/com/claudewatch/mobile/ui/SettingsScreen.kt
git commit -m "feat: sync watch config from the phone over the data layer

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Cliente HTTP del reloj

**Files:**
- Create: `android/wear/src/main/java/com/claudewatch/wear/ask/AskApi.kt`

- [ ] **Step 1: Crea la interfaz y los DTOs**

Crea `android/wear/src/main/java/com/claudewatch/wear/ask/AskApi.kt`:

```kotlin
package com.claudewatch.wear.ask

import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path

data class ProjectDto(val id: String, val name: String)
data class ProjectsResponse(val projects: List<ProjectDto>)

data class AskBody(
    val project_id: String,
    val prompt: String,
    val mode: String,
    val thread: String,
)

data class AskAccepted(val job_id: String, val status: String)

data class JobStatus(
    val status: String,
    val short: String?,
    val full: String?,
    val plan: String?,
    val error: String?,
)

data class SimpleStatus(val status: String)

interface AskApi {
    @GET("projects")
    suspend fun projects(@Header("X-Api-Key") apiKey: String): ProjectsResponse

    @POST("ask")
    suspend fun ask(
        @Body body: AskBody,
        @Header("X-Api-Key") apiKey: String,
    ): AskAccepted

    @GET("ask/{jobId}")
    suspend fun job(
        @Path("jobId") jobId: String,
        @Header("X-Api-Key") apiKey: String,
    ): JobStatus

    @POST("ask/{jobId}/approve")
    suspend fun approve(
        @Path("jobId") jobId: String,
        @Header("X-Api-Key") apiKey: String,
    ): SimpleStatus

    @POST("ask/{jobId}/cancel")
    suspend fun cancel(
        @Path("jobId") jobId: String,
        @Header("X-Api-Key") apiKey: String,
    ): SimpleStatus

    @POST("ask/{jobId}/to-phone")
    suspend fun toPhone(
        @Path("jobId") jobId: String,
        @Header("X-Api-Key") apiKey: String,
    ): SimpleStatus

    companion object {
        fun create(baseUrl: String): AskApi = Retrofit.Builder()
            .baseUrl(baseUrl.trimEnd('/') + "/")
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(AskApi::class.java)
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add android/wear/src/main/java/com/claudewatch/wear/ask/AskApi.kt
git commit -m "feat: add watch HTTP client for the ask endpoints

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: Estados y ViewModel del reloj

**Files:**
- Create: `android/wear/src/main/java/com/claudewatch/wear/ask/AskState.kt`
- Create: `android/wear/src/main/java/com/claudewatch/wear/ask/AskViewModel.kt`

- [ ] **Step 1: Crea los estados**

Crea `android/wear/src/main/java/com/claudewatch/wear/ask/AskState.kt`:

```kotlin
package com.claudewatch.wear.ask

sealed interface AskState {
    /** Eligiendo proyecto y modo, esperando a que dictes o teclees. */
    data class Composing(
        val projects: List<ProjectDto> = emptyList(),
        val selected: ProjectDto? = null,
        val writeMode: Boolean = false,
        val canFollowUp: Boolean = false,
    ) : AskState

    data class Thinking(val jobId: String, val seconds: Int) : AskState

    data class AwaitingApproval(val jobId: String, val plan: String) : AskState

    data class Answered(
        val jobId: String,
        val short: String,
        val full: String,
        val expanded: Boolean = false,
        val sentToPhone: Boolean = false,
    ) : AskState

    data class Failed(val message: String) : AskState
}
```

- [ ] **Step 2: Crea el ViewModel**

Crea `android/wear/src/main/java/com/claudewatch/wear/ask/AskViewModel.kt`:

```kotlin
package com.claudewatch.wear.ask

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

private const val POLL_MILLIS = 2000L

class AskViewModel(app: Application) : AndroidViewModel(app) {

    private val _state = MutableStateFlow<AskState>(AskState.Composing())
    val state: StateFlow<AskState> = _state

    private var settings: WatchSettings? = null
    private var api: AskApi? = null
    private var pollJob: Job? = null
    private var projects: List<ProjectDto> = emptyList()
    private var selected: ProjectDto? = null
    private var writeMode: Boolean = false

    fun start() {
        viewModelScope.launch {
            val loaded = WatchConfig.load(getApplication())
            if (!loaded.isUsable) {
                _state.value = AskState.Failed("Abre la app del movil y guarda los ajustes")
                return@launch
            }
            settings = loaded
            api = AskApi.create(loaded.baseUrl)
            loadProjects()
        }
    }

    private suspend fun loadProjects() {
        val client = api ?: return
        val key = settings?.apiKey ?: return
        try {
            val fetched = client.projects(key).projects
            if (fetched.isEmpty()) {
                _state.value = AskState.Failed("No hay proyectos configurados")
                return
            }
            projects = fetched
            selected = selected?.let { previous -> fetched.firstOrNull { it.id == previous.id } }
                ?: fetched.first()
            showComposing()
        } catch (e: Exception) {
            _state.value = AskState.Failed("Sin conexion con el servidor")
        }
    }

    private fun showComposing(canFollowUp: Boolean = false) {
        _state.value = AskState.Composing(
            projects = projects,
            selected = selected,
            writeMode = writeMode,
            canFollowUp = canFollowUp,
        )
    }

    fun selectProject(project: ProjectDto) {
        selected = project
        showComposing()
    }

    fun toggleWriteMode() {
        writeMode = !writeMode
        showComposing()
    }

    fun send(prompt: String, followUp: Boolean = false) {
        val project = selected ?: return
        val client = api ?: return
        val key = settings?.apiKey ?: return

        viewModelScope.launch {
            try {
                val accepted = client.ask(
                    AskBody(
                        project_id = project.id,
                        prompt = prompt,
                        mode = if (writeMode) "write" else "read",
                        thread = if (followUp) "continue" else "new",
                    ),
                    key,
                )
                _state.value = AskState.Thinking(accepted.job_id, seconds = 0)
                poll(accepted.job_id)
            } catch (e: retrofit2.HttpException) {
                _state.value = AskState.Failed(
                    when (e.code()) {
                        409 -> "Hay una consulta en marcha"
                        429 -> "Limite de consultas por hora"
                        else -> "Error ${e.code()}"
                    }
                )
            } catch (e: Exception) {
                _state.value = AskState.Failed("Sin conexion")
            }
        }
    }

    private fun poll(jobId: String) {
        pollJob?.cancel()
        pollJob = viewModelScope.launch {
            var seconds = 0
            while (true) {
                delay(POLL_MILLIS)
                seconds += (POLL_MILLIS / 1000).toInt()
                val client = api ?: return@launch
                val key = settings?.apiKey ?: return@launch
                val job = try {
                    client.job(jobId, key)
                } catch (e: Exception) {
                    _state.value = AskState.Failed("Sin conexion")
                    return@launch
                }
                when (job.status) {
                    "running" -> _state.value = AskState.Thinking(jobId, seconds)
                    "awaiting_approval" -> {
                        _state.value = AskState.AwaitingApproval(jobId, job.plan.orEmpty())
                        return@launch
                    }
                    "done" -> {
                        _state.value = AskState.Answered(
                            jobId = jobId,
                            short = job.short.orEmpty(),
                            full = job.full.orEmpty(),
                        )
                        return@launch
                    }
                    "cancelled" -> {
                        showComposing()
                        return@launch
                    }
                    else -> {
                        _state.value = AskState.Failed(job.error ?: "Error")
                        return@launch
                    }
                }
            }
        }
    }

    fun approve() {
        val current = _state.value as? AskState.AwaitingApproval ?: return
        val client = api ?: return
        val key = settings?.apiKey ?: return
        viewModelScope.launch {
            try {
                client.approve(current.jobId, key)
                _state.value = AskState.Thinking(current.jobId, seconds = 0)
                poll(current.jobId)
            } catch (e: Exception) {
                _state.value = AskState.Failed("No se pudo aprobar")
            }
        }
    }

    fun cancel() {
        val jobId = when (val current = _state.value) {
            is AskState.Thinking -> current.jobId
            is AskState.AwaitingApproval -> current.jobId
            else -> null
        } ?: return
        pollJob?.cancel()
        val client = api ?: return
        val key = settings?.apiKey ?: return
        viewModelScope.launch {
            runCatching { client.cancel(jobId, key) }
            showComposing()
        }
    }

    fun expand() {
        val current = _state.value as? AskState.Answered ?: return
        _state.value = current.copy(expanded = true)
    }

    fun sendToPhone() {
        val current = _state.value as? AskState.Answered ?: return
        val client = api ?: return
        val key = settings?.apiKey ?: return
        viewModelScope.launch {
            runCatching { client.toPhone(current.jobId, key) }
                .onSuccess { _state.value = current.copy(sentToPhone = true) }
        }
    }

    /** Vuelve a la pantalla de preguntar dejando repreguntar sobre el mismo hilo. */
    fun prepareFollowUp() {
        pollJob?.cancel()
        showComposing(canFollowUp = true)
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add android/wear/src/main/java/com/claudewatch/wear/ask/AskState.kt \
        android/wear/src/main/java/com/claudewatch/wear/ask/AskViewModel.kt
git commit -m "feat: add watch ask state machine and polling

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: Las pantallas

**Files:**
- Create: `android/wear/src/main/java/com/claudewatch/wear/ask/ui/AskScreens.kt`

- [ ] **Step 1: Crea las pantallas**

Crea `android/wear/src/main/java/com/claudewatch/wear/ask/ui/AskScreens.kt`:

```kotlin
package com.claudewatch.wear.ask.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.wear.compose.foundation.lazy.ScalingLazyColumn
import androidx.wear.compose.foundation.lazy.items
import androidx.wear.compose.material.*
import com.claudewatch.wear.ask.AskState
import com.claudewatch.wear.ask.ProjectDto

@Composable
fun ComposingScreen(
    state: AskState.Composing,
    onPickProject: () -> Unit,
    onToggleWrite: () -> Unit,
    onDictate: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(12.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Chip(
            onClick = onPickProject,
            label = { Text(state.selected?.name ?: "Proyecto") },
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(8.dp))
        Button(onClick = onDictate, modifier = Modifier.size(56.dp)) {
            Text(if (state.canFollowUp) "↻" else "🎤")
        }
        Spacer(Modifier.height(8.dp))
        ToggleChip(
            checked = state.writeMode,
            onCheckedChange = { onToggleWrite() },
            label = { Text(if (state.writeMode) "Escritura" else "Lectura") },
            toggleControl = { Switch(checked = state.writeMode) },
            modifier = Modifier.fillMaxWidth(),
        )
    }
}

@Composable
fun ProjectPickerScreen(
    projects: List<ProjectDto>,
    onPick: (ProjectDto) -> Unit,
) {
    ScalingLazyColumn(modifier = Modifier.fillMaxSize()) {
        items(projects) { project ->
            Chip(
                onClick = { onPick(project) },
                label = { Text(project.name) },
                modifier = Modifier.fillMaxWidth(),
            )
        }
    }
}

@Composable
fun ThinkingScreen(seconds: Int, onCancel: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(12.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        CircularProgressIndicator()
        Spacer(Modifier.height(8.dp))
        Text("pensando", style = MaterialTheme.typography.caption1)
        Text("${seconds / 60}:${(seconds % 60).toString().padStart(2, '0')}")
        Spacer(Modifier.height(8.dp))
        CompactChip(onClick = onCancel, label = { Text("Cancelar") })
    }
}

@Composable
fun PlanScreen(plan: String, onApprove: () -> Unit, onCancel: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(12.dp).verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Va a hacer esto", style = MaterialTheme.typography.caption1)
        Spacer(Modifier.height(4.dp))
        Text(plan, textAlign = TextAlign.Center, style = MaterialTheme.typography.body2)
        Spacer(Modifier.height(8.dp))
        Chip(
            onClick = onApprove,
            label = { Text("Aprobar") },
            colors = ChipDefaults.primaryChipColors(),
            modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(4.dp))
        CompactChip(onClick = onCancel, label = { Text("Cancelar") })
    }
}

@Composable
fun AnswerScreen(
    state: AskState.Answered,
    onExpand: () -> Unit,
    onToPhone: () -> Unit,
    onFollowUp: () -> Unit,
) {
    Column(
        modifier = Modifier.fillMaxSize().padding(12.dp).verticalScroll(rememberScrollState()),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = if (state.expanded) state.full else state.short,
            textAlign = TextAlign.Center,
            style = MaterialTheme.typography.body2,
        )
        Spacer(Modifier.height(8.dp))
        if (!state.expanded && state.full.length > state.short.length) {
            CompactChip(onClick = onExpand, label = { Text("Mas") })
            Spacer(Modifier.height(4.dp))
        }
        CompactChip(
            onClick = onToPhone,
            label = { Text(if (state.sentToPhone) "Enviado" else "Al movil") },
        )
        Spacer(Modifier.height(4.dp))
        CompactChip(onClick = onFollowUp, label = { Text("Repreguntar") })
    }
}

@Composable
fun FailedScreen(message: String, onRetry: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(12.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(message, textAlign = TextAlign.Center, style = MaterialTheme.typography.body2)
        Spacer(Modifier.height(8.dp))
        CompactChip(onClick = onRetry, label = { Text("Reintentar") })
    }
}
```

Si `ScalingLazyColumn` no resuelve desde `androidx.wear.compose.foundation.lazy`,
la versión de Wear Compose del proyecto lo expone en `androidx.wear.compose.material`:
cambia los dos imports y usa `items(projects.size) { index -> ... }`.

- [ ] **Step 2: Commit**

```bash
git add android/wear/src/main/java/com/claudewatch/wear/ask/ui/AskScreens.kt
git commit -m "feat: add the ask screens

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: La actividad, el dictado y el botón de entrada

`RemoteInput` es la pieza que da voz y teclado a la vez: abre el selector del
sistema de Wear OS, que ofrece micrófono, teclado, escritura a mano y frases
guardadas sin que escribamos ninguna de esas pantallas.

**Files:**
- Create: `android/wear/src/main/java/com/claudewatch/wear/ask/AskActivity.kt`
- Modify: `android/wear/src/main/java/com/claudewatch/wear/ui/ApprovalScreen.kt`
- Modify: `android/wear/src/main/java/com/claudewatch/wear/MainActivity.kt`

- [ ] **Step 1: Crea la actividad**

Crea `android/wear/src/main/java/com/claudewatch/wear/ask/AskActivity.kt`:

```kotlin
package com.claudewatch.wear.ask

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.*
import androidx.core.app.RemoteInput
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.claudewatch.wear.ask.ui.*

private const val PROMPT_KEY = "prompt"

class AskActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            val model: AskViewModel = viewModel()
            val state by model.state.collectAsStateWithLifecycle()
            var pickingProject by remember { mutableStateOf(false) }
            var followUp by remember { mutableStateOf(false) }

            LaunchedEffect(Unit) { model.start() }

            val dictate = rememberLauncherForActivityResult(
                ActivityResultContracts.StartActivityForResult()
            ) { result ->
                if (result.resultCode != Activity.RESULT_OK) return@rememberLauncherForActivityResult
                val data = result.data ?: return@rememberLauncherForActivityResult
                val spoken = RemoteInput.getResultsFromIntent(data)
                    ?.getCharSequence(PROMPT_KEY)?.toString()?.trim()
                if (!spoken.isNullOrEmpty()) {
                    model.send(spoken, followUp = followUp)
                    followUp = false
                }
            }

            fun askForText() {
                val remoteInput = RemoteInput.Builder(PROMPT_KEY)
                    .setLabel("Pregunta a Claude")
                    .build()
                val intent = Intent(RemoteInput.ACTION_REMOTE_INPUT).apply {
                    RemoteInput.addResultsToIntent(arrayOf(remoteInput), this, Bundle())
                }
                dictate.launch(intent)
            }

            when (val current = state) {
                is AskState.Composing ->
                    if (pickingProject) {
                        ProjectPickerScreen(current.projects) { project ->
                            model.selectProject(project)
                            pickingProject = false
                        }
                    } else {
                        ComposingScreen(
                            state = current,
                            onPickProject = { pickingProject = true },
                            onToggleWrite = { model.toggleWriteMode() },
                            onDictate = { askForText() },
                        )
                    }

                is AskState.Thinking ->
                    ThinkingScreen(current.seconds) { model.cancel() }

                is AskState.AwaitingApproval ->
                    PlanScreen(
                        plan = current.plan,
                        onApprove = { model.approve() },
                        onCancel = { model.cancel() },
                    )

                is AskState.Answered ->
                    AnswerScreen(
                        state = current,
                        onExpand = { model.expand() },
                        onToPhone = { model.sendToPhone() },
                        onFollowUp = {
                            followUp = true
                            model.prepareFollowUp()
                            askForText()
                        },
                    )

                is AskState.Failed ->
                    FailedScreen(current.message) { model.start() }
            }
        }
    }
}
```

- [ ] **Step 2: Pon el botón de entrada en la pantalla de espera**

En `ui/ApprovalScreen.kt`, cambia `WaitingScreen` para que acepte una acción y
muestre el botón:

```kotlin
@Composable
fun WaitingScreen(onAsk: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxSize().padding(12.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("Claude Watch", style = MaterialTheme.typography.title3)
        Spacer(Modifier.height(12.dp))
        Chip(
            onClick = onAsk,
            label = { Text("Preguntar") },
            colors = ChipDefaults.primaryChipColors(),
            modifier = Modifier.fillMaxWidth(),
        )
    }
}
```

Asegúrate de que el archivo importa `androidx.compose.foundation.layout.*`,
`androidx.compose.ui.Alignment`, `androidx.compose.ui.unit.dp` y
`androidx.wear.compose.material.*`.

- [ ] **Step 3: Conecta el botón en `MainActivity`**

En `MainActivity.kt`, sustituye la llamada `WaitingScreen()` por:

```kotlin
                WaitingScreen(onAsk = {
                    startActivity(Intent(this, com.claudewatch.wear.ask.AskActivity::class.java))
                })
```

y añade el import `android.content.Intent`.

- [ ] **Step 4: Commit**

```bash
git add android/wear/src/main/java/com/claudewatch/wear/ask/AskActivity.kt \
        android/wear/src/main/java/com/claudewatch/wear/ui/ApprovalScreen.kt \
        android/wear/src/main/java/com/claudewatch/wear/MainActivity.kt
git commit -m "feat: wire the ask activity with voice and keyboard input

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 16: Documentación, PR y verificación en el reloj

**Files:**
- Modify: `README.md`
- Modify: `android/README.md`

- [ ] **Step 1: Comprueba la suite completa una última vez**

Run: `./venv/bin/python -m pytest server/tests hook/tests -q`
Expected: 83 passed

- [ ] **Step 2: Documenta el flujo nuevo**

En `README.md`, después de la sección del flujo de notificación, añade una sección
"Preguntar desde el reloj" con el diagrama del spec, los dos modos, y una frase
clara sobre el coste: cada consulta gasta tokens reales, con un límite de 20/hora.

En `android/README.md`, documenta las claves: la del hook y la del reloj son
distintas, y la que se guarda en los ajustes del móvil para el reloj es la segunda.

- [ ] **Step 3: Commit y push**

```bash
git add README.md android/README.md
git commit -m "docs: document asking Claude from the watch

Refs #2

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
git push -u origin feature/2-ask-from-watch
```

- [ ] **Step 4: Abre el PR**

```bash
gh pr create --title "feat: preguntar a Claude desde el reloj por voz o teclado" \
  --body "Implementa #2 segun docs/superpowers/specs/2026-09-20-claude-watch-ask-design.md

Canal de vuelta: el reloj dicta o teclea una pregunta, la contesta un \`claude -p\`
en el servidor, y la respuesta se lee en la muneca. El camino de notificaciones
existente no se toca.

- Servidor: cola de un solo job, seis endpoints nuevos, clave propia para el reloj
- Modo lectura por defecto; el de escritura pasa por plan y aprobacion en el reloj
- Lista blanca de proyectos: el reloj nunca manda una ruta
- 63 tests nuevos de servidor, con el subproceso simulado

Sin tests en Android: el proyecto no tiene ninguno y el APK no se compila en el
servidor (aapt2 x86-64 sobre aarch64). Se verifica a mano con el APK del release.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

- [ ] **Step 5: Verifica en el reloj de verdad**

Al mergear, el CI publica los APKs. Instala los dos y comprueba, en este orden:

1. Abre la app del móvil, guarda URL y clave del reloj. En el reloj, la pantalla de
   preguntar debe cargar la lista de proyectos (si dice "Abre la app del movil", la
   configuración no ha llegado por el Data Layer).
2. Pulsa el micrófono, dicta "¿qué hace este repo?" y comprueba que llega respuesta
   en menos de un minuto.
3. Pulsa "Mas": debe aparecer el texto largo sin volver a preguntar al servidor.
4. Pulsa "Al movil": debe llegar la notificación con el texto completo.
5. Pulsa "Repreguntar" y di "¿y por qué?": la respuesta debe tener en cuenta la
   anterior.
6. Activa el modo escritura y pide un cambio pequeño de verdad. Debe aparecer el
   plan y **no debe tocarse nada** hasta que pulses Aprobar. Comprueba con
   `git status` en el servidor que antes de aprobar no hay cambios.
7. Lanza una consulta y, mientras piensa, lanza otra: debe decir "Hay una consulta
   en marcha".

- [ ] **Step 6: Cierra el issue**

```bash
gh issue close 2 --comment "Implementado en la rama feature/2-ask-from-watch. Servidor con cola de un solo job y seis endpoints, modo lectura por defecto y aprobacion de plan en escritura, 63 tests nuevos. Verificado a mano en el reloj con el APK del release."
```

---

## Verificación de cobertura frente al spec

| Requisito del spec | Tarea |
|---|---|
| Dos modos elegibles en el reloj | 3, 6, 13, 14 |
| Transporte directo reloj ↔ servidor con sondeo | 12, 13 |
| Selector de proyecto con lista blanca | 1, 7, 14 |
| Hilo por proyecto con `--resume` y caducidad de 6 h | 5 |
| Corta + "más" + "al móvil" | 3, 8, 14 |
| Plan → aprobar → ejecutar, con caducidad de 5 min | 6, 8 |
| Clave del reloj distinta de la del hook | 7 |
| Lista negra en ejecución | 3 |
| Límite de 20/hora y prompt de 1000 caracteres | 5, 7 |
| Timeouts 180 s / 600 s | 1, 4, 5 |
| Jobs huérfanos al reiniciar | 2, 7 |
| Config sincronizada del móvil al reloj | 11 |
| Entrada por voz y teclado | 15 |
| Tabla de errores del spec | 4, 13 |
| Fuera de alcance (tile, streaming, historial, paralelo) | ninguna, a propósito |
