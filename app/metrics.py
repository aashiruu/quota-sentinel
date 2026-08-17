from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# 1. Total requests categorized by tenant, tier, and HTTP status code
REQUESTS_TOTAL = Counter(
    "quota_sentinel_requests_total",
    "Total HTTP requests handled by the gateway",
    ["tenant_id", "tier", "status_code"],
)

# 2. Total rate-limited / throttled requests per tenant and tier
THROTTLED_TOTAL = Counter(
    "quota_sentinel_throttled_total",
    "Total requests rejected by rate limiting per tenant",
    ["tenant_id", "tier"],
)

# 3. Static quota ceiling gauge per tenant and tier
QUOTA_LIMIT_GAUGE = Gauge(
    "quota_sentinel_quota_limit",
    "Configured rate limit ceiling per tenant (req/min)",
    ["tenant_id", "tier"],
)


def metrics_endpoint() -> Response:
    """Exposes standard Prometheus scrape format."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
