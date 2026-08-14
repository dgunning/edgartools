"""
BDC Portfolio Investment data models.

This module provides structured access to individual investment holdings
from a BDC's Schedule of Investments (SOI).
"""
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from datetime import date
from typing import Optional

import pandas as pd
from rich import box
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich

log = logging.getLogger(__name__)

__all__ = [
    'DataQuality',
    'PortfolioInvestment',
    'PortfolioInvestments',
]

# XBRL concepts for investment data
CONCEPT_FAIR_VALUE = 'us-gaap_InvestmentOwnedAtFairValue'
CONCEPT_COST = 'us-gaap_InvestmentOwnedAtCost'
CONCEPT_PRINCIPAL = 'us-gaap_InvestmentOwnedBalancePrincipalAmount'
CONCEPT_SHARES = 'us-gaap_InvestmentOwnedBalanceShares'
CONCEPT_INTEREST_RATE = 'us-gaap_InvestmentInterestRate'
CONCEPT_PIK_RATE = 'us-gaap_InvestmentInterestRatePaidInKind'
CONCEPT_SPREAD = 'us-gaap_InvestmentBasisSpreadVariableRate'
CONCEPT_PCT_NET_ASSETS = 'us-gaap_InvestmentOwnedPercentOfNetAssets'

# Entity-level aggregate concepts (not per-investment)
CONCEPT_NONACCRUAL_LOANS_FV = 'us-gaap:FairValueOptionLoansHeldAsAssetsAggregateAmountInNonaccrualStatus'

# Known investment types for parsing (order matters - more specific first)
INVESTMENT_TYPES = [
    # Secured Debt (used by some BDCs like Main Street)
    'First lien debt',
    'First lien secured debt',
    'Second lien debt',
    'Second lien secured debt',
    'Senior secured debt',
    'Secured debt',
    # Loans - most specific first
    'First lien senior secured revolving loan',
    'First lien senior secured delayed draw term loan',
    'First lien senior secured term loan',
    'First lien senior secured loan',
    'First-lien holdco loan',
    'First-lien revolving loan',
    'First-lien loan',
    'Second-lien loan',
    'First lien secured debt - delayed draw',
    'First lien secured debt - revolver',
    'First lien secured debt - term loan',
    '1st lien/senior secured debt',
    '2nd lien/senior secured debt',
    '1st lien/last-out unitranche',
    '1st lien, secured loan',
    '2nd lien, secured loan',
    'Second lien senior secured loan',
    'Senior secured revolving loan',
    'Senior secured term loan',
    'Senior secured loan',
    'Senior subordinated loan',
    'Junior secured loan',
    'Subordinated certificate',
    'Subordinate debt',
    'Subordinated debt',
    'Subordinated loan',
    'Subordinated note',
    'Structured note',
    'Unsecured debt',
    'Unsecured loan',
    'Mezzanine debt',
    'Mezzanine loan',
    'Convertible promissory note A',
    'Promissory note',
    'Other debt',
    'Corporate bonds',
    'Equipment financing',
    'Secured bond',
    'Unsecured bond',
    'Secured loan',
    'Term loan',
    'Revolver',
    'Revolving loan',
    # Preferred
    'Series A-1 preferred units',
    'Series A-1 preferred stock',
    'Series A preferred units',
    'Series A preferred shares',
    'Series A preferred stock',
    'Series B preferred units',
    'Series B preferred shares',
    'Series B preferred stock',
    'Series C-1 preferred shares',
    'Series C-2 preferred shares',
    'Series C preferred shares',
    'Series C preferred units',
    'Series D preferred units',
    'Series D units',
    'Series E units',
    'Senior preferred units',
    'Senior preferred stock',
    'Junior preferred stock',
    'Preferred equity interest',
    'Preferred shares',
    'Preferred stock',
    'Preferred units',
    'Preferred equity',
    # Common equity
    'Class A-1 common units',
    'Class A-2 common units',
    'Class A common units',
    'Class A common stock',
    'Class B common units',
    'Class B common stock',
    'Class C common units',
    'Common equity/warrants',
    'Common units',
    'Common stock',
    'Common shares',
    'Common equity',
    'Ordinary shares',
    # Class units (without common/preferred qualifier)
    'Class A-1 units',
    'Class A-2 units',
    'Class A units',
    'Class B units',
    'Class C units',
    'Class AA units',
    'Class C-1 units',
    # Member units (used by some BDCs like Main Street)
    'Class AA Preferred Member Units',
    'Class A Preferred Member Units',
    'Class B Preferred Member Units',
    'Preferred Member Units',
    'Class A Member Units',
    'Class B Member Units',
    'Member Units',
    # Other equity
    'LLC units',
    'LLC interest',
    'LP units',
    'LP interest',
    'Membership units',
    'Membership interest',
    'Member interest',
    'Class A membership units',
    'Class B membership units',
    'Partnership interest',
    'Partnership',
    'Equity interests',
    'Equity interest',
    'Earnout interests',
    'Equity',
    # Warrants
    'Warrants to purchase shares of common stock',
    'Warrant to purchase shares of common stock',
    'Warrant to purchase common stock',
    'Warrant to purchase units',
    'Warrants',
    'Warrant',
    'Options',
    # Series units
    'Series A common units',
    'Series B common units',
    'Series A units',
    'Series B units',
    'Series C units',
    # Class interests
    'Class A common interest',
    'Class B common interest',
    'Class A preferred units',
    'Class B preferred units',
    # Certificates
    'Trust certificates',
    'Subordinated certificates',
    'Senior certificates',
    'Certificates',
    # Notes
    'First lien senior secured note',
    'Second lien senior secured note',
    'First-lien note',
    'Second-lien note',
    'Senior secured note',
    'Senior subordinated note',
    'Subordinated note',
    'Unsecured note',
    # Partnership/LP interests
    'Limited partnership interests',
    'Limited partnership interest',
    'Limited partner interests',
    'Limited partner interest',
    'Limited partnership units',
    'General partnership interest',
    'Partnership units',
    'Class A LP interests',
    'Class A LP interest',
    'LP interests',
    # Notes (plural forms)
    'First lien senior secured notes',
    'Second lien senior secured notes',
    'Senior secured notes',
    'Senior subordinated notes',
    'Subordinated notes',
    'Unsecured notes',
    # Additional preferred
    'Series A-2 preferred shares',
    'Series A-3 preferred shares',
    'Series C-3 preferred shares',
    'Middle preferred shares',
    'Convertible preference shares',
    'Warrant to purchase shares of Series C preferred stock',
    'Warrant to purchase shares of Series A preferred stock',
    'Warrant to purchase shares of Series B preferred stock',
    # Additional common
    'Class A-1 common stock',
    'Series C common units',
    'Common member units',
    # BDC-specific instrument types
    'One stop',  # GBDC's primary type — unitranche / single-tranche loans
    'Delayed draw term loan',
    'Delayed draw',
    'Structured mezzanine',
    'Structured credit',
    'US Government Securities',
    'ABF Equity',  # Asset-based finance equity
    'Senior secured',  # HTGC format
    # Other
    'Loan instrument units',
    'Co-invest units',
    'Series E-1 preferred stock',
    'Warrant to purchase units of Class A common units',
]


_STRUCTURED_FIELD_RE = re.compile(
    r'(?:\b(?:Initial Acquisition Date|Issuer Name|Type of Investment|'
    r'Industry Classification|Industry|Interest Rate|Acquisition|Maturity(?: Date)?)|'
    r'Investment Type)\b',
    re.IGNORECASE,
)

_PAIRED_INVESTMENT_TYPE_RE = re.compile(
    r'\b(?P<type>(?:First Lien Senior Secured Loan|Lien Senior Secured Loan|'
    r'First Lien Secured Debt|Second Lien Secured Debt|Unsecured Debt|Secured Debt|'
    r'Structured Products and Other|Common Equity|Preferred Equity|Warrants)'
    r'\s*[-\u2013\u2014]\s*.+?)'
    r'(?=\s+(?:Initial Acquisition Date|Acquisition|Interest Rate|Reference Rate|Maturity(?: Date)?|'
    r'SOFR|LIBOR|EURIBOR|SONIA|CORRA|BBKM|BBSY|Prime)\b|$)',
    re.IGNORECASE,
)

_PORTFOLIO_CATEGORY_RE = re.compile(
    r'^(?:debt investment|equity investment|affiliate investment|control investment|'
    r'controlled investment|other investment|equity and other investment|portfolio company|'
    r'non-controlled|non-affiliate)',
    re.IGNORECASE,
)

_GENERIC_COMPANY_MEMBER_RE = re.compile(
    r'^(?:inc|llc|l l c|lp|l p|ltd|limited|corp|corporation|company|'
    r'(?:holding|holdco|acquisition|international)(?: usa)?(?: inc| llc| ltd| limited|'
    r'corp| corporation)?)$',
    re.IGNORECASE,
)


def _normalize_member_text(value: str) -> str:
    tokens = re.findall(r'[A-Za-z0-9]+', value.lower())
    return ' '.join(
        token[:-1] if len(token) > 3 and token.endswith('s') and not token.endswith('ss') else token
        for token in tokens
    )


