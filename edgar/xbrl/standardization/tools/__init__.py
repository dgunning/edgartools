"""
Tools for Concept Mapping

This package contains reusable tools for AI agents to use when static mapping fails.

Available Tools:
- discover_concepts: Search calc trees + facts for matching concepts
- check_fallback_quality: Verify a concept is semantically valid for a metric
- verify_mapping: Value comparison with consolidation checks
- learn_mappings: Auto-expand known_concepts from patterns
- resolve_gaps: Full gap resolution workflow with coverage comparison
"""

from .discover_concepts import discover_concepts, CandidateConcept, discover
from .check_fallback_quality import check_fallback_quality, QualityResult, check
from .verify_mapping import verify_mapping, MappingVerification, verify
from .learn_mappings import learn_mappings, LearningResult, learn
from .resolve_gaps import (
    resolve_all_gaps,
    calculate_coverage,
    generate_report,
    update_config,
    learn_patterns,
    resolve,
    CoverageStats,
    Resolution,
    ResolutionReport
)
from .onboard_company import (
    onboard_company,
    onboard_batch,
    detect_archetype,
    OnboardingResult,
    FailureDetail,
)
