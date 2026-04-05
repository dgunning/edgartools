"""Tests for YAML migration of importance tiers and company industry map."""
from pathlib import Path

import pytest
import yaml


CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "edgar" / "xbrl" / "standardization" / "config"


# ── Stage 2: Importance Tier Migration ──────────────────────────────

class TestImportanceTierMigration:
    """Verify that all metrics in metrics.yaml have importance_tier field."""

    @pytest.fixture(scope="class")
    def metrics_yaml(self):
        with open(CONFIG_DIR / "metrics.yaml") as f:
            return yaml.safe_load(f)

    def test_all_metrics_have_importance_tier(self, metrics_yaml):
        """Every metric in metrics.yaml must have an importance_tier field."""
        metrics = metrics_yaml.get("metrics", {})
        missing = [name for name, data in metrics.items() if "importance_tier" not in data]
        assert not missing, f"Metrics missing importance_tier: {missing}"

    def test_importance_tiers_are_valid(self, metrics_yaml):
        """All importance_tier values must be one of the allowed tiers."""
        valid_tiers = {"core", "extended", "derived", "exploratory"}
        metrics = metrics_yaml.get("metrics", {})
        invalid = {
            name: data.get("importance_tier")
            for name, data in metrics.items()
            if data.get("importance_tier") not in valid_tiers
        }
        assert not invalid, f"Invalid importance_tier values: {invalid}"

    def test_importance_tiers_match_legacy_values(self, metrics_yaml):
        """YAML tiers must match the legacy _DEFAULT_IMPORTANCE_TIERS mapping."""
        expected = {
            # Core (8)
            "Revenue": "core", "OperatingIncome": "core", "NetIncome": "core",
            "OperatingCashFlow": "core", "TotalAssets": "core", "EarningsPerShareDiluted": "core",
            "TotalLiabilities": "core", "StockholdersEquity": "core",
            # Extended (14)
            "COGS": "extended", "SGA": "extended", "PretaxIncome": "extended",
            "Capex": "extended", "LongTermDebt": "extended", "CashAndEquivalents": "extended",
            "WeightedAverageSharesDiluted": "extended", "DepreciationAmortization": "extended",
            "GrossProfit": "extended", "InterestExpense": "extended", "IncomeTaxExpense": "extended",
            "CurrentAssets": "extended", "CurrentLiabilities": "extended", "RetainedEarnings": "extended",
            # Derived (1)
            "EarningsPerShareBasic": "derived",
        }
        metrics = metrics_yaml.get("metrics", {})
        mismatches = {}
        for name, tier in expected.items():
            actual = metrics.get(name, {}).get("importance_tier")
            if actual != tier:
                mismatches[name] = f"expected={tier}, actual={actual}"
        assert not mismatches, f"Tier mismatches: {mismatches}"

    def test_config_loader_reads_tier(self):
        """ConfigLoader should populate MetricConfig.importance_tier from YAML."""
        from edgar.xbrl.standardization.config_loader import ConfigLoader
        config = ConfigLoader().load()
        revenue = config.get_metric("Revenue")
        assert revenue is not None
        assert revenue.importance_tier == "core"

        eps_basic = config.get_metric("EarningsPerShareBasic")
        assert eps_basic is not None
        assert eps_basic.importance_tier == "derived"


# ── Stage 3: Company Industry Map Migration ─────────────────────────

class TestCompanyIndustryMigration:
    """Verify that all companies from legacy _COMPANY_INDUSTRY_MAP are in YAML."""

    LEGACY_MAP = {
        "JPM": "banking", "BAC": "banking", "GS": "banking", "MS": "banking", "C": "banking",
        "WFC": "banking", "USB": "banking", "BK": "banking", "STT": "banking", "PNC": "banking",
        "SCHW": "securities", "ICE": "securities", "CME": "securities",
        "BLK": "asset_management",
        "AXP": "financial_services", "DE": "financial_services",
        "SPGI": "financial_services", "MCO": "financial_services",
        "UNH": "health_insurance", "AON": "insurance", "MMC": "insurance",
        "BRK-B": "insurance",
        "CI": "health_insurance", "CB": "insurance", "AIG": "insurance", "MET": "insurance",
        "XOM": "energy", "CVX": "energy", "COP": "energy", "SLB": "energy",
        "PLD": "reits", "AMT": "reits", "EQIX": "reits", "SPG": "reits",
        "T": "telecom", "VZ": "telecom", "TMUS": "telecom", "CMCSA": "telecom",
        "NEE": "utilities", "DUK": "utilities", "SO": "utilities", "D": "utilities",
        "UPS": "transportation", "FDX": "transportation", "CSX": "transportation", "NSC": "transportation",
        "MCD": "franchise",
    }

    @pytest.fixture(scope="class")
    def companies_yaml(self):
        with open(CONFIG_DIR / "companies.yaml") as f:
            return yaml.safe_load(f)

    def test_all_industry_entries_in_yaml(self, companies_yaml):
        """Every ticker in legacy map must have matching industry in companies.yaml."""
        companies = companies_yaml.get("companies", {})
        missing = {}
        mismatched = {}
        for ticker, expected_industry in self.LEGACY_MAP.items():
            company = companies.get(ticker)
            if not company:
                missing[ticker] = expected_industry
            elif company.get("industry") != expected_industry:
                mismatched[ticker] = f"expected={expected_industry}, actual={company.get('industry')}"
        assert not missing, f"Tickers missing from companies.yaml: {missing}"
        assert not mismatched, f"Industry mismatches: {mismatched}"

    def test_industry_values_valid(self, companies_yaml):
        """All industry values must exist in industry_metrics.yaml."""
        with open(CONFIG_DIR / "industry_metrics.yaml") as f:
            industry_metrics = yaml.safe_load(f) or {}

        valid_industries = set(industry_metrics.keys())
        companies = companies_yaml.get("companies", {})

        invalid = {}
        for ticker, data in companies.items():
            if isinstance(data, dict) and "industry" in data:
                ind = data["industry"]
                if ind not in valid_industries:
                    invalid[ticker] = ind

        assert not invalid, f"Invalid industry values (not in industry_metrics.yaml): {invalid}"

    def test_yaml_industry_takes_priority(self):
        """ConfigLoader._get_industry_for_company should return YAML industry."""
        from edgar.xbrl.standardization.config_loader import ConfigLoader
        config = ConfigLoader().load()

        # Check a few representative companies
        for ticker, expected in [("JPM", "banking"), ("XOM", "energy"), ("MCD", "franchise")]:
            company = config.get_company(ticker)
            assert company is not None, f"{ticker} not in config"
            industry = config._get_industry_for_company(ticker, company, network=False)
            assert industry == expected, f"{ticker}: expected={expected}, actual={industry}"

    def test_no_company_industry_map_in_code(self):
        """The _COMPANY_INDUSTRY_MAP constant must not exist in config_loader.py."""
        config_loader_path = CONFIG_DIR.parent / "config_loader.py"
        content = config_loader_path.read_text()
        assert "_COMPANY_INDUSTRY_MAP" not in content, (
            "_COMPANY_INDUSTRY_MAP still exists in config_loader.py — should be removed"
        )

    def test_no_default_importance_tiers_in_code(self):
        """The _DEFAULT_IMPORTANCE_TIERS constant must not exist in config_loader.py."""
        config_loader_path = CONFIG_DIR.parent / "config_loader.py"
        content = config_loader_path.read_text()
        assert "_DEFAULT_IMPORTANCE_TIERS" not in content, (
            "_DEFAULT_IMPORTANCE_TIERS still exists in config_loader.py — should be removed"
        )
