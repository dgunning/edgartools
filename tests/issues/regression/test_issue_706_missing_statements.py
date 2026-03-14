"""
Regression tests for GitHub Issue #706: Missing critical statements data

Tests that `comprehensive_income()` and `statement_of_equity()` return Statement objects
(not None) for historical filings where these statements may be embedded in other
presentations rather than filed as separate XBRL presentation roles.

Root cause: Older filings (pre-2015) often embed Other Comprehensive Income (OCI) data
within the equity rollforward statement rather than filing a separate Statement of
Comprehensive Income. The resolver now falls back to the equity statement as a
ComprehensiveIncome result when the equity statement contains CI concepts.

Confirmed affected cases:
- TSLA 2012 10-K (0001193125-12-137560): CI embedded in equity statement
- TSLA 2011 10-K (0001193125-12-081990): CI embedded in equity statement
- TSLA 2018 Q3 10-Q (0001564590-18-026353): equity statement genuinely absent
- TSLA 2018 Q2 10-Q (0001564590-18-019254): equity statement genuinely absent
- IBM 2010 10-K (0001047469-10-001151): CI embedded in equity statement
- GE 2010 10-K: CI embedded in roll-forward equity statement
"""

import pytest
from edgar import Filing, get_by_accession_number
from edgar.xbrl.statements import Statement


