"""
Test script to verify that the SSL verification fix works.

This tests that configure_http(verify_ssl=False) properly propagates the
verify parameter to the HTTP transport layer, fixing the httpxthrottlecache bug.
"""

from edgar.httpclient import configure_http, get_http_config, HTTP_MGR


def test_ssl_verify_propagation():
    """Test that verify parameter is properly passed to transport."""

    print("Testing SSL verification parameter propagation...")
    print("=" * 70)

    # Test 1: Default should be True
    print("\n1. Testing default SSL verification (should be True):")
    config = get_http_config()
    print(f"   verify_ssl in config: {config['verify_ssl']}")
    assert config['verify_ssl'] is True, "Default should be SSL verification enabled"
    print("   ✓ Default is True (SSL verification enabled)")

    # Test 2: Disable SSL verification
    print("\n2. Disabling SSL verification with configure_http(verify_ssl=False):")
    configure_http(verify_ssl=False)
    config = get_http_config()
    print(f"   verify_ssl in config: {config['verify_ssl']}")
    assert config['verify_ssl'] is False, "Should be disabled after configure_http()"
    print("   ✓ Successfully disabled in config")

    # Test 3: Check that it's in httpx_params
    print("\n3. Checking HTTP_MGR.httpx_params:")
    verify_in_params = HTTP_MGR.httpx_params.get("verify")
    print(f"   verify in httpx_params: {verify_in_params}")
    assert verify_in_params is False, "Should be False in httpx_params"
    print("   ✓ httpx_params['verify'] is False")

    # Test 4: Check transport params (this tests our monkey patch)
    print("\n4. Testing transport params (the monkey patch fix):")
    test_params = {"verify": False, "http2": False}
    transport_params = HTTP_MGR._get_httpx_transport_params(test_params)
    print(f"   Transport params: {transport_params}")
    assert "verify" in transport_params, "verify should be in transport params"
    assert transport_params["verify"] is False, "verify should be False in transport params"
    print("   ✓ verify parameter is properly passed to transport!")

    # Test 5: Re-enable SSL verification
    print("\n5. Re-enabling SSL verification with configure_http(verify_ssl=True):")
    configure_http(verify_ssl=True)
    config = get_http_config()
    print(f"   verify_ssl in config: {config['verify_ssl']}")
    assert config['verify_ssl'] is True, "Should be re-enabled"

    test_params = {"verify": True, "http2": False}
    transport_params = HTTP_MGR._get_httpx_transport_params(test_params)
    assert transport_params["verify"] is True, "verify should be True in transport params"
    print("   ✓ Successfully re-enabled")

    print("\n" + "=" * 70)
    print("✓ All tests passed! The SSL verification fix is working correctly.")
    print("\nThe monkey patch successfully fixes the httpxthrottlecache bug where")
    print("the 'verify' parameter was not being passed to the HTTP transport.")


if __name__ == "__main__":
    test_ssl_verify_propagation()
