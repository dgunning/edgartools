"""Check filer-defined facts against Tesla's June 2024 Form 10-Q."""

from pathlib import Path

import pytest

from edgar.xbrl import XBRL


@pytest.mark.fast
def test_by_extension_returns_filer_defined_facts():
    fixture = Path(__file__).parents[1] / 'fixtures' / 'xbrl' / 'tsla'
    xbrl = XBRL.from_files(
        instance_file=fixture / 'tsla-20240630_htm.xml',
        schema_file=fixture / 'tsla-20240630.xsd.xml',
    )

    all_facts = xbrl.query().to_dataframe()
    extension_facts = xbrl.query().by_extension().to_dataframe()

    assert 'us-gaap:Assets' in all_facts['concept'].values
    assert 'us-gaap:Assets' not in extension_facts['concept'].values
    assert (extension_facts['fact_id'] == 'f-50').sum() == 1
    assert extension_facts.loc[extension_facts['fact_id'] == 'f-50', 'numeric_value'].item() == 184_000_000
