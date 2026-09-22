"""
Regression test for GitHub issue #486: ZeroDivisionError in comprehensive income access

This test ensures that comprehensive income statements can be accessed without
ZeroDivisionError, even when weight_map is empty or sums to zero.

The bug was in edgar/xbrl/statement_resolver.py:626 where division by
sum(weight_map.values()) occurred without checking if it was zero.

Root cause: total_weight > 0 but sum(weight_map.values()) == 0, causing
ZeroDivisionError and blocking access to legitimate financial data.

Affected ~9.5% of filings (~2,038 filings, 28+ companies).

GitHub Issue: https://github.com/dgunning/edgartools/issues/486
"""

import pytest

from edgar import Company
from edgar.xbrl.exceptions import StatementNotFound


class TestComprehensiveIncomeZeroDivision:
    """Test cases for comprehensive income access without ZeroDivisionError"""

    @pytest.mark.network
    def test_comprehensive_income_no_zerodiv_error(self):
        """Test that accessing comprehensive income does not raise ZeroDivisionError.

        The original bug was ZeroDivisionError when weight_map sums to zero.
        This test verifies the fix by attempting to access comprehensive income
        on multiple filings - even if the statement doesn't exist, it should
        NOT raise ZeroDivisionError (it may raise StatementNotFound instead).
        """
        # Test with Apple which has comprehensive income
        company = Company("AAPL")
        filing = company.get_filings(form="10-K").latest(1)
        xb = filing.xbrl()

        # This should NOT raise ZeroDivisionError
        try:
            ci = xb.statements.comprehensive_income()
        except ZeroDivisionError as e:
            pytest.fail(f"ZeroDivisionError raised: {e}. Bug #486 not fixed.")
        except StatementNotFound as e:
            pytest.fail(
                f"Apple's 10-K has no comprehensive income statement ({e}). The "
                "absence used to be tolerated here, which meant the test could "
                "report green having never rendered anything -- and rendering is "
                "where #486 crashed."
            )

        # Apple files a comprehensive income statement in every 10-K; treating
        # its absence as acceptable is what let this test pass without
        # exercising the weight_map arithmetic that raised ZeroDivisionError.
        assert ci is not None, "comprehensive_income() returned None for AAPL"
        df = ci.to_dataframe()
        assert not df.empty, (
            "comprehensive income rendered an empty dataframe, so the summing "
            "path that raised ZeroDivisionError was never reached"
        )

    @pytest.mark.network
    def test_comprehensive_income_bracket_notation_no_zerodiv(self):
        """Test bracket notation doesn't raise ZeroDivisionError"""
        company = Company("MSFT")
        filing = company.get_filings(form="10-K").latest(1)
        xb = filing.xbrl()

        # Bracket notation should NOT raise ZeroDivisionError
        try:
            ci_br = xb.statements['ComprehensiveIncome']
        except ZeroDivisionError as e:
            pytest.fail(f"ZeroDivisionError raised: {e}. Bug #486 not fixed.")
        except (StatementNotFound, KeyError) as e:
            pytest.fail(
                f"bracket notation could not resolve ComprehensiveIncome for "
                f"MSFT ({type(e).__name__}: {e}). Tolerating that made a green "
                "run mean nothing -- see the sibling accessor test."
            )

        assert ci_br is not None, "statements['ComprehensiveIncome'] returned None for MSFT"
        df = ci_br.to_dataframe()
        assert not df.empty, (
            "comprehensive income rendered an empty dataframe, so the summing "
            "path that raised ZeroDivisionError was never reached"
        )

    @pytest.mark.network
    def test_comprehensive_income_multiple_affected_companies(self):
        """Two more of the 28+ affected CIKs, and one of them must render.

        HISTORY, because this test has been weakened twice by accident. It
        began as a loop ending in a bare `except Exception: pass`, so it passed
        with outbound sockets blocked -- the very first Company() call raised a
        connection error straight into the swallow. Counting companies
        exercised fixed that but left `assert ci_bracket.to_dataframe() is not
        None` as the only claim about the data, which an empty dataframe
        satisfies. #486 was a crash *while rendering*, so a run in which
        nothing rendered proves nothing, however many companies it visited.

        The last 10-K is a moving target, so nothing here is pinned to a
        figure: the assertions are that the CIKs are the companies the issue
        named, that their XBRL parses, that neither access path raises, and
        that at least one company produces a comprehensive income statement
        with rows in it.
        """
        from edgar import Company

        expected = {
            1001601: "MGT CAPITAL INVESTMENTS, INC.",
            1009829: "JAKKS PACIFIC INC",
        }
        rendered = []

        for cik, name in expected.items():
            company = Company(str(cik))
            assert company.name == name, (
                f"CIK {cik} is now {company.name!r}, not {name!r}; this test's "
                "sample no longer matches the companies issue #486 listed"
            )

            filing = company.get_filings(form="10-K").latest(1)
            assert filing, f"{name} has no 10-K to check"

            xb = filing.xbrl()
            assert not xb.facts.to_dataframe().empty, (
                f"{name} {filing.accession_no} parsed to zero facts, so no "
                "statement could be rendered from it"
            )

            try:
                # Both access paths, neither of which may raise ZeroDivisionError.
                ci = xb.statements.comprehensive_income()
                ci_bracket = xb.statements.get('ComprehensiveIncome')
            except ZeroDivisionError as e:
                pytest.fail(f"ZeroDivisionError for CIK {cik}: {e}. Bug #486 not fixed.")
            except (StatementNotFound, KeyError):
                # The statement being absent is not this bug; the crash was.
                continue

            if ci is None:
                # Not every small filer presents comprehensive income
                # separately, so this is allowed -- but it renders nothing, and
                # a run where BOTH companies land here fails below.
                assert ci_bracket is None, (
                    f"{name}: the accessor found no comprehensive income "
                    "statement but bracket notation did; the two paths disagree"
                )
                continue

            df = ci.to_dataframe()
            assert not df.empty, f"{name}: comprehensive income rendered no rows"
            assert (df['label'].astype(str).str.strip() != '').all(), \
                f"{name}: comprehensive income has unlabelled rows"
            rendered.append(name)

        assert rendered, (
            f"neither {list(expected.values())} rendered a comprehensive "
            "income statement, so the summing path that raised "
            "ZeroDivisionError was never reached"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
