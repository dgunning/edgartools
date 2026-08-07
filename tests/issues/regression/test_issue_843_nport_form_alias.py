"""Regression test for GitHub issue #843 (form alias half).

`company.get_filings(form="N-PORT")` returned 0 results because SEC filings never
carry the literal form "N-PORT" -- the portfolio-holdings report is filed as
"NPORT-P" (no hyphen after the N). filter_by_form is exact-match, so the friendly
"N-PORT" matched nothing and failed silently.

The fix adds a small form-alias map so "N-PORT"/"NPORT" expand to the real
"NPORT-P" before filtering, applied centrally in filter_by_form() so both
edgar.get_filings() and company.get_filings() benefit.
"""
import pyarrow as pa
import pytest

from edgar.filtering import FORM_ALIASES, _expand_form_aliases, filter_by_form


def _form_table(forms):
    return pa.table({"form": pa.array(forms)})


# --------------------------------------------------------------------------- #
# Alias expansion (fast, no network)
# --------------------------------------------------------------------------- #

@pytest.mark.fast
@pytest.mark.parametrize("alias", ["N-PORT", "n-port", " N-PORT ", "NPORT", "nport"])
def test_alias_expands_to_nport_p(alias):
    assert _expand_form_aliases([alias]) == ["NPORT-P"]


@pytest.mark.fast
def test_non_aliased_forms_pass_through_unchanged():
    assert _expand_form_aliases(["NPORT-P", "10-K", "8-K", "3"]) == ["NPORT-P", "10-K", "8-K", "3"]


@pytest.mark.fast
def test_alias_preserved_in_mixed_list_and_order():
    assert _expand_form_aliases(["N-PORT", "NPORT-EX"]) == ["NPORT-P", "NPORT-EX"]


@pytest.mark.fast
def test_filter_by_form_matches_real_rows_via_alias():
    table = _form_table(["NPORT-P", "NPORT-P", "NPORT-EX", "10-K", "NPORT-P/A"])

    via_alias = filter_by_form(table, form="N-PORT", amendments=False)
    via_real = filter_by_form(table, form="NPORT-P", amendments=False)
    assert via_alias.num_rows == via_real.num_rows == 2  # the two plain NPORT-P rows

    # amendments=True should pick up NPORT-P/A through the alias too.
    via_alias_amd = filter_by_form(table, form="N-PORT", amendments=True)
    assert via_alias_amd.num_rows == 3  # 2x NPORT-P + 1x NPORT-P/A


@pytest.mark.fast
def test_n_port_not_a_real_form_so_exact_match_would_be_empty():
    """Guards the premise: without the alias, 'N-PORT' matches nothing."""
    table = _form_table(["NPORT-P", "NPORT-EX"])
    # The literal string is intentionally absent from the alias *values*.
    assert "N-PORT" not in FORM_ALIASES.values()
    # Sanity: a genuinely unknown form yields no rows.
    assert filter_by_form(table, form="DEFINITELY-NOT-A-FORM", amendments=False).num_rows == 0


# --------------------------------------------------------------------------- #
# End-to-end via the public API (network)
# --------------------------------------------------------------------------- #

@pytest.mark.network
def test_company_n_port_alias_matches_nport_p():
    import edgar
    edgar.set_identity("research@example.com")

    company = edgar.Company("VOO")
    n_port = company.get_filings(form="N-PORT")
    nport_p = company.get_filings(form="NPORT-P")

    assert len(nport_p) > 0
    assert len(n_port) == len(nport_p)  # the #843 bug: N-PORT used to be 0


@pytest.mark.network
def test_global_n_port_alias_matches_nport_p():
    import edgar
    edgar.set_identity("research@example.com")

    n_port = edgar.get_filings(year=2025, quarter=1, form="N-PORT")
    nport_p = edgar.get_filings(year=2025, quarter=1, form="NPORT-P")

    assert len(nport_p) > 0
    assert len(n_port) == len(nport_p)
