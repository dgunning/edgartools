"""
Regression tests for edgartools-j7iz (GH #1206): `Statement.get_raw_data()`
merged two different concepts into one row, so a row reported another concept's
value and the real row was deleted.

The report blamed statement detail materialization. It is not there — the fault
is `_merge_complementary_rows`, which `get_raw_data()` applies on top of
`XBRL.get_statement()`. That function exists for a real case (GH #572: a company
switches XBRL concepts between years, producing two same-label rows with
complementary period values) and it matches rows on their LABEL, checking level
and dimension status but never concept identity.

For a DIMENSIONAL row the label is the MEMBER's label — "Cerner Corporation",
"Unfavorable investigation outcome, EU State Aid rules" — which every concept
broken down by that member shares. So the label says nothing about which line
item the row is, and matching on it merged unrelated concepts. Complementarity
was no protection either: an instant fact and a duration fact can never collide,
so the "no conflicting values" test passes trivially.

MEASURED over the 2,052 statements in the committed fixture corpus: 215 merges,
of which 213 combined two DIFFERENT concepts and every one of those was a
dimensional row. Not one non-dimensional row merged across concepts anywhere,
so the rename case the function was written for does not even occur here. After
the guards: 2 merges, both same-concept.

Two guards, because each is independently sufficient for a different reason:
  * a dimensional row must also match on concept, since its label is a member
    name and cannot identify a line item;
  * a row reporting instants and a row reporting durations are not two
    observations of one series whatever their labels say.

Ground truth is Apple's FY2022 10-K income-taxes note, on the EU State Aid
matter: two Irish subsidiaries, a $13.1B assessment, $12.7B outstanding. Before
the fix the SUBSIDIARY COUNT row carried the dollar amounts and the loss
contingency row was gone.
"""

import glob
from pathlib import Path

import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.statements import _period_kinds

AAPL_2022 = Path("tests/fixtures/xbrl/aapl/10k_2022")

EU_STATE_AID_LABEL = "Unfavorable investigation outcome, EU State Aid rules"
SUBSIDIARY_COUNT = "aapl_IncomeTaxContingencyNumberOfSubsidiaries"
POSSIBLE_LOSS = "us-gaap_LossContingencyEstimateOfPossibleLoss"

# AAPL FY2022 10-K, EU State Aid.
SUBSIDIARIES = 2.0
ASSESSMENT = 13_100_000_000.0
OUTSTANDING = 12_700_000_000.0


@pytest.fixture(scope="module")
def aapl_2022():
    return XBRL.from_directory(AAPL_2022)


@pytest.fixture(scope="module")
def eu_state_aid_rows(aapl_2022):
    role = next(
        r for r in aapl_2022.presentation_trees
        if r.endswith("IncomeTaxesAdditionalInformationDetails")
    )
    return [
        row for row in aapl_2022.statements[role].get_raw_data()
        if row.get("label") == EU_STATE_AID_LABEL
    ]


def test_a_count_does_not_absorb_a_dollar_amount(eu_state_aid_rows):
    """The subsidiary count carried $13.1B and $12.7B before the fix."""
    counts = [r for r in eu_state_aid_rows if r["concept"] == SUBSIDIARY_COUNT]
    assert len(counts) == 1

    values = counts[0]["values"]
    assert values == {"duration_2016-08-30_2016-08-30": SUBSIDIARIES}


def test_the_absorbed_row_is_not_deleted(eu_state_aid_rows):
    """
    The other half of the defect: the row whose values were stolen was dropped,
    so the assessment disappeared from the statement entirely.
    """
    losses = [r for r in eu_state_aid_rows if r["concept"] == POSSIBLE_LOSS]
    by_value = {
        key: value
        for row in losses
        for key, value in row["values"].items()
    }

    assert by_value["instant_2016-08-30"] == ASSESSMENT
    assert by_value["instant_2022-09-24"] == OUTSTANDING


def _load(directory):
    """Parse a fixture directory, or None if it is not a parseable filing."""
    try:
        return XBRL.from_directory(directory)
    except Exception:
        return None


