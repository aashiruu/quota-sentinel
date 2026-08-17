import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse
from app.limiter import SlidingWindowRateLimiter
from app.config import get_tenant_tier, TENANT_TIER_MAP, TIER_DEFINITIONS
from app.metrics import (
    REQUESTS_TOTAL,
    THROTTLED_TOTAL,
    QUOTA_LIMIT_GAUGE,
    metrics_endpoint,
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

limiter: SlidingWindowRateLimiter = None


def get_limiter() -> SlidingWindowRateLimiter:
    global limiter
    if limiter is None:
        limiter = SlidingWindowRateLimiter(redis_url=REDIS_URL)
    return limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize static quota gauge metrics
    for tenant_id, tier_name in TENANT_TIER_MAP.items():
        tier_cfg = TIER_DEFINITIONS[tier_name]
        QUOTA_LIMIT_GAUGE.labels(tenant_id=tenant_id, tier=tier_name).set(
            tier_cfg.rate_limit
        )

    get_limiter()
    yield
    global limiter
    if limiter:
        await limiter.close()
        limiter = None


app = FastAPI(
    title="Quota Sentinel",
    description="Learning project exploring multi-tenant rate limiting and fair resource allocation.",
    version="0.3.0",
    lifespan=lifespan,
)


@app.get("/metrics")
def get_metrics():
    return metrics_endpoint()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Bypass health checks, metrics scraper, and openapi routes
    if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json"]:
        return await call_next(request)

    # 1. Identify Tenant
    tenant_id = request.headers.get("X-Tenant-ID") or request.headers.get("X-API-Key")
    if not tenant_id:
        REQUESTS_TOTAL.labels(
            tenant_id="anonymous", tier="none", status_code="401"
        ).inc()
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "Unauthorized",
                "message": "Missing required 'X-Tenant-ID' or 'X-API-Key' header.",
            },
        )

    # 2. Resolve Tenant Tier Quota
    tier = get_tenant_tier(tenant_id)
    QUOTA_LIMIT_GAUGE.labels(tenant_id=tenant_id, tier=tier.name).set(tier.rate_limit)

    # 3. Check Sliding Window Limit against Tier Limit
    active_limiter = get_limiter()
    is_limited, current_usage, retry_after = await active_limiter.is_rate_limited(
        tenant_id=tenant_id,
        limit=tier.rate_limit,
        window_seconds=60,
    )

    if is_limited:
        REQUESTS_TOTAL.labels(
            tenant_id=tenant_id, tier=tier.name, status_code="429"
        ).inc()
        THROTTLED_TOTAL.labels(tenant_id=tenant_id, tier=tier.name).inc()

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
    REQUESTS_TOTAL.labels(
        tenant_id=tenant_id, tier=tier.name, status_code=str(response.status_code)
    ).inc()

    response.headers["X-Tenant-ID"] = tenant_id
    response.headers["X-RateLimit-Tier"] = tier.name
    response.headers["X-RateLimit-Limit"] = str(tier.rate_limit)
    response.headers["X-RateLimit-Remaining"] = str(
        max(0, tier.rate_limit - current_usage)
    )
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