def _strip_trailing_member_candidate(
    value: str,
    member_candidates: tuple[str, ...],
) -> str:
    """Remove a trailing taxonomy industry while preserving the company span."""
    normalized_value = _normalize_member_text(value)
    suffixes = [
        candidate for candidate in member_candidates
        if normalized_value.endswith(f' {candidate}')
        if not _PORTFOLIO_CATEGORY_RE.match(candidate)
        if not _GENERIC_COMPANY_MEMBER_RE.fullmatch(candidate)
    ]
    if not suffixes:
        return value.strip()

    suffix_tokens = len(max(suffixes, key=len).split())
    value_tokens = list(re.finditer(r'[A-Za-z0-9]+', value))
    company_name = value[:value_tokens[-suffix_tokens].start()].rstrip(' ,')
    return company_name.strip()


def _get_investment_member_candidates(xbrl) -> tuple[str, ...]:
    """Collect normalized taxonomy member labels used to bound company names."""
    candidates = set()
    for element_name, element in xbrl.element_catalog.items():
        if not element_name.lower().endswith('member'):
            continue
        for label in element.labels.values():
            candidate = re.sub(r'\s*\[Member\]\s*$', '', label).strip()
            if 1 < len(candidate) <= 120:
                normalized_candidate = _normalize_member_text(candidate)
                if normalized_candidate:
                    candidates.add(normalized_candidate)
    return tuple(candidates)


def _known_investment_type_matches(identifier: str) -> list[re.Match]:
    matches = []
    for investment_type in INVESTMENT_TYPES:
        for match in re.finditer(re.escape(investment_type), identifier, re.IGNORECASE):
            starts_at_boundary = match.start() == 0 or not identifier[match.start() - 1].isalnum()
            follows_member_code = bool(re.search(r'\b[A-Z]\d{1,3}$', identifier[:match.start()]))
            ends_at_boundary = match.end() == len(identifier) or not identifier[match.end()].isalnum()
            if (starts_at_boundary or follows_member_code) and ends_at_boundary:
                matches.append(match)
    matches = [
        match for match in matches
        if identifier.rfind('(', 0, match.start()) <= identifier.rfind(')', 0, match.start())
    ]
    return [
        match for match in matches
        if not any(
            other.start() <= match.start()
            and other.end() >= match.end()
            and (other.end() - other.start()) > (match.end() - match.start())
            for other in matches
        )
    ]


def _anchored_investment_type_match(identifier: str, type_matches: list[re.Match]) -> Optional[re.Match]:
    for match in sorted(type_matches, key=lambda item: item.start()):
        if re.search(
            r'\bInvestment(?:\s+[A-Z]\d{1,3})?\s*$',
            identifier[:match.start()],
            re.IGNORECASE,
        ):
            return match
    return None


def _portfolio_company_fields(
    identifier: str,
    member_candidates: tuple[str, ...] = (),
) -> Optional[tuple[str, str]]:
    relationship_equity = re.match(
        r'^(?:Control|Affiliate) Investments Equity Investments\s+(?P<company>.+)$',
        identifier,
        re.IGNORECASE,
    )
    if relationship_equity and not _STRUCTURED_FIELD_RE.search(identifier):
        return relationship_equity.group('company').strip(), 'Equity'

    relationship_debt = re.match(
        r'^(?:Control|Affiliate) Investments Debt Investments\s+(?P<body>.+)$',
        identifier,
        re.IGNORECASE,
    )
    if relationship_debt and not _STRUCTURED_FIELD_RE.search(identifier):
        body = relationship_debt.group('body')
        leading_types = [match for match in _known_investment_type_matches(body) if match.start() == 0]
        if leading_types:
            type_match = max(leading_types, key=lambda match: match.end())
            return body[type_match.end():].strip(), type_match.group().strip()

    short_term_investment = re.match(
        r'^Short-Term Investments\s+(?P<company>.+)$',
        identifier,
        re.IGNORECASE,
    )
    if short_term_investment:
        return short_term_investment.group('company').strip(), 'Short-Term Investments'

    truncated_warrants = re.match(r'^/Warrants\s+(?P<company>.+)$', identifier, re.IGNORECASE)
    if truncated_warrants:
        company_name = re.sub(
            r'\s+-\s+Warrants$',
            '',
            truncated_warrants.group('company'),
            flags=re.IGNORECASE,
        ).strip()
        return company_name, 'Warrants'

    portfolio_match = re.match(
        r'^(?:Investments\s+)?in .+? Portfolio Companies\s+(?P<body>.+)$',
        identifier,
        re.IGNORECASE,
    )
    if not portfolio_match:
        return None

    body = portfolio_match.group('body')
    lien_prefix = re.match(
        r'^(?P<lien>First|Second) Lien\s*/\s*Senior Secured Debt\s+(?P<fields>.+)$',
        body,
        re.IGNORECASE,
    )
    if lien_prefix:
        investment_type = f"{lien_prefix.group('lien')} Lien/Senior Secured Debt"
        company_and_fields = lien_prefix.group('fields').strip()
    else:
        leading_types = [
            match for match in _known_investment_type_matches(body)
            if match.start() == 0
        ]
        if not leading_types:
            return None
        type_match = max(leading_types, key=lambda match: match.end())
        investment_type = type_match.group().strip()
        company_and_fields = body[type_match.end():].strip()

    continuation_units = re.match(
        r'^and (?P<type>Membership Units|Units)\s+(?P<fields>.+)$',
        company_and_fields,
        re.IGNORECASE,
    )
    if continuation_units:
        investment_type = f"{investment_type} and {continuation_units.group('type')}"
        company_and_fields = continuation_units.group('fields').strip()

    issuer_path = re.match(
        r'^(?P<type_path>/.*?)?(?:of Net Assets\s+)?Issuer(?: Name)?\s+(?P<fields>.+)$',
        company_and_fields,
        re.IGNORECASE,
    )
    if issuer_path:
        company_and_fields = issuer_path.group('fields').strip()
        type_path = issuer_path.group('type_path')
        if type_path:
            investment_type = f'{investment_type}{type_path.strip()}'
    field_match = re.search(
        r'\s+(?:Acquisitions?(?=\s+\d)|Maturity(?: Date)?|Industry(?: Classification)?|'
        r'Current Coupon|Interest Rate|Reference Rate(?: and Spread)?)\b',
        company_and_fields,
        re.IGNORECASE,
    )
    company_and_detail = company_and_fields[:field_match.start() if field_match else None].strip()
    repeated_type = re.match(
        rf'^(?P<company>.+?)\s+(?:[-\u2013\u2014]\s+)?'
        rf'(?P<detail>{re.escape(investment_type)}\s*[-\u2013\u2014]\s*.+)$',
        company_and_detail,
        re.IGNORECASE,
    )
    if repeated_type:
        company_name = repeated_type.group('company').strip()
        detail = repeated_type.group('detail').strip()
    else:
        company_and_detail = re.split(r'\s+[-\u2013\u2014]\s*', company_and_detail, maxsplit=1)
        if len(company_and_detail) == 1:
            legal_suffix_detail = re.match(
                r'^(?P<company>.+?\b(?:LLC|Inc\.?|LP|Corp\.?))\s*[-\u2013\u2014]\s*(?P<detail>.+)$',
                company_and_detail[0],
                re.IGNORECASE,
            )
            if legal_suffix_detail:
                company_and_detail = [
                    legal_suffix_detail.group('company'),
                    legal_suffix_detail.group('detail'),
                ]
        company_name = company_and_detail[0].strip()
        detail = company_and_detail[1].strip() if len(company_and_detail) > 1 else ''

    if detail:
        if detail.casefold().startswith(f'{investment_type.casefold()} -'):
            investment_type = detail
        elif detail.casefold() != investment_type.casefold():
            investment_type = f'{investment_type} - {detail}'
    company_name = _strip_trailing_member_candidate(company_name, member_candidates)
    named_facility = re.search(
        r'\s+(?P<facility>(?:First|Second) Lien,\s*Term Loan [A-Z0-9-]+)$',
        company_name,
        re.IGNORECASE,
    )
    if named_facility:
        company_name = company_name[:named_facility.start()].strip()
        investment_type = f"{investment_type} - {named_facility.group('facility')}"
    parenthetical_facility = re.search(
        r'\s+\((?P<facility>Revolver|(?:[^()]+ )?Delayed Draw Term Loan|'
        r'Term Loan [A-Z0-9-]+|Second Out|Third Out|Super Senior [A-Z])\)$',
        company_name,
        re.IGNORECASE,
    )
    if parenthetical_facility:
        company_name = company_name[:parenthetical_facility.start()].strip()
        investment_type = f"{investment_type} - {parenthetical_facility.group('facility')}"
    if 'warrant' in investment_type.casefold():
        company_name = re.sub(r'\s+\(Warrants?\)$', '', company_name, flags=re.IGNORECASE)
    if investment_type.casefold().startswith('preferred equity'):
        series = re.search(
            r'\s+\((?P<series>[A-Z]-\d+\s+Series)\)$',
            company_name,
            re.IGNORECASE,
        )
        if series:
            company_name = company_name[:series.start()].strip()
            investment_type = f"{investment_type} - {series.group('series')}"
        company_name = re.sub(r'\s+Preferred$', '', company_name, flags=re.IGNORECASE)
    return company_name, investment_type


