"""
Inline XBRL scale and sign conversion must not depend on the caller's Decimal context.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1854

``apply_scale`` used ``Decimal.scaleb`` and ``normalize``, and the sign path
used unary minus. All three round to the ambient context precision, so a caller
running under ``decimal.localcontext(prec=8)`` turned IBM's filed cover-page
count of 927,264,332 shares into 927,264,330.

Source: IBM 10-K for fiscal 2024, accession 0000051143-25-000015, filed
2025-02-25 (tracked fixture ``tests/fixtures/html/ibm/10k/ibm-10-k-2025-02-25.html``).
Fact f-113::

    <ix:nonFraction unitRef="shares" contextRef="c-32" decimals="INF"
      name="dei:EntityCommonStockSharesOutstanding" format="ixt:num-dot-decimal"
      scale="0" id="f-113">927,264,332</ix:nonFraction>
"""
from decimal import ROUND_HALF_EVEN, Context, localcontext
from pathlib import Path

import pytest

from edgar.documents import parse_html
from edgar.documents.strategies.ixbrl_transforms import apply_scale, negate_exactly

IBM_10K = Path(__file__).parents[2] / "fixtures" / "html" / "ibm" / "10k" / "ibm-10-k-2025-02-25.html"


def _ibm_shares_outstanding(precision: int):
    html = IBM_10K.read_text(encoding="utf-8")
    with localcontext(Context(prec=precision, rounding=ROUND_HALF_EVEN)):
        facts = parse_html(html).xbrl_facts
    return next(
        f for f in facts
        if f.concept == "dei:EntityCommonStockSharesOutstanding" and f.context_ref == "c-32"
    )


@pytest.mark.fast
def test_ibm_share_count_survives_reduced_caller_precision():
    fact = _ibm_shares_outstanding(precision=8)
    assert fact.value == "927264332"
    assert fact.numeric_value == 927264332.0
    assert fact.decimals == "INF"
    assert fact.unit_ref == "shares"


@pytest.mark.fast
@pytest.mark.parametrize("precision", [1, 3, 8])
def test_scale_and_sign_ignore_the_ambient_context(precision):
    with localcontext(Context(prec=precision, rounding=ROUND_HALF_EVEN)):
        assert apply_scale("927,264,332", "0") == "927264332"
        assert apply_scale("61,363", "6") == "61363000000"
        assert apply_scale("0.7", "-2") == "0.007"
        assert apply_scale("7.000", "-3") == "0.007"
        assert negate_exactly("927264332") == "-927264332"
        assert negate_exactly("-0.125") == "0.125"


@pytest.mark.fast
def test_non_numeric_input_is_rejected_even_without_the_invalid_operation_trap():
    # With the trap off, Decimal('abc') is NaN instead of an exception.
    with localcontext(Context(traps=[])):
        assert apply_scale("not a number", "3") is None
        assert negate_exactly("n/a") is None
