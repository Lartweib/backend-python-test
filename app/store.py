"""In-memory store for notification requests."""

from schemas import NotificationStatus


_store: dict[str, dict] = {}


def create(request_id: str, to: str, message: str, type: str) -> None:
    """Create a new request in queued status."""
    _store[request_id] = {
        "id": request_id,
        "status": NotificationStatus.QUEUED,
        "to": to,
        "message": message,
        "type": type,
    }


def get(request_id: str) -> dict | None:
    """Get a request by id, or None if not found."""
    return _store.get(request_id)


def update_status(request_id: str, status: NotificationStatus) -> None:
    """Update the status of a request."""
    if request_id in _store:
        _store[request_id]["status"] = status
