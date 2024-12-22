import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, Tuple
from typing import Union

from bs4 import Tag

from edgar.core import log as logger

__all__ = ['StyleInfo', 'UnitType', 'StyleUnit', 'parse_style', 'is_heading', 'get_heading_level']

base_font_size = 10.0

# First define the patterns at module level for reliability
HEADING_PATTERNS = {
    # Level 1 patterns (Parts)
    'l1': re.compile(r'(?i)^part\s+[IVX0-9]+(?:\s.*)?$', re.IGNORECASE),

    # Level 2 patterns (Items, Articles, Major Sections)
    'l2': [
        re.compile(r'(?i)^item\s+[0-9]+[A-Z]?\.?(?:\s.*)?$'),
        re.compile(r'(?i)^article\s+[IVX0-9]+(?:[\s\.].*)?$'),
        re.compile(r'(?i)^section\s+[0-9]+(?:\.[0-9]+)*(?:\s.*)?$')
    ],

    # Level 3 patterns (Major subsections)
    'l3': [
        re.compile(r'^[A-Z][A-Z\s\-\&]{5,}$'),
        re.compile(r'(?i)^(?:consolidated|combined)\s+[A-Z\s]+$'),
        re.compile(r'(?i)^management[A-Z\s]+(?:discussion|analysis)$'),
        re.compile(r'(?i)^notes?\s+to\s+[A-Z\s]+$'),
        re.compile(r'(?i)^selected\s+financial\s+data$'),
        re.compile(r'(?i)^supplementary\s+information$'),
        re.compile(r'(?i)^signatures?$'),
        re.compile(r'(?i)^exhibits?\s+and\s+financial\s+statement\s+schedules$')
    ]
}


class UnitType(Enum):
    POINT = 'pt'
    PIXEL = 'px'
    INCH = 'in'
    CM = 'cm'
    MM = 'mm'
    PERCENT = '%'
    EM = 'em'
    REM = 'rem'


@dataclass
class StyleUnit:
    """Represents a CSS measurement with original and normalized values
       The original value is what was parsed from the CSS string, while the normalized
       value is converted to a standard unit characters for display in the terminal.
    """
    value: float
    unit: UnitType

    def __init__(self, value: float, unit: Union[str, UnitType]):
        self.value = value
        self.unit = UnitType(unit) if isinstance(unit, str) else unit

    def to_chars(self, console_width: int) -> int:
        """Convert width to character count based on console width"""
        # Base conversion rates (at standard 80-char width)
        BASE_CONSOLE_WIDTH = 80  # standard width
        CHARS_PER_INCH = 12.3  # at standard width

        # Scale factor based on actual console width
        scale = console_width / BASE_CONSOLE_WIDTH

        # Handle percentage specifically
        if self.unit == UnitType.PERCENT:
            return round(console_width * (self.value / 100))

        # Convert to inches first
        inches = self._to_inches()

        # Convert to characters, scaling based on console width
        chars = round(inches * CHARS_PER_INCH * scale)

        return chars

    def _to_inches(self) -> float:
        """Convert any unit to inches"""
        conversions = {
            UnitType.INCH: 1.0,
            UnitType.POINT: 1 / 72,  # 72 points per inch
            UnitType.PIXEL: 1 / 96,  # 96 pixels per inch
            UnitType.CM: 0.393701,  # 1 cm = 0.393701 inches
            UnitType.MM: 0.0393701,  # 1 mm = 0.0393701 inches
            UnitType.EM: 1 / 6,  # Approximate, assumes 1em = 1/6 inch
            UnitType.REM: 1 / 6,  # Same as EM
            UnitType.PERCENT: 1.0  # Handled separately in to_chars
        }
        return self.value * conversions[self.unit]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, StyleUnit):
            return NotImplemented
        if self.unit == other.unit:
            return self.value == other.value
        # Compare by converting both to inches
        return self._to_inches() == other._to_inches()

    def __gt__(self, other: Union['StyleUnit', float]) -> bool:
        if isinstance(other, float):
            # Assume points when comparing with raw numbers
            other = StyleUnit(other, UnitType.POINT)
        return self._to_inches() > other._to_inches()

    def __ge__(self, other: Union['StyleUnit', float]) -> bool:
        if isinstance(other, float):
            other = StyleUnit(other, UnitType.POINT)
        return self._to_inches() >= other._to_inches()

    def __str__(self) -> str:
        return f"{self.value}{self.unit.value}"

