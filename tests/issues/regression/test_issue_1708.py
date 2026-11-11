"""EFTS search results kept the raw display name on ``EFTSResult.company``.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1708

``_parse_hit`` copied ``display_names[0]`` unchanged. A hit shaped like an
EFTS response for NVIDIA's FY2024 10-K (accession ``0001045810-24-000029``)
left ``NVIDIA CORP  (NVDA)  (CIK 0001045810)`` in ``company``. The same module
already cleans that decoration in ``resolve_accession``. Offline dict fixtures.
"""

import pytest

from edgar.search.efts import EFTSSearch, _parse_hit

pytestmark = pytest.mark.fast

_OMIT = object()


def _hit(display_names, ciks=("0001045810", "0000070858")):
    source = {
        "adsh": "0001045810-24-000029",
        "form": "10-K",
        "file_date": "2024-02-21",
        "ciks": list(ciks),
    }
    if display_names is not _OMIT:
        source["display_names"] = display_names
    return {
        "_id": "0001045810-24-000029:nvda-20240128.htm",
        "_score": 12.5,
        "_source": source,
    }


def test_nvidia_company_is_cleaned_and_the_rest_of_the_hit_is_unchanged():
    result = _parse_hit(_hit(["NVIDIA CORP  (NVDA)  (CIK 0001045810)"]))
    assert (result.company, result.cik, result.accession_number, result.form,
            result.filed, result.score, result.file_type, result.document_id) == (
        "NVIDIA CORP", "0001045810", "0001045810-24-000029", "10-K",
        "2024-02-21", 12.5, None, "nvda-20240128.htm",
    )
    frame = EFTSSearch(query="nvidia", total=1, results=[result]).to_filings().to_pandas()
    assert frame.iloc[0]["company"] == "NVIDIA CORP"


@pytest.mark.parametrize("display_names, expected", [
    (["Apple Inc."], "Apple Inc."),
    (["Airbnb, Inc.  (ABNB)  (CIK 0001559720)"], "Airbnb, Inc."),
    (["BANK OF AMERICA CORP /DE/  (CIK 0000070858)"], "BANK OF AMERICA CORP /DE/"),
    (["ACME HOLDINGS (DELAWARE)"], "ACME HOLDINGS (DELAWARE)"),
    (["ACME HOLDINGS (DELAWARE)  (CIK 0000000001)"], "ACME HOLDINGS (DELAWARE)"),
    (["", "BANK OF AMERICA CORP /DE/  (CIK 0000070858)"], ""),
    ([None], None),
    ([], None),
    (None, None),
    (_OMIT, None),
])
def test_name_edges_keep_the_first_cik(display_names, expected):
    result = _parse_hit(_hit(display_names))
    assert result.company == expected
    assert result.cik == "0001045810"
