"""
Data models for the 3-layer concept mapping architecture.

This module defines the core data structures used throughout the mapping system:
- MappingResult: Output of mapping operations
- AuditLogEntry: Tracking for all mapping decisions
- MetricConfig: Loaded from metrics.yaml
- CompanyConfig: Loaded from companies.yaml
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import json


class MappingSource(Enum):
    """Source of a mapping decision."""
    TREE = "tree"           # Layer 1: Tree structure parser
    AI = "ai"               # Layer 2: AI semantic mapper
    TEMPORAL = "temporal"   # Layer 3: Temporal tracker
    MANUAL = "manual"       # Manual override
    CONFIG = "config"       # From known_concepts in config
    UNKNOWN = "unknown"     # Not mapped


class ConfidenceLevel(Enum):
    """Confidence levels for mapping decisions."""
    HIGH = "high"       # >= 0.95
    MEDIUM = "medium"   # >= 0.70
    LOW = "low"         # < 0.70
    NONE = "none"       # Not mapped


@dataclass
class MappingResult:
    """
    Result of a concept mapping operation.
    
    This is the primary output of the mapping system, containing
    the mapped concept, confidence, source, and audit trail.
    """
    metric: str                         # Target metric name (e.g., "Revenue")
    company: str                        # Company ticker
    fiscal_period: str                  # e.g., "2024-Q1" or "2024-FY"
    concept: Optional[str] = None       # XBRL concept if mapped
    value: Optional[float] = None       # Extracted value if available
    confidence: float = 0.0             # 0.0 - 1.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.NONE
    source: MappingSource = MappingSource.UNKNOWN
    reasoning: Optional[str] = None     # Explanation for the mapping
    tree_context: Optional[Dict] = None # Parent, siblings, weight from tree
    timestamp: datetime = field(default_factory=datetime.utcnow)
    version: str = "1.0.0"              # Config version used
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        d = asdict(self)
        d['confidence_level'] = self.confidence_level.value
        d['source'] = self.source.value
        d['timestamp'] = self.timestamp.isoformat()
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MappingResult':
        """Create from dictionary."""
        data['confidence_level'] = ConfidenceLevel(data.get('confidence_level', 'none'))
        data['source'] = MappingSource(data.get('source', 'unknown'))
        data['timestamp'] = datetime.fromisoformat(data.get('timestamp', datetime.utcnow().isoformat()))
        return cls(**data)
    
    @property
    def is_mapped(self) -> bool:
        """Check if this result has a valid mapping."""
        return self.concept is not None and self.confidence >= 0.7


@dataclass
class AuditLogEntry:
    """
    Audit log entry for tracking mapping decisions.
    
    This is append-only and provides a complete history of
    all mapping decisions for debugging and analysis.
    """
    timestamp: datetime
    company: str
    metric: str
    fiscal_period: str
    action: str                         # "mapped", "fallback", "override", "failed"
    concept: Optional[str]
    source: MappingSource
    confidence: float
    reasoning: Optional[str]
    version: str
    previous_concept: Optional[str] = None  # For tracking changes
    
    def to_json(self) -> str:
        """Convert to JSON line for append-only log."""
        d = {
            'timestamp': self.timestamp.isoformat(),
            'company': self.company,
            'metric': self.metric,
            'fiscal_period': self.fiscal_period,
            'action': self.action,
            'concept': self.concept,
            'source': self.source.value,
            'confidence': self.confidence,
            'reasoning': self.reasoning,
            'version': self.version,
            'previous_concept': self.previous_concept
        }
        return json.dumps(d)
    
    @classmethod
    def from_json(cls, line: str) -> 'AuditLogEntry':
        """Parse from JSON line."""
        d = json.loads(line)
        d['timestamp'] = datetime.fromisoformat(d['timestamp'])
        d['source'] = MappingSource(d['source'])
        return cls(**d)


@dataclass
class MetricConfig:
    """Configuration for a single metric from metrics.yaml."""
    name: str
    description: str
    known_concepts: List[str]
    tree_hints: Dict[str, Any] = field(default_factory=dict)
    universal: bool = False
    notes: Optional[str] = None
    
    def matches_concept(self, concept: str) -> bool:
        """Check if a concept matches this metric's known concepts."""
        # Strip namespace prefix
        clean = concept.replace('us-gaap:', '').replace('us-gaap_', '')
        return clean in self.known_concepts


@dataclass 
class CompanyConfig:
    """Configuration for a single company from companies.yaml."""
    ticker: str
    name: str
    cik: int
    legacy_ciks: List[int] = field(default_factory=list)
    exclude_metrics: List[str] = field(default_factory=list)
    metric_overrides: Dict[str, Dict] = field(default_factory=dict)
    notes: Optional[str] = None
    fiscal_year_end: str = "December"
    
    def should_skip_metric(self, metric: str) -> bool:
        """Check if a metric should be skipped for this company."""
        return metric in self.exclude_metrics


@dataclass
class MappingState:
    """
    Current state of mappings for a company-period combination.
    
    This is used by the orchestrator to track progress through layers.
    """
    company: str
    fiscal_period: str
    results: Dict[str, MappingResult] = field(default_factory=dict)
    layer_attempts: Dict[str, List[str]] = field(default_factory=dict)  # layer -> metrics attempted
    
    def get_unmapped_metrics(self, all_metrics: List[str]) -> List[str]:
        """Get list of metrics not yet successfully mapped."""
        return [m for m in all_metrics if m not in self.results or not self.results[m].is_mapped]
    
    def add_result(self, result: MappingResult):
        """Add or update a mapping result."""
        self.results[result.metric] = result
