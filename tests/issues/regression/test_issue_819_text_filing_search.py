"""
Regression test for GitHub Issue #819 (quick-win partial fix):
Filing.search() raised bare AssertionError on pre-2001 SGML/text filings
because Filing.sections() asserted that filing.html() was non-null with no
helpful message.

This test covers only the assertion → ValueError change. The deeper fix
(making sections() and grep() actually work on text filings) is scheduled
for 5.32.0.
"""

from unittest.mock import MagicMock, patch

import pytest

from edgar._filings import Filing


def _make_filing_no_html() -> Filing:
    """Build a minimal Filing instance whose .html() returns None."""
    filing = Filing(
        cik=12345,
        company="TEST",
        form="10-K",
        filing_date="2000-03-08",
        accession_no="0000000000-00-000000",
    )
    return filing


class TestSectionsRaisesUsefulError:
    """sections() must raise a legible ValueError when html() returns None."""

    def test_sections_raises_value_error_not_assertion(self):
        filing = _make_filing_no_html()
        with patch.object(filing, "html", return_value=None):
            with pytest.raises(ValueError) as exc_info:
                filing.sections()

        msg = str(exc_info.value)
        assert "no HTML primary document" in msg
        assert "filing.text()" in msg
        assert filing.accession_no in msg

    def test_sections_does_not_raise_assertion_error(self):
        """Specifically — no bare AssertionError (the original GH #819 symptom)."""
        filing = _make_filing_no_html()
        with patch.object(filing, "html", return_value=None):
            try:
                filing.sections()
            except ValueError:
                pass  # expected
            except AssertionError:
                pytest.fail("sections() must not raise bare AssertionError")

    def test_search_surfaces_useful_error_on_text_filing(self):
        """search() delegates to sections() — the error must propagate legibly."""
        filing = _make_filing_no_html()
        with patch.object(filing, "html", return_value=None):
            with pytest.raises(ValueError) as exc_info:
                filing.search("employees")

        msg = str(exc_info.value)
        assert "filing.text()" in msg, (
            "Error message must point users at the working workaround"
        )
