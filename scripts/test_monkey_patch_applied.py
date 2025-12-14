"""
Test if the monkey patch is actually applied.
"""

# Ensure clean import
import sys

for mod in list(sys.modules.keys()):
    if 'edgar' in mod or 'httpxthrottle' in mod:
        del sys.modules[mod]

print("Clean import - all edgar and httpxthrottlecache modules removed from cache")

# Now import
print("\nImporting edgar.httpclient...")
from edgar import httpclient

print("\nChecking HttpxThrottleCache class:")
print(f"Class: {httpclient.HttpxThrottleCache}")
print(f"Method: {httpclient.HttpxThrottleCache._get_httpx_transport_params}")
print(f"Method name: {httpclient.HttpxThrottleCache._get_httpx_transport_params.__name__}")

# Check if it's the patched version
if httpclient.HttpxThrottleCache._get_httpx_transport_params.__name__ == "_patched_get_httpx_transport_params":
    print("✓ Monkey patch IS applied to the class!")
else:
    print("✗ Monkey patch is NOT applied to the class!")

# Now test on an instance
print("\nCreating instance...")
mgr = httpclient.HttpxThrottleCache(cache_dir="/tmp/test", cache_mode="Disabled")

print(f"Instance method: {mgr._get_httpx_transport_params}")
print(f"Instance method __func__: {mgr._get_httpx_transport_params.__func__}")
print(f"Instance method __func__.__name__: {mgr._get_httpx_transport_params.__func__.__name__}")

if mgr._get_httpx_transport_params.__func__.__name__ == "_patched_get_httpx_transport_params":
    print("✓ Monkey patch IS applied to the instance!")
else:
    print("✗ Monkey patch is NOT applied to the instance!")

# Now let's test calling it
print("\nCalling method...")
print("=" * 70)
result = mgr._get_httpx_transport_params({"verify": False, "http2": True})
print("=" * 70)
print(f"Result: {result}")
