# Noisy-Neighbor Fairness Testing

This document contains scenario design, fairness definitions, and execution results for the multi-tenant noisy-neighbor experiment.

---

## Scenario Design
The load test evaluates whether an aggressive tenant attempting to flood the platform beyond its quota can degrade or starve compliant tenants sharing the same gateway and Redis instance.

### Traffic Profile Matrix
| Tenant Persona | Assigned Tier | Quota Limit | Injected Traffic Pattern | Expected Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **`tenant-noisy`** | Free | 5 req/min | 5 concurrent VUs hammering the gateway with zero delay (2,250+ requests in 30s) | First 5 requests succeed (200 OK); remaining 2,250+ requests rejected with 429. |
| **`tenant-standard`** | Standard | 20 req/min | Constant arrival rate of 15 req/min (~1 request every 4s) | 100% success rate (200 OK), 0 throttled requests. |
| **`tenant-free`** | Free | 5 req/min | Constant arrival rate of 4 req/min (~1 request every 15s) | 100% success rate (200 OK), 0 throttled requests. |

---

## Measurable Definition of Fairness
Fairness is validated if and only if all of the following measurable criteria are met:
1. **Compliant Tenant Zero-Degradation:** `tenant-standard` and `tenant-free` achieve a $100\%$ success rate (`count == 0` for `throttled_count`) with zero `5xx` errors.
2. **Deterministic Noisy Throttling:** `tenant-noisy` receives exactly 5 successful `200 OK` responses during the 60-second sliding window, and 100% of all excess requests return `429 Too Many Requests`.
3. **No Cross-Tenant Counter Poisoning:** Flooding by `tenant-noisy` does not consume or alter the sliding window sorted set counters of adjacent tenants in Redis.

---

## Test Results

### 1. k6 Multi-Tenant Concurrency Output (30-second run)
```text
          /\      Grafana   /‾‾/
     /\  /  \     |\  __   /  /
    /  \/    \    | |/ /  /   ‾‾\
   /          \   |   (  |  (‾)  |
  / __________ \  |_|\_\  \_____/

     execution: local
        script: load-test.js
        output: -

     scenarios: (100.00%) 3 scenarios, 8 max VUs, 1m0s max duration:
              * noisy_neighbor: 5 looping VUs for 30s (exec: noisyTenant, gracefulStop: 30s)
              * well_behaved_free: 0.07 iterations/s for 30s (maxVUs: 1, exec: steadyFreeTenant, gracefulStop: 30s)
              * well_behaved_standard: 0.25 iterations/s for 30s (maxVUs: 2, exec: steadyStandardTenant, gracefulStop: 30s)

  █ THRESHOLDS
    steady_free_throttled_count
    ✓ 'count==0' count=0

    steady_std_throttled_count
    ✓ 'count==0' count=0

  █ TOTAL RESULTS
    checks_total.......: 2268   75.697049/s
    checks_succeeded...: 100.00% 2268 out of 2268
    checks_failed......: 0.00%   0 out of 2268

    ✓ noisy: status is 200 or 429
    ✓ steady_free: status is 200 OK
    ✓ steady_standard: status is 200 OK

    CUSTOM
    noisy_success_count............: 5      0.166881/s
    noisy_throttled_count..........: 2252   75.163031/s
    steady_free_success_count......: 3      0.100128/s
    steady_free_throttled_count....: 0      0/s
    steady_std_success_count.......: 8      0.267009/s
    steady_std_throttled_count.....: 0      0/s

    HTTP
    http_reqs......................: 2268   75.697049/s
    http_req_failed................: 99.29% 2252 out of 2268 (all from tenant-noisy)
```

