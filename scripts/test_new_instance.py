"""
Test if a new instance of HttpxThrottleCache uses the patched method.
"""

from edgar.httpclient import HttpxThrottleCache

print("Creating a new HttpxThrottleCache instance...")
mgr = HttpxThrottleCache(cache_dir="/tmp/test", cache_mode="Disabled", httpx_params={"verify": False})

print("\nCalling _get_httpx_transport_params with verify=False:")
test_params = {"verify": False, "http2": True}
result = mgr._get_httpx_transport_params(test_params)

print(f"Input params: {test_params}")
print(f"Output result: {result}")
print(f"Has 'verify' key: {'verify' in result}")

if 'verify' in result and result['verify'] is False:
    print("\n✓ SUCCESS! The monkey patch is working!")
else:
    print("\n✗ FAIL! The monkey patch is NOT working!")
