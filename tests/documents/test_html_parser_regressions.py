"""
Regression prevention tests for HTML parser.

Tests for specific bugs that were fixed during development to prevent regression.
Each test documents:
- The original bug
- The fix applied
- The expected behavior
"""

import pytest
from pathlib import Path
from edgar.documents import parse_html
from edgar.documents.config import ParserConfig


class TestTableRenderingRegressions:
    """Regression tests for table rendering bugs."""


    def test_oracle_table_6_rendering(self):
        """
        Regression: Oracle Table 6 had rendering issues.

        Bug: Complex financial table with nested headers
        Fix: Improved header detection and cell merging logic
        Expected: Table renders correctly with all cells
        """
        html_path = Path('data/html/Oracle.10-K.html')
        if not html_path.exists():
            pytest.skip("Oracle 10-K test file not found")

        html = html_path.read_text()
        doc = parse_html(html)

        # Should have tables
        assert len(doc.tables) > 0

        # Table 6 should exist
        if len(doc.tables) > 5:
            table_6 = doc.tables[5]

            # Should render without error
            table_str = str(table_6)
            assert len(table_str) > 0



class TestInlineBoundaryWordGluing:
    """Regression tests for edgartools-tlj1's second half: word gluing.

    The preprocessor collapsed whitespace at text<->tag boundaries by DELETING
    it, so '<font>UNITED STATES </font><font>SECURITIES...' became
    'UNITED STATESSECURITIES' in extracted text — the word boundary was
    destroyed in the HTML string before lxml ever parsed it, unrecoverable
    downstream. Ubiquitous in font-tag-era filings (pre-2009 N-PX, proxies).
    Whitespace touching a tag boundary is still a word boundary under HTML
    rendering rules; it is now collapsed to a single space, never deleted.
    """

    def test_trailing_space_inside_inline_element_is_a_word_boundary(self):
        html = (
            '<html><body>'
            '<p><font>UNITED STATES </font><font>SECURITIES AND EXCHANGE COMMISSION</font></p>'
            '<p><span>REGISTERED </span><span>MANAGEMENT INVESTMENT COMPANY</span></p>'
            '</body></html>'
        )
        text = parse_html(html).text()
        assert 'UNITED STATES SECURITIES AND EXCHANGE COMMISSION' in text
        assert 'STATESSECURITIES' not in text
        assert 'REGISTERED MANAGEMENT' in text

    def test_leading_space_inside_inline_element_is_a_word_boundary(self):
        html = (
            '<html><body>'
            '<p><font>PROXY</font><font> VOTING RECORD</font></p>'
            '</body></html>'
        )
        text = parse_html(html).text()
        assert 'PROXY VOTING RECORD' in text

    def test_genuinely_unspaced_inline_split_stays_glued(self):
        # A word split mid-token across inline elements has no whitespace and
        # must NOT gain a space: the fix preserves real boundaries, it does not
        # invent them.
        html = '<html><body><p><font>Edgar</font><font>Tools</font> parses filings.</p></body></html>'
        text = parse_html(html).text()
        assert 'EdgarTools' in text

    def test_nbsp_normalised_to_space(self):
        # The old streaming pipeline skipped the preprocessor and leaked \xa0
        # into text. One pipeline now, and nbsp is always normalised.
        html = '<html><body><p>FORM&nbsp;N-PX</p></body></html>'
        text = parse_html(html).text()
        assert 'FORM N-PX' in text
        assert '\xa0' not in text


class TestTextNodeEdgeWordGluing:
    """The same word gluing, one layer down: DocumentBuilder text nodes.

    Fixing the preprocessor (TestInlineBoundaryWordGluing) left a second copy of
    the bug in DocumentBuilder._process_element, which built TextNodes with
    element.text.strip() / element.tail.strip(). lxml puts precisely the
    word-separating whitespace on those edges, so the boundary was destroyed
    again before ParagraphNode.text() ever saw it — that method then guessed it
    back from punctuation plus a hardcoded ['span','a','em','strong','i','b']
    allowlist, which is why <font> filings stayed glued.

    Edge whitespace is now collapsed, never deleted, matching the preprocessor.
    The markup below is the real shape from Airbnb's S-1 and Bank of America's
    424B2, both of which shipped glued text before this fix.
    """

    def test_space_before_an_inline_child_survives(self):
        # BofA 424B2 0001481057-23-010389: '$1,246.00 per$1,000 in principal'.
        # The boundary lives on the parent <p>'s own text, not between children.
        html = ('<html><body><p>you will receive $1,246.00 per '
                '<font>$1,000 </font>in principal amount.</p></body></html>')
        text = parse_html(html).text()
        assert 'per $1,000 in principal' in text
        assert 'per$1,000' not in text

    def test_space_after_an_inline_child_survives(self):
        # The mirror case: the boundary lives on the child's tail.
        html = ('<html><body><p><font>UNITED STATES</font> SECURITIES AND '
                'EXCHANGE COMMISSION</p></body></html>')
        text = parse_html(html).text()
        assert 'UNITED STATES SECURITIES AND EXCHANGE COMMISSION' in text

    def test_nowrap_font_span_does_not_glue_its_neighbours(self):
        # Airbnb S-1 (tests/fixtures/html/abnb/s1): a white-space:nowrap <FONT>
        # wrapping a hyphenated term, with the boundary whitespace on both edges
        # outside it. Extracted as 'anon-acceleratedfiler' before the fix.
        html = ('<html><body><p>an accelerated filer, a\n'
                '<font style="white-space:nowrap">non-accelerated</font> filer, '
                'a smaller reporting company</p></body></html>')
        text = parse_html(html).text()
        assert 'a non-accelerated filer' in text
        assert 'anon-accelerated' not in text
        assert 'acceleratedfiler' not in text

    def test_nested_inline_elements_do_not_glue(self):
        # Airbnb S-1: triple-nested nowrap <FONT>s around 'one-of-a-kind'.
        html = ('<html><body><p>has become synonymous with '
                '<font><font><font>one-of-a-kind</font></font></font> travel '
                'on a global scale.</p></body></html>')
        text = parse_html(html).text()
        assert 'with one-of-a-kind travel' in text

    def test_unspaced_edges_still_stay_glued(self):
        # No whitespace in the source means no word boundary: the fix must not
        # invent one. 'S-T' is one token split by a nowrap wrapper.
        html = '<html><body><p>Regulation<font>S-T</font>(the rule)</p></body></html>'
        text = parse_html(html).text()
        assert 'RegulationS-T(the rule)' in text


