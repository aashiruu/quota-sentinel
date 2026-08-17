# Design Trade-offs & Decisions

This document records architectural decisions made at each milestone.

---

## 1. Rate Limiting Algorithm (Stage 1)

### Options Evaluated
1. **Fixed Window Counter:**
   - *Mechanism:* Increments an integer counter mapped to a fixed time slice (e.g., `ratelimit:tenant_a:16:00`).
   - *Trade-off:* Low memory overhead and fast execution, but vulnerable to **boundary bursts**. A tenant can send 100% of their limit at second :59 and another 100% at second :00, effectively sending 2x the allowed rate across a 2-second interval.
2. **Token Bucket:**
   - *Mechanism:* Refills tokens continuously at a set rate up to a max capacity; requests consume tokens.
   - *Trade-off:* Smooths traffic and permits controlled bursts, but requires multi-field state tracking per tenant (token count and timestamp).
3. **Sliding Window Log (via Redis Sorted Set):**
   - *Mechanism:* Tracks request timestamps in a Redis sorted set (`ZSET`). For every incoming request, elements older than `now - window_seconds` are evicted, the current timestamp is inserted, and cardinality is evaluated.
   - *Trade-off:* Consumes more memory per request than an integer counter, but guarantees complete protection against boundary bursts without approximation error.

### Decision
Chose the **Sliding Window Log** backed by a Redis pipeline. In an async API gateway handling multi-tenant isolation, eliminating boundary burst vulnerabilities is critical to prevent aggressive tenants from momentarily degrading shared capacity at window boundaries.

## 2. Quota Tier Storage & Lookup (Stage 2)

### Options Evaluated
1. **External Database (PostgreSQL / DynamoDB):**
   - *Mechanism:* Query tenant tier limits from a database table per request or on cache miss.
   - *Trade-off:* Supports dynamic updates without restarts and persistent auditing, but adds network latency (2-10 ms) on the API hot path if cache synchronization fails.
2. **In-Memory Configuration Registry:**
   - *Mechanism:* Static tier mapping dictionary loaded at gateway initialization.
   - *Trade-off:* Sub-microsecond O(1) in-memory lookups with zero network overhead, but requires service restarts or a reload hook to update tenant tier assignments.
3. **Redis-Backed Hash Mappings:**
   - *Mechanism:* Store tenant configurations in Redis keys (`HGETALL tenant:config:<id>`).
   - *Trade-off:* Shared across multiple gateway worker replicas, but requires additional Redis round-trips if not combined with the sliding window Lua pipeline.

### Decision
Implemented an **in-memory configuration registry** with standard tiers (`free: 5 req/min`, `standard: 20 req/min`, `premium: 60 req/min`) and fallback defaults. This guarantees zero added latency during tenant resolution while isolating tier limits per tenant ID.

## 3. Metric Cardinality Strategy (Stage 4)

### Options Evaluated
1. **Unbounded High-Cardinality Labels:**
   - *Approach:* Tag metrics with `tenant_id`, `path`, `method`, `user_ip`, `status_code`.
   - *Trade-off:* High debuggability, but severe cardinality explosion risk. If a platform has 10,000 tenants across 50 endpoints and 5 status codes, a single metric creates $10,000 \times 50 \times 5 = 2,500,000$ active time series in Prometheus TSDB, crashing memory.
2. **Global Aggregated Metrics:**
   - *Approach:* Scrape total request counts and status codes without tenant tags.
   - *Trade-off:* Near-zero storage footprint, but completely obscures tenant-level fairness and prevents identifying which tenant is exhausting capacity.
3. **Bounded Cardinality with Controlled Labels:**
   - *Approach:* Tag metrics strictly with `tenant_id`, `tier`, and standard `status_code`. Normalize unauthenticated requests to `anonymous` and omit ephemeral attributes like IPs and request parameters.
   - *Trade-off:* Bounded metric footprint ($O(\text{tenants} \times \text{tiers})$) with full visibility into per-tenant throughput and throttle rates.

### Decision
Adopted **Bounded Cardinality with Controlled Labels** (`tenant_id`, `tier`, `status_code`). High-cardinality metadata (such as individual client IP addresses and trace tokens) is relegated to structured logging and distributed tracing rather than Prometheus counters.

## 4. Rate-Limit Rejection Behavior (Stage 5)
*Pending implementation.*
