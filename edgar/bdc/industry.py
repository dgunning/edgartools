"""
One industry vocabulary for both BDC paths.

The per-filing XBRL path (``edgar.bdc.investments``) and the DERA data set path
(``edgar.bdc.datasets``) both end up with an industry label as the filer wrote
it. Filers spell the same industry many ways: the 2025Q2 DERA file carries
1,075 distinct labels, among them "Software Sector", "Software And Services"
and "Software & Services". This module holds the single normalization table
that folds those spellings into a ``sector`` so summaries are comparable
across BDCs, while the raw ``industry`` stays available next to it.

``SECTOR_ALIASES`` is a plain dict keyed by :func:`sector_key` (lower-cased,
punctuation and "and"/"&" dropped, trailing "Sector"/"Industry" removed). A
label with no entry passes through as its own sector after the same light
clean-up, so a sector is never None for a non-empty industry.
"""
import re
from typing import Optional

__all__ = [
    'SECTOR_ALIASES', 'INDUSTRY_SOURCES', 'clean_industry_label', 'issuer_key',
    'normalize_sector', 'sector_key',
]

# The provenance values an industry can carry, in resolution order.
INDUSTRY_SOURCES = ('axis', 'enumeration', 'identifier', 'peer')

_MEMBER_SUFFIX = re.compile(r'\s*(\[Member\]|\{Member\]|Member)$')
_CAMEL_BOUNDARY = re.compile(r'(?<=[a-z0-9])(?=[A-Z])')
_QNAME_MEMBER = re.compile(r'^[A-Za-z][\w.-]*:(?P<local>[A-Za-z]\w*Member)$')
_LEGAL_FORM_TOKENS = frozenset({
    'inc', 'llc', 'l', 'lp', 'llp', 'ltd', 'limited', 'corp', 'corporation', 'co', 'company',
    'plc', 'gmbh', 'sa', 'sas', 'sarl', 'bv', 'nv', 'ag', 'pte', 'pty', 'ab', 'aps', 'spa', 'se',
    'kg', 'pc', 'the',
})


def clean_industry_label(value):
    """
    Reduce the ways an industry member arrives to one readable label.

    Axis members come as 'Healthcare Sector [Member]' or 'Healthcare Sector Member';
    the extensible enumeration comes as a QName URI such as
    'http://fasb.org/us-gaap/2024#HealthcareSectorMember' or, from a fact
    dimension, 'us-gaap:HealthcareSectorMember'. All become 'Healthcare Sector'.
    Spelling differences between filers are left alone; see normalize_sector.
    """
    if not isinstance(value, str):
        return value
    if value.startswith('http') and '#' in value:
        value = _CAMEL_BOUNDARY.sub(' ', value.rsplit('#', 1)[1])
    else:
        qname = _QNAME_MEMBER.match(value.strip())
        if qname:
            value = _CAMEL_BOUNDARY.sub(' ', qname.group('local'))
    return _MEMBER_SUFFIX.sub('', value).strip()


def issuer_key(name) -> Optional[str]:
    """
    The key under which one portfolio company is the same company across filers.

    'Truck-Lite Co., LLC', 'Truck-Lite Co LLC [Member]' and 'TRUCK-LITE CO., LLC'
    all become 'truck lite'. Legal-form words are dropped, so the key is None
    when nothing else is left ('Holdings, LLC').
    """
    if not isinstance(name, str):
        return None
    name = clean_industry_label(name)
    name = re.sub(r'\s*\((?:f/?k/?a|dba|d/b/a|aka|formerly)[^)]*\)', '', name, flags=re.IGNORECASE)
    tokens = [
        token for token in re.findall(r'[a-z0-9]+', name.lower())
        if token not in _LEGAL_FORM_TOKENS
    ]
    key = ' '.join(tokens)
    return key or None


_TRAILING_NOISE = re.compile(
    r'\s*(?:\[?\{?member\]?\}?|sector|industry|classification)\.?\s*$', re.IGNORECASE
)
_DROP_TOKENS = frozenset({'and', 'of', 'the'})
_SMALL_WORDS = frozenset({'and', 'of', 'the', 'or', 'in', 'to', 'a', 'an'})


