"""Request/response models and enums."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class NotificationStatus(str, Enum):
    """Lifecycle of a notification request."""

    QUEUED = "queued"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"


class CreateRequest(BaseModel):
    """Body for creating a notification request."""

    to: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    type: Literal["email", "sms", "push"]


class RequestResponse(BaseModel):
    """Response after creating a request."""

    id: str


class StatusResponse(BaseModel):
    """Response for request status."""

    id: str
    status: NotificationStatus
