"""Statement.validate(level="detailed") promised line-item rollups it never ran.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1739

``ValidationLevel.DETAILED`` was documented as "All line items roll up to
subtotals" and ``Statement.validate`` as "Full line-item rollup validation",
but ``validate_balance_sheet`` has no detailed branch: it runs the same
fundamental-equation and section-total checks as ``sections``. The
documentation now says so; the argument and its results are unchanged.

Ground truth: IBM 10-K for fiscal 2024, accession 0000051143-25-000015
(fixture tests/fixtures/xbrl/ibm/10k_2024). At 2024-12-31 total assets
(f-394) and total liabilities and equity (f-448) are both $137,175M, total
liabilities (f-422) $109,783M and current assets (f-368) $34,482M.
"""
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.statements import Statement
from edgar.xbrl.validation import ValidationLevel, validate_balance_sheet

pytestmark = pytest.mark.fast


@pytest.fixture(scope="module")
def balance_sheet():
    return XBRL.from_directory(Path("tests/fixtures/xbrl/ibm/10k_2024")).statements.balance_sheet()


def test_detailed_runs_the_section_checks(balance_sheet):
    sections = balance_sheet.validate(level="sections")
    detailed = balance_sheet.validate(level="detailed")
    assert detailed.checks_performed == sections.checks_performed == ["fundamental_equation", "section_totals"]
    assert detailed.is_valid is True
    assert detailed.issues == sections.issues == []
    assert detailed.metadata == sections.metadata
    assert detailed.metadata["liab_equity_check"]["assets"] == 137_175_000_000
    assert detailed.metadata["liab_equity_check"]["liabilities_and_equity"] == 137_175_000_000
    assert detailed.metadata["extracted_values"]["total_liabilities"] == 109_783_000_000
    assert detailed.metadata["extracted_values"]["current_assets"] == 34_482_000_000


def test_documentation_describes_what_detailed_runs():
    for doc in (Statement.validate.__doc__, validate_balance_sheet.__doc__):
        assert "rollup validation" not in doc
        assert "line-item rollups to subtotals are not implemented" in " ".join(doc.split())


def test_enum_value_is_kept():
    assert ValidationLevel("detailed") is ValidationLevel.DETAILED
