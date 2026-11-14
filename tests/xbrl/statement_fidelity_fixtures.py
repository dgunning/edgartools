"""Offline statement-fidelity inputs: a FilingViewer and an XBRL built from tests/fixtures/statement-fidelity."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from edgar.sgml.filing_summary import Report
from edgar.sgml.metalinks import MetaLinks
from edgar.xbrl.viewer import FilingViewer
from edgar.xbrl.xbrl import XBRL

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "statement-fidelity"


def fixture_viewer_and_xbrl(accession: str):
    """The fixture's page as a FilingViewer, and its trimmed XBRL files as an XBRL.

    The XBRL is parsed with ``XBRL.from_directory``. What ``XBRL.from_filing``
    adds from the filing itself is applied from the manifest and MetaLinks: the
    FilingSummary menu category of each kept role (``_apply_filing_summary``), the industry from the header's SIC code, and the
    header's period of report.
    """
    d = FIXTURE_DIR / accession
    manifest = json.loads((d / "manifest.json").read_text())
    metalinks = MetaLinks.parse((d / "xbrl" / "MetaLinks.json").read_text())
    xbrl = XBRL.from_directory(d / "xbrl")
    xbrl._apply_filing_summary(SimpleNamespace(reports=[
        SimpleNamespace(role=role, menu_category=category)
        for role, category in manifest["menu_categories"].items()]))
    if manifest.get("sic"):
        xbrl.standardization.set_industry_from_sic(manifest["sic"])
    xbrl._sgml_period_of_report = manifest.get("period_of_report")

    sgml = MagicMock()
    sgml.get_content = lambda name: (d / name).read_text() if (d / name).exists() else None
    reports = []
    for rkey, meta in sorted(metalinks.reports.items(), key=lambda kv: kv[1].order):
        report = Report(instance=None, is_default=False, has_embedded_reports=False,
                        html_file_name=f"{rkey}.htm", long_name=meta.long_name, report_type=None,
                        role=meta.role, parent_role=None, short_name=meta.short_name,
                        menu_category=meta.menu_cat, position=str(meta.order), reports=None)
        report._reports = MagicMock()
        report._reports._filing_summary._filing_sgml = sgml
        reports.append(report)
    filing_summary = MagicMock()
    filing_summary.reports = reports
    viewer = FilingViewer(sgml, filing_summary, metalinks)
    viewer._xbrl = xbrl
    viewer._xbrl_loaded = True
    return viewer, xbrl
