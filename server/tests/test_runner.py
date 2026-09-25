import pytest
from server.runner import build_command, split_answer


def _flag_values(cmd, flag):
    """Devuelve los valores que siguen a un flag hasta el siguiente flag.

    Ojo: corta en el primer elemento que empiece por "--", asi que no sirve
    para leer un valor que pueda empezar asi (por ejemplo el prompt del
    usuario). Para eso, trocea el comando directamente.
    """
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
    assert "Bash(git status:*)" in tools
    assert "Edit" not in tools
    assert "Write" not in tools


def test_read_command_allows_no_git_command_that_writes_files():
    # git log y git diff aceptan --output=<fichero>: con ellos el modo
    # lectura podia escribir en cualquier ruta.
    tools = _flag_values(build_command("read", "que tal"), "--allowedTools")
    assert not any(t.startswith(("Bash(git log", "Bash(git diff")) for t in tools)


def test_read_command_has_no_permission_mode():
    cmd = build_command("read", "que tal")
    assert "--permission-mode" not in cmd


def test_plan_command_uses_plan_mode():
    cmd = build_command("plan", "arregla el typo")
    assert _flag_values(cmd, "--permission-mode") == ["plan"]
    tools = _flag_values(cmd, "--tools")
    assert tools == ["Read,Grep,Glob,Bash"]
    allowed = _flag_values(cmd, "--allowedTools")
    assert "Read" in allowed
    assert "Edit" not in allowed
    assert "Write" not in allowed


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
    from server.runner import BREVITY_PROMPT
    for phase in ("read", "plan", "exec"):
        cmd = build_command(phase, "hola", session_id="s-1")
        assert _flag_values(cmd, "--append-system-prompt") == [BREVITY_PROMPT]


def test_unknown_phase_raises():
    with pytest.raises(ValueError):
        build_command("borrarlo-todo", "hola")


def test_every_phase_is_restricted():
    """Sin --restricted, claude hereda los permisos globales del usuario."""
    for phase in ("read", "plan", "exec"):
        assert "--restricted" in build_command(phase, "hola", session_id="s-1")


def test_read_and_plan_phases_have_no_writing_tools():
    for phase in ("read", "plan"):
        tools = _flag_values(build_command(phase, "hola"), "--tools")[0]
        assert "Write" not in tools
        assert "Edit" not in tools
        assert "Read" in tools


def test_exec_phase_can_write():
    tools = _flag_values(build_command("exec", "hola", session_id="s-1"), "--tools")[0]
    assert "Edit" in tools
    assert "Write" in tools


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


def test_split_answer_handles_windows_line_endings():
    short, full = split_answer("Corto.\r\n\r\nEl detalle largo.")
    assert short == "Corto."
    assert full == "Corto.\n\nEl detalle largo."


import json
import os
from server.runner import run_claude


def _fake_claude(tmp_path, body: str) -> str:
    """Crea un ejecutable que imita a claude bajo tmp_path.

    Va en tmp_path a proposito: pytest lo limpia pase lo que pase, incluso
    si run_claude lanza o se cuelga, que es justo lo que estos tests cazan.
    """
    script = tmp_path / "fake-claude.sh"
    script.write_text("#!/bin/sh\n" + body)
    script.chmod(0o755)
    return str(script)


