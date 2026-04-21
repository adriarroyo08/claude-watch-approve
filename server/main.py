from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from server.config import API_KEY, DB_PATH
from server.database import ApprovalDB
from server.fcm import send_approval_notification

app = FastAPI(title="Claude Watch Approve")
db = ApprovalDB(DB_PATH)


def verify_api_key(x_api_key: str = Header()):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")


class ApprovalRequest(BaseModel):
    tool_name: str
    tool_input_summary: str
    context: str | None = None


class ApprovalResponse(BaseModel):
    approved: bool


class DeviceRegistration(BaseModel):
    fcm_token: str


@app.post("/approval-request", status_code=201)
def create_approval(body: ApprovalRequest, x_api_key: str = Header()):
    verify_api_key(x_api_key)
    approval = db.create_approval(body.tool_name, body.tool_input_summary, body.context)
    tokens = db.get_device_tokens()
    send_approval_notification(
        tokens=tokens,
        approval_id=approval["id"],
        tool_name=body.tool_name,
        summary=body.tool_input_summary,
    )
    return approval


@app.get("/approval-status/{approval_id}")
def get_approval_status(approval_id: str, x_api_key: str = Header()):
    verify_api_key(x_api_key)
    approval = db.get_approval(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return {"id": approval["id"], "status": approval["status"]}


@app.post("/approval-response/{approval_id}")
def respond_to_approval(approval_id: str, body: ApprovalResponse, x_api_key: str = Header()):
    verify_api_key(x_api_key)
    status = "approved" if body.approved else "denied"
    success = db.resolve_approval(approval_id, status)
    if not success:
        raise HTTPException(status_code=404, detail="Approval not found or already resolved")
    return {"id": approval_id, "status": status}


@app.post("/register-device")
def register_device(body: DeviceRegistration, x_api_key: str = Header()):
    verify_api_key(x_api_key)
    db.register_device(body.fcm_token)
    return {"status": "registered"}
