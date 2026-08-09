"""Build ``Filing`` objects for tests without going through the quarterly index.

``find("0001493152-25-029712")`` and ``get_by_accession_number(...)`` resolve an
accession by downloading the SEC quarterly full-index
(``/Archives/edgar/full-index/YYYY/QTRn/form.gz``) and scanning it. That is the
right behaviour for a user holding an accession and nothing else, and the wrong
one for a test that already knows exactly which filing it wants:

* It spends a ~30 MB download to learn four short fields.
* Recorded into a cassette, the index dwarfs the filing under test. The corpus
  carries cassettes of 30 MB and one of 135 MB that are nearly all index
  (bead edgartools-9q82).
* No cassette records it consistently, so whether one of these tests touches
  the network depends on whether an earlier test on the same xdist worker
  already populated ``available_quarters``' in-process cache. That made them
  unclassifiable as ``fast`` or ``network`` and kept 170 tests out of the
  pull-request gate (bead edgartools-zuuu).

``offline_filing`` skips the lookup. The four index fields are frozen in the
table below, so the ``Filing`` is constructed directly and only the filing's own
documents are fetched — and those the cassettes do record.

Every row was read from SEC EDGAR and is immutable for a given accession: the
CIK, form, company and filing date of a filed document do not change. Add a row
by looking the accession up once, with the network available::

    python -c "from edgar import get_by_accession_number as g; \\
               f = g('0001493152-25-029712'); \\
               print(f.form, f.cik, f.company, f.filing_date)"
"""
from __future__ import annotations

from typing import Dict, Tuple

from edgar import Filing

