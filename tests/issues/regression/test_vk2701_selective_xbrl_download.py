"""filing.xbrl() on a large filing fetches only its XBRL files, not the whole submission.

Bead: edgartools-vk270.1

`XBRL.from_filing` read `filing.attachments`, which is the complete submission
.txt with every exhibit, image and PDF. For VALE's FY2025 20-F
(0001292814-26-001844) that was 101.4 MB over the wire to parse 0.76 MB of XBRL.
Above `selective_attachment_download_min_bytes` (20 MB, as the filing index page lists the
.txt) it now fetches the index page, the XBRL files and FilingSummary.xml. The
period of report and SIC come from the index page too, because
`filing.period_of_report` would load the whole submission.

Measured before the change on 11 XBRL filings (ARCC, MAIN, AAPL 2019 and 2025,
BCS, VALE, JPM, CATO, CNQ, an MSFT 8-K, the MSFT 2010 10-K): facts, every
statement, period of report and industry identical to the full-submission path.

WHAT THESE TESTS PROTECT:

  1. **The selective path never loads the submission** and gives the filed
     values (CATO FY2023 total assets $486,817,000).
  2. **Today's path is kept** when the setting is off, the form is not an
     annual or quarterly report (the size check costs a request), the
     submission is small, the SGML is already loaded, or the index page fails.
  3. **The instance is downloaded once**, not once to recognise it and again
     to parse it.
"""
from pathlib import Path

import pytest

import edgar.settings as settings
from edgar import Filing
from edgar.xbrl import xbrl as xbrl_module
from edgar.xbrl.xbrl import XBRL, XBRLAttachments, _selective_xbrl_sources

CATO_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "xbrl" / "cato" / "10k_2023"
CATO_10K = dict(form="10-K", filing_date="2024-03-27", company="CATO CORP", cik=18255,
                accession_no="0001562762-24-000065")

# Total assets at 2026-08-01, read from SEC's cato26qtr2q_htm.xml (0001562762-26-000100).
CATO_ASSETS_2026_08_01 = 423_438_000

_KINDS = {
    "cato-20240203.xsd": "EX-101.SCH",
    "cato-20240203_cal.xml": "EX-101.CAL",
    "cato-20240203_def.xml": "EX-101.DEF",
    "cato-20240203_lab.xml": "EX-101.LAB",
    "cato-20240203_pre.xml": "EX-101.PRE",
    "cato2023012810K_htm.xml": "XML",
}


class _FakeAttachment:
    """The parts of an index-page Attachment that from_filing reads, counting downloads."""

    def __init__(self, document, document_type, size=None, path=None, reads=None):
        self.document = document
        self.document_type = document_type
        self.size = size
        self.extension = Path(document).suffix
        self._path = path
        self._reads = reads

    @property
    def content(self):
        self._reads[self.document] = self._reads.get(self.document, 0) + 1
        return self._path.read_text()


class _FakeAttachments(list):
    @property
    def data_files(self):
        return [a for a in self if a.document_type != "submission"]


class _FakeFiler:
    identification = "IRS No.: 560484485 | State of Incorp.: DE | Fiscal Year End: 0201\nSIC: 5621 Retail-Women's"


class _FakeHomepage:
    url = "https://www.sec.gov/Archives/edgar/data/18255/000156276224000065/0001562762-24-000065-index.htm"
    period_of_report = "2024-02-03"

    def __init__(self, submission_bytes, reads):
        self.attachments = _FakeAttachments(
            [_FakeAttachment(name, kind, path=CATO_DIR / name, reads=reads) for name, kind in _KINDS.items()]
            + [_FakeAttachment("0001562762-24-000065.txt", "submission", size=submission_bytes)])

    def get_filers(self):
        return [_FakeFiler()]


def _cato_filing(monkeypatch, submission_bytes=25_000_000):
    """A CATO filing whose index page is local and whose whole submission must not be read."""
    reads = {}
    filing = Filing(**CATO_10K)
    filing._filing_homepage = _FakeHomepage(submission_bytes, reads)

    def no_submission(*args, **kwargs):
        raise AssertionError("the selective path loaded the whole submission")

    monkeypatch.setattr(Filing, "sgml", no_submission)
    monkeypatch.setattr(xbrl_module, "_download_filing_summary", lambda url: None)
    monkeypatch.delenv("EDGAR_SELECTIVE_ATTACHMENT_DOWNLOAD", raising=False)
    return filing, reads


