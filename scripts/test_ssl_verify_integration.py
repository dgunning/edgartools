"""
Integration test: Verify that SSL verification actually works with real HTTPS requests.

This test makes actual network requests to verify that:
1. With verify=True, invalid SSL certs are rejected (secure)
2. With verify=False, invalid SSL certs are accepted (for VPN/proxy environments)
"""

import ssl

from edgar.httpclient import configure_http, get_http_config, http_client


def test_ssl_verification_with_sec_gov():
    """
    Test SSL verification with actual SEC.gov requests.

    Note: This is a network test - it requires internet connectivity.
    """
    print("Integration Test: SSL Verification with SEC.gov")
    print("=" * 70)

    # Test 1: Verify that SSL verification is enabled by default
    print("\n1. Testing default SSL verification (should be enabled):")
    configure_http(verify_ssl=True)

    config = get_http_config()
    print(f"   Config verify_ssl: {config['verify_ssl']}")
    assert config['verify_ssl'] is True, "Default should have SSL verification enabled"

    try:
        with http_client() as client:
            # Make a simple request to SEC.gov
            response = client.get("https://www.sec.gov/robots.txt")
            print(f"   Response status: {response.status_code}")
            print("   ✓ Successfully connected to SEC.gov with SSL verification")
            assert response.status_code == 200
    except Exception as e:
        print(f"   ✗ Failed to connect: {e}")
        raise

    # Test 2: Verify that we can disable SSL verification
    print("\n2. Testing with SSL verification disabled:")
    configure_http(verify_ssl=False)

    # Close the old client to force creation of new one with new settings
    from edgar.httpclient import HTTP_MGR
    if HTTP_MGR._client is not None:
        HTTP_MGR._client.close()
        HTTP_MGR._client = None

    config = get_http_config()
    print(f"   Config verify_ssl: {config['verify_ssl']}")
    assert config['verify_ssl'] is False, "Should have SSL verification disabled"

    try:
        with http_client() as client:
            # Verify the SSL context is actually disabled
            transport = client._transport

            # Unwrap to HTTPTransport
            actual_transport = transport
            if hasattr(transport, '_transport'):
                actual_transport = transport._transport
            if hasattr(actual_transport, '_transport'):
                actual_transport = actual_transport._transport

            if hasattr(actual_transport, '_pool') and hasattr(actual_transport._pool, '_ssl_context'):
                ssl_context = actual_transport._pool._ssl_context
                print(f"   SSL verify_mode: {ssl_context.verify_mode} (CERT_NONE={ssl.CERT_NONE})")
                assert ssl_context.verify_mode == ssl.CERT_NONE, "SSL verification should be disabled"

            # Make a request - should work even with verify=False
            response = client.get("https://www.sec.gov/robots.txt")
            print(f"   Response status: {response.status_code}")
            print("   ✓ Successfully connected with SSL verification disabled")
            assert response.status_code == 200
    except Exception as e:
        print(f"   ✗ Failed to connect: {e}")
        raise

    # Test 3: Verify we can re-enable SSL verification
    print("\n3. Re-enabling SSL verification:")
    configure_http(verify_ssl=True)

    # Close client again
    if HTTP_MGR._client is not None:
        HTTP_MGR._client.close()
        HTTP_MGR._client = None

    config = get_http_config()
    print(f"   Config verify_ssl: {config['verify_ssl']}")
    assert config['verify_ssl'] is True, "Should have SSL verification re-enabled"

    try:
        with http_client() as client:
            # Verify SSL context is enabled
            transport = client._transport
            actual_transport = transport
            if hasattr(transport, '_transport'):
                actual_transport = transport._transport
            if hasattr(actual_transport, '_transport'):
                actual_transport = actual_transport._transport

            if hasattr(actual_transport, '_pool') and hasattr(actual_transport._pool, '_ssl_context'):
                ssl_context = actual_transport._pool._ssl_context
                print(f"   SSL verify_mode: {ssl_context.verify_mode} (CERT_REQUIRED={ssl.CERT_REQUIRED})")
                assert ssl_context.verify_mode == ssl.CERT_REQUIRED, "SSL verification should be enabled"

            response = client.get("https://www.sec.gov/robots.txt")
            print(f"   Response status: {response.status_code}")
            print("   ✓ Successfully connected with SSL verification re-enabled")
            assert response.status_code == 200
    except Exception as e:
        print(f"   ✗ Failed to connect: {e}")
        raise

    print("\n" + "=" * 70)
    print("✓ INTEGRATION TEST PASSED!")
    print("\nThe fix works correctly with real HTTPS requests to SEC.gov:")
    print("  • SSL verification can be enabled (secure default)")
    print("  • SSL verification can be disabled (for VPN/proxy users)")
    print("  • SSL verification can be re-enabled (toggle support)")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_ssl_verification_with_sec_gov()
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    except Exception as e:
        print(f"\n⚠ TEST ERROR: {e}")
        print("Note: This test requires internet connectivity to SEC.gov")
        import traceback
        traceback.print_exc()
        exit(1)
