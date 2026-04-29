"""
Regression test: prevent duplicated revenue rows from additional income statement roots.

When revenue is promoted to the top-level income statement, some learned virtual trees also
contain RevenuesAbstract as an additional root. That extra root must not re-introduce
Revenues as a second row.
"""

from types import SimpleNamespace

import pytest

from edgar.entity.enhanced_statement import EnhancedStatementBuilder


def _collect_concepts(item, concepts):
    """Recursively collect concept names from a statement subtree."""
    concepts.append(item.concept)
    for child in item.children:
        _collect_concepts(child, concepts)


@pytest.mark.fast
def test_promoted_revenue_not_duplicated_with_additional_revenue_root():
    """Revenue should appear once even if RevenuesAbstract is also a root."""
    builder = EnhancedStatementBuilder()

    virtual_tree = {
        "nodes": {
            "IncomeStatementAbstract": {
                "concept": "IncomeStatementAbstract",
                "label": "Income Statement [Abstract]",
                "children": [],
                "is_abstract": True,
                "is_total": False,
                "occurrence_rate": 1.0,
            },
            "RevenuesAbstract": {
                "concept": "RevenuesAbstract",
                "label": "Revenues:",
                "children": ["Revenues"],
                "is_abstract": True,
                "is_total": False,
                "occurrence_rate": 0.35,
            },
            "Revenues": {
                "concept": "Revenues",
                "label": "Revenues",
                "children": [],
                "is_abstract": False,
                "is_total": False,
                "occurrence_rate": 0.35,
            },
        },
        "roots": ["IncomeStatementAbstract", "RevenuesAbstract"],
    }

    periods = ["FY 2025", "FY 2024"]
    period_maps = {
        "FY 2025": {
            "Revenues": SimpleNamespace(numeric_value=100.0, label="Revenues"),
        },
        "FY 2024": {
            "Revenues": SimpleNamespace(numeric_value=95.0, label="Revenues"),
        },
    }

    items = builder._build_with_promoted_concepts(
        virtual_tree=virtual_tree,
        period_maps=period_maps,
        periods=periods,
        statement_type="IncomeStatement",
    )

    concepts = []
    for item in items:
        _collect_concepts(item, concepts)

    assert concepts.count("Revenues") == 1