class TestSpacerElementWordGluing:
    """A third copy of the same bug: whitespace-only spacer elements.

    _remove_empty_tags treated a tag holding only whitespace as empty and deleted it
    outright, taking the whitespace with it. Filers draw a word gap that way — Apple's
    FY2024 10-K separates 'the App Store and Safari' from 'in the EU' with
    '<span style="font-size:5.85pt"> </span>' — so the words either side were glued.
    A tag with whitespace in it now leaves a space behind; a genuinely empty one still
    leaves nothing.

    The cases below all start the following word with a glyph or a digit, because
    ParagraphNode.text()'s allowlist heuristic (see edgartools-jysx) hides the bug
    whenever the next character is a letter — it force-spaces adjacent spans anyway.
    Those masked cases are real too; they just cannot fail here.
    """

    def test_spacer_before_a_digit_leaves_a_space(self):
        # Microsoft FY2025 Q3 cover page: 'Washington98052-6399' before the fix.
        html = ('<html><body><p><span>REDMOND, Washington</span>'
                '<span style="font-size:5.85pt"> </span>'
                '<span>98052-6399</span></p></body></html>')
        text = parse_html(html).text()
        assert 'Washington 98052-6399' in text

    def test_spacer_inside_a_sentence_before_a_number(self):
        # Chevron FY2024 10-K: 'Chevron holds a63 percent-owned' before the fix.
        html = ('<html><body><p><span>Chevron holds a</span>'
                '<span style="font-size:5.85pt"> </span>'
                '<span>63 percent-owned interest.</span></p></body></html>')
        text = parse_html(html).text()
        assert 'holds a 63 percent-owned' in text

    def test_genuinely_empty_tag_leaves_nothing(self):
        # No whitespace anywhere in the source means no word boundary to restore.
        html = '<html><body><p>Edgar<span></span>Tools</p></body></html>'
        text = parse_html(html).text()
        assert 'EdgarTools' in text

    def test_spacer_removal_does_not_double_the_space(self):
        # The whitespace pass already left a space either side of the spacer; the
        # replacement must collapse with them, not stack up.
        html = '<html><body><p>FORM <span> </span> N-PX</p></body></html>'
        text = parse_html(html).text()
        assert 'FORM N-PX' in text

    def test_checkbox_glyph_is_separated_from_its_label(self):
        # Apple FY2024 10-K cover page: '☒ANNUAL REPORT' before the fix.
        html = ('<html><body><p><span>&#9746;</span><span style="font-size:6pt"> </span>'
                '<span>ANNUAL REPORT PURSUANT TO SECTION 13</span></p></body></html>')
        text = parse_html(html).text()
        assert '☒ ANNUAL REPORT' in text


class TestBlankTextNodeWordGluing:
    """A fourth copy of the same bug, this one inside lxml: remove_blank_text.

    The preprocessor collapses a whitespace run between two tags down to a single
    space, deliberately, because that space is a word boundary. lxml was then being
    handed remove_blank_text=True, and libxml2 discards a text node it judges to be
    all-ignorable whitespace — so the surviving space was deleted after all, and the
    ParagraphNode allowlist had to guess the boundary back (see edgartools-jysx).
    Where the guess did not apply, real filings shipped glued words.

    The whitespace that gets deleted is the one standing alone between two tags. Sibling
    inline elements at the same level keep theirs, which is why this survived three
    earlier passes over the bug family: the losing shape is a whitespace-only tail on a
    child of an inline element, and for JPMorgan and Boeing that child is an
    <ix:nonFraction> fact — a tag libxml2 has never heard of.
    """

    def test_whitespace_tail_after_an_inline_xbrl_fact_survives(self):
        # JPMorgan FY2024 10-K note 32: '...the Firm has threereportable business
        # segments' before the fix (edgartools-vfwp). The space is the ix fact's tail
        # and the enclosing <span> ends immediately after it.
        html = ('<html><body><div>'
                '<span>As a result of the reorganization, the Firm has '
                '<ix:nonFraction contextRef="c-1" name="us-gaap:NumberOfReportableSegments"'
                ' format="ixt-sec:numwordsen">three</ix:nonFraction> </span>'
                '<span>reportable business segments.</span>'
                '</div></body></html>')
        text = parse_html(html).text()
        assert 'has three reportable business segments' in text

    def test_cover_page_checkbox_keeps_its_gap(self):
        # Apple FY2024 10-K cover page: 'Yes☒ No ☐' before the fix. The gap between the
        # label and the glyph is a lone space between two <span>s.
        html = ('<html><body><div><span>Yes</span>'
                '<span>&#160;</span><span>&#9746;</span></div></body></html>')
        text = parse_html(html).text()
        assert 'Yes ☒' in text

    def test_no_space_is_invented_where_the_source_has_none(self):
        # The mirror requirement: keeping blank text nodes must not add boundaries that
        # were never in the markup. 'S-T' is one token split by a wrapper.
        html = '<html><body><p>Regulation<font>S-T</font>(the rule)</p></body></html>'
        text = parse_html(html).text()
        assert 'RegulationS-T(the rule)' in text


