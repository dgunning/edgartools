"""
Regression tests for edgartools-xn1u: two unrelated parser defects.

GH #1284 -- ixt word-date transforms accepted only a SPACE between the fields.
`_date_words` replaced commas with spaces and called `.split()`, so '19-Sep-2024'
stayed a single token and the length check rejected it;
`XBRLExtractor._get_fact_value` caught the TransformError and exposed the raw
display string with a `format_issue`. The Transformation Registry separates the
fields with a run of non-alphanumeric characters, and the NUMERIC sibling
`_date_numeric` already accepted `.`, `/`, `-` and whitespace -- the two
implementations of one rule simply disagreed.

This was never confined to the one format that was reported: all THIRTEEN
registry formats dispatching to `_date_words` share the tokenizer, and every one
of them rejected every separator but a space. Measured on FingerMotion's 10-K
0001520138-23-000448, four `fngr:WarrantExpiryDate` facts were exposed as
'19-Sep-2024', '4-Nov-2025', '21-Nov-2025' and '1-Oct-2024'; the SEC-extracted
instance carries the ISO values, which is the ground truth asserted below.
Across 16 filings and 40,219 iXBRL facts, no already-transformed value changed.

GH #1278 -- `_resolve_axis_domain` handled the first dimension-domain arc and
then `break`, so an axis carrying several domain roots kept only one. XBRL
Dimensions 1.0 s2.5.3 permits several, and a root that parents no member of its
own is registered nowhere else -- the domain-hierarchy pass only creates elements
that parent at least one domain-member arc -- so such a root vanished from
`domains_for_role()` entirely. Ellington Financial's 10-K 0001411342-23-000184
declares `efc_DerivativeMaturityPeriodDomain` (20 members) and the childless
`efc_Year2038Member` on `efc_DerivativeMaturityPeriodAxis`; five facts use the
omitted member. This is metadata only: the facts stay queryable and no value is
wrong. Across 1,040 roles in 17 filings, no `axis.domain_id` changed and exactly
that one domain was recovered.
"""

import pytest

from edgar.documents.strategies.ixbrl_transforms import TransformError, apply_transform
from edgar.xbrl.models import Axis, Domain, ElementCatalog, Table
from edgar.xbrl.parsers.definition import DefinitionParser


# ---------------------------------------------------------------------------
# GH #1284 -- word-date separators
# ---------------------------------------------------------------------------

# The four facts FingerMotion filed with ixt:datedaymonthyearen, against the ISO
# values in the SEC-extracted instance for the same filing.
FNGR_WARRANT_EXPIRY_DATES = [
    ('19-Sep-2024', '2024-09-19'),
    ('4-Nov-2025', '2025-11-04'),
    ('21-Nov-2025', '2025-11-21'),
    ('1-Oct-2024', '2024-10-01'),
]


@pytest.mark.parametrize("filed,iso", FNGR_WARRANT_EXPIRY_DATES)
def test_hyphenated_day_month_year_matches_the_extracted_instance(filed, iso):
    assert apply_transform('datedaymonthyearen', filed) == iso


@pytest.mark.parametrize("separator", [' ', '-', '.', '/', ', ', ' - ', ' '])
def test_every_separator_run_is_accepted(separator):
    """The registry separates the fields with a run of non-alphanumerics; only a
    space used to work."""
    assert apply_transform('datedaymonthyearen', separator.join(['19', 'Sep', '2024'])) == '2024-09-19'


@pytest.mark.parametrize("fmt,value,expected", [
    # Every registry format that shares this tokenizer, with a non-space separator.
    ('datedaymonthyearen', '19-Sep-2024', '2024-09-19'),
    ('datedaymonthnameyearen', '19-Sep-2024', '2024-09-19'),
    ('datelongeu', '19-September-2024', '2024-09-19'),
    ('dateshorteu', '19-Sep-2024', '2024-09-19'),
    ('datemonthdayyearen', 'Sep-19-2024', '2024-09-19'),
    ('datemonthnamedayyearen', 'Sep-19-2024', '2024-09-19'),
    ('datelongus', 'September-19-2024', '2024-09-19'),
    ('dateshortus', 'Sep-19-2024', '2024-09-19'),
    ('datemonthdayen', 'Sep-19', '--09-19'),
    ('datemonthnamedayen', 'Sep-19', '--09-19'),
    ('datelongmonthday', 'September-19', '--09-19'),
    ('dateshortmonthday', 'Sep-19', '--09-19'),
    ('datedaymonthen', '19-Sep', '--09-19'),
])
def test_all_word_date_formats_share_the_fixed_tokenizer(fmt, value, expected):
    assert apply_transform(fmt, value) == expected


