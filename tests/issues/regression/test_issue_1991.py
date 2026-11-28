"""GitHub Issue: https://github.com/dgunning/edgartools/issues/1991"""

from pathlib import Path

import pytest

from edgar.exceptions import ValidationError
from edgar.xbrl import XBRL, XBRLS

pytestmark = pytest.mark.fast

# Tesla Form 10-Q, quarter ended June 30, 2024, accession 0001628280-24-032662.
TESLA = Path("tests/fixtures/xbrl/tsla")


@pytest.fixture(scope="module")
def tesla():
    return XBRL.from_files(
        instance_file=TESLA / "tsla-20240630_htm.xml",
        schema_file=TESLA / "tsla-20240630.xsd.xml",
    )


def test_by_extension_returns_filer_defined_facts(tesla):
    all_facts = tesla.query().to_dataframe()
    extension_facts = tesla.query().by_extension().to_dataframe()

    assert 'us-gaap:Assets' in all_facts['concept'].values
    assert 'us-gaap:Assets' not in extension_facts['concept'].values
    assert (extension_facts['fact_id'] == 'f-50').sum() == 1
    assert extension_facts.loc[extension_facts['fact_id'] == 'f-50', 'numeric_value'].item() == 184_000_000


def test_by_extension_reports_an_unloaded_schema():
    xbrl = XBRL.from_files(instance_file=TESLA / "tsla-20240630_htm.xml")

    with pytest.raises(ValidationError, match="no filing schema with a target namespace was loaded"):
        xbrl.query().by_extension()


def test_by_extension_reports_unsupported_stitched_query(tesla):
    stitched = XBRLS([tesla])

    with pytest.raises(NotImplementedError, match="only supports single-filing"):
        stitched.query().by_extension()