def _structured_company_window(
    identifier: str,
    member_candidates: tuple[str, ...] = (),
) -> Optional[str]:
    portfolio_fields = _portfolio_company_fields(identifier, member_candidates)
    if portfolio_fields:
        return portfolio_fields[0]

    issuer_match = re.search(r'\bIssuer Name\s+', identifier, re.IGNORECASE)
    if issuer_match:
        tail = identifier[issuer_match.end():]
        end_match = re.search(
            r'\s+-\s+|\s+(?:First|Second)\s+Lien\s*-\s*|'
            r'\s+(?:Acquisition|Maturity(?: Date)?|Industry(?: Classification)?|'
            r'Current Coupon|Interest Rate|Reference Rate)\b',
            tail,
            re.IGNORECASE,
        )
        return tail[:end_match.start() if end_match else None].strip()

    type_field = re.search(
        r'(?:Investment Type|\b(?:Type of Investment|Facility Type))\b',
        identifier,
        re.IGNORECASE,
    )
    if type_field:
        return identifier[:type_field.start()].strip()

    industry_field = re.search(r'\bIndustry(?: Classification)?\b', identifier, re.IGNORECASE)
    if industry_field:
        return identifier[:industry_field.start()].strip()

    type_matches = _known_investment_type_matches(identifier)
    if type_matches:
        type_match = _anchored_investment_type_match(identifier, type_matches)
        if type_match is None:
            type_match = max(type_matches, key=lambda match: (match.start(), match.end() - match.start()))
        company_window = identifier[:type_match.start()]
        return re.sub(
            r'\bInvestment(?:\s+[A-Z]\d{1,3})?\s*$',
            '',
            company_window,
            flags=re.IGNORECASE,
        ).strip()
    return None


def _match_company_candidate(window: str, member_candidates: tuple[str, ...]) -> Optional[str]:
    category_matches = list(
        re.finditer(
            r'\b(?:Equity and Other Investments|Debt Investments|Equity Investments|Other Investments)\b',
            window,
            re.IGNORECASE,
        )
    )
    if len(category_matches) > 1:
        window = window[category_matches[-1].start():].strip()

    window_tokens = list(re.finditer(r'[A-Za-z0-9]+', window))
    normalized_window = _normalize_member_text(window)
    suffixes = [
        candidate for candidate in member_candidates
        if normalized_window == candidate or normalized_window.endswith(f' {candidate}')
        if not _PORTFOLIO_CATEGORY_RE.match(candidate)
        if normalized_window == candidate or not _GENERIC_COMPANY_MEMBER_RE.fullmatch(candidate)
    ]
    if suffixes:
        company_tokens = len(max(suffixes, key=len).split())
        company_start = window_tokens[-company_tokens].start()
        if window.rfind('(', 0, company_start) <= window.rfind(')', 0, company_start):
            company_name = window[company_start:].strip()
            if company_name.count('(') >= company_name.count(')'):
                return company_name

    other_investments = re.match(r'^Other Investments\s+(?P<company>.+)$', window, re.IGNORECASE)
    if other_investments:
        return other_investments.group('company').strip()

    # Typed identifiers may not have a company member. In that case, remove
    # portfolio/category prefixes and the longest taxonomy industry prefix.
    cleaned_window = re.sub(
        r'^(?:(?:[A-Z]?Investments[-\u2013\u2014][\w/-]+|'
        r'Non-(?:control|controlled)/Non-Affiliate(?:d)?(?: Investments)?|'
        r'Non-Controlled/Affiliate Investments|'
        r'Non-affiliate Investments|Controlled Affiliate Investments|Controlled Investments|'
        r'Affiliate Investments|Control Investments|Debt Investments|Equity Investments|Warrants?|'
        r'Issuer Name|'
        r'Equity and Other Investments|Equity Securities|Corporate Bonds|CLO Mezzanine|CLO Equity|'
        r'US Corporate Debt|U\.S\. Debt|'
        r'Senior Secured U\.S\. Notes|U\.S\. Dollar|European Currency|British Pound|'
        r'Canadian Dollar|Australian Dollar|New Zealand Dollar|'
        r'First Lien Senior Secured U\.S\. Debt|'
        r'Second Lien Senior Secured(?: U\.S\. Debt)?|'
        r'First Lien Senior Secured Canadian Debt(?: Information)?|'
        r'Portfolio Company (?:Debt Securities|Equity Investments|Warrant Investments)\s*'
        r'[-\u2013\u2014]\s*(?:United States|Canada|Europe))\s+)+',
        '',
        window,
        flags=re.IGNORECASE,
    )
    removed_prefix = cleaned_window != window
    acronym_prefix = re.match(
        r'^.+?\(["\'](?P<acronym>[^"\']+)["\']\)\s+(?P<company>.+)$',
        cleaned_window,
    )
    if acronym_prefix and _normalize_member_text(acronym_prefix.group('acronym')) in member_candidates:
        cleaned_window = acronym_prefix.group('company').strip()
        removed_prefix = True
    last_prefix = None
    for _ in range(4):
        cleaned_tokens = list(re.finditer(r'[A-Za-z0-9]+', cleaned_window))
        normalized_cleaned = _normalize_member_text(cleaned_window)
        suffixes = [
            candidate for candidate in member_candidates
            if normalized_cleaned == candidate or normalized_cleaned.endswith(f' {candidate}')
            if not _PORTFOLIO_CATEGORY_RE.match(candidate)
            if normalized_cleaned == candidate or not _GENERIC_COMPANY_MEMBER_RE.fullmatch(candidate)
        ]
        if suffixes:
            company_tokens = len(max(suffixes, key=len).split())
            company_start = cleaned_tokens[-company_tokens].start()
            if cleaned_window.rfind('(', 0, company_start) <= cleaned_window.rfind(')', 0, company_start):
                company_name = cleaned_window[company_start:].strip()
                if company_name.count('(') >= company_name.count(')'):
                    return company_name

        prefixes = [
            candidate for candidate in member_candidates
            if normalized_cleaned.startswith(f'{candidate} ')
            if not _GENERIC_COMPANY_MEMBER_RE.fullmatch(candidate)
        ]
        if not prefixes:
            return cleaned_window.strip() if removed_prefix else None
        prefix = max(prefixes, key=len)
        if prefix == last_prefix:
            return cleaned_window.strip()
        prefix_tokens = len(prefix.split())
        prefix_tail = cleaned_window[cleaned_tokens[prefix_tokens - 1].end():].strip()
        if re.fullmatch(r'[\s.,)]*\([^)]*\)', prefix_tail):
            return cleaned_window.strip()
        remaining_window = cleaned_window[cleaned_tokens[prefix_tokens].start():].strip()
        if _GENERIC_COMPANY_MEMBER_RE.fullmatch(_normalize_member_text(remaining_window)):
            return cleaned_window.strip()
        cleaned_window = remaining_window
        removed_prefix = True
        last_prefix = prefix
    return cleaned_window.strip()


def _extract_structured_investment_type(
    identifier: str,
    member_candidates: tuple[str, ...] = (),
) -> str:
    portfolio_fields = _portfolio_company_fields(identifier, member_candidates)
    if portfolio_fields:
        return portfolio_fields[1]

    type_field = re.search(
        r'(?:Investment Type|\b(?:Type of Investment|Facility Type|Security))\s+(?P<type>.+?)'
        r'(?=\s+(?:Initial Acquisition Date|Investment Date|Acquisition|Maturity(?: Date)?|'
        r'Interest Rate|Reference Rate|All in Rate|Benchmark|Industry Classification|Current Coupon)\b|$)',
        identifier,
        re.IGNORECASE,
    )
    if type_field:
        investment_type = type_field.group('type').strip()
        warrant_type = re.match(r'Warrants?\b', investment_type, re.IGNORECASE)
        if warrant_type:
            return warrant_type.group()
        return re.split(
            r'\s+(?=(?:SOFR|LIBOR|Prime|Fixed interest|Variable interest|\d+(?:\.\d+)?%))',
            investment_type,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0].strip()

    issuer_match = re.search(r'\bIssuer Name\b', identifier, re.IGNORECASE)
    if issuer_match:
        after_issuer = identifier[issuer_match.end():]
        dash_type = re.search(r'\s+-\s+(?P<type>.+?)\s+Acquisition\b', after_issuer, re.IGNORECASE)
        if dash_type:
            return dash_type.group('type').strip()

    type_matches = _known_investment_type_matches(identifier)
    if type_matches:
        match = _anchored_investment_type_match(identifier, type_matches)
        if match is None:
            match = max(type_matches, key=lambda item: (item.start(), item.end() - item.start()))
        return match.group().strip()
    return "Unknown"


def _parse_percentage_hierarchy(
    identifier: str,
    member_candidates: tuple[str, ...],
) -> Optional[tuple[str, str]]:
    company_path = re.split(r'\s+Industry', identifier, maxsplit=1, flags=re.IGNORECASE)[0]
    company_path = re.sub(
        r'^(?:Investment\s+)?(?:Debt Investments|Equity Securities)\s*[-\u2013\u2014]\s*',
        '',
        company_path,
        flags=re.IGNORECASE,
    )
    hierarchy_match = re.match(
        r'^\d+(?:\.\d+)?%\s+.+?\s+[-\u2013\u2014]\s+\d+(?:\.\d+)?%\s+'
        r'(?P<type>.+?)\s+[-\u2013\u2014]\s+\d+(?:\.\d+)?%\s+(?P<company>.+)$',
        company_path,
        re.IGNORECASE,
    )
    if not hierarchy_match:
        return None

    company_name = hierarchy_match.group('company').strip()
    normalized_company = _normalize_member_text(company_name)
    candidate_prefixes = [
        candidate for candidate in member_candidates
        if normalized_company == candidate or normalized_company.startswith(f'{candidate} ')
        if not _PORTFOLIO_CATEGORY_RE.match(candidate)
    ]
    if candidate_prefixes:
        company_tokens = list(re.finditer(r'[A-Za-z0-9]+', company_name))
        candidate_token_count = len(max(candidate_prefixes, key=len).split())
        if candidate_token_count < len(company_tokens):
            company_name = company_name[:company_tokens[candidate_token_count].start()].strip()
    investment_type = re.sub(r'\s*\(\d+\)$', '', hierarchy_match.group('type')).strip()
    return company_name, investment_type


