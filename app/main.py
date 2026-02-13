import uuid
import asyncio
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
import httpx

app = FastAPI(title="Notification Service (Technical Test)")

# --- Schemas ---


class CreateRequest(BaseModel):
    to: str = Field(..., description="Recipient address or identifier")
    message: str = Field(..., description="Notification content")
    type: Literal["email", "sms", "push"] = Field(
        ..., description="Channel type"
    )


class RequestResponse(BaseModel):
    id: str


class StatusResponse(BaseModel):
    id: str
    status: Literal["queued", "processing", "sent", "failed"]

# --- In-memory store ---


RequestStatus = Literal["queued", "processing", "sent", "failed"]
_store: dict[str, dict] = {}  # id -> {id, status, to, message, type}


def _create_id() -> str:
    return str(uuid.uuid4())

# --- Provider client ---


PROVIDER_URL = "http://localhost:3001"
API_KEY = "test-dev-2026"


async def _send_to_provider(request_id: str, to: str, message: str, type: str) -> None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            r = await client.post(
                f"{PROVIDER_URL}/v1/notify",
                json={"to": to, "message": message, "type": type},
                headers={"X-API-Key": API_KEY},
            )
            if r.status_code == 200:
                _store[request_id]["status"] = "sent"
            else:
                _store[request_id]["status"] = "failed"
        except Exception:
            _store[request_id]["status"] = "failed"

# --- Routes ---


@app.post("/v1/requests", status_code=201, response_model=RequestResponse)
async def create_request(body: CreateRequest) -> RequestResponse:
    request_id = _create_id()
    _store[request_id] = {
        "id": request_id,
        "status": "queued",
        "to": body.to,
        "message": body.message,
        "type": body.type,
    }
    return RequestResponse(id=request_id)


@app.get("/v1/requests/{request_id}", response_model=StatusResponse)
async def get_request_status(request_id: str) -> StatusResponse:
    if request_id not in _store:
        raise HTTPException(status_code=404, detail="Request not found")
    row = _store[request_id]
    return StatusResponse(id=row["id"], status=row["status"])


@app.post("/v1/requests/{request_id}/process")
async def process_request(request_id: str) -> Response:
    if request_id not in _store:
        raise HTTPException(status_code=404, detail="Request not found")
    row = _store[request_id]
    if row["status"] == "queued":
        row["status"] = "processing"
        asyncio.create_task(
            _send_to_provider(
                request_id,
                row["to"],
                row["message"],
                row["type"],
            )
        )
        return Response(status_code=202)
    return Response(status_code=200)