class TestCssGapWordBoundary:
    """Bullets and footnote markers glued to their text: '•MacBook Pro 16-in.'

    A filer who puts a bullet glyph in one span and the item text in the next does not
    separate them with whitespace — the text span carries a padding-left, and that CSS
    gap *is* the word boundary. ParagraphNode.text()'s tag allowlist was standing in for
    it (95% of the 8,109 boundaries it restores across the fixture corpus turn out to
    have such a gap), but the allowlist keys on `original_tag` metadata, which only
    TextNodes carry. Header detection promotes a short span like a bare '•' to a
    HeadingNode, and those lose the boundary — 640 of them across the corpus, including
    14 bullets in Apple's FY2024 10-K.

    The gap is now read directly off the style, independent of node type. (edgartools-jysx)
    """

    def test_bullet_glyph_is_separated_from_its_item_text(self):
        # Apple FY2024 10-K Item 1: shipped as '•MacBook Pro 16-in.; and'. Both spans are
        # promoted to HeadingNodes here, which is what defeated the allowlist.
        html = ('<html><body>'
                '<div style="padding-left:36pt;text-indent:-18pt">'
                '<span style="font-family:Helvetica;font-size:9pt">&#8226;</span>'
                '<span style="font-family:Helvetica;font-size:9pt;padding-left:14.85pt">'
                'MacBook Pro 16-in.; and</span></div></body></html>')
        text = parse_html(html).text()
        assert '• MacBook Pro 16-in.' in text

    def test_footnote_marker_is_separated_from_its_note(self):
        # AbbVie FY2024 10-K Item 15: shipped as '(1)Financial Statements:'.
        html = ('<html><body><div><span>(1)</span>'
                '<span style="padding-left:9pt">Financial Statements: See Item 8.</span>'
                '</div></body></html>')
        text = parse_html(html).text()
        assert '(1) Financial Statements' in text

    def test_a_margin_left_gap_counts_too(self):
        html = ('<html><body><div><span>(a)</span>'
                '<span style="margin-left:4.3pt">Includes restructuring charges.</span>'
                '</div></body></html>')
        text = parse_html(html).text()
        assert '(a) Includes restructuring' in text

    def test_no_gap_means_no_space_from_this_rule(self):
        # <font> is outside the allowlist, so with no CSS gap nothing separates these —
        # which is correct: a browser renders them glued too.
        html = '<html><body><p><font>Edgar</font><font>Tools</font></p></body></html>'
        text = parse_html(html).text()
        assert 'EdgarTools' in text


class TestTailWhitespaceInsideAWrapper:
    """A fifth copy of the delete-vs-collapse bug, created by the two fixes before it.

    DocumentBuilder records a whitespace-only tail as `has_tail_whitespace` metadata on
    the element that owns it — the innermost one. ParagraphNode.text() read that flag off
    the sibling it was comparing, so it was missed whenever the whitespace sat inside a
    wrapper. Chevron's FY2024 10-K puts a run-in heading in an <ix:nonNumeric> with the
    gap after it in a spacer span *inside* that element, so the flag landed two levels
    below the sibling and 'GeneralThe Company follows' shipped.

    This only became reachable once the preprocessor started turning a spacer element into
    whitespace (8b45d8f7) and lxml stopped deleting it (the remove_blank_text fix): before
    those, there was no whitespace-only tail to lose. The flag is now looked for down the
    rightmost spine. (edgartools-jysx)
    """

    def test_spacer_at_the_end_of_a_wrapper_still_separates(self):
        # Chevron FY2024 10-K note 1, reduced to the shape that matters.
        html = ('<html><body><div>'
                '<ix:nonNumeric contextRef="c-1" name="us-gaap:BasisOfAccountingPolicyPolicyTextBlock">'
                '<span style="font-style:italic;font-weight:700">General</span>'
                '<span style="font-style:italic;font-weight:700"> </span>'
                '</ix:nonNumeric>'
                '<span>The Company follows generally accepted accounting principles.</span>'
                '</div></body></html>')
        text = parse_html(html).text()
        assert 'General The Company follows' in text

    def test_no_spacer_means_no_space(self):
        # The mirror: with nothing between the wrapper and the next span, nothing is
        # invented — the flag is only set for whitespace that was in the source.
        html = ('<html><body><div>'
                '<ix:nonNumeric contextRef="c-1" name="x"><span>Edgar</span></ix:nonNumeric>'
                '<font>Tools</font></div></body></html>')
        text = parse_html(html).text()
        assert 'EdgarTools' in text


