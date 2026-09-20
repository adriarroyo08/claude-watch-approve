import hmac
import sys
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from server.config import API_KEY, ASK_KEY, DB_PATH, PROJECTS
from server.database import ApprovalDB
from server.fcm import send_info_notification
from server.jobs import Busy, JobManager, NotApprovable, RateLimited

db = ApprovalDB(DB_PATH)
job_manager = JobManager(db=db)

INSECURE_DEFAULT = "change-me-in-production"


def _on_startup() -> None:
    """Lo que toca al empezar a servir de verdad, no al importar el modulo."""
    # Los jobs que quedaron corriendo ya no tienen proceso detras.
    db.orphan_running_jobs()
    if ASK_KEY == INSECURE_DEFAULT:
        print(
            "AVISO: CLAUDE_WATCH_ASK_KEY sin configurar. Los endpoints del "
            "reloj devolveran 503 hasta que se ponga una clave.",
            file=sys.stderr,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _on_startup()
    yield


app = FastAPI(title="Claude Watch", lifespan=lifespan)


def _keys_match(provided: str, expected: str) -> bool:
    """Compara en tiempo constante, sin romperse con basura de internet.

    compare_digest lanza TypeError si le llegan str con caracteres fuera de
    ASCII, asi que una cabecera como 'X-Api-Key: cafe con acento' convertia
    la comprobacion de credenciales en un 500. Se comparan bytes.
    """
    try:
        return hmac.compare_digest(provided.encode(), expected.encode())
    except (AttributeError, UnicodeEncodeError):
        return False


def verify_api_key(x_api_key: str = Header()):
    """Clave del hook: solo abre /notify y /register-device."""
    if not _keys_match(x_api_key, API_KEY):
        raise HTTPException(status_code=403, detail="Clave no valida")


def verify_ask_key(x_api_key: str = Header()):
    """Clave del reloj: solo abre /projects y /ask*.

    Son dos claves distintas a proposito: perder el reloj se arregla
    revocando una sola, sin tocar las notificaciones.
    """
    if ASK_KEY == INSECURE_DEFAULT:
        # Fallar cerrado. El valor por defecto esta escrito en config.py, que
        # esta publicado, y estos endpoints lanzan procesos. Un despliegue que
        # se olvide de la clave debe romperse ruidosamente, no quedarse abierto.
        raise HTTPException(
            status_code=503, detail="CLAUDE_WATCH_ASK_KEY sin configurar"
        )
    if not _keys_match(x_api_key, ASK_KEY):
        raise HTTPException(status_code=403, detail="Clave no valida")


def get_project(project_id: str):
    """Traduce el id que manda el reloj a un proyecto de la lista blanca.

    El reloj nunca manda una ruta. Un id que no sea clave del diccionario
    simplemente no existe, asi que '../../etc' da 404 sin necesidad de
    sanear nada.
    """
    project = PROJECTS.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="No existe ese proyecto")
    return project


class NotifyRequest(BaseModel):
    tool_name: str = Field(..., max_length=200)
    summary: str = Field(..., max_length=2000)
    result: str | None = Field(default=None, max_length=5000)


class DeviceRegistration(BaseModel):
    fcm_token: str = Field(..., min_length=10, max_length=500)


class AskRequest(BaseModel):
    project_id: str = Field(..., max_length=100)
    prompt: str = Field(..., min_length=1, max_length=1000)
    mode: Literal["read", "write"] = "read"
    thread: Literal["new", "continue"] = "new"


@app.post("/notify", status_code=201, dependencies=[Depends(verify_api_key)])
def notify(body: NotifyRequest):
    tokens = db.get_device_tokens()
    message = body.result or body.summary
    try:
        send_info_notification(
            tokens=tokens,
            tool_name=body.tool_name,
            message=message,
        )
    except Exception:
        pass
    return {"status": "sent", "devices": len(tokens)}


@app.post("/register-device", dependencies=[Depends(verify_api_key)])
def register_device(body: DeviceRegistration):
    db.register_device(body.fcm_token)
    return {"status": "registered"}


@app.get("/projects", dependencies=[Depends(verify_ask_key)])
def list_projects():
    # Solo id y nombre: la ruta del proyecto no sale del servidor.
    return {
        "projects": [
            {"id": project.id, "name": project.name} for project in PROJECTS.values()
        ]
    }


@app.post("/ask", status_code=202, dependencies=[Depends(verify_ask_key)])
async def ask(body: AskRequest):
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


@app.get("/ask/{job_id}", dependencies=[Depends(verify_ask_key)])
def get_ask(job_id: str):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No existe ese trabajo")
    return {
        "status": job["status"],
        "short": job["short_text"],
        "full": job["full_text"],
        "plan": job["plan"],
        "error": job["error"],
    }


@app.post("/ask/{job_id}/approve", dependencies=[Depends(verify_ask_key)])
async def approve_ask(job_id: str):
    """Ejecuta un plan que la persona ha aprobado en el reloj.

    Es el unico endpoint de este servidor que puede modificar archivos.
    El proyecto sale de la fila, no del cliente: aprobar un plan de un repo
    dentro de otro es exactamente lo que no puede pasar.
    """
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No existe ese trabajo")
    project = get_project(job["project_id"])
    try:
        await job_manager.approve(job_id, project)
    except NotApprovable as exc:
        raise HTTPException(status_code=409, detail=exc.reason)
    except Busy:
        raise HTTPException(status_code=409, detail="Hay una consulta en marcha")
    return {"status": "running"}


@app.post("/ask/{job_id}/cancel", dependencies=[Depends(verify_ask_key)])
async def cancel_ask(job_id: str):
    status = await job_manager.cancel(job_id)
    if status is None:
        raise HTTPException(status_code=404, detail="No existe ese trabajo")
    # Devuelve el estado real: si el job ya habia terminado no se cancelo
    # nada, y el reloj no debe creerse lo contrario.
    return {"status": status}


@app.post("/ask/{job_id}/to-phone", dependencies=[Depends(verify_ask_key)])
def send_ask_to_phone(job_id: str):
    job = db.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No existe ese trabajo")
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
