"""
Regression test: the XBRL-extraction warning must be traceable and must not
break warning interception.

Reported by Michael Gruening (TU Ilmenau) during a bulk crawl. A single
"WARNING:root:Failed to extract XBRL data: Document is empty" appeared in
2005 Q2 and he could not identify which filing produced it. Attaching a
logging.Handler that raises on WARNING - the standard trick for turning a
warning into a locatable traceback - made the message disappear entirely
instead of raising.

Three defects combined:

1. `_extract_xbrl_pre_process` logged via the module-level `logging.warning`,
   i.e. the ROOT logger ("WARNING:root:"), so it could not be filtered or
   routed per-module.
2. The message carried no document context whatsoever, so it was untraceable
   in a 7M-filing crawl.
3. The call sat inside `parse()`'s try block, whose `except Exception` turns
   anything into HTMLParsingError. A handler-raised exception was therefore
   swallowed and reborn as a parse failure - the warning vanished. This is the
   defect that made the message impossible to locate: the extraction step is
   best-effort and already swallows its own errors, so it belongs outside the
   fatal wrapper.

Additionally, lxml's "Document is empty" is benign here - a document with no
parseable root has no inline XBRL either - so it is now DEBUG, not WARNING.

Bead: edgartools-cxvz
"""
import logging

import pytest

from edgar.documents import HTMLParser
from edgar.documents.exceptions import HTMLParsingError

PARSER_LOGGER = "edgar.documents.parser"
VALID_HTML = "<html><body><p>hello</p></body></html>"


class RaiseOnWarning(logging.Handler):
    """Grüning's WarningToExceptionHandler, verbatim in behaviour."""

    class TriggeredError(Exception):
        pass

    def emit(self, record):
        if record.levelno >= logging.WARNING:
            raise self.TriggeredError(record.getMessage())


@pytest.fixture
def parser():
    return HTMLParser()


class TestBenignEmptyDocumentIsNotAWarning:
    def test_empty_document_logs_debug_not_warning(self, parser, caplog):
        with caplog.at_level(logging.DEBUG, logger=PARSER_LOGGER):
            assert parser._extract_xbrl_pre_process('<?xml version="1.0"?>') == []
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("no parseable root" in r.getMessage() for r in caplog.records)

    def test_nothing_is_logged_to_the_root_logger(self, parser, caplog):
        """The message used to surface as "WARNING:root:"."""
        with caplog.at_level(logging.DEBUG):
            parser._extract_xbrl_pre_process('<?xml version="1.0"?>')
        assert all(r.name != "root" for r in caplog.records)


class TestGenuineFailureIsTraceable:
    def test_warning_names_the_module_and_carries_context(self, parser, caplog):
        with caplog.at_level(logging.WARNING, logger=PARSER_LOGGER):
            # A non-str input reaches the generic handler rather than ParserError.
            assert parser._extract_xbrl_pre_process(12345) == []
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warnings) == 1
        assert warnings[0].name == PARSER_LOGGER
        message = warnings[0].getMessage()
        assert "AttributeError" in message      # the underlying error type
        assert "Preview:" in message            # identifying content
        assert "Document size:" in message

    def test_diagnostic_never_raises_on_odd_input(self, parser):
        """A diagnostic for a swallowed error must not itself raise."""
        assert parser._extract_xbrl_pre_process(12345) == []
        assert parser._extract_xbrl_pre_process(None) == []


class TestWarningInterceptionReachesTheCaller:
    """The reported symptom: a raising handler saw nothing at all."""

    def test_handler_exception_is_not_reborn_as_parse_error(self, parser, monkeypatch):
        original = parser._extract_xbrl_pre_process
        monkeypatch.setattr(parser, "_extract_xbrl_pre_process", lambda html: original(12345))

        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers, root.level
        root.handlers, root.level = [RaiseOnWarning()], logging.WARNING
        try:
            with pytest.raises(RaiseOnWarning.TriggeredError):
                parser.parse(VALID_HTML)
        finally:
            root.handlers, root.level = saved_handlers, saved_level

    def test_xbrl_failure_alone_does_not_fail_the_parse(self, parser, monkeypatch):
        """Best-effort really is best-effort: extraction failure still parses."""
        original = parser._extract_xbrl_pre_process
        monkeypatch.setattr(parser, "_extract_xbrl_pre_process", lambda html: original(12345))
        document = parser.parse(VALID_HTML)
        assert "hello" in document.text()

    def test_real_parse_errors_still_raise_html_parsing_error(self, parser):
        """The broad wrapper still does its job for genuine parse failures."""
        with pytest.raises(HTMLParsingError):
            parser.parse("<!-- just a comment -->")