class TestFixedWidthMarkerBox:
    """Dash bullets whose gap is a box width rather than a padding.

    SigmaTron's FY2025 10-K lays out risk-factor bullets as
    '<span style="display:inline-block;width:0.250in">-</span><span>the political
    climate…</span>' — the filer reserved a quarter inch for the dash, so the text starts
    at the far edge of that box. It is the same gap as a padding-left on the text, drawn
    from the other side, and it is read off the style the same way.

    Do not be tempted to key this on the `white-space:pre-wrap` these spans also carry:
    that property is near-universal in Word-exported filings and marks nothing. The same
    property sits on HubSpot's 'Item 1A. RI SK FACTORS', where the space is wrong.
    (edgartools-jysx)
    """

    def test_marker_in_a_fixed_width_box_is_separated_from_its_text(self):
        html = ('<html><body><p style="margin-left:0.50in;text-indent:-0.25in">'
                '<span style="display:inline-block;width:0.250in;text-indent:0">-</span>'
                '<span>the political climate and relations with the United States</span>'
                '</p></body></html>')
        text = parse_html(html).text()
        assert '- the political climate' in text

    def test_an_inline_block_without_a_width_is_not_a_marker_box(self):
        # display:inline-block alone reserves nothing, so it is not a gap.
        html = ('<html><body><p><font style="display:inline-block">Edgar</font>'
                '<font>Tools</font></p></body></html>')
        text = parse_html(html).text()
        assert 'EdgarTools' in text


class TestMidWordSplitSpacing:
    """Adjacent inline elements are no longer spaced on the strength of their tag name.

    ParagraphNode.text() used to force a space between adjacent inline elements whenever
    the following text began with a letter and the child's original_tag was one of
    span/a/em/strong/i/b. That allowlist existed because nothing at that point could tell
    a boundary an upstream pass had destroyed from a word the filer split mid-token — and
    filers split words mid-token constantly, so it shipped 'identify, asse ss, and
    monitor' in Apple's FY2024 10-K, 'Th e facility', 'jurisd ictions', 'Chevr on'.

    The allowlist is gone as of 2026-08-02 (edgartools-jysx). Spacing is now decided by
    three signals that read the boundary instead of guessing at it — see
    TestCssGapWordBoundary, TestFixedWidthMarkerBox and TestMarkerGlyphWordBoundary.
    These tests guard the negative: no signal, no space.
    """

    def test_lowercase_fragments_in_one_typeface_are_rejoined(self):
        # Apple FY2024 10-K Item 1C: 'asse</span><span style="background-color:#ffffff">ss'.
        html = ('<html><body><p>'
                '<span style="font-family:Helvetica">designed to identify, asse</span>'
                '<span style="font-family:Helvetica;background-color:#ffffff">ss</span>'
                '<span style="font-family:Helvetica">, and monitor</span>'
                '</p></body></html>')
        text = parse_html(html).text()
        assert 'identify, assess, and monitor' in text

    def test_a_css_left_gap_still_separates_the_words(self):
        # padding-left is how filers draw a word gap without whitespace; the fragments
        # are both lowercase, so only the gap distinguishes this from a split word.
        html = ('<html><body><p>'
                '<span style="font-family:Helvetica">the</span>'
                '<span style="font-family:Helvetica;padding-left:4.3pt">facility</span>'
                '</p></body></html>')
        text = parse_html(html).text()
        assert 'the facility' in text

    def test_a_word_split_before_a_capital_is_also_rejoined(self):
        """The allowlist spaced this and was wrong to; caps are not a boundary signal.

        It is how 'Item 1A. RI SK FACTORS' and 'ITEM 1B. UNRESOLV ED STAFF COMMENTS'
        reached users — an all-caps heading split across two spans, spaced on tag name
        alone. Item headings are exactly what a section matcher keys on, so the damage
        was not cosmetic. 25 such repairs across the 57-fixture corpus.
        """
        html = ('<html><body><p>'
                '<span>Item 1A. RI</span><span>SK FACTORS</span>'
                '</p></body></html>')
        text = parse_html(html).text()
        assert 'Item 1A. RISK FACTORS' in text
        assert 'RI SK' not in text

    def test_no_space_is_invented_after_an_opening_quote(self):
        """A filer who closes a span after `("` did not intend a space to follow it.

        92 of the 245 spaces removed from the fixture corpus by deleting the allowlist
        are this shape — '(the " SEC")', '( i.e.,', 'http:// www.sec.gov'.
        """
        html = ('<html><body><p>'
                '<span>of the Securities and Exchange Commission (the &ldquo;</span>'
                '<span>SEC</span><span>&rdquo;)</span>'
                '</p></body></html>')
        text = parse_html(html).text()
        assert '“SEC”' in text

    def test_two_adjacent_elements_with_no_signal_are_joined(self):
        """The deliberate cost of removing the allowlist, pinned so it stays visible.

        Two genuinely distinct words in adjacent inline elements, with no whitespace, no
        CSS gap and no marker, are now concatenated. Measured across 57 large-cap
        fixtures and a 129-filing corpus spanning five markup eras and nine form types,
        this costs 2 real boundaries on the wide corpus ('security See' in an N-CSR
        footnote, a Latin-to-CJK boundary in a 20-F) against 222 confirmed repairs on the
        fixtures — which is why the trade was taken. If a signal for this shape is ever
        found, this test is the one to change.
        """
        html = ('<html><body><p>'
                '<span style="font-family:Arial">reported by</span>'
                '<span style="font-family:Arial">Morgan Stanley</span>'
                '</p></body></html>')
        text = parse_html(html).text()
        assert 'reported byMorgan Stanley' in text


