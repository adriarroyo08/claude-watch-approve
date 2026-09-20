import asyncio
import json
import os
import signal
from dataclasses import dataclass, field
from typing import Literal

from server.config import ASK_MODEL, CLAUDE_BIN

BREVITY_PROMPT = (
    "Responde con una primera linea de 40 palabras o menos que conteste "
    "directamente, sin preambulo. Despues una linea en blanco. Despues el "
    "detalle si lo hay. Sin markdown ni tablas: esto se lee en un reloj."
)

# Lo consume jobs.py al aprobar un plan: se pasa como prompt de la fase exec.
EXEC_PROMPT = "Ejecuta el plan que acabas de describir."

# LIMITE DE SEGURIDAD. Esta lista es lo unico que impide que el modo lectura
# escriba: con --permission-prompts none, cualquier herramienta que no este
# aqui se deniega sola. Ampliarla es una decision deliberada, no un retoque.
READ_TOOLS = (
    "Read",
    "Grep",
    "Glob",
    "Bash(git log:*)",
    "Bash(git diff:*)",
    "Bash(git status:*)",
)

# LIMITE DE SEGURIDAD. Segundo cinturon de la fase exec, que corre sin
# vigilancia despues de que apruebes en el reloj. Recortarla es una decision
# deliberada: esta maquina sostiene el tunel de cloudflared y 19 contenedores.
EXEC_DENIED_TOOLS = (
    "Bash(git push:*)",
    "Bash(sudo:*)",
    "Bash(systemctl:*)",
    "Bash(docker:*)",
    "Bash(rm:*)",
    "WebFetch",
)

SHORT_MAX = 200


def build_command(
    phase: Literal["read", "plan", "exec"],
    prompt: str,
    session_id: str | None = None,
) -> list[str]:
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
    full = text.replace("\r\n", "\n").strip()
    if not full:
        return "", ""
    head, separator, _ = full.partition("\n\n")
    short = head.strip() if separator else full
    return short[:SHORT_MAX], full


ERROR_MAX = 300


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

    Usa create_subprocess_exec con argv como lista: no hay shell de por
    medio, asi que el prompt del usuario no puede inyectar comandos.

    Nunca lanza excepciones: cualquier fallo vuelve como RunResult(ok=False)
    con un mensaje que cabe en un reloj. Si una excepcion se escapara de
    aqui, el job se quedaria en 'running' para siempre.
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
        # start_new_session=True mete el proceso en su propio grupo,
        # asi que matamos el grupo entero: si claude lanzo hijos (por
        # ejemplo herramientas Bash), un kill() simple al proceso
        # principal los deja huerfanos corriendo hasta que terminen solos.
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()
        return RunResult(ok=False, error="Tardo demasiado")

    if process.returncode != 0:
        message = stderr.decode(errors="replace").strip() or "claude fallo sin decir por que"
        return RunResult(ok=False, error=message[:ERROR_MAX])

    try:
        payload = json.loads(stdout.decode(errors="replace"))
    except json.JSONDecodeError:
        return RunResult(ok=False, error="Respuesta ilegible de claude")

    if not isinstance(payload, dict):
        return RunResult(ok=False, error="Respuesta ilegible de claude")

    text = payload.get("result") or ""
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