class TestIssue706MissingStatements:
    """
    Tests for Issue #706: comprehensive_income() and statement_of_equity()
    returning None for historical filings.
    """

    def test_tsla_2012_10k_comprehensive_income_not_none(self):
        """
        TSLA 2012 10-K (accession 0001193125-12-137560) should return a Statement
        for comprehensive_income(), not None.

        In this filing, OCI data is embedded within the equity rollforward statement
        'ConsolidatedStatementsOfConvertiblePreferredStockAndStockholdersEquityDeficit'.
        The resolver should fall back to this equity statement when no separate CI
        statement is present.
        """
        filing = get_by_accession_number('0001193125-12-137560')
        xbrl = filing.xbrl()
        ci = xbrl.statements.comprehensive_income()

        # Ground truth: should return a Statement, not None
        assert ci is not None, (
            "comprehensive_income() returned None for TSLA 2012 10-K (0001193125-12-137560). "
            "This filing embeds OCI in the equity statement - the resolver should fall back "
            "to that statement."
        )
        assert isinstance(ci, Statement), f"Expected Statement, got {type(ci)}"

        # Verify the statement is callable and returns data
        df = ci.to_dataframe()
        assert df is not None, "to_dataframe() returned None"
        assert len(df) > 0, "Statement DataFrame should not be empty"

        # Ground truth: the fallback statement resolves to the equity presentation role
        # It should contain stockholders equity concepts
        concept_names = df['concept'].tolist()
        has_equity_concept = any(
            'StockholdersEquity' in c or 'stockholdersequity' in c.lower()
            for c in concept_names if c
        )
        assert has_equity_concept, (
            "The CI fallback statement should contain stockholders equity concepts. "
            f"Found concepts: {concept_names[:10]}"
        )

    def test_tsla_2011_10k_comprehensive_income_not_none(self):
        """
        TSLA 2011 10-K (accession 0001193125-12-081990) should return a Statement
        for comprehensive_income(), not None.
        """
        filing = get_by_accession_number('0001193125-12-081990')
        xbrl = filing.xbrl()
        ci = xbrl.statements.comprehensive_income()

        assert ci is not None, (
            "comprehensive_income() returned None for TSLA 2011 10-K (0001193125-12-081990). "
            "This filing embeds OCI in the equity statement."
        )
        assert isinstance(ci, Statement)

        # Verify it produces a valid DataFrame (silence check: no AttributeError)
        df = ci.to_dataframe()
        assert df is not None
        assert len(df) > 0

    def test_tsla_2018_q3_statement_of_equity_none_when_absent(self):
        """
        TSLA 2018 Q3 10-Q (accession 0001564590-18-026353) genuinely does not contain
        a Statement of Stockholders' Equity in its XBRL presentation linkbase.

        statement_of_equity() should return None (not raise an exception).
        The user must check for None and handle it gracefully.
        """
        filing = get_by_accession_number('0001564590-18-026353')
        xbrl = filing.xbrl()

        # Should not raise an exception - just return None
        se = xbrl.statements.statement_of_equity()

        # Silence check: None is acceptable when the statement genuinely does not exist.
        # The key guarantee is that calling to_dataframe() on a non-None result works.
        # None means the filing doesn't include this statement in its XBRL data.
        assert se is None, (
            "statement_of_equity() should return None for TSLA 2018 Q3 10-Q "
            "(0001564590-18-026353) because the equity rollforward statement is not "
            "included in the filing's XBRL presentation linkbase."
        )

    def test_tsla_2018_q2_statement_of_equity_none_when_absent(self):
        """
        TSLA 2018 Q2 10-Q (accession 0001564590-18-019254) genuinely does not contain
        a Statement of Stockholders' Equity in its XBRL presentation linkbase.

        statement_of_equity() should return None (not raise an exception).
        """
        filing = get_by_accession_number('0001564590-18-019254')
        xbrl = filing.xbrl()

        se = xbrl.statements.statement_of_equity()
        assert se is None, (
            "statement_of_equity() should return None for TSLA 2018 Q2 10-Q "
            "(0001564590-18-019254) because the equity statement is absent from the XBRL."
        )

    def test_ibm_2010_10k_comprehensive_income_not_none(self):
        """
        IBM 2010 10-K (accession 0001047469-10-001151) should return a Statement
        for comprehensive_income(), not None.

        IBM's 2010 filing embeds comprehensive income data (OCI items) within the
        StatementOfStockholdersEquity presentation. The resolver should fall back to
        this equity statement as the CI statement.

        Ground truth: IBM 2009 OCI - Foreign currency translation adjustment was $1,732M.
        """
        filing = get_by_accession_number('0001047469-10-001151')
        xbrl = filing.xbrl()
        ci = xbrl.statements.comprehensive_income()

        assert ci is not None, (
            "comprehensive_income() returned None for IBM 2010 10-K (0001047469-10-001151). "
            "IBM's filing embeds OCI in the equity statement. The resolver should use it "
            "as a ComprehensiveIncome fallback."
        )
        assert isinstance(ci, Statement)

        # Verify it resolves to the equity statement
        role = ci.role_or_type
        assert role is not None
        assert 'stockholder' in role.lower() or 'equity' in role.lower(), (
            f"Expected CI fallback role to contain 'stockholder' or 'equity', got: {role}"
        )

        # Verify data is accessible - no AttributeError
        df = ci.to_dataframe()
        assert df is not None
        assert len(df) > 0

        # Ground truth: IBM 2009 foreign currency translation adjustment = $1,732M
        # (from the equity statement that embeds OCI)
        currency_rows = df[
            df['concept'].str.contains('ForeignCurrency', case=False, na=False)
        ]
        assert len(currency_rows) > 0, (
            "Expected to find ForeignCurrency OCI concepts in IBM's equity+OCI statement"
        )

    def test_comprehensive_income_fallback_produces_usable_dataframe(self):
        """
        When comprehensive_income() returns a Statement via the equity statement fallback,
        to_dataframe() should work without errors.

        This is the critical user-facing check: calling to_dataframe() on the result of
        comprehensive_income() should never raise AttributeError.
        """
        # Test all cases where CI is available (via fallback or directly)
        test_cases = [
            '0001193125-12-137560',  # TSLA 2012 - CI via equity fallback
            '0001193125-12-081990',  # TSLA 2011 - CI via equity fallback
            '0001047469-10-001151',  # IBM 2010 - CI via equity fallback
        ]

        for accession in test_cases:
            filing = get_by_accession_number(accession)
            xbrl = filing.xbrl()
            ci = xbrl.statements.comprehensive_income()

            # Key check: if ci is not None, to_dataframe() must work without error
            if ci is not None:
                # This should NOT raise AttributeError
                df = ci.to_dataframe()
                assert df is not None, f"to_dataframe() returned None for {accession}"
                assert len(df) > 0, f"DataFrame is empty for {accession}"

    def test_statement_of_equity_works_for_modern_quarterly_filings(self):
        """
        Verify that the CI->SE fallback does not break modern filings that have
        both a proper SE statement and (separately) a CI statement.

        TSLA 2019 Q3 10-Q includes both statements.
        """
        # TSLA 2019 Q3 10-Q has both CI and SE statements
        filing = get_by_accession_number('0001564590-19-038256')
        xbrl = filing.xbrl()

        se = xbrl.statements.statement_of_equity()
        ci = xbrl.statements.comprehensive_income()

        # Both should resolve separately
        assert se is not None, "StatementOfEquity should resolve for TSLA 2019 Q3"
        assert ci is not None, "ComprehensiveIncome should resolve for TSLA 2019 Q3"

        # They should be different statements (CI is separate in 2019)
        # Both should produce valid DataFrames
        se_df = se.to_dataframe()
        ci_df = ci.to_dataframe()

        assert len(se_df) > 0
        assert len(ci_df) > 0