def _parse_structured_identifier(
    identifier: str,
    member_candidates: tuple[str, ...],
) -> Optional[tuple[str, str]]:
    clo_subordinated_note = re.match(
        r'^(?P<company>.+?)\s+(?P<type>CLO Subordinated Notes)\s+(?P<detail>.+)$',
        identifier,
        re.IGNORECASE,
    )
    if clo_subordinated_note:
        return (
            clo_subordinated_note.group('company').strip(),
            f"{clo_subordinated_note.group('type')} - "
            f"{clo_subordinated_note.group('detail').strip()}",
        )

    labeled_security = re.match(
        r'^(?P<company>.+?)\s+Industry\s+.+?\s+Security\s+(?P<type>.+?)'
        r'(?=\s+(?:Interest Rate|(?:\d+[DMY]\s+)?SOFR|Initial Acquisition Date|'
        r'Acquisition Date|Maturity)\b|$)',
        identifier,
        re.IGNORECASE,
    )
    if labeled_security:
        return labeled_security.group('company').strip(), labeled_security.group('type').strip()

    missing_security_label = re.match(
        r'^(?P<company>.+?)\s+Industry\s+.+?\s+'
        r'(?P<type>(?:Unsecured|Secured) Bond)\s+'
        r'(?=Interest Rate|Initial Acquisition Date|Acquisition Date|Maturity\b)',
        identifier,
        re.IGNORECASE,
    )
    if missing_security_label:
        return (
            missing_security_label.group('company').strip(),
            missing_security_label.group('type').strip(),
        )

    short_term_security = re.match(
        r'^(?P<company>.+?)\s+Short-Term Investments\s+'
        r'(?P<type>Money Market|Treasury Bill)\s+Interest Rate\b',
        identifier,
        re.IGNORECASE,
    )
    if short_term_security:
        return (
            short_term_security.group('company').strip(),
            f"Short-Term Investments - {short_term_security.group('type').strip()}",
        )

    continuation_units = re.match(
        r'^and (?P<type>Membership Units|Units)\s+(?P<company>.+)$',
        identifier,
        re.IGNORECASE,
    )
    if continuation_units:
        company_name = _strip_trailing_member_candidate(
            continuation_units.group('company'),
            member_candidates,
        )
        return company_name, continuation_units.group('type')

    portfolio_category = re.match(
        r'^Investments in .+? Portfolio Companies\s+'
        r'(?P<category>Collateralized Loan Obligations|Derivatives|Joint Ventures|'
        r'Asset Manager Affiliates)\s+(?P<body>.+)$',
        identifier,
        re.IGNORECASE,
    )
    if portfolio_category:
        category = portfolio_category.group('category')
        body = portfolio_category.group('body')
        clo = re.match(
            r'(?P<company>.+?)\s+(?P<type>CLO Fund Securities)\s+Maturity\b',
            body,
            re.IGNORECASE,
        )
        if clo:
            return clo.group('company').strip(), clo.group('type')

        joint_venture = re.match(r'(?P<company>.+?)\s+Joint Venture$', body, re.IGNORECASE)
        if joint_venture:
            return joint_venture.group('company').strip(), 'Joint Venture'

        company_name = _strip_trailing_member_candidate(body, member_candidates)
        if category.casefold() == 'asset manager affiliates':
            duplicate_name = re.fullmatch(
                r'(?P<company>.+)\s+(?P=company)',
                company_name,
                re.IGNORECASE,
            )
            if duplicate_name:
                company_name = duplicate_name.group('company')
        return company_name, category

    us_equity = re.match(
        r'^U\.S\. (?:Preferred Stock|Warrants)\s+(?P<body>.+?)\s+'
        r'(?P<type>(?:[A-Z]-\d+\s+)?(?:Preferred|Warrants))\s+'
        r'Initial Acquisition Date\b',
        identifier,
        re.IGNORECASE,
    )
    if us_equity:
        company_name = _match_company_candidate(
            us_equity.group('body'),
            member_candidates,
        )
        if company_name:
            return company_name, us_equity.group('type')

    portfolio_fields = _portfolio_company_fields(identifier, member_candidates)
    if portfolio_fields:
        return portfolio_fields

    leading_warrant = re.match(
        r'^(?P<type>Warrants?)\s+(?P<company>.+)$',
        identifier,
        re.IGNORECASE,
    )
    if leading_warrant:
        company_name = _match_company_candidate(
            leading_warrant.group('company'),
            member_candidates,
        )
        if company_name:
            company_name = re.sub(r'Investment$', '', company_name).rstrip(',').strip()
            return company_name, leading_warrant.group('type')

    hierarchy_result = _parse_percentage_hierarchy(identifier, member_candidates)
    if hierarchy_result:
        return hierarchy_result

    paired_type = _PAIRED_INVESTMENT_TYPE_RE.search(identifier)
    if paired_type:
        company_name = _match_company_candidate(
            identifier[:paired_type.start()].strip(),
            member_candidates,
        )
        if company_name:
            company_name = re.sub(
                r'^\(?[^)]*(?:dba|f/?k/?a)[^)]*\)\s+',
                '',
                company_name,
                flags=re.IGNORECASE,
            )
            duplicate_name = re.fullmatch(r'(?P<company>.+)\s+(?P=company)', company_name, re.IGNORECASE)
            if duplicate_name:
                company_name = duplicate_name.group('company')
            company_name = re.sub(r'\s+[-\u2013\u2014]\s*$', '', company_name).strip()
            return company_name, paired_type.group('type').strip()

    if not _STRUCTURED_FIELD_RE.search(identifier) and not _known_investment_type_matches(identifier):
        return None

    company_window = _structured_company_window(identifier, member_candidates)
    if not company_window:
        return None

    security_detail = re.search(
        r'\s+[-\u2013\u2014]\s+(?P<detail>Series [A-Z0-9-]+|'
        r'Class [A-Z0-9-]+ Preferred|Preferred|Warrant|Put Option)$',
        company_window,
        re.IGNORECASE,
    )
    if security_detail:
        company_window = company_window[:security_detail.start()].strip()

    portfolio_equity_or_warrant = re.match(
        r'^Portfolio Company (?:Equity|Warrant) Investments\s*[-\u2013\u2014]',
        identifier,
        re.IGNORECASE,
    )
    if portfolio_equity_or_warrant:
        company_window = re.sub(
            r'\s+(?:One|Two|Three)$',
            '',
            company_window,
            flags=re.IGNORECASE,
        )

    company_name = _match_company_candidate(company_window, member_candidates)
    if company_name is None and (
        re.search(r'\bIssuer Name\b', identifier, re.IGNORECASE)
        or _portfolio_company_fields(identifier, member_candidates)
    ):
        company_name = company_window
    if company_name is None:
        return None

    investment_type = _extract_structured_investment_type(identifier, member_candidates)
    if investment_type == "Unknown":
        return None
    if portfolio_equity_or_warrant:
        company_name = re.sub(
            r'\s+(?:One|Two|Three)$',
            '',
            company_name,
            flags=re.IGNORECASE,
        )
        series = re.search(r'\s+Series\s+(?P<series>.+)$', identifier, re.IGNORECASE)
        if series:
            investment_type = f"{investment_type} - {series.group('series').strip()}"
        elif investment_type.casefold() == 'warrant':
            warrant_detail = re.search(
                r'\s+(?:Expiration|Maturity) Date\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}\s+'
                r'(?P<series>Ordinary)$',
                identifier,
                re.IGNORECASE,
            )
            if warrant_detail:
                investment_type = f"{investment_type} - {warrant_detail.group('series')}"
    if security_detail:
        investment_type = f"{investment_type} - {security_detail.group('detail')}"
    company_name = re.sub(r'(?<=\S)Investment$', '', company_name).rstrip(',').strip()
    company_name = re.sub(r'\s+[-\u2013\u2014]\s*$', '', company_name).strip()
    company_name = re.sub(
        r'\s*\|\s*(?=(?:LLC|L\.L\.C\.|LP|L\.P\.|Inc\.?|Corp\.?)\b)',
        ', ',
        company_name,
        flags=re.IGNORECASE,
    ).rstrip('|').strip()
    facility = re.search(
        r'\s+\((?P<facility>Revolver|Delayed Draw|Term Loan)\)$',
        company_name,
        re.IGNORECASE,
    )
    if facility:
        company_name = company_name[:facility.start()].strip()
        facility_type = facility.group('facility')
        if facility_type.casefold() not in investment_type.casefold():
            investment_type = f'{investment_type} - {facility_type}'
    return company_name, investment_type


