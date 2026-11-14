"""Regression test for edgartools-ru9x: ParserConfig.extract_images was a knob that lied.

The field was declared ``extract_images: bool = False`` and nothing read it:
every ``<img>`` became an ImageNode, so the documented default was the opposite
of the behaviour. Removing it in a minor release would break
``ParserConfig(extract_images=...)`` call sites, so it is deprecated instead:
still accepted, ignored, and it warns. It is removed in 7.0.
"""

import warnings

import pytest

from edgar.documents import HTMLParser, ParserConfig
from edgar.documents.nodes import NodeType

HTML = '<html><body><p>Logo</p><img src="logo.png" alt="Company logo"><p>Body text.</p></body></html>'


def _images(config):
    doc = HTMLParser(config).parse(HTML)
    return [node for node in doc.root.walk() if node.type == NodeType.IMAGE]


def test_default_config_does_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        ParserConfig()
        ParserConfig.for_ai()


@pytest.mark.parametrize("value", [True, False])
def test_passing_extract_images_warns_and_is_ignored(value):
    with pytest.warns(DeprecationWarning, match="extract_images"):
        config = ParserConfig(extract_images=value)
    images = _images(config)
    assert len(images) == 1
    assert (images[0].src, images[0].alt) == ("logo.png", "Company logo")


def test_text_leaves_images_out_by_default():
    doc = HTMLParser(ParserConfig()).parse(HTML)
    assert "Company logo" not in doc.text()
    assert "Company logo" in doc.text(include_images=True)
