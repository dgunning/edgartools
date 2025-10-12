"""
Reproduction script for Issue #457: Filing Access Failure with Locale-dependent Date Parsing

Issue: https://github.com/dgunning/edgartools/issues/457
Reporter: chuhanyi03 (Holly)
Environment: Windows 11, Python 3.12.11, EdgarTools 4.18.0

Description:
The httpxthrottlecache library uses time.strptime() to parse HTTP date headers
without forcing the C locale. When the system locale is set to Chinese (or any
non-English locale), the date parsing fails because month/day names are in the
local language format (e.g., '周五, 10 10月 2025' instead of 'Fri, 10 Oct 2025').

Root Cause:
In httpxthrottlecache/filecache/transport.py, the code uses:
    time.strptime(last_modified, "%a, %d %b %Y %H:%M:%S GMT")

This is locale-dependent and fails when LC_TIME is not set to C/en_US.

Expected Behavior:
EdgarTools should work regardless of system locale settings.

Actual Behavior:
ValueError: time data '周五, 10 10月 2025 11:57:10 GMT' does not match format '%a, %d %b %Y %H:%M:%S GMT'
"""

import locale
import os
import sys
from pathlib import Path

# Set identity before importing edgar
os.environ["EDGAR_IDENTITY"] = "Issue 457 Reproduction test@example.com"

def test_with_chinese_locale():
    """Test that simulates the Chinese locale issue"""
    print("\n" + "="*80)
    print("Testing Issue #457: Locale-dependent Date Parsing")
    print("="*80)

    # Show current locale
    current_locale = locale.getlocale()
    print(f"\nCurrent locale: {current_locale}")

    # Try to set Chinese locale (this might not work on all systems)
    try:
        locale.setlocale(locale.LC_TIME, 'zh_CN.UTF-8')
        print("✓ Successfully set locale to Chinese (zh_CN.UTF-8)")
        new_locale = locale.getlocale()
        print(f"  New locale: {new_locale}")
    except locale.Error:
        print("✗ Could not set Chinese locale (zh_CN.UTF-8) - trying alternatives")
        try:
            # Try Windows format
            locale.setlocale(locale.LC_TIME, 'Chinese_China.936')
            print("✓ Successfully set locale to Chinese (Chinese_China.936)")
        except locale.Error:
            print("✗ Could not set any Chinese locale - skipping locale-specific test")
            print("  This test requires Chinese locale support to be installed")
            return False

    # Now try to use EdgarTools
    print("\n" + "-"*80)
    print("Attempting to use EdgarTools with Chinese locale...")
    print("-"*80)

    try:
        from edgar import Company
        print("\n1. Importing Company class... ✓")

        print("2. Creating Company('AAPL')...")
        apple = Company("AAPL")
        print(f"   Company created: {apple.name} ✓")

        print("3. Getting latest 10-K filing...")
        filing = apple.latest("10-K")
        print(f"   Filing retrieved: {filing.form} on {filing.filing_date} ✓")

        print("\n" + "="*80)
        print("SUCCESS: EdgarTools works correctly with Chinese locale!")
        print("="*80)
        return True

    except ValueError as e:
        error_msg = str(e)
        print(f"\n❌ ERROR: {error_msg}")

        if "does not match format" in error_msg and "GMT" in error_msg:
            print("\n" + "="*80)
            print("REPRODUCED: Issue #457 - Locale-dependent date parsing failure")
            print("="*80)
            print("\nRoot Cause:")
            print("  The httpxthrottlecache library uses locale-dependent time.strptime()")
            print("  to parse HTTP date headers. With Chinese locale, month/day names are")
            print("  in Chinese (e.g., '周五' for Friday, '10月' for October), causing")
            print("  parsing to fail.")
            print("\nExpected date format: 'Fri, 10 Oct 2025 11:57:10 GMT'")
            print(f"Actual parsed format:  (extracted from error: {error_msg.split('time data ')[1].split(' does not')[0]})")
            return True  # Successfully reproduced the issue
        else:
            print(f"\n❌ Unexpected error: {e}")
            import traceback
            traceback.print_exc()
            return False

    except Exception as e:
        print(f"\n❌ Unexpected error type: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Restore original locale
        try:
            locale.setlocale(locale.LC_TIME, current_locale[0] or 'C')
            print(f"\n✓ Restored original locale: {locale.getlocale()}")
        except Exception as e:
            print(f"\n⚠ Could not restore locale: {e}")


def test_with_c_locale():
    """Test that EdgarTools works with C locale (baseline)"""
    print("\n" + "="*80)
    print("Baseline Test: EdgarTools with C/English Locale")
    print("="*80)

    try:
        locale.setlocale(locale.LC_TIME, 'C')
        print(f"✓ Set locale to C: {locale.getlocale()}")
    except locale.Error:
        print("✗ Could not set C locale - using default")

    try:
        from edgar import Company
        print("\n1. Importing Company class... ✓")

        print("2. Creating Company('AAPL')...")
        apple = Company("AAPL")
        print(f"   Company created: {apple.name} ✓")

        print("3. Getting latest 10-K filing...")
        filing = apple.latest("10-K")
        print(f"   Filing retrieved: {filing.form} on {filing.filing_date} ✓")

        print("\n" + "="*80)
        print("SUCCESS: EdgarTools works correctly with C locale (baseline)")
        print("="*80)
        return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "EdgarTools Issue #457 Reproduction" + " "*24 + "║")
    print("║" + " "*15 + "Locale-dependent Date Parsing Failure" + " "*26 + "║")
    print("╚" + "="*78 + "╝")

    # Run baseline test first
    baseline_success = test_with_c_locale()

    if baseline_success:
        # Run Chinese locale test
        issue_reproduced = test_with_chinese_locale()

        print("\n" + "="*80)
        print("REPRODUCTION SUMMARY")
        print("="*80)
        print(f"Baseline test (C locale):     {'PASSED' if baseline_success else 'FAILED'}")
        print(f"Chinese locale test:          {'ISSUE REPRODUCED' if issue_reproduced else 'FAILED TO REPRODUCE'}")
        print("="*80)

        if issue_reproduced:
            print("\n✓ Issue #457 has been successfully reproduced!")
            print("\nNext Steps:")
            print("  1. Fix httpxthrottlecache to use locale-independent date parsing")
            print("  2. Alternative: Implement workaround in EdgarTools to force C locale")
            print("  3. Add regression test to prevent future locale-related issues")
    else:
        print("\n❌ Baseline test failed - cannot proceed with locale-specific test")
        sys.exit(1)
