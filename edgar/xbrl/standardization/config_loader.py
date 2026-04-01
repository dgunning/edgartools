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
    
    def get_excluded_metrics_for_company(self, ticker: str) -> Dict[str, Dict[str, str]]:
        """Get all excluded metrics for a company (company-specific + industry).

        Combines:
        1. Industry-based excludes (always reason=not_applicable)
        2. Company-specific excludes (override industry if present)

        Args:
            ticker: Company ticker (e.g., 'JPM')

        Returns:
            Dict mapping metric name -> {"reason": "...", "notes": "..."}
        """
        result: Dict[str, Dict[str, str]] = {}
        company = self.get_company(ticker)

        # Get industry - auto-detect from SIC or use manual config
        industry = self._get_industry_for_company(ticker, company)

        # Industry-based exclusions (always not_applicable)
        if industry:
            industry_exclusions = self.defaults.get('industry_exclusions', {})
            for metric in industry_exclusions.get(industry, []):
                result[metric] = {"reason": "not_applicable", "notes": f"Industry exclusion ({industry})"}

        # Company-specific exclusions (override industry if present)
        if company and company.exclude_metrics:
            result.update(company.exclude_metrics)

        return result
    
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
            # Handle both legacy list and new dict format for exclude_metrics
            raw_excludes = data.get("exclude_metrics", {})
            if isinstance(raw_excludes, list):
                # Auto-convert legacy list format → dict with not_applicable default
                exclude_metrics = {m: {"reason": "not_applicable", "notes": ""} for m in raw_excludes}
            else:
                exclude_metrics = raw_excludes or {}

            companies[ticker] = CompanyConfig(
                ticker=ticker,
                name=data.get("name", ""),
                cik=data.get("cik", 0),
                legacy_ciks=data.get("legacy_ciks", []),
                exclude_metrics=exclude_metrics,
                metric_overrides=data.get("metric_overrides", {}),
                known_divergences=data.get("known_divergences", {}),
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


@dataclass
class DataDictionaryEntry:
    """A single entry in the data dictionary."""
    name: str
    display_name: str
    description: str
    statement_family: str
    unit: str
    sign_convention: str
    metric_tier: str  # "headline" | "secondary" | "derived"
    source_concepts: List[str] = field(default_factory=list)
    composite_formula: Optional[str] = None
    exclusions: List[str] = field(default_factory=list)


# Singleton instance for data dictionary
_data_dictionary: Optional[Dict[str, DataDictionaryEntry]] = None


def load_data_dictionary(reload: bool = False) -> Dict[str, DataDictionaryEntry]:
    """
    Load the data dictionary from config/data_dictionary.yaml.

    Returns a dict mapping metric name -> DataDictionaryEntry.
    Cached after first load.
    """
    global _data_dictionary
    if _data_dictionary is not None and not reload:
        return _data_dictionary

    dict_path = Path(__file__).parent / "config" / "data_dictionary.yaml"
    if not dict_path.exists():
        log.warning(f"Data dictionary not found at {dict_path}")
        return {}

    with open(dict_path, 'r') as f:
        raw = yaml.safe_load(f)

    entries = {}
    for name, defn in raw.get("metrics", {}).items():
        entries[name] = DataDictionaryEntry(
            name=name,
            display_name=defn.get("display_name", name),
            description=defn.get("description", ""),
            statement_family=defn.get("statement_family", ""),
            unit=defn.get("unit", "USD"),
            sign_convention=defn.get("sign_convention", "positive"),
            metric_tier=defn.get("metric_tier", "secondary"),
            source_concepts=defn.get("source_concepts", []),
            composite_formula=defn.get("composite_formula"),
            exclusions=defn.get("exclusions", []),
        )

    _data_dictionary = entries
    log.info(f"Loaded data dictionary: {len(entries)} metrics")
    return entries
