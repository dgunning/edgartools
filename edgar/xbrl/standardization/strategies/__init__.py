"""
Strategy Registry for XBRL Metric Extraction

This module provides the central registry for all extraction strategies.
Strategies are registered by name and can be retrieved via get_strategy().

Usage:
    from edgar.xbrl.standardization.strategies import get_strategy, list_strategies

    # Get a specific strategy
    strategy = get_strategy('commercial_debt')

    # List all registered strategies
    for name in list_strategies():
        print(name)
"""

from typing import Dict, List, Optional, Type, Any
from .base import BaseStrategy, StrategyResult, ExtractionMode, ExtractionMethod, FactHelper

# Strategy registry
_STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {}


def register_strategy(cls: Type[BaseStrategy]) -> Type[BaseStrategy]:
    """
    Decorator to register a strategy class.

    Usage:
        @register_strategy
        class MyStrategy(BaseStrategy):
            strategy_name = "my_strategy"
            ...
    """
    if not hasattr(cls, 'strategy_name') or not cls.strategy_name:
        raise ValueError(f"Strategy class {cls.__name__} must define strategy_name")

    _STRATEGY_REGISTRY[cls.strategy_name] = cls
    return cls


def get_strategy(
    name: str,
    params: Optional[Dict[str, Any]] = None
) -> BaseStrategy:
    """
    Get a strategy instance by name.

    Args:
        name: Strategy name (e.g., 'commercial_debt', 'dealer_debt')
        params: Optional parameters to pass to strategy constructor

    Returns:
        Instantiated strategy object

    Raises:
        KeyError: If strategy name is not registered
    """
    if name not in _STRATEGY_REGISTRY:
        available = ', '.join(_STRATEGY_REGISTRY.keys())
        raise KeyError(f"Unknown strategy '{name}'. Available: {available}")

    strategy_cls = _STRATEGY_REGISTRY[name]
    return strategy_cls(params=params)


def list_strategies() -> List[str]:
    """
    List all registered strategy names.

    Returns:
        List of strategy names
    """
    return list(_STRATEGY_REGISTRY.keys())


def get_strategies_for_metric(metric_name: str) -> List[str]:
    """
    Get all strategies that extract a specific metric.

    Args:
        metric_name: Metric name (e.g., 'ShortTermDebt')

    Returns:
        List of strategy names that extract this metric
    """
    return [
        name for name, cls in _STRATEGY_REGISTRY.items()
        if cls.metric_name == metric_name
    ]


# Import debt strategies to trigger registration
# These imports are at the bottom to avoid circular imports
try:
    from .debt import (
        CommercialDebtStrategy,
        DealerDebtStrategy,
        CustodialDebtStrategy,
        HybridDebtStrategy,
        StandardDebtStrategy,
    )
except ImportError:
    # Strategies not yet created - this is fine during initial setup
    pass


__all__ = [
    # Base classes
    'BaseStrategy',
    'StrategyResult',
    'ExtractionMode',
    'ExtractionMethod',
    'FactHelper',
    # Registry functions
    'register_strategy',
    'get_strategy',
    'list_strategies',
    'get_strategies_for_metric',
]
