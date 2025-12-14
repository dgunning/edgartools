"""Check what SSL error messages look like."""

from edgar.httprequests import _build_solution_section, _categorize_ssl_error, _get_ssl_diagnostic

# Test the errors used in the failing tests
errors = [
    "self signed certificate",
    "certificate verify failed"
]

for error in errors:
    category = _categorize_ssl_error(error)
    diag = _get_ssl_diagnostic()
    solution = _build_solution_section(category, diag)

    print(f"Error: '{error}'")
    print(f"Category: {category}")
    print(f"Solution text includes 'EDGAR_VERIFY_SSL': {'EDGAR_VERIFY_SSL' in solution}")
    print(f"Solution text includes 'configure_http': {'configure_http' in solution}")
    print()
    print("Solution:")
    print(solution)
    print("\n" + "=" * 70 + "\n")
