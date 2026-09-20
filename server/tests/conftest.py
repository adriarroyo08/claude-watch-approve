"""Entorno compartido de los tests.

server/config.py lee os.environ una sola vez al importarse, asi que estas
variables tienen que estar puestas antes de que cualquier modulo de test
importe server.main. conftest.py se carga antes que los tests, que es el
unico sitio donde esto funciona de forma fiable.

Se fuerza la asignacion (no setdefault): esta maquina ya tiene
CLAUDE_WATCH_API_KEY puesta en el shell para el servidor real desplegado, y
setdefault la habria respetado, dejando que quien importe server.main
primero arrastrase el secreto real a los tests en vez de "test-api-key".
"""
import os
import tempfile

_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_fd)

os.environ["CLAUDE_WATCH_DB_PATH"] = _db_path
os.environ["CLAUDE_WATCH_API_KEY"] = "test-api-key"
os.environ["CLAUDE_WATCH_ASK_KEY"] = "watch-key"
os.environ["CLAUDE_WATCH_PROJECTS"] = "ahorrapp:/tmp;petwatch:/tmp"
