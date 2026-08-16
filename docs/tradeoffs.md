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
*Pending implementation.*

## 4. Rate-Limit Rejection Behavior (Stage 5)
*Pending implementation.*
