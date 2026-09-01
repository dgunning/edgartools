"""
Inline XBRL Transformation Registry.

An ``ix:nonNumeric`` / ``ix:nonFraction`` element carries human display text; its
``format`` attribute names the transformation that turns that text into the
fact's semantic value. Without the transformation the fact value is the display
string, which is a different thing that happens to look plausible: ``"Delaware"``
where the value is ``"DE"``, ``"ten years"`` where it is ``"P10Y"``.

This module implements the transformations of Transformation Registry 1-4 and
the SEC's ``ixt-sec`` extensions, keyed on a normalized form of the format name
so that every registry version's spelling of the same transform resolves to one
implementation (TR1's ``ixt:datemonthdayyearen`` and TR4's
``ixt:date-monthname-day-year-en`` are the same rule).

Two failures are reported rather than swallowed, because a silently untransformed
value is indistinguishable from a correctly transformed one:

- :class:`UnknownTransformError` - the format is not implemented here.
- :class:`TransformError` - the format is implemented but the input does not
  match what it accepts (a filer error, or our rule being too narrow).

Callers decide the policy; see ``XBRLExtractor._get_fact_value``.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from typing import Callable, Dict, Optional

__all__ = [
    'TransformError',
    'UnknownTransformError',
    'normalize_format',
    'apply_transform',
    'is_known_format',
    'apply_scale',
]


class TransformError(ValueError):
    """The format is implemented, but the input does not satisfy it."""


class UnknownTransformError(TransformError):
    """The format is not implemented by this registry."""


# ---------------------------------------------------------------------------
# Format-name normalization
# ---------------------------------------------------------------------------

def normalize_format(format_attr: str) -> str:
    """
    Reduce a format QName to a registry key.

    Strips the prefix or namespace URI, lowercases, and removes the separators
    that differ between registry versions, so ``ixt:date-monthname-day-year-en``,
    ``ixt:datemonthnamedayyearen`` and
    ``{http://.../transformation/2020-02-12}date-monthname-day-year-en`` all
    reduce to ``datemonthnamedayyearen``.
    """
    name = (format_attr or '').strip()
    if not name:
        return ''
    if '}' in name:              # {namespace-uri}local-name
        name = name.split('}')[-1]
    elif ':' in name:            # prefix:local-name
        name = name.rsplit(':', 1)[-1]
    return re.sub(r'[-_\s]', '', name).lower()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Inline XBRL content routinely carries non-breaking spaces and the various
# Unicode dashes; normalizing them once keeps every rule below simple.
_SPACES = '         '
_DASHES = '‐‑‒–—―−'


def _clean(value: str) -> str:
    text = value or ''
    for ch in _SPACES:
        text = text.replace(ch, ' ')
    return ' '.join(text.split())


def _fail(value: str, expected: str) -> 'TransformError':
    return TransformError(f"{value!r} is not {expected}")


def _fixed(constant: str) -> Callable[[str], str]:
    """A transform whose output ignores the element's content entirely."""
    return lambda _value: constant


MONTHS = {
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
    'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6, 'july': 7, 'jul': 7,
    'august': 8, 'aug': 8, 'september': 9, 'sep': 9, 'sept': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12,
}

_DAYS_IN_MONTH = (0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def _check_month_day(month: int, day: int, value: str) -> None:
    if not 1 <= month <= 12 or not 1 <= day <= _DAYS_IN_MONTH[month]:
        raise _fail(value, 'a valid month/day')


def _iso_date(year: int, month: int, day: int, value: str) -> str:
    _check_month_day(month, day, value)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _month_number(token: str, value: str) -> int:
    month = MONTHS.get(token.strip('.').lower())
    if month is None:
        raise _fail(value, 'an English month name')
    return month


def _expand_year(digits: str) -> int:
    """Two-digit years follow the registry rule: 00-99 map into 2000-2099."""
    year = int(digits)
    return year + 2000 if len(digits) <= 2 else year


# ---------------------------------------------------------------------------
# Numeric transforms
# ---------------------------------------------------------------------------

def _strip_sign(text: str):
    """Split a leading/parenthesized negation off the numeric body."""
    negative = False
    if text.startswith('(') and text.endswith(')'):
        negative, text = True, text[1:-1].strip()
    for dash in _DASHES + '-':
        if text.startswith(dash):
            negative, text = not negative, text[1:].strip()
            break
    return negative, text


def _numeric(value: str, thousands: str, decimal: str) -> str:
    text = _clean(value)
    if not text:
        raise _fail(value, 'a number')
    negative, text = _strip_sign(text)
    for sep in thousands:
        text = text.replace(sep, '')
    if decimal and decimal != '.':
        text = text.replace(decimal, '.')
    text = text.replace(' ', '')
    if not re.fullmatch(r'\d*\.?\d+|\d+\.?', text):
        raise _fail(value, 'a number')
    if text.endswith('.'):
        text = text[:-1]
    return ('-' + text) if negative and text.strip('0.') else text


def _num_words_en(value: str) -> str:
    """English cardinal words to a non-negative integer, per ixt-sec:numwordsen."""
    text = _clean(value).lower().replace('-', ' ').replace(' and ', ' ')
    if not text:
        raise _fail(value, 'an English number')
    if re.fullmatch(r'\d+', text):
        return text
    if text in ('no', 'none', 'nil', 'zero'):
        return '0'

    units = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
             'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
             'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
             'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
             'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40,
             'fourty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
             'eighty': 80, 'ninety': 90}
    scales = {'hundred': 100, 'thousand': 1000, 'million': 10 ** 6,
              'billion': 10 ** 9, 'trillion': 10 ** 12}

    total = current = 0
    saw_word = False
    for word in text.split():
        if word in units:
            current += units[word]
        elif word == 'hundred':
            current = (current or 1) * 100
        elif word in scales:
            total += (current or 1) * scales[word]
            current = 0
        elif word.isdigit():
            current += int(word)
        elif word in ('a', 'an'):
            current += 1
        else:
            raise _fail(value, 'an English number')
        saw_word = True
    if not saw_word:
        raise _fail(value, 'an English number')
    return str(total + current)


def _bool_ballot_box(value: str) -> str:
    """A checkbox glyph to a boolean, per ixt-sec:boolballotbox."""
    text = _clean(value)
    if text in ('☐',):                          # empty ballot box
        return 'false'
    if text in ('☑', '☒', '■', '◼'):  # checked / crossed / filled
        return 'true'
    raise _fail(value, 'a ballot box character')


# ---------------------------------------------------------------------------
# Date transforms
# ---------------------------------------------------------------------------

_SEPS = r'[./\-\s]'


def _date_numeric(order: str) -> Callable[[str], str]:
    """
    Numeric dates in a fixed field order.

    ``order`` is a permutation of ``'d'``, ``'m'``, ``'y'`` naming the fields as
    they appear in the display text.
    """
    pattern = re.compile(_SEPS.join(r'(\d{1,4})' for _ in order) + r'\.?')

    def transform(value: str) -> str:
        text = _clean(value)
        match = pattern.fullmatch(text)
        if not match:
            raise _fail(value, f'a numeric {"/".join(order)} date')
        fields = dict(zip(order, match.groups(), strict=True))
        if 'y' in fields:
            return _iso_date(_expand_year(fields['y']), int(fields['m']), int(fields['d']), value)
        month, day = int(fields['m']), int(fields['d'])
        _check_month_day(month, day, value)
        return f"--{month:02d}-{day:02d}"

    return transform


def _date_words(order: str) -> Callable[[str], str]:
    """
    Dates written with an English month name, in the given field order.

    ``order`` uses ``'M'`` for the month name and ``'d'`` / ``'y'`` for the
    numeric fields.
    """
    def transform(value: str) -> str:
        text = _clean(value).replace(',', ' ')
        tokens = _clean(text).split()
        if len(tokens) != len(order):
            raise _fail(value, f'a date of the form {order}')
        fields = dict(zip(order, tokens, strict=True))
        month = _month_number(fields['M'], value)
        if 'd' not in fields:                                    # gYearMonth
            year = fields['y']
            if not re.fullmatch(r'\d{1,4}', year):
                raise _fail(value, 'a year')
            return f"{_expand_year(year):04d}-{month:02d}"
        day_text = fields['d'].rstrip('.')
        day_match = re.fullmatch(r'(\d{1,2})(?:st|nd|rd|th)?', day_text, re.I)
        if not day_match:
            raise _fail(value, 'a day of the month')
        day = int(day_match.group(1))
        if 'y' not in fields:                                    # gMonthDay
            _check_month_day(month, day, value)
            return f"--{month:02d}-{day:02d}"
        if not re.fullmatch(r'\d{1,4}', fields['y']):
            raise _fail(value, 'a year')
        return _iso_date(_expand_year(fields['y']), month, day, value)

    return transform


def _date_month_year_words(value: str) -> str:
    return _date_words('My')(value)


def _date_year_month_words(value: str) -> str:
    return _date_words('yM')(value)


# ---------------------------------------------------------------------------
# Duration transforms (ixt-sec)
# ---------------------------------------------------------------------------

def _duration_number(designator: str, time_part: bool = False) -> Callable[[str], str]:
    """A bare count of years/months/days/hours to an xs:duration."""
    def transform(value: str) -> str:
        text = _clean(value)
        # "10", "10 years" and "10-year" all appear in filings for these formats.
        text = re.sub(r'[-\s]*(years?|months?|days?|hours?)$', '', text, flags=re.I).strip()
        if not re.fullmatch(r'\d+(\.\d+)?', text):
            text = _num_words_en(text)
        number = text.rstrip('.')
        if number.startswith('.'):
            number = '0' + number
        return f"PT{number}{designator}" if time_part else f"P{number}{designator}"

    return transform


_DURATION_UNITS = {'year': 'Y', 'month': 'M', 'week': 'W', 'day': 'D',
                   'hour': 'H', 'minute': 'M', 'second': 'S'}
_DURATION_ORDER = ('Y', 'M', 'W', 'D', 'H', 'MIN', 'S')


def _dur_words_en(value: str) -> str:
    """
    English duration phrases to an xs:duration, per ixt-sec:durwordsen.

    Handles the shapes filers actually use: ``five years``, ``three-year``,
    ``364-day``, ``two years and six months``.
    """
    text = _clean(value).lower().replace('’', "'")
    for dash in _DASHES:
        text = text.replace(dash, '-')
    if not text:
        raise _fail(value, 'an English duration')
    text = re.sub(r"'s\b|\bs\b", '', text)
    parts = re.findall(r'([\w\s]+?)[\s-]+(years?|months?|weeks?|days?|hours?|minutes?|seconds?)\b', text)
    if not parts:
        raise _fail(value, 'an English duration')

    amounts: Dict[str, str] = {}
    for count_text, unit_text in parts:
        count_text = count_text.replace(' and ', ' ').strip()
        count_text = re.sub(r'^(a|an|the|of|for|approximately|about|up to)\b\s*', '', count_text).strip()
        if not count_text:
            count_text = 'one'
        count = count_text if re.fullmatch(r'\d+(\.\d+)?', count_text) else _num_words_en(count_text)
        unit = _DURATION_UNITS[unit_text.rstrip('s')]
        if unit_text.startswith('minute'):
            unit = 'MIN'
        if unit in amounts:
            raise _fail(value, 'an English duration with distinct units')
        amounts[unit] = count

    date_part = ''.join(f"{amounts[u]}{u}" for u in ('Y', 'M', 'W', 'D') if u in amounts)
    time_units = [(u, 'M' if u == 'MIN' else u) for u in ('H', 'MIN', 'S') if u in amounts]
    time_part = ''.join(f"{amounts[u]}{designator}" for u, designator in time_units)
    if not date_part and not time_part:
        raise _fail(value, 'an English duration')
    return 'P' + date_part + ('T' + time_part if time_part else '')


# ---------------------------------------------------------------------------
# SEC name-to-code transforms (ixt-sec)
# ---------------------------------------------------------------------------

def _lookup_key(name: str) -> str:
    """Fold a name to a comparison key: ASCII, lowercase, punctuation-free."""
    text = unicodedata.normalize('NFKD', _clean(name))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = text.lower().replace('&', ' and ')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return ' '.join(text.split())


@lru_cache(maxsize=1)
def _place_name_to_code() -> Dict[str, Dict[str, str]]:
    """
    SEC place-code tables keyed by name.

    Returns two maps: ``stateprov`` (US states and Canadian provinces, the
    domain of ixt-sec:stateprovnameen) and ``all`` (those plus every foreign
    jurisdiction, the domain of ixt-sec:edgarprovcountryen).
    """
    from edgar.reference.data.common import read_csv_from_package

    frame = read_csv_from_package('place_codes.csv')
    stateprov: Dict[str, str] = {}
    every: Dict[str, str] = {}
    for _, row in frame.iterrows():
        code, place, kind = row['Code'], row['Place'], row['Type']
        names = [place]
        # Canadian provinces are stored as "ALBERTA CANADA"; filers write "Alberta".
        if kind == 'CANADIAN' and place.upper().endswith(' CANADA'):
            names.append(place[:-len(' CANADA')])
        # A parenthesized qualifier is EDGAR's disambiguation, not part of the
        # name a filer types: "CANADA (FEDERAL LEVEL)" is written "Canada".
        if '(' in place:
            names.append(place.split('(')[0])
        for name in names:
            key = _lookup_key(name)
            every.setdefault(key, code)
            if kind in ('US', 'CANADIAN'):
                stateprov.setdefault(key, code)
    return {'stateprov': stateprov, 'all': every}


@lru_cache(maxsize=1)
def _country_name_to_code() -> Dict[str, str]:
    """ISO 3166-1 country names (and common spellings) to alpha-2 codes."""
    from edgar.reference.data.common import read_csv_from_package

    frame = read_csv_from_package('iso3166.csv')
    return {_lookup_key(row['Name']): row['Code'] for _, row in frame.iterrows()}


def _state_prov_name_en(value: str) -> str:
    code = _place_name_to_code()['stateprov'].get(_lookup_key(value))
    if code is None:
        raise _fail(value, 'a US state or Canadian province name')
    return code


def _edgar_prov_country_en(value: str) -> str:
    code = _place_name_to_code()['all'].get(_lookup_key(value))
    if code is None:
        raise _fail(value, 'an EDGAR state, province or country name')
    return code


def _country_name_en(value: str) -> str:
    code = _country_name_to_code().get(_lookup_key(value))
    if code is None:
        raise _fail(value, 'an ISO 3166 country name')
    return code


# Exchange names as filers write them on the cover page, to the code the SEC
# expects in dei:SecurityExchangeName. Matching is on the folded key, after the
# leading article and the corporate suffix are dropped.
_EXCHANGE_CODES = {
    'new york stock exchange': 'NYSE',
    'nyse': 'NYSE',
    'nyse american': 'NYSEAMER',
    'american stock exchange': 'NYSEAMER',
    'nyse arca': 'NYSEARCA',
    'nyse national': 'NYSENAT',
    'nyse texas': 'NYSETXSE',
    'nasdaq': 'NASDAQ',
    'nasdaq stock market': 'NASDAQ',
    'nasdaq global select market': 'NASDAQ',
    'nasdaq global market': 'NASDAQ',
    'nasdaq capital market': 'NASDAQ',
    'cboe bzx': 'CboeBZX',
    'cboe byx': 'CboeBYX',
    'cboe edgx': 'CboeEDGX',
    'cboe edga': 'CboeEDGA',
    'cboe c2': 'C2',
    'cboe exchange': 'CBOE',
    'chicago board options exchange': 'CBOE',
    'chicago stock exchange': 'CHX',
    'investors exchange': 'IEX',
    'iex': 'IEX',
    'long term stock exchange': 'LTSE',
    'members exchange': 'MEMX',
    'memx': 'MEMX',
    'miax pearl': 'MIAXPEARL',
    'miami international securities exchange': 'MIAX',
    'box exchange': 'BOX',
    'nyse chicago': 'NYSECHX',
    'bse': 'BX',
}


def _exchange_name_en(value: str) -> str:
    key = _lookup_key(value)
    key = re.sub(r'^the\s+', '', key)
    key = re.sub(r'\s+(inc|llc|lp|corporation|corp|ltd|limited)$', '', key)
    key = re.sub(r'\s+exchange llc$', ' exchange', key)
    code = _EXCHANGE_CODES.get(key)
    if code is None:
        raise _fail(value, 'a registered securities exchange name')
    return code


# dei:EntityFilerCategory is an enumeration; filers vary the capitalization.
_FILER_CATEGORIES = {
    'large accelerated filer': 'Large Accelerated Filer',
    'accelerated filer': 'Accelerated Filer',
    'non accelerated filer': 'Non-accelerated Filer',
    'smaller reporting company': 'Smaller Reporting Company',
    'emerging growth company': 'Emerging Growth Company',
}


def _entity_filer_category_en(value: str) -> str:
    category = _FILER_CATEGORIES.get(_lookup_key(value))
    if category is None:
        raise _fail(value, 'a dei:EntityFilerCategory value')
    return category


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

TRANSFORMS: Dict[str, Callable[[str], str]] = {
    # -- numeric -----------------------------------------------------------
    'numdotdecimal': lambda v: _numeric(v, thousands=', ', decimal='.'),
    'numdotdecimalin': lambda v: _numeric(v, thousands=', ', decimal='.'),
    'numcommadecimal': lambda v: _numeric(v, thousands='. ', decimal=','),
    'numcomma': lambda v: _numeric(v, thousands='', decimal=','),
    'numdotcomma': lambda v: _numeric(v, thousands='. ', decimal=','),
    'numspacedot': lambda v: _numeric(v, thousands=' ', decimal='.'),
    'numspacecomma': lambda v: _numeric(v, thousands=' ', decimal=','),
    'numunitdecimal': lambda v: _numeric(v, thousands=', ', decimal='.'),
    'numwordsen': _num_words_en,

    # -- fixed-output ------------------------------------------------------
    'fixedzero': _fixed('0'),
    'fixedempty': _fixed(''),
    'nocontent': _fixed(''),
    'fixedtrue': _fixed('true'),
    'fixedfalse': _fixed('false'),
    'booleantrue': _fixed('true'),
    'booleanfalse': _fixed('false'),
    'boolballotbox': _bool_ballot_box,
    # zerodash is the one dash rule that is not fixed: only a dash becomes 0.
    'zerodash': lambda v: '0' if _clean(v).strip(_DASHES + '-') == '' and _clean(v) else _numeric(v, ', ', '.'),
    'numdash': lambda v: '0' if _clean(v).strip(_DASHES + '-') == '' and _clean(v) else _numeric(v, ', ', '.'),

    # -- numeric dates -----------------------------------------------------
    'datedoteu': _date_numeric('dmy'),
    'datedotus': _date_numeric('mdy'),
    'dateslasheu': _date_numeric('dmy'),
    'dateslashus': _date_numeric('mdy'),
    'datedaymonthyear': _date_numeric('dmy'),
    'datemonthdayyear': _date_numeric('mdy'),
    'dateyearmonthday': _date_numeric('ymd'),
    'datedaymonth': _date_numeric('dm'),
    'datemonthday': _date_numeric('md'),
    'dateeu': _date_numeric('dmy'),
    'dateus': _date_numeric('mdy'),

    # -- dates written with a month name -----------------------------------
    # TR1 spelled these ``datemonthdayyearen``; TR3/TR4 spell the same rule
    # ``date-monthname-day-year-en``. Both keys land here.
    'datemonthdayyearen': _date_words('Mdy'),
    'datemonthnamedayyearen': _date_words('Mdy'),
    'datelongus': _date_words('Mdy'),
    'dateshortus': _date_words('Mdy'),
    'datedaymonthyearen': _date_words('dMy'),
    'datedaymonthnameyearen': _date_words('dMy'),
    'datelongeu': _date_words('dMy'),
    'dateshorteu': _date_words('dMy'),
    'datemonthdayen': _date_words('Md'),
    'datemonthnamedayen': _date_words('Md'),
    'datelongmonthday': _date_words('Md'),
    'dateshortmonthday': _date_words('Md'),
    'datedaymonthen': _date_words('dM'),
    'datedaymonthnameen': _date_words('dM'),
    'datelongdaymonth': _date_words('dM'),
    'dateshortdaymonth': _date_words('dM'),
    'datemonthyearen': _date_month_year_words,
    'datemonthnameyearen': _date_month_year_words,
    'datelongmonthyear': _date_month_year_words,
    'dateshortmonthyear': _date_month_year_words,
    'dateyearmonthen': _date_year_month_words,
    'dateyearmonthnameen': _date_year_month_words,

    # -- durations (ixt-sec) -----------------------------------------------
    'duryear': _duration_number('Y'),
    'durmonth': _duration_number('M'),
    'durweek': _duration_number('W'),
    'durday': _duration_number('D'),
    'durhour': _duration_number('H', time_part=True),
    'durwordsen': _dur_words_en,

    # -- SEC name-to-code (ixt-sec) ----------------------------------------
    'stateprovnameen': _state_prov_name_en,
    'edgarprovcountryen': _edgar_prov_country_en,
    'countrynameen': _country_name_en,
    'exchnameen': _exchange_name_en,
    'entityfilercategoryen': _entity_filer_category_en,
}


def is_known_format(format_attr: str) -> bool:
    """Whether this registry implements the named transformation."""
    return normalize_format(format_attr) in TRANSFORMS


def apply_transform(format_attr: str, value: str) -> str:
    """
    Apply the named transformation to an element's display text.

    Raises :class:`UnknownTransformError` if the format is not implemented, and
    :class:`TransformError` if it is implemented but the input does not satisfy
    it. Neither is swallowed here: returning ``value`` unchanged would make an
    untransformed display string indistinguishable from a real value.
    """
    key = normalize_format(format_attr)
    transform = TRANSFORMS.get(key)
    if transform is None:
        raise UnknownTransformError(f"No implementation for iXBRL format {format_attr!r}")
    return transform(value)


# ---------------------------------------------------------------------------
# Scale
# ---------------------------------------------------------------------------

def apply_scale(value: str, scale: str) -> Optional[str]:
    """
    Multiply a lexical numeric value by ``10 ** scale``, exactly.

    Binary floating point cannot represent the powers of ten this attribute
    names, so ``float('0.7') * 10 ** -2`` yields ``0.006999999999999999``. That
    error used to be written back into the fact's lexical value, where it also
    reached ``numeric_value``. Decimal keeps the result exact and free of
    exponent notation.

    Returns None if either input is not numeric, leaving the caller's value
    untouched.
    """
    try:
        scale_factor = int(scale)
    except (TypeError, ValueError):
        return None
    try:
        scaled = Decimal(value.replace(',', '').strip()).scaleb(scale_factor)
    except (InvalidOperation, AttributeError, ValueError):
        return None
    # scaleb can leave an exponent (1.234E+9); 'f' renders positional digits.
    # normalize() first so 7E-3 does not print as 0.007000.
    return f"{scaled.normalize():f}"
