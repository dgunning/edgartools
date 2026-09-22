"""Document nodes compare by identity (edgartools-llmp.10).

`Node` and its subclasses were plain `@dataclass`, so Python generated a
field-by-field `__eq__` that recursed through `parent` and `children`. Every
`==`, `in`, `.index()` and `.remove()` on a node therefore bought a deep
structural walk of the tree where the caller meant identity — 10.5s of
Citigroup's 18s sections stage went to `ParagraphNode.__eq__` alone
(edgartools-llmp.6.10) — and on a deep-copied subtree it did not return at all.

Nothing observable changed when `eq=False` landed: `id` is a uuid compared
first, so distinct nodes were already unequal and a node was already equal to
itself. Identity was the only answer equality could give that was not a crash.
These tests lock that in, including for subclasses added later.
"""
import copy

import pytest

from edgar.documents.nodes import (
    ContainerNode,
    HeadingNode,
    ImageNode,
    LinkNode,
    ListItemNode,
    ListNode,
    Node,
    ParagraphNode,
    SectionNode,
    TextNode,
)
from edgar.documents.table_nodes import TableNode

# Offline: constructs nodes directly, no parsing, filesystem or network.
pytestmark = pytest.mark.fast


def _all_node_classes():
    """Every concrete Node subclass, however deeply nested."""
    seen = {}

    def walk(cls):
        for sub in cls.__subclasses__():
            if sub.__name__ not in seen:
                seen[sub.__name__] = sub
                walk(sub)

    walk(Node)
    return seen


def _paragraph_with_child():
    node = ParagraphNode()
    node.add_child(TextNode(content="x"))
    return node


class TestNoGeneratedEquality:

    def test_no_node_class_generates_eq(self):
        """A new subclass declared with a bare @dataclass would reintroduce this."""
        offenders = [name for name, cls in _all_node_classes().items()
                     if "__eq__" in cls.__dict__]
        assert not offenders, (
            f"these Node subclasses generate __eq__; declare them "
            f"@dataclass(eq=False): {offenders}")

    def test_base_node_does_not_generate_eq(self):
        assert "__eq__" not in Node.__dict__

    @pytest.mark.parametrize("cls", [
        TextNode, ParagraphNode, HeadingNode, ContainerNode, SectionNode,
        ListNode, ListItemNode, LinkNode, ImageNode, TableNode,
    ])
    def test_subclasses_are_hashable(self, cls):
        """eq=True sets __hash__ to None, so nodes were unhashable."""
        node = cls()
        assert hash(node) == hash(node)
        assert len({node, cls()}) == 2


class TestIdentitySemantics:

    def test_node_equals_itself(self):
        node = _paragraph_with_child()
        assert node == node

    def test_structurally_identical_nodes_are_not_equal(self):
        assert _paragraph_with_child() != _paragraph_with_child()

    def test_deep_copy_does_not_recurse_forever(self):
        """deepcopy preserves `id`, so the uuid stopped short-circuiting and the
        walk turned back on itself: parent -> children -> parent."""
        node = _paragraph_with_child()
        clone = copy.deepcopy(node)
        assert clone.id == node.id, "precondition: deepcopy preserves the uuid"
        assert node != clone  # previously RecursionError

    def test_membership_is_identity(self):
        first, second = _paragraph_with_child(), _paragraph_with_child()
        assert first in [second, first]
        assert first not in [second]

    def test_index_finds_the_object_not_a_lookalike(self):
        first, second = TextNode(content="x"), TextNode(content="x")
        assert [first, second].index(second) == 1


class TestChildListOperations:

    def test_remove_child_removes_the_right_one(self):
        parent = ContainerNode()
        first, second = TextNode(content="x"), TextNode(content="x")
        parent.add_child(first)
        parent.add_child(second)

        parent.remove_child(second)

        assert len(parent.children) == 1
        assert parent.children[0] is first
        assert second.parent is None
        assert first.parent is parent

    def test_remove_child_ignores_a_lookalike_from_another_tree(self):
        parent = ContainerNode()
        child = TextNode(content="x")
        parent.add_child(child)

        parent.remove_child(TextNode(content="x"))

        assert parent.children == [child]

    def test_a_node_can_be_added_to_a_set_of_visited_nodes(self):
        """The pattern llmp.6.10 had to write as `{id(n) for n in ...}`."""
        nodes = [_paragraph_with_child() for _ in range(3)]
        visited = set(nodes)
        assert len(visited) == 3
        assert all(node in visited for node in nodes)
