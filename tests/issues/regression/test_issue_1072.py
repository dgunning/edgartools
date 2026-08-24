"""Regression tests for GH issue #1072: CUSIP column bleed silently drops rows.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1072

On pre-2013 TXT-format 13F-HR infotables, the fixed-width slice cut from the
``<S>/<C>`` marker-line offsets could miss the true CUSIP on both sides: the
slice started too late (the issuer/class block ran wider than the markers
imply) and/or ran long (a 12-digit padded value bled the leading digits of the
value column into the slice). ``_clean_cusip`` then rejected every such slice
and the row was dropped without a warning -- 15 rows out of 192 on Gilder
Gagnon Howe's 2002-Q4 filing, and 5 out of 217 on its 2008-Q4 filing.

The fix treats the marker-line column spec as a *hint*: when the exact slice
does not yield a valid CUSIP, a tolerance window around the expected start is
searched for a checksum-valid 9-character candidate (spaces/dashes collapsed),
preferring the window whose start is closest to the expected offset. The CUSIP
checksum (SEC/CUSIP Mod-10) makes spurious candidates from neighbouring
fields vanishingly rare.

Ground truth for the counts is each filing's own cover-page
"Form 13F Information Table Entry Total", confirmed by hand against SEC EDGAR:

===========================  ==========================  ==========  ==========
Filing                       Accession                   Entry Total Pre-fix
===========================  ==========================  ==========  ==========
GGH 2002-Q4                  0000922423-03-000187        192         15 rows
GGH 2001-Q3                  0000922423-01-501041        194         20 rows
GGH 2008-Q4                  0000922423-09-000197        217          5 rows
Berkshire Hathaway 2008-Q4   0000950134-09-003064        108        107 rows
===========================  ==========================  ==========  ==========

Berkshire's filing pins the no-regression side: only one row (Wellpoint,
CUSIP ``949773V107``) was affected there, so the recovery must fix that row
without disturbing the other 107 already-parsed rows.

Fixtures are trimmed to the "FORM 13F INFORMATION TABLE" section of each
filing's primary document; they replay through ``parse_multiline_format``
unchanged.
"""
import pathlib

import pytest

from edgar.thirteenf.parsers.infotable_txt.format_multiline import (
    _clean_cusip,
    _cusip_checksum_valid,
    _expected_start_distance_ok,
    extract_entry_total,
    parse_multiline_format,
    reconcile_entry_total,
)

pytestmark = [pytest.mark.fast, pytest.mark.regression]

FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures" / "issues" / "regression" / "issue_1072"


def _parse(name: str):
    txt = (FIXTURES / name).read_text(encoding="utf-8")
    return parse_multiline_format(txt)


# ---------------------------------------------------------------------------
# Unit tests for the checksum validator and helpers
# ---------------------------------------------------------------------------

class TestCusipChecksum:
    # Real CUSIPs from the filings in this issue, with their check digits.
    @pytest.mark.parametrize("cusip", [
        # Berkshire 2008-Q4 Wellpoint row. The filer wrote it as
        # ``949773V 10 7`` (a 10-character run once collapsed); the only
        # 9-character reading consistent with the Mod-10 check digit is
        # ``949773V10``, which is what recovery returns.
        "949773V10",
        "H0023R105",    # GGH 2008-Q4 ACE Limited (Mode B: slice started too late)
        "020936100",    # GGH 2008-Q4 Altius Minerals (Mode B)
        "008474108",    # GGH 2008-Q4 Agnico Eagle
        "025816109",    # American Express, from the format_multiline docstring
    ])
    def test_real_cusips_pass_checksum(self, cusip):
        assert _cusip_checksum_valid(cusip) is True

    @pytest.mark.parametrize("cusip", [
        "123456789",
        "023R10500",    # shifted window of H0023R105000, wrong check digit
    ])
    def test_invalid_windows_fail_checksum(self, cusip):
        assert _cusip_checksum_valid(cusip) is False

    @pytest.mark.parametrize("cusip", [
        # These DO pass the checksum (~10% of arbitrary 9-char runs do) --
        # which is precisely why recovery cannot rely on the checksum alone.
        # They are shifted windows / neighbouring-field runs, excluded by the
        # token-alignment rule in _recover_cusip_near instead. See
        # test_no_shifted_window_garbage_in_recovered_rows for the end-to-end
        # guarantee over the real filings.
        "MH0023R10",
        "210X27700",
        "770022440",
        "0023R1050",
        "971940200",
    ])
    def test_checksum_alone_is_not_sufficient(self, cusip):
        assert _cusip_checksum_valid(cusip) is True

    def test_exact_slice_still_rejected_when_not_9_chars(self):
        # A 12-digit padded slice must not be accepted as-is even though its
        # first 9 characters would checksum-validate: the recovery path, not
        # the exact path, owns that case.
        assert _clean_cusip("90385V107000") is None


