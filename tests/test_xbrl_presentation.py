from pathlib import Path
import pytest
from rich import print

from edgar.xbrl.presentation import XBRLPresentation


@pytest.fixture
def rad_presentation():
    presentation_text = Path('data/xbrl/datafiles/radcq/rad-20230304_pre.xml').read_text()
    return XBRLPresentation.parse(presentation_text)

def test_parse_labels_with_namespace():
    presentation_text = Path('data/xbrl/datafiles/aapl/aapl-20230930_pre.xml').read_text()
    presentation: XBRLPresentation = XBRLPresentation.parse(presentation_text)
    print(presentation)


def test_parse_presentation_with_no_namespace(rad_presentation):
    structure = rad_presentation.print_structure()
    print(structure)


def test_presentation_get_structure(rad_presentation):
    structure = rad_presentation.get_structure(detailed=True)
    print(structure)
