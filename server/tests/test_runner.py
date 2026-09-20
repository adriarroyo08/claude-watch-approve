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
    from server.runner import BREVITY_PROMPT
    for phase in ("read", "plan", "exec"):
        cmd = build_command(phase, "hola", session_id="s-1")
        assert _flag_values(cmd, "--append-system-prompt") == [BREVITY_PROMPT]


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


def test_split_answer_handles_windows_line_endings():
    short, full = split_answer("Corto.\r\n\r\nEl detalle largo.")
    assert short == "Corto."
    assert full == "Corto.\n\nEl detalle largo."


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
async def test_run_claude_rejects_json_that_is_not_an_object(tmp_path):
    script = _fake_claude("echo '[1, 2, 3]'\n")
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