@dataclass
class Width:
    """Represents a width value with its unit"""
    value: float
    unit: UnitType

    def to_chars(self, console_width: int) -> int:
        """Convert width to character count based on console width"""
        # Base conversion rates (at standard 80-char width)
        BASE_CONSOLE_WIDTH = 80  # standard width
        CHARS_PER_INCH = 12.3  # at standard width

        # Scale factor based on actual console width
        scale = console_width / BASE_CONSOLE_WIDTH

        # Convert to inches first
        inches = self._to_inches()

        # Convert to characters, scaling based on console width
        chars = round(inches * CHARS_PER_INCH * scale)

        # Handle percentage
        if self.unit == '%':
            return round(console_width * (self.value / 100))

        return min(chars, console_width)

    def _to_inches(self) -> float:
        """Convert any unit to inches"""
        conversions = {
            'in': 1.0,
            'pt': 1 / 72,  # 72 points per inch
            'px': 1 / 96,  # 96 pixels per inch
            'cm': 0.393701,  # 1 cm = 0.393701 inches
            'mm': 0.0393701,  # 1 mm = 0.0393701 inches
            '%': 1.0  # percentage handled separately in to_chars
        }
        return self.value * conversions[self.unit]


@dataclass
class StyleInfo:
    """Style information with proper unit handling"""
    display: Optional[str] = None
    margin_top: Optional[StyleUnit] = None
    margin_bottom: Optional[StyleUnit] = None
    font_size: Optional[StyleUnit] = None
    font_weight: Optional[str] = None
    text_align: Optional[str] = None
    line_height: Optional[StyleUnit] = None
    width: Optional[StyleUnit] = None
    text_decoration: Optional[str] = None

    def merge(self, parent_style: Optional['StyleInfo']) -> 'StyleInfo':
        """Merge with parent style, child properties take precedence"""
        if not parent_style:
            return self

        return StyleInfo(
            display=self.display or parent_style.display,
            margin_top=self.margin_top or parent_style.margin_top,
            margin_bottom=self.margin_bottom or parent_style.margin_bottom,
            font_size=self.font_size or parent_style.font_size,
            font_weight=self.font_weight or parent_style.font_weight,
            text_align=self.text_align or parent_style.text_align,
            line_height=self.line_height or parent_style.line_height,
            width=self.width or parent_style.width,
            text_decoration=self.text_decoration or parent_style.text_decoration
        )


def parse_style(style_str: str) -> StyleInfo:
    """Parse inline CSS style string into StyleInfo object with robust unit validation"""
    style = StyleInfo()
    if not style_str:
        return style

    # Use UnitType enum for valid units
    valid_units = {unit.value for unit in UnitType}

    properties = [p.strip() for p in style_str.split(';') if p.strip()]
    for prop in properties:
        if ':' not in prop:
            continue

        key, value = prop.split(':', 1)
        key = key.strip().lower()
        value = value.strip().lower()

        # Handle non-numeric properties
        if key == 'font-weight':
            style.font_weight = value
            continue
        elif key == 'text-align':
            style.text_align = value
            continue
        elif key == 'display':
            style.display = value
            continue
        elif key == 'text-decoration':
            style.text_decoration = value
            continue

        # For properties that expect numeric values with units
        match = re.match(r'(-?\d*\.?\d+)([a-z%]*)', value)
        if match:
            try:
                num_val = float(match.group(1))
                unit = match.group(2) or 'px'  # Default to pixels

                # Validate the unit is supported
                if unit not in valid_units:
                    continue  # Skip this property if unit is invalid

                # Scientific notation check
                if 'e' in str(num_val).lower():
                    continue  # Skip scientific notation values

                style_unit = StyleUnit(num_val, unit)

                if key == 'margin-top':
                    style.margin_top = style_unit
                elif key == 'margin-bottom':
                    style.margin_bottom = style_unit
                elif key == 'font-size':
                    style.font_size = style_unit
                elif key == 'line-height':
                    style.line_height = style_unit
                elif key == 'width':
                    style.width = style_unit
            except (ValueError, TypeError):
                continue  # Skip this property if number parsing fails

    return style