def _parse_investment_identifier(
    dimension_label: str,
    member_candidates: tuple[str, ...] = (),
) -> tuple[str, str, str]:
    """
    Parse the dimension label to extract company name and investment type.

    Handles multiple formats:
    1. ARCC format: "Company Name, First lien senior secured loan"
    2. HTGC format: "Debt Investments Software and Armis, Inc., Senior Secured, Maturity Date..."
    3. FDUS format: "Non-control/Non-affiliate Investments Company LLC Industry First Lien Debt ..."
    4. Structured format: "... Issuer Name Company LLC ... Maturity Date ..."
    5. Category rollups: "Debt Investments Software (52.80%)" - treated as Unknown type

    Args:
        dimension_label: The full dimension label, e.g.,
            "us-gaap:InvestmentIdentifierAxis: Company Name, First lien senior secured loan"

    Returns:
        Tuple of (identifier, company_name, investment_type)
    """
    # Strip the axis prefix
    identifier = dimension_label
    if ':' in dimension_label:
        parts = dimension_label.split(': ', 1)
        if len(parts) > 1:
            identifier = parts[1].strip()

    # Check for category rollup pattern (e.g., "Debt Investments Software (52.80%)")
    # These should be excluded as they're not individual investments
    if re.search(r'\(\d+\.\d+%\)\s*$', identifier):
        return identifier, identifier, "Unknown"
    if re.fullmatch(
        r'(?:Control|Affiliate|Control and Affiliate) Investments',
        identifier,
        re.IGNORECASE,
    ):
        return identifier, identifier, "Unknown"
    if re.fullmatch(
        r'(?:Prime Rate|(?:SOFR|CORRA) \d+-Month Term Rate|Bank of England Base Rate|'
        r'Foreign Currency Forward Contracts Counterparty|Formation Transactions)',
        identifier,
        re.IGNORECASE,
    ):
        return identifier, identifier, "Unknown"
    if re.fullmatch(
        r'Non Controlled Affiliated(?: and Controlled)? Investments \[Member\]',
        identifier,
        re.IGNORECASE,
    ):
        return identifier, identifier, "Unknown"

    company_name = identifier
    investment_type = "Unknown"

    # Some FDUS labels leak relationship-prefix fragments into the company
    # name, e.g. "Investmnts Suited Connector LLC" or
    # "InvesAffiliate Investments Medsurant Holdings LLC".
    normalized_identifier = re.sub(
        r'^(?:InvesAffiliate Investments|Investmnts)\s+',
        '',
        identifier,
        flags=re.IGNORECASE,
    )

    # Try FDUS prose format:
    # "Non-control/Non-affiliate Investments Company Name LLC Industry First Lien Debt ..."
    # Some labels omit the trailing "Investments" and some use bare "Subordinated".
    fdus_match = None
    if not re.search(
        r'(?:Investment Type|\b(?:Type of Investment|Facility Type))\b',
        normalized_identifier,
        re.IGNORECASE,
    ):
        fdus_match = re.match(
            r'^(?P<prefix>'
            r'Non-control/Non-affiliate(?: Investments| Investmnts)?|'
            r'Affiliate(?: Investments| InvesAffiliate Investments)?|'
            r'Control(?: Investments)?'
            r')\s+'
            r'(?P<body>.+?)\s+'
            r'(?P<instrument>'
            r'First Lien Debt|Second Lien Debt|Subordinated Debt|Subordinated|'
            r'Revolving Loan|Term Loan|Unsecured Debt|Unsecured Loan|'
            r'Common Equity|Preferred Equity|Warrant|Warrants'
            r')\b',
            normalized_identifier,
            re.IGNORECASE,
        )
    if fdus_match:
        company_name = normalized_identifier
        investment_type = fdus_match.group('instrument').strip()
        body = fdus_match.group('body').strip()

        if re.match(
            r'^.*\b('
            r'LLC|L\.L\.C\.|LLP|L\.P\.|LP|Ltd|Limited|Inc|Corp|Co|'
            r'Corporation|Company|Holdings|Partners|Group|PLC'
            r')\.?(?:\s*\([^)]*\))?$',
            body,
            re.IGNORECASE,
        ):
            return identifier, body, investment_type

        # FDUS places an industry label between the company name and instrument.
        # Prefer a company-like prefix ending in a legal suffix, followed by one
        # or more title-cased industry words.
        entity_match = re.match(
            r'^(?P<company>.*\b(?:'
            r'LLC|L\.L\.C\.|LLP|L\.P\.|LP|Ltd|Limited|Inc|Corp|Co|'
            r'Corporation|Company|Holdings|Partners|Group|PLC'
            r')\.?(?:\s*\([^)]*\))?)'
            r'(?:\s+[A-Z&][A-Za-z&:/-]*)+$',
            body,
            re.IGNORECASE,
        )
        if entity_match:
            company_name = entity_match.group('company').strip()
        else:
            company_name = re.sub(
                r'\s+[A-Z][A-Za-z&:/-]*(?:\s+[A-Z][A-Za-z&:/-]*){0,3}$',
                '',
                body,
            ).strip()
            if not company_name:
                company_name = body
        return identifier, company_name, investment_type

    relationship_investment = None
    if not _STRUCTURED_FIELD_RE.search(identifier):
        relationship_investment = re.match(
            r'^(?:Affiliated|Controlled) Investments\s+(?P<company>.+),\s*(?P<type>[^,]+)$',
            identifier,
            re.IGNORECASE,
        )
    if relationship_investment:
        return (
            identifier,
            relationship_investment.group('company').strip(),
            relationship_investment.group('type').strip(),
        )

    descriptor_pipe = re.fullmatch(
        r'(?P<company>.+?)\s+\|\s+[^|]*?\b(?P<type>Debt|Equity)\s+Investment'
        r'(?:\s+\d+(?:\.\d+)*)?(?:\s+\|\s+.+)?',
        identifier,
        re.IGNORECASE,
    )
    if descriptor_pipe:
        # Title-cased because the match is case-insensitive and the label's own
        # casing varies: OBDC writes "Specialty finance equity investment", so
        # returning the captured span verbatim yielded 'equity' and 'debt' — the
        # only lowercase-initial types in the vocabulary, sitting beside
        # 'Preferred Equity' and 'Secured Debt' from every other branch. Grouping
        # by investment_type then splits the same concept across two buckets,
        # which is the thing this parsing work is meant to make reliable.
        return (
            identifier,
            descriptor_pipe.group('company').strip(),
            descriptor_pipe.group('type').strip().title(),
        )

    if ' | ' in identifier:
        for inv_type in sorted(INVESTMENT_TYPES, key=len, reverse=True):
            pipe_investment = re.fullmatch(
                rf'(?P<company>.+?)\s+\|\s+(?P<type>{re.escape(inv_type)})'
                r'(?P<facility>\s+\([^)]*\))?'
                r'(?P<detail>\s+-\s+.+?)?(?:\s+\d+(?:\.\d+)*)?',
                identifier,
                re.IGNORECASE,
            )
            if pipe_investment:
                investment_type = pipe_investment.group('type')
                facility = pipe_investment.group('facility')
                if facility:
                    investment_type = f'{investment_type}{facility}'
                detail = pipe_investment.group('detail')
                if detail:
                    investment_type = f'{investment_type}{detail}'
                return (
                    identifier,
                    pipe_investment.group('company').strip(),
                    investment_type,
                )

    # Prefer an explicit trailing delimiter over taxonomy-derived company spans.
    for inv_type in INVESTMENT_TYPES:
        trailing_type = re.fullmatch(
            rf'(?P<company>.+),\s*(?P<type>{re.escape(inv_type)})'
            r'(?:\s+\d+(?:\.\d+)*)?',
            identifier,
            re.IGNORECASE,
        )
        if trailing_type:
            company_name = trailing_type.group('company').strip()
            company_name = re.sub(
                r'\s*\|\s*(?=(?:LLC|L\.L\.C\.|LP|L\.P\.|Inc\.?|Corp\.?)\b)',
                ', ',
                company_name,
                flags=re.IGNORECASE,
            )
            return identifier, company_name, trailing_type.group('type').strip()

    structured_result = _parse_structured_identifier(identifier, member_candidates)
    if structured_result:
        company_name, investment_type = structured_result
        return identifier, company_name, investment_type

    relationship_member = re.fullmatch(
        r'(?P<relationship>Control|Affiliate) Investments\s+(?P<company>.+)',
        identifier,
        re.IGNORECASE,
    )
    if relationship_member:
        return identifier, relationship_member.group('company').strip(), 'Unknown'

    # Try pipe-separated format (e.g., "Company | Type" or "Company, Type | Industry")
    # Some BDCs (Blue Owl) put instrument type after pipe; others (FSK) put GICS
    # industry category after pipe. We check if the pipe-right matches a known
    # instrument type — if not, it's an industry label and we parse the left side.
    if ' | ' in identifier:
        pipe_parts = [p.strip() for p in identifier.split(' | ')]
        if len(pipe_parts) >= 2:
            right_side = pipe_parts[1]
            # Strip numeric suffix for matching (e.g., "Software & Services 1" → "Software & Services")
            right_base = re.sub(r'\s*\d+\s*$', '', right_side)
            right_is_instrument = any(
                re.fullmatch(
                    rf'{re.escape(inv_type)}(?:\s*\([^)]*\)|\s*[\d.]*)?',
                    right_base,
                    re.IGNORECASE,
                )
                for inv_type in INVESTMENT_TYPES
            )
            if right_is_instrument:
                company_name = pipe_parts[0]
                investment_type = right_side
                return identifier, company_name, investment_type
            else:
                # Right side is an industry category (FSK pattern).
                # Parse the left side for comma-separated instrument type.
                left_side = pipe_parts[0]
                for inv_type in INVESTMENT_TYPES:
                    pattern = rf',\s*{re.escape(inv_type)}(\s*[\d.]*)?$'
                    match = re.search(pattern, left_side, re.IGNORECASE)
                    if match:
                        company_name = left_side[:match.start()].strip()
                        investment_type = left_side[match.start() + 1:].strip()
                        return identifier, company_name, investment_type
                # No instrument type found in left side either — bare company name
                company_name = left_side
                # Fall through to remaining parsing logic

    # Try HTGC format: "Debt Investments [Industry] and [Company], Senior Secured, ..."
    # Look for ", Senior Secured" anywhere in the string
    htgc_match = re.search(r',\s*(Senior Secured)\s*,', identifier, re.IGNORECASE)
    if htgc_match:
        investment_type = "Senior Secured"
        # Extract company name - look for " and " before "Senior Secured"
        and_match = re.search(r'\s+and\s+(.+?)(?:,\s*Senior Secured)', identifier, re.IGNORECASE)
        if and_match:
            company_name = and_match.group(1).strip()
        return identifier, company_name, investment_type

    # Check for patterns like "Total [Company]" which are rollups
    if identifier.startswith('Total ') or identifier.startswith('Investments ') or \
       identifier.startswith('Investment Fund ') or identifier.startswith('Debt Investments (') or \
       identifier.startswith('Equity Investments ('):
        return identifier, identifier, "Unknown"

    # If we reach here with no match, this is a bare company name (e.g. HTGC's "Armis, Inc.")
    # or an unrecognized format — not a rollup. Mark as "Unclassified" so it can be
    # distinguished from rollup "Unknown" entries and retained in the portfolio.
    if investment_type == "Unknown":
        investment_type = "Unclassified"

    return identifier, company_name, investment_type