### 2. Python Async Driver Verification Output
```text
Starting Noisy-Neighbor Simulation (15s concurrent execution)...

=== Simulation Results ===
Tenant: tenant-noisy | 200 OK: 3 | 429 Throttled: 266
Tenant: tenant-noisy | 200 OK: 2 | 429 Throttled: 267
Tenant: tenant-standard | 200 OK: 4 | 429 Throttled: 0
Tenant: tenant-free | 200 OK: 3 | 429 Throttled: 0
```
## Analysis of Results
- **Strict Isolation**: Despite `tenant-noisy` sending 2,257 total requests over 30 seconds, only 5 requests were admitted into the upstream application.
- **Zero Impact on Neighbors**: `tenant-standard` (8 requests) and `tenant-free` (3 requests) achieved 100% availability with 0 throttled requests.
- **Fair Allocation**: Each tenant operated entirely within their isolated quota boundary, proving that shared platform infrastructure can remain resilient against bad actors under heavy saturation.
## Visual Evidence
### Prometheus Raw Metrics Scrape Output (Post Noisy-Neighbor Test)
```text
# HELP quota_sentinel_requests_total Total HTTP requests handled by the gateway
# TYPE quota_sentinel_requests_total counter
quota_sentinel_requests_total{status_code="200",tenant_id="tenant-noisy",tier="free"} 5.0
quota_sentinel_requests_total{status_code="200",tenant_id="tenant-standard",tier="standard"} 8.0
quota_sentinel_requests_total{status_code="200",tenant_id="tenant-free",tier="free"} 3.0
quota_sentinel_requests_total{status_code="429",tenant_id="tenant-noisy",tier="free"} 1915.0

# HELP quota_sentinel_throttled_total Total requests rejected by rate limiting per tenant
# TYPE quota_sentinel_throttled_total counter
quota_sentinel_throttled_total{tenant_id="tenant-noisy",tier="free"} 1915.0

# HELP quota_sentinel_quota_limit Configured rate limit ceiling per tenant (req/min)
# TYPE quota_sentinel_quota_limit gauge
quota_sentinel_quota_limit{tenant_id="tenant-free",tier="free"} 5.0
quota_sentinel_quota_limit{tenant_id="tenant-standard",tier="standard"} 20.0
quota_sentinel_quota_limit{tenant_id="tenant-noisy",tier="free"} 5.0# HELP quota_sentinel_requests_total Total HTTP requests handled by the gateway
# TYPE quota_sentinel_requests_total counter
quota_sentinel_requests_total{status_code="200",tenant_id="tenant-noisy",tier="free"} 5.0
quota_sentinel_requests_total{status_code="200",tenant_id="tenant-standard",tier="standard"} 8.0
quota_sentinel_requests_total{status_code="200",tenant_id="tenant-free",tier="free"} 3.0
quota_sentinel_requests_total{status_code="429",tenant_id="tenant-noisy",tier="free"} 1915.0

# HELP quota_sentinel_throttled_total Total requests rejected by rate limiting per tenant
# TYPE quota_sentinel_throttled_total counter
quota_sentinel_throttled_total{tenant_id="tenant-noisy",tier="free"} 1915.0

# HELP quota_sentinel_quota_limit Configured rate limit ceiling per tenant (req/min)
# TYPE quota_sentinel_quota_limit gauge
quota_sentinel_quota_limit{tenant_id="tenant-free",tier="free"} 5.0
quota_sentinel_quota_limit{tenant_id="tenant-standard",tier="standard"} 20.0
quota_sentinel_quota_limit{tenant_id="tenant-noisy",tier="free"} 5.0
```

## Visual Evidence

### 1. Multi-Tenant Fairness Dashboard Overview
![Grafana dashboard showing tenant-noisy throttled at 80+ req/s while tenant-standard and tenant-free maintain 100% 200 OK availability](assets/grafana-fairness-dashboard.png)

*Real-time Grafana telemetry during the noisy-neighbor test: `tenant-noisy` is throttled at 80+ req/s (bottom-left and top-left) while concurrent compliant tenants maintain uninterrupted 200 OK availability (top-right).*

---

### 2. Deep-Dive Telemetry Breakdown

#### A. Compliant Tenant Isolation & Success Stream (Zoomed)
![Compliant Tenants 200 OK Stream](assets/grafana-compliant-stream.png)

- **`tenant-standard (200 OK)`**: Maintained a steady rate of ~0.25 req/s (15 req/min) with zero dropped requests.
- **`tenant-free (200 OK)`**: Maintained its scheduled ~0.1 req/s rate with zero dropped requests.
- **`tenant-free (429 Drops)`**: Remained flat at exactly 0 req/s along the baseline throughout the entire saturation window.

#### B. Rejections: 429 Throttled Rate
![Rejections 429 Throttled Rate](assets/grafana-rejections-panel.png)

- Only `tenant-noisy` appears in the throttled time series, absorbing between 60 to 80+ req/s of rate-limit drops immediately after its initial 5-request burst.
- Compliant tenants recorded zero throttle events.

> **Scope Note:** While the gateway maintains static configuration ceilings for 6 reference tenants (`tenant-alpha`, `tenant-beta`, `tenant-free`, `tenant-noisy`, `tenant-premium`, `tenant-standard`), the fairness load test specifically exercises a 3-tenant concurrent matrix (`tenant-noisy`, `tenant-standard`, `tenant-free`) to isolate tier behaviors under saturation.

---

### Prometheus Raw Metrics Scrape Output (Post Load Test)
```text
# HELP quota_sentinel_requests_total Total HTTP requests handled by the gateway
# TYPE quota_sentinel_requests_total counter
quota_sentinel_requests_total{status_code="200",tenant_id="tenant-noisy",tier="free"} 5.0
quota_sentinel_requests_total{status_code="200",tenant_id="tenant-standard",tier="standard"} 8.0
quota_sentinel_requests_total{status_code="200",tenant_id="tenant-free",tier="free"} 3.0
quota_sentinel_requests_total{status_code="429",tenant_id="tenant-noisy",tier="free"} 1915.0

# HELP quota_sentinel_throttled_total Total requests rejected by rate limiting per tenant
# TYPE quota_sentinel_throttled_total counter
quota_sentinel_throttled_total{tenant_id="tenant-noisy",tier="free"} 1915.0

# HELP quota_sentinel_quota_limit Configured rate limit ceiling per tenant (req/min)
# TYPE quota_sentinel_quota_limit gauge
quota_sentinel_quota_limit{tenant_id="tenant-free",tier="free"} 5.0
quota_sentinel_quota_limit{tenant_id="tenant-alpha",tier="free"} 5.0
quota_sentinel_quota_limit{tenant_id="tenant-standard",tier="standard"} 20.0
quota_sentinel_quota_limit{tenant_id="tenant-beta",tier="standard"} 20.0
quota_sentinel_quota_limit{tenant_id="tenant-premium",tier="premium"} 60.0
quota_sentinel_quota_limit{tenant_id="tenant-noisy",tier="free"} 5.0
```
