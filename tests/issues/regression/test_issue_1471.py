"""Regression: a decrease row is not folded into the increase row it shares a label with.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1471

Oracle's FY2026 10-K (0001193125-26-277521) rolls forward its gross unrecognized
tax benefits. The line "Cumulative translation adjustments and other, net" is an
INCREASE in fiscal 2026 and a DECREASE in fiscal 2025 and 2024, so the filer tags
the three facts with two concepts and presents the decrease concept with a
negated label:

    FY2026   22   UnrecognizedTaxBenefitsIncreasesResultingFromForeignCurrencyTranslation  (sign +1)
    FY2025  (11)  UnrecognizedTaxBenefitsDecreasesResultingFromForeignCurrencyTranslation  (sign -1)
    FY2024   (8)  UnrecognizedTaxBenefitsDecreasesResultingFromForeignCurrencyTranslation  (sign -1)

Both concepts carry one label, are non-dimensional, sit side by side, and report
different fiscal years, so `_merge_complementary_rows` (GH #572) took them for one
line item whose concept had been renamed. It copied the decrease values into the
increase row and dropped the decrease row, which kept only the increase concept
and the +1 sign of its single period. `Statement.to_dataframe(presentation=False)`
then reported FY2025 and FY2024 as increases with `preferred_sign` 1.

The merge now also requires the two rows to be shown with the same sign, on the
assumption that a rename keeps the direction of the line item it renames. Nothing
in the fixture corpus tests that assumption; Oracle is the only cross-concept
merge known. A merge that is skipped leaves two rows with one label and loses no
value. When rows do merge, the second row's `preferred_signs` now travel with its
values, so a negated row keeps its -1 in every period.

Ground truth is the filed table (Note on income taxes, in millions): 22, (11), (8).
"""

import pandas as pd
import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.statements import _display_signs, _merge_complementary_rows

# Oracle's FY2026 10-K. Its linkbases are embedded in the schema, so the schema
# and the instance document are the whole XBRL; fetching just those two (9.5 MB)
# loads the same 91 roles and 2,195 facts as `filing.xbrl()` does from the 29 MB
# full submission, and keeps the cassette to a third of the size.
ORCL_10K_FOLDER = "https://www.sec.gov/Archives/edgar/data/1341439/000119312526277521/"
ORCL_10K_XBRL_FILES = ("orcl-20260531.xsd", "orcl-20260531_htm.xml")
ROLE = "http://www.oracle.com/20260531/taxonomy/role/Role_DisclosureINCOMETAXESGrossUnrecognizedTaxBenefitsIncludingAcquisitionsDetails"
LABEL = "Cumulative translation adjustments and other, net"
INCREASES = "us-gaap_UnrecognizedTaxBenefitsIncreasesResultingFromForeignCurrencyTranslation"
DECREASES = "us-gaap_UnrecognizedTaxBenefitsDecreasesResultingFromForeignCurrencyTranslation"

FY2026 = "duration_2025-06-01_2026-05-31"
FY2025 = "duration_2024-06-01_2025-05-31"
FY2024 = "duration_2023-06-01_2024-05-31"


@pytest.mark.vcr
def test_oracle_keeps_its_increase_and_decrease_rows_apart(tmp_path):
    """Ground truth: Oracle FY2026 10-K, 0001193125-26-277521, income taxes note."""
    for name in ORCL_10K_XBRL_FILES:
        (tmp_path / name).write_text(download_file(ORCL_10K_FOLDER + name), encoding="utf-8")
    xbrl = XBRL.from_directory(tmp_path)
    statement = xbrl.statements[ROLE]

    # Nothing in this role is a rename, so nothing may be merged away.
    assert len(statement.get_raw_data()) == len(xbrl.get_statement(ROLE))

    rows = [r for r in statement.get_raw_data() if r["label"] == LABEL]
    assert [r["concept"] for r in rows] == [INCREASES, DECREASES]

    increases, decreases = rows
    assert increases["values"] == {FY2026: 22_000_000.0}
    assert increases["preferred_signs"] == {FY2026: 1}
    assert decreases["values"] == {FY2025: 11_000_000.0, FY2024: 8_000_000.0}
    assert decreases["preferred_signs"] == {FY2025: -1, FY2024: -1}

    # The export the report was filed against: raw values, no presentation sign.
    df = statement.to_dataframe(standard=False, view="detailed", presentation=False)
    exported = df[df["label"] == LABEL].set_index("concept")
    assert list(exported.index) == [INCREASES, DECREASES]
    assert exported["preferred_sign"].to_dict() == {INCREASES: 1, DECREASES: -1}

    fy2026, fy2025, fy2024 = "2026-05-31 (FY)", "2025-05-31 (FY)", "2024-05-31 (FY)"
    assert exported.loc[INCREASES, fy2026] == 22_000_000.0
    assert exported.loc[DECREASES, [fy2025, fy2024]].tolist() == [11_000_000.0, 8_000_000.0]
    assert exported.loc[INCREASES, [fy2025, fy2024]].isna().all()
    assert pd.isna(exported.loc[DECREASES, fy2026])