@dataclass(frozen=True)
class DataQuality:
    """
    Data quality metrics for a PortfolioInvestments collection.

    Provides coverage percentages for each field to help users understand
    data completeness and reliability.
    """
    total_investments: int
    fair_value_coverage: float  # Percentage with fair value
    cost_coverage: float  # Percentage with cost
    principal_coverage: float  # Percentage with principal (debt only)
    interest_rate_coverage: float  # Percentage with interest rate (debt only)
    pik_rate_coverage: float  # Percentage with PIK rate
    spread_coverage: float  # Percentage with spread
    debt_count: int  # Number of debt investments
    equity_count: int  # Number of equity investments

    def __rich__(self):
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Total Investments", str(self.total_investments))
        table.add_row("Debt", str(self.debt_count))
        table.add_row("Equity", str(self.equity_count))
        table.add_row("", "")
        table.add_row("Fair Value Coverage", f"{self.fair_value_coverage:.0%}")
        table.add_row("Cost Coverage", f"{self.cost_coverage:.0%}")
        table.add_row("Principal Coverage", f"{self.principal_coverage:.0%}")
        table.add_row("Interest Rate Coverage", f"{self.interest_rate_coverage:.0%}")
        table.add_row("PIK Rate Coverage", f"{self.pik_rate_coverage:.0%}")
        table.add_row("Spread Coverage", f"{self.spread_coverage:.0%}")

        return Panel(
            table,
            title="Data Quality",
            border_style="green" if self.fair_value_coverage > 0.9 else "yellow",
            width=40
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


@dataclass(frozen=True)
class PortfolioInvestment:
    """
    A single investment holding from a BDC's Schedule of Investments.

    Represents an individual investment in a portfolio company, including
    debt instruments (loans) and equity positions.
    """
    identifier: str  # Full investment identifier
    company_name: str  # Parsed company name
    investment_type: str  # Type of investment (loan, equity, etc.)
    fair_value: Optional[Decimal] = None
    cost: Optional[Decimal] = None
    principal_amount: Optional[Decimal] = None
    shares: Optional[int] = None
    interest_rate: Optional[float] = None
    pik_rate: Optional[float] = None  # Paid-in-kind interest rate
    spread: Optional[float] = None
    percent_of_net_assets: Optional[float] = None

    @property
    def unrealized_gain_loss(self) -> Optional[Decimal]:
        """Calculate unrealized gain/loss (fair value - cost)."""
        if self.fair_value is not None and self.cost is not None:
            return self.fair_value - self.cost
        return None

    @property
    def is_debt(self) -> bool:
        """Check if this is a debt investment.

        Uses a two-tier approach: first checks the investment type label for
        debt keywords, then falls back to XBRL data signals (principal amount
        or interest rate implies debt).
        """
        type_lower = self.investment_type.lower()
        debt_keywords = ['loan', 'debt', 'mezzanine', 'note', 'one stop',
                         'revolver', 'revolving', 'senior secured', 'lien']
        if any(kw in type_lower for kw in debt_keywords):
            return True
        # Data-driven fallback: if we have principal or interest rate, it's debt
        if self.principal_amount is not None or self.interest_rate is not None:
            return True
        return False

    @property
    def is_equity(self) -> bool:
        """Check if this is an equity investment.

        Uses a two-tier approach: first checks the investment type label for
        equity keywords, then falls back to XBRL data signals (shares count
        without principal implies equity).
        """
        type_lower = self.investment_type.lower()
        equity_keywords = ['equity', 'stock', 'shares', 'warrant', 'units',
                           'membership', 'interest', 'certificate', 'lp ']
        if any(kw in type_lower for kw in equity_keywords):
            return True
        # Data-driven fallback: shares without principal or interest rate
        if self.shares is not None and self.principal_amount is None and self.interest_rate is None:
            return True
        return False

    def __rich__(self):
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
        table.add_column("Field", style="dim")
        table.add_column("Value")

        table.add_row("Type", self.investment_type)

        if self.fair_value is not None:
            table.add_row("Fair Value", f"${self.fair_value:,.0f}")
        if self.cost is not None:
            table.add_row("Cost", f"${self.cost:,.0f}")
        if self.unrealized_gain_loss is not None:
            gain_loss = self.unrealized_gain_loss
            style = "green" if gain_loss >= 0 else "red"
            table.add_row("Unrealized G/L", f"[{style}]${gain_loss:,.0f}[/{style}]")
        if self.principal_amount is not None:
            table.add_row("Principal", f"${self.principal_amount:,.0f}")
        if self.shares is not None:
            table.add_row("Shares", f"{self.shares:,}")
        if self.interest_rate is not None:
            table.add_row("Interest Rate", f"{self.interest_rate:.2%}")
        if self.pik_rate is not None:
            table.add_row("PIK Rate", f"{self.pik_rate:.2%}")
        if self.spread is not None:
            table.add_row("Spread", f"{self.spread:.2%}")
        if self.percent_of_net_assets is not None:
            table.add_row("% of Net Assets", f"{self.percent_of_net_assets:.2%}")

        return Panel(
            table,
            title=self.company_name,
            subtitle=self.investment_type,
            border_style="blue",
            width=80
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class PortfolioInvestments:
    """
    A collection of portfolio investments from a BDC's Schedule of Investments.

    Provides filtering, aggregation, and display capabilities for BDC holdings.

    Attributes:
        period: The date of the data (e.g., '2024-12-31')
        data_quality: Coverage metrics for data completeness
    """

    def __init__(
        self,
        investments: list[PortfolioInvestment],
        period: Optional[str] = None,
        nonaccrual_fair_value: Optional[Decimal] = None,
    ):
        self._investments = investments
        self._period = period
        self._nonaccrual_fair_value = nonaccrual_fair_value

    def __len__(self) -> int:
        return len(self._investments)

    def __getitem__(self, item) -> PortfolioInvestment:
        return self._investments[item]

    def __iter__(self):
        return iter(self._investments)

    @property
    def period(self) -> Optional[str]:
        """The period date for this data (e.g., '2024-12-31')."""
        return self._period

    @property
    def data_quality(self) -> DataQuality:
        """Data quality metrics showing coverage for each field."""
        total = len(self._investments)
        if total == 0:
            return DataQuality(
                total_investments=0,
                fair_value_coverage=0.0,
                cost_coverage=0.0,
                principal_coverage=0.0,
                interest_rate_coverage=0.0,
                pik_rate_coverage=0.0,
                spread_coverage=0.0,
                debt_count=0,
                equity_count=0,
            )

        debt_investments = [i for i in self._investments if i.is_debt]
        debt_count = len(debt_investments)
        equity_count = sum(1 for i in self._investments if i.is_equity)

        return DataQuality(
            total_investments=total,
            fair_value_coverage=sum(1 for i in self._investments if i.fair_value is not None) / total,
            cost_coverage=sum(1 for i in self._investments if i.cost is not None) / total,
            principal_coverage=(
                sum(1 for i in debt_investments if i.principal_amount is not None) / debt_count
                if debt_count > 0 else 0.0
            ),
            interest_rate_coverage=(
                sum(1 for i in debt_investments if i.interest_rate is not None) / debt_count
                if debt_count > 0 else 0.0
            ),
            pik_rate_coverage=(
                sum(1 for i in debt_investments if i.pik_rate is not None) / debt_count
                if debt_count > 0 else 0.0
            ),
            spread_coverage=(
                sum(1 for i in debt_investments if i.spread is not None) / debt_count
                if debt_count > 0 else 0.0
            ),
            debt_count=debt_count,
            equity_count=equity_count,
        )

    @property
    def total_fair_value(self) -> Decimal:
        """Total fair value of all investments."""
        return sum(
            (inv.fair_value for inv in self._investments if inv.fair_value is not None),
            Decimal(0)
        )

    @property
    def total_cost(self) -> Decimal:
        """Total cost basis of all investments."""
        return sum(
            (inv.cost for inv in self._investments if inv.cost is not None),
            Decimal(0)
        )

    @property
    def total_unrealized_gain_loss(self) -> Decimal:
        """Total unrealized gain/loss across all investments."""
        return self.total_fair_value - self.total_cost

    # --- Health metrics ---

    @property
    def nonaccrual_fair_value(self) -> Optional[Decimal]:
        """Fair value of loans on non-accrual status (entity-level aggregate from XBRL).

        Returns None if the BDC does not tag this concept in its filing.
        """
        return self._nonaccrual_fair_value

    @property
    def non_accrual_rate(self) -> Optional[float]:
        """Non-accrual rate: fair value of non-accrual loans / total fair value.

        Returns None if non-accrual data is not available in the filing.
        The BDC sector average is ~0.7%. Rates above 1.5% warrant investigation;
        above 3% is a serious credit quality signal.
        """
        if self._nonaccrual_fair_value is None:
            return None
        total_fv = self.total_fair_value
        if not total_fv:
            return 0.0
        return float(self._nonaccrual_fair_value / total_fv)

    @property
    def pik_investments(self) -> list[PortfolioInvestment]:
        """Investments with Payment-In-Kind interest."""
        return [inv for inv in self._investments if inv.pik_rate]

    @property
    def pik_fair_value(self) -> Decimal:
        """Total fair value of PIK investments."""
        return sum(
            (inv.fair_value for inv in self._investments
             if inv.pik_rate and inv.fair_value is not None),
            Decimal(0)
        )

    @property
    def pik_exposure(self) -> float:
        """PIK exposure: fair value of PIK investments / total fair value.

        Returns 0.0 if no investments or no fair value data.
        """
        total_fv = self.total_fair_value
        if not total_fv:
            return 0.0
        return float(self.pik_fair_value / total_fv)

    def filter(
        self,
        investment_type: Optional[str] = None,
        company_name: Optional[str] = None,
        min_fair_value: Optional[Decimal] = None,
    ) -> 'PortfolioInvestments':
        """
        Filter investments by criteria.

        Args:
            investment_type: Filter by investment type (partial match, case-insensitive)
            company_name: Filter by company name (partial match, case-insensitive)
            min_fair_value: Minimum fair value threshold

        Returns:
            New PortfolioInvestments with matching investments
        """
        investments = self._investments

        if investment_type:
            investments = [
                inv for inv in investments
                if investment_type.lower() in inv.investment_type.lower()
            ]

        if company_name:
            investments = [
                inv for inv in investments
                if company_name.lower() in inv.company_name.lower()
            ]

        if min_fair_value is not None:
            investments = [
                inv for inv in investments
                if inv.fair_value is not None and inv.fair_value >= min_fair_value
            ]

        return PortfolioInvestments(investments, period=self._period,
                                    nonaccrual_fair_value=self._nonaccrual_fair_value)

    def to_context(self, detail: str = 'standard') -> str:
        """
        AI-optimized context string for LLM consumption.

        Args:
            detail: 'minimal' (~100 tokens), 'standard' (~350 tokens),
                    'full' (~600+ tokens with top holdings)
        """
        lines: list = []
        lines.append('BDC PORTFOLIO INVESTMENTS')
        lines.append('')

        if self._period:
            lines.append(f'Period: {self._period}')
        lines.append(f'Holdings: {len(self._investments)}')
        lines.append(f'Total Fair Value: ${self.total_fair_value:,.0f}')
        lines.append(f'Total Cost: ${self.total_cost:,.0f}')

        gain_loss = self.total_unrealized_gain_loss
        lines.append(f'Unrealized Gain/Loss: ${gain_loss:,.0f}')

        dq = self.data_quality
        lines.append(f'Composition: {dq.debt_count} debt, {dq.equity_count} equity')

        # Health metrics
        if self._nonaccrual_fair_value is not None:
            rate = self.non_accrual_rate
            lines.append(f'Non-Accrual: ${self._nonaccrual_fair_value:,.0f} ({rate:.1%})')

        pik = self.pik_investments
        if pik:
            lines.append(f'PIK: {len(pik)} investments (${self.pik_fair_value:,.0f}, {self.pik_exposure:.1%})')

        if detail == 'minimal':
            return '\n'.join(lines)

        # Data quality
        lines.append('')
        lines.append('DATA QUALITY:')
        lines.append(f'  Fair Value Coverage: {dq.fair_value_coverage:.0%}')
        lines.append(f'  Cost Coverage: {dq.cost_coverage:.0%}')
        if dq.debt_count > 0:
            lines.append(f'  Principal Coverage (debt): {dq.principal_coverage:.0%}')
            lines.append(f'  Interest Rate Coverage (debt): {dq.interest_rate_coverage:.0%}')

        # Top holdings
        lines.append('')
        limit = 10 if detail == 'standard' else 20
        lines.append(f'TOP {min(limit, len(self._investments))} HOLDINGS BY FAIR VALUE:')
        for inv in self._investments[:limit]:
            fv = f'${inv.fair_value:,.0f}' if inv.fair_value is not None else 'N/A'
            lines.append(f'  {inv.company_name} ({inv.investment_type}) — {fv}')

        if detail == 'standard':
            lines.append('')
            lines.append('AVAILABLE ACTIONS:')
            lines.append('  .filter(investment_type=, company_name=)   Filter investments')
            lines.append('  .to_dataframe()      All holdings as DataFrame')
            lines.append('  .data_quality        Coverage metrics')
            lines.append('  .non_accrual_rate    Non-accrual rate at FV')
            lines.append('  .pik_exposure        PIK as % of portfolio')
            return '\n'.join(lines)

        # Full: investment type breakdown
        from collections import Counter
        type_counts = Counter(inv.investment_type for inv in self._investments)
        lines.append('')
        lines.append('INVESTMENT TYPE BREAKDOWN:')
        for t, c in type_counts.most_common(15):
            lines.append(f'  {t}: {c}')

        lines.append('')
        lines.append('AVAILABLE ACTIONS:')
        lines.append('  .filter(investment_type=, company_name=)   Filter investments')
        lines.append('  .to_dataframe()      All holdings as DataFrame')
        lines.append('  .data_quality        Coverage metrics')
        lines.append('  .non_accrual_rate    Non-accrual rate at FV')
        lines.append('  .pik_exposure        PIK as % of portfolio')
        return '\n'.join(lines)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame."""
        return pd.DataFrame([
            {
                'company_name': inv.company_name,
                'investment_type': inv.investment_type,
                'fair_value': float(inv.fair_value) if inv.fair_value else None,
                'cost': float(inv.cost) if inv.cost else None,
                'principal_amount': float(inv.principal_amount) if inv.principal_amount else None,
                'shares': inv.shares,
                'interest_rate': inv.interest_rate,
                'pik_rate': inv.pik_rate,
                'spread': inv.spread,
                'percent_of_net_assets': inv.percent_of_net_assets,
            }
            for inv in self._investments
        ])

    def __rich__(self):
        table = Table(
            title="Portfolio Investments",
            box=box.SIMPLE,
            show_header=True,
            header_style="bold",
            row_styles=["", "dim"],
        )
        table.add_column("#", justify="right", style="dim")
        table.add_column("Company", style="bold", max_width=80, overflow="fold")
        table.add_column("Type", max_width=30)
        table.add_column("Fair Value", justify="right")
        table.add_column("Cost", justify="right")
        table.add_column("Rate", justify="right")

        # Show first 30 investments
        for idx, inv in enumerate(self._investments[:30]):
            fair_value = f"${inv.fair_value:,.0f}" if inv.fair_value else ""
            cost = f"${inv.cost:,.0f}" if inv.cost else ""
            rate = f"{inv.interest_rate:.2%}" if inv.interest_rate else ""

            table.add_row(
                str(idx),
                inv.company_name,
                inv.investment_type[:30],
                fair_value,
                cost,
                rate,
            )

        if len(self._investments) > 30:
            table.add_row("...", "...", "...", "...", "...", "...")

        # Summary
        summary = Table(box=box.SIMPLE, show_header=False)
        summary.add_column("Metric", style="dim")
        summary.add_column("Value", style="bold")
        summary.add_row("Total Investments", str(len(self._investments)))
        summary.add_row("Total Fair Value", f"${self.total_fair_value:,.0f}")
        summary.add_row("Total Cost", f"${self.total_cost:,.0f}")

        gain_loss = self.total_unrealized_gain_loss
        style = "green" if gain_loss >= 0 else "red"
        summary.add_row("Unrealized G/L", f"[{style}]${gain_loss:,.0f}[/{style}]")

        # Health metrics
        if self._nonaccrual_fair_value is not None:
            rate = self.non_accrual_rate
            rate_style = "green" if rate < 0.015 else ("yellow" if rate < 0.03 else "red")
            summary.add_row(
                "Non-Accrual",
                f"[{rate_style}]${self._nonaccrual_fair_value:,.0f} ({rate:.1%})[/{rate_style}]"
            )

        pik_invs = self.pik_investments
        if pik_invs:
            pik_fv = self.pik_fair_value
            pik_exp = self.pik_exposure
            summary.add_row(
                "PIK",
                f"{len(pik_invs)} investments (${pik_fv:,.0f}, {pik_exp:.1%})"
            )

        from rich.console import Group
        return Panel(
            Group(table, summary),
            title="BDC Portfolio Investments",
            border_style="blue",
            expand=False,
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    @classmethod
    def from_statement(
        cls,
        statement,
        period: Optional[str] = None,
        include_untyped: bool = False
    ) -> 'PortfolioInvestments':
        """
        Create PortfolioInvestments from an XBRL Schedule of Investments Statement.

        Args:
            statement: The Statement from xbrl.statements.schedule_of_investments()
            period: Optional period column (e.g., '2024-12-31'). If None, uses latest.
            include_untyped: If False (default), excludes investments with "Unknown" type.
                These are typically company-level rollup entries that would inflate totals.

        Returns:
            PortfolioInvestments collection
        """
        df = statement.to_dataframe()

        # Find the period column to use
        if period is None:
            # Find date columns (exclude metadata columns)
            date_cols = [
                col for col in df.columns
                if re.match(r'\d{4}-\d{2}-\d{2}', str(col))
            ]
            if not date_cols:
                return cls([], period=None)
            # Use the latest (first) date column
            period = date_cols[0]

        # Filter to rows with values and dimension labels
        mask = (
            df[period].notna() &
            df['dimension_label'].notna() &
            df['dimension_label'].str.contains('InvestmentIdentifierAxis', na=False)
        )
        data = df[mask].copy()

        if data.empty:
            return cls([], period=period)

        # Group by dimension_label and pivot concepts
        investments = {}
        for _, row in data.iterrows():
            dim_label = row['dimension_label']
            concept = row['concept']
            value = row[period]

            if dim_label not in investments:
                identifier, company_name, inv_type = _parse_investment_identifier(dim_label)
                investments[dim_label] = {
                    'identifier': identifier,
                    'company_name': company_name,
                    'investment_type': inv_type,
                }

            # Map concept to field
            inv = investments[dim_label]

            # Skip empty or invalid values
            if pd.isna(value) or value == '':
                continue

            try:
                if concept == CONCEPT_FAIR_VALUE:
                    inv['fair_value'] = Decimal(str(value))
                elif concept == CONCEPT_COST:
                    inv['cost'] = Decimal(str(value))
                elif concept == CONCEPT_PRINCIPAL:
                    inv['principal_amount'] = Decimal(str(value))
                elif concept == CONCEPT_SHARES:
                    inv['shares'] = int(float(value))
                elif concept == CONCEPT_INTEREST_RATE:
                    inv['interest_rate'] = float(value)
                elif concept == CONCEPT_PIK_RATE:
                    inv['pik_rate'] = float(value)
                elif concept == CONCEPT_SPREAD:
                    inv['spread'] = float(value)
                elif concept == CONCEPT_PCT_NET_ASSETS:
                    inv['percent_of_net_assets'] = float(value)
            except (ValueError, TypeError, InvalidOperation):
                # Skip values that can't be converted
                pass

        # Create PortfolioInvestment objects
        portfolio = [
            PortfolioInvestment(**inv_data)
            for inv_data in investments.values()
        ]

        # Filter out Unknown types unless include_untyped is True
        # Unknown types are typically company-level rollups that inflate totals
        if not include_untyped:
            portfolio = [inv for inv in portfolio if inv.investment_type != "Unknown"]

        # Sort by fair value (largest first)
        portfolio.sort(
            key=lambda x: x.fair_value if x.fair_value is not None else Decimal(0),
            reverse=True
        )

        return cls(portfolio, period=period)

    @classmethod
    def from_xbrl(
        cls,
        xbrl,
        period: Optional[str] = None,
        include_untyped: bool = False
    ) -> 'PortfolioInvestments':
        """
        Create PortfolioInvestments directly from XBRL facts.

        This method extracts investment data directly from XBRL facts using the
        dimension columns (dim_*), which works for BDCs that have dimensional
        investment data in facts but not in the Statement presentation hierarchy.

        Args:
            xbrl: The XBRL object from filing.xbrl()
            period: Optional period (e.g., '2024-12-31'). If None, uses latest instant.
            include_untyped: If False (default), excludes investments with "Unknown" type.

        Returns:
            PortfolioInvestments collection
        """
        all_facts = xbrl.facts.get_facts()

        # Determine the period to use
        if period is None:
            # Find the latest instant period with fair value data
            fv_facts = [
                f for f in all_facts
                if f.get('concept') == 'us-gaap:InvestmentOwnedAtFairValue'
                and f.get('period_type') == 'instant'
            ]
            if not fv_facts:
                return cls([], period=None)

            # Get unique periods and use the latest
            periods = set(f.get('period_instant') for f in fv_facts if f.get('period_instant'))
            if not periods:
                return cls([], period=None)
            period = max(periods)

        # The dimension key for investment identifier
        dim_key = 'dim_us-gaap_InvestmentIdentifierAxis'

        # Filter facts to the target period with investment dimension
        period_key = f'instant_{period}'

        # Collect all relevant concepts for the period
        relevant_concepts = {
            'us-gaap:InvestmentOwnedAtFairValue': 'fair_value',
            'us-gaap:InvestmentOwnedAtCost': 'cost',
            'us-gaap:InvestmentOwnedBalancePrincipalAmount': 'principal_amount',
            'us-gaap:InvestmentOwnedBalanceShares': 'shares',
            'us-gaap:InvestmentInterestRate': 'interest_rate',
            'us-gaap:InvestmentInterestRatePaidInKind': 'pik_rate',
            'us-gaap:InvestmentBasisSpreadVariableRate': 'spread',
            'us-gaap:InvestmentOwnedPercentOfNetAssets': 'percent_of_net_assets',
        }

        # Group facts by investment identifier
        investments = {}
        member_candidates = _get_investment_member_candidates(xbrl)
        for fact in all_facts:
            # Check if this is a relevant concept
            concept = fact.get('concept')
            if concept not in relevant_concepts:
                continue

            # Check for investment dimension
            inv_identifier = fact.get(dim_key)
            if not inv_identifier:
                continue

            # Check period matches
            fact_period = fact.get('period_instant')
            if fact_period != period:
                continue

            # Initialize investment if needed
            if inv_identifier not in investments:
                # Parse the identifier to get company name and type
                # Format: "us-gaap:InvestmentIdentifierAxis: Company Name, Investment Type"
                # But here we just have the member value, not the axis prefix
                full_label = f"us-gaap:InvestmentIdentifierAxis: {inv_identifier}"
                identifier, company_name, inv_type = _parse_investment_identifier(
                    full_label,
                    member_candidates=member_candidates,
                )
                investments[inv_identifier] = {
                    'identifier': identifier,
                    'company_name': company_name,
                    'investment_type': inv_type,
                }

            # Map the value to the appropriate field
            field_name = relevant_concepts[concept]
            value = fact.get('numeric_value') or fact.get('value')

            if value is None or pd.isna(value):
                continue

            try:
                if field_name in ('fair_value', 'cost', 'principal_amount'):
                    investments[inv_identifier][field_name] = Decimal(str(value))
                elif field_name == 'shares':
                    investments[inv_identifier][field_name] = int(float(value))
                elif field_name in ('interest_rate', 'pik_rate', 'spread', 'percent_of_net_assets'):
                    investments[inv_identifier][field_name] = float(value)
            except (ValueError, TypeError, InvalidOperation):
                pass

        # Extract non-accrual data using footnote-based extraction
        nonaccrual_fv = None
        try:
            from edgar.bdc.nonaccrual import _extract_nonaccrual_from_xbrl
            nonaccrual_result = _extract_nonaccrual_from_xbrl(xbrl, period, all_facts=all_facts)
            if nonaccrual_result is not None:
                nonaccrual_fv = nonaccrual_result.nonaccrual_fair_value
        except Exception as e:
            # Fall back to the single-concept check if extraction fails
            log.warning(f"Non-accrual footnote extraction failed, falling back to aggregate concept: {e}")
            for fact in all_facts:
                if (fact.get('concept') == CONCEPT_NONACCRUAL_LOANS_FV
                        and fact.get('period_instant') == period
                        and not fact.get(dim_key)):
                    value = fact.get('numeric_value') or fact.get('value')
                    if value is not None and not pd.isna(value):
                        try:
                            nonaccrual_fv = Decimal(str(value))
                        except (ValueError, InvalidOperation):
                            pass
                        break

        # Create PortfolioInvestment objects
        portfolio = [
            PortfolioInvestment(**inv_data)
            for inv_data in investments.values()
        ]

        # Filter out Unknown types unless include_untyped is True
        if not include_untyped:
            portfolio = [inv for inv in portfolio if inv.investment_type != "Unknown"]

        # Sort by fair value (largest first)
        portfolio.sort(
            key=lambda x: x.fair_value if x.fair_value is not None else Decimal(0),
            reverse=True
        )

        return cls(portfolio, period=period, nonaccrual_fair_value=nonaccrual_fv)