def is_heading(element: Tag, style: StyleInfo) -> bool:
    """
    Detect if an element is likely a heading based on multiple weighted factors.
    Returns True if enough heading indicators are present.
    """
    if not style:
        return False

    # Initialize score and evidence
    score = 0
    max_score = 6

    # Get text content
    text = element.get_text(strip=True)
    if not text:
        return False

    debug_evidence = []

    # 1. Length checks - fail fast for long text
    if len(text) > 100:
        debug_evidence.append("-5 excessive length")
        score -= 5
        return False
    elif len(text) > 50:
        score -= 2
        debug_evidence.append("-2 for medium length")


    # Primary document structure patterns
    primary_patterns = [
            (r'(?i)^part\s+[IVX0-9]+(?:\s.*)?$', "PART pattern", 4),
            (r'(?i)^section\s+[0-9]+(?:\.[0-9]+)*(?:\s.*)?$', "SECTION pattern", 4),
            (r'(?i)^article\s+[IVX0-9]+(?:[\s\.].*)?$', "ARTICLE pattern", 4),
            (r'(?i)^item\s+[0-9]+[A-Z]?\.?(?:\s.*)?$', "ITEM pattern", 4),
    ]

    # Common SEC heading patterns
    sec_heading_patterns = [
            (r'(?i)^(?:consolidated|combined)\s+[A-Z\s]+$', "Financial statement heading", 3),
            (r'(?i)^management[A-Z\s]+(?:discussion|analysis)$', "MD&A heading", 3),
            (r'(?i)^notes?\s+to\s+[A-Z\s]+$', "Notes heading", 3),
            (r'(?i)^[A-Z][A-Z\s]{2,}\s+(?:and|of|to|for|from)\s+[A-Z\s]+$', "Complex heading", 3),
    ]

    # Secondary patterns
    secondary_patterns = [
            (r'^\d+\.\s*[A-Z].*$', "Numbered pattern", 3),
            (r'^[A-Z][A-Z\s\-\&]+$', "All caps text", 3),
    ]

    # Check patterns in order
    all_patterns = primary_patterns + sec_heading_patterns + secondary_patterns
    for pattern, desc, points in all_patterns:
        if re.match(pattern, text):
            score += points
            debug_evidence.append(f"+{points} for {desc}")
            break

    # 3. All caps bonus for short text
    if text.isupper() and len(text) <= 30 and not any(char.isdigit() for char in text):
        score += 1
        debug_evidence.append("+1 for short all-caps text")

    # 4. Style properties
    if style.font_weight in ['bold', '700', '800', '900']:
        points = 2 if len(text) < 30 else 1
        score += points
        debug_evidence.append(f"+{points} for bold weight")

    if style.font_size:
        base_size = StyleUnit(base_font_size, 'pt')
        size_ratio = style.font_size._to_inches() / base_size._to_inches()

        if size_ratio >= 1.2:
            score += 2
            debug_evidence.append(f"+2 for large font ({size_ratio:.1f}x base)")
        elif size_ratio >= 1.1:
            score += 1
            debug_evidence.append(f"+1 for medium font ({size_ratio:.1f}x base)")

    # Margin handling
    if style.margin_top:
        large_margin = StyleUnit(18, 'pt')
        medium_margin = StyleUnit(12, 'pt')

        if style.margin_top >= large_margin:
            score += 2
            debug_evidence.append(f"+2 for large margin ({style.margin_top.value}{style.margin_top.unit.value})")
        elif style.margin_top >= medium_margin:
            score += 2
            debug_evidence.append(f"+2 for medium margin ({style.margin_top.value}{style.margin_top.unit.value})")

    # Parent margin
    parent = element.parent
    if parent and isinstance(parent, Tag):
        parent_style = parse_style(parent.get('style', ''))
        if parent_style.margin_top:
            if parent_style.margin_top >= StyleUnit(18, 'pt'):
                score += 2
                debug_evidence.append("+2 for large parent margin")
            elif parent_style.margin_top >= StyleUnit(12, 'pt'):
                score += 1
                debug_evidence.append("+1 for medium parent margin")

    # Debug output
    print(f"\nHeading detection for: '{text[:50]}{'...' if len(text) > 50 else ''}'")
    print(f"Score: {score}/{max_score}")
    print("Evidence:", "\n  ".join([''] + debug_evidence))
    print(
            f"Style details: font_size={style.font_size}, font_weight={style.font_weight}, text_align={style.text_align}")

    return score >= max_score


