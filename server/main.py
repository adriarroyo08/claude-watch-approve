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
    """Traduce el id que manda el reloj a un proyecto de la lista blanca.

    El reloj nunca manda una ruta. Un id que no sea clave del diccionario
    simplemente no existe, asi que '../../etc' da 404 sin necesidad de
    sanear nada.
    """
    project = PROJECTS.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Unknown project")
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


@app.post("/notify", status_code=201)
def notify(body: NotifyRequest, x_api_key: str = Header()):
    verify_api_key(x_api_key)
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


@app.post("/register-device")
def register_device(body: DeviceRegistration, x_api_key: str = Header()):
    verify_api_key(x_api_key)
    db.register_device(body.fcm_token)
    return {"status": "registered"}


@app.get("/projects")
def list_projects(x_api_key: str = Header()):
    verify_ask_key(x_api_key)
    # Solo id y nombre: la ruta del proyecto no sale del servidor.
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
