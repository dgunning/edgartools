"""6.0 removed the legacy ``edgar.files`` parser and ``ChunkedDocument``.

Bead: edgartools-07lk.3
GitHub Issue: https://github.com/dgunning/edgartools/issues/930

Every public route into the package warned through 5.x (``chunked_document``
from 5.49, the ``edgar.files`` modules from 5.55, ``CurrentReport.doc`` from
5.56, ``include_page_breaks`` from 5.46). 6.0 deletes it, and these tests pin
what the upgrade guide promised in its place:

* the package and its three top-level re-exports are gone, and the re-exports
  fail with directions rather than a bare "no attribute";
* nothing shipped imports it, checked statically so a reintroduced import fails
  here before it fails a user's ``import edgar``;
* ``chunked_document`` is gone from every report class, and ``CurrentReport.doc``
  is the parsed ``edgar.documents`` document, like ``.doc`` everywhere else;
* ``markdown()`` no longer takes ``include_page_breaks``/``start_page_number``;
* ``Attachment.text()`` and 8-K exhibit text, which reached the legacy parser
  through a lazy ``from edgar import Document`` the 5.x warnings never covered,
  render through the same rule as ``FilingSGML.text()``.

All offline: the fixture is a real 8-K tracked under tests/fixtures/parity_gate.
"""
import ast
import importlib.util
import inspect
import pathlib
import warnings

import pytest

import edgar
from edgar.attachments import Attachment, Attachments
from edgar.company_reports._base import CompanyReport
from edgar.company_reports.current_report import CurrentReport
from edgar.sgml.text_extraction import html_to_text

pytestmark = pytest.mark.fast

EDGAR_DIR = pathlib.Path(edgar.__file__).parent
FIXTURES = pathlib.Path(__file__).parent.parent.parent / "fixtures"
# Premier Financial Bancorp, 8-K filed 2021 (accession 0000887919-21-000012).
GATE_8K = FIXTURES / "parity_gate" / "8-K" / "0000887919-21-000012.html"


# ---------------------------------------------------------------------------
# The package
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("module", ["html", "htmltools", "html_documents", "markdown", "page_breaks",
                                    "styles", "tables", "text", "_deprecation"])
def test_the_package_is_gone(module):
    """Checked by source and by submodule, not by ``import edgar.files``.

    After the deletion a checkout that had imported the package keeps
    ``edgar/files/__pycache__/``, and Python imports a directory with no
    ``__init__.py`` as an empty namespace package — so ``import edgar.files``
    succeeds on a developer machine and fails only on a fresh one. Bytecode in
    ``__pycache__`` is never imported without its source, so the submodules
    are the honest check.
    """
    assert not list((EDGAR_DIR / "files").rglob("*.py"))
    try:
        spec = importlib.util.find_spec(f"edgar.files.{module}")
    except ModuleNotFoundError:  # a fresh checkout: no edgar/files directory at all
        spec = None
    assert spec is None
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(f"edgar.files.{module}")


def _legacy_imports(path: pathlib.Path, source: str):
    """Every import of edgar.files in one module, absolute or relative."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                # A relative import resolved against the module's own package.
                package = path.parent.relative_to(EDGAR_DIR.parent).parts
                base = ".".join(package[: len(package) - node.level + 1])
                module = f"{base}.{module}" if module else base
            names = [module]
        else:
            continue
        found += [n for n in names if n == "edgar.files" or n.startswith("edgar.files.")]
    return found


def test_no_shipped_module_imports_it():
    offenders = {}
    for path in EDGAR_DIR.rglob("*.py"):
        hits = _legacy_imports(path, path.read_text(encoding="utf-8"))
        if hits:
            offenders[str(path.relative_to(EDGAR_DIR.parent))] = hits
    assert not offenders, offenders


def test_the_import_scan_is_not_vacuous():
    """The scan above must be able to find what it is looking for."""
    module = EDGAR_DIR / "company_reports" / "probe.py"
    assert _legacy_imports(module, "from edgar.files.html import Document") == ["edgar.files.html"]
    assert _legacy_imports(module, "import edgar.files") == ["edgar.files"]
    assert _legacy_imports(EDGAR_DIR / "probe.py", "from .files import html") == ["edgar.files"]
    assert _legacy_imports(module, "from edgar.filesystem import EdgarPath") == []


@pytest.mark.parametrize("name", ["Document", "detect_page_breaks", "mark_page_breaks"])
def test_removed_top_level_names_explain_themselves(name):
    assert not hasattr(edgar, name)
    with pytest.raises(AttributeError, match="6.0"):
        getattr(edgar, name)


# ---------------------------------------------------------------------------
# Report classes
# ---------------------------------------------------------------------------

def _all_report_classes():
    """CompanyReport and its library subclasses.

    Filtered to classes defined under ``edgar.``: several regression tests build
    throwaway subclasses that stub ``_chunked_document``, and in a shared worker
    process those would otherwise turn up here depending on test order.
    """
    import edgar.company_reports  # noqa: F401 — registers every report class

    seen, stack = [], [CompanyReport]
    while stack:
        cls = stack.pop()
        if cls.__module__.startswith("edgar."):
            seen.append(cls)
        stack.extend(cls.__subclasses__())
    return seen


def test_chunked_document_is_gone_from_every_report_class():
    classes = _all_report_classes()
    assert len(classes) >= 6, [c.__name__ for c in classes]
    still = [c.__name__ for c in classes
             if hasattr(c, "chunked_document") or hasattr(c, "_chunked_document")]
    assert not still, still


class FixtureFiling:
    """The minimum surface the report classes touch, backed by a local file."""

    filing_date = None

    def __init__(self, path: pathlib.Path, form: str):
        self._path = path
        self.form = form
        self.company = "fixture"
        self.accession_number = path.stem
        self.base_dir = str(path.parent)

    def html(self):
        return self._path.read_text(encoding="utf-8", errors="replace")

    def text(self):
        return self.html()


def test_eight_k_doc_is_the_parsed_document_and_does_not_warn():
    from edgar.documents import Document

    report = CurrentReport(FixtureFiling(GATE_8K, "8-K"))
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        doc = report.doc
    assert isinstance(doc, Document)
    assert doc is report.document
    assert "PREMIER FINANCIAL BANCORP, INC." in doc.text()


# ---------------------------------------------------------------------------
# markdown() and text()
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method", [edgar.Filing.markdown, Attachment.markdown, Attachments.markdown],
                         ids=["Filing", "Attachment", "Attachments"])
def test_markdown_no_longer_takes_page_break_arguments(method):
    params = inspect.signature(method).parameters
    assert "include_page_breaks" not in params
    assert "start_page_number" not in params


def _attachment(content):
    attachment = Attachment(sequence_number="1", description="8-K", document="form8-k.htm",
                            ixbrl=False, path="/Archives/edgar/data/887919/000088791921000012/form8-k.htm",
                            document_type="8-K", size=None)
    attachment.content = content
    return attachment


def test_passing_include_page_breaks_is_a_loud_error():
    """Silence check: the removed argument fails at the call, naming itself."""
    with pytest.raises(TypeError, match="include_page_breaks"):
        _attachment(GATE_8K.read_text()).markdown(include_page_breaks=True)


def test_attachment_text_renders_through_the_filing_text_rule():
    html = GATE_8K.read_text(encoding="utf-8", errors="replace")
    text = _attachment(html).text()
    assert text == html_to_text(html)
    assert "PREMIER FINANCIAL BANCORP, INC." in text
    assert "(304) 525-1600" in text