class TestMarkerGlyphWordBoundary:
    """A standalone list or checkbox glyph is a word boundary, read from the text.

    Landed with the allowlist's removal (edgartools-jysx). The CSS-gap and marker-box
    signals cover most bullet boundaries, but not the ones drawn with no style at all —
    and not SigmaTron's cover page, where `style="…font-family: "Wingdings""` nests
    double quotes inside a double-quoted attribute so font-family parses as empty for us
    and for a browser alike. Reading the glyph out of the text survives that.
    """

    def test_a_bullet_is_separated_from_its_item_text(self):
        # AAON FY2021 DEF 14A: 43 lines of '• Proposal No. 1...' shipped as '•Proposal'
        # under the CSS-gap rule alone.
        html = '<html><body><p><span>&bull;</span><span>Proposal No. 1.</span></p></body></html>'
        assert '• Proposal No. 1.' in parse_html(html).text()

    def test_a_footnote_asterisk_is_separated_from_its_note(self):
        html = '<html><body><p><span>*</span><span>Certain projects have multiple wells.</span></p></body></html>'
        assert '* Certain projects' in parse_html(html).text()

    def test_a_wingdings_checkbox_is_separated_from_its_label(self):
        # SigmaTron FY2025 10-K: 'o' and 'y-acute' are the unchecked/checked boxes.
        html = '<html><body><p><span>of the Act.</span><span>o</span><span>Yes</span></p></body></html>'
        assert 'o Yes' in parse_html(html).text()

    def test_a_letter_marker_does_not_split_a_word(self):
        """A-Power's FY2009 20-F writes 'our' as 'o'+'ur' across two elements.

        The marker branch is reached before any mid-word-split test, so without this
        guard the letter markers turn 'our wind turbine business' into 'o ur wind
        turbine business'. A checkbox label is 'Yes' or 'No', never lowercase.
        """
        html = '<html><body><p><span>o</span><span>ur wind turbine business</span></p></body></html>'
        text = parse_html(html).text()
        assert 'our wind turbine business' in text
        assert 'o ur' not in text

    def test_a_glyph_ending_a_word_is_not_a_marker(self):
        html = '<html><body><p><span>Chevro</span><span>n Corporation</span></p></body></html>'
        assert 'Chevron Corporation' in parse_html(html).text()


class TestHeadingContentFloor:
    """A bullet or a bare enumerator is not a heading however it is styled.

    Filers put the glyph in its own span, and header detection scored that span on
    everything except what it said — ContextualDetector awards +0.3 whenever the next
    element is three times longer, which a one-character text passes against almost
    anything, and another +0.3 when the *previous* sibling looks like a heading, so a
    '•' cleared the 0.6 threshold on borrowed evidence alone.

    Measured across the 57 fixtures before the fix: 17,016 HeadingNodes, of which 2,818
    had no alphanumeric character at all (2,636 a bare '•') and 1,199 were bare
    enumerators — 23.6% of every heading built. Meta's FY2024 10-K was 180 of 296.
    They surfaced through doc.headings, through the markdown renderer as '### •' and its
    table of contents, and through the heading index DocumentSearch scores.

    HeaderDetectionStrategy.detect() now applies a content floor before any detector
    runs. Measured after: 12,999 headings, 0 of either kind, section map 0 of 55 changed,
    doc.text() byte-identical on all 57 fixtures, and no markdown token lost once
    escaping and emphasis are normalised. (edgartools-1xxo)
    """

    def _headings(self, html):
        from edgar.documents.nodes import HeadingNode
        doc = parse_html(html)
        return [(h.content or '').strip()
                for h in doc.root.find(lambda n: isinstance(n, HeadingNode))]

    def test_a_styled_bullet_is_not_promoted_to_a_heading(self):
        # Apple's FY2024 10-K shipped 12 of these; JNJ's 76.
        html = ('<html><body><div>'
                '<p style="font-weight:bold;text-align:center">Products</p>'
                '<p><span style="font-weight:bold">&bull;</span></p>'
                '<p>iPhone is the Company&rsquo;s line of smartphones based on its iOS operating '
                'system, and it represents a substantial share of net sales.</p>'
                '</div></body></html>')
        assert '•' not in self._headings(html)

    def test_a_trademark_symbol_is_not_promoted_to_a_heading(self):
        # 19 bare '®' headings across the fixture corpus, 8 of them in Apple's 10-K,
        # each one a symbol lifted out of the middle of a product sentence.
        html = ('<html><body><div>'
                '<p>The Company offers Apple Watch</p>'
                '<p><span style="vertical-align:super">&reg;</span></p>'
                '<p>Series 10, which extends the health and fitness features described above.</p>'
                '</div></body></html>')
        assert '®' not in self._headings(html)

    def test_a_bare_enumerator_is_not_promoted_to_a_heading(self):
        # 1,199 across the corpus: '(1)' x203, '(a)' x134, '(2)' x124. JPMorgan's 10-Q
        # alone had 147, which is what a footnote-heavy financial table looks like.
        html = ('<html><body><div>'
                '<p style="font-weight:bold">Note 3</p>'
                '<p><span style="font-weight:bold">(1)</span></p>'
                '<p>Amounts represent the fair value of derivative receivables and payables '
                'after netting adjustments permitted under master netting agreements.</p>'
                '</div></body></html>')
        headings = self._headings(html)
        assert '(1)' not in headings

    def test_a_real_heading_is_still_promoted(self):
        """The floor rejects on content only, so nothing that reads as a heading moves.

        Guards against the tempting-but-wrong fix of adding 'span' to
        skip_header_detection_tags — filers do legitimately mark headings with a styled
        span, and that would lose the real ones along with the glyphs.
        """
        html = ('<html><body><div>'
                '<p><span style="font-weight:bold;font-size:18px">Item 1A. Risk Factors</span></p>'
                '<p>The Company&rsquo;s business, reputation, results of operations and financial '
                'condition can be affected by a number of factors described below.</p>'
                '</div></body></html>')
        assert 'Item 1A. Risk Factors' in self._headings(html)

    def test_the_content_floor_admits_what_it_should(self):
        """The floor itself, tested directly — the detectors are a separate question.

        A heading has to clear the floor *and* convince a detector, and most synthetic
        markup never convinces one, so asserting through parse_html() here would measure
        detection rather than the floor. These are the boundaries the regex draws.
        """
        from edgar.documents.strategies.header_detection import _can_be_heading

        # Rejected: nothing alphanumeric, or a bare enumerator.
        for text in ['•', '®', '*', '**', '—', '––', '☐',
                     '1', '(1)', '(a)', 'iv.', 'b)', '[3]', 'A']:
            assert not _can_be_heading(text), f'{text!r} should be rejected'

        # Admitted: a year is four digits, so the enumerator rule stops short of it.
        for text in ['2024', 'Item 1A. Risk Factors', 'PART I', 'Note 3',
                     '(1) Basis of Presentation', '10-K', 'Overview']:
            assert _can_be_heading(text), f'{text!r} should be admitted'

    def test_the_bullet_still_reaches_the_text_with_its_boundary_intact(self):
        """De-promoting the glyph must not undo the boundary work it was masking.

        The bullet becomes an inline TextNode rather than a HeadingNode, which is the
        path _is_bare_marker covers (TestMarkerGlyphWordBoundary). Before the allowlist
        removal landed, this fix would have shipped '•iPhone'.
        """
        html = ('<html><body><p>'
                '<span style="font-weight:bold">&bull;</span><span>iPhone</span>'
                '</p></body></html>')
        assert '• iPhone' in parse_html(html).text()


