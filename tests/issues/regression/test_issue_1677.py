"""Regression: a fact's preferred label and sign come from the statement it is assigned to.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1677

The Facts API took a concept's preferred label from the first presentation role
that had one, whatever statement the fact was assigned to. Omega Healthcare's
10-Q (0000888491-26-000024) presents us-gaap:InterestExpenseDebt on its
CONSOLIDATED STATEMENTS OF OPERATIONS with no preferredLabel, and in a segments
disclosure with negatedLabel. Every fact, each assigned to the income statement,
came back with preferred_sign -1 and the negated label's text, while
`get_statement()` on the operations role gave the same row no preferred label.

A preferredLabel belongs to one arc (XBRL 2.1 section 5.2.4.2.1). A fact assigned
to a statement now reads it from that statement's role.
"""

import pandas as pd
import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from tests._synthetic_xbrl import NOTE, OPS, write_two_role_filing

OHI_FOLDER = "https://www.sec.gov/Archives/edgar/data/888491/000088849126000024/"
OHI_FILES = ("ohi-20260630.xsd", "ohi-20260630x10q_htm.xml", "ohi-20260630_pre.xml", "ohi-20260630_lab.xml")
OPERATIONS = "http://www.omegahealthcare.com/role/StatementConsolidatedStatementsOfOperations"
SEGMENTS = "http://www.omegahealthcare.com/role/DisclosureSegmentsReportableSegmentsDetails"
CONCEPT = "us-gaap_InterestExpenseDebt"


@pytest.mark.vcr
def test_ohi_interest_expense_facts_take_the_income_statements_label(tmp_path):
    """Ground truth: Omega Healthcare 10-Q, 0000888491-26-000024, ohi-20260630_pre.xml."""
    for name in OHI_FILES:
        (tmp_path / name).write_text(download_file(OHI_FOLDER + name), encoding="utf-8")
    xbrl = XBRL.from_directory(tmp_path)

    # The linkbase: no preferred label on the face, negatedLabel in the segments note.
    assert xbrl.presentation_trees[OPERATIONS].all_nodes[CONCEPT].preferred_label is None
    assert xbrl.presentation_trees[SEGMENTS].all_nodes[CONCEPT].preferred_label.endswith("/negatedLabel")

    row = next(item for item in xbrl.get_statement(OPERATIONS) if item["concept"] == CONCEPT)
    assert row["preferred_label"] is None
    assert row["label"] == "Interest Expense"

    df = xbrl.facts.query().by_concept("us-gaap:InterestExpenseDebt", exact=True).to_dataframe()
    face = df[df["statement_type"] == "IncomeStatement"]
    assert sorted(face["value"].astype(int).unique()) == [48_116_000, 52_897_000, 97_871_000, 105_177_000]
    assert face["preferred_sign"].map(pd.isna).all()
    assert set(face["label"]) == {"Interest Expense"}


def test_fact_on_the_income_statement_ignores_a_notes_negated_label(tmp_path):
    """Offline: the income statement's arc names no preferred label, the note's names negatedLabel."""
    write_two_role_filing(tmp_path)
    xbrl = XBRL.from_directory(tmp_path)
    assert xbrl.presentation_trees[OPS].all_nodes["us-gaap_InterestExpenseDebt"].preferred_label is None
    assert xbrl.presentation_trees[NOTE].all_nodes["us-gaap_InterestExpenseDebt"].preferred_label.endswith("/negatedLabel")

    df = xbrl.facts.query().by_concept("us-gaap:InterestExpenseDebt", exact=True).to_dataframe()
    assert list(df["statement_type"]) == ["IncomeStatement"]
    assert pd.isna(df["preferred_sign"].iloc[0])
    assert df["label"].iloc[0] == "Interest Expense"
