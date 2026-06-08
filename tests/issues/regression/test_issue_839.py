"""
Regression test for GitHub Issue #839:

The standardized cash flow statement dropped the primary "Depreciation and
amortization" line for filers that tag it with ``us-gaap:OtherDepreciationAndAmortization``
instead of the common ``us-gaap:DepreciationDepletionAndAmortization``. For
Marvell (MRVL), ``Company("MRVL").cashflow_statement()`` had no canonical
"Depreciation and amortization" row; the value surfaced only under a stray
"Other Depreciation and Amortization" orphan row. The as-filed XBRL view was
correct, so the gap was purely in the EntityFacts standardization layer.

Root cause: ``OtherDepreciationAndAmortization`` was absent from
``EnhancedStatementBuilder.CONCEPT_NORMALIZATIONS``, so it never folded into the
canonical D&A concept and instead fell through to the orphan ("Additional Items")
collector.

Fix (edgar/entity/enhanced_statement.py):
  1. Map ``OtherDepreciationAndAmortization`` -> ``DepreciationAndAmortization``
     in ``CONCEPT_NORMALIZATIONS`` so it populates the canonical
     "Depreciation and amortization" line (the cash flow virtual tree's D&A node).
  2. In ``_add_orphan_facts``, skip an orphan whose normalized concept matches a
     canonical tree node *and* which resolved to the same fact the canonical row
     used — preventing a double row (the canonical line plus a leftover orphan /
     normalization-alias row). Filers reporting BOTH the canonical concept and
     ``OtherDepreciationAndAmortization`` keep their separate line, because the
     canonical row used a different fact.

The fold is naturally cash-flow-scoped: the income statement virtual tree has no
D&A node, so ``DepreciationAndAmortization`` is not a normalized target there and
``OtherDepreciationAndAmortization`` is left untouched on the income statement.

Cross-company survey (SEC XBRL frames, CY2022-CY2024): ~101 filers report
``OtherDepreciationAndAmortization`` with no canonical D&A total — including AMD,
Workday, Open Text, Elevance, MetLife, Crown Holdings, plus MRVL.
See docs/internal/analysis/issue-839-otherDA-survey.md.
"""

from datetime import date

import pytest

from edgar.entity.enhanced_statement import EnhancedStatementBuilder
from edgar.entity.models import FinancialFact


# ---------------------------------------------------------------------------
# Deterministic unit tests — no network
# ---------------------------------------------------------------------------

class TestConceptNormalization:
    """OtherDepreciationAndAmortization folds into the canonical D&A concept."""

    def test_normalization_entry_present(self):
        assert (
            EnhancedStatementBuilder.CONCEPT_NORMALIZATIONS.get("OtherDepreciationAndAmortization")
            == "DepreciationAndAmortization"
        )

    def test_normalize_concept_folds_other_da(self):
        builder = EnhancedStatementBuilder()
        assert builder._normalize_concept("OtherDepreciationAndAmortization") == "DepreciationAndAmortization"
        # Namespaced form normalizes identically.
        assert builder._normalize_concept("us-gaap:OtherDepreciationAndAmortization") == "DepreciationAndAmortization"


class TestXbrlStandardizationMapping:
    """The XBRL standardization layer (gaap_mappings.json) classifies
    OtherDepreciationAndAmortization as depreciation, not non-operating income.

    Before the fix it mapped to NonoperatingIncomeExpense ("Non-Operating Income
    (Expense)", confidence 0.5), so the standard_concept column on the XBRL cash
    flow statement misclassified the primary D&A line.
    """

    def test_maps_to_depreciation_expense(self):
        from edgar.xbrl.standardization.reverse_index import (
            get_display_name,
            get_standard_concept,
        )

        assert get_standard_concept("OtherDepreciationAndAmortization") == "DepreciationExpense"
        assert get_display_name("OtherDepreciationAndAmortization") == "Depreciation Expense"

    def test_matches_sibling_da_concepts(self):
        """It resolves to the same standard concept as the canonical D&A tags."""
        from edgar.xbrl.standardization.reverse_index import get_standard_concept

        target = get_standard_concept("DepreciationDepletionAndAmortization")
        assert target == "DepreciationExpense"
        assert get_standard_concept("OtherDepreciationAndAmortization") == target


def _fact(concept: str, label: str, value: float, year: int) -> FinancialFact:
    """Build a minimal annual (FY) cash-flow FinancialFact for the given year."""
    return FinancialFact(
        concept=f"us-gaap:{concept}",
        taxonomy="us-gaap",
        label=label,
        value=value,
        numeric_value=float(value),
        unit="USD",
        period_start=date(year, 1, 1),
        period_end=date(year, 12, 31),
        period_type="duration",
        fiscal_year=year,
        fiscal_period="FY",
        filing_date=date(year + 1, 2, 15),
        form_type="10-K",
        statement_type="CashFlowStatement",
    )


def _build_cashflow(concepts_by_year):
    facts = []
    for year, items in concepts_by_year.items():
        for concept, label, value in items:
            facts.append(_fact(concept, label, value, year))
    builder = EnhancedStatementBuilder()
    return builder.build_multi_period_statement(facts, "CashFlowStatement", periods=2, annual=True)


def _flatten(statement):
    rows = []

    def walk(items):
        for item in items:
            rows.append(item)
            if item.children:
                walk(item.children)

    walk(statement.items)
    return rows


# Filler concepts so each period clears the builder's >=5-facts threshold.
_FILLER = [
    ("NetIncomeLoss", "Net income", 1000.0),
    ("ShareBasedCompensation", "Stock-based compensation", 200.0),
    ("IncreaseDecreaseInAccountsReceivable", "Accounts receivable", -50.0),
    ("NetCashProvidedByUsedInOperatingActivities", "Cash from operations", 1500.0),
]


