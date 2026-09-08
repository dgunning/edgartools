"""
Regression tests for edgartools-jj77 / GH #1282: `FactQuery.to_dataframe()`
deleted a fact denominated in a different currency because its number matched.

`_deduplicate_facts` classified duplicates on

    ['concept', 'context_ref', 'value', 'decimals']

with no unit, so two facts that agreed on everything except their currency were
treated as one tagging of the same fact. XBRL 2.1 §4.10 requires unit equality
before numeric items can be called duplicates, and these fail it: Aebi Schmidt
reports a CHF 10,000,000 and a EUR 10,000,000 subordinated shareholder loan in
the same context, with different translated USD amounts elsewhere in the filing
that show they are separate observations.

The loss was invisible: `execute()` returned all four facts and only the frame
dropped two, with no error or warning.

THE OTHER HALF, which is why the fix adds `unit_ref` rather than removing the
deduplication. GH #769 put this policy in to collapse the genuinely repeated
physical tags a filer emits when one fact appears in both a statement and a
note. BorgWarner is the case that pins both requirements at once: four physical
tags carrying two currency observations must come back as two rows -- the
repeat of each currency collapsed, neither currency deleted.

Neither behaviour was reachable from the pre-existing corpus: frame row counts
were identical across all 33 filing directories before and after this change,
because none of them files one concept in two currencies. Both filings are
therefore checked in as full, unmodified filed instances.
"""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL

AEBI = Path("tests/fixtures/xbrl/aebi/10q_2026q2/aebi-20260630_htm.xml")
BWA = Path("tests/fixtures/xbrl/bwa/10q_2026q2/bwa-20260630_htm.xml")


@pytest.fixture(scope="module")
def aebi():
    return XBRL.from_files(instance_file=AEBI)


@pytest.fixture(scope="module")
def bwa():
    return XBRL.from_files(instance_file=BWA)


def aebi_loans(xbrl):
    return (xbrl.query(include_contexts=True)
            .by_concept("us-gaap:LongTermDebt", exact=True)
            .by_custom(lambda row: row["context_ref"] in {"c-178", "c-179"}))


def test_aebi_frame_keeps_both_currencies(aebi):
    """Two instants x two currencies = four rows, as filed."""
    frame = aebi_loans(aebi).to_dataframe()

    assert len(frame) == 4
    assert set(zip(frame["fact_id"], frame["context_ref"], frame["currency"])) == {
        ("f-726", "c-178", "CHF"),
        ("f-730", "c-178", "EUR"),
        ("f-727", "c-179", "CHF"),
        ("f-731", "c-179", "EUR"),
    }
    # Same number in both currencies -- the coincidence that caused the deletion.
    assert set(frame["value"]) == {"10000000"}
    assert set(frame["decimals"]) == {"-3"}


def test_aebi_frame_agrees_with_execute(aebi):
    """The frame must not be a lossy view of the same query.

    `execute()` was already correct; the defect was that exporting the identical
    selection returned fewer facts than iterating it.
    """
    query = aebi_loans(aebi)
    assert {r["fact_id"] for r in query.execute()} == set(aebi_loans(aebi).to_dataframe()["fact_id"])


def test_aebi_units_resolve_to_distinct_currencies(aebi):
    """The two units really are different measures, not a labelling artefact."""
    assert aebi.units["chf"]["measure"] == "iso4217:CHF"
    assert aebi.units["eur"]["measure"] == "iso4217:EUR"


def test_bwa_collapses_repeated_tags_but_keeps_both_currencies(bwa):
    """gh #769 and gh #1282 at once: 4 physical tags -> 2 rows."""
    concept = ("us-gaap:BusinessCombinationContingentConsiderationArrangements"
               "RangeOfOutcomesValueHigh")
    query = (bwa.query(include_contexts=True)
             .by_concept(concept, exact=True)
             .by_custom(lambda row: row["context_ref"] == "c-19"))

    # Four physical occurrences: each currency tagged twice.
    tags = [(r["fact_id"], r["unit_ref"]) for r in query.execute()]
    assert tags == [("f-285", "chf"), ("f-286", "usd"),
                    ("f-291", "chf"), ("f-292", "usd")]

    frame = query.to_dataframe()
    assert len(frame) == 2, "one representative per currency"
    assert list(frame["fact_id"]) == ["f-285", "f-286"]
    assert set(frame["currency"]) == {"CHF", "USD"}
