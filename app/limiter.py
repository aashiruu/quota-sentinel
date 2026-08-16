import time
from typing import Tuple
import redis.asyncio as redis


class SlidingWindowRateLimiter:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)

    async def is_rate_limited(
        self, tenant_id: str, limit: int, window_seconds: int = 60
    ) -> Tuple[bool, int, int]:
        """
        Enforces a sliding-window rate limit using a Redis sorted set (ZSET).
        Returns: (is_limited, current_usage, retry_after_seconds)
        """
        now = time.time()
        window_start = now - window_seconds
        key = f"ratelimit:{tenant_id}"

        async with self.redis_client.pipeline(transaction=True) as pipe:
            # 1. Purge requests older than the sliding window threshold
            pipe.zremrangebyscore(key, 0, window_start)
            # 2. Add the current request timestamp with a unique member
            pipe.zadd(key, {f"{now}:{time.time_ns()}": now})
            # 3. Count remaining requests within current window
            pipe.zcard(key)
            # 4. Set TTL so idle keys expire automatically
            pipe.expire(key, window_seconds + 5)

            results = await pipe.execute()

        request_count = results[2]

        if request_count > limit:
            # Calculate oldest request timestamp to provide accurate retry-after
            oldest_requests = await self.redis_client.zrange(
                key, 0, 0, withscores=True
            )
            if oldest_requests:
                oldest_ts = oldest_requests[0][1]
                retry_after = max(1, int(window_seconds - (now - oldest_ts)))
            else:
                retry_after = window_seconds
            return True, request_count, retry_after

        return False, request_count, 0

    async def close(self):
        await self.redis_client.aclose()
