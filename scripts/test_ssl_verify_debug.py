"""
Debug script to check if monkey patch is applied correctly.
"""

import sys

# Force reload to ensure monkey patch is fresh
if 'edgar.httpclient' in sys.modules:
    del sys.modules['edgar.httpclient']

from edgar.httpclient import HTTP_MGR, HttpxThrottleCache

# Check if the method is patched
print("Checking if HttpxThrottleCache._get_httpx_transport_params is patched...")
print(f"Method: {HttpxThrottleCache._get_httpx_transport_params}")
print(f"Method name: {HttpxThrottleCache._get_httpx_transport_params.__name__}")
print(f"Method doc: {HttpxThrottleCache._get_httpx_transport_params.__doc__}")

# Test calling it directly
print("\nTesting direct call to _get_httpx_transport_params:")
test_params = {"verify": False, "http2": True}
result = HTTP_MGR._get_httpx_transport_params(test_params)
print(f"Input params: {test_params}")
print(f"Output result: {result}")
print(f"Has 'verify' key: {'verify' in result}")