def _get_effective_style(element: Tag, base_style: StyleInfo, debug: bool = False) -> StyleInfo:
    """Get combined styles with parent-first approach and semantic tag handling"""
    if debug:
        print("\nStyle Computation:")
        print(f"Base style: {_format_style_debug(base_style)}")
        print(f"Element: {element.name}")
        print(f"Element style attr: {element.get('style', 'None')}")

    # Start with base style
    effective_style = base_style or StyleInfo()

    # Get parent styles working up the tree
    for parent in element.parents:
        if parent.name == 'div':
            parent_style = parse_style(parent.get('style', ''))
            if debug:
                print(f"Parent {parent.name} style: {_format_style_debug(parent_style)}")
            if parent_style:
                effective_style = effective_style.merge(parent_style)
        # Stop at first div to avoid going too far up
        if parent.name == 'div':
            break

    # Get styles from span parents for font-size
    span_parent = element.find_parent('span')
    if span_parent:
        span_style = parse_style(span_parent.get('style', ''))
        if debug:
            print(f"Span parent style: {_format_style_debug(span_style)}")
        if span_style:
            effective_style = effective_style.merge(span_style)

    # Apply element's own style
    element_style = parse_style(element.get('style', ''))
    if element_style:
        effective_style = effective_style.merge(element_style)

    # Handle semantic bold tags
    if element.name in ['strong', 'b'] or element.find_parent(['strong', 'b']):
        effective_style = StyleInfo(
            font_weight='700',
            margin_top=effective_style.margin_top,
            margin_bottom=effective_style.margin_bottom,
            font_size=effective_style.font_size,
            text_align=effective_style.text_align,
            line_height=effective_style.line_height,
            width=effective_style.width,
            text_decoration=effective_style.text_decoration,
            display=effective_style.display
        )

    if debug:
        print(f"Final effective style: {_format_style_debug(effective_style)}")

    return effective_style

def _merge_styles(parent_style: StyleInfo, child_style: StyleInfo, debug: bool = False) -> StyleInfo:
    """
    Helper function to properly merge parent and child styles
    """
    if not parent_style:
        return child_style
    if not child_style:
        return parent_style

    merged = StyleInfo(
        display=child_style.display or parent_style.display,
        margin_top=child_style.margin_top or parent_style.margin_top,
        margin_bottom=child_style.margin_bottom or parent_style.margin_bottom,
        font_size=child_style.font_size or parent_style.font_size,
        font_weight=child_style.font_weight or parent_style.font_weight,
        text_align=child_style.text_align or parent_style.text_align,
        line_height=child_style.line_height or parent_style.line_height,
        width=child_style.width or parent_style.width,
        text_decoration=child_style.text_decoration or parent_style.text_decoration
    )

    if debug:
        logger.debug("Merged style: %s", _format_style_debug(merged))

    return merged