def _raw_rows(xbrl, role):
    """The statement's rows, or an empty list if the role cannot be rendered.

    A role that fails to render is covered by its own tests; this sweep is only
    about rows that DO come back.
    """
    try:
        return xbrl.statements[role].get_raw_data()
    except Exception:
        return []


def test_no_dimensional_row_merges_across_concepts():
    """
    The corpus-wide invariant. 213 rows violated this before the fix; a single
    violation anywhere means a row is reporting another concept's number.
    """
    offenders = []
    for directory in sorted(set(glob.glob("tests/fixtures/xbrl/*/*"))):
        xbrl = _load(directory)
        if xbrl is None:
            continue
        for role in list(xbrl.presentation_trees):
            for row in _raw_rows(xbrl, role):
                # A merged row keeps its own concept but gains the other's
                # period kinds. A concept is either an instant or a duration
                # concept, never both, so a row reporting both kinds is the
                # signature of a row that absorbed another concept's facts.
                if row.get("is_dimension") and len(_period_kinds(row)) > 1:
                    offenders.append((directory, row.get("concept"), row.get("label")))

    assert offenders == []


def test_a_same_concept_merge_still_happens():
    """
    The control, and it has to be a real one: guards that simply switch the
    feature off would pass every test above. This is the only legitimate merge
    left in the corpus — one concept, one member, two complementary periods —
    and it must still combine into a single row.

    Golden Ally Holdings, Q3 2024 10-Q: payments to acquire an interest in the
    Global Election Services joint venture, $50,000 in June 2019 and $40,000 in
    December 2019, filed against two separate periods.
    """
    xbrl = XBRL.from_directory(Path("data/xbrl/datafiles/gahc"))
    role = next(
        r for r in xbrl.presentation_trees
        if r.endswith("EquityInvestmentsNarrativeDetails")
    )
    rows = [
        r for r in xbrl.statements[role].get_raw_data()
        if r.get("concept") == "us-gaap_PaymentsToAcquireInterestInJointVenture"
        and str(r.get("label", "")).startswith("Global Election")
    ]

    assert len(rows) == 1, "the two complementary rows should still merge into one"
    values = rows[0]["values"]
    assert values["duration_2019-06-14_2019-06-15"] == 50_000.0
    assert values["duration_2019-12-01_2019-12-17"] == 40_000.0


@pytest.mark.parametrize(
    "values, expected",
    [
        ({"instant_2022-09-24": 1.0}, {"instant"}),
        ({"duration_2021-09-26_2022-09-24": 1.0}, {"duration"}),
        ({"instant_2022-09-24": 1.0, "duration_2021-09-26_2022-09-24": 2.0},
         {"instant", "duration"}),
        ({}, set()),
        (None, set()),
    ],
)
def test_period_kinds(values, expected):
    assert _period_kinds({"values": values}) == expected


@pytest.mark.network
def test_the_reported_oracle_row():
    """
    The report's own repro: ORCL Q1 FY2024. The Cerner row for equity
    consideration transferred carried $18.6B, which is us-gaap:Goodwill.
    """
    from edgar import get_by_accession_number

    xbrl = get_by_accession_number("0000950170-23-047713").xbrl()
    role = (
        "http://www.oracle.com/20230831/taxonomy/role/"
        "Role_DisclosureACQUISITIONSNarrativeDetails"
    )
    rows = xbrl.statements[role].get_raw_data(view="detailed")

    concept = (
        "us-gaap_BusinessCombinationConsiderationTransferredEquityInterests"
        "IssuedAndIssuable"
    )
    cerner = [
        r for r in rows
        if r.get("concept") == concept and r.get("is_dimension")
    ]
    assert len(cerner) == 1
    # Only its own duration fact, and no instant key at all.
    assert cerner[0]["values"] == {"duration_2022-06-08_2022-06-08": 55_000_000.0}

    # Control: the real Goodwill row still carries the value.
    goodwill = [
        r for r in rows
        if r.get("concept") == "us-gaap_Goodwill" and not r.get("is_dimension")
    ]
    assert goodwill
    assert goodwill[0]["values"]["instant_2022-06-08"] == 18_600_000_000.0
