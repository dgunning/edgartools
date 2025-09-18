"""
Fund data models.

This package contains all the data models used for fund reporting,
separated by functional area for better maintainability.
"""

# Import all derivative models for convenience
from edgar.funds.models.derivatives import (
    DerivativeInfo,
    ForwardDerivative,
    FutureDerivative,
    OptionDerivative,
    SwapDerivative,
    SwaptionDerivative,
)

__all__ = [
    # Derivative models
    'DerivativeInfo',
    'ForwardDerivative',
    'SwapDerivative',
    'FutureDerivative',
    'SwaptionDerivative',
    'OptionDerivative',
]