def get_heading_level(element: Tag, style: StyleInfo, text: str, debug: bool = False) -> Optional[int]:
    """Get heading level with comprehensive debugging"""
    debug_info: Dict[str, Any] = {'text': text, 'decisions': []}

    def log_decision(stage: str, result: bool, reason: str):
        if debug:
            print(f"{stage}: {'✓' if result else '✗'} - {reason}")
            debug_info['decisions'].append({
                'stage': stage,
                'result': result,
                'reason': reason
            })

    # Early return for empty or whitespace-only text
    if not text.strip():
        if debug:
            print("\nEmpty Content Check: Text is empty or whitespace-only")
        return None

    # Special handling for elements inside a div
    parent_div = element.find_parent('div')
    if parent_div:
        # Get all spans in the div
        spans = parent_div.find_all('span')
        if len(spans) > 1:  # Only process as split heading if multiple spans
            # Combine text from all spans
            combined_text = ' '.join(span.get_text(strip=True) for span in spans)
            if combined_text.strip():
                # Get div's style
                div_style = parse_style(parent_div.get('style', ''))
                # Check for bold styling in any span
                has_bold = any(
                    'font-weight' in span.get('style', '').lower() and
                    any(weight in span.get('style', '').lower()
                        for weight in ['bold', '700', '800', '900'])
                    for span in spans
                )
                if has_bold:
                    div_style = StyleInfo(
                        font_weight='700',
                        margin_top=div_style.margin_top,
                        font_size=div_style.font_size,
                        text_align=div_style.text_align,
                        display=div_style.display
                    )

                if debug:
                    print("\nProcessing split heading:")
                    print(f"Combined text: '{combined_text}'")
                    print(f"Has bold span: {has_bold}")

                # Process the combined heading
                return get_heading_level(parent_div, div_style, combined_text, debug)

    # Get complete style for the element
    complete_style = _get_effective_style(element, style, debug)
    if debug:
        print("\nStyle Analysis:")
        print(f"Text: '{text}'")
        print(f"Element: {element.name}")
        print(f"Complete style: {_format_style_debug(complete_style)}")

    # Check minimum heading traits
    has_min_traits, trait_details = _has_minimum_heading_traits(complete_style, text, return_details=True)
    if debug:
        print("\nHeading Traits:")
        for trait, value in trait_details.items():
            print(f"  {trait}: {value}")

    if not has_min_traits:
        log_decision("Style Check", False, "Does not meet minimum heading traits")
        return None

    log_decision("Style Check", True, "Meets minimum heading traits")
    text_to_check = text.strip()

    # First check prominence since it affects L3 pattern matching
    is_prominent = _is_prominently_styled(complete_style, debug=debug)

    # Level 1 check (PART headers)
    if debug:
        print(f"\nChecking Level 1 pattern against: '{text_to_check}'")
        print(f"Pattern: {HEADING_PATTERNS['l1'].pattern}")

    if HEADING_PATTERNS['l1'].match(text_to_check):
        log_decision("Pattern Check", True, "Matches Level 1 (PART) pattern")
        return 1

    # Level 2 check (Items, Articles)
    if debug:
        print("\nChecking Level 2 patterns:")
    for pattern in HEADING_PATTERNS['l2']:
        if debug:
            print(f"Testing pattern: {pattern.pattern}")
        if pattern.match(text_to_check):
            log_decision("Pattern Check", True, f"Matches Level 2 pattern: {pattern.pattern}")
            return 2

    # Level 3 check (requires prominence)
    if is_prominent:
        if debug:
            print("\nChecking Level 3 patterns (prominence check passed):")
        for pattern in HEADING_PATTERNS['l3']:
            if debug:
                print(f"Testing pattern: {pattern.pattern}")
            if pattern.match(text_to_check):
                log_decision("Pattern Check", True, f"Matches Level 3 pattern: {pattern.pattern}")
                return 3

        # Check if it's a likely section heading even if it doesn't match exact patterns
        if _is_likely_section_heading(text_to_check, complete_style):
            log_decision("Pattern Check", True, "Matches section heading criteria")
            return 3
    elif debug:
        print("\nSkipping Level 3 patterns (prominence check failed)")

    # Level 4 check (minor subsections)
    # Check for basic heading traits that didn't match higher level patterns
    if (text_to_check and  # Ensure there is non-empty text
            complete_style.font_weight in ['bold', '700', '800', '900'] and
            len(text_to_check) < 50 and
            not text_to_check.startswith(('Note:', '*', '(', '$')) and
            not text_to_check.endswith(':')):
        log_decision("Pattern Check", True, "Matches Level 4 (minor heading) criteria")
        return 4

    log_decision("Pattern Check", False, "No heading patterns matched")
    return None


def _format_style_debug(style: StyleInfo) -> Dict[str, str]:
    """Format style information for debugging"""
    if not style:
        return {"status": "no style"}

    return {
        "font_weight": str(style.font_weight),
        "font_size": str(style.font_size) if style.font_size else None,
        "margin_top": str(style.margin_top) if style.margin_top else None,
        "text_align": style.text_align,
        "display": style.display
    }