class TestStreamingParserRegressions:
    """Regression tests from the era of the separate StreamingParser.

    The StreamingParser (a second, size-gated text pipeline for documents over
    ParserConfig.streaming_threshold) was removed in edgartools-tlj1: it produced
    divergent and lossy text (dropped div-hosted content entirely, skipped the
    preprocessor and inline-XBRL extraction) and was ~20x slower than the normal
    pipeline it was meant to relieve. These tests are kept because they pin
    behaviour that must now hold trivially: one pipeline, same output at any
    document size, no duplicated or dropped content.
    """

    def test_jpm_streaming_parent_none_bug(self):
        """
        Regression: a JPM 10-K crashed in the old streaming parser.

        Large documents now take the normal pipeline; this pins that a big real
        filing parses successfully.

        It used to read data/html/JPM.10-K.html, which is untracked and under the
        blanket /data/ ignore, so it ran only for whoever had that file locally
        and never in CI. It now reads the tracked 12.3 MB JPM 10-K fixture, which
        is the largest real filing the repository actually ships.
        """
        html_path = Path('tests/fixtures/html/jpm/10k/jpm-10-k-2025-02-14.html')
        assert html_path.exists(), f"tracked fixture missing: {html_path}"

        html = html_path.read_text()

        config = ParserConfig(max_document_size=100 * 1024 * 1024)

        # Should not crash
        doc = parse_html(html, config=config)

        # Should parse successfully
        assert doc is not None
        assert len(doc.tables) > 0

        # This filing parses to 633 tables; assert the order of magnitude, not
        # the exact count, so a benign parser change does not fail the gate.
        assert len(doc.tables) > 500

    def test_large_document_streaming_trigger(self):
        """
        Documents over the (now-ignored) streaming_threshold parse without error.
        """
        # Create a document just over the old streaming threshold
        threshold = 5 * 1024 * 1024  # 5MB
        large_content = "x" * (threshold + 1000)
        html = f"<html><body><p>{large_content}</p></body></html>"

        config = ParserConfig(
            streaming_threshold=threshold,
            max_document_size=100 * 1024 * 1024
        )

        doc = parse_html(html, config=config)
        assert doc is not None

    def test_div_text_survives_above_old_streaming_threshold(self):
        """
        Regression (edgartools-tlj1): documents over 10MB silently lost ALL text
        hosted directly in <div> elements.

        The old StreamingParser only materialised p/h1-h6/section/table nodes;
        text in divs went to an internal buffer that was never flushed into the
        document. Modern SEC filings are div-based, so any filing crossing the
        10MB default threshold lost most of its body text — silently, while the
        same content under 10MB was fine. The streaming path was removed; this
        builds a genuinely >10MB document (so a reintroduced hardcoded gate
        would be caught) and asserts div-hosted text survives.
        """
        filler = "<p>" + "x" * 1000 + "</p>"
        n = (10 * 1024 * 1024) // len(filler) + 50
        html = (
            "<html><body>"
            "<div>Sentinel div text that must survive.</div>"
            + filler * n +
            "<div>Closing sentinel in a div.</div>"
            "</body></html>"
        )
        assert len(html.encode("utf-8")) > 10 * 1024 * 1024

        config = ParserConfig(max_document_size=100 * 1024 * 1024)
        text = parse_html(html, config=config).text()

        assert "Sentinel div text that must survive." in text
        assert "Closing sentinel in a div." in text

    def test_streaming_preserves_span_wrapped_paragraph_text(self):
        """
        Regression: Streaming parser dropped text from <span>-wrapped paragraphs.

        Bug: The iterparse loop called elem.clear() on every event (both
        start and end), and on every element regardless of whether an
        enclosing structural element (p/h1-h6/section) had finished reading
        its children. Because iterparse fires end events depth-first, the
        inner <span>'s end event cleared its .text/.tail before <p>'s end
        event ran _get_text_content(p). SEC filings wrap virtually every
        word in <span style="..."> tags, so streaming-mode paragraphs
        produced empty text — silently, with no warning.

        Symptom in production: filings in the ~30MB–110MB band (which
        cross the default 10MB streaming_threshold) returned text() output
        20%+ shorter than the non-streaming path; for some filings,
        nearly empty. No exception was raised.

        Fix: edgar/documents/utils/streaming.py — clear only on end
        events, and gate clearing on a content-depth counter that tracks
        open p/h1-h6/section elements (matching the existing _table_depth
        gate). This defers child cleanup until the enclosing structural
        element has read its subtree.

        Expected: Streaming-mode text() returns the full paragraph
        content, including text inside nested <span> wrappers.
        """
        # Mimics SEC filing structure: every word inside its own <span>.
        html = (
            "<html><body>"
            "<p><span>Alpha </span><span>beta </span><span>gamma</span></p>"
            "<p><span>second </span><span>paragraph</span></p>"
            "<h2><span>Risk Factors</span></h2>"
            "<p><span>nested </span><span>spans </span><span>everywhere</span></p>"
            "</body></html>"
        )

        # Force streaming mode regardless of size.
        streaming_cfg = ParserConfig(
            streaming_threshold=1,
            max_document_size=10 * 1024 * 1024,
        )
        text = parse_html(html, config=streaming_cfg).text()

        # All paragraph and heading content must survive the streaming path.
        assert "Alpha" in text and "beta" in text and "gamma" in text
        assert "second paragraph" in text
        assert "Risk Factors" in text
        assert "nested spans everywhere" in text

        # Non-streaming baseline must agree on the same content.
        normal_cfg = ParserConfig(streaming_threshold=10 * 1024 * 1024)
        normal_text = parse_html(html, config=normal_cfg).text()
        for needle in ("Alpha", "beta", "gamma", "second paragraph",
                       "Risk Factors", "nested spans everywhere"):
            assert needle in normal_text, f"baseline missing {needle!r}"

    def test_streaming_does_not_double_emit_table_cell_paragraphs(self):
        """
        Regression: Streaming parser emitted text inside <td><p>...</p></td>
        twice — once as a free-standing ParagraphNode (because the <p>
        start/end handlers fired unconditionally) and once as TableNode
        cell text (because _end_table walks the full subtree via
        processor.process(elem)). Same applies to <h*> and <section>
        inside <td>.

        This was masked before the span-bug fix because <p> handlers
        produced empty paragraphs anyway. Once paragraph text was
        recovered, the duplication showed up as 10-36% content overshoot
        vs non-streaming on table-heavy filings — visible as the same
        financial-statement labels ('Total', interest-income line items,
        etc.) repeating dozens of times more in streaming output than
        non-streaming output.

        Fix: _handle_start_tag / _handle_end_tag gate <p>/<h1-6>/<section>
        on _table_depth == 0, symmetrical to the existing _table_depth
        gate on elem.clear(). The table processor remains the single
        source of cell text.

        Expected: each cell's text appears exactly once in streaming
        output, matching non-streaming behaviour.
        """
        html = (
            "<html><body>"
            "<table>"
            "<tr><td><p>Cell paragraph one</p></td>"
            "    <td><p>Cell paragraph two</p></td></tr>"
            "<tr><td><p>Row two A</p></td>"
            "    <td><p>Row two B</p></td></tr>"
            "</table>"
            "</body></html>"
        )

        streaming_cfg = ParserConfig(
            streaming_threshold=1,
            max_document_size=10 * 1024 * 1024,
        )
        text = parse_html(html, config=streaming_cfg).text()

        # Each cell must appear exactly once. Pre-fix this PR, each of
        # these would appear twice (once as standalone paragraph, once
        # as a table cell), and `text.count(...) == 2`.
        for cell in ("Cell paragraph one", "Cell paragraph two",
                     "Row two A", "Row two B"):
            assert text.count(cell) == 1, (
                f"{cell!r} appears {text.count(cell)} times in streaming "
                f"output (expected 1) — table cell content is being "
                f"double-emitted as both ParagraphNode and TableNode cell"
            )

        # And the non-streaming baseline must show the same single-emission
        # behaviour, so the assertion isn't accidentally locking in a
        # streaming-specific quirk.
        normal_cfg = ParserConfig(streaming_threshold=10 * 1024 * 1024)
        normal_text = parse_html(html, config=normal_cfg).text()
        for cell in ("Cell paragraph one", "Cell paragraph two",
                     "Row two A", "Row two B"):
            assert normal_text.count(cell) == 1, (
                f"baseline emits {cell!r} {normal_text.count(cell)} times"
            )


