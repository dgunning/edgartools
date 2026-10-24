"""
Instance parser for XBRL documents.

This module handles parsing of XBRL instance documents including facts, contexts,
units, footnotes, and entity information extraction.
"""

import math
from datetime import datetime
from decimal import MAX_EMAX, MIN_EMIN, ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from decimal import Context as DecimalContext
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from lxml import etree as ET

from edgar.core import log
from edgar.xbrl.core import (
    INFINITE_PRECISION,
    NAMESPACES,
    classify_duration,
    duration_days,
    is_amendment_document_type,
    is_annual_document_type,
    is_quarterly_document_type,
)
from edgar.xbrl.models import Context, Fact, XBRLProcessingError
from edgar.xmltools import xml_parser

from .base import BaseParser

XLINK_NS = "{http://www.w3.org/1999/xlink}"
LINKBASE_NS = "{http://www.xbrl.org/2003/linkbase}"
XML_NS = "{http://www.w3.org/XML/1998/namespace}"

# Elements whose content is a block: a break belongs after them, or the last
# word of one runs into the first word of the next.
_BLOCK_ELEMENTS = frozenset({
    'address', 'article', 'blockquote', 'br', 'div', 'dd', 'dl', 'dt',
    'fieldset', 'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'header', 'hr', 'li', 'main', 'nav', 'ol', 'p', 'pre',
    'section', 'table', 'tbody', 'tfoot', 'thead', 'tr', 'ul',
})

# Cells sit side by side on one line, so they take a space rather than a break.
_CELL_ELEMENTS = frozenset({'td', 'th'})

XBRLI_NS = "{http://www.xbrl.org/2003/instance}"
XSI_NS = "{http://www.w3.org/2001/XMLSchema-instance}"

# The structural children of an instance root -- everything that is not a fact.
#
# These are FULLY QUALIFIED and compared by equality. Two copies of this set
# used to exist, and only one of them was right: the counting pass matched the
# half-qualified '}unit' while the extracting pass matched a bare 'unit' with
# str.endswith, so any concept whose local name merely ended in one of these
# words was dropped before its contextRef was ever read (gh #1293 --
# ctso:NumberOfSharesInAunit, the sole occurrence of that fact in the filing).
# A suffix test cannot tell a structural element from an issuer's concept;
# only the expanded name can.
_STRUCTURAL_ELEMENTS = frozenset({
    f"{XBRLI_NS}context",
    f"{XBRLI_NS}unit",
    f"{LINKBASE_NS}schemaRef",
    f"{LINKBASE_NS}roleRef",
    f"{LINKBASE_NS}arcroleRef",
    f"{LINKBASE_NS}linkbaseRef",
    f"{LINKBASE_NS}footnoteLink",
})

# Axes whose member names another legal entity: a DEI fact on one of them is a
# co-registrant's, not the filer's (GH #1420, #1710).
_ENTITY_AXES = ('dei:LegalEntityAxis', 'srt:ConsolidatedEntitiesAxis')

# xsi:nil is a boolean: true/false or 1/0.
_NIL_TRUE = frozenset({'true', '1'})


def _is_nil(element: ET.Element) -> bool:
    """Whether an element is marked ``xsi:nil``."""
    nil = element.get(f"{XSI_NS}nil")
    return isinstance(nil, str) and nil.strip().lower() in _NIL_TRUE


def _xbrli_child(element: ET.Element, local_name: str) -> Optional[ET.Element]:
    """The direct child in the XBRL instance namespace, if any."""
    tag = f"{XBRLI_NS}{local_name}"
    for child in element:
        if child.tag == tag:
            return child
    return None


def _significant_digits(text: str) -> int:
    """Significant digits in a decimal lexical form, at least one.

    Used only to size the division context. A non-decimal still returns a
    count; the division then fails and the caller keeps the slash form.
    """
    body = text.strip().lstrip('+-')
    exponent = body.lower().find('e')
    if exponent != -1:
        body = body[:exponent]
    body = body.replace('.', '', 1).lstrip('0')
    return max(len(body), 1)


