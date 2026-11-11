"""
Core utilities for XBRL processing.

This module provides common functions used throughout the XBRL parser.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Mapping, NamedTuple, Optional, Tuple, Union

# Constants for label roles
STANDARD_LABEL = "http://www.xbrl.org/2003/role/label"
TERSE_LABEL = "http://www.xbrl.org/2003/role/terseLabel"
PERIOD_START_LABEL = "http://www.xbrl.org/2003/role/periodStartLabel"
PERIOD_END_LABEL = "http://www.xbrl.org/2003/role/periodEndLabel"
TOTAL_LABEL = "http://www.xbrl.org/2003/role/totalLabel"


def _period_boundary_name(role: Optional[str]) -> str:
    """Local name of a label role, lower-cased, without a leading 'negated'."""
    if not role:
        return ''
    name = role.rsplit('/', 1)[-1].lower()
    return name[len('negated'):] if name.startswith('negated') else name


def is_period_start_label_role(role: Optional[str]) -> bool:
    """
    Report whether a preferred-label role marks a roll-forward's opening balance.

    True for periodStartLabel and its negated forms (the 2009 LRR's
    negatedPeriodStartLabel and the legacy xbrl.us '.../label/negatedPeriodStart'),
    matched by local name like `is_negated_label_role` (GH #1700).
    """
    return _period_boundary_name(role).startswith('periodstart')


def is_period_end_label_role(role: Optional[str]) -> bool:
    """Report whether a preferred-label role marks a roll-forward's closing balance (see above)."""
    return _period_boundary_name(role).startswith('periodend')


def is_period_boundary_label_role(role: Optional[str]) -> bool:
    """Report whether a preferred-label role is a period start or period end role, negated or not."""
    return is_period_start_label_role(role) or is_period_end_label_role(role)


def iso4217_code(measure: Optional[str]) -> Optional[str]:
    """Return the ISO 4217 code of an ``iso4217:`` unit measure, else ``None``."""
    if measure and measure.startswith('iso4217:'):
        return measure[len('iso4217:'):]
    return None


def unit_currency(unit_info: Optional[Dict[str, Any]]) -> Optional[str]:
    """Resolve a parsed XBRL unit to its ISO 4217 currency code, or ``None``.

    A currency fact uses a simple ``iso4217:`` measure (``iso4217:HKD`` -> ``HKD``).
    A per-share monetary fact uses a ``divide`` unit whose numerator is the
    currency (``iso4217:USD`` per ``xbrli:shares``), so the numerator's currency
    is the fact's currency. Non-monetary units (shares, pure) return ``None``.
    The opaque ``unit_ref`` id itself (e.g. ``UNIT_STANDARD_HKD_...``) is never
    parsed -- only the resolved measure is used (see issue #850).

    This lives here, above every consumer, because three of them need it and a
    per-unit rule spelled out in three places is how the negated-label matchers
    drifted apart (edgartools-hxnw). Until edgartools-uetp, divided units were
    misparsed as simple, so the ``divide`` branch never ran on a real filing.
    """
    if not unit_info:
        return None
    unit_type = unit_info.get('type')
    if unit_type == 'simple':
        return iso4217_code(unit_info.get('measure'))
    if unit_type == 'divide':
        for measure in unit_info.get('numerator', []):
            code = iso4217_code(measure)
            if code:
                return code
    return None


def unit_currency_measure(unit_info: Optional[Dict[str, Any]]) -> Optional[str]:
    """The full ``iso4217:``-prefixed measure a unit denominates its value in.

    Same rule as :func:`unit_currency` but keeping the prefix, for callers that
    hand the measure to currency-symbol lookup rather than reading the code.
    """
    if not unit_info:
        return None
    unit_type = unit_info.get('type')
    if unit_type == 'simple':
        measure = unit_info.get('measure')
        return measure if iso4217_code(measure) else None
    if unit_type == 'divide':
        for measure in unit_info.get('numerator', []):
            if iso4217_code(measure):
                return measure
    return None

# Standard XBRL taxonomy prefixes. Anything else in an element_id is a filer extension.
# Used by calculation_linkbase() and Statement.extension_arcs() to distinguish
# filer-authored concepts from standard taxonomy concepts.
STANDARD_TAXONOMIES = frozenset({
    'us-gaap', 'dei', 'srt', 'ifrs', 'ifrs-full',
    'country', 'currency', 'exch', 'ecd',
    'naics', 'sic', 'stpr', 'invest',
})


def split_element_id(element_id: str) -> Tuple[str, str]:
    """Split an element ID like 'us-gaap_Revenues' or 'tsla_RestructuringAndOtherExpenses'
    into (taxonomy_prefix, local_name) on the FIRST underscore.

    Handles 'us-gaap' correctly (contains a hyphen, not an underscore separator).
    Returns ('', element_id) if there is no underscore.
    """
    if not element_id or '_' not in element_id:
        return '', element_id or ''
    prefix, _, local = element_id.partition('_')
    return prefix, local

# XML namespaces
NAMESPACES = {
    "xlink": "http://www.w3.org/1999/xlink",
    "xsd": "http://www.w3.org/2001/XMLSchema",
    "xbrli": "http://www.xbrl.org/2003/instance",
    "link": "http://www.xbrl.org/2003/linkbase"
}


def parse_date(date_str: str) -> datetime.date:
    """
    Parse an XBRL date string to a date object.

    Args:
        date_str: Date string in YYYY-MM-DD format

    Returns:
        datetime.date object
    """
    if not date_str:
        raise ValueError("Empty date string provided")

    try:
        # Parse the date string
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        # Additional validation - some dates in XBRL can have invalid day values
        # (e.g. September 31, which doesn't exist)
        year, month, day = map(int, date_str.split('-'))

        # Validate day of month
        if month == 2:  # February
            if day > 29:
                # February never has more than 29 days
                raise ValueError(f"Invalid day {day} for February")
            elif day == 29 and not (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
                # February 29 is only valid in leap years
                raise ValueError(f"Invalid day 29 for February in non-leap year {year}")
        elif month in [4, 6, 9, 11] and day > 30:
            # April, June, September, November have 30 days max
            raise ValueError(f"Invalid day {day} for month {month}")
        elif day > 31:
            # No month has more than 31 days
            raise ValueError(f"Invalid day {day}")

        return date_obj
    except (ValueError, TypeError) as e:
        # Provide more specific error message
        raise ValueError(f"Invalid date format or value: {date_str} - {str(e)}") from e


def format_date(date_obj: datetime.date) -> str:
    """
    Format a date object to a human-readable string.

    Args:
        date_obj: datetime.date object

    Returns:
        Formatted date string (e.g., "Sep 30, 2023")
    """
    # Use abbreviated month format (%b) instead of full month (%B)
    formatted_date = date_obj.strftime('%b %d, %Y')

    # Remove leading zeros from day
    if formatted_date.split()[1].startswith('0'):
        day_part = formatted_date.split()[1].lstrip('0')
        formatted_date = f"{formatted_date.split()[0]} {day_part} {formatted_date.split()[2]}"

    return formatted_date


def extract_element_id(href: str) -> str:
    """
    Extract element ID from an XLink href.

    Args:
        href: XLink href attribute value

    Returns:
        Element ID
    """
    return href.split('#')[-1]


def duration_days(start: date, end: date) -> int:
    """Days a date-only XBRL duration covers, counting both endpoints.

    XBRL 2.1 reads a date-only ``endDate`` as the end of that day, so the
    context runs to 24:00 on it and the final day belongs to the period.
    Subtracting the two dates counts one day short: a calendar year of
    2023-01-01 to 2023-12-31 measures 364, and Apple's 53-week FY2023
    (2022-09-25 to 2023-09-30) measures 370 instead of 371 (issue #1247).

    Args:
        start: Context startDate.
        end: Context endDate.

    Returns:
        Days covered, inclusive of both endpoints.
    """
    return (end - start).days + 1


def classify_duration(days: int) -> str:
    """
    Classify a duration in days as quarterly, semi-annual, annual, etc.

    Args:
        days: Duration in days

    Returns:
        Description of the duration (e.g., "Quarterly", "Annual")
    """
    if 85 <= days <= 95:
        return "Quarterly"
    elif 175 <= days <= 185:
        return "Semi-Annual"
    elif 265 <= days <= 285:
        return "Nine Months"
    elif 350 <= days <= 380:
        return "Annual"
    else:
        return "Period"


def determine_dominant_scale(statement_data: List[Dict[str, Any]],
                             periods_to_display: List[Tuple[str, str]]) -> int:
    """
    Determine the dominant scale (thousands, millions, billions) for a statement.

    This looks at all monetary values in the statement and determines the most appropriate
    scale to use for the "In millions/billions/thousands" note.

    Args:
        statement_data: The statement data with items and values
        periods_to_display: List of period keys and labels to consider

    Returns:
        int: The dominant scale (-3 for thousands, -6 for millions, -9 for billions, 0 for no scaling)
    """
    # Collect all decimals attributes
    all_decimals = []
    for item in statement_data:
        # Skip non-monetary items or items without values
        if not item.get('has_values', False) or not item.get('values'):
            continue

        # Skip items that appear to be share counts or ratios
        label_lower = item['label'].lower()
        if any(keyword in label_lower for keyword in [
            'shares', 'share', 'stock', 'eps', 'earnings per share',
            'weighted average', 'number of', 'per common share', 'per share',
            'per basic', 'per diluted', 'outstanding', 'issued',
            'ratio', 'margin', 'percentage', 'rate', 'per cent'
        ]):
            continue

        # Get all decimals values for this item. A filed 'INF' says the value
        # is exact, which implies no scale -- the same 0 this collected before
        # statements began keeping the sentinel (GH #1229).
        for period_key, _ in periods_to_display:
            if period_key in item.get('decimals', {}):
                all_decimals.append(decimals_for_scaling(item['decimals'][period_key]))

    # If we have decimals information, use that to determine the scale
    if all_decimals:
        # Count the occurrences of each scale
        scale_counts = {
            -9: 0,  # billions
            -6: 0,  # millions
            -3: 0,  # thousands
            0: 0    # no scaling
        }

        for decimals in all_decimals:
            if decimals <= -9:
                scale_counts[-9] += 1
            elif decimals <= -6:
                scale_counts[-6] += 1
            elif decimals <= -3:
                scale_counts[-3] += 1
            else:
                scale_counts[0] += 1

        # Find the most common scale (excluding no scaling)
        most_common_scale = 0
        max_count = 0

        for scale, count in scale_counts.items():
            if scale != 0 and count > max_count:  # Prioritize scaling over no scaling
                max_count = count
                most_common_scale = scale

        return most_common_scale

    # If no decimals information, examine the magnitude of values
    all_values = []
    for item in statement_data:
        if not item.get('has_values', False) or not item.get('values'):
            continue

        # Skip items that appear to be share counts or ratios
        label_lower = item['label'].lower()
        if any(keyword in label_lower for keyword in [
            'shares', 'share', 'stock', 'eps', 'earnings per share',
            'weighted average', 'number of', 'per common share', 'per share',
            'per basic', 'per diluted', 'outstanding', 'issued',
            'ratio', 'margin', 'percentage', 'rate', 'per cent'
        ]):
            continue

        # Get all values for this item
        for period_key, _ in periods_to_display:
            value = item['values'].get(period_key)
            if isinstance(value, (int, float)) and value != 0:
                all_values.append(abs(value))

    # Determine the appropriate scale based on the magnitude of values
    if all_values:
        # Calculate median value to avoid outliers affecting the scale
        all_values.sort()
        median_value = all_values[len(all_values) // 2]

        if median_value >= 1_000_000_000:
            return -9  # billions
        elif median_value >= 1_000_000:
            return -6  # millions
        elif median_value >= 1_000:
            return -3  # thousands

    # Default to millions if we couldn't determine a scale
    return -6


# Common ISO 4217 currency measures and the symbol a statement displays for them.
CURRENCY_SYMBOLS = {
    'iso4217:USD': '$',
    'iso4217:EUR': '€',
    'iso4217:GBP': '£',
    'iso4217:JPY': '¥',
    'iso4217:CAD': 'C$',
    'iso4217:AUD': 'A$',
    'iso4217:CHF': 'CHF',
    'iso4217:CNY': '¥',
    'iso4217:INR': '₹',
    'iso4217:KRW': '₩',
    'iso4217:BRL': 'R$',
    'iso4217:MXN': 'MX$',
    'iso4217:SEK': 'kr',
    'iso4217:NOK': 'kr',
    'iso4217:DKK': 'kr',
    'iso4217:PLN': 'zł',
    'iso4217:CZK': 'Kč',
    'iso4217:HUF': 'Ft',
    'iso4217:RUB': '₽',
    'iso4217:ZAR': 'R',
    'iso4217:SGD': 'S$',
    'iso4217:HKD': 'HK$',
    'iso4217:TWD': 'NT$',
    'iso4217:THB': '฿',
    'iso4217:MYR': 'RM',
    'iso4217:IDR': 'Rp',
    'iso4217:PHP': '₱',
    'iso4217:VND': '₫',
    'iso4217:ILS': '₪',
    'iso4217:TRY': '₺',
    'iso4217:AED': 'AED',
    'iso4217:SAR': 'SR',
    'iso4217:EGP': 'E£',
    'iso4217:NGN': '₦',
}


def get_currency_symbol(unit_measure: Optional[str]) -> str:
    """
    Get the appropriate currency symbol from a unit measure string.

    Args:
        unit_measure: Unit measure string (e.g., 'iso4217:USD', 'iso4217:EUR')

    Returns:
        Currency symbol (e.g., '$', '€', '£')
    """
    if not unit_measure:
        return "$"  # Default to USD

    return CURRENCY_SYMBOLS.get(unit_measure, '$')  # Default to USD if unknown


def format_value(value: Union[int, float, str], is_monetary: bool, scale: int,
                 decimals: Optional[int] = None, currency_symbol: Optional[str] = None) -> str:
    """
    Format a value with appropriate scaling and formatting.

    Args:
        value: The value to format
        is_monetary: Whether the value is monetary
        scale: The scale to apply (-3 for thousands, -6 for millions, -9 for billions)
        decimals: XBRL decimals attribute value (optional)
        currency_symbol: Currency symbol to use for monetary values (default: '$')

    Returns:
        Formatted value string
    """
    # Non-numeric values pass through. Zero is formatted like any other number
    # ("$0", "0.00"); it used to return the control character U+0014.
    if not isinstance(value, (int, float)):
        return str(value)
    value += 0  # -0.0 + 0 is 0.0, so a negative zero cannot format as "-0"

    # Apply scaling
    scaled_value = value
    if scale <= -9:  # Billions
        scaled_value = value / 1_000_000_000
    elif scale <= -6:  # Millions
        scaled_value = value / 1_000_000
    elif scale <= -3:  # Thousands
        scaled_value = value / 1_000

    # Determine decimal places to show
    if isinstance(decimals, int):
        if decimals >= 0:
            # Positive decimals - show up to 2 decimal places
            decimal_places = min(2, decimals)
        else:
            # For negative decimals, adjust based on scaling
            if scale <= -9:  # Billions
                decimal_places = min(2, max(0, decimals + 9))
            elif scale <= -6:  # Millions
                decimal_places = min(2, max(0, decimals + 6))
            elif scale <= -3:  # Thousands
                decimal_places = min(2, max(0, decimals + 3))
            else:
                # For unscaled values, respect the decimals attribute
                # If decimals is negative, show that many zeros to the left of decimal
                # E.g., decimals=-2 means precision to hundreds place (two zeros after decimal)
                decimal_places = max(0, -decimals)
    else:
        # Default decimal places
        if is_monetary:
            decimal_places = 0  # Standard for financial statements
        else:
            # For non-monetary values, check if it's effectively a whole number
            if abs(round(value) - value) < 0.001:
                decimal_places = 0  # Effectively whole numbers
            else:
                decimal_places = 2  # Show 2 decimals for actual fractional values

    # Apply formatting
    decimal_format = f",.{decimal_places}f"

    # Format with currency symbol if monetary, otherwise just format the number
    if is_monetary:
        # Use the provided currency symbol or default to '$'
        symbol = currency_symbol if currency_symbol is not None else '$'
        if value < 0:
            return f"{symbol}({abs(scaled_value):{decimal_format}})"
        else:
            return f"{symbol}{scaled_value:{decimal_format}}"
    else:
        # For non-monetary values, use parentheses for negative numbers
        if value < 0:
            return f"({abs(scaled_value):{decimal_format}})"
        else:
            return f"{scaled_value:{decimal_format}}"


def find_previous_fiscal_year_period(instant_periods: List[Dict[str, Any]],
                                    prev_fiscal_year: int,
                                    fiscal_month: int,
                                    fiscal_day: int) -> Optional[Dict[str, Any]]:
    """
    Find the previous fiscal year period using simple matching logic.

    Args:
        instant_periods: List of instant periods sorted by date (most recent first)
        prev_fiscal_year: Previous fiscal year to find
        fiscal_month: Fiscal year end month
        fiscal_day: Fiscal year end day

    Returns:
        Previous fiscal year period or None if not found
    """
    for period in instant_periods[1:]:  # Skip the current one
        try:
            period_date = parse_date(period['date'])
            # Check if this period is from the previous fiscal year and around fiscal year end
            if (period_date.year == prev_fiscal_year and
                period_date.month == fiscal_month and
                abs(period_date.day - fiscal_day) <= 7):
                return period
        except (ValueError, TypeError):
            continue
    return None


XBRLI_NAMESPACE = 'http://www.xbrl.org/2003/instance'
ISO4217_NAMESPACE = 'http://www.xbrl.org/2003/iso4217'

# Row unit summaries that are not a single unit (GH #1746)
UNIT_UNAVAILABLE = 'unit unavailable'
UNIT_MIXED = 'mixed'

_OMITTED = object()


def expanded_measure_name(measure: str, nsmap: Mapping[Optional[str], str]) -> Optional[str]:
    """A measure's QName as ``{namespace}local``, resolved against in-scope namespaces.

    ``nsmap`` is the measure element's own in-scope map (lxml's ``element.nsmap``),
    so a local declaration and the default namespace both count: Microsoft files
    ``shares`` unprefixed under the default XBRL instance namespace. An
    unprefixed name with no default namespace has no namespace and is returned
    bare. A prefix with no declaration cannot be resolved and returns ``None``.
    """
    prefix, sep, local = measure.partition(':')
    if not sep:
        prefix, local = None, measure
    if not local:
        return None
    namespace = nsmap.get(prefix)
    if namespace is None:
        return None if prefix else local
    return f'{{{namespace}}}{local}'


def unit_definition(numerator: List[str], denominator: List[str],
                    lexical_numerator: List[str], lexical_denominator: List[str]) -> Dict[str, Any]:
    """The common descriptor of a parsed unit (GH #1747, #1746).

    ``numerator`` and ``denominator`` are expanded QNames in source order with
    repeats kept; a simple or product unit has an empty denominator. They, not
    the opaque unit id or the measures' prefixes, are what a unit means.
    ``expression`` is the filed lexical form, for display only.
    """
    expression = '*'.join(lexical_numerator)
    if lexical_denominator:
        denominator_text = '*'.join(lexical_denominator)
        if len(lexical_denominator) > 1:
            denominator_text = f'({denominator_text})'
        expression = f'{expression}/{denominator_text}'
    return {'numerator': list(numerator), 'denominator': list(denominator), 'expression': expression}


class UnitClass(NamedTuple):
    """What a unit definition measures, and how a statement labels it.

    ``kind`` is one of ``currency``, ``shares``, ``pure``,
    ``currency_per_share`` or ``other``; ``currency`` is the ISO 4217 code for
    the two monetary kinds and ``None`` otherwise.
    """
    kind: str
    label: str
    currency: Optional[str] = None


def _split_expanded(name: str) -> Tuple[str, str]:
    """``{namespace}local`` -> (namespace, local); a bare name has no namespace."""
    if name.startswith('{') and '}' in name:
        namespace, local = name[1:].split('}', 1)
        return namespace, local
    return '', name


def _descriptor(definition: Any) -> Optional[Dict[str, Any]]:
    """Accept a parsed unit (carrying ``definition``) or the descriptor itself."""
    if not isinstance(definition, dict):
        return None
    if 'definition' in definition:
        definition = definition['definition']
        if not isinstance(definition, dict):
            return None
    numerator = definition.get('numerator')
    denominator = definition.get('denominator')
    if not isinstance(numerator, list) or not isinstance(denominator, list) or not numerator:
        return None
    return definition


def _single_measure_class(namespace: str, local: str) -> Optional[UnitClass]:
    """Classify a unit of one measure, or ``None`` when it is not a standard one."""
    if namespace == ISO4217_NAMESPACE:
        return UnitClass('currency', local.lower(), local)
    if namespace == XBRLI_NAMESPACE and local == 'shares':
        return UnitClass('shares', 'shares')
    if namespace == XBRLI_NAMESPACE and local == 'pure':
        return UnitClass('pure', 'number')
    return None


def classify_unit_definition(definition: Any) -> Optional[UnitClass]:
    """Classify a unit from its definition (its measures), never from its id.

    Only complete supported shapes get a short label: one ISO 4217 currency
    (``usd``), one ``xbrli:shares`` (``shares``), one ``xbrli:pure``
    (``number``, with no percentage inferred) and exactly one currency divided
    by one ``xbrli:shares`` (``usdPerShare``). Anything else -- a custom
    measure, a product, another quotient -- is labelled with its complete filed
    expression, so USD x shares or USD / EUR never reads as cash. Measures are
    compared by namespace, so an ``iso4217`` prefix bound to another namespace
    confers no currency. Returns ``None`` when there is no usable definition.
    """
    descriptor = _descriptor(definition)
    if descriptor is None:
        return None
    numerator = [_split_expanded(name) for name in descriptor['numerator']]
    denominator = [_split_expanded(name) for name in descriptor['denominator']]
    if len(numerator) == 1 and not denominator:
        single = _single_measure_class(*numerator[0])
        if single is not None:
            return single
    if (len(numerator) == 1 and len(denominator) == 1
            and numerator[0][0] == ISO4217_NAMESPACE
            and denominator[0] == (XBRLI_NAMESPACE, 'shares')):
        code = numerator[0][1]
        return UnitClass('currency_per_share', f'{code.lower()}PerShare', code)
    expression = descriptor.get('expression') or _clark_expression(descriptor)
    return UnitClass('other', expression)


def _clark_expression(descriptor: Dict[str, Any]) -> str:
    """A complete expression from expanded names, when no lexical form was kept."""
    return unit_definition(descriptor['numerator'], descriptor['denominator'],
                           descriptor['numerator'], descriptor['denominator'])['expression']


def _unit_identity(descriptor: Dict[str, Any]) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Two units are equal when their measures are (XBRL 2.1 section 4.10), in any order."""
    return tuple(sorted(descriptor['numerator'])), tuple(sorted(descriptor['denominator']))


def summarize_unit_definitions(definitions: Iterable[Any]) -> Optional[str]:
    """One unit label for a statement row from its selected numeric cells' units.

    ``definitions`` holds one entry per selected numeric cell: a parsed unit or
    its descriptor, or ``None`` when the cell's unit could not be resolved. The
    summary is that unit's label when every cell has the same unit -- aliases
    and different unit ids of one definition are the same unit -- ``mixed``
    when they differ, and ``unit unavailable`` when any cell's unit is
    unresolved. A row with no numeric cell has no unit (``None``).
    """
    labels: Dict[Tuple[Tuple[str, ...], Tuple[str, ...]], str] = {}
    for definition in definitions:
        unit_class = classify_unit_definition(definition)
        if unit_class is None:
            return UNIT_UNAVAILABLE
        labels.setdefault(_unit_identity(_descriptor(definition)), unit_class.label)
    if not labels:
        return None
    if len(labels) > 1:
        return UNIT_MIXED
    return next(iter(labels.values()))


def get_unit_display_name(unit_ref: Optional[str], *, definition: Any = _OMITTED) -> Optional[str]:
    """
    Convert a unit to a human-readable unit name.

    With ``definition=`` (a parsed unit from ``xbrl.units``, or its
    ``definition`` descriptor), the name comes from the unit's measures and
    the id is ignored: USD / shares is ``usdPerShare`` whatever its id says. An
    explicit ``definition=None`` means the unit is known to be unresolved and
    returns ``'unit unavailable'``; it never falls back to reading the id.
    Statement DataFrames always take this path (GH #1746).

    Called with the id alone, this is a legacy lexical heuristic kept for
    compatibility: it guesses from substrings of the id and cannot establish
    what a filing's unit is (``U_UnitedStatesOfAmericaDollarsShare`` reads as
    ``shares``).

    Maps XBRL unit references to standard display names:
    - 'U-Monetary' / 'iso4217:USD' -> 'usd'
    - 'U-Shares' / 'shares' -> 'shares'
    - 'U-USD-per-shares' -> 'usdPerShare'
    - etc.

    Args:
        unit_ref: XBRL unit reference string

    Returns:
        Human-readable unit name or None if unit_ref is None

    Examples:
        >>> get_unit_display_name('U-Monetary')
        'usd'
        >>> get_unit_display_name('U-Shares')
        'shares'
        >>> get_unit_display_name('U-USD-per-shares')
        'usdPerShare'
    """
    if definition is not _OMITTED:
        unit_class = classify_unit_definition(definition)
        return unit_class.label if unit_class is not None else UNIT_UNAVAILABLE
    if not unit_ref:
        return None

    # Common unit patterns and their standard names
    unit_ref_lower = unit_ref.lower()

    # Per-share units (ratios) - Check FIRST before simple monetary/share checks
    if 'per' in unit_ref_lower and 'share' in unit_ref_lower:
        if 'usd' in unit_ref_lower or 'monetary' in unit_ref_lower:
            return 'usdPerShare'
        elif 'eur' in unit_ref_lower:
            return 'eurPerShare'
        elif 'gbp' in unit_ref_lower:
            return 'gbpPerShare'
        else:
            return 'perShare'

    # Share units (but not per-share)
    if 'share' in unit_ref_lower:
        return 'shares'

    # Monetary units
    if 'monetary' in unit_ref_lower or 'iso4217:usd' in unit_ref_lower or unit_ref_lower == 'usd':
        return 'usd'
    elif 'eur' in unit_ref_lower or 'iso4217:eur' in unit_ref_lower:
        return 'eur'
    elif 'gbp' in unit_ref_lower or 'iso4217:gbp' in unit_ref_lower:
        return 'gbp'
    elif 'jpy' in unit_ref_lower or 'iso4217:jpy' in unit_ref_lower:
        return 'jpy'

    # Pure numbers / ratios (no unit)
    if 'pure' in unit_ref_lower or 'number' in unit_ref_lower:
        return 'number'

    # Default: return a simplified version of the unit_ref
    # Remove common prefixes and normalize
    simplified = unit_ref.replace('U-', '').replace('iso4217:', '')
    return simplified.lower()


def is_point_in_time(period_type: Optional[str]) -> Optional[bool]:
    """
    Determine if a period type represents a point-in-time value.

    Args:
        period_type: XBRL period type ('instant' or 'duration')

    Returns:
        True for 'instant' periods, False for 'duration' periods, None if period_type is None

    Examples:
        >>> is_point_in_time('instant')
        True
        >>> is_point_in_time('duration')
        False
        >>> is_point_in_time(None)
        None
    """
    if period_type is None:
        return None
    return period_type == 'instant'


#: Document types that are annual reports, without the amendment suffix.
ANNUAL_REPORT_FORMS = frozenset({'10-K', '10-KT', '10-KSB', '20-F', '40-F', '11-K'})

#: Document types that are quarterly reports, without the amendment suffix.
QUARTERLY_REPORT_FORMS = frozenset({'10-Q', '10-QT', '10-QSB'})


def base_document_type(document_type: Optional[str]) -> str:
    """The document type with its amendment suffix removed: '10-K/A' -> '10-K'."""
    if not document_type:
        return ''
    return document_type.split('/')[0].strip().upper()


def is_amendment_document_type(document_type: Optional[str]) -> bool:
    """Whether a dei:DocumentType carries the amendment suffix."""
    return bool(document_type) and '/A' in document_type.upper()


def is_annual_document_type(document_type: Optional[str]) -> bool:
    """Whether a dei:DocumentType is an annual report, amended or not.

    An amended annual report is still an annual report. Comparing the whole
    string against '10-K' made Shopify's 10-K/A report amendment=True alongside
    annual_report=False, which contradicts its own dei:DocumentAnnualReport
    (GH #1226).
    """
    return base_document_type(document_type) in ANNUAL_REPORT_FORMS


def is_quarterly_document_type(document_type: Optional[str]) -> bool:
    """Whether a dei:DocumentType is a quarterly report, amended or not."""
    return base_document_type(document_type) in QUARTERLY_REPORT_FORMS
#: The XBRL ``decimals`` sentinel for a value reported exactly, to unlimited
#: precision. It is not a number and is never interchangeable with 0, which
#: says the value is rounded to the unit.
INFINITE_PRECISION = 'INF'


def normalize_decimals(decimals: Union[int, str, None]) -> Union[int, str, None]:
    """Read a fact's ``decimals`` attribute into the form a statement stores.

    Statement assembly used to collapse ``INF`` to integer 0 in five places, so
    Apple's $0.00001 par value arrived at ``get_statement()`` claiming to be
    rounded to the dollar while the same fact still read ``'INF'`` through
    ``FactQuery`` (GH #1229). The sentinel is kept; anything that scales or
    formats asks :func:`decimals_for_scaling` for a number.

    Returns None when the attribute is absent, so a caller can tell "not filed"
    from a filed value and leave its map untouched.
    """
    if decimals is None:
        return None
    if isinstance(decimals, str) and decimals.strip().upper() == INFINITE_PRECISION:
        return INFINITE_PRECISION
    try:
        return int(decimals)
    except (ValueError, TypeError):
        return 0


def decimals_from_precision(precision: Optional[str], value: Optional[str]) -> Union[int, str, None]:
    """The decimals a fact reported with ``@precision`` implies (XBRL 2.1 §4.6.6).

    ``decimals = precision - floor(log10(abs(value))) - 1``: two significant
    digits of 2,000,000 are accurate to the hundred-thousand, decimals -5. An
    ``INF`` precision, or a zero value, is INF. ``precision="0"`` says nothing
    is known about the value's accuracy (§4.6.4), so it implies nothing and
    returns None, as does an unreadable precision or value.

    ``Decimal.adjusted()`` is the exact ``floor(log10(abs(value)))`` of the
    lexical value, so no float rounding or decimal context is involved.
    """
    if precision is None:
        return None
    text = str(precision).strip()
    if text.upper() == INFINITE_PRECISION:
        return INFINITE_PRECISION
    try:
        digits = int(text)
    except ValueError:
        return None
    if digits <= 0:
        return None
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not number.is_finite():
        return None
    if number.is_zero():
        return INFINITE_PRECISION
    return digits - number.adjusted() - 1


def decimals_for_scaling(decimals: Union[int, str, None]) -> int:
    """The integer a scaling or formatting step can use.

    ``INF`` says the value is exact, so it implies no scale of its own and
    contributes 0 -- the same number the old code stored, which is why keeping
    the sentinel upstream leaves rendered statements unchanged.
    """
    if isinstance(decimals, bool) or not isinstance(decimals, int):
        return 0
    return decimals


class SourceKeyLookup:
    """A row's per-period values that remember which period key answered a lookup.

    A statement column can show a value filed under another key -- a cash
    balance's instant under a duration column -- so the unit that belongs to the
    cell is the one filed under the key the value came from (GH #1655, #1746).
    ``get`` returns exactly what ``dict.get`` would; it only records the key.
    """

    def __init__(self, values: Optional[Mapping[str, Any]]):
        self._values = values or {}
        self.source_key: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        if self._values.get(key) is not None:
            self.source_key = key
        return self._values.get(key, default)


def is_numeric_cell(value: Any) -> bool:
    """Whether a statement cell holds a number (not text, a blank, a bool or NaN)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return value == value  # NaN is the only value unequal to itself


def cell_unit_definition(item_units: Optional[Mapping[str, Any]], source_key: Optional[str],
                         units: Optional[Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    """The unit definition of the fact a cell was read from, or ``None`` if unresolved.

    ``item_units`` maps the row's period keys to unit ids, ``units`` is
    ``xbrl.units``. Only the cell's own source key is read: no neighbouring
    period or fact lends its unit.
    """
    unit_ref = (item_units or {}).get(source_key) if source_key else None
    unit = (units or {}).get(unit_ref) if isinstance(unit_ref, str) else None
    return unit.get('definition') if isinstance(unit, dict) else None


def record_cell_unit(cell_units: Dict[str, Any], column_key: str, value: Any,
                     item_units: Optional[Mapping[str, Any]], source_key: Optional[str],
                     units: Optional[Mapping[str, Any]]) -> None:
    """Record a shown cell's unit definition under its column, if the cell is a number.

    The map feeds :func:`summarize_unit_definitions`; a blank or text cell asserts no unit.
    """
    if is_numeric_cell(value):
        cell_units[column_key] = cell_unit_definition(item_units, source_key, units)


def row_metadata_value(mapping: Optional[Dict[str, Any]],
                       period_keys: Iterable[str]) -> Optional[Any]:
    """Pick a concept-level value (a unit, a period type) out of a per-period map.

    Unit and period type belong to the concept rather than to the column: an
    element's ``periodType`` is fixed by its declaration, and a statement row
    does not change unit between periods. Reading only the displayed columns
    reported nothing whenever the row's facts were filed under other period
    keys -- a cash flow statement displays duration columns while its beginning
    and ending balances are instant facts, so their maps shared no key with the
    columns at all and both ``unit`` and ``point_in_time`` came back empty for
    Apple's cash balances (GH #1228). Prefer a displayed column, then fall back
    to anything the row has.
    """
    if not mapping:
        return None
    for period_key in period_keys:
        value = mapping.get(period_key)
        if value is not None:
            return value
    return next((value for value in mapping.values() if value is not None), None)