def _has_minimum_heading_traits(style: StyleInfo, text: str, return_details: bool = False) -> Union[
    bool, Tuple[bool, Dict[str, bool]]]:
    """
    Check for minimum heading characteristics with improved font-weight handling
    """
    if not style:
        return (False, {"reason": "no style"}) if return_details else False

    # Improved font-weight checking
    has_bold = False
    if style.font_weight:
        has_bold = (
                style.font_weight == 'bold' or
                style.font_weight == '700' or
                style.font_weight == '800' or
                style.font_weight == '900' or
                # Also handle possible numeric values
                (style.font_weight.isdigit() and int(style.font_weight) >= 700)
        )

    details = {
        "has_bold": has_bold,
        "has_large_font": bool(style.font_size and style.font_size > StyleUnit(11, 'pt')),
        "has_margin": bool(style.margin_top and style.margin_top >= StyleUnit(12, 'pt')),
        "has_center_caps": bool(style.text_align == 'center' and text.isupper() and len(text) > 4)
    }

    # Consider any combination of significant styling as valid
    result = details["has_bold"] or details["has_large_font"] or \
             (details["has_margin"] and (details["has_bold"] or details["has_center_caps"]))

    if return_details:
        return result, details
    return result


def _is_prominently_styled(style: StyleInfo, debug: bool = False) -> bool:
    """Check for prominent styling with detailed debug output"""
    if not style:
        if debug:
            print("No style provided to prominence check")
        return False

    prominence_checks = {
        "large_font": bool(style.font_size and style.font_size > StyleUnit(12, 'pt')),
        "large_margin": bool(style.margin_top and style.margin_top >= StyleUnit(18, 'pt')),
        "centered": style.text_align == 'center',
        "bold_with_margin": bool(style.font_weight in ('700', '800', '900', 'bold') and style.margin_top)
    }

    if debug:
        print("\nProminent Style Check:")
        for check, result in prominence_checks.items():
            print(f"  {check}: {result}")
            if result:
                print(f"    - {_get_prominence_detail(style, check)}")

    result = any(prominence_checks.values())
    if debug:
        print(f"Final prominence result: {result}")

    return result


def _get_prominence_detail(style: StyleInfo, check: str) -> str:
    """Get detailed information about why a prominence check passed"""
    if check == "large_font" and style.font_size:
        return f"Font size: {style.font_size}"
    elif check == "large_margin" and style.margin_top:
        return f"Margin top: {style.margin_top}"
    elif check == "centered":
        return f"Text align: {style.text_align}"
    elif check == "bold_with_margin":
        return f"Font weight: {style.font_weight}, Margin top: {style.margin_top}"
    return ""




def _is_likely_minor_heading(text: str, style: StyleInfo, return_details: bool = False) -> Union[
    bool, Tuple[bool, Dict[str, Any]]]:
    """Detect minor headings with detailed output"""
    details = {
        "length_ok": len(text) < 40,
        "has_bold": bool(style and style.font_weight in ('bold', '700')),
        "no_exclusions": not text.startswith(('Note:', '*', '(', '$')) and not text.endswith(':'),
        "text_sample": text[:30] + ('...' if len(text) > 30 else '')
    }

    result = all([details["length_ok"], details["has_bold"], details["no_exclusions"]])

    if return_details:
        return result, details
    return result


def _print_debug_info(debug_info: Dict[str, Any], debug: bool):
    """Print formatted debug information"""
    if not debug:
        return

    logger.debug("\nHeading Detection Analysis:")
    logger.debug("-" * 50)
    logger.debug(f"Text: '{debug_info['text']}'")
    logger.debug("\nStyle Information:")
    logger.debug(f"  {debug_info.get('effective_style', 'No style info')}")

    if 'style_traits' in debug_info:
        logger.debug("\nStyle Traits:")
        for trait, value in debug_info['style_traits'].items():
            logger.debug(f"  {trait}: {value}")

    logger.debug("\nDecision Process:")
    for decision in debug_info['decisions']:
        result_mark = "✓" if decision['result'] else "✗"
        logger.debug(f"  {result_mark} {decision['stage']}: {decision['reason']}")

    logger.debug("-" * 50)


def _is_likely_section_heading(text: str, style: StyleInfo) -> bool:
    """
    Check if text matches common SEC section heading patterns
    Uses heuristics based on common SEC document structure
    """
    # Skip common false positives
    if len(text) < 8 or len(text) > 60:
        return False

    text_lower = text.lower()

    # Common SEC section keywords
    section_keywords = {
        'overview', 'background', 'business', 'operations',
        'risk factors', 'management', 'financial', 'discussion',
        'analysis', 'results', 'liquidity', 'capital resources',
        'critical accounting', 'controls', 'procedures'
    }

    # Check for keyword matches
    words = set(text_lower.split())
    if len(words & section_keywords) >= 1:
        return True

    return False