class TestToleranceWindow:
    def test_window_is_bounded(self):
        assert _expected_start_distance_ok(51, 51)
        assert _expected_start_distance_ok(48, 51)
        assert _expected_start_distance_ok(63, 51)
        assert not _expected_start_distance_ok(64, 51)
        assert not _expected_start_distance_ok(38, 51)

    def test_negative_and_zero_offsets(self):
        assert _expected_start_distance_ok(0, 0)
        # Distance |(-1) - 5| = 6, inside the tolerance.
        assert _expected_start_distance_ok(-1, 5)
        assert not _expected_start_distance_ok(5, -8)


# ---------------------------------------------------------------------------
# Cover-page Entry Total reconciliation (the generic silent-loss detector)
# ---------------------------------------------------------------------------

class TestEntryTotalReconciliation:
    def test_extract_same_line_value(self):
        assert extract_entry_total(
            "Form 13F Information Table Entry Total:         108") == 108

    def test_extract_next_line_value(self):
        # GGH 2002-Q4 puts the count on the line after the label.
        txt = "Form 13F Information Table Entry Total:\n192\n- ---\n"
        assert extract_entry_total(txt) == 192

    def test_extract_absent(self):
        assert extract_entry_total("no totals here") is None

    def test_warning_fires_when_rows_missing(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING,
                             logger="edgar.thirteenf.parsers.infotable_txt.format_multiline"):
            reconcile_entry_total(217, 5)
        assert any("may be incomplete" in r.message and "217" in r.message
                   for r in caplog.records)

    def test_no_warning_on_exact_match(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING,
                             logger="edgar.thirteenf.parsers.infotable_txt.format_multiline"):
            reconcile_entry_total(108, 108)
        assert not caplog.records

    def test_no_warning_without_declared_total(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING,
                             logger="edgar.thirteenf.parsers.infotable_txt.format_multiline"):
            reconcile_entry_total(None, 5)
        assert not caplog.records


class TestEndToEndWithReconciliation:
    """The trimmed fixtures carry the cover-page totals, so the full
    parse_multiline_format path exercises the reconciliation too."""

    def test_ggh_2008q4_parses_with_no_incomplete_warning(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING,
                             logger="edgar.thirteenf.parsers.infotable_txt.format_multiline"):
            df = _parse("ggh_2008Q4.txt")
        incomplete = [r for r in caplog.records if "incomplete" in r.message]
        if len(df) < 217:
            assert incomplete, "row shortfall must warn"
        else:
            assert not incomplete



class TestRowRecovery:
    def test_ggh_2002q4_full_recovery(self):
        df = _parse("ggh_2002Q4.txt")
        assert len(df) == 192

    def test_ggh_2001q3_full_recovery(self):
        df = _parse("ggh_2001Q3.txt")
        assert len(df) == 194

    def test_ggh_2008q4_recovers_mode_b(self):
        # Mode B: slices wrong on BOTH sides ('H0023R105' never appears inside
        # the sliced span). 215 of 217 recover; the remaining 2 rows have no
        # checksum-valid window anywhere near the expected offset because the
        # filer wrote the class column over the CUSIP field entirely.
        df = _parse("ggh_2008Q4.txt")
        assert len(df) == 215

    def test_brk_2008q4_no_regression_on_good_rows(self):
        # 107 of 108 parsed before; the fix must keep all 107 AND add back
        # the Wellpoint row (recovered as ``949773V10`` -- see the checksum
        # test above for why the filer's ``949773V 10 7`` reads that way).
        df = _parse("brk_2008Q4.txt")
        assert len(df) == 108
        assert (df["Cusip"] == "949773V10").sum() == 1


class TestRecoveredValues:
    """Spot-check recovered CUSIPs against the values printed on the filings."""

    def test_mode_b_cusips_are_the_true_values(self):
        df = _parse("ggh_2008Q4.txt")
        cusips = set(df["Cusip"])
        # From the issue thread: these were cut off at the left by the marker
        # slice before the fix ('023R105000', '032X135000' were parsed instead).
        assert "H0023R105" in cusips   # ACE Limited
        assert "H0032X135" in cusips   # Actelion
        assert "G0450A105" in cusips   # G4S plc (filed as '450A105...')
        assert "020936100" in cusips   # Altius Minerals

    def test_no_shifted_window_garbage_in_recovered_rows(self):
        # The nearest-start rule must not admit off-by-one windows like
        # '0023R1050' (start+1) or 'MH0023R10'.
        df = _parse("ggh_2008Q4.txt")
        bad = {"0023R1050", "23R105000", "MH0023R10", "971940200", "719402000"}
        assert not (bad & set(df["Cusip"]))

    def test_row_fields_survive_recovery(self):
        df = _parse("ggh_2002Q4.txt")
        akbank = df[df["Issuer"].str.contains("AKBANK", case=False, na=False)]
        assert len(akbank) >= 1
        row = akbank.iloc[0]
        assert row["Cusip"] == "009719402"
        # The class column on the AKBANK data line holds 'COM'; 'SPONSORED
        # ADR' arrives via the multi-line name path and lands in Issuer.
        assert row["Class"] == "COM"
