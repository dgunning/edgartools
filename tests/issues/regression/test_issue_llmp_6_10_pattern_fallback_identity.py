"""Regression tests for edgartools-llmp.6.10:
the pattern-detection fallback resolved "is this node already in range" with
``in`` on a list, which runs the dataclass ``__eq__``.

Bug:
    edgar/documents/extractors/pattern_section_extractor.py, _create_sections()

        nodes_in_range = []          # a list
        for n in nodes_in_range:
            if n.parent not in nodes_in_range:
                section_node.add_child(n)

    ``Node`` is a @dataclass (edgar/documents/nodes.py:94), so ``==`` is
    generated field-by-field. Membership against a list therefore ran that
    comparison once per candidate: quadratic in the nodes in range. On
    citigroup_10k_fy2024 the sections stage spent 10.5s of 16.4s inside
    ParagraphNode.__eq__, and the whole stage dropped from 5,215ms to 801ms
    when the test became an identity check.

    The comparison never changed the ANSWER — ``Node.id`` is a per-instance
    uuid and is compared first, so two distinct nodes are never equal, and
    section content is byte-identical across all 11 corpus filings before and
    after. The defect was cost, not correctness.

Fix:
    Snapshot ``{id(n) for n in nodes_in_range}`` and test ``id(n.parent)``
    against it. The ids must be snapshotted before the loop because
    ``add_child()`` reassigns ``child.parent`` as it goes.

What these tests lock:
    The invariant is "membership here is identity" — asserted directly by
    counting ``__eq__`` calls rather than by timing, which would be flaky in
    CI. A wall-clock assertion would also pass on a merely-faster-but-still-
    quadratic implementation.
"""
import pytest

from edgar.documents import parse_html
from edgar.documents.config import ParserConfig
from edgar.documents.nodes import Node


def _synthetic_10k(n: int = 200) -> str:
    """A 10-K with body item headers and NO anchored TOC.

    Without TOC anchors the hybrid detector falls through to pattern
    detection, which is the path under test. The paragraph bodies are
    deliberately templated so many nodes are structurally similar — the shape
    that made the old list membership expensive.
    """
    def paras(label: str) -> str:
        return ''.join(f'<p>{label} paragraph {i} of the filing text.</p>'
                       for i in range(n))

    return (
        '<html><body>'
        '<p><b>Item 1. Business</b></p>' + paras('Business') +
        '<p><b>Item 1A. Risk Factors</b></p>' + paras('Risk factor') +
        "<p><b>Item 7. Management's Discussion and Analysis of Financial "
        "Condition and Results of Operations</b></p>" + paras('MD&A') +
        '</body></html>'
    )


def _all_node_classes():
    """Every concrete Node subclass, which is where @dataclass puts __eq__.

    Patching Node.__eq__ alone would miss them: @dataclass generates a fresh
    __eq__ into each subclass's own __dict__, so the subclass never inherits
    the base one.
    """
    seen = set()
    stack = [Node]
    while stack:
        cls = stack.pop()
        if cls in seen:
            continue
        seen.add(cls)
        stack.extend(cls.__subclasses__())
    return [cls for cls in seen if '__eq__' in cls.__dict__]


@pytest.fixture
def eq_counter(monkeypatch):
    """Count every dataclass __eq__ call across all Node subclasses."""
    calls = []

    for cls in _all_node_classes():
        original = cls.__dict__['__eq__']

        def counting(self, other, _original=original, _cls=cls):
            calls.append(_cls.__name__)
            return _original(self, other)

        monkeypatch.setattr(cls, '__eq__', counting)

    return calls


class TestPatternFallbackUsesIdentity:

    def test_section_creation_never_calls_node_eq(self, eq_counter):
        """The regression itself: node equality must not be consulted."""
        document = parse_html(_synthetic_10k(), ParserConfig(form='10-K'))
        sections = document.sections

        # Guard against a vacuous pass: if this document stopped reaching the
        # pattern path, the assertion below would hold for the wrong reason.
        assert sections, "no sections detected — fixture no longer exercises the path"
        assert any(getattr(s, 'detection_method', None) == 'pattern'
                   for s in sections.values()), \
            "fixture no longer reaches pattern detection; the test proves nothing"

        assert not eq_counter, (
            f"Node.__eq__ called {len(eq_counter)} times during section "
            f"detection (e.g. {eq_counter[:3]}). Membership must be by "
            f"identity — see edgartools-llmp.6.10."
        )

    def test_pattern_sections_keep_their_content(self):
        """Identity membership must select the same top-level nodes as before.

        Asserts on the first and last paragraph of each section, so a boundary
        that silently drops the head or tail of the range fails here.
        """
        sections = parse_html(_synthetic_10k(), ParserConfig(form='10-K')).sections

        assert set(sections) == {'business', 'risk_factors', 'mda'}

        business = sections['business'].text()
        assert 'Business paragraph 0 of the filing text.' in business
        assert 'Business paragraph 199 of the filing text.' in business

        risk_factors = sections['risk_factors'].text()
        assert 'Risk factor paragraph 0 of the filing text.' in risk_factors
        assert 'Risk factor paragraph 199 of the filing text.' in risk_factors

        mda = sections['mda'].text()
        assert 'MD&A paragraph 0 of the filing text.' in mda
        assert 'MD&A paragraph 199 of the filing text.' in mda

    def test_no_node_is_added_to_a_section_twice(self):
        """The membership test exists to keep a parent and its children from
        both becoming direct section children. Identity must preserve that."""
        sections = parse_html(_synthetic_10k(), ParserConfig(form='10-K')).sections

        for name, section in sections.items():
            node = getattr(section, 'node', None)
            if node is None:
                continue
            child_ids = [id(child) for child in node.children]
            assert len(child_ids) == len(set(child_ids)), \
                f"section {name} has a duplicated direct child"
