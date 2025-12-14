"""
Enterprise Configuration Example

Demonstrates how to configure EdgarTools for enterprise use cases including:
- Custom SEC mirrors (corporate, academic, regional)
- Configurable rate limiting
- Environment-based configuration profiles
- Validation and health checks
- Fallback strategies

EdgarTools v4.28.0+ supports the following environment variables:
- EDGAR_BASE_URL: Base URL for SEC EDGAR website
- EDGAR_DATA_URL: Base URL for SEC data archives
- EDGAR_XBRL_URL: Base URL for XBRL data
- EDGAR_RATE_LIMIT_PER_SEC: Requests per second limit

See docs/configuration.md#enterprise-configuration for complete documentation.
"""

import os
import sys
from typing import Dict, Optional

# ============================================================================
# Configuration Profiles
# ============================================================================

def configure_official_sec():
    """
    Official SEC servers (default configuration).

    Rate limit: 9 req/sec (SEC standard)
    Use case: Individual users, standard compliance
    """
    os.environ['EDGAR_IDENTITY'] = "Research User researcher@example.com"
    os.environ['EDGAR_BASE_URL'] = "https://www.sec.gov"
    os.environ['EDGAR_DATA_URL'] = "https://data.sec.gov"
    os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "9"
    print("✓ Configured for official SEC servers (9 req/sec)")


def configure_corporate_mirror():
    """
    Corporate SEC mirror with higher rate limits.

    Rate limit: 50 req/sec
    Use case: Enterprise deployments, corporate compliance teams
    Requirements: Private SEC mirror infrastructure
    """
    os.environ['EDGAR_IDENTITY'] = "Corporate Compliance compliance@company.com"
    os.environ['EDGAR_BASE_URL'] = "https://sec-mirror.company.com"
    os.environ['EDGAR_DATA_URL'] = "https://sec-data.company.com"
    os.environ['EDGAR_XBRL_URL'] = "https://sec-xbrl.company.com"
    os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "50"
    os.environ['EDGAR_USE_LOCAL_DATA'] = "True"
    os.environ['EDGAR_LOCAL_DATA_DIR'] = "/var/lib/edgar"
    print("✓ Configured for corporate mirror (50 req/sec)")


def configure_academic_mirror():
    """
    Academic/research institution mirror.

    Rate limit: 25 req/sec
    Use case: University research, academic analysis
    Requirements: Academic SEC mirror subscription
    """
    os.environ['EDGAR_IDENTITY'] = "Research Lab research@university.edu"
    os.environ['EDGAR_BASE_URL'] = "https://sec.university.edu"
    os.environ['EDGAR_DATA_URL'] = "https://sec-data.university.edu"
    os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "25"
    os.environ['EDGAR_USE_LOCAL_DATA'] = "True"
    os.environ['EDGAR_LOCAL_DATA_DIR'] = "/research/edgar_data"
    print("✓ Configured for academic mirror (25 req/sec)")


def configure_regional_mirror():
    """
    Regional mirror for international users.

    Rate limit: 15 req/sec
    Use case: Reduced latency for international users
    Requirements: Regional SEC mirror access
    """
    os.environ['EDGAR_IDENTITY'] = "International Analyst analyst@company.com"
    os.environ['EDGAR_BASE_URL'] = "https://sec-eu.example.com"
    os.environ['EDGAR_DATA_URL'] = "https://sec-data-eu.example.com"
    os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "15"
    os.environ['EDGAR_ACCESS_MODE'] = "NORMAL"
    print("✓ Configured for regional mirror (15 req/sec)")


def configure_development():
    """
    Development/testing environment with local mock server.

    Rate limit: 100 req/sec (no restrictions)
    Use case: Local development, testing, CI/CD
    """
    os.environ['EDGAR_IDENTITY'] = "Developer dev@company.com"
    os.environ['EDGAR_BASE_URL'] = "http://localhost:8080"
    os.environ['EDGAR_DATA_URL'] = "http://localhost:8080/data"
    os.environ['EDGAR_XBRL_URL'] = "http://localhost:8080/xbrl"
    os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "100"
    os.environ['EDGAR_VERIFY_SSL'] = "false"
    os.environ['EDGAR_USE_RICH_LOGGING'] = "1"
    print("✓ Configured for development (100 req/sec, SSL verification disabled)")


