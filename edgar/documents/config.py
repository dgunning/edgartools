"""
Configuration for the HTML parser.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ParserConfig:
    """
    Configuration for HTML parser.

    Attributes:
        max_document_size: Maximum document size in bytes
        streaming_threshold: Document size threshold for streaming mode
        cache_size: Maximum number of cached items
        enable_parallel: Enable parallel processing for tables
        strict_mode: Fail on parsing errors vs. best effort
        extract_xbrl: Extract inline XBRL facts
        extract_styles: Extract and process CSS styles
        preserve_whitespace: Preserve original whitespace
        optimize_for_ai: Enable AI-specific optimizations
        max_token_estimation: Maximum estimated tokens for AI optimization
        features: Feature flags for optional functionality
    """

    # Performance settings
    max_document_size: int = 50 * 1024 * 1024  # 50MB
    streaming_threshold: int = 10 * 1024 * 1024  # 10MB
    cache_size: int = 1000
    enable_parallel: bool = True
    max_workers: Optional[int] = None  # None = use CPU count

    # Parsing settings
    strict_mode: bool = False
    extract_xbrl: bool = True
    extract_styles: bool = True
    preserve_whitespace: bool = False
    normalize_text: bool = True
    extract_links: bool = True
    extract_images: bool = False

    # AI optimization
    optimize_for_ai: bool = True
    max_token_estimation: int = 100_000
    chunk_size: int = 512
    chunk_overlap: int = 128

    # Table processing
    table_extraction: bool = True
    detect_table_types: bool = True
    extract_table_relationships: bool = True

    # Section detection
    detect_sections: bool = True
    section_patterns: Dict[str, List[str]] = field(default_factory=lambda: {
        'business': [
            r'item\s+1\.?\s*business',
            r'business\s+overview',
            r'our\s+business'
        ],
        'risk_factors': [
            r'item\s+1a\.?\s*risk\s+factors',
            r'risk\s+factors',
            r'factors\s+that\s+may\s+affect'
        ],
        'properties': [
            r'item\s+2\.?\s*properties',
            r'properties'
        ],
        'legal_proceedings': [
            r'item\s+3\.?\s*legal\s+proceedings',
            r'legal\s+proceedings',
            r'litigation'
        ],
        'mda': [
            r'item\s+7\.?\s*management\'?s?\s+discussion',
            r'md&a',
            r'management\'?s?\s+discussion\s+and\s+analysis'
        ],
        'financial_statements': [
            r'item\s+8\.?\s*financial\s+statements',
            r'consolidated\s+financial\s+statements',
            r'financial\s+statements'
        ]
    })

    # Feature flags
    features: Dict[str, bool] = field(default_factory=lambda: {
        'ml_header_detection': True,
        'semantic_analysis': True,
        'table_understanding': True,
        'xbrl_validation': True,
        'auto_section_detection': True,
        'smart_text_extraction': True,
        'footnote_linking': True,
        'cross_reference_resolution': True
    })

    # Header detection settings
    header_detection_threshold: float = 0.6  # Minimum confidence
    header_detection_methods: List[str] = field(default_factory=lambda: [
        'style',
        'pattern',
        'structural',
        'contextual'
    ])

    # Text extraction settings
    min_text_length: int = 10  # Minimum text length to keep
    merge_adjacent_nodes: bool = True
    merge_distance: int = 2  # Max distance between nodes to merge

    # Performance monitoring
    enable_profiling: bool = False
    log_performance: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'max_document_size': self.max_document_size,
            'streaming_threshold': self.streaming_threshold,
            'cache_size': self.cache_size,
            'enable_parallel': self.enable_parallel,
            'strict_mode': self.strict_mode,
            'extract_xbrl': self.extract_xbrl,
            'extract_styles': self.extract_styles,
            'preserve_whitespace': self.preserve_whitespace,
            'optimize_for_ai': self.optimize_for_ai,
            'features': self.features.copy()
        }

    @classmethod
    def for_performance(cls) -> 'ParserConfig':
        """Create config optimized for performance."""
        return cls(
            extract_styles=False,
            extract_xbrl=False,
            enable_parallel=True,
            cache_size=5000,
            features={
                'ml_header_detection': False,
                'semantic_analysis': False,
                'table_understanding': False,
                'xbrl_validation': False
            }
        )

    @classmethod
    def for_accuracy(cls) -> 'ParserConfig':
        """Create config optimized for accuracy."""
        return cls(
            strict_mode=True,
            extract_styles=True,
            extract_xbrl=True,
            enable_parallel=True,
            features={
                'ml_header_detection': True,
                'semantic_analysis': True,
                'table_understanding': True,
                'xbrl_validation': True,
                'auto_section_detection': True,
                'smart_text_extraction': True,
                'footnote_linking': True,
                'cross_reference_resolution': True
            }
        )

    @classmethod
    def for_ai(cls) -> 'ParserConfig':
        """Create config optimized for AI/LLM processing."""
        return cls(
            optimize_for_ai=True,
            extract_styles=False,
            extract_xbrl=True,
            normalize_text=True,
            merge_adjacent_nodes=True,
            features={
                'ml_header_detection': True,
                'semantic_analysis': True,
                'smart_text_extraction': True
            }
        )
