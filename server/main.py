from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from server.config import API_KEY, DB_PATH
from server.database import ApprovalDB
from server.fcm import send_info_notification

app = FastAPI(title="Claude Watch")
db = ApprovalDB(DB_PATH)


def verify_api_key(x_api_key: str = Header()):
    import hmac
    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=403, detail="Invalid API key")


class NotifyRequest(BaseModel):
    tool_name: str = Field(..., max_length=200)
    summary: str = Field(..., max_length=2000)
    result: str | None = Field(default=None, max_length=5000)


class DeviceRegistration(BaseModel):
    fcm_token: str = Field(..., min_length=10, max_length=500)


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
