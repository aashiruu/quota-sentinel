# General Verification & Evidence

This document contains raw execution evidence, curl outputs, and test logs verifying functional behavior outside the noisy-neighbor load test.

---

## Stage 0: Scaffold Verification

### Verification Goal
Verify that the baseline FastAPI application initializes cleanly and responds to HTTP requests on both the health probe and upstream data route.

### Terminal Output: Service Startup
```text
(.venv) famous@famous:~/quota-sentinel$ uvicorn app.main:app --host 0.0.0.0 --port 8000
INFO:     Started server process [535]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on [http://0.0.0.0:8000](http://0.0.0.0:8000) (Press CTRL+C to quit)
INFO:     127.0.0.1:41534 - "GET /health HTTP/1.1" 200 OK
INFO:     127.0.0.1:47424 - "GET /api/v1/data HTTP/1.1" 200 OK
```
### Route 1: Health Check (GET /health)
```HTTP
HTTP/1.1 200 OK
date: Sat, 15 Aug 2026 15:07:40 GMT
server: uvicorn
content-length: 47
content-type: application/json

{"status":"healthy","service":"quota-sentinel"}
```
### Route 2: Upstream Data Payload (GET /api/v1/data)
```HTTP
HTTP/1.1 200 OK
date: Sat, 15 Aug 2026 15:07:50 GMT
server: uvicorn
content-length: 73
content-type: application/json

{"message":"Resource payload successfully retrieved.","status":"success"}
```

## Stage 1: Per-Tenant Rate Limiting

### Verification Goal
Demonstrate that:
1. Missing tenant identification headers are rejected with `401 Unauthorized`.
2. A single tenant (`tenant-alpha`) is rate-limited at 5 requests/minute with `429 Too Many Requests` and a `Retry-After` header.
3. An adjacent tenant (`tenant-beta`) remains unaffected (200 OK) during `tenant-alpha`'s throttling period.

### Automated Test Suite Execution
```text
(.venv) famous@famous:~/quota-sentinel$ pytest -v
================================================= test session starts ==================================================
platform linux -- Python 3.10.12, pytest-9.1.1, pluggy-1.6.0 -- /home/famous/quota-sentinel/.venv/bin/python3
cachedir: .pytest_cache
rootdir: /home/famous/quota-sentinel
configfile: pytest.ini
plugins: asyncio-1.4.0, anyio-4.14.2
asyncio: mode=auto, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 3 items

tests/test_rate_limiter.py::test_health_check_does_not_require_tenant PASSED                                     [ 33%]
tests/test_rate_limiter.py::test_missing_tenant_header_rejected PASSED                                           [ 66%]
tests/test_rate_limiter.py::test_tenant_isolation_and_rate_limiting PASSED                                       [100%]

================================================== 3 passed in 1.21s ===================================================
```

### Manual Curl Verification Outputs
1. Missing Authentication Header (401 Unauthorized)
```HTTP
HTTP/1.1 401 Unauthorized
date: Sun, 16 Aug 2026 13:22:12 GMT
server: uvicorn
content-length: 90
content-type: application/json

{"error":"Unauthorized","message":"Missing required 'X-Tenant-ID' or 'X-API-Key' header."}
```
2. Throttled Tenant (`tenant-alpha` Request 6 -> 429)
```HTTP
HTTP/1.1 429 Too Many Requests
date: Sun, 16 Aug 2026 13:22:28 GMT
server: uvicorn
x-ratelimit-limit: 5
x-ratelimit-remaining: 0
retry-after: 59
content-length: 135
content-type: application/json

{"error":"Too Many Requests","message":"Tenant 'tenant-alpha' exceeded quota limit of 5 requests per minute.","retry_after_seconds":59}
```
3. Isolated Tenant (`tenant-beta` Request -> 200 OK)
```HTTP
HTTP/1.1 200 OK
date: Sun, 16 Aug 2026 13:22:47 GMT
server: uvicorn
content-length: 73
content-type: application/json
x-ratelimit-limit: 5
x-ratelimit-remaining: 4
x-tenant-id: tenant-beta

{"message":"Resource payload successfully retrieved.","status":"success"}
```
