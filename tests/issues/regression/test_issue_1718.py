"""The holdings skill and common-pitfalls.md called ``Filings.filter(company=...)``.

``Filings.filter()`` takes ``cik`` and ``ticker`` but no ``company``, so the "Get 13F
Holdings" pattern in ``edgar/ai/skills/holdings/skill.yaml``, the ``reverse-lookup-trap``
entry in ``sharp-edges.yaml`` and the example in ``docs/common-pitfalls.md`` raised
``TypeError: Filings.filter() got an unexpected keyword argument 'company'``.

They now filter by ``cik``, and this test executes the corrected code from each file.

Ground truth: Berkshire Hathaway (CIK 1067983) filed 13F-HR 0000950123-24-008740 on
2024-08-14 (read from its SEC submissions list).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1718
"""
import re
from datetime import date

import pyarrow as pa
import pytest
import yaml

from edgar import Filings, get_filings
from tests.paths import REPO_ROOT

BERKSHIRE_CIK = 1067983
BERKSHIRE_13F = "0000950123-24-008740"
HOLDINGS_SKILL = REPO_ROOT / "edgar/ai/skills/holdings/skill.yaml"
HOLDINGS_EDGES = REPO_ROOT / "edgar/ai/skills/holdings/sharp-edges.yaml"
PITFALLS = REPO_ROOT / "docs/common-pitfalls.md"


def skill_pattern(name):
    patterns = yaml.safe_load(HOLDINGS_SKILL.read_text(encoding="utf-8"))["patterns"]
    return next(p["code"] for p in patterns if p["name"] == name)


def sharp_edge(edge_id):
    edges = yaml.safe_load(HOLDINGS_EDGES.read_text(encoding="utf-8"))["sharp_edges"]
    return next(e["solution"] for e in edges if e["id"] == edge_id)


def pitfalls_block(marker):
    blocks = re.findall(r"```python\n(.*?)```", PITFALLS.read_text(encoding="utf-8"), re.DOTALL)
    return next(b for b in blocks if marker in b and "RIGHT" in b)


def two_filers():
    return Filings(pa.table({
        "form": ["13F-HR", "13F-HR"],
        "company": ["BERKSHIRE HATHAWAY INC", "SOME OTHER MANAGER"],
        "cik": pa.array([BERKSHIRE_CIK, 1], pa.int32()),
        "filing_date": pa.array([date(2024, 8, 14)] * 2, pa.date32()),
        "accession_number": [BERKSHIRE_13F, "0000000001-24-000001"],
    }))


def run(code, filings):
    """Run documented code with get_filings() answering `filings`; filing.obj() is not called."""
    lines = [line for line in code.splitlines() if "thirteenf = " not in line and ".holdings" not in line]
    ns = {"get_filings": lambda **kwargs: filings}
    exec(compile("\n".join(lines), "doc", "exec"), ns)  # noqa: S102 - our own documentation
    return ns["filing"]


@pytest.mark.fast
def test_filter_has_no_company_keyword():
    with pytest.raises(TypeError, match="company"):
        two_filers().filter(company="BERKSHIRE HATHAWAY")


@pytest.mark.fast
@pytest.mark.parametrize("name, code", [
    ("skill.yaml Get 13F Holdings", lambda: skill_pattern("Get 13F Holdings")),
    ("sharp-edges.yaml reverse-lookup-trap", lambda: sharp_edge("reverse-lookup-trap")),
    ("common-pitfalls.md", lambda: pitfalls_block("RIGHT: Filter by filer first")),
])
def test_documented_code_selects_the_filer(name, code):
    code = "\n".join(line for line in code().splitlines() if not line.lstrip().startswith("# WRONG"))
    # Drop the WRONG loop (an iteration over every filing); keep the lines after RIGHT
    if "for filing in" in code:
        code = code[code.index("# RIGHT"):]
    filing = run(code, two_filers())
    assert filing.accession_no == BERKSHIRE_13F
    assert "company=" not in code


@pytest.mark.vcr
def test_issue_1718_filter_by_cik_on_berkshires_real_filings():
    filings = get_filings(form="13F-HR", year=2024, quarter=3)
    filing = run(skill_pattern("Get 13F Holdings"), filings)
    assert filing.accession_no == BERKSHIRE_13F
    assert filing.filing_date.isoformat() == "2024-08-14"
