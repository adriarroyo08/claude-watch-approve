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
