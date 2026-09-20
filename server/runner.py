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