def _format_decimal(value: Decimal) -> str:
    """Fixed-point form of an exact quotient, without a trailing ``.0``."""
    text = format(value, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    if text in ('', '-'):
        return '0'
    return text


def _decimal_context(prec: int) -> DecimalContext:
    """Division context that does not inherit the caller's settings.

    ``localcontext()`` with no argument copies the caller's rounding and
    exponent limits. ``ROUND_UP`` would change the last digit of 1/3,
    ``Emax=2`` overflows 1000/1, and ``Emin=-9`` underflows 10^-100 to zero.
    """
    return DecimalContext(
        prec=prec,
        rounding=ROUND_HALF_EVEN,
        Emin=MIN_EMIN,
        Emax=MAX_EMAX,
        traps=[],
        clamp=0,
    )


def _coefficient(value: Decimal) -> tuple[int, int]:
    """Integer coefficient and base-10 exponent of a finite ``Decimal``."""
    sign, digits, exponent = value.as_tuple()
    coefficient = 0
    for digit in digits:
        coefficient = coefficient * 10 + digit
    if sign:
        coefficient = -coefficient
    return coefficient, exponent


def _decimal_digit_count(number: int) -> int:
    """Decimal digits of a non-negative int, without converting it to a string.

    ``str`` of an int longer than the default 4300 digits raises ``ValueError``.
    ``1/2**6200`` has a 4334-digit significand, so that conversion cannot be
    the way the count is computed.
    """
    if number == 0:
        return 1
    # floor(log10(number)) + 1, from log2, then corrected against a power of
    # ten. The log uses this context so the caller's precision cannot move it.
    log_ctx = _decimal_context(50)
    log10_2 = log_ctx.divide(log_ctx.ln(Decimal(2)), log_ctx.ln(Decimal(10)))
    scaled = log_ctx.multiply(Decimal(number.bit_length() - 1), log10_2)
    estimate = int(scaled) + 1
    while 10 ** estimate <= number:
        estimate += 1
    while estimate > 1 and 10 ** (estimate - 1) > number:
        estimate -= 1
    return estimate


def _exact_terminating_digits(numerator: Decimal, denominator: Decimal) -> Optional[int]:
    """Significant digits of an exact quotient, or None when it does not terminate.

    A reduced fraction terminates exactly when the denominator is ``2^a * 5^b``.
    The digit count is the length of that significand after factors of ten are
    folded into the exponent.
    """
    numerator_coeff, numerator_exp = _coefficient(numerator)
    denominator_coeff, denominator_exp = _coefficient(denominator)
    numerator_coeff = abs(numerator_coeff)
    denominator_coeff = abs(denominator_coeff)
    if denominator_coeff == 0:
        return None
    common = math.gcd(numerator_coeff, denominator_coeff)
    numerator_coeff //= common
    denominator_coeff //= common
    shift = numerator_exp - denominator_exp
    if shift > 0:
        numerator_coeff *= 10 ** shift
    elif shift < 0:
        denominator_coeff *= 10 ** (-shift)
    common = math.gcd(numerator_coeff, denominator_coeff)
    numerator_coeff //= common
    denominator_coeff //= common
    twos = 0
    while denominator_coeff % 2 == 0:
        denominator_coeff //= 2
        twos += 1
    fives = 0
    while denominator_coeff % 5 == 0:
        denominator_coeff //= 5
        fives += 1
    if denominator_coeff != 1:
        return None
    coefficient = numerator_coeff
    coefficient *= 1 << max(fives - twos, 0)
    coefficient *= 5 ** max(twos - fives, 0)
    if coefficient == 0:
        return 1
    while coefficient % 10 == 0:
        coefficient //= 10
    return _decimal_digit_count(coefficient)


def _fraction_item(element: ET.Element) -> Optional[tuple[str, Optional[float], bool]]:
    """Read an ``xbrli:fractionItemType`` fact, or None when the element is not one.

    A fraction item has no text of its own. Its value is the numerator divided
    by the denominator (XBRL 2.1 §5.1.1.3.2), and its precision is INF (§4.6.6).
    Joining the children's text reads 1/3 as 13, because blank text between the
    two elements is removed before ``itertext()`` runs (GH #1766).

    The third item is True when the quotient is a finite decimal. The caller
    then sets ``decimals`` to INF even if the float conversion cannot represent
    that decimal. ``numeric_value`` is the float of the quotient. It is left
    unset only when that float overflows, or a nonzero quotient underflows to
    zero; the exact text stays in ``value``. A non-finite quotient
    (a zero denominator, or a non-decimal) leaves the numeric value unset and
    keeps the two parts separated by ``/``. A nil fact, or a nil numerator or
    denominator, is an absent value.

    A terminating quotient (denominator ``2^a * 5^b`` in lowest terms) is
    stored in full. ``1/2**100`` needs 70 significant digits; 50 would drop
    the tail and still be marked INF. A non-terminating quotient is rounded
    half-even to at least 50 significant digits, or to the operands' own
    digit count when that is larger. ``1/3`` is therefore fifty 3s, not an
    infinite expansion and not the ROUND_UP spelling that ends in 4.
    """
    numerator = _xbrli_child(element, 'numerator')
    denominator = _xbrli_child(element, 'denominator')
    if numerator is None or denominator is None:
        return None
    if _is_nil(element) or _is_nil(numerator) or _is_nil(denominator):
        return '', None, False
    # ``.text`` stops at a comment or processing instruction, so 1<!--c-->2
    # would be read as 1. The operand is the element's whole character content.
    num_text = ''.join(numerator.itertext()).strip()
    den_text = ''.join(denominator.itertext()).strip()
    if not num_text or not den_text:
        return '', None, False
    slash = f'{num_text}/{den_text}'
    try:
        # String construction is exact, so prec here does not round the
        # operands. The explicit context only shuts out the caller's traps
        # and exponent limits.
        with localcontext(_decimal_context(1)):
            numerator_value = Decimal(num_text)
            denominator_value = Decimal(den_text)
            invalid = (
                not numerator_value.is_finite()
                or not denominator_value.is_finite()
                or denominator_value.is_zero()
            )
        if invalid:
            return slash, None, False
        exact = _exact_terminating_digits(numerator_value, denominator_value)
        if exact is None:
            # Terminating quotients are exact; recurring ones are rounded half-even to 50 significant digits. decimals stays INF.
            prec = max(50, _significant_digits(num_text) + _significant_digits(den_text))
        else:
            prec = exact
        quotient = _decimal_context(prec).divide(numerator_value, denominator_value)
    except (InvalidOperation, ZeroDivisionError, ValueError, TypeError):
        return slash, None, False
    if not quotient.is_finite():
        return slash, None, False
    value = _format_decimal(quotient)
    numeric = float(quotient)
    if not math.isfinite(numeric) or (numeric == 0.0 and quotient != 0):
        return value, None, True
    return value, numeric, True


class InstanceParser(BaseParser):
    """Parser for XBRL instance documents."""

    def __init__(self, contexts: Dict[str, Context], facts: Dict[str, Fact],
                 units: Dict[str, Any], footnotes: Dict[str, Any],
                 calculation_trees: Dict[str, Any], entity_info: Dict[str, Any],
                 reporting_periods: List[Dict[str, Any]], context_period_map: Dict[str, str]):
        """
        Initialize instance parser with data structure references.

        Args:
            contexts: Reference to contexts dictionary
            facts: Reference to facts dictionary
            units: Reference to units dictionary
            footnotes: Reference to footnotes dictionary
            calculation_trees: Reference to calculation trees dictionary
            entity_info: Reference to entity info dictionary
            reporting_periods: Reference to reporting periods list
            context_period_map: Reference to context period map
        """
        super().__init__()

        # Store references to data structures
        self.contexts = contexts
        self.facts = facts
        self.units = units
        self.footnotes = footnotes
        self.calculation_trees = calculation_trees
        self.entity_info = entity_info
        self.reporting_periods = reporting_periods
        self.context_period_map = context_period_map

        # DEI facts extracted during entity info processing
        self.dei_facts: Dict[str, Fact] = {}

    def _create_normalized_fact_key(self, element_id: str, context_ref: str, instance_id: Optional[int] = None) -> str:
        """
        Create a normalized fact key using underscore format.

        Args:
            element_id: The element ID
            context_ref: The context reference
            instance_id: Optional instance ID for duplicate facts

        Returns:
            Normalized key in format: element_id|context_ref[|instance_id]

        The parts are joined with '|' because it cannot occur in either of
        them: a context ref is an NCName and an element ID is a QName, and
        neither production admits it. Joining with '_' did (gh #1295), because
        '_' is legal *inside* an NCName. A filer that names its quarterly
        contexts 'D20250630_1' alongside year-to-date 'D20250630' -- a common
        filer-agent convention -- collided the two identities

            (element, 'D20250630_1', no duplicate index)
            (element, 'D20250630',   duplicate index 1)

        on one key, and ``facts_dict[key] = fact`` silently dropped whichever
        arrived first. In ClearOne 0001753926-25-001345 that lost 6 of 590
        facts, including the quarter's revenue and net income, leaving only
        the six-month figures behind.

        The element ID keeps its ':' -> '_' rewrite: it is what lets a caller
        holding the underscore spelling find a fact stored under the colon
        one, which ``XBRL.element_context_index`` relies on. That rewrite is
        itself ambiguous for a prefix containing '_' (no such filing is known,
        and removing it would break those lookups), so it is left alone here.
        """
        normalized_element_id = element_id
        if ':' in element_id:
            prefix, name = element_id.split(':', 1)
            normalized_element_id = f"{prefix}_{name}"
        if instance_id is not None:
            return f"{normalized_element_id}|{context_ref}|{instance_id}"
        return f"{normalized_element_id}|{context_ref}"

    def parse_instance(self, file_path: Union[str, Path]) -> None:
        """Parse instance document file and extract contexts, facts, and units."""
        try:
            content = Path(file_path).read_text()
            self.parse_instance_content(content)
        except Exception as e:
            raise XBRLProcessingError(f"Error parsing instance file {file_path}: {str(e)}") from e

    def parse_instance_content(self, content: str) -> None:
        """Parse instance document content and extract contexts, facts, and units."""
        try:
            # Use lxml's optimized parser with smart string handling and recovery mode
            parser = xml_parser(remove_blank_text=True, recover=True, huge_tree=True)

            # Convert to bytes for faster parsing if not already
            if isinstance(content, str):
                content_bytes = content.encode('utf-8')
            else:
                content_bytes = content

            # Parse content with optimized settings
            root = ET.XML(content_bytes, parser)

            # Extract data in optimal order (contexts first, then units, then facts)
            # This ensures dependencies are resolved before they're needed
            self._extract_contexts(root)
            self._extract_units(root)
            self._extract_facts(root)
            self._extract_footnotes(root)

            # Post-processing steps after all raw data is extracted
            self._extract_entity_info()
            self._build_reporting_periods()

        except Exception as e:
            raise XBRLProcessingError(f"Error parsing instance content: {str(e)}") from e

    def count_facts(self, content: str) -> tuple:
        """Count the number of facts in the instance document
        This function counts both unique facts and total fact instances in the XBRL document.

        Returns:
            tuple: (unique_facts_count, total_fact_instances)
        """

        # Use lxml's optimized parser with smart string handling and recovery mode
        parser = xml_parser(remove_blank_text=True, recover=True, huge_tree=True)

        # Convert to bytes for faster parsing if not already
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content

        # Parse content with optimized settings
        root = ET.XML(content_bytes, parser)

        # Namespace -> prefix, and prefix -> namespace, so two namespaces are
        # never counted as one concept
        counted_prefixes = {}
        counted_claims = {}

        # Track both total instances and unique facts
        total_fact_instances = 0  # Total number of fact references in the document
        unique_facts = set()      # Set of unique element_id + context_ref combinations
        create_key = self._create_normalized_fact_key

        # Define counting function
        def count_element(element):
            """Process a single element as a potential fact."""
            nonlocal total_fact_instances

            # Skip known non-fact elements
            tag = element.tag
            if tag in _STRUCTURAL_ELEMENTS:
                return

            # Get context reference - key check to identify facts
            context_ref = element.get('contextRef')
            if context_ref is None:
                return

            # Extract element namespace and name - optimized split
            if '}' in tag:
                namespace, element_name = tag.split('}', 1)
                namespace = namespace[1:]  # Faster than strip('{')
            else:
                element_name = tag
                namespace = None

            # Get namespace prefix - cached for performance
            prefix = None
            for std_prefix, std_uri_base in NAMESPACES.items():
                if namespace.startswith(std_uri_base):
                    prefix = std_prefix
                    break

            if not prefix and namespace:
                prefix = counted_prefixes.get(namespace) or self._resolve_prefix(
                    namespace, element, counted_prefixes, counted_claims)

            # Construct element ID with optimized string concatenation
            if prefix:
                element_id = f"{prefix}:{element_name}" if prefix else element_name
            else:
                element_id = element_name

            # Create a normalized key using underscore format for consistency
            normalized_key = create_key(element_id, context_ref)

            # Track unique facts
            unique_facts.add(normalized_key)

            # Increment total instances count
            total_fact_instances += 1

        # Optimize traversal using lxml's iterchildren and iterdescendants if available
        if hasattr(root, 'iterchildren'):
            # Use lxml's optimized traversal methods
            for child in root.iterchildren():
                count_element(child)
                # Process nested elements with optimized iteration
                for descendant in child.iterdescendants():
                    count_element(descendant)
        else:
            # Fallback for ElementTree
            for child in root:
                count_element(child)
                for descendant in child.findall('.//*'):
                    count_element(descendant)

        # Return tuple of counts (unique_facts_count, total_fact_instances)
        return len(unique_facts), total_fact_instances

    def _extract_contexts(self, root: ET.Element) -> None:
        """Extract contexts from instance document."""
        try:
            # Find all context elements
            for context_elem in root.findall('.//{http://www.xbrl.org/2003/instance}context'):
                context_id = context_elem.get('id')
                if not context_id:
                    continue

                # Create context object
                context = Context(context_id=context_id)

                # Extract entity information
                entity_elem = context_elem.find('.//{http://www.xbrl.org/2003/instance}entity')
                if entity_elem is not None:
                    # Get identifier
                    identifier_elem = entity_elem.find('.//{http://www.xbrl.org/2003/instance}identifier')
                    if identifier_elem is not None:
                        scheme = identifier_elem.get('scheme', '')
                        identifier = identifier_elem.text
                        context.entity = {
                            'scheme': scheme,
                            'identifier': identifier
                        }

                    # Get segment dimensions if present
                    segment_elem = entity_elem.find('.//{http://www.xbrl.org/2003/instance}segment')
                    if segment_elem is not None:
                        self._read_dimension_members(segment_elem, context.dimensions)

                # Dimensions may also sit in the context's scenario (XBRL Dimensions 1.0 §3.1.4.1);
                # without them a scenario-qualified fact reads as the undimensioned total.
                scenario_elem = context_elem.find('{http://www.xbrl.org/2003/instance}scenario')
                if scenario_elem is not None:
                    self._read_dimension_members(scenario_elem, context.dimensions)

                # Extract period information
                period_elem = context_elem.find('.//{http://www.xbrl.org/2003/instance}period')
                if period_elem is not None:
                    # Check for instant period
                    instant_elem = period_elem.find('.//{http://www.xbrl.org/2003/instance}instant')
                    if instant_elem is not None and instant_elem.text:
                        context.period = {
                            'type': 'instant',
                            'instant': instant_elem.text
                        }

                    # Check for duration period
                    start_elem = period_elem.find('.//{http://www.xbrl.org/2003/instance}startDate')
                    end_elem = period_elem.find('.//{http://www.xbrl.org/2003/instance}endDate')
                    if start_elem is not None and end_elem is not None and start_elem.text and end_elem.text:
                        context.period = {
                            'type': 'duration',
                            'startDate': start_elem.text,
                            'endDate': end_elem.text
                        }

                    # Check for forever period
                    forever_elem = period_elem.find('.//{http://www.xbrl.org/2003/instance}forever')
                    if forever_elem is not None:
                        context.period = {
                            'type': 'forever'
                        }

                # Add context to registry
                self.contexts[context_id] = context

        except Exception as e:
            raise XBRLProcessingError(f"Error extracting contexts: {str(e)}") from e

    @staticmethod
    def _read_dimension_members(container: ET.Element, dimensions: Dict[str, str]) -> None:
        """Read explicit and typed dimension members from a segment or scenario element."""
        for dim_elem in container.findall('.//{http://xbrl.org/2006/xbrldi}explicitMember'):
            dimension = dim_elem.get('dimension')
            value = dim_elem.text
            if dimension and value:
                dimensions[dimension] = value

        for dim_elem in container.findall('.//{http://xbrl.org/2006/xbrldi}typedMember'):
            dimension = dim_elem.get('dimension')
            if dimension:
                # The typed dimension value is the text content of the first child element
                for child in dim_elem:
                    if child.text and child.text.strip():
                        dimensions[dimension] = child.text.strip()
                    else:
                        # Fallback to tag if no text content
                        dimensions[dimension] = child.tag
                    break

    def _extract_units(self, root: ET.Element) -> None:
        """Extract units from instance document."""
        try:
            # Find all unit elements
            for unit_elem in root.findall('.//{http://www.xbrl.org/2003/instance}unit'):
                unit_id = unit_elem.get('id')
                if not unit_id:
                    continue

                # Check for divide FIRST. A divided unit necessarily contains
                # measures of its own, inside unitNumerator and unitDenominator,
                # so the descendant `.//measure` search below matches the
                # numerator and would record `usdPerShare` as plain USD with the
                # denominator discarded -- making a per-share amount
                # indistinguishable from a dollar amount, and leaving this
                # branch unreachable for any well-formed divided unit
                # (edgartools-uetp).
                divide_elem = unit_elem.find('.//{http://www.xbrl.org/2003/instance}divide')
                if divide_elem is None:
                    # A simple unit's measure is a CHILD of xbrli:unit per the
                    # spec, so a direct-child search is the precise test; the
                    # descendant search is kept as a fallback for filings that
                    # nest it, which is safe now that divide is handled above.
                    measure_elem = unit_elem.find('{http://www.xbrl.org/2003/instance}measure')
                    if measure_elem is None:
                        measure_elem = unit_elem.find('.//{http://www.xbrl.org/2003/instance}measure')
                    # Strip: a pretty-printed <measure> carries whitespace that
                    # breaks every iso4217: prefix test downstream (GH #1704).
                    measure_text = (measure_elem.text or '').strip() if measure_elem is not None else ''
                    if measure_text:
                        self.units[unit_id] = {
                            'type': 'simple',
                            'measure': measure_text
                        }
                    continue

                if divide_elem is not None:
                    # Get numerator
                    numerator_elem = divide_elem.find('.//{http://www.xbrl.org/2003/instance}unitNumerator')
                    denominator_elem = divide_elem.find('.//{http://www.xbrl.org/2003/instance}unitDenominator')

                    if numerator_elem is not None and denominator_elem is not None:
                        # Get measures
                        numerator_measures = [elem.text.strip() for elem in numerator_elem.findall('.//{http://www.xbrl.org/2003/instance}measure') if elem.text and elem.text.strip()]
                        denominator_measures = [elem.text.strip() for elem in denominator_elem.findall('.//{http://www.xbrl.org/2003/instance}measure') if elem.text and elem.text.strip()]

                        self.units[unit_id] = {
                            'type': 'divide',
                            'numerator': numerator_measures,
                            'denominator': denominator_measures
                        }

        except Exception as e:
            raise XBRLProcessingError(f"Error extracting units: {str(e)}") from e

    def _resolve_prefix(self, namespace: str, element,
                        prefix_map: Dict[str, str],
                        claimed: Dict[str, str]) -> str:
        """
        The prefix for a namespace, resolved so that distinct namespaces keep
        distinct identities.

        The expanded name — namespace URI plus local name — is what identifies a
        concept; the prefix is a display choice. Deriving the prefix from the
        URI's final path segment made that display choice load-bearing, and two
        taxonomies whose URIs end in the same segment (.../alpha/2024 and
        .../beta/2024) collapsed into one concept string.

        Two things prevent that. A namespace declared on the fact element rather
        than the instance root is read from the element's own in-scope
        declarations, which is where its real prefix is. Where no prefix is
        declared at all and the URI segment must be used, a segment already
        claimed by a different namespace is suffixed rather than shared.

        The result is cached in prefix_map, so an unknown namespace is resolved
        once per document.
        """
        prefix = None

        # The prefix the document itself declares, wherever it declares it
        nsmap = getattr(element, 'nsmap', None)
        if nsmap:
            for declared_prefix, declared_uri in nsmap.items():
                if declared_uri == namespace and declared_prefix:
                    prefix = declared_prefix
                    break

        if not prefix:
            # Nothing declared: fall back to the URI's final path segment
            parts = namespace.rstrip('/').split('/')
            prefix = parts[-1] if parts and parts[-1] else namespace

        # Never let two namespaces share one prefix
        if claimed.get(prefix) not in (None, namespace):
            base, suffix = prefix, 2
            while claimed.get(f"{base}_{suffix}") not in (None, namespace):
                suffix += 1
            prefix = f"{base}_{suffix}"

        claimed[prefix] = namespace
        prefix_map[namespace] = prefix
        return prefix

    def _extract_facts(self, root: ET.Element) -> None:
        """Extract facts from instance document."""
        try:
            # Get direct access to nsmap if using lxml (much faster than regex extraction)
            if hasattr(root, 'nsmap'):
                # Leverage lxml's native nsmap functionality
                prefix_map = {uri: prefix for prefix, uri in root.nsmap.items() if prefix is not None}
            else:
                # Fallback for ElementTree - precompile regex patterns for namespace extraction
                xmlns_pattern = '{http://www.w3.org/2000/xmlns/}'
                prefix_map = {}

                # Extract namespace declarations from root
                for attr_name, attr_value in root.attrib.items():
                    if attr_name.startswith(xmlns_pattern) or attr_name.startswith('xmlns:'):
                        # Extract the prefix more efficiently
                        if attr_name.startswith(xmlns_pattern):
                            prefix = attr_name[len(xmlns_pattern):]
                        else:
                            prefix = attr_name.split(':', 1)[1]
                        prefix_map[attr_value] = prefix

            # prefix -> namespace, so a prefix is never shared by two namespaces
            claimed_prefixes = {prefix: uri for uri, prefix in prefix_map.items()}

            # Initialize counters and tracking
            fact_count = 0
            facts_dict = {}
            base_keys = {}

            def process_element(element):
                """Process a single element as a potential fact."""
                nonlocal fact_count

                # Skip annotation nodes and other non element nodes
                if not ET.iselement(element):
                    return
                # Skip known non-fact elements - faster check with set membership
                # If the tag is not a string, try calling () to get the string value (in rare cases)
                if callable(element.tag):
                    if isinstance(element, ET._Comment):
                        return
                    if not element.values():
                        return
                tag = element.tag
                if tag in _STRUCTURAL_ELEMENTS:
                    return

                # Get context reference - key check to identify facts
                context_ref = element.get('contextRef')
                if not context_ref:
                    return

                # Get fact ID if present (for footnote linkage)
                fact_id = element.get('id')

                # Extract element namespace and name - optimized split
                if '}' in tag:
                    namespace, element_name = tag.split('}', 1)
                    namespace = namespace[1:]  # Faster than strip('{')

                    # Try to extract prefix from the namespace
                    prefix = prefix_map.get(namespace)
                    if not prefix:
                        prefix = self._resolve_prefix(
                            namespace, element, prefix_map, claimed_prefixes)
                else:
                    element_name = tag
                    prefix = ''

                # Construct element ID with optimized string concatenation
                element_id = f"{prefix}:{element_name}" if prefix else element_name

                # Get unit reference
                unit_ref = element.get('unitRef')

                # Get decimals attribute - direct access
                decimals = element.get('decimals')

                # A fraction item's value is numerator / denominator and its
                # precision is INF (XBRL 2.1 §5.1.1.3.2, §4.6.6). It has no
                # text node of its own, so the itertext() fallback would
                # concatenate the two children (GH #1766: 1/3 was read as 13).
                # The children's tags are the type signal the element catalog
                # would have given, so this does not depend on unitRef the way
                # a plain numeric fact does.
                fraction = _fraction_item(element)
                if fraction is not None:
                    value, numeric_value, evaluated = fraction
                    # INF is the fraction's precision (§4.6.6), including when
                    # the quotient does not fit in a float. A nil or non-finite
                    # fraction did not evaluate, so its decimals stay as filed.
                    if evaluated:
                        decimals = INFINITE_PRECISION
                else:
                    # Get value - optimize string handling
                    value = element.text
                    if not value or not value.strip():
                        # Collect all nested text (handles HTML content in TextBlock elements)
                        all_text = "".join(element.itertext()).strip()
                        if all_text:
                            value = all_text

                    # Optimize string handling - inline conditional
                    value = value.strip() if value else ""

                    # Optimize numeric conversion with faster try/except.
                    #
                    # A unitRef is what makes a fact numeric. XBRL requires one on
                    # every numeric item and forbids one on non-numeric items, so
                    # its presence is an exact test here, where the element catalog
                    # (and with it the declared type) is not reachable.
                    #
                    # Without the check, float() succeeded on anything that merely
                    # looked like a number, so unitless metadata carried a
                    # numeric_value: dei:DocumentFiscalYearFocus is a gYear, and a
                    # query for facts valued near 2023 returned the fiscal-year
                    # focus alongside real monetary facts. numeric_value is the
                    # field consumers read as "this is a numeric fact", so every
                    # one of them inherited the misclassification (gh #1220).
                    numeric_value = None
                    if value and unit_ref:
                        try:
                            numeric_value = float(value)
                        except (ValueError, TypeError):
                            pass

                # Create base key for duplicate detection
                base_key = self._create_normalized_fact_key(element_id, context_ref)

                # Handle duplicates
                instance_id = None
                if base_key in base_keys:
                    # This is a duplicate - convert existing fact to use instance_id if needed
                    if base_key in facts_dict:
                        existing_fact = facts_dict[base_key]
                        # Move existing fact to new key with instance_id=0
                        del facts_dict[base_key]
                        existing_fact.instance_id = 0
                        facts_dict[self._create_normalized_fact_key(element_id, context_ref, 0)] = existing_fact
                    # Add new fact with next instance_id
                    instance_id = len(base_keys[base_key])
                    base_keys[base_key].append(True)
                else:
                    # First instance of this fact
                    base_keys[base_key] = [True]

                # Create fact object
                fact = Fact(
                    element_id=element_id,
                    context_ref=context_ref,
                    value=value,
                    unit_ref=unit_ref,
                    decimals=decimals,
                    numeric_value=numeric_value,
                    instance_id=instance_id,
                    fact_id=fact_id
                )

                # Store fact with appropriate key
                key = self._create_normalized_fact_key(element_id, context_ref, instance_id)
                facts_dict[key] = fact
                fact_count += 1

            # Use lxml's optimized traversal methods
            if hasattr(root, 'iterchildren'):
                # Use lxml's optimized traversal methods
                for child in root.iterchildren():
                    process_element(child)
                    # Process nested elements with optimized iteration
                    for descendant in child.iterdescendants():
                        process_element(descendant)
            else:
                # Fallback for ElementTree
                for child in root:
                    process_element(child)
                    for descendant in child.findall('.//*'):
                        process_element(descendant)

            # Update instance facts
            self.facts.update(facts_dict)

            log.debug(f"Extracted {fact_count} facts ({len(base_keys)} unique fact identifiers)")

        except Exception as e:
            raise XBRLProcessingError(f"Error extracting facts: {str(e)}") from e

    def _extract_footnotes(self, root: ET.Element) -> None:
        """Extract footnotes from instance document.

        A footnoteLink is an extended link, and everything in it resolves
        WITHIN it: `xlink:from` names a `link:loc` whose `xlink:href` fragment
        is the fact id, and `xlink:to` names a `link:footnote` in the same link.
        Two links may legitimately reuse a label, so resources are matched per
        link and only disambiguated in the store when they actually collide.
        """
        try:
            from edgar.xbrl.models import Footnote

            # Track undefined footnotes for deduplication
            undefined_footnotes = set()

            for footnote_link in root.findall(f'.//{LINKBASE_NS}footnoteLink'):
                # label -> the key this link's resource was stored under
                resources = {}
                for footnote_elem in footnote_link.findall(f'{LINKBASE_NS}footnote'):
                    # Prioritize xlink:label over id attribute for footnote identification.
                    # FootnoteArcs reference footnotes using xlink:to, which corresponds to xlink:label.
                    # In pre-2016 filings, these attributes often differ (e.g., xlink:label="lbl_footnote_0"
                    # vs id="FN_0"), so we must use xlink:label to match arc references correctly.
                    label = (footnote_elem.get(f'{XLINK_NS}label')
                             or footnote_elem.get('id'))
                    if not label:
                        continue

                    key = self._footnote_storage_key(label)
                    self.footnotes[key] = Footnote(
                        footnote_id=key,
                        text=self._footnote_text(footnote_elem),
                        lang=footnote_elem.get(f'{XML_NS}lang', 'en-US'),
                        role=footnote_elem.get(f'{XLINK_NS}role'),
                        related_fact_ids=[]
                    )
                    resources[label] = key

                # A locator's label is not the fact id; its href fragment is.
                locators = {
                    loc.get(f'{XLINK_NS}label'): (loc.get(f'{XLINK_NS}href') or '').split('#')[-1]
                    for loc in footnote_link.findall(f'{LINKBASE_NS}loc')
                }

                for arc_elem in footnote_link.findall(f'{LINKBASE_NS}footnoteArc'):
                    from_ref = arc_elem.get(f'{XLINK_NS}from')
                    to_ref = arc_elem.get(f'{XLINK_NS}to')
                    if not from_ref or not to_ref:
                        continue

                    # Fall back to the label when the arc names no locator —
                    # that is how this resolved for filings where it resolved.
                    fact_id = locators.get(from_ref) or from_ref
                    footnote_key = resources.get(to_ref)

                    if footnote_key is None:
                        # Track undefined footnote (common in older filings due
                        # to naming inconsistencies)
                        if to_ref not in undefined_footnotes:
                            undefined_footnotes.add(to_ref)
                            log.debug(f"Footnote arc references undefined footnote: {to_ref}")
                        continue

                    self.footnotes[footnote_key].related_fact_ids.append(fact_id)
                    self._attach_footnote_to_fact(fact_id, footnote_key)

            # Summary message for undefined footnotes (non-critical)
            if undefined_footnotes:
                log.debug(f"{len(undefined_footnotes)} footnote arc references could not be resolved (non-critical)")

            log.debug(f"Extracted {len(self.footnotes)} footnotes")

        except Exception as e:
            # Log the error but don't fail - footnotes are optional
            log.warning(f"Error extracting footnotes: {str(e)}")

    def _footnote_storage_key(self, label: str) -> str:
        """
        The key a footnote resource is stored under.

        Labels are unique within their own extended link, not across the
        document, so a label already taken by an earlier link is suffixed. The
        overwhelmingly common case is one link and no collision, where the key
        stays exactly the label.
        """
        if label not in self.footnotes:
            return label

        suffix = 2
        while f"{label}#{suffix}" in self.footnotes:
            suffix += 1
        return f"{label}#{suffix}"

    def _attach_footnote_to_fact(self, fact_id: str, footnote_key: str) -> None:
        """Record the footnote on the fact it annotates."""
        for fact in self.facts.values():
            if fact.fact_id == fact_id:
                if footnote_key not in fact.footnotes:
                    fact.footnotes.append(footnote_key)
                return

    def _footnote_text(self, footnote_elem) -> str:
        """
        The full text of a footnote resource, in document order.

        Reading only descendant `<div>`s dropped direct-child and sibling text
        and, because `findall('.//div')` returns nested divs alongside their
        ancestors while `itertext()` already descends, emitted nested text
        twice. One ordered walk visits every character exactly once, inserting a
        break after a block so the last word of one does not glue to the first
        word of the next.
        """
        parts: List[str] = []
        self._collect_footnote_text(footnote_elem, parts)

        lines = []
        for raw_line in ''.join(parts).split('\n'):
            line = ' '.join(raw_line.split())
            if line:
                lines.append(line)
        return '\n'.join(lines)

    def _collect_footnote_text(self, node, parts: List[str]) -> None:
        """Append this node's text, its children's, and their tails, in order."""
        if node.text:
            parts.append(node.text)

        for child in node:
            tag = child.tag
            name = tag.rsplit('}', 1)[-1].lower() if isinstance(tag, str) else ''

            self._collect_footnote_text(child, parts)

            if name in _BLOCK_ELEMENTS:
                parts.append('\n')
            elif name in _CELL_ELEMENTS:
                parts.append(' ')

            if child.tail:
                parts.append(child.tail)

    def _extract_entity_info(self) -> None:
        """Extract entity information from contexts and DEI facts."""
        try:
            # Extract CIK/identifier from first context
            identifier = None
            if self.contexts:
                first = next(iter(self.contexts.values()))
                ident = first.entity.get('identifier')
                if ident and ident.isdigit():
                    identifier = ident.lstrip('0')

            # Collect all DEI facts into a dict: concept -> Fact.
            #
            # A fact whose context has a dei:LegalEntityAxis member describes
            # another legal entity: in a combined filing, a co-registrant. The
            # filer's own cover facts carry no such member, so they win, and a
            # co-registrant's fact is used only for a concept the filer does not
            # report. Keeping whichever fact came last named Duke Energy's
            # combined 10-K after Piedmont Natural Gas, the last of its seven
            # co-registrants, beside Duke Energy's own CIK (GH #1420).
            # Lamar's combined 10-Q puts its co-registrant on
            # srt:ConsolidatedEntitiesAxis instead, so both entity axes count
            # (GH #1710). A class-of-stock member alone does not: it qualifies
            # the filer's own securities.
            self.dei_facts: Dict[str, Fact] = {}
            co_registrant_facts: Dict[str, Fact] = {}
            for fact in self.facts.values():
                eid = fact.element_id
                if eid.startswith('dei:'):
                    concept = eid.split(':', 1)[1]
                elif eid.startswith('dei_'):
                    concept = eid.split('_', 1)[1]
                else:
                    continue
                context = self.contexts.get(fact.context_ref)
                if context is not None and any(axis in context.dimensions for axis in _ENTITY_AXES):
                    co_registrant_facts[concept] = fact
                else:
                    self.dei_facts[concept] = fact
            for concept, fact in co_registrant_facts.items():
                self.dei_facts.setdefault(concept, fact)

            # Helper: get the first available DEI fact value
            def get_dei(*names):
                for n in names:
                    f = self.dei_facts.get(n)
                    if f:
                        return f.value
                return None

            # Build entity_info preserving existing keys
            self.entity_info.update({
                'entity_name':             get_dei('EntityRegistrantName'),
                'ticker':                  get_dei('TradingSymbol'),
                'identifier':              identifier,
                'document_type':           get_dei('DocumentType'),
                'reporting_end_date':      None,
                'document_period_end_date':get_dei('DocumentPeriodEndDate'),
                'fiscal_year':             get_dei('DocumentFiscalYearFocus','FiscalYearFocus','FiscalYear'),
                'fiscal_period':           get_dei('DocumentFiscalPeriodFocus','FiscalPeriodFocus'),
                'fiscal_year_end_month':   None,
                'fiscal_year_end_day':     None,
                'annual_report':           False,
                'quarterly_report':        False,
                'amendment':               False,
            })

            # Determine reporting_end_date from contexts
            for ctx in self.contexts.values():
                period = getattr(ctx, 'period', {})
                if period.get('type') == 'instant':
                    ds = period.get('instant')
                    if ds:
                        try:
                            dt_obj = datetime.strptime(ds, '%Y-%m-%d').date()
                            curr = self.entity_info['reporting_end_date']
                            if curr is None or dt_obj > curr:
                                self.entity_info['reporting_end_date'] = dt_obj
                        except Exception:
                            pass

            # Parse fiscal year end date into month/day
            fye = get_dei('CurrentFiscalYearEndDate','FiscalYearEnd')
            if fye:
                try:
                    s = fye
                    if s.startswith('--'):
                        s = s[2:]
                    if '-' in s:
                        m, d = s.split('-', 1)
                        if m.isdigit() and d.isdigit():
                            self.entity_info['fiscal_year_end_month'] = int(m)
                            self.entity_info['fiscal_year_end_day'] = int(d)
                except Exception:
                    pass

            # Flags based on document_type. An amended annual report is still
            # an annual report, so the suffix is stripped before classifying
            # rather than compared away (GH #1226).
            dt_val = self.entity_info['document_type'] or ''
            self.entity_info['annual_report']    = is_annual_document_type(dt_val)
            self.entity_info['quarterly_report'] = is_quarterly_document_type(dt_val)
            self.entity_info['amendment']        = is_amendment_document_type(dt_val)

            log.debug(f"Entity info: {self.entity_info}")
        except Exception as e:
            log.warning(f"Warning: Error extracting entity info: {str(e)}")

    def _build_reporting_periods(self) -> None:
        """Build reporting periods from contexts."""
        try:
            # Clear existing periods
            self.reporting_periods.clear()
            self.context_period_map.clear()

            # Collect unique periods from contexts
            instant_periods = {}
            duration_periods = {}

            for context_id, context in self.contexts.items():
                if 'period' in context.model_dump() and 'type' in context.period:
                    period_type = context.period.get('type')

                    if period_type == 'instant':
                        date_str = context.period.get('instant')
                        if date_str:
                            if date_str not in instant_periods:
                                instant_periods[date_str] = []

                            # Add context ID to this period
                            instant_periods[date_str].append(context_id)

                            # Map context to period key
                            period_key = f"instant_{date_str}"
                            self.context_period_map[context_id] = period_key

                    elif period_type == 'duration':
                        start_date = context.period.get('startDate')
                        end_date = context.period.get('endDate')
                        if start_date and end_date:
                            duration_key = f"{start_date}_{end_date}"
                            if duration_key not in duration_periods:
                                duration_periods[duration_key] = []

                            # Add context ID to this period
                            duration_periods[duration_key].append(context_id)

                            # Map context to period key
                            period_key = f"duration_{start_date}_{end_date}"
                            self.context_period_map[context_id] = period_key

            # Process instant periods
            for date_str, context_ids in instant_periods.items():
                try:
                    date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                    formatted_date = date_obj.strftime('%B %d, %Y')

                    period = {
                        'type': 'instant',
                        'date': date_str,
                        'date_obj': date_obj,
                        'label': formatted_date,
                        'context_ids': context_ids,
                        'key': f"instant_{date_str}"
                    }
                    self.reporting_periods.append(period)
                except (ValueError, TypeError):
                    # Skip invalid dates
                    continue

            # Process duration periods
            for period_key, context_ids in duration_periods.items():
                start_date, end_date = period_key.split('_')
                try:
                    start_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                    formatted_start = start_obj.strftime('%B %d, %Y')
                    formatted_end = end_obj.strftime('%B %d, %Y')

                    # Both endpoints belong to the period: a date-only endDate
                    # runs to 24:00 on that day (issue #1247).
                    days = duration_days(start_obj, end_obj)

                    # Determine period type based on duration
                    period_description = classify_duration(days)

                    period = {
                        'type': 'duration',
                        'start_date': start_date,
                        'end_date': end_date,
                        'start_obj': start_obj,
                        'end_obj': end_obj,
                        'days': days,
                        'period_type': period_description,
                        'label': f"{period_description}: {formatted_start} to {formatted_end}",
                        'context_ids': context_ids,
                        'key': f"duration_{start_date}_{end_date}"
                    }
                    self.reporting_periods.append(period)
                except (ValueError, TypeError):
                    # Skip invalid dates
                    continue

            # Sort periods by date (most recent first)
            self.reporting_periods.sort(key=lambda p: p['date_obj'] if p['type'] == 'instant' else p['end_obj'], reverse=True)

            # Enrich periods with fiscal year and fiscal period info
            self._enrich_periods_with_fiscal_info()

            # Debug printout to verify periods are extracted
            if len(self.reporting_periods) > 0:
                log.debug(f"Found {len(self.reporting_periods)} reporting periods.")
                log.debug(f"First period: {self.reporting_periods[0]['label']}")
            else:
                log.debug("Warning: No reporting periods found!")

            # Debug context period map
            log.debug(f"Context period map has {len(self.context_period_map)} entries.")

        except Exception as e:
            # Log error but don't fail
            log.debug(f"Warning: Error building reporting periods: {str(e)}")
            self.reporting_periods.clear()

    def _enrich_periods_with_fiscal_info(self):
        """Add fiscal_year and fiscal_period fields to reporting periods.

        Derives fiscal year and period (FY, Q1-Q4) from period dates
        and the entity's fiscal year end information.
        """
        fy_end_month = self.entity_info.get('fiscal_year_end_month')
        fy_end_day = self.entity_info.get('fiscal_year_end_day')

        if fy_end_month is None or fy_end_day is None:
            # Default to calendar year (Dec 31) if not available
            fy_end_month = 12
            fy_end_day = 31

        for period in self.reporting_periods:
            if period['type'] == 'duration':
                end_obj = period['end_obj']
                days = period['days']

                period['fiscal_year'] = _fiscal_year_for_date(end_obj, fy_end_month, fy_end_day)

                # Classify fiscal period from duration length
                if 350 <= days <= 380:
                    period['fiscal_period'] = 'FY'
                elif 260 <= days <= 290:
                    period['fiscal_period'] = 'YTD9'  # 9-month YTD (Q3 10-Q)
                elif 170 <= days <= 200:
                    period['fiscal_period'] = 'YTD6'  # 6-month YTD (Q2 10-Q)
                elif 85 <= days <= 95:
                    period['fiscal_period'] = _quarter_for_date(end_obj, fy_end_month)

            elif period['type'] == 'instant':
                date_obj = period['date_obj']
                period['fiscal_year'] = _fiscal_year_for_date(date_obj, fy_end_month, fy_end_day)


def _fiscal_year_for_date(d, fy_end_month: int, fy_end_day: int) -> int:
    """Determine the fiscal year a date belongs to.

    The fiscal year is named by the calendar year in which it ends.
    For example, AAPL's fiscal year ending Sep 2024 is FY2024.
    A date in Dec 2024 (after Sep end) belongs to FY2025.
    """
    import calendar
    # Build the fiscal year end date for the same calendar year as d
    # Clamp the day to the max valid day for that month
    max_day = calendar.monthrange(d.year, fy_end_month)[1]
    fy_end_date = d.replace(month=fy_end_month, day=min(fy_end_day, max_day))

    if d > fy_end_date:
        return d.year + 1
    return d.year


def _quarter_for_date(end_date, fy_end_month: int) -> str:
    """Determine the fiscal quarter (Q1-Q4) for a quarterly period end date.

    Quarters are counted from the start of the fiscal year.
    For AAPL (FY end Sep): Q1=Oct-Dec, Q2=Jan-Mar, Q3=Apr-Jun, Q4=Jul-Sep.

    52/53-week filers (JNJ, PFE, AAPL, COST, etc.) pin quarter ends to a
    weekday (e.g. Sunday nearest Jun 30), so the end_date can drift into the
    first few days of the following calendar month — e.g. JNJ Q2 2023 ended
    2023-07-02. A first-of-month classification puts those facts in the wrong
    quarter (GH #816). Normalize by treating end dates in the first week of a
    month as belonging to the previous month for quarter classification.
    """
    classification_month = end_date.month
    if end_date.day <= 7:
        classification_month = 12 if classification_month == 1 else classification_month - 1
    month_offset = (classification_month - fy_end_month - 1) % 12
    quarter = (month_offset // 3) + 1
    return f"Q{quarter}"
