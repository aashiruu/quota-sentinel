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
*Pending implementation.*

## 3. Metric Cardinality Strategy (Stage 4)
*Pending implementation.*

## 4. Rate-Limit Rejection Behavior (Stage 5)
*Pending implementation.*
