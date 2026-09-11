"""Public 13F unit diagnostics and overrides, including Kahn's dollar-valued 2022 filing.

The original XML documents are preserved under tests/fixtures/13f/kahn-0001039565-22-000009.
See its README for provenance and independent corroboration. The summary is $1
higher than the sum of its 46 rows; an override must preserve that discrepancy.
"""

import warnings
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from edgar import ThirteenF
from edgar.thirteenf import Ambiguous13FValueUnitWarning
from edgar.thirteenf.units import resolve_value_unit

pytestmark = pytest.mark.fast
DATA = Path(__file__).resolve().parents[2] / 'tests/fixtures/13f/kahn-0001039565-22-000009'


@pytest.fixture
def kahn_filing(monkeypatch):
    """Use original SEC XML; only attachment I/O and optional tickers are stubbed."""
    import importlib
    parser = importlib.import_module('edgar.thirteenf.parsers.infotable_xml')
    monkeypatch.setattr(parser, 'cusip_ticker_mapping',
                        lambda **kwargs: pd.DataFrame({'Ticker': pd.Series(dtype=str)}))
    monkeypatch.setattr(ThirteenF, '_get_infotable_from_attachment',
                        lambda self: ((DATA / 'holdings.xml').read_text(), 'xml'))
    monkeypatch.setattr(ThirteenF, '_cache_provider', None)
    return SimpleNamespace(
        form='13F-HR', accession_no='0001039565-22-000009',
        filing_date='2022-05-02', xml=lambda: (DATA / 'primary.xml').read_text(),
    )


def test_kahn_diagnostics_preserve_original_values(kahn_filing):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        report = ThirteenF(kahn_filing)
        resolution = report.value_unit_resolution
        assert resolution.unit == 'thousands'
        assert resolution.multiplier == 1000
        assert resolution.source == 'report_period'
        assert resolution.ambiguous is True
        assert resolution.priceable_rows == 46
        assert resolution.fraction_sub_dollar == 0
        assert resolution.schema_version is None
        assert resolution.report_period == datetime(2022, 3, 31)
        assert report.raw_infotable.Value.sum() == 787_553_692
    assert not caught


@pytest.mark.parametrize('first', ['infotable', 'total_value', 'holdings'])
def test_ambiguous_conversion_warns_once_regardless_of_access_order(kahn_filing, first):
    report = ThirteenF(kahn_filing)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        getattr(report, first)
        # Backward-compatible output, now explicitly flagged as an uncertain conversion.
        assert report.total_value == Decimal('787553693000')
        assert report.infotable.Value.sum() == 787_553_692_000
        assert report.holdings.Value.sum() == 787_553_692_000
    assert len(caught) == 1
    assert caught[0].category is Ambiguous13FValueUnitWarning
    assert '0001039565-22-000009' in str(caught[0].message)
    assert "value_unit='dollars'" in str(caught[0].message)


@pytest.mark.parametrize('first', ['infotable', 'total_value', 'holdings'])
def test_verified_dollars_override_corrects_all_surfaces(kahn_filing, first):
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        report = ThirteenF(kahn_filing, value_unit='dollars')
        getattr(report, first)
        assert report.total_value == Decimal('787553693')
        assert report.infotable.Value.sum() == 787_553_692
        assert report.holdings.Value.sum() == 787_553_692
        assert len(report.infotable) == 46
        assert report.raw_infotable.Value.sum() == 787_553_692
        assert report.value_unit_resolution.source == 'override'
        assert report.value_unit_resolution.multiplier == 1
        alcon = report.infotable[report.infotable.Issuer == 'ALCON'].iloc[0]
        assert alcon.Value == 254_000
        assert alcon.SharesPrnAmount == 3_175
    assert not caught


def test_explicit_thousands_scales_once_without_mutating_raw_values(kahn_filing):
    report = ThirteenF(kahn_filing, value_unit='thousands')
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always')
        assert report.total_value == Decimal('787553693000')
        assert report.infotable.Value.sum() == 787_553_692_000
        assert report.raw_infotable.Value.sum() == 787_553_692
        assert report.infotable.Value.sum() == 787_553_692_000
    assert not caught


@pytest.mark.parametrize('unit,expected', [('dollars', '787553693'), ('thousands', '787553693000')])
def test_summary_override_does_not_fetch_holdings(kahn_filing, monkeypatch, unit, expected):
    def unavailable_attachment(self):
        raise OSError('Holdings attachment unavailable')

    monkeypatch.setattr(ThirteenF, '_get_infotable_from_attachment', unavailable_attachment)
    report = ThirteenF(kahn_filing, value_unit=unit)
    assert report.total_value == Decimal(expected)
    # The override does not hide an actual error when holdings are requested.
    with pytest.raises(OSError, match='Holdings attachment unavailable'):
        _ = report.infotable


def test_zero_summary_does_not_fetch_holdings(kahn_filing, monkeypatch):
    xml = kahn_filing.xml().replace('<tableValueTotal>787553693</tableValueTotal>',
                                    '<tableValueTotal>0</tableValueTotal>')
    kahn_filing.xml = lambda: xml

    def unavailable_attachment(self):
        raise OSError('Holdings attachment unavailable')

    monkeypatch.setattr(ThirteenF, '_get_infotable_from_attachment', unavailable_attachment)
    assert ThirteenF(kahn_filing).total_value == Decimal(0)


