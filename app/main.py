import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from app.limiter import SlidingWindowRateLimiter
from app.config import get_tenant_tier

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

limiter: SlidingWindowRateLimiter = None


def get_limiter() -> SlidingWindowRateLimiter:
    global limiter
    if limiter is None:
        limiter = SlidingWindowRateLimiter(redis_url=REDIS_URL)
    return limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_limiter()
    yield
    global limiter
    if limiter:
        await limiter.close()
        limiter = None


app = FastAPI(
    title="Quota Sentinel",
    description="Learning project exploring multi-tenant rate limiting and fair resource allocation.",
    version="0.2.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path in ["/health", "/docs", "/openapi.json"]:
        return await call_next(request)

    # 1. Identify Tenant
    tenant_id = request.headers.get("X-Tenant-ID") or request.headers.get("X-API-Key")
    if not tenant_id:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "Unauthorized",
                "message": "Missing required 'X-Tenant-ID' or 'X-API-Key' header.",
            },
        )

    # 2. Resolve Tenant Quota Tier
    tier = get_tenant_tier(tenant_id)

    # 3. Check Sliding Window Limit against Tier Limit
    active_limiter = get_limiter()
    is_limited, current_usage, retry_after = await active_limiter.is_rate_limited(
        tenant_id=tenant_id,
        limit=tier.rate_limit,
        window_seconds=60,
    )

    if is_limited:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={
                "X-RateLimit-Tier": tier.name,
                "X-RateLimit-Limit": str(tier.rate_limit),
                "X-RateLimit-Remaining": "0",
                "Retry-After": str(retry_after),
            },
            content={
                "error": "Too Many Requests",
                "message": f"Tenant '{tenant_id}' on tier '{tier.name}' exceeded quota limit of {tier.rate_limit} requests per minute.",
                "tier": tier.name,
                "limit": tier.rate_limit,
                "retry_after_seconds": retry_after,
            },
        )

    response: Response = await call_next(request)
    response.headers["X-Tenant-ID"] = tenant_id
    response.headers["X-RateLimit-Tier"] = tier.name
    response.headers["X-RateLimit-Limit"] = str(tier.rate_limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, tier.rate_limit - current_usage))
    return response


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "quota-sentinel"}


@app.get("/api/v1/data")
def get_sample_data():
    return {
        "message": "Resource payload successfully retrieved.",
        "status": "success",
    }
