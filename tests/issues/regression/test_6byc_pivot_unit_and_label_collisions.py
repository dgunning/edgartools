"""Company Facts pivot_by_period() silently discarded facts that collided on an
insufficient key, and for an IFRS filer discarded almost all of them.

bead edgartools-6byc, GH #1196. Ground truth is LPA (CIK 1997711), 20-F
accession 0001997711-25-000030, via the tracked fixture
``tests/fixtures/entity/lpa_facts.json``, so this runs offline.

Two independent keys were too narrow, and they compounded:

* ``_deduplicate_facts`` grouped on (concept, period) with **no unit**, so
  ``ifrs-full:AverageForeignExchangeRate`` filed once per currency became one
  group from which a single fact survived. 19 distinct facts were lost, and the
  survivor no longer identified its currency, so it read as an unqualified number.
* ``pivot_by_period`` then indexed on ``label`` alone. SEC company facts carry no
  label for IFRS concepts — all 177 of this filer's ``ifrs-full`` tags have
  ``label: null`` upstream — so **765 of 768 facts shared the label ''** and the
  entire filing pivoted into a 2-row table.

Residual collisions are logged rather than silently resolved. The ones that
remain on this filing are a *different* key: ``_format_period_label`` maps
distinct periods (monthly durations and the full year; instants at 2024-03-26 and
2024-12-31) onto one "FY 2024" label. That is the edgartools-51xd period-identity
species, which this bead was deliberately filed apart from.
"""

import json
from pathlib import Path

import pandas as pd
import pytest

from edgar.entity.parser import EntityFactsParser

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "entity" / "lpa_facts.json"

# LPA's 20-F, as filed. Each rate is filed for the same FY2024 period under a
# different currency unit; before the fix only the COP row survived.
FX_2024 = {"COP": 4071.0, "CRC": 518.0, "PEN": 3.756}
REVENUE_2024 = 43_862_372.0


@pytest.fixture(scope="module")
def facts():
    assert FIXTURE.exists(), f"missing fixture: {FIXTURE}"
    return EntityFactsParser.parse_company_facts(json.loads(FIXTURE.read_text("utf-8")))


def test_dedup_keeps_facts_that_differ_only_by_unit(facts):
    query = facts.query()
    all_facts = query.execute()

    fx = [f for f in all_facts if f.concept.endswith("AverageForeignExchangeRate")]
    assert {f.unit for f in fx} == {"COP", "CRC", "PEN"}, "fixture no longer has the multi-currency case"

    kept = [f for f in query._deduplicate_facts(all_facts)
            if f.concept.endswith("AverageForeignExchangeRate")]
    by_unit_2024 = {f.unit: f.numeric_value for f in kept
                    if f.period_end and f.period_end.year == 2024}
    assert by_unit_2024 == FX_2024, "dedup collapsed currencies that are distinct facts"


def test_pivot_does_not_collapse_an_ifrs_filing_into_one_row(facts):
    """The labels really are empty upstream -- the row key must survive that."""
    all_facts = facts.query().execute()
    empty_labels = sum(1 for f in all_facts if not (f.label or "").strip())
    assert empty_labels > 700, "fixture no longer exercises the empty-label case"

    pivot = facts.query().pivot_by_period(return_statement=False)
    assert len(pivot) > 150, f"pivot collapsed to {len(pivot)} rows"

    # A concept with a usable label keeps it, unqualified, because it never collided.
    assert "Revenue" in pivot.index
    assert pivot.loc["Revenue", "FY 2024"] == REVENUE_2024


def test_colliding_rows_keep_the_field_that_identifies_them(facts):
    """The survivor of a currency collision used to read as an unqualified number."""
    pivot = facts.query().pivot_by_period(return_statement=False)
    for unit, expected in FX_2024.items():
        row = f"AverageForeignExchangeRate ({unit})"
        assert row in pivot.index, f"{row} missing -- its currency was dropped"
        assert pivot.loc[row, "FY 2024"] == expected


def test_discriminators_are_added_only_where_they_are_needed(facts):
    """Suffixing every row to fix the uncommon case would make the common one unreadable."""
    pivot = facts.query().pivot_by_period(return_statement=False)
    assert "Revenue" in pivot.index, "a non-colliding row was given a unit suffix"
    assert "Revenue (USD)" not in pivot.index


def test_unresolved_collisions_are_reported_not_silently_dropped(facts, caplog):
    """A remaining collision must say so. Silence is what this bug was."""
    import logging

    with caplog.at_level(logging.WARNING, logger="edgar"):
        facts.query().pivot_by_period(return_statement=False)

    assert any("share a cell" in record.getMessage() for record in caplog.records), (
        "residual collisions were resolved in silence")


def test_measured_shape_of_this_filing(facts):
    """Ground truth, so a future change that drops rows again fails here.

    The residual collisions are a different key -- `_format_period_label` maps
    monthly durations and the full year onto one "FY 2024" -- and belong to
    edgartools-51xd, not here. They are logged, and pinned so their count cannot
    grow unnoticed.
    """
    query = facts.query()
    all_facts = query.execute()
    dedup = query._deduplicate_facts(all_facts)
    pivot = query.pivot_by_period(return_statement=False)

    assert len(all_facts) == 768
    assert len(dedup) == 569            # was 550: 19 unit-distinguished facts recovered
    assert pivot.shape == (188, 6)      # was (2, 6)

    records = pd.DataFrame([{"label": f.label, "concept": f.concept, "unit": f.unit,
                             "period_key": query._format_period_label(f)} for f in dedup])
    keys = query._pivot_row_keys(records)
    colliding = int(pd.DataFrame({"k": keys, "p": records["period_key"]})
                    .duplicated(keep=False).sum())
    assert colliding == 21

    # Every distinct (row, period) the facts produce occupies a cell -- nothing
    # lands nowhere.
    distinct_cells = len(set(zip(keys, records["period_key"], strict=True)))
    assert int(pivot.notna().sum().sum()) == distinct_cells
