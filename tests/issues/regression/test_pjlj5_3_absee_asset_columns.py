"""ABS-EE asset data: every tag a filer reports lands in a filled column.

Bead: edgartools-pjlj5.3

The 6.2 parser (edgar/abs/abs_ee.py) carried one hand-written field map, written
for the auto lease schema and applied to auto loans too. On World Omni Auto
Receivables Trust 2022-C (0001104659-26-111517, autoloan) 21 of its 37 columns
were 100% empty, credit score and state among them, and summary() reported an
acquisition cost of $0. On BMW Vehicle Lease Trust 2023-2 (0000929638-25-004537,
autolease) 7 columns were always empty: six mapped tags do not exist in the
schema, and paidThroughDate (MM-DD-YYYY) was parsed as MM/YYYY.

The reader now takes its columns from SEC's XSDs, so a column is empty only when
the filer left the tag out. These checks read trimmed verbatim copies of both
exhibits (tests/fixtures/absee/).
"""
import re
from pathlib import Path

import pytest

from edgar.abs import AssetData
from edgar.abs.absee_schemas import SCHEMAS

pytestmark = pytest.mark.fast

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "absee"


@pytest.mark.parametrize("fixture, schema", [
    ("woart_2022c_0001104659-26-111517_first25.xml", "autoloan"),
    ("bmwlt_2023-2_0000929638-25-004537_first25.xml", "autolease"),
])
def test_every_filed_tag_fills_its_column(fixture, schema):
    path = FIXTURES / fixture
    filed_tags = {tag for tag, value in re.findall(r"<(\w+)>([^<]*)</\1>", path.read_text()) if value.strip()}
    assert len(filed_tags) > 50
    data = AssetData.from_source(path)
    assert data.info.schema == schema
    spec = SCHEMAS[schema]['tables']['assets']
    for tag in filed_tags:
        column = spec[tag][0]
        assert data.assets[column].notna().any(), f"{tag} is filed but {column} is empty"


def test_autoloan_summary_is_not_zero():
    data = AssetData.from_source(FIXTURES / "woart_2022c_0001104659-26-111517_first25.xml")
    summary = data.summary()
    assert summary.total_original_amount > 0
    assert summary.avg_credit_score is not None
