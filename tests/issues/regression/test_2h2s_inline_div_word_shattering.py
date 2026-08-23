"""A div styled ``display:inline`` no longer shatters its inline runs
(edgartools-2h2s).

Filers routinely bold one letter of a word by putting it in its own ``<font>``
or ``<span>`` — the initials of an acronym, a drop cap. When those runs sit
inside a ``<div>`` whose style carries ``display:inline``, ``Document.text()``
used to emit each run as its own block::

    <div style="display:inline;"><font>H</font><font>unger </font>
    <font>E</font><font>limination</font></div>

    legacy edgar.files : 'Hunger Elimination'
    edgar.documents    : 'H\\n\\nunger\\n\\nE\\n\\nlimination'

Every character survived, which is why no length check caught it — the damage
only shows in a word-level comparison, or to a reader.

CAUSE. In ``DocumentBuilder``'s div/block branch, ``style.display in
('inline','inline-block')`` called ``_get_element_text()`` and, on a falsy
result, returned a bare ``ContainerNode`` — which emits each child run as its
own block. But ``_get_element_text()`` only descends into children for elements
that are inline BY TAG, and a ``div`` is not one, so it sees only the div's
direct text. That is empty for exactly the shape this branch exists to serve,
so the fallback fired every time. The normal-block path directly below already
handled the same shape correctly via ``_is_text_only_container()`` ->
``ParagraphNode``, which concatenates inline children. The ``display:inline``
branch was strictly worse than the block branch it was meant to refine.

WHY THE BARE-DIV TEST IS HERE. The bare ``<div>`` case was always correct. It is
pinned below so that a future change cannot "fix" the inline case by regressing
the block case — the two paths sit four lines apart and share a fallback.

Found while comparing legacy and modern text output for the ``press_release``
migration (edgartools-3dp), on 8-K 0000950170-25-047769, where the filer writes
the acronym HERO with each initial bolded: '(Hunger Elimination or Reduction
Objective)' came out as '(\\nH\\nunger\\nE\\nlimination or\\nR\\neduction\\nO\\nbjective)'.
"""
import pytest

from edgar.documents import parse_html

pytestmark = pytest.mark.fast


RUNS = ('<font style="font-weight:bold;">H</font><font>unger </font>'
        '<font style="font-weight:bold;">E</font><font>limination</font>')

# The shape as the real filing writes it, attributes and all.
REAL_SHAPE = (
    '<div style="width:100%;display:inline;">'
    '<font style="color:#212121;white-space:pre-wrap;font-weight:bold;font-size:12pt;'
    'font-family:\'Aptos\',sans-serif;font-kerning:none;min-width:fit-content;">H</font>'
    '<font style="color:#212121;white-space:pre-wrap;font-size:12pt;'
    'font-family:\'Aptos\',sans-serif;font-kerning:none;min-width:fit-content;">unger </font>'
    '<font style="color:#212121;white-space:pre-wrap;font-weight:bold;font-size:12pt;'
    'font-family:\'Aptos\',sans-serif;font-kerning:none;min-width:fit-content;">E</font>'
    '<font style="color:#212121;white-space:pre-wrap;font-size:12pt;'
    'font-family:\'Aptos\',sans-serif;font-kerning:none;min-width:fit-content;">limination</font>'
    '</div>'
)


@pytest.mark.parametrize("display", ["inline", "inline-block"])
def test_an_inline_styled_div_keeps_its_runs_on_one_line(display):
    """Both values route through the same branch, so both must hold."""
    text = parse_html(f'<div style="display:{display};">{RUNS}</div>').text().strip()
    assert text == "Hunger Elimination"


def test_the_real_filing_shape_survives():
    """The 8-K 0000950170-25-047769 shape, attributes included.

    The synthetic case above is the diagnosis; this is the thing that broke.
    """
    assert parse_html(REAL_SHAPE).text().strip() == "Hunger Elimination"


def test_a_word_is_never_split_across_lines():
    """The symptom stated directly, rather than via an equality that could be
    satisfied by some other rendering."""
    text = parse_html(f'<div style="display:inline;">{RUNS}</div>').text().strip()
    assert "\n" not in text
    assert "H\nunger" not in text


@pytest.mark.parametrize("container", [
    f'<div>{RUNS}</div>',
    f'<p>{RUNS}</p>',
    f'<div style="width:100%;">{RUNS}</div>',
])
def test_containers_that_were_already_correct_stay_correct(container):
    """Guards the block path, four lines from the one that was fixed."""
    assert parse_html(container).text().strip() == "Hunger Elimination"


def test_an_inline_div_holding_a_real_block_is_not_flattened():
    """The fix routes through ``_is_text_only_container``, so a div carrying an
    actual block child must still keep those blocks apart — otherwise the fix
    would have traded one wrong rendering for another."""
    html = '<div style="display:inline;"><p>First para</p><p>Second para</p></div>'
    text = parse_html(html).text()
    assert "First para" in text
    assert "Second para" in text
    assert "First paraSecond para" not in text
