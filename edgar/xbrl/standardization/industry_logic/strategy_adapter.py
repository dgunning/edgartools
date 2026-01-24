"""
Strategy Adapter

This module provides the adapter layer that bridges the new modular strategies
to the existing BankingExtractor interface, ensuring backward compatibility.

The adapter:
1. Converts company config to strategy parameters
2. Selects the appropriate strategy based on archetype
3. Converts StrategyResult back to ExtractedMetric

Usage:
    from edgar.xbrl.standardization.industry_logic.strategy_adapter import StrategyAdapter

    adapter = StrategyAdapter()
    result = adapter.extract_short_term_debt(xbrl, facts_df, ticker='JPM', mode='gaap')
"""

import logging
from typing import Any, Dict, Optional

from . import ExtractedMetric, ExtractionMethod

# Import strategies (lazy to avoid circular imports)
_strategies_loaded = False
_get_strategy = None
_ExtractionMode = None
_StrategyResult = None


def _ensure_strategies_loaded():
    """Lazy load strategies to avoid circular imports."""
    global _strategies_loaded, _get_strategy, _ExtractionMode, _StrategyResult

    if not _strategies_loaded:
        from ..strategies import get_strategy, ExtractionMode, StrategyResult
        _get_strategy = get_strategy
        _ExtractionMode = ExtractionMode
        _StrategyResult = StrategyResult
        _strategies_loaded = True


logger = logging.getLogger(__name__)


