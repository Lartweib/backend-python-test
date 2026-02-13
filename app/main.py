import uuid
import asyncio
from typing import Literal
from enum import Enum

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

app = FastAPI(title="Notification Service (Technical Test)")

# --- Configuration ---

PROVIDER_URL = "http://localhost:3001"
API_KEY = "test-dev-2026"


# --- Enums ---


class NotificationStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"


# --- Schemas ---


class CreateRequest(BaseModel):
    to: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    type: Literal["email", "sms", "push"]


class RequestResponse(BaseModel):
    id: str


class StatusResponse(BaseModel):
    id: str
    status: NotificationStatus


# --- In-memory store ---

_store: dict[str, dict] = {}

# --- Provider client ---

_http_client: httpx.AsyncClient | None = None


@app.on_event("startup")
async def startup():
    global _http_client
    _http_client = httpx.AsyncClient(timeout=10.0)


@app.on_event("shutdown")
async def shutdown():
    if _http_client:
        await _http_client.aclose()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((
        httpx.HTTPStatusError,
        httpx.HTTPError,
    )),
)
async def _call_provider(to: str, message: str, type: str) -> httpx.Response:
    response = await _http_client.post(
        f"{PROVIDER_URL}/v1/notify",
        json={
            "to": to,
            "message": message,
            "type": type,
        },
        headers={"X-API-Key": API_KEY},
    )

    # Retry on these status codes
    if response.status_code in (429, 500):
        response.raise_for_status()

    return response


async def _send_to_provider(
    request_id: str, to: str, message: str, type: str
) -> None:
    try:
        response = await _call_provider(to, message, type)
        _store[request_id]["status"] = (
            NotificationStatus.SENT
            if response.status_code == 200
            else NotificationStatus.FAILED
        )
    except Exception:
        _store[request_id]["status"] = NotificationStatus.FAILED

# --- Routes ---


@app.post("/v1/requests", status_code=201, response_model=RequestResponse)
async def create_request(body: CreateRequest) -> RequestResponse:
    request_id = str(uuid.uuid4())
    _store[request_id] = {
        "id": request_id,
        "status": NotificationStatus.QUEUED,
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

    if row["status"] == NotificationStatus.QUEUED:
        row["status"] = NotificationStatus.PROCESSING
        asyncio.create_task(
            _send_to_provider(
                request_id, row["to"], row["message"], row["type"]
            )
        )
        return Response(status_code=202)

    return Response(status_code=200)
