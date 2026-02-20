"""HTTP client for the notification provider with retries."""

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from config import settings
from schemas import NotificationStatus
from store import update_status

_http_client: httpx.AsyncClient | None = None


def init_client() -> None:
    """Create the shared HTTP client. Call from app startup."""
    global _http_client
    _http_client = httpx.AsyncClient(
        timeout=settings.provider_timeout_seconds
    )


async def close_client() -> None:
    """Close the shared HTTP client. Call from app shutdown."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None


@retry(
    stop=stop_after_attempt(settings.provider_retry_attempts),
    wait=wait_exponential(
        multiplier=0.5,
        min=settings.provider_retry_min_wait,
        max=settings.provider_retry_max_wait,
    ),
    retry=retry_if_exception_type((
        httpx.HTTPStatusError,
        httpx.HTTPError,
    )),
)
async def call_provider(to: str, message: str, type: str) -> httpx.Response:
    """Send notification to provider.Retries on 429, 500 and network errors."""
    if _http_client is None:
        raise RuntimeError("HTTP client not initialized")
    response = await _http_client.post(
        f"{settings.provider_url}/v1/notify",
        json={"to": to, "message": message, "type": type},
        headers={"X-API-Key": settings.provider_api_key},
    )
    if response.status_code in (429, 500):
        response.raise_for_status()
    return response


async def send_to_provider(
    request_id: str, to: str, message: str, type: str
) -> None:
    """Call provider and update request status (sent/failed) in store."""
    try:
        response = await call_provider(to, message, type)
        status = (
            NotificationStatus.SENT
            if response.status_code == 200
            else NotificationStatus.FAILED
        )
        update_status(request_id, status)
    except Exception:
        update_status(request_id, NotificationStatus.FAILED)