# ============================================================================
# Environment-Based Configuration
# ============================================================================

def configure_from_environment(env: str = "production"):
    """
    Load configuration based on environment name.

    Args:
        env: Environment name (development, staging, production)
    """
    configs = {
        "development": {
            "identity": "Developer dev@company.com",
            "base_url": "http://localhost:8080",
            "data_url": "http://localhost:8080/data",
            "rate_limit": "100",
            "verify_ssl": "false",
        },
        "staging": {
            "identity": "Staging System staging@company.com",
            "base_url": "https://sec-staging.company.com",
            "data_url": "https://sec-data-staging.company.com",
            "rate_limit": "25",
            "verify_ssl": "true",
        },
        "production": {
            "identity": "Production System prod@company.com",
            "base_url": "https://sec-mirror.company.com",
            "data_url": "https://sec-data.company.com",
            "rate_limit": "50",
            "verify_ssl": "true",
        }
    }

    if env not in configs:
        raise ValueError(f"Unknown environment: {env}. Choose from: {list(configs.keys())}")

    config = configs[env]
    os.environ['EDGAR_IDENTITY'] = config['identity']
    os.environ['EDGAR_BASE_URL'] = config['base_url']
    os.environ['EDGAR_DATA_URL'] = config['data_url']
    os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = config['rate_limit']
    os.environ['EDGAR_VERIFY_SSL'] = config['verify_ssl']

    print(f"✓ Configured for {env} environment ({config['rate_limit']} req/sec)")


# ============================================================================
# Regional Configuration
# ============================================================================

def configure_region(region: str):
    """
    Configure regional mirrors for reduced latency.

    Args:
        region: Region code (us, eu, apac)
    """
    mirrors = {
        "us": {
            "base": "https://www.sec.gov",
            "data": "https://data.sec.gov",
            "rate": "9",
        },
        "eu": {
            "base": "https://sec-eu.example.com",
            "data": "https://sec-data-eu.example.com",
            "rate": "15",
        },
        "apac": {
            "base": "https://sec-apac.example.com",
            "data": "https://sec-data-apac.example.com",
            "rate": "15",
        }
    }

    if region not in mirrors:
        raise ValueError(f"Unknown region: {region}. Choose from: {list(mirrors.keys())}")

    mirror = mirrors[region]
    os.environ['EDGAR_BASE_URL'] = mirror['base']
    os.environ['EDGAR_DATA_URL'] = mirror['data']
    os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = mirror['rate']

    print(f"✓ Configured for {region.upper()} region ({mirror['rate']} req/sec)")


# ============================================================================
# Validation and Health Checks
# ============================================================================

def validate_configuration() -> bool:
    """
    Validate enterprise configuration and connectivity.

    Returns:
        True if configuration is valid and operational
    """
    from edgar import Company

    print("\n" + "="*70)
    print("Configuration Validation")
    print("="*70)

    # Check environment variables
    required_vars = {
        'EDGAR_IDENTITY': os.getenv('EDGAR_IDENTITY'),
        'EDGAR_BASE_URL': os.getenv('EDGAR_BASE_URL', 'https://www.sec.gov'),
        'EDGAR_DATA_URL': os.getenv('EDGAR_DATA_URL', 'https://data.sec.gov'),
        'EDGAR_RATE_LIMIT_PER_SEC': os.getenv('EDGAR_RATE_LIMIT_PER_SEC', '9'),
    }

    print("\nEnvironment Variables:")
    for key, value in required_vars.items():
        status = "✓" if value else "✗"
        print(f"  {status} {key}: {value or 'NOT SET'}")

    # Validate identity
    if not required_vars['EDGAR_IDENTITY']:
        print("\n❌ ERROR: EDGAR_IDENTITY must be set")
        return False

    # Test connectivity
    print("\nConnectivity Test:")
    try:
        company = Company("AAPL")
        print(f"  ✓ Successfully connected: {company.name}")

        # Test filing retrieval
        filings = company.get_filings(form="10-K").head(1)
        if filings:
            print(f"  ✓ Successfully retrieved filing: {filings[0].accession_number}")

        print("\n" + "="*70)
        print("✓ Configuration is valid and operational")
        print("="*70)
        return True

    except Exception as e:
        print(f"  ❌ Connection failed: {e}")
        print("\n" + "="*70)
        print("✗ Configuration validation failed")
        print("="*70)
        return False


