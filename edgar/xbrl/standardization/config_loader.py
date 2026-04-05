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

# Cache for industry_metrics.yaml (loaded once per process)
_industry_metrics_cache: Optional[dict] = None


def _load_industry_metrics() -> dict:
    """Load industry_metrics.yaml with module-level caching."""
    global _industry_metrics_cache
    if _industry_metrics_cache is not None:
        return _industry_metrics_cache

    path = Path(__file__).parent / "config" / "industry_metrics.yaml"
    if not path.exists():
        _industry_metrics_cache = {}
        return _industry_metrics_cache

    with open(path, 'r') as f:
        _industry_metrics_cache = yaml.safe_load(f) or {}
    return _industry_metrics_cache



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
    
    def get_excluded_metrics_for_company(self, ticker: str, *, network: bool = True) -> Dict[str, Dict[str, str]]:
        """Get all excluded metrics for a company (company-specific + industry).

        Combines (in priority order):
        1. industry_metrics.yaml forbidden_metrics (authoritative)
        2. Legacy defaults['industry_exclusions'] (backward compat)
        3. Company-specific excludes (override industry if present)

        Args:
            ticker: Company ticker (e.g., 'JPM')
            network: If False, skip SEC API auto-detection (for scoring hot path)

        Returns:
            Dict mapping metric name -> {"reason": "...", "notes": "..."}
        """
        result: Dict[str, Dict[str, str]] = {}
        company = self.get_company(ticker)

        # Get industry - auto-detect from SIC or use manual config
        industry = self._get_industry_for_company(ticker, company, network=network)

        if industry:
            # Primary: industry_metrics.yaml forbidden_metrics (unified authority)
            industry_metrics = _load_industry_metrics()
            forbidden = industry_metrics.get(industry, {}).get("forbidden_metrics", [])
            for metric in forbidden:
                result[metric] = {"reason": "not_applicable", "notes": f"Industry exclusion ({industry})"}

            # Legacy fallback: defaults['industry_exclusions'] (for categories not yet in industry_metrics.yaml)
            industry_exclusions = self.defaults.get('industry_exclusions', {})
            for metric in industry_exclusions.get(industry, []):
                if metric not in result:
                    result[metric] = {"reason": "not_applicable", "notes": f"Industry exclusion ({industry})"}

        # Company-specific exclusions (override industry if present)
        if company and company.exclude_metrics:
            result.update(company.exclude_metrics)

        return result
    
    def _get_industry_for_company(self, ticker: str, company: Optional[CompanyConfig] = None, *, network: bool = True) -> Optional[str]:
        """Get industry for a company from YAML config or SEC SIC auto-detection.

        Priority:
        1. companies.yaml industry field (authoritative)
        2. Auto-detect from SEC SIC code (requires network — last resort, skipped when network=False)

        Args:
            network: If False, skip SEC API auto-detection. Use for scoring hot paths
                     where speed matters and all known companies are in companies.yaml.
        """
        # Check YAML config (authoritative source after migration)
        if company and company.industry:
            return company.industry

        if not network:
            return None

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
                importance_tier=data.get("importance_tier", "exploratory"),
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
                validation_tolerance_pct=data.get("validation_tolerance_pct"),
                quality_tier=data.get("quality_tier"),
            )
        
        # Load per-company JSON overrides (replaces former Phase 10/11 Python overrides)
        self._load_company_overrides(companies)

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
    
    def _load_company_overrides(self, companies: Dict[str, CompanyConfig]):
        """Load per-company JSON overrides from config/company_overrides/.

        Each file is {ticker}.json with optional keys:
        - known_divergences: merged into CompanyConfig.known_divergences
        - exclude_metrics: merged into CompanyConfig.exclude_metrics
        - metric_overrides: merged into CompanyConfig.metric_overrides
        - quality_tier: sets CompanyConfig.quality_tier

        JSON overrides replace former Python override functions for WSL persistence.
        """
        overrides_dir = self.config_dir / "company_overrides"
        if not overrides_dir.exists():
            return

        for json_path in sorted(overrides_dir.glob("*.json")):
            ticker = json_path.stem.upper()
            cc = companies.get(ticker)
            if cc is None:
                # Create a minimal CompanyConfig for companies only in overrides
                cc = CompanyConfig(ticker=ticker, name="", cik=0)
                companies[ticker] = cc

            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                log.warning(f"Failed to load override {json_path}: {e}")
                continue

            # Merge known_divergences (don't overwrite existing)
            for metric, div in data.get("known_divergences", {}).items():
                if metric not in cc.known_divergences:
                    cc.known_divergences[metric] = div

            # Merge exclude_metrics (don't overwrite existing)
            for metric, exc in data.get("exclude_metrics", {}).items():
                if metric not in cc.exclude_metrics:
                    cc.exclude_metrics[metric] = exc

            # Merge metric_overrides (don't overwrite existing)
            for metric, ovr in data.get("metric_overrides", {}).items():
                if metric not in cc.metric_overrides:
                    cc.metric_overrides[metric] = ovr

            # Set quality_tier if not already set
            if data.get("quality_tier") and cc.quality_tier is None:
                cc.quality_tier = data["quality_tier"]

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
    known_limitations: Optional[str] = None
    reference_standard_notes: Optional[str] = None
    coverage_rate: Optional[float] = None


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
            known_limitations=defn.get("known_limitations"),
            reference_standard_notes=defn.get("reference_standard_notes"),
            coverage_rate=defn.get("coverage_rate"),
        )

    _data_dictionary = entries
    log.info(f"Loaded data dictionary: {len(entries)} metrics")
    return entries
