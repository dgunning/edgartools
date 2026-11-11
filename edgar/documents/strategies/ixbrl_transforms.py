"""
Inline XBRL Transformation Registry.

An ``ix:nonNumeric`` / ``ix:nonFraction`` element carries human display text; its
``format`` attribute names the transformation that turns that text into the
fact's semantic value. Without the transformation the fact value is the display
string, which is a different thing that happens to look plausible: ``"Delaware"``
where the value is ``"DE"``, ``"ten years"`` where it is ``"P10Y"``.

A ``format`` is an expanded name: a registry namespace URI plus a rule's local
name (Inline XBRL 1.1, sections 10.1.1 and 11.1.1). :data:`REGISTRIES` keys each
supported registry by its namespace URI, and a format whose prefix is declared
in the document resolves only to a rule of THAT registry, by its exact local
name: TR3 has no ``fixed-zero``, so ``{TR3}fixed-zero`` is unknown.

A format whose prefix is not declared (a direct call such as
``apply_transform('ixt:num-dot-decimal', ...)``, or a fragment parsed without its
root) falls back to :data:`TRANSFORMS`, a compatibility view keyed on the
normalized local name, in which the newest registry defining a name wins.

Coverage is partial and stated here rather than implied. Implemented: every
numeric, fixed-value, English, numeric-date and Roman-numeral-month rule of
Transformation Registries 1-5, and every ``ixt-sec`` rule. Not implemented:
the date rules written in languages other than English (TR3 ``*dk``/``*in``,
TR4/TR5 ``*-bg`` ... ``*-sv``, ``-cy``, ``-hi``, ``-hu``, ``-lt``, ``-lv``),
the CJK and Japanese-era rules, and ``calindaymonthyear``; those raise
:class:`UnknownTransformError`.

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

from edgar.xmltools import prefix_namespace

__all__ = [
    'TransformError',
    'UnknownTransformError',
    'normalize_format',
    'expand_format',
    'apply_transform',
    'is_known_format',
    'apply_scale',
    'negate_exactly',
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


# Registry namespace URIs (Inline XBRL Transformation Registries 1-5 and the
# SEC's ixt-sec registry).
TR1_PRE_REC_NS = 'http://www.xbrl.org/2008/inlineXBRL/transformation'
TR1_NS = 'http://www.xbrl.org/inlineXBRL/transformation/2010-04-20'
TR2_NS = 'http://www.xbrl.org/inlineXBRL/transformation/2011-07-31'
TR3_NS = 'http://www.xbrl.org/inlineXBRL/transformation/2015-02-26'
TR4_NS = 'http://www.xbrl.org/inlineXBRL/transformation/2020-02-12'
TR5_NS = 'http://www.xbrl.org/inlineXBRL/transformation/2022-02-16'
IXT_SEC_NS = 'http://www.sec.gov/inlineXBRL/transformation/2015-08-31'


def expand_format(element, format_attr: Optional[str]) -> Optional[str]:
    """
    The ``format`` attribute of ``element`` as an expanded name.

    Returns ``{namespace-uri}local-name`` when the prefix is declared in scope,
    and the attribute unchanged when it is not, which leaves resolution to the
    compatibility view (see the module docstring).
    """
    name = (format_attr or '').strip()
    if not name or name.startswith('{') or ':' not in name:
        return format_attr
    prefix, local = name.split(':', 1)
    uri = prefix_namespace(element, prefix)
    return f'{{{uri}}}{local}' if uri else format_attr


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


_NUMBER_WORDS = {'zero': 0, 'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
                 'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
                 'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14,
                 'fifteen': 15, 'sixteen': 16, 'seventeen': 17, 'eighteen': 18,
                 'nineteen': 19, 'twenty': 20, 'thirty': 30, 'forty': 40,
                 'fourty': 40, 'fifty': 50, 'sixty': 60, 'seventy': 70,
                 'eighty': 80, 'ninety': 90}

_NUMBER_SCALES = {'thousand': 1000, 'million': 10 ** 6,
                  'billion': 10 ** 9, 'trillion': 10 ** 12}


def _accumulate_number_word(word: str, total: int, current: int, value: str):
    """Fold one English number word into the running (total, current) pair."""
    if word in _NUMBER_WORDS:
        return total, current + _NUMBER_WORDS[word]
    if word == 'hundred':
        return total, (current or 1) * 100
    if word in _NUMBER_SCALES:
        return total + (current or 1) * _NUMBER_SCALES[word], 0
    if word.isdigit():
        return total, current + int(word)
    if word in ('a', 'an'):
        return total, current + 1
    raise _fail(value, 'an English number')


def _num_words_en(value: str) -> str:
    """English cardinal words to a non-negative integer, per ixt-sec:numwordsen."""
    text = _clean(value).lower().replace('-', ' ').replace(' and ', ' ')
    if not text:
        raise _fail(value, 'an English number')
    if re.fullmatch(r'\d+', text):
        return text
    if text in ('no', 'none', 'nil', 'zero'):
        return '0'

    total = current = 0
    saw_word = False
    for word in text.split():
        total, current = _accumulate_number_word(word, total, current, value)
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

# A word date's fields are separated by a run of anything that is neither a digit
# nor a letter, per the Transformation Registry's separator grammar. The month is
# a NAME here, so the numeric ``_SEPS`` class cannot be reused: it must not eat
# the letters it sits beside.
_WORD_DATE_SEPS = re.compile(r'[^0-9A-Za-z]+')


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
        if 'd' not in fields:                                    # gYearMonth
            month = int(fields['m'])
            if not 1 <= month <= 12:
                raise _fail(value, 'a valid month')
            return f"{_expand_year(fields['y']):04d}-{month:02d}"
        if 'y' in fields:
            return _iso_date(_expand_year(fields['y']), int(fields['m']), int(fields['d']), value)
        month, day = int(fields['m']), int(fields['d'])
        _check_month_day(month, day, value)
        return f"--{month:02d}-{day:02d}"

    return transform


def _date_words(order: str,
                month_number: Callable[[str, str], int] = None) -> Callable[[str], str]:
    """
    Dates written with an English month name, in the given field order.

    ``order`` uses ``'M'`` for the month name and ``'d'`` / ``'y'`` for the
    numeric fields. ``month_number`` reads the month token; the default reads
    an English name, :func:`_roman_month_number` a Roman numeral.
    """
    month_number = month_number or _month_number

    def transform(value: str) -> str:
        # Split on the separator RUN, not on whitespace. Replacing commas with
        # spaces and calling .split() accepted only space-separated dates, so
        # '19-Sep-2024' stayed a single token and every hyphenated, dotted or
        # slashed date was rejected -- across all 13 formats sharing this
        # tokenizer, not just the one reported. The numeric sibling already
        # accepted those separators, which is what made the two disagree.
        tokens = [t for t in _WORD_DATE_SEPS.split(_clean(value)) if t]
        if len(tokens) != len(order):
            raise _fail(value, f'a date of the form {order}')
        fields = dict(zip(order, tokens, strict=True))
        month = month_number(fields['M'], value)
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


_ROMAN_MONTHS = {'i': 1, 'ii': 2, 'iii': 3, 'iv': 4, 'v': 5, 'vi': 6, 'vii': 7,
                 'viii': 8, 'ix': 9, 'x': 10, 'xi': 11, 'xii': 12}


def _roman_month_number(token: str, value: str) -> int:
    month = _ROMAN_MONTHS.get(token.strip('.').lower())
    if month is None:
        raise _fail(value, 'a Roman-numeral month')
    return month


# Apostrophes and primes that TR5's ``*-apos`` rules accept as a thousands
# separator ("1'234'567.89").
_APOSTROPHES = "'`´’′＇"

# num-unit-decimal: an integer part, a unit word, then one or two digits of
# fraction and an optional minor-unit word ("5 dollars 25 cents" is 5.25).
_UNIT_DECIMAL = re.compile(r'([0-9.,，]+)[^0-9.,，][^0-9]*?([0-9]{1,2})[^0-9]*')


def _num_unit_decimal(separators: str = '.,，') -> Callable[[str], str]:
    def transform(value: str) -> str:
        text = _clean(value)
        for apostrophe in _APOSTROPHES:
            if apostrophe in separators:
                text = text.replace(apostrophe, ',')
        match = _UNIT_DECIMAL.fullmatch(text)
        if not match:
            raise _fail(value, 'an amount in major and minor units')
        major = re.sub(r'[.,，]', '', match.group(1))
        if not major:
            raise _fail(value, 'an amount in major and minor units')
        return _plain_decimal(Decimal(f"{major}.{match.group(2).zfill(2)}"))
    return transform


def _num_dash(value: str) -> str:
    """A lone dash means zero (TR1 numdash, TR2/TR3 zerodash)."""
    text = _clean(value)
    if text and text.strip(_DASHES + '-') == '':
        return '0'
    return _numeric(value, ', ', '.')


# ---------------------------------------------------------------------------
# Duration transforms (ixt-sec)
# ---------------------------------------------------------------------------

# An xs:duration allows a fraction only on its seconds, so the SEC's rules
# spill a fractional count into the next smaller unit and truncate there:
# 9.5 years is P9Y6M, 2.5 months P2M15D (a month is 30.4375 days), 1.5 days
# P1DT12H, 1.5 weeks P10D (xs:duration has no weeks) and 1.5 hours PT1H.
_DAYS_PER_MONTH = Decimal('30.4375')


def _split_years(n: Decimal):
    years = int(n)
    months = (n - years) * 12
    return years, int(months), int((months - int(months)) * _DAYS_PER_MONTH), None


def _split_months(n: Decimal):
    months = int(n)
    return None, months, int((n - months) * _DAYS_PER_MONTH), None


def _split_weeks(n: Decimal):
    return None, None, int(n * 7), None


def _split_days(n: Decimal):
    days = int(n)
    return None, None, days, int((n - days) * 24)


def _split_hours(n: Decimal):
    return None, None, None, int(n)


_DURATION_SPLITS = {'Y': _split_years, 'M': _split_months, 'W': _split_weeks,
                    'D': _split_days, 'H': _split_hours}


def _duration_lexical(years, months, days, hours, negative: bool = False) -> str:
    """
    Components to an xs:duration, as the SEC's ixt-sec implementation writes it.

    ``None`` means the rule does not produce that component. The first component
    the rule produces is always written and a later one only when it is not zero,
    so 9 years is ``P9Y``, half a year ``P0Y6M``, and zero years ``P0Y`` with no sign.
    """
    parts = [(years, 'Y'), (months, 'M'), (days, 'D'), (hours, 'H')]
    produced = [(count, unit) for count, unit in parts if count is not None]
    if not any(count for count, _ in produced):
        negative = False
    produced = produced[:1] + [(count, unit) for count, unit in produced[1:] if count]
    date_part = ''.join(f"{count}{unit}" for count, unit in produced if unit != 'H')
    time_part = ''.join(f"T{count}H" for count, unit in produced if unit == 'H')
    return ('-' if negative else '') + 'P' + date_part + time_part


def _duration_number(designator: str) -> Callable[[str], str]:
    """A count of years/months/weeks/days/hours to an xs:duration."""
    split = _DURATION_SPLITS[designator]

    def transform(value: str) -> str:
        text = _clean(value)
        # "10", "10 years" and "10-year" all appear in filings for these formats.
        text = re.sub(r'[-\s]*(years?|months?|weeks?|days?|hours?)$', '', text, flags=re.I).strip()
        if not re.fullmatch(r'[+-]?(\d+(\.\d*)?|\.\d+)', text):
            text = _num_words_en(text)
        number = Decimal(text)
        return _duration_lexical(*split(abs(number)), negative=number < 0)

    return transform


_DURATION_UNITS = {'year': 'Y', 'month': 'M', 'week': 'W', 'day': 'D',
                   'hour': 'H', 'minute': 'M', 'second': 'S'}
_DURATION_ORDER = ('Y', 'M', 'W', 'D', 'H', 'MIN', 'S')

# Real durations are a few words ("two years and six months" is 24 characters).
# The phrase regex below is quadratic in its input, so 24 KB of filer-supplied
# text took 7 s; anything longer than this cannot be a duration and is refused
# before matching (attack-surface audit 2026-10-22).
_DUR_WORDS_MAX_LEN = 200


_DUR_WORDS_PART = re.compile(
    r'([\w\s-]+?)[\s-]+(years?|months?|weeks?|days?|hours?|minutes?|seconds?)\b')
_DUR_WORDS_GAP = re.compile(r'[\s,;-]*(?:and\b[\s-]*)?')


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
    if len(text) > _DUR_WORDS_MAX_LEN:
        raise _fail(text[:40] + '...',
                    f'an English duration (longer than {_DUR_WORDS_MAX_LEN} characters)')
    text = re.sub(r"'s\b|\bs\b", '', text)
    matches = list(_DUR_WORDS_PART.finditer(text))
    # Every character must belong to a component or to the punctuation between
    # them. findall alone skipped what it could not read, so "5.5 years" lost
    # its "5." and came out as P5Y.
    ends = [0] + [m.end() for m in matches]
    starts = [m.start() for m in matches] + [len(text)]
    if not matches or any(_DUR_WORDS_GAP.fullmatch(text[e:s]) is None for e, s in zip(ends, starts, strict=True)):
        raise _fail(value, 'an English duration')
    parts = [m.groups() for m in matches]

    amounts: Dict[str, int] = {}
    for count_text, unit_text in parts:
        unit = 'MIN' if unit_text.startswith('minute') else _DURATION_UNITS[unit_text.rstrip('s')]
        if unit in amounts:
            raise _fail(value, 'an English duration with distinct units')
        amounts[unit] = _duration_word_count(count_text, value)

    # xs:duration has no weeks; a week is seven days, as in ixt-sec:durweek.
    if 'W' in amounts:
        amounts['D'] = amounts.get('D', 0) + 7 * amounts.pop('W')
    date_part = ''.join(f"{amounts[u]}{u}" for u in ('Y', 'M', 'D') if u in amounts)
    time_units = [(u, 'M' if u == 'MIN' else u) for u in ('H', 'MIN', 'S') if u in amounts]
    time_part = ''.join(f"{amounts[u]}{designator}" for u, designator in time_units)
    if not date_part and not time_part:
        raise _fail(value, 'an English duration')
    return 'P' + date_part + ('T' + time_part if time_part else '')


def _duration_word_count(count_text: str, value: str) -> int:
    """
    One duration component's count, written in words or digits.

    The SEC's grammar for these phrases takes whole numbers only: "5.5 years"
    is not one of them, and writing it as P5.5Y is not an xs:duration either.
    """
    count_text = count_text.replace(' and ', ' ').strip()
    count_text = re.sub(r'^(a|an|the|of|for|approximately|about|up to)\b\s*', '', count_text).strip()
    if not count_text:
        return 1
    if re.fullmatch(r'\d+', count_text):
        return int(count_text)
    if re.fullmatch(r'\d*\.\d+', count_text):
        raise _fail(value, 'an English duration in whole units')
    return int(_num_words_en(count_text))


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
# expects in dei:SecurityExchangeName (the dei edgarExchangeCodeItemType
# enumeration; the 21 names of SEC's ixt-sec:exchnameen registry are all here).
# Matching is on the folded key, after the leading article and the corporate
# suffix are dropped. Every value must be a member of that enumeration, which
# matches exactly, case included: NYSE Texas is NYSETX (dei 2026), and NYSE
# Chicago, the former Chicago Stock Exchange, is CHX. The Long-Term Stock
# Exchange and MEMX have no dei code, so their names are rejected rather than
# given an invented one.
_EXCHANGE_CODES = {
    'new york stock exchange': 'NYSE',
    'nyse': 'NYSE',
    'nyse american': 'NYSEAMER',
    'american stock exchange': 'NYSEAMER',
    'nyse arca': 'NYSEArca',
    'nyse national': 'NYSENAT',
    'nyse texas': 'NYSETX',
    'nasdaq': 'NASDAQ',
    'nasdaq stock market': 'NASDAQ',
    'nasdaq global select market': 'NASDAQ',
    'nasdaq global market': 'NASDAQ',
    'nasdaq capital market': 'NASDAQ',
    'cboe bzx': 'CboeBZX',
    'cboe bzx exchange': 'CboeBZX',
    'cboe byx': 'CboeBYX',
    'cboe byx exchange': 'CboeBYX',
    'cboe edgx': 'CboeEDGX',
    'cboe edgx exchange': 'CboeEDGX',
    'cboe edga': 'CboeEDGA',
    'cboe edga exchange': 'CboeEDGA',
    'cboe c2': 'C2',
    'cboe c2 exchange': 'C2',
    'nasdaq bx': 'BX',
    'nasdaq gemx': 'GEMX',
    'nasdaq ise': 'ISE',
    'nasdaq mrx': 'MRX',
    'nasdaq phlx': 'Phlx',
    'cboe exchange': 'CBOE',
    'chicago board options exchange': 'CBOE',
    'chicago stock exchange': 'CHX',
    'investors exchange': 'IEX',
    'iex': 'IEX',
    'miax pearl': 'PEARL',
    'miami international securities exchange': 'MIAX',
    'box exchange': 'BOX',
    'nyse chicago': 'CHX',
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


def _yes_no_ballot_box(value: str) -> str:
    """A checkbox glyph to Yes/No, per ixt-sec:yesnoballotbox."""
    return 'Yes' if _bool_ballot_box(value) == 'true' else 'No'


_QUARTER_MONTHS = {'1': 3, 'first': 3, '2': 6, 'second': 6, '3': 9, 'third': 9,
                   '4': 12, 'fourth': 12, 'last': 12}
_QUARTER = r'(1|first|2|second|3|third|4|fourth|last)'
# "Q3 2024", "third quarter of 2024", "2024 Q3", "fiscal 2024, third quarter"
_QUARTER_YEAR = re.compile(r'(?:(?![0-9]{2})\w[^0-9]*?)?' + _QUARTER + r'[^0-9]*?([0-9]{4})', re.I)
_YEAR_QUARTER = re.compile(r'([0-9]{4})[^0-9]*?' + _QUARTER + r'(?:(?![0-9]).*\w+)?', re.I)


def _date_quarter_end(value: str) -> str:
    """A calendar quarter to the date it ends, per ixt-sec:datequarterend."""
    text = _clean(value)
    match = _QUARTER_YEAR.fullmatch(text)
    if match:
        quarter, year = match.group(1), match.group(2)
    else:
        match = _YEAR_QUARTER.fullmatch(text)
        if not match:
            raise _fail(value, 'a calendar quarter')
        year, quarter = match.group(1), match.group(2)
    month = _QUARTER_MONTHS[quarter.lower()]
    return f"{int(year):04d}-{month:02d}-{31 if month in (3, 12) else 30:02d}"


# ---------------------------------------------------------------------------
# The registries
# ---------------------------------------------------------------------------

def _dot_decimal(value: str) -> str:
    return _numeric(value, thousands=', ', decimal='.')


def _comma_decimal(value: str) -> str:
    return _numeric(value, thousands='. ', decimal=',')


# Transformation Registry 1 (REC 2010-04-20; also the pre-REC 2008 namespace).
_TR1: Dict[str, Callable[[str], str]] = {
    'dateslashus': _date_numeric('mdy'),
    'dateslasheu': _date_numeric('dmy'),
    'datedotus': _date_numeric('mdy'),
    'datedoteu': _date_numeric('dmy'),
    'datelongus': _date_words('Mdy'),
    'dateshortus': _date_words('Mdy'),
    'datelonguk': _date_words('dMy'),
    'dateshortuk': _date_words('dMy'),
    'numcommadot': lambda v: _numeric(v, thousands=',', decimal='.'),
    'numdash': _num_dash,
    'numspacedot': lambda v: _numeric(v, thousands=' ', decimal='.'),
    'numdotcomma': lambda v: _numeric(v, thousands='. ', decimal=','),
    'numcomma': lambda v: _numeric(v, thousands='', decimal=','),
    'numspacecomma': lambda v: _numeric(v, thousands=' ', decimal=','),
    'datelongdaymonthuk': _date_words('dM'),
    'dateshortdaymonthuk': _date_words('dM'),
    'datelongmonthdayus': _date_words('Md'),
    'dateshortmonthdayus': _date_words('Md'),
    'dateslashdaymontheu': _date_numeric('dm'),
    'dateslashmonthdayus': _date_numeric('md'),
    'datelongyearmonth': _date_year_month_words,
    'dateshortyearmonth': _date_year_month_words,
    'datelongmonthyear': _date_month_year_words,
    'dateshortmonthyear': _date_month_year_words,
}

# Transformation Registry 2 (REC 2011-07-31).
_TR2: Dict[str, Callable[[str], str]] = {
    'booleanfalse': _fixed('false'),
    'booleantrue': _fixed('true'),
    'datedaymonth': _date_numeric('dm'),
    'datedaymonthen': _date_words('dM'),
    'datedaymonthyear': _date_numeric('dmy'),
    'datedaymonthyearen': _date_words('dMy'),
    'datemonthday': _date_numeric('md'),
    'datemonthdayen': _date_words('Md'),
    'datemonthdayyear': _date_numeric('mdy'),
    'datemonthdayyearen': _date_words('Mdy'),
    'datemonthyearen': _date_month_year_words,
    'dateyearmonthen': _date_year_month_words,
    'nocontent': _fixed(''),
    'numcommadecimal': _comma_decimal,
    'zerodash': _num_dash,
    'numdotdecimal': _dot_decimal,
    'numunitdecimal': _num_unit_decimal(),
}

# Transformation Registry 3 (REC 2015-02-26): TR2 plus these.
_TR3: Dict[str, Callable[[str], str]] = {
    **_TR2,
    'datemonthyear': _date_numeric('my'),
    'dateyearmonthday': _date_numeric('ymd'),
    'numdotdecimalin': _dot_decimal,
    'numunitdecimalin': _num_unit_decimal(),
}

# Transformation Registry 4 (REC 2020-02-12). A fresh rule set, not TR3's.
_TR4: Dict[str, Callable[[str], str]] = {
    'date-day-month': _date_numeric('dm'),
    'date-day-monthname-en': _date_words('dM'),
    'date-day-monthroman': _date_words('dM', _roman_month_number),
    'date-day-month-year': _date_numeric('dmy'),
    'date-day-monthname-year-en': _date_words('dMy'),
    'date-day-monthroman-year': _date_words('dMy', _roman_month_number),
    'date-monthname-day-en': _date_words('Md'),
    'date-monthname-day-year-en': _date_words('Mdy'),
    'date-month-day': _date_numeric('md'),
    'date-month-day-year': _date_numeric('mdy'),
    'date-month-year': _date_numeric('my'),
    'date-monthname-year-en': _date_month_year_words,
    'date-monthroman-year': _date_words('My', _roman_month_number),
    'date-year-month': _date_numeric('ym'),
    'date-year-month-day': _date_numeric('ymd'),
    'date-year-monthname-en': _date_year_month_words,
    'fixed-empty': _fixed(''),
    'fixed-false': _fixed('false'),
    'fixed-true': _fixed('true'),
    'fixed-zero': _fixed('0'),
    'num-comma-decimal': _comma_decimal,
    'num-dot-decimal': _dot_decimal,
    'numdotdecimalin': _dot_decimal,
    'num-unit-decimal': _num_unit_decimal(),
}

# Transformation Registry 5 (REC 2022-02-16): TR4 plus these.
_TR5: Dict[str, Callable[[str], str]] = {
    **_TR4,
    'num-comma-decimal-apos': lambda v: _numeric(v, thousands='. ' + _APOSTROPHES, decimal=','),
    'num-dot-decimal-apos': lambda v: _numeric(v, thousands=', ' + _APOSTROPHES, decimal='.'),
    'num-unit-decimal-apos': _num_unit_decimal('.,，' + _APOSTROPHES),
}

# The SEC's ixt-sec registry (2015-08-31 namespace).
_IXT_SEC: Dict[str, Callable[[str], str]] = {
    'duryear': _duration_number('Y'),
    'durmonth': _duration_number('M'),
    'durweek': _duration_number('W'),
    'durday': _duration_number('D'),
    'durhour': _duration_number('H'),
    'durwordsen': _dur_words_en,
    'datequarterend': _date_quarter_end,
    'numinf': _fixed('INF'),
    'numneginf': _fixed('-INF'),
    'numnan': _fixed('NaN'),
    'numwordsen': _num_words_en,
    'boolballotbox': _bool_ballot_box,
    'yesnoballotbox': _yes_no_ballot_box,
    'countrynameen': _country_name_en,
    'stateprovnameen': _state_prov_name_en,
    'edgarprovcountryen': _edgar_prov_country_en,
    'exchnameen': _exchange_name_en,
    'entityfilercategoryen': _entity_filer_category_en,
}

# Each supported registry by namespace URI, local name matched exactly.
REGISTRIES: Dict[str, Dict[str, Callable[[str], str]]] = {
    TR1_PRE_REC_NS: _TR1,
    TR1_NS: _TR1,
    TR2_NS: _TR2,
    TR3_NS: _TR3,
    TR4_NS: _TR4,
    TR5_NS: _TR5,
    IXT_SEC_NS: _IXT_SEC,
}


# Names no registry defines, kept because earlier releases accepted them on
# direct calls. They are reachable only through the compatibility view.
_LEGACY_ALIASES: Dict[str, Callable[[str], str]] = {
    'dateeu': _date_numeric('dmy'),
    'dateus': _date_numeric('mdy'),
    'datelongeu': _date_words('dMy'),
    'dateshorteu': _date_words('dMy'),
    'datelongmonthday': _date_words('Md'),
    'dateshortmonthday': _date_words('Md'),
    'datelongdaymonth': _date_words('dM'),
    'dateshortdaymonth': _date_words('dM'),
}


def _compatibility_view() -> Dict[str, Callable[[str], str]]:
    """Every rule keyed on its normalized local name; the newest registry wins."""
    view: Dict[str, Callable[[str], str]] = dict(_LEGACY_ALIASES)
    for rules in (_TR1, _TR2, _TR3, _TR4, _TR5, _IXT_SEC):
        for local_name, transform in rules.items():
            view[normalize_format(local_name)] = transform
    return view


# For formats whose prefix is not declared in scope: direct calls, and
# fragments parsed without their root element. See the module docstring.
TRANSFORMS: Dict[str, Callable[[str], str]] = _compatibility_view()


def _resolve(format_attr: str) -> Optional[Callable[[str], str]]:
    name = (format_attr or '').strip()
    if name.startswith('{') and '}' in name:
        uri, local = name[1:].split('}', 1)
        return REGISTRIES.get(uri.strip(), {}).get(local.strip())
    return TRANSFORMS.get(normalize_format(name))


def is_known_format(format_attr: str) -> bool:
    """
    Whether this registry implements the named transformation.

    ``format_attr`` is either an expanded name, ``{namespace-uri}local-name``,
    which must name a rule of that registry exactly, or a prefixed or bare name,
    resolved through the compatibility view.
    """
    return _resolve(format_attr) is not None


def apply_transform(format_attr: str, value: str) -> str:
    """
    Apply the named transformation to an element's display text.

    ``format_attr`` is resolved as :func:`is_known_format` describes; use
    :func:`expand_format` to turn an element's prefixed ``format`` attribute
    into the expanded name its document declares.

    Raises :class:`UnknownTransformError` if the format is not implemented, and
    :class:`TransformError` if it is implemented but the input does not satisfy
    it. Neither is swallowed here: returning ``value`` unchanged would make an
    untransformed display string indistinguishable from a real value.
    """
    transform = _resolve(format_attr)
    if transform is None:
        raise UnknownTransformError(f"No implementation for iXBRL format {format_attr!r}")
    return transform(value)


# ---------------------------------------------------------------------------
# Scale
# ---------------------------------------------------------------------------

def _plain_decimal(value: Decimal) -> str:
    """Positional form of a finite Decimal without trailing fractional zeros.

    Formatting with ``'f'`` and trimming the text never consults the decimal
    context, unlike ``Decimal.normalize()``, which rounds to the caller's
    precision.
    """
    text = f"{value:f}"
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text or '0'


def apply_scale(value: str, scale: str) -> Optional[str]:
    """
    Multiply a lexical numeric value by ``10 ** scale``, exactly.

    Binary floating point cannot represent the powers of ten this attribute
    names, so ``float('0.7') * 10 ** -2`` yields ``0.006999999999999999``. That
    error used to be written back into the fact's lexical value, where it also
    reached ``numeric_value``. Decimal keeps the result exact and free of
    exponent notation.

    The scaling moves the exponent of the parsed digits and does no arithmetic,
    so the caller's decimal context cannot round it. ``scaleb`` and
    ``normalize`` both round to the ambient precision: under ``prec=8`` IBM's
    927,264,332 shares became 927264330 (GH #1854).

    Returns None if either input is not numeric, leaving the caller's value
    untouched.
    """
    try:
        scale_factor = int(scale)
    except (TypeError, ValueError):
        return None
    number = exact_decimal(value.replace(',', '') if isinstance(value, str) else value)
    if number is None:
        return None
    sign, digits, exponent = number.as_tuple()
    return _plain_decimal(Decimal((sign, digits, exponent + scale_factor)))


def exact_decimal(value: str) -> Optional[Decimal]:
    """Parse a lexical number into a finite Decimal, or None.

    String construction is exact whatever the caller's context. A caller that
    has switched off the ``InvalidOperation`` trap gets ``NaN`` back instead of
    an exception, so finiteness is checked rather than assumed.
    """
    try:
        number = Decimal(value.strip())
    except (InvalidOperation, AttributeError, ValueError, TypeError):
        return None
    return number if number.is_finite() else None


def negate_exactly(value: str) -> Optional[str]:
    """The lexical negation of a number, independent of the decimal context.

    Unary minus on a Decimal rounds to the caller's precision; ``copy_negate``
    only flips the sign.
    """
    number = exact_decimal(value)
    if number is None:
        return None
    return f"{number.copy_negate():f}"
