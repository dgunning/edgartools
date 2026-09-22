"""
Regression test for GitHub issue #841: `filing.document.text` returns a bound
method, not a string.

GitHub Issue: https://github.com/dgunning/edgartools/issues/841

The report is that `filing.document.text` is not the text. It is not a bug in
the sense of the library doing the wrong thing — the design is deliberate and
consistent, properties for cheap raw access and methods for work that parses or
renders — but the shapes involved are genuinely easy to get wrong, and two
things made it worse:

* `filing.document` returns an **Attachment**, not the `edgar.documents.Document`
  parser object the name suggests.
* `Filing.to_context()` told agents to "Use `.document()` for structured text
  extraction". `.document` is a property, so `.document()` raises TypeError, and
  it is not a text extractor either. That hint is fixed and pinned by
  `test_to_context_hint_integrity.py`.

WHAT THIS FILE PINS: the shapes themselves, so the decision recorded in the bead
("do NOT make .text a property") cannot be quietly reversed. Making
`Attachment.text` a property would break every existing `attachment.text()`
call, and `Document.text(clean=, include_tables=, max_length=, ...)` takes
arguments, so it cannot be a property at all — the trio has to stay methods, and
the fix for the confusion is documentation, not a redefinition.

Bead: edgartools-1h9c

These are class-level assertions on purpose: they need no filing, so the
contract is checked on every pull request rather than only when a network job
runs. One network test at the end confirms the shapes hold on a real filing.
"""
import inspect

import pytest

from edgar._filings import Filing
from edgar.attachments import Attachment
from edgar.documents import Document


def _static(cls, name):
    """The class attribute itself, not what accessing it on an instance yields."""
    return inspect.getattr_static(cls, name, None)


class TestTheShapesUsersTripOver:
    """`.content` is a property, `.text()` is a method — on purpose."""

    def test_attachment_content_is_a_property(self):
        assert isinstance(_static(Attachment, "content"), property), (
            "Attachment.content is the cheap raw-access half of the design; if it "
            "became a method, every documented `attachment.content` breaks"
        )

    @pytest.mark.parametrize("name", ["text", "markdown"])
    def test_attachment_work_methods_stay_methods(self, name):
        attr = _static(Attachment, name)
        assert attr is not None, f"Attachment.{name} disappeared"
        assert not isinstance(attr, property), (
            f"Attachment.{name} became a property. That is the change issue #841 "
            f"asks for and it must not be made: it breaks every existing "
            f"`attachment.{name}()` call, and the bead records the decision."
        )
        assert callable(attr)

    def test_document_text_takes_arguments_so_it_cannot_be_a_property(self):
        """The structural reason the trio stays methods."""
        params = inspect.signature(Document.text).parameters
        tunable = [p for p in params if p != "self"]
        assert tunable, (
            "Document.text() takes no arguments any more, which removes the "
            "structural argument for it being a method — revisit #841 deliberately"
        )
        for expected in ("clean", "include_tables"):
            assert expected in params, (
                f"Document.text() lost its {expected!r} parameter; the signature "
                f"is {sorted(tunable)}"
            )


class TestWhatFilingDotDocumentActuallyIs:
    """`filing.document` is a property returning an Attachment."""

    def test_document_is_a_property_not_a_callable(self):
        assert isinstance(_static(Filing, "document"), property), (
            "Filing.document is a property. to_context() once advertised "
            "'.document()', which raises TypeError — see "
            "test_to_context_hint_integrity.py"
        )

    def test_the_documented_text_entry_points_are_callable(self):
        """`.text()` and `.markdown()` are what to_context() now points at."""
        for name in ("text", "markdown"):
            attr = _static(Filing, name)
            assert attr is not None, f"Filing.{name} disappeared"
            assert not isinstance(attr, property), (
                f"Filing.{name} became a property, so the documented "
                f"`filing.{name}()` call now raises"
            )
            # Filing.text is lru_cache-wrapped, so it is not a plain function.
            assert callable(attr)


@pytest.mark.network
def test_the_shapes_hold_on_a_real_filing():
    """The contract above, confirmed against Apple's FY2024 10-K.

    Anchors the class-level assertions to something a reader can check: the
    types are what the guide promises, and `.text` really is a bound method
    rather than the string the issue expected.
    """
    from tests._offline_filings import offline_filing

    filing = offline_filing("0000320193-24-000123")
    attachment = filing.document

    assert isinstance(attachment, Attachment), (
        f"filing.document should be an Attachment, got {type(attachment).__name__}. "
        "That mismatch with the name is the root of issue #841."
    )
    assert isinstance(attachment.content, str) and attachment.content, (
        "attachment.content is a property returning the raw document"
    )

    # The reported surprise, pinned: truthy, but not the text.
    assert not isinstance(attachment.text, str), (
        "attachment.text is a bound method — `if attachment.text:` is always "
        "True and is never the document text. Call it."
    )
    assert callable(attachment.text)

    text = attachment.text()
    assert isinstance(text, str) and text.strip(), "attachment.text() returns the text"
