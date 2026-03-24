"""
Configuration loader for the concept mapping system.

Loads and validates metrics.yaml and companies.yaml configurations.
"""

import json
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

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
        2. Industry-based excludes (auto-detected from SEC SIC code, or manual fallback)
        
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
        
        # Get industry - auto-detect from SIC or use manual config
        industry = self._get_industry_for_company(ticker, company)
        
        # Industry-based exclusions
        if industry:
            industry_exclusions = self.defaults.get('industry_exclusions', {})
            industry_metrics = industry_exclusions.get(industry, [])
            excluded.update(industry_metrics)
        
        return list(excluded)
    
    def _get_industry_for_company(self, ticker: str, company: Optional[CompanyConfig] = None) -> Optional[str]:
        """Get industry for a company, preferring manual config over network calls.

        Priority:
        1. Manual industry from company config (no network)
        2. Auto-detect from SEC SIC code (requires network)
        """
        # Check manual config first — avoids unnecessary network calls
        if company and company.industry:
            return company.industry

        # Fall through to SEC API auto-detection
        try:
            from edgar import Company
            from edgar.entity.mappings_loader import get_industry_for_sic

            c = Company(ticker)
            sic = c.data.sic
            if sic:
                industry = get_industry_for_sic(sic)
                if industry:
                    return industry
        except Exception:
            pass

        return None


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
            # Normalize standard_tag: string -> list, missing -> empty list
            raw_tag = data.get("standard_tag", [])
            if isinstance(raw_tag, str):
                raw_tag = [raw_tag]

            metrics[name] = MetricConfig(
                name=name,
                description=data.get("description", ""),
                known_concepts=data.get("known_concepts", []),
                tree_hints=data.get("tree_hints", {}),
                universal=data.get("universal", False),
                notes=data.get("notes"),
                dimensional_handling=data.get("dimensional_handling"),
                exclude_patterns=data.get("exclude_patterns", []),
                composite=data.get("composite", False),
                components=data.get("components", []),
                standard_tag=raw_tag,
                validation_tolerance=data.get("validation_tolerance"),
                standardization=data.get("standardization"),
                known_variances=data.get("known_variances"),
                sign_convention=data.get("sign_convention"),
            )

        # Expand known_concepts using upstream GAAP mappings
        gaap_index = self._load_gaap_mappings()
        if gaap_index:
            self._expand_known_concepts(metrics, gaap_index)

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
    
    def _load_gaap_mappings(self) -> Dict[str, List[str]]:
        """Load upstream GAAP mappings and build a reverse index: standard_tag -> [gaap_concept, ...].

        Filters out:
        - Entries flagged as ambiguous
        - Entries flagged as deprecated
        - Entries with multiple standard_tags (same as ambiguous in practice)
        """
        path = self.config_dir / "upstream_gaap_mappings.json"
        if not path.exists():
            log.debug("upstream_gaap_mappings.json not found, skipping expansion")
            return {}

        with open(path, "r") as f:
            raw: Dict = json.load(f)

        # Build reverse index: standard_tag -> [gaap_concept_name, ...]
        index: Dict[str, List[str]] = {}
        for concept_name, entry in raw.items():
            tags = entry.get("standard_tags", [])
            if entry.get("ambiguous"):
                continue
            if entry.get("deprecated"):
                continue
            if len(tags) != 1:
                continue
            tag = tags[0]
            index.setdefault(tag, []).append(concept_name)

        log.debug("GAAP index: %d standard_tags, %d total concepts",
                   len(index), sum(len(v) for v in index.values()))
        return index

    def _expand_known_concepts(
        self,
        metrics: Dict[str, 'MetricConfig'],
        gaap_index: Dict[str, List[str]],
    ) -> None:
        """Expand each metric's known_concepts using the GAAP reverse index.

        For each metric that has a standard_tag:
        1. Look up all GAAP concepts for that tag
        2. Filter out concepts matching exclude_patterns
        3. Deduplicate against existing known_concepts
        4. Append new concepts after originals (preserving priority order)
        """
        for name, metric in metrics.items():
            if not metric.standard_tag:
                continue
            # Skip composite metrics — they use component-based extraction
            if metric.composite:
                continue

            existing = set(metric.known_concepts)
            new_concepts: List[str] = []

            for tag in metric.standard_tag:
                for concept in gaap_index.get(tag, []):
                    if concept in existing:
                        continue
                    # Apply exclude_patterns
                    if any(pat in concept for pat in metric.exclude_patterns):
                        continue
                    existing.add(concept)
                    new_concepts.append(concept)

            if new_concepts:
                metric.known_concepts = metric.known_concepts + new_concepts
                log.debug("%s: expanded by %d concepts (total %d)",
                          name, len(new_concepts), len(metric.known_concepts))

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
