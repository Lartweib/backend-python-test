"""Notification service API: mediator between clients and the provider."""

import uuid
import asyncio

from fastapi import FastAPI, HTTPException, Response

from schemas import (
    CreateRequest,
    RequestResponse,
    StatusResponse,
    NotificationStatus,
)
from store import create as store_create, get as store_get, update_status
from provider_client import (
    init_client,
    close_client,
    send_to_provider,
)


app = FastAPI(title="Notification Service (Technical Test)")


@app.on_event("startup")
async def startup() -> None:
    init_client()


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_client()


@app.post("/v1/requests", status_code=201, response_model=RequestResponse)
async def create_request(body: CreateRequest) -> RequestResponse:
    request_id = str(uuid.uuid4())
    store_create(
        request_id=request_id,
        to=body.to,
        message=body.message,
        type=body.type,
    )
    return RequestResponse(id=request_id)


@app.get("/v1/requests/{request_id}", response_model=StatusResponse)
async def get_request_status(request_id: str) -> StatusResponse:
    row = store_get(request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")
    return StatusResponse(id=row["id"], status=row["status"])


@app.post("/v1/requests/{request_id}/process")
async def process_request(request_id: str) -> Response:
    row = store_get(request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Request not found")

    if row["status"] == NotificationStatus.QUEUED:
        update_status(request_id, NotificationStatus.PROCESSING)
        asyncio.create_task(
            send_to_provider(
                request_id,
                row["to"],
                row["message"],
                row["type"],
            )
        )
        return Response(status_code=202)

    return Response(status_code=200)