@pytest.mark.fast
def test_large_filing_reads_only_its_xbrl_files(monkeypatch):
    filing, reads = _cato_filing(monkeypatch)
    xbrl = XBRL.from_filing(filing)

    assets = xbrl.facts.query().by_concept("us-gaap:Assets", exact=True).to_dataframe()
    # The entity-level context; the instance also carries segment-level Assets facts.
    assert assets.loc[assets["context_ref"] == "AS_OF_Feb03_2024_Entity_0000018255", "numeric_value"].tolist() == [486_817_000]
    assert xbrl._sgml_period_of_report == "2024-02-03"
    assert xbrl.standardization.industry == settings_industry_for("5621")


def settings_industry_for(sic):
    """The industry today's path sets for this SIC, so the test does not hard-code the mapping."""
    probe = XBRL()
    probe.standardization.set_industry_from_sic(sic)
    return probe.standardization.industry


@pytest.mark.fast
def test_instance_is_downloaded_once(monkeypatch):
    filing, reads = _cato_filing(monkeypatch)
    XBRL.from_filing(filing)
    assert reads == {name: 1 for name in _KINDS}


@pytest.mark.fast
def test_small_submission_keeps_the_full_path(monkeypatch):
    filing, _ = _cato_filing(monkeypatch, submission_bytes=settings.selective_attachment_download_min_bytes)
    assert _selective_xbrl_sources(filing) is None


@pytest.mark.fast
@pytest.mark.parametrize("value", ["false", "0", "no", "off", "FALSE"])
def test_setting_off_keeps_the_full_path(monkeypatch, value):
    filing, _ = _cato_filing(monkeypatch)
    monkeypatch.setenv("EDGAR_SELECTIVE_ATTACHMENT_DOWNLOAD", value)
    assert settings.selective_attachment_download() is False
    assert _selective_xbrl_sources(filing) is None


@pytest.mark.fast
def test_setting_defaults_on(monkeypatch):
    monkeypatch.delenv("EDGAR_SELECTIVE_ATTACHMENT_DOWNLOAD", raising=False)
    assert settings.selective_attachment_download() is True


@pytest.mark.fast
@pytest.mark.parametrize("form", ["8-K", "6-K", "4", "S-1", "N-CSR"])
def test_other_forms_skip_the_size_check(monkeypatch, form):
    """Only annual and quarterly reports pay the index-page request; others keep one request."""
    filing, _ = _cato_filing(monkeypatch)
    filing.form = form

    class _Untouchable:
        def __getattr__(self, name):
            raise AssertionError(f"the index page was read for a {form}")

    filing._filing_homepage = _Untouchable()
    assert _selective_xbrl_sources(filing) is None


@pytest.mark.fast
def test_amended_annual_report_is_checked(monkeypatch):
    filing, _ = _cato_filing(monkeypatch)
    filing.form = "10-K/A"
    sources = _selective_xbrl_sources(filing)
    assert (sources.period_of_report, sources.sic) == ("2024-02-03", "5621")


@pytest.mark.fast
def test_loaded_submission_is_used_as_is(monkeypatch):
    filing, _ = _cato_filing(monkeypatch)
    filing._sgml = object()
    assert _selective_xbrl_sources(filing) is None


@pytest.mark.fast
def test_failing_index_page_falls_back(monkeypatch):
    filing, _ = _cato_filing(monkeypatch)

    class _Broken(_FakeHomepage):
        def get_filers(self):
            raise ValueError("index page changed shape")

    filing._filing_homepage = _Broken(25_000_000, {})
    assert _selective_xbrl_sources(filing) is None


@pytest.mark.fast
def test_xbrl_attachments_reuse_the_sniffed_instance():
    reads = {}
    attachments = _FakeAttachments(
        [_FakeAttachment(name, kind, path=CATO_DIR / name, reads=reads) for name, kind in _KINDS.items()])
    documents = XBRLAttachments(attachments)
    assert documents.content("instance").startswith("<?xml")
    assert reads["cato2023012810K_htm.xml"] == 1


@pytest.mark.network
@pytest.mark.vcr
def test_cato_10q_selective_download_live(monkeypatch):
    """CATO's 10-Q for the quarter ended 2026-08-01 (0001562762-26-000100), threshold forced to 0."""
    monkeypatch.setattr(settings, "selective_attachment_download_min_bytes", 0)
    monkeypatch.delenv("EDGAR_SELECTIVE_ATTACHMENT_DOWNLOAD", raising=False)
    filing = Filing(form="10-Q", filing_date="2026-08-27", company="CATO CORP", cik=18255,
                    accession_no="0001562762-26-000100")
    xbrl = filing.xbrl()
    assert filing._sgml is None, "the selective path loaded the whole submission"
    assets = xbrl.facts.query().by_concept("us-gaap:Assets", exact=True).to_dataframe()
    assert assets.loc[assets["context_ref"] == "AS_OF_Aug01_2026_Entity_0000018255", "numeric_value"].tolist() == [CATO_ASSETS_2026_08_01]
    assert xbrl._sgml_period_of_report == "2026-08-01"