@pytest.mark.parametrize('raw_value,unit,expected,automatic_unit', [
    (254_000, 'thousands', 254_000_000, 'dollars'),
    (254, 'dollars', 254, 'thousands'),
])
def test_override_can_reverse_automatic_unit_choice(kahn_filing, raw_value, unit, expected, automatic_unit):
    # Synthetic values under a dollar-era schema exercise both override directions.
    # Reuse only the table shape, not a fabricated SEC fixture.
    automatic = ThirteenF(kahn_filing)
    raw = automatic.raw_infotable.iloc[:1].copy()
    raw['Value'] = raw_value
    automatic.__dict__.update(raw_infotable=raw, _schema_version='X0202')
    assert automatic.value_unit_resolution.unit == automatic_unit

    corrected = ThirteenF(kahn_filing, value_unit=unit)
    corrected.__dict__.update(raw_infotable=raw, _schema_version='X0202')
    assert corrected.infotable.Value.sum() == expected
    assert corrected.raw_infotable.Value.sum() == raw_value
    assert corrected.value_unit_resolution.source == 'override'


def test_override_bypasses_accession_only_cache(kahn_filing, monkeypatch):
    calls = []
    cached = pd.DataFrame({'Value': [787_553_692_000]})

    def provider(accession):
        calls.append(accession)
        return cached

    monkeypatch.setattr(ThirteenF, '_cache_provider', provider)
    assert ThirteenF(kahn_filing).holdings is cached
    assert calls == ['0001039565-22-000009']
    report = ThirteenF(kahn_filing, value_unit='dollars')
    assert report.holdings.Value.sum() == 787_553_692
    assert calls == ['0001039565-22-000009']


@pytest.mark.parametrize('unit', ['', 'auto', 'USD', 'millions', 1000])
def test_invalid_override_rejected_before_fetching(unit):
    with pytest.raises(ValueError, match='value_unit must be'):
        ThirteenF(None, value_unit=unit)


def test_warning_can_be_promoted_to_error(kahn_filing):
    report = ThirteenF(kahn_filing)
    with warnings.catch_warnings():
        warnings.simplefilter('error', Ambiguous13FValueUnitWarning)
        for _ in range(2):
            with pytest.raises(Ambiguous13FValueUnitWarning):
                _ = report.total_value


def test_documented_example(kahn_filing):
    # Execute the guide's example using the original documents without SEC I/O.
    guide = Path(__file__).resolve().parents[2] / 'docs/guides/thirteenf-data-object-guide.md'
    section = guide.read_text().split('### Ambiguous reporting units', 1)[1]
    example = section.split('```python\n', 1)[1].split('```', 1)[0]
    exec(compile(example, str(guide), 'exec'), {'filing': kahn_filing})


@pytest.mark.parametrize('value,shares', [(None, 1), (float('inf'), 1), (1, float('inf')),
                                         (-1, 1), (1, 0), (0, 1)])
def test_unpriceable_rows_do_not_establish_units(value, shares):
    df = pd.DataFrame([{'Value': value, 'SharesPrnAmount': shares, 'Type': 'Shares'}])
    result = resolve_value_unit(df, 'X0202')
    assert result.priceable_rows == 0
    assert result.fraction_sub_dollar is None
    assert result.source == 'schema'
    assert result.ambiguous is True


def test_duplicate_managers_do_not_change_override(kahn_filing):
    report = ThirteenF(kahn_filing, value_unit='dollars')
    raw = report.raw_infotable.copy()
    report.__dict__['raw_infotable'] = pd.concat([raw, raw], ignore_index=True)
    assert report.infotable.Value.sum() == 2 * 787_553_692
    assert report.holdings.Value.sum() == 2 * 787_553_692
    assert len(report.holdings) == 46


def test_notice_and_legacy_txt_use_same_unit_decision(monkeypatch):
    notice = SimpleNamespace(form='13F-NT', accession_no='notice', xml=lambda: None,
                             period_of_report='2022-03-31')
    report = ThirteenF(notice, value_unit='dollars')
    assert report.raw_infotable is None
    assert report.total_value is None
    assert report.value_unit_resolution.multiplier == 1

    # TXT parsing produces the same raw frame; exercise the public TXT fallback.
    import importlib
    parser = importlib.import_module('edgar.thirteenf.parsers.infotable_txt')
    raw = pd.DataFrame([{'Value': 766, 'SharesPrnAmount': 5896, 'Type': 'Shares'}])
    monkeypatch.setattr(parser, 'parse_infotable_txt', lambda _: raw)
    legacy = SimpleNamespace(form='13F-HR', accession_no='legacy', xml=lambda: None,
                              period_of_report='2012-03-31')
    report = ThirteenF(legacy)
    report.__dict__.update(infotable_xml=None, infotable_txt='stubbed TXT parser input')
    assert report.total_value == Decimal('766000')
    assert report.raw_infotable.Value.sum() == 766
    assert report.value_unit_resolution.source == 'implied_prices'
