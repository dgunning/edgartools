"""
Detailed test of SSL verify parameter passing.
"""


print("Starting test...")

# Import the module fresh
from edgar.httpclient import HttpxThrottleCache

print("\n1. Creating HttpxThrottleCache instance with verify=False in httpx_params:")
mgr = HttpxThrottleCache(
    cache_dir="/tmp/test",
    cache_mode="Disabled",
    httpx_params={"verify": False, "http2": False}
)

print(f"   httpx_params: {mgr.httpx_params}")

print("\n2. Calling _get_httpx_transport_params:")
test_params = {"verify": False, "http2": False}
print(f"   Input: {test_params}")

try:
    result = mgr._get_httpx_transport_params(test_params)
    print(f"   Output: {result}")
    print(f"   Has 'verify': {'verify' in result}")

    if 'verify' in result:
        print(f"   verify value: {result['verify']}")
        if result['verify'] is False:
            print("\n✓ SUCCESS! verify=False is in the transport params!")
        else:
            print(f"\n✗ FAIL! verify is {result['verify']}, expected False")
    else:
        print("\n✗ FAIL! 'verify' key not in transport params")
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
