"""
Configuration loader for the concept mapping system.

Loads and validates metrics.yaml and companies.yaml configurations.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .models import MetricConfig, CompanyConfig


@dataclass
class MappingConfig:
    """Complete configuration for the mapping system."""
    version: str
    metrics: Dict[str, MetricConfig]
    companies: Dict[str, CompanyConfig]
    defaults: Dict
    
    def get_metric(self, name: str) -> Optional[MetricConfig]:
        """Get metric configuration by name."""
        return self.metrics.get(name)
    
    def get_company(self, ticker: str) -> Optional[CompanyConfig]:
        """Get company configuration by ticker."""
        return self.companies.get(ticker.upper())
    
    def get_all_metric_names(self) -> List[str]:
        """Get list of all metric names."""
        return list(self.metrics.keys())
    
    def get_universal_metrics(self) -> List[str]:
        """Get metrics marked as universal."""
        return [name for name, m in self.metrics.items() if m.universal]
    
    def get_excluded_metrics_for_company(self, ticker: str) -> List[str]:
        """Get all excluded metrics for a company (company-specific + industry).
        
        Combines:
        1. Company-specific excludes from company config
        2. Industry-based excludes from defaults.industry_exclusions
        
        Args:
            ticker: Company ticker (e.g., 'JPM')
            
        Returns:
            List of metric names to exclude for this company
        """
        company = self.get_company(ticker)
        excluded = set()
        
        # Company-specific exclusions (from company config)
        if company and company.exclude_metrics:
            excluded.update(company.exclude_metrics)
        
        # Industry-based exclusions (from defaults)
        if company and company.industry:
            industry_exclusions = self.defaults.get('industry_exclusions', {})
            industry_metrics = industry_exclusions.get(company.industry, [])
            excluded.update(industry_metrics)
        
        return list(excluded)


class ConfigLoader:
    """Loads configuration from YAML files."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            # Default to config/ directory relative to this file
            config_dir = Path(__file__).parent / "config"
        self.config_dir = Path(config_dir)
    
    def load(self) -> MappingConfig:
        """Load complete configuration."""
        metrics_data = self._load_yaml("metrics.yaml")
        companies_data = self._load_yaml("companies.yaml")
        
        # Parse metrics
        metrics = {}
        for name, data in metrics_data.get("metrics", {}).items():
            metrics[name] = MetricConfig(
                name=name,
                description=data.get("description", ""),
                known_concepts=data.get("known_concepts", []),
                tree_hints=data.get("tree_hints", {}),
                universal=data.get("universal", False),
                notes=data.get("notes"),
                dimensional_handling=data.get("dimensional_handling")
            )
        
        # Parse companies
        companies = {}
        for ticker, data in companies_data.get("companies", {}).items():
            companies[ticker] = CompanyConfig(
                ticker=ticker,
                name=data.get("name", ""),
                cik=data.get("cik", 0),
                legacy_ciks=data.get("legacy_ciks", []),
                exclude_metrics=data.get("exclude_metrics", []),
                metric_overrides=data.get("metric_overrides", {}),
                notes=data.get("notes"),
                fiscal_year_end=data.get("fiscal_year_end", "December"),
                industry=data.get("industry"),
                validation_tolerance_pct=data.get("validation_tolerance_pct")
            )
        
        # Get defaults
        defaults = companies_data.get("defaults", {
            "confidence_thresholds": {
                "tree_high": 0.95,
                "tree_medium": 0.80,
                "ai_high": 0.90,
                "ai_medium": 0.70
            },
            "fallback_chain": ["tree_parser", "ai_semantic", "temporal", "manual"]
        })
        
        return MappingConfig(
            version=metrics_data.get("version", "1.0.0"),
            metrics=metrics,
            companies=companies,
            defaults=defaults
        )
    
    def _load_yaml(self, filename: str) -> Dict:
        """Load a YAML file."""
        path = self.config_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        
        with open(path, 'r') as f:
            return yaml.safe_load(f) or {}


# Singleton instance for easy access
_config: Optional[MappingConfig] = None


def get_config(reload: bool = False) -> MappingConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None or reload:
        _config = ConfigLoader().load()
    return _config


def get_known_concepts(metric: str) -> List[str]:
    """Quick helper to get known concepts for a metric."""
    config = get_config()
    m = config.get_metric(metric)
    return m.known_concepts if m else []
