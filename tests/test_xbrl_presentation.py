from pathlib import Path

from rich import print

from edgar.xbrl.presentation import XBRLPresentation


def test_parse_labels_with_namespace():
    presentation_text = Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml').read_text()
    presentation: XBRLPresentation = XBRLPresentation.parse(presentation_text)
    print(presentation)


def test_parse_presentation_with_no_namespace():
    presentation_text = Path('data/xbrl/datafiles/radcq/rad-20230304_pre.xml').read_text()
    presentation: XBRLPresentation = XBRLPresentation.parse(presentation_text)
    presentation.print_structure()
    print(presentation)