def _row(concept, values, sign):
    """A statement row shaped like `XBRL.get_statement` output, reduced to what the merge reads.

    ``sign=None`` leaves ``preferred_signs`` empty, which is what a row with no
    preferredLabel carries.
    """
    return {
        "concept": concept,
        "label": LABEL,
        "level": 2,
        "is_abstract": False,
        "is_dimension": False,
        "values": dict(values),
        "units": {key: "usd" for key in values},
        "period_types": {key: "duration" for key in values},
        "preferred_signs": {key: sign for key in values} if sign is not None else {},
    }


@pytest.mark.parametrize(
    "increase_sign, decrease_first",
    [(1, False), (None, False), (1, True)],
    ids=["increase-first", "increase-row-has-no-signs", "decrease-first"],
)
def test_an_increase_and_a_decrease_are_not_merged(increase_sign, decrease_first):
    """The report in miniature: complementary periods, one label, opposite signs.

    The empty-signs case is the common real shape (a row with no preferredLabel);
    the reversed case checks that the order of the two rows does not matter.
    """
    increase = _row(INCREASES, {FY2026: 22.0}, increase_sign)
    decrease = _row(DECREASES, {FY2025: 11.0, FY2024: 8.0}, -1)
    rows = [decrease, increase] if decrease_first else [increase, decrease]

    merged = {r["concept"]: r for r in _merge_complementary_rows(rows)}

    assert list(merged) == [r["concept"] for r in rows]
    assert merged[INCREASES]["values"] == {FY2026: 22.0}
    assert merged[INCREASES]["preferred_signs"] == ({FY2026: 1} if increase_sign else {})
    assert merged[DECREASES]["values"] == {FY2025: 11.0, FY2024: 8.0}
    assert merged[DECREASES]["preferred_signs"] == {FY2025: -1, FY2024: -1}


@pytest.mark.parametrize("sign", [1, -1])
def test_a_same_direction_concept_rename_still_merges(sign):
    """
    The control. A guard that refused every cross-concept merge would pass the
    test above, so this pins the case `_merge_complementary_rows` exists for
    (GH #572): one line item, tagged with a company extension in the older years
    and a us-gaap concept in the newer, both shown with the same sign.

    It also pins that the sign travels with the values: the merged row used to
    keep only the first row's per-period signs, so a negated row lost its -1 for
    every period that came from the second.
    """
    rows = [
        _row("us-gaap_NewConcept", {FY2026: 22.0}, sign),
        _row("orcl_OldConcept", {FY2025: 11.0, FY2024: 8.0}, sign),
    ]

    merged = _merge_complementary_rows(rows)

    assert len(merged) == 1
    assert merged[0]["concept"] == "us-gaap_NewConcept"
    assert merged[0]["values"] == {FY2026: 22.0, FY2025: 11.0, FY2024: 8.0}
    assert merged[0]["preferred_signs"] == {FY2026: sign, FY2025: sign, FY2024: sign}


def test_display_signs():
    assert _display_signs({"values": {"a": 1.0}, "preferred_signs": {"a": -1}}) == {-1}
    # A row with no preferredLabel (missing, None or 0) is shown as filed, which is +1.
    for signs in ({}, {"a": None}, {"a": 0}):
        assert _display_signs({"values": {"a": 1.0}, "preferred_signs": signs}) == {1}
    assert _display_signs({"values": {"a": 1.0}}) == {1}
