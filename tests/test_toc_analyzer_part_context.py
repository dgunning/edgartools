from edgar.documents.utils.toc_analyzer import TOCAnalyzer


def test_infers_part_from_standalone_rows_in_toc():
    html = """
    <html><body>
      <table>
        <tr><td>PART I</td></tr>
        <tr><td>Item 1.</td><td><a href="#i1">Business</a></td></tr>
        <tr><td>Item 1A.</td><td><a href="#i1">Business</a></td></tr>
        <tr><td>Item 2.</td><td><a href="#i1">Business</a></td></tr>
        <tr><td>Item 3.</td><td><a href="#i1">Business</a></td></tr>
        <tr><td>Item 4.</td><td><a href="#i1">Business</a></td></tr>
        <tr><td>PART II</td></tr>
        <tr><td>Item 5.</td><td><a href="#i5">Market for Registrant's Common Equity</a></td></tr>
      </table>
      <h2 id="i1">ITEM 1. BUSINESS</h2>
      <h2 id="i5">ITEM 5. MARKET FOR REGISTRANT'S COMMON EQUITY</h2>
    </body></html>
    """

    mapping = TOCAnalyzer().analyze_toc_structure(html)

    assert "part_i_item_1" in mapping
    assert "part_i_item_4" in mapping
    assert "part_ii_item_5" in mapping
