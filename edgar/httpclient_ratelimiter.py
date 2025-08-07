"""
To control rate limit across multiple processes, see https://pyratelimiter.readthedocs.io/en/latest/#backends
"""

import httpx
import logging
from typing import Tuple

from pyrate_limiter import Limiter, Duration, Rate, InMemoryBucket, BucketAsyncWrapper

log = logging.getLogger(__name__)


def create_rate_limiter(requests_per_second: int, max_delay: int, async_bucket: bool = False) -> Limiter:
    rate = Rate(requests_per_second, Duration.SECOND)
    rate_limits = [rate]
    
    base_bucket = InMemoryBucket(rate_limits)
    
    if async_bucket:
        bucket = BucketAsyncWrapper(base_bucket)
    else:
        bucket = base_bucket

    limiter = Limiter(
        bucket, raise_when_fail=False, retry_until_max_delay=True
    )
    
    return limiter

class RateLimitingTransport(httpx.HTTPTransport):
    def __init__(self, limiter: Limiter, **kwargs):
        super().__init__(**kwargs)
        self.limiter = limiter

    def handle_request(self, request: httpx.Request, **kwargs) -> httpx.Response:
        # using a constant string for item name means that the same
        # rate is applied to all requests.
        while not self.limiter.try_acquire("httpx_ratelimiter"):
            log.debug("Lock acquisition timed out, retrying")

        log.debug("Acquired lock")
        return super().handle_request(request, **kwargs)


class AsyncRateLimitingTransport(httpx.AsyncHTTPTransport):
    def __init__(self, limiter: Limiter, **kwargs):
        super().__init__(**kwargs)
        self.limiter = limiter

    async def handle_async_request(self, request: httpx.Request, **kwargs) -> httpx.Response:

        while not await self.limiter.try_acquire_async("httpx_ratelimiter"):
            log.debug("Lock acquisition timed out, retrying")

        log.debug("Acquired lock")
        response = await super().handle_async_request(request, **kwargs)

        return response