class StrategyAdapter:
    """
    Adapter that bridges new modular strategies to existing ExtractedMetric interface.

    This maintains backward compatibility while enabling the new strategy architecture.
    """

    # Archetype to strategy mapping
    ARCHETYPE_STRATEGIES = {
        'commercial': 'commercial_debt',
        'dealer': 'dealer_debt',
        'custodial': 'custodial_debt',
        'hybrid': 'hybrid_debt',
        'regional': 'commercial_debt',  # Regional uses commercial rules
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the adapter.

        Args:
            config_path: Optional path to companies.yaml for config loading
        """
        self.config_path = config_path
        self._company_configs = {}

    def extract_short_term_debt(
        self,
        xbrl: Any,
        facts_df: Any,
        ticker: str = None,
        mode: str = 'gaap',
        archetype: str = None,
    ) -> ExtractedMetric:
        """
        Extract ShortTermDebt using the appropriate strategy.

        Args:
            xbrl: XBRL object for linkbase access
            facts_df: DataFrame of XBRL facts
            ticker: Company ticker for config lookup
            mode: 'gaap' or 'street'
            archetype: Override archetype (if not using config)

        Returns:
            ExtractedMetric (backward compatible format)
        """
        _ensure_strategies_loaded()

        # Get company config and archetype
        config = self._get_company_config(ticker) if ticker else {}

        # Determine archetype
        if archetype is None:
            archetype = config.get('bank_archetype', 'commercial')

        # Get strategy name
        strategy_name = self.ARCHETYPE_STRATEGIES.get(archetype, 'commercial_debt')

        # Build strategy parameters from config
        params = self._build_strategy_params(ticker, config, archetype)

        # Get and execute strategy
        try:
            strategy = _get_strategy(strategy_name, params=params)

            # Map mode string to ExtractionMode enum
            extraction_mode = _ExtractionMode.GAAP if mode == 'gaap' else _ExtractionMode.STREET

            # Execute strategy (uses execute() to auto-inject fingerprint per ADR-005)
            result = strategy.execute(xbrl, facts_df, mode=extraction_mode)

            # Convert to ExtractedMetric
            return self._result_to_metric(result, archetype)

        except Exception as e:
            logger.warning(f"Strategy {strategy_name} failed for {ticker}: {e}")
            # Return empty metric on failure
            return ExtractedMetric(
                standard_name="ShortTermDebt",
                industry_counterpart=None,
                xbrl_concept=None,
                value=None,
                extraction_method=ExtractionMethod.DIRECT,
                notes=f"Strategy {strategy_name} failed: {str(e)}"
            )

    def _build_strategy_params(
        self,
        ticker: str,
        config: Dict[str, Any],
        archetype: str,
    ) -> Dict[str, Any]:
        """Build strategy parameters from company config."""
        params = {'ticker': ticker}

        # Get extraction_rules from config
        extraction_rules = config.get('extraction_rules', {})

        # Map extraction_rules to strategy params
        if archetype == 'commercial':
            params['subtract_repos_from_stb'] = extraction_rules.get('subtract_repos_from_stb', True)
            params['subtract_trading_from_stb'] = extraction_rules.get('subtract_trading_from_stb', True)
            params['safe_fallback'] = extraction_rules.get('safe_fallback', True)

        elif archetype == 'dealer':
            params['use_unsecured_stb'] = extraction_rules.get('use_unsecured_stb', True)
            params['safe_fallback'] = extraction_rules.get('safe_fallback', True)

        elif archetype == 'custodial':
            params['repos_as_debt'] = extraction_rules.get('repos_as_debt', False)
            params['safe_fallback'] = extraction_rules.get('safe_fallback', False)  # Never fuzzy!

        elif archetype == 'hybrid':
            params['subtract_repos_from_stb'] = extraction_rules.get('subtract_repos_from_stb', False)
            params['check_nesting'] = extraction_rules.get('check_nesting', True)
            params['safe_fallback'] = extraction_rules.get('safe_fallback', True)

        return params

    def _result_to_metric(
        self,
        result: Any,  # StrategyResult
        archetype: str,
    ) -> ExtractedMetric:
        """Convert StrategyResult to ExtractedMetric for backward compatibility."""
        # Map ExtractionMethod from strategy to industry_logic enum
        method_map = {
            'direct': ExtractionMethod.DIRECT,
            'composite': ExtractionMethod.COMPOSITE,
            'calculated': ExtractionMethod.CALCULATED,
            'mapped': ExtractionMethod.MAPPED,
            'fallback': ExtractionMethod.DIRECT,
        }

        method = method_map.get(result.method.value, ExtractionMethod.DIRECT)

        # ADR-005: Propagate strategy fingerprint in metadata
        result_metadata = result.metadata.copy() if result.metadata else {}
        if result.fingerprint:
            result_metadata['strategy_fingerprint'] = result.fingerprint

        return ExtractedMetric(
            standard_name="ShortTermDebt",
            industry_counterpart=f"ShortTermDebt_GAAP_{archetype.title()}",
            xbrl_concept=result.concept,
            value=result.value,
            extraction_method=method,
            notes=result.notes,
            metadata=result_metadata,
        )

    def _get_company_config(self, ticker: str) -> Dict[str, Any]:
        """Get company config from cache or load from YAML."""
        if ticker in self._company_configs:
            return self._company_configs[ticker]

        # Try to load from YAML
        try:
            import yaml
            from pathlib import Path

            if self.config_path:
                config_file = Path(self.config_path)
            else:
                config_file = Path(__file__).parent.parent / 'config' / 'companies.yaml'

            if config_file.exists():
                with open(config_file) as f:
                    config = yaml.safe_load(f)
                    companies = config.get('companies', {})
                    company_config = companies.get(ticker.upper(), {})
                    self._company_configs[ticker] = company_config
                    return company_config

        except Exception as e:
            logger.debug(f"Failed to load config for {ticker}: {e}")

        self._company_configs[ticker] = {}
        return {}

    def get_strategy_for_ticker(self, ticker: str) -> str:
        """Get the strategy name that would be used for a ticker."""
        config = self._get_company_config(ticker)
        archetype = config.get('bank_archetype', 'commercial')
        return self.ARCHETYPE_STRATEGIES.get(archetype, 'commercial_debt')


# Global adapter instance
_adapter = None


def get_adapter() -> StrategyAdapter:
    """Get or create global adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = StrategyAdapter()
    return _adapter


def extract_short_term_debt_via_strategy(
    xbrl: Any,
    facts_df: Any,
    ticker: str = None,
    mode: str = 'gaap',
    archetype: str = None,
) -> ExtractedMetric:
    """
    Convenience function for extracting short-term debt via the strategy adapter.

    This can be used as a drop-in replacement for direct extraction methods.
    """
    return get_adapter().extract_short_term_debt(
        xbrl, facts_df, ticker=ticker, mode=mode, archetype=archetype
    )
