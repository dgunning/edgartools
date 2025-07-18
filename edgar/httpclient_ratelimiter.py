"""
The default pyrate_limiter is set to 9 requests per second. 

To change the rate limit, call update_rate_limiter(requests_per_minute)

To control rate limit across multiple processes, see https://pyratelimiter.readthedocs.io/en/latest/#backends
"""

import httpx
import logging

from pyrate_limiter import Limiter, Rate, Duration

log = logging.getLogger(__name__)

def create_rate_limiter(requests_per_second: int, max_delay: int) -> Limiter:
    return Limiter(Rate(requests_per_second, Duration.SECOND), raise_when_fail=False, max_delay=max_delay)

class RateLimitingTransport(httpx.HTTPTransport):
    def __init__(self, limiter: Limiter):
        super().__init__()
        self._limiter = limiter

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        log.debug("Limiter applied")
        self._limiter.try_acquire("edgar", 1)  # blocks until slot available
        return super().handle_request(request)


class AsyncRateLimitingTransport(httpx.AsyncHTTPTransport):
    def __init__(self, limiter: Limiter):
        super().__init__()
        self._limiter = limiter

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        log.debug("Limiter applied")
        self._limiter.try_acquire("edgar", 1)  # blocks until slot available
        return await super().handle_async_request(request)
