"""
Complete SSL Verification Test Suite

Runs all SSL verification tests to definitively prove the fix works:
1. Unit tests - Parameter passing
2. Client tests - SSL context inspection
3. Integration tests - Real HTTPS requests

Run this to verify the httpxthrottlecache monkey patch is working correctly.
"""

import subprocess
import sys


def run_test(test_file, description):
    """Run a test script and report results."""
    print(f"\n{'=' * 70}")
    print(f"Running: {description}")
    print(f"File: {test_file}")
    print('=' * 70)

    result = subprocess.run(
        [sys.executable, test_file],
        capture_output=False,
        text=True
    )

    if result.returncode == 0:
        print(f"\n✓ {description} PASSED")
        return True
    else:
        print(f"\n✗ {description} FAILED")
        return False


def main():
    """Run all SSL verification tests."""
    print("\n" + "=" * 70)
    print("COMPLETE SSL VERIFICATION TEST SUITE")
    print("=" * 70)
    print("\nThis suite verifies that configure_http(verify_ssl=False) works")
    print("correctly with the httpxthrottlecache monkey patch fix.")
    print("\nTests run:")
    print("  1. Unit tests - Parameter passing through transport chain")
    print("  2. Client tests - Actual httpx.Client SSL context inspection")
    print("  3. Integration tests - Real HTTPS requests to SEC.gov")

    tests = [
        ("scripts/test_ssl_verify_fix.py", "Unit Tests - Parameter Passing"),
        ("scripts/test_ssl_verify_httpx_client.py", "Client Tests - SSL Context Inspection"),
        ("scripts/test_ssl_verify_integration.py", "Integration Tests - Real HTTPS Requests"),
    ]

    results = []
    for test_file, description in tests:
        passed = run_test(test_file, description)
        results.append((description, passed))

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUITE SUMMARY")
    print("=" * 70)

    all_passed = True
    for description, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{status}: {description}")
        if not passed:
            all_passed = False

    print("=" * 70)

    if all_passed:
        print("\n🎉 ALL TESTS PASSED!")
        print("\nThe httpxthrottlecache monkey patch is working correctly:")
        print("  • Parameters are passed through transport chain")
        print("  • SSL context is properly configured in httpx.Client")
        print("  • Real HTTPS requests work with SSL verification on/off")
        print("\nThe fix is production-ready!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        print("The SSL verification fix has issues that need to be addressed.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