def show_current_config():
    """Display current configuration."""
    print("\n" + "="*70)
    print("Current Configuration")
    print("="*70)

    config_items = [
        ("Identity", os.getenv('EDGAR_IDENTITY', 'NOT SET')),
        ("Base URL", os.getenv('EDGAR_BASE_URL', 'https://www.sec.gov (default)')),
        ("Data URL", os.getenv('EDGAR_DATA_URL', 'https://data.sec.gov (default)')),
        ("XBRL URL", os.getenv('EDGAR_XBRL_URL', 'https://www.sec.gov (default)')),
        ("Rate Limit", f"{os.getenv('EDGAR_RATE_LIMIT_PER_SEC', '9')} req/sec"),
        ("Access Mode", os.getenv('EDGAR_ACCESS_MODE', 'NORMAL (default)')),
        ("Local Data", os.getenv('EDGAR_USE_LOCAL_DATA', 'False (default)')),
        ("SSL Verify", os.getenv('EDGAR_VERIFY_SSL', 'true (default)')),
    ]

    for label, value in config_items:
        print(f"  {label:15}: {value}")

    print("="*70)


# ============================================================================
# Fallback Strategy
# ============================================================================

def configure_with_fallback(primary_config: str, fallback_to_official: bool = True):
    """
    Configure with fallback to official SEC servers on failure.

    Args:
        primary_config: Primary configuration function name
        fallback_to_official: Whether to fallback to official SEC servers
    """
    configs = {
        "corporate": configure_corporate_mirror,
        "academic": configure_academic_mirror,
        "regional": configure_regional_mirror,
    }

    if primary_config not in configs:
        raise ValueError(f"Unknown config: {primary_config}")

    # Try primary configuration
    print(f"Attempting {primary_config} configuration...")
    configs[primary_config]()

    if not validate_configuration():
        if fallback_to_official:
            print("\n⚠️  Primary configuration failed, falling back to official SEC...")
            configure_official_sec()
            if not validate_configuration():
                print("\n❌ Fallback configuration also failed")
                sys.exit(1)
        else:
            print("\n❌ Configuration failed and fallback disabled")
            sys.exit(1)


# ============================================================================
# Example Usage
# ============================================================================

def main():
    """Demonstrate configuration profiles."""
    print("\n" + "="*70)
    print("EdgarTools Enterprise Configuration Examples")
    print("="*70)

    # Show available configurations
    print("\nAvailable Configuration Profiles:")
    print("  1. Official SEC (default)")
    print("  2. Corporate Mirror")
    print("  3. Academic Mirror")
    print("  4. Regional Mirror")
    print("  5. Development/Testing")
    print("  6. Environment-based (dev/staging/prod)")
    print("  7. Region-based (us/eu/apac)")

    # Example: Configure for corporate mirror
    print("\n" + "-"*70)
    print("Example 1: Corporate Mirror Configuration")
    print("-"*70)
    configure_corporate_mirror()
    show_current_config()

    # Example: Environment-based configuration
    print("\n" + "-"*70)
    print("Example 2: Environment-Based Configuration")
    print("-"*70)
    configure_from_environment("production")
    show_current_config()

    # Example: Validation
    print("\n" + "-"*70)
    print("Example 3: Configuration Validation")
    print("-"*70)

    # Note: Actual validation requires network access
    print("To run validation, ensure you have network access and uncomment:")
    print("  validate_configuration()")

    print("\n" + "="*70)
    print("Configuration examples completed")
    print("="*70)
    print("\nNext steps:")
    print("  1. Choose a configuration profile")
    print("  2. Set EDGAR_IDENTITY with your details")
    print("  3. Validate configuration before production use")
    print("  4. See docs/configuration.md for complete documentation")


if __name__ == "__main__":
    main()
