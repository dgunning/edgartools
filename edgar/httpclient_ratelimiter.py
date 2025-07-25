"""
The default pyrate_limiter is set to 9 requests per second. 

To change the rate limit, call update_rate_limiter(requests_per_minute)

To control rate limit across multiple processes, see https://pyratelimiter.readthedocs.io/en/latest/#backends
"""

import httpx
import logging

from pyrate_limiter import Limiter, Duration, Rate, InMemoryBucket

log = logging.getLogger(__name__)

def create_rate_limiter(requests_per_second: int, max_delay: int) -> Limiter:
    rate = Rate(requests_per_second, Duration.SECOND)
    rate_limits = [rate]
    bucket = InMemoryBucket(rate_limits)
    
    limiter = Limiter(
        bucket, raise_when_fail=False, max_delay=max_delay, retry_until_max_delay=True
    )

    return limiter

class RateLimitingTransport(httpx.HTTPTransport):
    def __init__(self, limiter: Limiter):
        super().__init__()
        self._limiter = limiter

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        log.debug("Limiter applied")
        if not self._limiter.try_acquire("edgar", 1):  
            # this should never occur because we're using
            # retry_until_max_delay, so only result should be True or Exception            
            raise RuntimeError("Rate acquisition failed")

        return super().handle_request(request)


class AsyncRateLimitingTransport(httpx.AsyncHTTPTransport):
    def __init__(self, limiter: Limiter):
        super().__init__()
        self._limiter = limiter

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        log.debug("Limiter applied")
        if not await self._limiter.try_acquire_async("edgar", 1):  # blocks until slot available
            # this should never occur because we're using
            # retry_until_max_delay, so only result should be True or Exception
            raise RuntimeError("Rate acquisition failed")

        return await super().handle_async_request(request)
