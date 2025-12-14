"""Check what error messages are generated in different diagnostic states."""

from edgar.httpclient import HTTP_MGR, configure_http
from edgar.httprequests import SSLErrorCategory, _build_solution_section, _get_ssl_diagnostic

# Test different states
states = [
    ("Default (verify=True)", True, False),
    ("Disabled (verify=False)", False, False),
    ("Disabled with client", False, True),
]

for name, verify, create_client in states:
    print(f"\n{name}:")
    print("=" * 60)

    # Reset
    if HTTP_MGR._client:
        HTTP_MGR._client.close()
        HTTP_MGR._client = None

    configure_http(verify_ssl=verify)

    # Create client if requested
    if create_client:
        from edgar.httpclient import http_client
        with http_client() as _:
            pass

    diag = _get_ssl_diagnostic()
    print(f"configured_verify: {diag.configured_verify}")
    print(f"client_exists: {diag.client_exists}")
    print(f"client_verify: {diag.client_verify}")
    print(f"status: {diag.status}")

    solution = _build_solution_section(SSLErrorCategory.UNKNOWN, diag)
    has_edgar_ssl = "EDGAR_VERIFY_SSL" in solution
    has_configure = "configure_http" in solution

    print(f"Has EDGAR_VERIFY_SSL: {has_edgar_ssl}")
    print(f"Has configure_http: {has_configure}")

# Reset to default
configure_http(verify_ssl=True)
if HTTP_MGR._client:
    HTTP_MGR._client.close()
    HTTP_MGR._client = None
