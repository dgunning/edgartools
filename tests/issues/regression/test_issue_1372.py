"""Regression test: category-led identifiers name a heading or sub-sector as the company.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1372

Three filers open the Investment Identifier with schedule headings, not the
company: CGBD (10-Q 0001544206-26-000055) writes "Investment | Non-Affiliated
Issuer | First Lien Debt | <Company> | <Industry>", SLRC (10-Q
0001193125-26-332726) "Common Equity/Equity Interests/Warrants | <Company> |
<Industry>", PFX (10-Q 0001213900-26-085667) "<Relationship> Investments -
<Company> - <Industry> - <Instrument>". Two defects met there.

The axis-prefix strip cut the label at its first ": ", so a trailing
"Sector: Sub-sector" ("Transportation: Cargo") left "Cargo" as the whole
identifier. And with the prefix gone, the first heading was taken for the
company. Before the fix, CGBD's company_name was wrong on 348 of its 352
positions, SLRC's on 40 of 110, PFX's on 27 of 96.

Every identifier below is verbatim from those filings. Offline:
`member_candidates=()` needs no filing.
"""

import pytest

from edgar.bdc.investments import parse_investment_identifier


@pytest.mark.parametrize(
    ('identifier', 'company_name', 'investment_type'),
    [
        # CGBD: headings, company, then "Sector: Sub-sector" ("Durable" before).
        ('Credit Fund | First Lien Debt | Yellowstone Buyer Acquisition, LLC | Consumer Goods: Durable',
         'Yellowstone Buyer Acquisition, LLC', 'First Lien Debt'),
        # "Cargo" before.
        ('Investment | Non-Affiliated Issuer | First Lien Debt | Auctane, Inc. | Transportation: Cargo',
         'Auctane, Inc.', 'First Lien Debt'),
        # "Investment" before; the trailing 2 is the filer's duplicate counter.
        ('Investment | Affiliated Issuer | Structured Credit Partners JV, LLC 2',
         'Structured Credit Partners JV, LLC', 'Unclassified'),
        # SLRC: "Common Equity/Equity Interests/Warrants" before.
        ('Common Equity/Equity Interests/Warrants | KBH Topco LLC (Kingsbridge) | Multi-Sector Holdings',
         'KBH Topco LLC (Kingsbridge)', 'Common Equity/Equity Interests/Warrants'),
        # SLRC: the instrument trails the company inside its segment.
        ('Common Equity/Equity Interests/Warrants | CardioFocus, Inc. Warrants | '
         'Health Care Equipment & Supplies | 3/2017',
         'CardioFocus, Inc.', 'Warrants'),
        # PFX: "Business - Equity" before.
        ('Non-Controlled/Non-Affiliated Investments - Altisource S.A.R.L. - Services: Business - Equity',
         'Altisource S.A.R.L.', 'Equity'),
        # PFX: "- ECC Capital Corp. - Real Estate" before.
        ('Controlled Investments - ECC Capital Corp. - Real Estate - Equity',
         'ECC Capital Corp.', 'Equity'),
    ],
)
def test_a_category_led_identifier_names_the_company(identifier, company_name, investment_type):
    parsed = parse_investment_identifier(identifier)

    assert parsed.company_name == company_name
    assert parsed.investment_type == investment_type


def test_a_heading_the_filer_tags_as_a_member_is_still_a_heading():
    # SLRC tags "Senior Secured Loans" as a member, so from_xbrl passes it as a
    # candidate; "First Lien Bank Debt/" came back before.
    from edgar.bdc.investments import _normalize_member_text
    identifier = ('Senior Secured Loans | First Lien Bank Debt/Senior Secured Loans | '
                  'Streamland Media Holdings LLC | Professional Services | S+400 | 2.00% | 9.66% | 5/2025 | 5/2030')
    candidates = tuple(_normalize_member_text(label) for label in (
        'Senior Secured Loans', 'Streamland Media Holdings LLC', 'Professional Services'))

    parsed = parse_investment_identifier(identifier, member_candidates=candidates)

    assert parsed.company_name == 'Streamland Media Holdings LLC'
    assert parsed.investment_type == 'First Lien Bank Debt/Senior Secured Loans'


def test_only_the_axis_prefix_is_stripped():
    identifier = 'Investment | Non-Affiliated Issuer | First Lien Debt | Auctane, Inc. | Transportation: Cargo'

    parsed = parse_investment_identifier(f'us-gaap:InvestmentIdentifierAxis: {identifier}')

    assert parsed.identifier == identifier
    assert parsed.company_name == 'Auctane, Inc.'


def test_a_company_led_pipe_identifier_is_unchanged():
    # SLRC's other layout leads with the company; the heading rule leaves it alone.
    parsed = parse_investment_identifier(
        'SunMed Group Holdings, LLC | Health Care Equipment & Supplies | S+550 | 0.75% | 9.26% | 6/2028'
    )

    assert parsed.company_name == 'SunMed Group Holdings, LLC'
