import asyncio
import uuid
import time
import random
import logging
from typing import Literal

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import httpx

app = FastAPI(title="Notification Service")

PROVIDER_URL = "http://localhost:3001"
PROVIDER_API_KEY = "test-dev-2026"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notification-service")

# In-memory store: request_id -> {id, status, data, created_at}
requests_store: dict[str, dict] = {}

# Limit concurrent outgoing calls
_provider_semaphore = asyncio.Semaphore(15)


class NotificationRequest(BaseModel):
    to: str
    message: str
    type: Literal["email", "sms", "push"]


async def _call_provider(data: dict) -> bool:
    """
    Send notification to provider with basic retry logic.
    Retries only for 429 and 5xx errors.
    """
    max_attempts = 5
    base_delay = 0.5

    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(max_attempts):
            try:
                async with _provider_semaphore:
                    resp = await client.post(
                        f"{PROVIDER_URL}/v1/notify",
                        json=data,
                        headers={"X-API-Key": PROVIDER_API_KEY},
                    )
            except httpx.RequestError as e:
                logger.warning(f"Provider request error: {e}")
                if attempt < max_attempts - 1:
                    await asyncio.sleep(base_delay * (2 ** attempt))
                continue

            if resp.status_code == 200:
                return True

            # reintentar solo si es algo transitorio
            if resp.status_code in (429, 500, 503):
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.2)
                await asyncio.sleep(min(delay, 8.0))
                continue

            return False

    return False


async def _process_in_background(request_id: str) -> None:
    entry = requests_store.get(request_id)
    if not entry:
        return

    logger.info(f"{request_id} - processing")
    entry["status"] = "processing"

    success = await _call_provider(entry["data"])

    entry["status"] = "sent" if success else "failed"
    logger.info(f"{request_id} - {entry['status']}")


@app.post("/v1/requests", status_code=201)
async def create_request(notification: NotificationRequest):
    request_id = str(uuid.uuid4())

    requests_store[request_id] = {
        "id": request_id,
        "status": "queued",
        "data": notification.model_dump(),
        "created_at": time.time(),
    }

    logger.info(f"Request created: {request_id}")

    return {"id": request_id}


@app.post("/v1/requests/{id}/process")
async def process_request(id: str, background_tasks: BackgroundTasks):
    entry = requests_store.get(id)

    if not entry:
        raise HTTPException(status_code=404, detail="Request not found")

    if entry["status"] == "queued":
        background_tasks.add_task(_process_in_background, id)

    return JSONResponse(
        status_code=202,
        content={"id": id, "status": entry["status"]},
    )


@app.get("/v1/requests/{id}")
async def get_request_status(id: str):
    entry = requests_store.get(id)

    if not entry:
        raise HTTPException(status_code=404, detail="Request not found")

    return {"id": id, "status": entry["status"]}
