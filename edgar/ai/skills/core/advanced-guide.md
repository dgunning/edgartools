# Advanced Guide

Advanced patterns, helper functions, error handling, and skill exportation for EdgarTools.

**For basic usage, see** [SKILL.md](SKILL.md).
**For complete examples, see** [common-questions.md](common-questions.md).

## Table of Contents

1. [Advanced Patterns](#advanced-patterns)
   - [Filtering and Pagination](#filtering-and-pagination)
   - [Multi-Company Analysis](#multi-company-analysis)
   - [Error Handling](#error-handling)
   - [Enterprise Configuration](#enterprise-configuration)
   - [Working with Filing Documents](#working-with-filing-documents)
2. [Helper Functions Reference](#helper-functions-reference)
3. [Exporting Skills](#exporting-skills)
   - [Export for Claude Desktop](#export-for-claude-desktop)
   - [Using in Claude Desktop](#using-in-claude-desktop)
   - [Creating External Skills](#creating-external-skills)
   - [Skill Discovery](#skill-discovery)

---

## Advanced Patterns

Multi-step workflows and advanced use cases.

### Filtering and Pagination

```python
from edgar import get_filings

# Get large result set
filings = get_filings(2023, 1)

# Filter by multiple criteria
filtered = filings.filter(
    form=["10-K", "10-Q"],
    ticker=["AAPL", "MSFT", "GOOGL"]
)

# Pagination
print(filtered.head(10))  # First 10
print(filtered[10:20])  # Next 10

# Iterate
for filing in filtered[:5]:
    print(f"{filing.company} - {filing.form} - {filing.filing_date}")
```

### Multi-Company Analysis

```python
from edgar import Company

tickers = ["AAPL", "MSFT", "GOOGL", "META", "AMZN"]

# Collect revenue data
revenue_data = {}
for ticker in tickers:
    company = Company(ticker)
    income = company.income_statement(periods=3)
    revenue_data[ticker] = income

# Display comparisons
for ticker, statement in revenue_data.items():
    print(f"\n{ticker} Revenue:")
    print(statement)
```

### Error Handling

```python
from edgar import Company

try:
    company = Company("INVALID_TICKER")
    income = company.income_statement(periods=3)
except Exception as e:
    print(f"Error: {e}")
    # Handle error appropriately

# Check data availability
filings = get_filings(2023, 1, form="RARE-FORM")
if len(filings) == 0:
    print("No filings found matching criteria")
else:
    print(f"Found {len(filings)} filings")

# Verify XBRL availability
filing = company.get_filings(form="10-K")[0]
if hasattr(filing, 'xbrl') and filing.xbrl:
    xbrl = filing.xbrl()
    # Process XBRL
else:
    print("XBRL data not available")
```

### Enterprise Configuration

EdgarTools v4.28.0+ supports enterprise deployments with custom SEC mirrors, flexible rate limiting, and containerized environments. This section covers practical patterns for advanced users.

**See also**: [Configuration Documentation](../../../../docs/configuration.md#enterprise-configuration) for complete reference.

#### Custom SEC Mirror Setup

Configure EdgarTools to use your organization's private SEC mirror:

```python
import os

# Set before importing edgar modules
os.environ['EDGAR_IDENTITY'] = "Corporate Compliance compliance@company.com"
os.environ['EDGAR_BASE_URL'] = "https://sec-mirror.company.com"
os.environ['EDGAR_DATA_URL'] = "https://sec-data.company.com"
os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "50"

# Now import and use EdgarTools
from edgar import Company, get_filings

# All requests use custom mirror
company = Company("AAPL")
filings = get_filings(2023, 1, form="10-K")
```

#### Rate Limiting for High-Volume Applications

Adjust rate limits for authorized custom mirrors:

```python
import os
from edgar import httpclient

# Environment variable approach (set before import)
os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "25"

# Programmatic approach (after import)
httpclient.update_rate_limiter(requests_per_second=25)

# Verify current rate limit
print(f"Rate limit: {os.getenv('EDGAR_RATE_LIMIT_PER_SEC', '9')} req/sec")
```

#### Docker/Container Configuration

**Dockerfile Example:**

```dockerfile
FROM python:3.11-slim

# Install EdgarTools
RUN pip install edgartools

# Enterprise configuration
ENV EDGAR_IDENTITY="Container App app@company.com"
ENV EDGAR_BASE_URL="https://sec-mirror.company.com"
ENV EDGAR_DATA_URL="https://sec-data.company.com"
ENV EDGAR_RATE_LIMIT_PER_SEC="50"
ENV EDGAR_USE_LOCAL_DATA="True"
ENV EDGAR_LOCAL_DATA_DIR="/app/edgar_data"

# Create data directory and volume
RUN mkdir -p /app/edgar_data
VOLUME /app/edgar_data

WORKDIR /app
COPY . .

CMD ["python", "analysis.py"]
```

**Docker Compose with Multiple Services:**

```yaml
version: '3.8'

services:
  edgar-analyzer:
    build: .
    environment:
      - EDGAR_IDENTITY=Analyzer Service analyzer@company.com
      - EDGAR_BASE_URL=https://sec-mirror.company.com
      - EDGAR_RATE_LIMIT_PER_SEC=50
      - EDGAR_USE_LOCAL_DATA=True
      - EDGAR_LOCAL_DATA_DIR=/data
    volumes:
      - edgar-data:/data
    networks:
      - edgar-net

  edgar-batch:
    build: .
    environment:
      - EDGAR_IDENTITY=Batch Processor batch@company.com
      - EDGAR_BASE_URL=https://sec-mirror.company.com
      - EDGAR_ACCESS_MODE=CRAWL
      - EDGAR_RATE_LIMIT_PER_SEC=30
      - EDGAR_USE_LOCAL_DATA=True
      - EDGAR_LOCAL_DATA_DIR=/data
    volumes:
      - edgar-data:/data
    networks:
      - edgar-net

volumes:
  edgar-data:

networks:
  edgar-net:
```

#### Configuration Profiles for Different Environments

**Development:**
```python
import os

def configure_development():
    """Development environment with local mock server."""
    os.environ['EDGAR_IDENTITY'] = "Developer dev@company.com"
    os.environ['EDGAR_BASE_URL'] = "http://localhost:8080"
    os.environ['EDGAR_VERIFY_SSL'] = "false"
    os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "100"
    os.environ['EDGAR_USE_RICH_LOGGING'] = "1"
```

**Staging:**
```python
def configure_staging():
    """Staging environment with corporate mirror."""
    os.environ['EDGAR_IDENTITY'] = "Staging System staging@company.com"
    os.environ['EDGAR_BASE_URL'] = "https://sec-staging.company.com"
    os.environ['EDGAR_DATA_URL'] = "https://sec-data-staging.company.com"
    os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "25"
    os.environ['EDGAR_ACCESS_MODE'] = "CAUTION"
    os.environ['EDGAR_USE_LOCAL_DATA'] = "True"
```

**Production:**
```python
def configure_production():
    """Production environment with full enterprise setup."""
    os.environ['EDGAR_IDENTITY'] = "Production System prod@company.com"
    os.environ['EDGAR_BASE_URL'] = "https://sec-mirror.company.com"
    os.environ['EDGAR_DATA_URL'] = "https://sec-data.company.com"
    os.environ['EDGAR_XBRL_URL'] = "https://sec-xbrl.company.com"
    os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "50"
    os.environ['EDGAR_ACCESS_MODE'] = "CAUTION"
    os.environ['EDGAR_USE_LOCAL_DATA'] = "True"
    os.environ['EDGAR_LOCAL_DATA_DIR'] = "/var/lib/edgar"
    os.environ['EDGAR_VERIFY_SSL'] = "true"

# Load based on environment
import sys
env = os.getenv('APP_ENV', 'development')
if env == 'production':
    configure_production()
elif env == 'staging':
    configure_staging()
else:
    configure_development()
```

#### Kubernetes Deployment

**ConfigMap:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: edgar-config
data:
  EDGAR_BASE_URL: "https://sec-mirror.company.com"
  EDGAR_DATA_URL: "https://sec-data.company.com"
  EDGAR_RATE_LIMIT_PER_SEC: "50"
  EDGAR_ACCESS_MODE: "CAUTION"
  EDGAR_USE_LOCAL_DATA: "True"
```

**Deployment:**
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: edgar-analyzer
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: analyzer
        image: company/edgar-analyzer:latest
        envFrom:
        - configMapRef:
            name: edgar-config
        env:
        - name: EDGAR_IDENTITY
          value: "K8s Analyzer analyzer@company.com"
        - name: EDGAR_LOCAL_DATA_DIR
          value: "/data"
        volumeMounts:
        - name: edgar-data
          mountPath: /data
      volumes:
      - name: edgar-data
        persistentVolumeClaim:
          claimName: edgar-pvc
```

#### Validation and Health Checks

```python
import os
from edgar import Company

def validate_enterprise_config() -> bool:
    """Validate enterprise configuration and connectivity."""

    # Check required environment variables
    required = {
        'EDGAR_IDENTITY': os.getenv('EDGAR_IDENTITY'),
        'EDGAR_BASE_URL': os.getenv('EDGAR_BASE_URL', 'https://www.sec.gov'),
        'EDGAR_RATE_LIMIT_PER_SEC': os.getenv('EDGAR_RATE_LIMIT_PER_SEC', '9'),
    }

    print("Enterprise Configuration:")
    for key, value in required.items():
        print(f"  {key}: {value}")

    # Test connectivity
    try:
        company = Company("AAPL")
        print(f"\n✓ Successfully connected: {company.name}")

        # Test filing retrieval
        filings = company.get_filings(form="10-K").head(1)
        if filings:
            print(f"✓ Successfully retrieved filing: {filings[0].accession_number}")

        return True
    except Exception as e:
        print(f"\n❌ Configuration test failed: {e}")
        return False

# Run as health check
if __name__ == "__main__":
    is_valid = validate_enterprise_config()
    sys.exit(0 if is_valid else 1)
```

#### Multi-Region Deployment

```python
import os
from typing import Literal

Region = Literal['us', 'eu', 'asia']

def configure_for_region(region: Region):
    """Configure SEC mirror based on deployment region."""

    mirrors = {
        'us': {
            'base': 'https://sec-us.company.com',
            'data': 'https://sec-data-us.company.com',
            'rate': '50'
        },
        'eu': {
            'base': 'https://sec-eu.company.com',
            'data': 'https://sec-data-eu.company.com',
            'rate': '30'  # Lower rate for international
        },
        'asia': {
            'base': 'https://sec-asia.company.com',
            'data': 'https://sec-data-asia.company.com',
            'rate': '25'
        }
    }

    config = mirrors[region]
    os.environ['EDGAR_BASE_URL'] = config['base']
    os.environ['EDGAR_DATA_URL'] = config['data']
    os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = config['rate']

    print(f"Configured for region: {region.upper()}")

# Auto-detect or configure
region = os.getenv('DEPLOY_REGION', 'us')
configure_for_region(region)
```

#### Best Practices

**1. Configuration Security:**
```python
# Use environment variables, never hardcode
# ❌ Bad:
# edgar_config = {'base_url': 'https://sec-mirror.company.com'}

# ✓ Good:
import os
base_url = os.getenv('EDGAR_BASE_URL')
```

**2. Startup Validation:**
```python
def startup_checks():
    """Run configuration checks at application startup."""
    assert os.getenv('EDGAR_IDENTITY'), "EDGAR_IDENTITY must be set"
    assert os.getenv('EDGAR_BASE_URL'), "EDGAR_BASE_URL must be set"

    # Test connectivity
    validate_enterprise_config()
```

**3. Rate Limit Monitoring:**
```python
import time
from edgar import Company

def monitor_rate_limit():
    """Monitor actual vs configured rate limit."""
    start = time.time()
    requests = 20

    for i in range(requests):
        Company("AAPL")  # Make request

    elapsed = time.time() - start
    actual_rate = requests / elapsed
    configured_rate = int(os.getenv('EDGAR_RATE_LIMIT_PER_SEC', '9'))

    print(f"Configured: {configured_rate} req/sec")
    print(f"Actual: {actual_rate:.2f} req/sec")
```

**4. Graceful Degradation:**
```python
def get_company_with_fallback(ticker: str):
    """Try custom mirror, fallback to official SEC if needed."""
    try:
        return Company(ticker)
    except Exception as e:
        print(f"Custom mirror failed: {e}")
        print("Falling back to official SEC servers...")

        # Temporarily switch to official SEC
        os.environ['EDGAR_BASE_URL'] = "https://www.sec.gov"
        os.environ['EDGAR_DATA_URL'] = "https://data.sec.gov"
        os.environ['EDGAR_RATE_LIMIT_PER_SEC'] = "9"

        return Company(ticker)
```

### Working with Filing Documents

```python
from edgar import Company

company = Company("AAPL")
filing = company.get_filings(form="10-K")[0]

# Get parsed document
doc = filing.document()

# Access sections (for 10-K/10-Q)
if hasattr(doc, 'get_section'):
    item1 = doc.get_section("Item 1")  # Business description
    item1a = doc.get_section("Item 1A")  # Risk factors
    item7 = doc.get_section("Item 7")  # MD&A

# Get raw HTML
html = filing.html()
```

## Helper Functions Reference

Convenience functions available in `edgar.ai.helpers`:

```python
from edgar.ai.helpers import (
    get_filings_by_period,
    get_today_filings,
    get_revenue_trend,
    get_filing_statement,
    compare_companies_revenue,
)

# Get filings for a period
filings = get_filings_by_period(2023, 1, form="10-K")

# Get today's filings
current = get_today_filings()

# Get revenue trend (annual or quarterly)
income = get_revenue_trend("AAPL", periods=3)  # Annual
quarterly = get_revenue_trend("AAPL", periods=4, quarterly=True)

# Get specific statement from filing
income = get_filing_statement("AAPL", 2023, "10-K", "income")
balance = get_filing_statement("AAPL", 2023, "10-K", "balance")
cash_flow = get_filing_statement("AAPL", 2023, "10-K", "cash_flow")

# Compare multiple companies
results = compare_companies_revenue(["AAPL", "MSFT", "GOOGL"], periods=3)
```

## Exporting Skills

EdgarTools AI skills can be exported for use in Claude Desktop and other AI tools.

### Export for Claude Desktop

```python
from edgar.ai import sec_analysis_skill, export_skill

# Export skill to current directory
skill_dir = export_skill(sec_analysis_skill, format="claude-desktop")
print(f"Skill exported to: {skill_dir}")
# Output: Skill exported to: sec-filing-analysis

# Export with custom output directory
from pathlib import Path
output_path = export_skill(
    sec_analysis_skill,
    format="claude-desktop",
    output_dir=Path.home() / "claude-skills"
)

# Export as zip archive
zip_path = export_skill(
    sec_analysis_skill,
    format="claude-desktop",
    create_zip=True
)
print(f"Skill packaged: {zip_path}")
# Output: Skill packaged: sec-filing-analysis.zip
```

### Using in Claude Desktop

After exporting, add the skill to Claude Desktop:

1. Export the skill: `export_skill(sec_analysis_skill)`
2. Move the `sec-filing-analysis` directory to your Claude Desktop skills folder
3. Restart Claude Desktop
4. The skill will appear in your available skills

### Creating External Skills

External packages can extend EdgarTools with custom skills using the `BaseSkill` abstract class:

```python
from edgar.ai.skills.base import BaseSkill
from pathlib import Path
from typing import Dict, Callable

class CustomAnalysisSkill(BaseSkill):
    """Custom SEC analysis skill with specialized workflows."""

    @property
    def name(self) -> str:
        return "Custom SEC Analysis"

    @property
    def description(self) -> str:
        return "Specialized SEC filing analysis for XYZ use case"

    @property
    def content_dir(self) -> Path:
        return Path(__file__).parent / "content"

    def get_helpers(self) -> Dict[str, Callable]:
        """Return custom helper functions."""
        from mypackage import custom_helpers
        return {
            'analyze_filing_sentiment': custom_helpers.sentiment_analysis,
            'extract_risk_factors': custom_helpers.risk_extraction,
        }

# Register with EdgarTools
custom_skill = CustomAnalysisSkill()

# Export custom skill
from edgar.ai import export_skill
export_skill(custom_skill, format="claude-desktop")
```

### Skill Discovery

List all available skills (built-in + external):

```python
from edgar.ai import list_skills, get_skill

# List all skills
skills = list_skills()
for skill in skills:
    print(f"{skill.name}: {skill.description}")

# Get specific skill by name
sec_skill = get_skill("SEC Filing Analysis")
```

---

## See Also

- [SKILL.md](SKILL.md) - Core concepts and API reference
- [common-questions.md](common-questions.md) - Complete examples with full code
- [workflows.md](workflows.md) - End-to-end analysis patterns
- [objects.md](objects.md) - Object representations and token estimates
