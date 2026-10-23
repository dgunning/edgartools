"""The ``amendment-new-holdings`` recipe in the holdings skill listed a security twice.

``sharp-edges.yaml`` said "Correct current holdings is the UNION (114)" and built it with
``pd.concat([original.holdings, tf.holdings])``. ``.holdings`` is aggregated per filing
(36 rows for the original, 4 for the amendment), so the recipe returned 40 rows, not 114,
and Lennar CL B twice. The 114 is the entry count (110 + 4), which is ``len(.infotable)``.

The recipe now concatenates ``.infotable`` and groups on ``Cusip`` and ``PutCall``
(``.holdings`` keeps puts and calls apart, GH #824), giving one row per security. The
code is executed here, as written in the skill.

Ground truth: Berkshire Hathaway Q1 2025 (period 2025-03-31). 13F-HR 0000950123-25-005701
(filed 2025-05-15): 110 entries, tableValueTotal $258,701,144,516. 13F-HR/A NEW HOLDINGS
0000950123-25-008361 (filed 2025-08-14): 4 entries, $1,106,550,356. Lennar CL B
(CUSIP 526057302): 152,572 shares / $16,641,028 in the original and 202 shares /
$22,032 in the amendment, so 152,774 shares / $16,663,060 combined.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1715
"""
import pandas as pd
import pytest
import yaml

from edgar import Filing
from tests.paths import REPO_ROOT

SHARP_EDGES = REPO_ROOT / "edgar/ai/skills/holdings/sharp-edges.yaml"


def berkshire(form, filing_date, accession_no):
    return Filing(form=form, filing_date=filing_date, company="Berkshire Hathaway Inc",
                  cik=1067983, accession_no=accession_no)


def recipe():
    edges = yaml.safe_load(SHARP_EDGES.read_text(encoding="utf-8"))["sharp_edges"]
    return next(e["solution"] for e in edges if e["id"] == "amendment-new-holdings")


@pytest.mark.vcr
def test_issue_1715_new_holdings_union_has_one_row_per_security():
    original = berkshire("13F-HR", "2025-05-15", "0000950123-25-005701").obj()
    amendment_filing = berkshire("13F-HR/A", "2025-08-14", "0000950123-25-008361")
    assert (len(original.infotable), len(original.holdings)) == (110, 36)

    ns = {"pd": pd, "filing": amendment_filing, "original": original}
    exec(compile(recipe(), "sharp-edges.yaml", "exec"), ns)  # noqa: S102 - our own documentation
    tf, holdings = ns["tf"], ns["holdings"]

    assert tf.amendment_type == "NEW HOLDINGS"
    assert (len(tf.infotable), len(tf.holdings)) == (4, 4)
    assert len(ns["entries"]) == 114
    assert len(holdings) == 39
    assert holdings.groupby(["Cusip", "PutCall"]).size().max() == 1
    lennar = holdings[holdings["Cusip"] == "526057302"]
    assert lennar[["SharesPrnAmount", "Value"]].to_numpy().tolist() == [[152_774, 16_663_060]]
    # The recipe's old form: concatenating the aggregated frames
    old = pd.concat([original.holdings, tf.holdings])
    assert (len(old), old["Cusip"].nunique()) == (40, 39)
