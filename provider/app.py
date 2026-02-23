from fastapi import FastAPI, Response, status, Depends, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
import asyncio
import random
import time
from typing import List, Literal

app = FastAPI(
    title="Backend Challenge - Notification Provider",
    description="Simulates an external environment with latency and random failures (500/429).",
    version="1.1.0"
)

API_KEY = "test-dev-2026"
api_key_header = APIKeyHeader(name="X-API-Key")

async def validate_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    return api_key

class Notification(BaseModel):
    to: str = Field(..., example="user@example.com")
    message: str = Field(..., example="Your verification code is 1234")
    type: Literal["email", "sms", "push"] = Field(..., example="email")

class NotificationResponse(BaseModel):
    status: str = Field(..., example="delivered")
    provider_id: str = Field(..., example="p-1234")

class ErrorResponse(BaseModel):
    error: str = Field(..., example="Rate limit exceeded")


FAIL_RATE = 0.1
LATENCY_MIN = 0.1
LATENCY_MAX = 0.5
RATE_LIMIT_THRESHOLD = 50
MAX_CONCURRENT_REQUESTS = 50

semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
request_counts: List[float] = []

@app.post(
    "/v1/notify",
    tags=["Notifications"],
    summary="Send notification",
    description="""
Sends a notification to the provider. 
- Requires 'X-API-Key' header. 
- This endpoint can return 429 (rate limit) or 500 (random error) to test client resilience.
""",
    response_model=NotificationResponse,
    responses={
        200: {"model": NotificationResponse},
        401: {
            "model": ErrorResponse, 
            "description": "Unauthorized - Missing or invalid API Key",
            "content": {"application/json": {"example": {"error": "Invalid API Key"}}}
        },
        429: {
            "model": ErrorResponse, 
            "description": "Rate limit exceeded",
            "content": {"application/json": {"example": {"error": "Rate limit exceeded"}}}
        },
        500: {
            "model": ErrorResponse, 
            "description": "Random server error",
            "content": {"application/json": {"example": {"error": "External server error"}}}
        }
    }
)
async def notify(
    notification: Notification, 
    response: Response,
    priority: Literal["low", "normal", "high"] = "normal",
    trace_id: str | None = None,
    api_key: str = Depends(validate_api_key)
):
    global request_counts
    
    async with semaphore:
        now = time.time()
        request_counts = [t for t in request_counts if now - t < 10]
        if len(request_counts) >= RATE_LIMIT_THRESHOLD:
            print(f"DEBUG: [Provider] 429 Rate Limit Exceeded (current load: {len(request_counts)})")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded"
            )
        request_counts.append(now)
        await asyncio.sleep(random.uniform(LATENCY_MIN, LATENCY_MAX))
        if random.random() < FAIL_RATE:
            print("DEBUG: [Provider] 500 Random Failure triggered")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="External server error"
            )
        print(f"DEBUG: [Provider] 200 Success to {notification.to} via {notification.type}")
        return {
            "status": "delivered", 
            "provider_id": f"p-{random.randint(1000, 9999)}"
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)
