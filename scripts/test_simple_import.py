"""
Simple test - just import and test.
"""

print("Importing edgar.httpclient...")
from edgar.httpclient import HttpxThrottleCache

print("\nTesting _get_httpx_transport_params:")
mgr = HttpxThrottleCache(cache_dir="/tmp/test", cache_mode="Disabled")

params = {"verify": False, "http2": True}
result = mgr._get_httpx_transport_params(params)

print(f"\nInput:  {params}")
print(f"Output: {result}")
print(f"\nHas 'verify': {'verify' in result}")
if 'verify' in result:
    print(f"verify value: {result['verify']}")
    if result['verify'] is False:
        print("\n✓ SUCCESS!")
