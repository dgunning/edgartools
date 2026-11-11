"""Regression: "Non-accruing debt investment." is a non-accrual flag.

Bead: edgartools-tfhpl

The non-accrual pattern was ``non[- ]?accrual``, so the participle BlackRock's
three BDCs mark their schedules with never matched, and every BlackRock TCP
Capital, BlackRock Private Credit Fund and BlackRock Direct Lending filing read
``extraction_method`` ``'none'``. Across the latest 10-K or 10-Q of 179 active
BDCs this was 3 filings; each now reads its footnote.
"""
from decimal import Decimal

import pytest

from edgar.bdc.nonaccrual import _classify_nonaccrual_footnote


@pytest.mark.parametrize("text", [
    "Non-accruing debt investment.",
    "(C) Non-accruing debt investment.",
    "Investment is non-accruing as of December 31, 2025.",
])
def test_the_participle_is_a_flag(text):
    assert _classify_nonaccrual_footnote(text.lower(), linked_to_investments=True) is True


@pytest.mark.parametrize("text", [
    "There were no investments on non-accruing status as of December 31, 2025.",
    "The Company did not have any non-accruing investments.",
])
def test_a_denial_in_the_participle_is_still_a_denial(text):
    assert _classify_nonaccrual_footnote(text.lower(), linked_to_investments=True) is False


@pytest.mark.network
@pytest.mark.vcr
def test_blackrock_direct_lending_reads_its_non_accruing_footnote():
    """BlackRock Direct Lending Corp 10-Q for 2026-09-30 (0001193125-26-449587).

    The printed schedule marks Terraboost Media Operating Company's First Lien
    Term Loan "J" (Non-accruing debt investment.) at cost $1,352,218 and fair
    value $818,012.

    BlackRock TCP Capital's 10-K for 2025-12-31 (0001193125-26-079299) reads the
    same way, 18 rows and 3.6% (Thras.io Second Out at $14,161,458 marked "C");
    it states 4.0% counting preferred equity, which "C" does not mark. Its
    cassette would pass GitHub's 100 MB file limit.
    """
    from edgar import find
    from edgar.bdc.nonaccrual import extract_nonaccrual

    result = extract_nonaccrual(find('0001193125-26-449587'))
    assert result.extraction_method == 'footnote'
    terraboost = [inv for inv in result.investments if 'Terraboost Media Operating Company' in inv.identifier]
    assert len(terraboost) == 1
    assert terraboost[0].fair_value == Decimal('818012')
    assert terraboost[0].cost == Decimal('1352218')
    assert result.num_nonaccrual == 19
