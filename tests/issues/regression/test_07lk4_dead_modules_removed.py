"""Two modules nothing used are gone in 6.0.

bead edgartools-07lk.4 (dead-code sweep, narrowed 2026-10-21 to modules with
no users). Found by an import graph over edgar/ plus a text search of the repo
for each module path and short name:

- edgar.documents.migration imitated the old SECHTMLParser on top of the new
  parser for a transition that 6.0 finishes by deleting edgar.files. Nothing
  imported it; its only mention was the package README.
- edgar.documents.extractors.heading_section_detector defined a
  HeadingSectionDetector that no module, test or document referenced.

docs/upgrade/6.0.md lists both with their replacements.
"""
import importlib

import pytest


@pytest.mark.fast
@pytest.mark.parametrize("module", [
    "edgar.documents.migration",
    "edgar.documents.extractors.heading_section_detector",
])
def test_removed_module_does_not_import(module):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module)


@pytest.mark.fast
def test_the_replacements_named_in_the_upgrade_guide_exist():
    from edgar.documents import HTMLParser, parse_html

    document = parse_html("<html><body><h1>Item 1. Business</h1><p>We make tractors.</p></body></html>")
    assert "We make tractors." in document.text()
    assert HTMLParser is not None and hasattr(document, "sections")
