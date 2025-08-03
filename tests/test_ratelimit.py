from edgar.httpclient import async_http_client, http_client

import pytest
import time
import asyncio

def test_cache_speedup(request):
    """When cache is enabled, then the total requests should be less than 1 second. Else 20ish seconds"""
    cache_enabled = request.config.getoption("--enable-cache")

    cacheable_url = 'https://www.sec.gov/Archives/edgar/data/730200/000073020016000084/0000730200-16-000084.txt'

    count = 30

    with http_client() as client:
        if cache_enabled:
            # Prime the cache
            response = client.get(cacheable_url)
        start = time.perf_counter()

        for _ in range(count):
            response = client.get(cacheable_url)
            assert response.status_code == 200

    end = time.perf_counter()

    duration = end - start
    if cache_enabled:
        assert duration < 1, f"With cache enabled, {duration=} is longer than a second"
    else:
        assert duration > 3.0 and duration < 5.0, f"{duration=} not between 3 and 5 seconds"

def test_dont_exceed_limit():
    """Verify that 30 requests take more than 3 seconds (given a rate limit of 9-10 requests per second), and
    all return status_code 200"""
    url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
    count = 30

    with http_client() as client:
        for _ in range(10): # warm the bucket
            response = client.get(url)
            assert response.status_code == 200

        start = time.perf_counter()
        for _ in range(count):
            response = client.get(url)
            assert response.status_code == 200

    end = time.perf_counter()

    duration = end - start
    assert duration > 3.0, f"{duration=} too fast"

@pytest.mark.asyncio
async def test_dont_exceed_limit_async():
    """Verify that 30 requests take more than 3 seconds (given a rate limit of 9-10 requests per second), and
    all return status_code 200"""
    url = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent"
    count = 30

    start = time.perf_counter()

    async def run_batch(cnt):
        tasks = [client.get(url) for _ in range(count)]
        results = await asyncio.gather(*tasks)
        for r in results:
            assert r.status_code == 200

    async with async_http_client() as client:
        await run_batch(10) # warm the bucket
        start = time.perf_counter()
        await run_batch(count) 

    end = time.perf_counter()

    duration = end - start
    assert duration > 3.0, f"{duration=} was faster than available rate limit"