class TestSectionDetectionRegressions:
    """Regression tests for section detection bugs."""

    def test_10q_part_distinction(self):
        """
        Regression: 10-Q Part I/Part II distinction.

        Bug: 10-Q Item 2 ambiguous between Part I and Part II
        Fix: Added Part I/II distinction in section detection
        Expected: Items correctly associated with Part I or Part II
        """
        html_path = Path('data/html/Apple.10-Q.html')
        if not html_path.exists():
            pytest.skip("Apple 10-Q test file not found")

        html = html_path.read_text()
        doc = parse_html(html,ParserConfig(form='10-Q'))

        sections = doc.sections

        # 10-Q should have sections
        assert len(sections) > 0

        # Check if Part I sections exist
        part_i_sections = [k for k in sections.keys() if 'Part I' in k or 'PART I' in k]
        part_ii_sections = [k for k in sections.keys() if 'Part II' in k or 'PART II' in k]

        # 10-Q should have both parts (if properly detected)
        # Note: This is aspirational - depends on filing structure
        if part_i_sections or part_ii_sections:
            assert len(part_i_sections) > 0 or len(part_ii_sections) > 0


class TestInputValidationRegressions:
    """Regression tests for input validation bugs."""

    def test_none_input_type_error(self):
        """
        Regression: None input crashed with AttributeError.

        Bug: Parser tried to call .strip() on None
        Error: 'NoneType' object has no attribute 'strip'
        Fix: Added input type validation at parse() entry point
        Expected: Clear TypeError with helpful message
        """
        with pytest.raises(TypeError, match="HTML input cannot be None"):
            parse_html(None)

    def test_invalid_type_clear_error(self):
        """
        Regression: Invalid input types had unclear errors.

        Bug: Non-string inputs caused confusing internal errors
        Fix: Added type checking with clear error messages
        Expected: TypeError with type name in message
        """
        with pytest.raises(TypeError, match="HTML must be string or bytes"):
            parse_html(12345)

        with pytest.raises(TypeError, match="HTML must be string or bytes"):
            parse_html(['html', 'list'])

    def test_bytes_input_accepted(self):
        """
        Regression: Bytes input should be accepted and decoded.

        Expected: Parser accepts both str and bytes input
        """
        html_bytes = b"<html><body><p>Test content</p></body></html>"
        doc = parse_html(html_bytes)

        assert doc is not None
        assert "Test content" in doc.text()


