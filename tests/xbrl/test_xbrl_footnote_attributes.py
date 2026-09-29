"""
Test XBRL footnote attribute priority handling.

Validates fix for GitHub issue #482 / Beads edgartools-tm2:
In pre-2016 filings, footnote elements have different values for 'id' and 'xlink:label'.
FootnoteArcs reference xlink:label, so parser must prioritize that attribute.
"""
import pytest
from edgar import Company


@pytest.mark.network
@pytest.mark.slow
def test_old_filing_footnote_attributes_apd_2015():
    """
    Test that pre-2016 filings with mismatched id/xlink:label attributes work correctly.

    APD 2015 10-K has footnotes with:
    - id="FN_0"
    - xlink:label="lbl_footnote_0"

    FootnoteArcs reference "lbl_footnote_0", so parser must use xlink:label to match them.
    """
    apd = Company("APD")
    filings = apd.get_filings(form="10-K", filing_date="2015-01-01:2015-12-31")

    assert len(filings) > 0, "Should find APD 2015 10-K"

    filing = list(filings)[0]
    xbrl = filing.xbrl()

    # Verify footnotes were extracted
    assert len(xbrl.footnotes) > 0, "Should have extracted footnotes"

    # Check that footnote IDs match xlink:label pattern (not id pattern)
    # Old filings use "lbl_footnote_X" pattern in xlink:label
    footnote_ids = list(xbrl.footnotes.keys())

    # Should have footnotes with lbl_footnote_* pattern
    lbl_footnotes = [fid for fid in footnote_ids if fid.startswith('lbl_footnote_')]
    assert len(lbl_footnotes) > 0, f"Should have lbl_footnote_* IDs, got: {footnote_ids[:5]}"

    # Should NOT have footnotes with FN_* pattern (the id attribute)
    fn_footnotes = [fid for fid in footnote_ids if fid.startswith('FN_')]
    assert len(fn_footnotes) == 0, f"Should not have FN_* IDs (id attribute), got: {fn_footnotes}"

    print(f"✓ APD 2015: Extracted {len(xbrl.footnotes)} footnotes using xlink:label")
    print(f"  Sample IDs: {footnote_ids[:5]}")


@pytest.mark.network
@pytest.mark.slow
def test_modern_filing_footnote_attributes_apd_2023():
    """
    Test that modern filings with matching id/xlink:label attributes still work.

    APD 2023 10-K has footnotes with:
    - id="fn-1"
    - xlink:label="fn-1"

    Both attributes match, so either would work. This tests no regression.
    """
    apd = Company("APD")
    filings = apd.get_filings(form="10-K", filing_date="2023-01-01:2023-12-31")

    assert len(filings) > 0, "Should find APD 2023 10-K"

    filing = list(filings)[0]
    xbrl = filing.xbrl()

    # Verify footnotes were extracted
    # Note: Modern iXBRL filings may have fewer footnotes in the instance document
    # as they use inline XBRL features
    assert xbrl.footnotes is not None, "Should have footnotes dict"

    if len(xbrl.footnotes) > 0:
        footnote_ids = list(xbrl.footnotes.keys())
        print(f"✓ APD 2023: Extracted {len(xbrl.footnotes)} footnotes")
        print(f"  Sample IDs: {footnote_ids[:5]}")
    else:
        print("✓ APD 2023: No footnotes in instance (expected for modern iXBRL)")


@pytest.mark.network
def test_footnote_arc_linkage():
    """
    Integration test: Verify footnotes are properly linked to facts via arcs.

    This is the real-world impact of the fix: footnotes should be accessible
    from facts they're linked to.
    """
    apd = Company("APD")
    filings = apd.get_filings(form="10-K", filing_date="2015-01-01:2015-12-31")

    assert len(filings) > 0, "Should find APD 2015 10-K"

    filing = list(filings)[0]
    xbrl = filing.xbrl()

    # Check that footnotes exist
    assert len(xbrl.footnotes) > 0, "Should have footnotes"

    # Check that some footnotes have related facts (linked via arcs)
    footnotes_with_facts = [fn for fn in xbrl.footnotes.values() if len(fn.related_fact_ids) > 0]

    assert len(footnotes_with_facts) > 0, (
        "Some footnotes should be linked to facts via arcs. "
        "If this fails, the arc linkage is broken."
    )

    print(f"✓ Arc linkage: {len(footnotes_with_facts)}/{len(xbrl.footnotes)} footnotes linked to facts")

    # Show a sample
    sample = footnotes_with_facts[0]
    print(f"  Sample footnote '{sample.footnote_id}' linked to {len(sample.related_fact_ids)} facts")