def sector_key(label: str) -> str:
    """Lookup key for a raw industry label: 'Aerospace & Defense Sector' -> 'aerospace defense'."""
    text = label.strip()
    for _ in range(3):
        stripped = _TRAILING_NOISE.sub('', text)
        if stripped == text:
            break
        text = stripped
    text = text.replace('&', ' ')
    tokens = re.findall(r'[a-z0-9]+', text.lower())
    return ' '.join(token for token in tokens if token not in _DROP_TOKENS)


def _pretty(label: str) -> str:
    """The pass-through spelling for a label with no alias: trailing 'Sector' gone, '&' as 'and'."""
    text = label.strip()
    for _ in range(3):
        stripped = _TRAILING_NOISE.sub('', text)
        if stripped == text:
            break
        text = stripped
    text = re.sub(r'\s*&\s*', ' and ', text)
    text = re.sub(r'\s+', ' ', text).strip(' ,.:;-')
    if not text:
        return label.strip()
    words = text.split(' ')
    pretty = []
    for index, word in enumerate(words):
        lower = word.lower()
        if index and lower in _SMALL_WORDS:
            pretty.append(lower)
        elif word.isupper() and len(word) <= 4:
            pretty.append(word)          # IT, CLO, FIRE, B2B stay as filed
        else:
            pretty.append(word[:1].upper() + word[1:])
    return ' '.join(pretty)


def normalize_sector(industry: Optional[str]) -> Optional[str]:
    """
    The normalized sector for a raw industry label.

    >>> normalize_sector('Software Sector')
    'Software'
    >>> normalize_sector('Health Care Providers & Services Sector')
    'Healthcare'
    >>> normalize_sector('Underwater Basket Weaving Sector')
    'Underwater Basket Weaving'

    Returns None only for None or an empty label.
    """
    if not isinstance(industry, str) or not industry.strip():
        return None
    return SECTOR_ALIASES.get(sector_key(industry)) or _pretty(industry)