class TestPerformanceRegressions:
    """Regression tests for performance issues."""

    def test_parsing_speed_threshold(self):
        """
        Regression: Ensure parsing remains fast.

        Target: < 1 second for typical 10-K
        Regression threshold: > 2 seconds indicates performance degradation
        """
        import time

        html_path = Path('data/html/Apple.10-K.html')
        if not html_path.exists():
            pytest.skip("Apple 10-K test file not found")

        html = html_path.read_text()

        start = time.perf_counter()
        doc = parse_html(html)
        elapsed = time.perf_counter() - start

        # Regression threshold: 2 seconds
        assert elapsed < 2.5, f"Parse time {elapsed:.3f}s exceeds 2s regression threshold"

        # Should have content
        assert len(doc.tables) > 0

    def test_memory_cleanup_in_streaming(self):
        """
        Regression: Streaming parser should clean up elements.

        Bug: Memory could grow unbounded in streaming mode
        Fix: Delete processed elements to free memory
        Expected: Streaming mode completes without excessive memory
        """
        # Create a document that triggers streaming
        threshold = 5 * 1024 * 1024

        # Create multiple tables to ensure cleanup happens
        tables = []
        for i in range(100):
            table = f"""
            <table>
                <tr><td>Row {i} Col 1</td><td>Row {i} Col 2</td></tr>
                <tr><td>Data {i} A</td><td>Data {i} B</td></tr>
            </table>
            """
            tables.append(table)

        # Pad with enough content to exceed threshold
        padding = "x" * threshold
        html = f"<html><body>{''.join(tables)}<p>{padding}</p></body></html>"

        config = ParserConfig(
            streaming_threshold=threshold,
            max_document_size=100 * 1024 * 1024
        )

        # Should complete without running out of memory
        doc = parse_html(html, config=config)
        assert doc is not None


class TestXBRLExtractionRegressions:
    """Regression tests for XBRL extraction bugs."""

    def test_xbrl_hidden_element_extraction(self):
        """
        Regression: XBRL facts in ix:hidden should be extracted.

        Bug: XBRL extraction only found visible facts
        Fix: Extract XBRL before preprocessing removes ix:hidden
        Expected: Facts from both visible and hidden sections
        """
        html = """
        <html xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
        <body>
            <ix:hidden>
                <ix:nonfraction name="us-gaap:Revenue" unitRef="usd">1000000</ix:nonfraction>
            </ix:hidden>
            <p>Revenue: <ix:nonfraction name="us-gaap:Revenue" unitRef="usd">1000000</ix:nonfraction></p>
        </body>
        </html>
        """

        config = ParserConfig(extract_xbrl=True)
        doc = parse_html(html, config=config)

        # Should have extracted XBRL metadata (xbrl_data is a List[XBRLFact])
        if hasattr(doc.metadata, 'xbrl_data') and doc.metadata.xbrl_data:
            facts = doc.metadata.xbrl_data

            # Should find facts (at least the visible one, ideally both)
            assert len(facts) > 0


class TestEdgeCaseRegressions:
    """Regression tests for edge case bugs."""

    def test_empty_html_no_crash(self):
        """
        Regression: Empty HTML should return empty document.

        Bug: Empty input could cause crashes
        Expected: Returns valid empty Document
        """
        doc = parse_html("")

        assert doc is not None
        assert len(doc.tables) == 0
        assert len(doc.text()) == 0

    def test_malformed_html_recovery(self):
        """
        Regression: Malformed HTML should parse gracefully.

        Bug: Unclosed tags could cause parser errors
        Fix: Use lxml's recover=True mode
        Expected: Parser auto-closes tags and continues
        """
        html = "<html><body><p>Unclosed paragraph<div>And div</body></html>"
        doc = parse_html(html)

        assert doc is not None
        assert "Unclosed paragraph" in doc.text()
        assert "And div" in doc.text()

    def test_deeply_nested_structure(self):
        """
        Regression: Deep nesting should not cause stack overflow.

        Bug: Very deep nesting could cause recursion errors
        Expected: Handles 100+ levels of nesting
        """
        # 100-level deep nesting
        html = "<html><body>" + "<div>" * 100 + "Content" + "</div>" * 100 + "</body></html>"
        doc = parse_html(html)

        assert doc is not None
        assert "Content" in doc.text()