@pytest.mark.parametrize("value,expected", [
    ('September 30, 2024', '2024-09-30'),   # the comma form that always worked
    ('30 September 2024', '2024-09-30'),
    ('1st-Oct-2024', '2024-10-01'),         # ordinal suffix survives
    ('19. Sep. 2024', '2024-09-19'),        # trailing dots are separators
    ('Sept-19-2024', '2024-09-19'),         # abbreviations keep working
])
def test_forms_that_already_worked_are_unchanged(value, expected):
    fmt = 'datemonthdayyearen' if value[0].isalpha() else 'datedaymonthyearen'
    assert apply_transform(fmt, value) == expected


@pytest.mark.parametrize("value", [
    '19Sep2024',            # no separator at all
    'Wed, 19 Sep 2024',     # an extra field
    '19-Smarch-2024',       # not a month
    '32-Sep-2024',          # not a day
    '19-Feb-',              # missing year
])
def test_content_that_is_not_a_date_is_still_rejected(value):
    """A looser tokenizer must not turn into an accept-anything parser."""
    with pytest.raises(TransformError):
        apply_transform('datedaymonthyearen', value)


# ---------------------------------------------------------------------------
# GH #1278 -- a second, childless domain root on one axis
# ---------------------------------------------------------------------------

ROLE = 'http://www.ellingtonfinancial.com/role/FinancialDerivativesInterestRateSwapsDetails'

# Ellington Financial's arcs for efc_DerivativeMaturityPeriodAxis, as filed: two
# dimension-domain arcs at order 1 and 2, where only the first parents members.
DEFINITION_LINKBASE = f"""<?xml version="1.0" encoding="UTF-8"?>
<linkbase xmlns="http://www.xbrl.org/2003/linkbase"
          xmlns:xlink="http://www.w3.org/1999/xlink"
          xmlns:xbrldt="http://xbrl.org/2005/xbrldt">
  <definitionLink xlink:type="extended" xlink:role="{ROLE}">
    <loc xlink:type="locator" xlink:href="efc.xsd#efc_DerivativeTable" xlink:label="table"/>
    <loc xlink:type="locator" xlink:href="efc.xsd#efc_DerivativeMaturityPeriodAxis" xlink:label="axis"/>
    <loc xlink:type="locator" xlink:href="efc.xsd#efc_DerivativeMaturityPeriodDomain" xlink:label="domain"/>
    <loc xlink:type="locator" xlink:href="efc.xsd#efc_Year2038Member" xlink:label="year2038"/>
    <loc xlink:type="locator" xlink:href="efc.xsd#efc_A2021Member" xlink:label="year2021"/>

    <definitionArc xlink:type="arc"
        xlink:arcrole="http://xbrl.org/int/dim/arcrole/hypercube-dimension"
        xlink:from="table" xlink:to="axis" order="1"/>

    <!-- TWO domain roots on one axis; the second parents nothing. -->
    <definitionArc xlink:type="arc"
        xlink:arcrole="http://xbrl.org/int/dim/arcrole/dimension-domain"
        xlink:from="axis" xlink:to="domain" order="1"/>
    <definitionArc xlink:type="arc"
        xlink:arcrole="http://xbrl.org/int/dim/arcrole/dimension-domain"
        xlink:from="axis" xlink:to="year2038" order="2"/>

    <definitionArc xlink:type="arc"
        xlink:arcrole="http://xbrl.org/int/dim/arcrole/domain-member"
        xlink:from="domain" xlink:to="year2021" order="1"/>
  </definitionLink>
</linkbase>
"""


@pytest.fixture
def parser():
    definition_roles: dict = {}
    tables: dict = {}
    axes: dict = {}
    domains: dict = {}
    catalog: dict = {}
    parser = DefinitionParser(definition_roles, tables, axes, domains, catalog)
    parser.parse_definition_content(DEFINITION_LINKBASE)
    return parser


def test_a_childless_second_domain_root_is_registered(parser):
    domains = parser.domains_for_role(ROLE)
    assert 'efc_DerivativeMaturityPeriodDomain' in domains
    assert 'efc_Year2038Member' in domains, \
        "the second dimension-domain arc was dropped, so a filed member had no domain"


def test_the_first_domain_root_still_names_the_axis(parser):
    """`Axis.domain_id` is a single field and must keep naming the first root, so
    no existing consumer sees a different answer."""
    axis = parser.axes_for_role(ROLE)['efc_DerivativeMaturityPeriodAxis']
    assert axis.domain_id == 'efc_DerivativeMaturityPeriodDomain'


def test_the_populated_root_keeps_its_members(parser):
    domains = parser.domains_for_role(ROLE)
    assert domains['efc_DerivativeMaturityPeriodDomain'].members == ['efc_A2021Member']
    assert domains['efc_Year2038Member'].members == []
