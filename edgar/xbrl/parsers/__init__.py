"""
XBRL Parser Components.

This package provides specialized parser components for different aspects
of XBRL document processing. Each parser handles a specific responsibility
in the XBRL parsing workflow.
"""

from .base import BaseParser
from .calculation import CalculationParser
from .coordinator import XBRLParser
from .definition import DefinitionParser
from .instance import InstanceParser
from .labels import LabelsParser
from .presentation import PresentationParser
from .schema import SchemaParser

__all__ = [
    'BaseParser',
    'XBRLParser',
    'SchemaParser',
    'LabelsParser',
    'PresentationParser',
    'CalculationParser',
    'DefinitionParser',
    'InstanceParser',
]