@pytest.mark.anyio
async def test_run_claude_parses_successful_json(tmp_path):
    payload = json.dumps({
        "result": "Corto.\n\nLargo.",
        "session_id": "s-99",
        "is_error": False,
        "permission_denials": [],
    })
    script = _fake_claude(tmp_path, f"cat <<'JSON'\n{payload}\nJSON\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    assert result.ok is True
    assert result.short == "Corto."
    assert result.full == "Corto.\n\nLargo."
    assert result.session_id == "s-99"


@pytest.mark.anyio
async def test_run_claude_reports_nonzero_exit(tmp_path):
    script = _fake_claude(tmp_path, "echo 'algo fue mal' >&2\nexit 1\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    assert result.ok is False
    assert "algo fue mal" in result.error


@pytest.mark.anyio
async def test_run_claude_reports_unreadable_output(tmp_path):
    script = _fake_claude(tmp_path, "echo 'esto no es json'\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    assert result.ok is False
    assert "ilegible" in result.error


@pytest.mark.anyio
async def test_run_claude_rejects_json_that_is_not_an_object(tmp_path):
    script = _fake_claude(tmp_path, "echo '[1, 2, 3]'\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    assert result.ok is False
    assert "ilegible" in result.error


@pytest.mark.anyio
async def test_run_claude_times_out_and_kills(tmp_path):
    script = _fake_claude(tmp_path, "sleep 30\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=1)
    assert result.ok is False
    assert "demasiado" in result.error


def _is_alive(pid: int) -> bool:
    """Vivo de verdad: existe y no es un zombi pendiente de recoger."""
    try:
        with open(f"/proc/{pid}/stat") as f:
            estado = f.read().rsplit(") ", 1)[1][0]
    except FileNotFoundError:
        return False
    return estado != "Z"


@pytest.mark.anyio
async def test_run_claude_kills_the_child_when_cancelled(tmp_path):
    """Comprueba SU nieto, no cualquier sleep de la maquina.

    La version anterior miraba 'pgrep -x sleep' en todo el sistema, asi que
    un sleep de otra sesion o de un cron la ponia roja con el codigo bien.
    El sleep va en segundo plano para ser nieto del proceso lanzado: es el
    caso que obligo a matar el grupo entero en vez de solo al hijo.
    """
    import asyncio as aio
    pidfile = tmp_path / "nieto.pid"
    script = _fake_claude(tmp_path, f"sleep 30 &\necho $! > {pidfile}\nwait\n")
    task = aio.create_task(run_claude([script], cwd=str(tmp_path), timeout=60))
    for _ in range(50):           # espera a que el nieto exista de verdad
        if pidfile.exists() and pidfile.read_text().strip():
            break
        await aio.sleep(0.05)
    nieto = int(pidfile.read_text().strip())
    assert _is_alive(nieto), "el nieto no llego a arrancar: el test no probaria nada"

    task.cancel()
    with pytest.raises(aio.CancelledError):
        await task

    for _ in range(40):           # hasta 2 s para que el kill surta efecto
        if not _is_alive(nieto):
            break
        await aio.sleep(0.05)
    assert not _is_alive(nieto), f"el nieto {nieto} sigue vivo tras cancelar"


@pytest.mark.anyio
async def test_run_claude_honours_is_error_flag(tmp_path):
    payload = json.dumps({
        "result": "se acabo el credito",
        "session_id": "s-1",
        "is_error": True,
        "permission_denials": [],
    })
    script = _fake_claude(tmp_path, f"cat <<'JSON'\n{payload}\nJSON\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
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
    script = _fake_claude(tmp_path, f"cat <<'JSON'\n{payload}\nJSON\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    assert result.ok is True
    assert result.denied_tools == ["Edit"]


@pytest.mark.anyio
async def test_run_claude_survives_a_non_string_result(tmp_path):
    payload = json.dumps({"result": 42, "session_id": "s-1", "is_error": False})
    script = _fake_claude(tmp_path, f"cat <<'JSON'\n{payload}\nJSON\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    assert result.ok is True
    assert result.short == ""


@pytest.mark.anyio
async def test_run_claude_ignores_malformed_denials(tmp_path):
    payload = json.dumps({
        "result": "hola", "session_id": "s-1", "is_error": False,
        "permission_denials": ["Edit", {"tool_name": "Write"}],
    })
    script = _fake_claude(tmp_path, f"cat <<'JSON'\n{payload}\nJSON\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    assert result.ok is True
    assert result.denied_tools == ["Write"]


@pytest.mark.anyio
async def test_run_claude_carries_denials_on_the_error_path(tmp_path):
    payload = json.dumps({
        "result": "se acabo el credito",
        "session_id": "s-1",
        "is_error": True,
        "permission_denials": [{"tool_name": "Bash"}],
    })
    script = _fake_claude(tmp_path, f"cat <<'JSON'\n{payload}\nJSON\n")
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    assert result.ok is False
    assert result.denied_tools == ["Bash"]


@pytest.mark.anyio
async def test_run_claude_keeps_the_end_of_a_long_stderr(tmp_path):
    script = _fake_claude(
        tmp_path,
        "python3 -c \"print('ruido ' * 200 + 'LA CAUSA REAL')\" >&2\nexit 1\n",
    )
    result = await run_claude([script], cwd=str(tmp_path), timeout=10)
    assert result.ok is False
    assert "LA CAUSA REAL" in result.error
    assert len(result.error) <= 300
