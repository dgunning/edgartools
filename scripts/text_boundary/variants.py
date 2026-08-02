"""Candidate ParagraphNode.text() bodies, installed by monkeypatch for measurement.

Heuristics in the current implementation:
  (1) prev child's 'has_tail_whitespace' metadata
  (2) prev part ends in .!?:; and is not an abbreviation
  (3) allowlist: child original_tag in span/a/em/strong/i/b
Plus the non-heuristic branch: current text starts with a real space.
"""


def _ends_with_tail_whitespace(node) -> bool:
    """Mirror of the shipped helper: walk the rightmost spine for the tail-ws flag."""
    while node is not None:
        if hasattr(node, 'get_metadata') and node.get_metadata('has_tail_whitespace'):
            return True
        children = getattr(node, 'children', None)
        node = children[-1] if children else None
    return False


def _has_left_gap(node) -> bool:
    """The filer drew a word gap with CSS instead of whitespace."""
    style = getattr(node, 'style', None)
    if style is None:
        return False
    return bool((style.padding_left or 0) > 0 or (style.margin_left or 0) > 0)


def _is_marker_box(node):
    """Mirror of the shipped helper: a fixed-width inline-block box holding a marker."""
    style = getattr(node, 'style', None)
    if style is None:
        return False
    return bool(style.display and 'inline-block' in style.display and style.width)


def _same_typeface(a, b):
    fa = getattr(getattr(a, 'style', None), 'font_family', None)
    fb = getattr(getattr(b, 'style', None), 'font_family', None)
    return fa is not None and fa == fb


def _splits_a_word(prev_part, t, prev_child, child):
    '''Inserting here would join two lowercase fragments of one word.'''
    if not (prev_part and prev_part[-1].islower() and t[:1].islower()):
        return False
    if _has_left_gap(child) or _is_marker_box(prev_child):
        return False
    return _same_typeface(prev_child, child)


def make_text(drop_tailws=False, drop_punct=False, drop_allowlist=False, pure_join=False,
              left_gap=False, left_gap_alpha_only=False, no_word_split=False, union=False,
              shallow_tailws=False):
    def text(self) -> str:
        def _generate_text():
            if pure_join:
                return ''.join(c.text() for c in self.children if c.text())
            parts = []
            for i, child in enumerate(self.children):
                t = child.text()
                if not t:
                    continue
                if i == 0:
                    parts.append(t)
                    continue
                prev_child = self.children[i - 1]
                should_add_space = False

                if not drop_tailws and (
                        (hasattr(prev_child, 'get_metadata')
                         and prev_child.get_metadata('has_tail_whitespace'))
                        if shallow_tailws else _ends_with_tail_whitespace(prev_child)):
                    should_add_space = True
                elif t.startswith(' '):
                    should_add_space = True
                    t = t.lstrip()
                elif (not drop_punct) and parts and parts[-1].rstrip()[-1:] in '.!?:;':
                    if not self._is_abbreviation_ending(parts[-1]):
                        should_add_space = True
                # Shipped behaviour plus a CSS-gap branch: the allowlist and the gap test
                # turn out to cover overlapping-but-different sets, so try both.
                elif (union and parts and parts[-1] and not parts[-1].endswith(' ')
                      and (_has_left_gap(child) or _is_marker_box(prev_child)
                           or (t[0].isalpha()
                               and hasattr(child, 'get_metadata')
                               and child.get_metadata('original_tag') in ['span', 'a', 'em', 'strong', 'i', 'b']
                               and not _splits_a_word(parts[-1], t, prev_child, child)))):
                    should_add_space = True
                elif (left_gap and parts and parts[-1] and not parts[-1].endswith(' ')
                      and (t[0].isalpha() if left_gap_alpha_only else True)
                      and (_has_left_gap(child) or _is_marker_box(prev_child))):
                    should_add_space = True
                elif (no_word_split and t and t[0].isalpha()
                      and parts and parts[-1] and not parts[-1].endswith(' ')
                      and hasattr(child, 'get_metadata')
                      and child.get_metadata('original_tag') in ['span', 'a', 'em', 'strong', 'i', 'b']
                      and not _splits_a_word(parts[-1], t, prev_child, child)):
                    should_add_space = True
                elif ((not drop_allowlist) and not left_gap and not no_word_split and not union and t and t[0].isalpha()
                      and parts and parts[-1] and not parts[-1].endswith(' ')
                      and hasattr(child, 'get_metadata')
                      and child.get_metadata('original_tag') in ['span', 'a', 'em', 'strong', 'i', 'b']):
                    should_add_space = True

                if should_add_space:
                    parts.append(' ' + t)
                elif parts:
                    parts[-1] += t
                else:
                    parts.append(t)
            return ''.join(parts)

        return self._get_cached_text(_generate_text)

    return text


VARIANTS = {
    # Shipped behaviour, to confirm the harness reproduces it: expect 0 changed.
    "D_union_allowlist_or_css_gap": dict(union=True),
    # Shipped minus the rightmost-spine tail-whitespace walk: the "lost" count is what
    # that fix restores.
    "E_shallow_tailws": dict(union=True, shallow_tailws=True),
    # What deleting the allowlist would now cost, with the spine fix in place.
    "F_css_gap_only": dict(left_gap=True),
}