def _aliases(table: dict[str, tuple[str, ...]]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for sector, spellings in table.items():
        for spelling in (sector, *spellings):
            aliases[sector_key(spelling)] = sector
    return aliases


# Canonical sector -> the spellings seen in the DERA files (each is reduced with
# sector_key, so case, punctuation, "and"/"&" and a trailing "Sector" do not
# need to be enumerated). Built from the labels in the live 2025Q2 file.
SECTOR_ALIASES: dict[str, str] = _aliases({
    'Aerospace and Defense': (
        'Aerospace', 'Aerospace Defense', 'Aerospace & Defense Manufacturing',
    ),
    'Air Freight and Logistics': ('Air Freight Logistics',),
    'Automotive': (
        'Automobiles', 'Automobile Components', 'Auto Components', 'Automotive Sector.',
        'Automotive Components',
    ),
    'Banking, Finance, Insurance and Real Estate': (
        'Banking Finance Insurance Real Estate', 'FIRE Finance', 'FIRE Real Estate',
        'FIRE Insurance', 'Fire Finance', 'Fire Insurance', 'Buildings And Real Estate',
    ),
    'Beverage, Food and Tobacco': (
        'Beverage Food Tobacco', 'Beverage, Food, and Tobacco', 'Food and Beverage',
        'Food Products', 'Beverages', 'Packaged Foods Meats', 'Packaged Foods & Meats',
        'Food Distributors', 'Food & Drug', 'Food And Staples Retailing',
        'Consumer Staples Distribution & Retail',
    ),
    'Building Products': ('Building Materials', 'Building Products Manufacturing'),
    'Business Services': (
        'Business Service', 'Services Business', 'Services: Business', 'Services, Business',
        'Service Business Industry', 'Business Products and Services', 'Business Products',
        'Consumer And Business Services', 'Diversified/Conglomerate Services',
        'Diversified Support Services', 'Commercial Services',
        'Business to Business Marketplace', 'Human Resource Support Services',
        'Data Processing And Outsourced Services', 'Research & Consulting Services',
    ),
    'Capital Equipment': (
        'Capital Equipment Industry', 'Capital Goods', 'Machinery', 'Industrial Machinery',
        'Construction Machinery & Heavy Transportation Equipment', 'Heavy Electrical Equipment',
        'Electrical Equipment', 'Electrical Components & Equipment',
        'Diversified/Conglomerate Manufacturing', 'Manufacturing', 'Industrial Conglomerates',
        'Industrials', 'General Industrial', 'Commercial and Industrial', 'Industrial Engineering',
    ),
    'Chemicals, Plastics and Rubber': (
        'Chemicals', 'Chemicals Plastics Rubber', 'Chemicals, Plastics, And Rubber Industry',
        'Diversified Chemicals', 'Specialty Chemicals', 'Commodity Chemicals',
    ),
    'Commercial Services and Supplies': (
        'Commercial Services Supplies', 'Commercial And Professional Services',
    ),
    'Communications Equipment': ('Telecommunications Equipment', 'Technology Hardware and Equipment'),
    'Construction and Engineering': (
        'Construction', 'Construction Building', 'Construction & Building',
        'Construction Materials', 'Homebuilders Real Estate',
    ),
    'Consumer Goods: Durable': (
        'Consumer Goods Durable', 'Consumer Goods, Durable', 'Durable Consumer Goods',
        'Consumer Durables And Apparel', 'Household Durables', 'Household Appliances',
        'Home Furnishings', 'Leisure Products',
    ),
    'Consumer Goods: Non-Durable': (
        'Consumer Goods Non Durable', 'Consumer Goods, Non-Durable', 'Consumer Non-Durables',
        'Non-Durable Consumer Goods', 'Household Products', 'Household And Personal Products',
        'Personal Care Products', 'Personal Products', 'Personal Goods',
        'Textiles Apparel Luxury Goods', 'Textiles, Apparel and Luxury Goods',
    ),
    'Consumer Products and Services': (
        'Consumer Products', 'Consumer', 'Consumer Discretionary',
    ),
    'Consumer Services': (
        'Services Consumer', 'Services: Consumer', 'Services, Consumer',
        'Diversified Consumer Services', 'Specialized Consumer Services',
    ),
    'Containers, Packaging and Glass': (
        'Container and Packaging', 'Containers', 'Containers & Packaging', 'Containers Packaging',
        'Containers Packaging And Glass', 'Paper and Plastic Packaging Products and Materials',
        'Paper And Forest Products',
    ),
    'Distribution': (
        'Distributors', 'Trading Companies & Distributors', 'Trading Companies Distributors',
        'Wholesale',
    ),
    'Education': ('Education Services', 'Interactive Learning', 'Healthcare, Education, and Childcare'),
    'Energy': (
        'Energy Electricity', 'Energy: Electricity', 'Energy Sector, Electricity',
        'Energy Oil Gas', 'Energy Sector, Oil And Gas', 'Energy Equipment & Services',
        'Oil, Gas & Consumable Fuels', 'Oil, Gas and Consumable Fuels', 'Oil & Gas Services',
        'Electricity Production',
    ),
    'Environmental Industries': (
        'Environmental & Facilities Services', 'Infrastructure And Environmental Services',
    ),
    'Financial Services': (
        'Diversified Financial Services', 'Diversified Financials', 'Other Financial Services',
        'Financial Institution and Services', 'Specialized Finance', 'Consumer Finance',
        'Capital Markets', 'Banks', 'Investment Banking and Brokerage Services',
        'Asset Based Lending and Fund Finance', 'Sovereign and Public Finance',
        'Investment Funds And Vehicles', 'Multi-Sector Holdings',
    ),
    'Healthcare': (
        'Health Care', 'Healthcare & Pharmaceuticals', 'Healthcare and Pharmaceuticals',
        'Health Care Providers & Services', 'Health Care Providers Services',
        'Healthcare Providers And Services', 'Health Care Services', 'Healthcare Services',
        'Health Care Facilities', 'Health Care Equipment', 'Health Care Equipment & Supplies',
        'Health Care Equipment Supplies', 'Healthcare Equipment Supplies',
        'Health Care Equipment And Services', 'Healthcare Equipment And Services',
        'Health Care Supplies', 'Health Care Technology', 'Healthcare Technology',
        'Healthcare Technology Systems', 'Health Care Distributors',
        'Medical Devices And Equipment', 'Medical Equipment and Services',
        'Medical Software and Information Services', 'Healthcare Products',
        'Health Products',
    ),
    'High Tech Industries': (
        'Technology', 'Information Technology', 'Computer Hardware',
        'Technology Hardware, Storage And Peripherals',
        'Electronic Equipment, Instruments And Components',
    ),
    'Hotels, Gaming and Leisure': (
        'Hotel Gaming Leisure', 'Hotel, Gaming And Leisure', 'Hotel, Gaming, & Leisure',
        'Hotels, Gaming & Leisure', 'Hotels Restaurants Leisure', 'Hotels, Restaurants & Leisure',
        'Hotels, Resorts & Cruise Lines', 'Leisure Facilities', 'Travel & Leisure',
        'Travel and Leisure', 'Gaming', 'Restaurants', 'Leisure Products & Services',
    ),
    'Insurance': ('Insurance Brokers', 'Non-Life Insurance', 'Property & Casualty Insurance', 'Life and Health Insurance'),
    'IT Services': (
        'I T Services', 'ITServices', 'ITConsulting', 'IT Consulting And Other Services',
        'Information Technology Services', 'IT Service', 'Digital Infrastructure & Services',
    ),
    'Media': (
        'Media: Advertising, Printing & Publishing', 'Advertising Printing And Publishing Media',
        'Media: Broadcasting & Subscription', 'Media Broadcasting Subscription',
        'Media: Diversified & Production', 'Media, Diversified & Production',
        'Diversified And Production Media', 'Advertising', 'Advertising And Media',
        'Broadcasting', 'Entertainment', 'General Media and Content',
        'Interactive Media & Services', 'Information Services (B2C)',
    ),
    'Metals and Mining': ('Metal & Mining', 'Metals Mining', 'Industrial Metals and Mining', 'Materials'),
    'Pharmaceuticals and Biotechnology': (
        'Pharmaceuticals', 'Biotechnology', 'Pharmaceutical and Biotechnology',
        'Pharmaceuticals, Biotechnology & Life Sciences', 'Life Sciences Tools & Services',
        'Life Sciences Tools And Services',
    ),
    'Professional Services': (),
    'Real Estate': (
        'Real Estates', 'Real Estate Services', 'Real Estate Development',
        'Real Estate Management & Development', 'Multifamily',
    ),
    'Retail': (
        'Retails', 'Specialty Retail', 'Broadline Retail', 'Broadline Retail {Member]',
        'Consumer Retail', 'Super Retail', 'Internet & Direct Marketing Retail',
        'Computer Electronics Retail', 'E-Commerce - Clothing and Accessories',
        'E-Commerce - Personal Goods', 'Shopping Facilitators',
    ),
    'Software': (
        'Software And Services', 'Software & Services', 'Software and Computer',
        'Application Software', 'Systems Software', 'Business Applications Software',
        'Business/Productivity Software', 'Database Software', 'Entertainment Software',
        'Educational/Training Software', 'Financial Software', 'Internet Software And Services',
        'Multimedia and Design Software', 'Network Management Software',
        'Network Systems Management Software', 'Social/Platform Software',
        'Software as a Service ("SaaS")', 'Software & Tech Services', 'Software/Services',
        'SaaS',
    ),
    'Telecommunications': (
        'Telecommunication Services', 'Diversified Telecommunication Services',
        'Wireless Telecommunication Services', 'Integrated Telecommunication Services',
        'Alternative Carriers', 'Communications',
    ),
    'Transportation': (
        'Transportation Cargo', 'Transportation: Cargo', 'Transportation Consumer',
        'Transportation: Consumer', 'Transportation Infrastructure', 'Ground Transportation',
        'Airlines', 'Passenger Airlines', 'Marine',
    ),
    'Utilities': (
        'Electric Utilities', 'Utilities, Electric', 'Utilities: Electric', 'Gas Utilities',
        'Water Utilities',
    ),
})