# accession number -> (form, cik, company, filing_date)
_INDEX_FIELDS: Dict[str, Tuple[str, int, str, str]] = {
    "0000019617-24-000664": ("ATS-N-W", 782124, "J.P. MORGAN SECURITIES LLC", "2024-12-23"),
    "0000215466-26-000004": ("10-K", 215466, "Coeur Mining, Inc.", "2026-02-18"),
    "0000320193-24-000061": ("CORRESP", 320193, "Apple Inc.", "2024-04-29"),
    "0000320193-24-000123": ("10-K", 320193, "Apple Inc.", "2024-11-01"),
    "0000827060-26-000002": ("N-CSRS", 827060, "AMERICAN CENTURY QUANTITATIVE EQUITY FUNDS, INC.", "2026-02-26"),
    "0000950103-25-008153": ("S-3", 1771910, "ADC Therapeutics SA", "2025-06-30"),
    "0000950123-23-009133": ("ATS-N/UA", 42352, "GOLDMAN SACHS & CO. LLC", "2023-10-30"),
    "0000950170-23-001409": ("10-K", 1318605, "Tesla, Inc.", "2023-01-31"),
    "0001026214-26-000021": ("10-K", 1026214, "FEDERAL HOME LOAN MORTGAGE CORP", "2026-02-12"),
    "0001026214-26-000027": ("10-Q", 1026214, "FEDERAL HOME LOAN MORTGAGE CORP", "2026-04-30"),
    "0001045810-26-000024": ("8-K", 1045810, "NVIDIA CORP", "2026-03-06"),
    "0001047469-18-007293": ("S-3", 1093691, "PLUG POWER INC", "2018-11-16"),
    "0001104659-20-040593": ("S-3", 1089531, "KINGOLD JEWELRY, INC.", "2020-03-30"),
    "0001104659-23-069410": ("F-3", 1053092, "CREDIT SUISSE AG", "2023-06-08"),
    "0001104659-23-076317": ("S-1", 1736243, "Acurx Pharmaceuticals, Inc.", "2023-06-29"),
    "0001104659-24-132924": ("424B4", 1130598, "Traws Pharma, Inc.", "2024-12-31"),
    "0001104659-25-064107": ("S-3ASR", 1368622, "AeroVironment Inc", "2025-06-30"),
    "0001104659-26-017097": ("CORRESP", 1875558, "Nuvectis Pharma, Inc.", "2026-02-18"),
    "0001108205-25-000026": ("424B5", 1108205, "CURIS INC", "2025-03-31"),
    "0001133228-26-002293": ("N-CSR", 832566, "ALGER PORTFOLIOS", "2026-02-26"),
    "0001140361-21-010426": ("S-1", 1847577, "Learn CW Investment Corp", "2021-03-29"),
    "0001140361-25-024210": ("S-3", 701347, "CENTRAL PACIFIC FINANCIAL CORP", "2025-06-30"),
    "0001145549-23-075236": ("N-MFP2", 862021, "AB FIXED INCOME SHARES INC", "2023-12-07"),
    "0001193125-20-294801": ("S-1", 1559720, "Airbnb, Inc.", "2020-11-16"),
    "0001193125-20-310765": ("S-3ASR", 316709, "SCHWAB CHARLES CORP", "2020-12-04"),
    "0001193125-20-311265": ("S-1/A", 1559720, "Airbnb, Inc.", "2020-12-07"),
    "0001193125-20-315318": ("424B4", 1559720, "Airbnb, Inc.", "2020-12-11"),
    "0001193125-22-186192": ("S-3", 1304492, "Anterix Inc.", "2022-06-30"),
    "0001193125-25-066253": ("S-3ASR", 766704, "WELLTOWER INC.", "2025-03-28"),
    "0001193125-25-067858": ("S-3", 1827087, "Vigil Neuroscience, Inc.", "2025-03-31"),
    "0001193125-25-068723": ("S-3/A", 1796129, "Vincerx Pharma, Inc.", "2025-03-31"),
    "0001193125-25-068732": ("424B5", 1888447, "Excelerate Energy, Inc.", "2025-03-31"),
    "0001193125-25-068799": ("F-3/A", 1814722, "TR Finance LLC", "2025-03-31"),
    "0001193125-25-068942": ("S-3", 1422142, "Whitehawk Therapeutics, Inc.", "2025-03-31"),
    "0001193125-25-148895": ("497K", 45291, "JOHN HANCOCK CAPITAL SERIES", "2025-06-26"),
    "0001193125-25-152548": ("497K", 772129, "GMO TRUST", "2025-06-30"),
    "0001193125-25-338333": ("424B5", 753308, "NEXTERA ENERGY INC", "2025-12-31"),
    "0001213900-21-035033": ("S-1/A", 1766140, "Unicycive Therapeutics, Inc.", "2021-06-30"),
    "0001213900-25-026186": ("424B2", 70858, "BANK OF AMERICA CORP /DE/", "2025-03-31"),
    "0001213900-25-058997": ("S-3", 1819796, "GCM Grosvenor Inc.", "2025-06-27"),
    "0001213900-25-059789": ("S-1", 2067592, "McKinley Acquisition Corp", "2025-06-30"),
    "0001214659-26-002941": ("424B5", 1677077, "Alzamend Neuro, Inc.", "2026-03-06"),
    "0001396440-25-000018": ("10-K", 1396440, "Main Street Capital CORP", "2025-02-28"),
    "0001410368-26-010417": ("N-MFP3", 862021, "AB FIXED INCOME SHARES INC", "2026-02-06"),
    "0001410368-26-010918": ("N-CEN", 1496608, "AB Active ETFs, Inc.", "2026-02-12"),
    "0001410368-26-010921": ("N-CEN", 81443, "AB CAP FUND, INC.", "2026-02-12"),
    "0001437749-26-019923": ("10-K", 69733, "NATHANS FAMOUS, INC.", "2026-06-09"),
    "0001493152-23-041369": ("S-3", 1847986, "Dragonfly Energy Holdings Corp.", "2023-11-15"),
    "0001493152-25-029712": ("424B5", 749647, "Imunon, Inc.", "2025-12-31"),
    "0001628280-25-015699": ("424B5", 1819438, "ESS Tech, Inc.", "2025-03-31"),
    "0001641172-25-001350": ("424B5", 1855485, "Calidi Biotherapeutics, Inc.", "2025-03-31"),
    "0001641172-25-001566": ("424B5", 1716947, "Ensysce Biosciences, Inc.", "2025-03-31"),
    "0001654954-21-007440": ("S-3/A", 720875, "DYNATRONICS CORP", "2021-06-30"),
    "0001675365-19-000012": ("ATS-N", 1675365, "BOFA SECURITIES, INC.", "2019-05-10"),
    "0001918704-24-002559": ("424B2", 70858, "BANK OF AMERICA CORP /DE/", "2024-12-31"),
    "0001918704-25-005439": ("424B2", 70858, "BANK OF AMERICA CORP /DE/", "2025-03-31"),
    "0001918704-25-005479": ("424B2", 70858, "BANK OF AMERICA CORP /DE/", "2025-03-31"),
    "0001918704-25-005486": ("424B2", 70858, "BANK OF AMERICA CORP /DE/", "2025-03-31"),
}


def offline_filing(accession_number: str) -> Filing:
    """Return the ``Filing`` for ``accession_number`` without an index download."""
    try:
        form, cik, company, filing_date = _INDEX_FIELDS[accession_number]
    except KeyError:
        raise KeyError(
            f"{accession_number} is not in the offline filing table. Add it to "
            f"tests/_offline_filings.py rather than calling find() — see that "
            f"module's docstring for why, and for the one-liner that reads the "
            f"fields from EDGAR."
        ) from None
    return Filing(cik=cik, company=company, form=form,
                  filing_date=filing_date, accession_no=accession_number)