class TestCashFlowFoldBuilder:
    """End-to-end through the statement builder with synthetic facts (no network)."""

    def test_other_da_as_primary_folds_into_canonical(self):
        """MRVL-like: OtherDepreciationAndAmortization is the only D&A line."""
        data = {
            2024: _FILLER + [("OtherDepreciationAndAmortization", "Depreciation and amortization", 350.0)],
            2023: _FILLER + [("OtherDepreciationAndAmortization", "Depreciation and amortization", 300.0)],
        }
        rows = _flatten(_build_cashflow(data))

        # Exactly one canonical D&A row, carrying the OtherD&A values.
        canonical = [r for r in rows if r.concept == "DepreciationDepletionAndAmortization"]
        assert len(canonical) == 1
        assert canonical[0].label == "Depreciation and amortization"
        assert canonical[0].values["FY 2024"] == 350.0
        assert canonical[0].values["FY 2023"] == 300.0

        # No leftover orphan row and no normalization-alias row.
        concepts = [r.concept for r in rows]
        assert "OtherDepreciationAndAmortization" not in concepts
        assert "DepreciationAndAmortization" not in concepts

        # And the value is not displayed twice.
        da_value_rows = [
            r for r in rows
            if not r.is_abstract and r.values.get("FY 2024") == 350.0
        ]
        assert len(da_value_rows) == 1

    def test_fold_is_robust_to_duplicate_facts_in_period(self):
        """Two OtherD&A facts in one period (comparative filings) must not double up.

        Regression guard for the fact-map alias: if the normalized alias key
        pinned a different (older) fact than the raw concept key, the canonical
        row and a leftover orphan row would both render. _create_fact_map keeps
        the two keys on the same fact, so exactly one canonical row appears.
        """
        builder = EnhancedStatementBuilder()
        facts = []
        for year in (2024, 2023):
            facts.extend(_fact(c, l, v, year) for c, l, v in _FILLER)
            # Same concept, same period, two comparative filings with different
            # filing dates and (slightly) different values.
            old = _fact("OtherDepreciationAndAmortization", "Depreciation and amortization", 349.0, year)
            old.filing_date = date(year + 1, 2, 1)
            new = _fact("OtherDepreciationAndAmortization", "Depreciation and amortization", 350.0, year)
            new.filing_date = date(year + 1, 3, 1)
            facts.extend([old, new])

        rows = _flatten(builder.build_multi_period_statement(facts, "CashFlowStatement", periods=2, annual=True))

        canonical = [r for r in rows if r.concept == "DepreciationDepletionAndAmortization"]
        assert len(canonical) == 1
        # No orphan / alias duplicate rows for the same concept.
        assert "OtherDepreciationAndAmortization" not in [r.concept for r in rows]
        assert "DepreciationAndAmortization" not in [r.concept for r in rows]
        # The canonical value is displayed exactly once.
        da_rows = [r for r in rows if not r.is_abstract and r.values.get("FY 2024") in (349.0, 350.0)]
        assert len(da_rows) == 1

    def test_both_canonical_and_other_kept_separate(self):
        """Filer reporting both DDA (canonical) and OtherD&A keeps both lines."""
        data = {
            2024: _FILLER + [
                ("DepreciationDepletionAndAmortization", "Depreciation, depletion and amortization", 900.0),
                ("OtherDepreciationAndAmortization", "Other depreciation and amortization", 120.0),
            ],
            2023: _FILLER + [
                ("DepreciationDepletionAndAmortization", "Depreciation, depletion and amortization", 900.0),
                ("OtherDepreciationAndAmortization", "Other depreciation and amortization", 120.0),
            ],
        }
        rows = _flatten(_build_cashflow(data))

        # Canonical row shows the authentic DDA value, not the OtherD&A value.
        canonical = [r for r in rows if r.concept == "DepreciationDepletionAndAmortization"]
        assert len(canonical) == 1
        assert canonical[0].values["FY 2024"] == 900.0

        # OtherD&A remains a distinct line (no data loss).
        other = [r for r in rows if r.concept == "OtherDepreciationAndAmortization"]
        assert len(other) == 1
        assert other[0].values["FY 2024"] == 120.0


# ---------------------------------------------------------------------------
# Ground-truth end-to-end on the reported filing — network + VCR
# ---------------------------------------------------------------------------

@pytest.mark.network
@pytest.mark.vcr
def test_mrvl_cashflow_canonical_da_present():
    """Marvell's standardized cash flow exposes the canonical D&A line.

    Ground truth (MRVL 10-K filed 2026-03-11, Consolidated Statements of Cash
    Flows, "Depreciation and amortization", $M):
        FY2026 = 348.6   FY2025 = 304.3   FY2024 = 299.8
    """
    from edgar import Company

    df = Company("MRVL").cashflow_statement(periods=3).to_dataframe()

    canonical = df[
        df["label"].astype(str).str.fullmatch(r"(?i)depreciation and amortization", na=False)
    ]
    # The canonical "Depreciation and amortization" row is present (was absent before the fix).
    assert len(canonical) == 1

    period_cols = [c for c in df.columns if c.startswith("FY")]
    values = {round(v) for v in canonical.iloc[0][period_cols].dropna().tolist()}
    assert 348_600_000 in values  # FY2026
    assert 304_300_000 in values  # FY2025
    assert 299_800_000 in values  # FY2024

    # The value must not also appear under a stray "Other Depreciation and Amortization" row.
    other = df[df["label"].astype(str).str.fullmatch(r"(?i)other depreciation and amortization", na=False)]
    assert len(other) == 0
