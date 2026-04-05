from edgar.xbrl.standardization.tools.report_generator import (
    generate_cohort_report,
    generate_escalation_report,
    parse_cohort_report,
    CohortReportData,
    CompanyResult,
    AppliedFix,
    UnresolvedGapEntry,
    EscalatedGap,
)


def test_generate_cohort_report():
    """Cohort report renders valid markdown with all sections."""
    report_data = CohortReportData(
        name="test-cohort-2026-04-05",
        status="inner_loop_complete",
        companies=[
            CompanyResult(ticker="HD", ef_cqs=0.92, status="graduated", gaps_remaining=2, notes="ShortTermDebt divergence"),
            CompanyResult(ticker="D", ef_cqs=0.71, status="needs_investigation", gaps_remaining=8, notes="Utility archetype gaps"),
        ],
        fixes=[
            AppliedFix(ticker="HD", metric="ResearchAndDevelopment", action="EXCLUDE_METRIC", confidence=1.0, detail="not_applicable (retail)"),
        ],
        unresolved=[
            UnresolvedGapEntry(ticker="D", metric="GrossProfit", gap_type="unmapped", variance=None, root_cause="concept absent from XBRL", graveyard=0),
        ],
    )
    md = generate_cohort_report(report_data)

    assert "# Cohort Report: test-cohort-2026-04-05" in md
    assert "inner_loop_complete" in md
    assert "| HD " in md
    assert "| D " in md
    assert "EXCLUDE_METRIC" in md
    assert "GrossProfit" in md


def test_parse_cohort_report_roundtrip():
    """Parse a generated cohort report back into structured data."""
    report_data = CohortReportData(
        name="roundtrip-test",
        status="inner_loop_complete",
        companies=[
            CompanyResult(ticker="AAPL", ef_cqs=0.95, status="graduated", gaps_remaining=1, notes=""),
        ],
        fixes=[],
        unresolved=[
            UnresolvedGapEntry(ticker="AAPL", metric="Goodwill", gap_type="unmapped", variance=None, root_cause="concept_absent", graveyard=0),
        ],
    )
    md = generate_cohort_report(report_data)
    parsed = parse_cohort_report(md)

    assert parsed.name == "roundtrip-test"
    assert parsed.status == "inner_loop_complete"
    assert len(parsed.companies) == 1
    assert parsed.companies[0].ticker == "AAPL"
    assert len(parsed.unresolved) == 1
    assert parsed.unresolved[0].metric == "Goodwill"


def test_generate_escalation_report():
    """Escalation report renders with evidence sections."""
    gaps = [
        EscalatedGap(
            ticker="D",
            metric="OperatingIncome",
            gap_type="unmapped",
            confidence=0.65,
            evidence=["Calc tree has OperatingExpenses but no OperatingIncome node",
                       "Peer utilities also lack this concept"],
            why_escalated="Ambiguous — could be reference_mismatch or needs_composite",
            recommendation="Likely DOCUMENT_DIVERGENCE",
        ),
    ]
    md = generate_escalation_report(
        name="test-cohort-2026-04-05",
        auto_fixes=[],
        escalated_gaps=gaps,
        ef_cqs_before=0.87,
        ef_cqs_after=0.91,
    )

    assert "# Escalation Report" in md
    assert "pending_review" in md
    assert "D" in md
    assert "OperatingIncome" in md
    assert "Ambiguous" in md


def test_generate_cohort_report_empty_sections():
    """Cohort report with no fixes or unresolved gaps still renders."""
    report_data = CohortReportData(
        name="empty-test",
        status="inner_loop_complete",
        companies=[
            CompanyResult(ticker="AAPL", ef_cqs=0.99, status="graduated", gaps_remaining=0, notes="Perfect score"),
        ],
        fixes=[],
        unresolved=[],
    )
    md = generate_cohort_report(report_data)

    assert "# Cohort Report: empty-test" in md
    assert "AAPL" in md


def test_roundtrip_with_enriched_gap_entry():
    """Enriched gap entries roundtrip through markdown without losing base fields."""
    report_data = CohortReportData(
        name="enriched-test",
        status="inner_loop_complete",
        companies=[],
        fixes=[],
        unresolved=[
            UnresolvedGapEntry(
                ticker="HD", metric="Revenue", gap_type="high_variance",
                variance=5.3, root_cause="wrong_concept", graveyard=1,
                reference_value=100.0, xbrl_value=94.7,
            ),
        ],
    )
    md = generate_cohort_report(report_data)
    parsed = parse_cohort_report(md)

    assert len(parsed.unresolved) == 1
    assert parsed.unresolved[0].ticker == "HD"
    assert parsed.unresolved[0].variance == 5.3
    # Note: enriched fields are NOT in markdown, so parsed version has defaults
    assert parsed.unresolved[0].reference_value is None


def test_parse_cohort_report_with_none_variance():
    """Parser handles None variance in unresolved gaps."""
    report_data = CohortReportData(
        name="none-var-test",
        status="inner_loop_complete",
        companies=[],
        fixes=[],
        unresolved=[
            UnresolvedGapEntry(ticker="HD", metric="Revenue", gap_type="unmapped", variance=None, root_cause="concept_absent", graveyard=0),
            UnresolvedGapEntry(ticker="HD", metric="NetIncome", gap_type="high_variance", variance=15.3, root_cause="wrong_concept", graveyard=2),
        ],
    )
    md = generate_cohort_report(report_data)
    parsed = parse_cohort_report(md)

    assert len(parsed.unresolved) == 2
    assert parsed.unresolved[0].variance is None
    assert parsed.unresolved[1].variance == 15.3
