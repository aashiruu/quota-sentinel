import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.limiter import SlidingWindowRateLimiter


@pytest.fixture(autouse=True)
async def flush_redis():
    limiter = SlidingWindowRateLimiter()
    await limiter.redis_client.flushall()
    await limiter.close()


@pytest.mark.asyncio
async def test_health_check_does_not_require_tenant():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_missing_tenant_header_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/data")
        assert response.status_code == 401
        assert "Missing required" in response.json()["message"]


@pytest.mark.asyncio
async def test_tiered_rate_limits_and_structured_rejection():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Free Tier (limit 5): Send 5 requests (200 OK)
        for i in range(5):
            res = await client.get("/api/v1/data", headers={"X-Tenant-ID": "tenant-free"})
            assert res.status_code == 200
            assert res.headers["X-RateLimit-Tier"] == "free"
            assert res.headers["X-RateLimit-Limit"] == "5"

        # 6th request triggers structured 429 payload
        res_free_blocked = await client.get("/api/v1/data", headers={"X-Tenant-ID": "tenant-free"})
        assert res_free_blocked.status_code == 429
        assert res_free_blocked.headers["X-RateLimit-Tier"] == "free"

        body = res_free_blocked.json()
        assert body["error"]["code"] == "rate_limit_exceeded"
        assert body["error"]["details"]["tier"] == "free"
        assert body["error"]["details"]["limit"] == 5

        # Standard Tier (limit 20): Send 10 requests, none throttled
        for _ in range(10):
            res_std = await client.get("/api/v1/data", headers={"X-Tenant-ID": "tenant-standard"})
            assert res_std.status_code == 200
            assert res_std.headers["X-RateLimit-Tier"] == "standard"
            assert res_std.headers["X-RateLimit-Limit"] == "20"
