import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


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
async def test_tenant_isolation_and_rate_limiting():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Tenant Alpha consumes quota up to limit (5)
        for i in range(5):
            res = await client.get("/api/v1/data", headers={"X-Tenant-ID": "tenant-alpha"})
            assert res.status_code == 200
            assert res.headers["X-RateLimit-Remaining"] == str(5 - (i + 1))

        # Tenant Alpha 6th request triggers 429
        res_alpha_blocked = await client.get("/api/v1/data", headers={"X-Tenant-ID": "tenant-alpha"})
        assert res_alpha_blocked.status_code == 429
        assert "Retry-After" in res_alpha_blocked.headers

        # Tenant Beta remains unaffected (fairness isolation)
        res_beta = await client.get("/api/v1/data", headers={"X-Tenant-ID": "tenant-beta"})
        assert res_beta.status_code == 200
        assert res_beta.headers["X-RateLimit-Remaining"] == "4"
