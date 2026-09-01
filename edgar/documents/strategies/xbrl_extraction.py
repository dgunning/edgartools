"""
XBRL extraction strategy for inline XBRL documents.
"""

import logging
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from lxml.etree import tostring
from lxml.html import HtmlElement

from edgar.documents.strategies.ixbrl_transforms import (
    TransformError,
    UnknownTransformError,
    apply_scale,
    apply_transform,
)
from edgar.documents.types import XBRLFact

logger = logging.getLogger(__name__)


class XBRLExtractor:
    """
    Extracts XBRL facts from inline XBRL (iXBRL) documents.

    Handles:
    - ix:nonFraction, ix:nonNumeric facts
    - Context and unit resolution
    - Continuation handling
    - Transformation rules

    Note on the tree this runs against: the caller parses with
    ``lxml.html.fromstring``, which does not process namespace declarations, so
    an element written ``<xbrli:context>`` has the literal tag
    ``"xbrli:context"`` and no namespace URI. Every lookup here therefore
    matches on the LOCAL NAME rather than using namespace-aware XPath, which
    silently returns nothing against such a tree. Do not "fix" these back to
    ``//xbrli:context``; switching the caller to an XML parser instead would
    change the tree for every other consumer of that pass.
    """

    # XBRL namespaces
    NAMESPACES = {
        'ix': 'http://www.xbrl.org/2013/inlineXBRL',
        'xbrli': 'http://www.xbrl.org/2003/instance',
        'xbrldi': 'http://xbrl.org/2006/xbrldi',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }

    # ix element types that carry a fact. ix:footnote and ix:continuation are
    # resources and are deliberately absent.
    FACT_TAGS = frozenset({'nonfraction', 'nonnumeric', 'fraction'})

    def __init__(self):
        """Initialize XBRL extractor."""
        self.contexts: Dict[str, Dict[str, Any]] = {}
        self.units: Dict[str, str] = {}
        self.continuations: Dict[str, HtmlElement] = {}
        self._initialized = False
        # Formats already reported, so a filing that uses an unsupported
        # transform 3,000 times warns once rather than 3,000 times.
        self._reported_formats: set = set()

    def extract_context(self, element: HtmlElement) -> Optional[Dict[str, Any]]:
        """
        Extract XBRL context from element.

        Args:
            element: HTML element that might contain XBRL

        Returns:
            XBRL metadata if found
        """
        # Check if element is an ix: tag
        if not self._is_xbrl_element(element):
            return None

        # Initialize context if needed
        if not self._initialized:
            self._initialize_context(element)

        # Extract based on element type
        tag_name = self._get_local_name(element.tag)

        if tag_name == 'nonfraction':
            return self._extract_nonfraction(element)
        elif tag_name == 'nonnumeric':
            return self._extract_nonnumeric(element)
        elif tag_name == 'continuation':
            return self._extract_continuation(element)
        elif tag_name == 'footnote':
            return self._extract_footnote(element)
        elif tag_name == 'fraction':
            return self._extract_fraction(element)

        return None

    def extract_fact(self, element: HtmlElement) -> Optional[XBRLFact]:
        """
        Extract XBRL fact from element.

        Only the element types that ARE facts produce one. ix:footnote and
        ix:continuation are resources: a footnote routed through here yielded a
        fact with no concept and no value, a non-fact injected into the fact
        list that corrupted counts and iteration, while a continuation's text
        belongs to the fact that references it.
        """
        if self._get_local_name(element.tag) not in self.FACT_TAGS:
            return None

        context = self.extract_context(element)
        if not context:
            return None

        # Get fact value
        value, issue = self._get_fact_value(element, escape=bool(context.get('escape')))

        # Create fact
        fact = XBRLFact(
            concept=context.get('name', ''),
            value=value,
            context_ref=context.get('contextRef'),
            unit_ref=context.get('unitRef'),
            decimals=context.get('decimals'),
            scale=context.get('scale'),
            format=context.get('format'),
            sign=context.get('sign'),
            escape=bool(context.get('escape')),
            continued_at=context.get('continuedAt')
        )

        # Resolve references
        if fact.context_ref and fact.context_ref in self.contexts:
            fact.context = self.contexts[fact.context_ref]

        if fact.unit_ref and fact.unit_ref in self.units:
            fact.unit = self.units[fact.unit_ref]

        if issue:
            fact.metadata = fact.metadata or {}
            fact.metadata['format_issue'] = issue

        return fact

    def _is_xbrl_element(self, element: HtmlElement) -> bool:
        """Check if element is an XBRL element."""
        tag = element.tag
        if not isinstance(tag, str):
            return False

        # Handle both namespaced and non-namespaced tags
        tag_lower = tag.lower()
        return (
            tag.startswith('{' + self.NAMESPACES['ix'] + '}') or
            tag.startswith('ix:') or
            tag_lower.startswith('ix:')
        )

    def _get_local_name(self, tag: Any) -> str:
        """Get local name from qualified tag."""
        if not isinstance(tag, str):
            # Comments and processing instructions carry a callable tag.
            return ''
        if '}' in tag:
            return tag.split('}')[1].lower()
        elif ':' in tag:
            return tag.split(':')[1].lower()
        return tag.lower()

    def _find_all(self, element: HtmlElement, local_name: str) -> List[HtmlElement]:
        """
        All descendants whose local name matches, prefix and namespace ignored.

        This is the literal-tag equivalent of ``.//xbrli:<local_name>``. See the
        class docstring for why namespace-aware XPath cannot be used here.
        """
        return [node for node in element.iter()
                if self._get_local_name(node.tag) == local_name]

    def _find_first(self, element: HtmlElement, local_name: str) -> Optional[HtmlElement]:
        """First descendant whose local name matches, or None."""
        for node in element.iter():
            if node is not element and self._get_local_name(node.tag) == local_name:
                return node
        return None

    def _initialize_context(self, element: HtmlElement):
        """Initialize context, unit and continuation information from document."""
        # Find root element
        root = element.getroottree().getroot()

        # One pass over the tree, bucketed by local name. Three separate
        # full-tree scans on a 20MB filing is the kind of cost that shows up.
        contexts, units, continuations = [], [], []
        for node in root.iter():
            local_name = self._get_local_name(node.tag)
            if local_name == 'context':
                contexts.append(node)
            elif local_name == 'unit':
                units.append(node)
            elif local_name == 'continuation':
                continuations.append(node)

        self._extract_contexts(contexts)
        self._extract_units(units)

        for node in continuations:
            cont_id = node.get('id')
            if cont_id:
                self.continuations.setdefault(cont_id, node)

        self._initialized = True

    def _extract_contexts(self, contexts: List[HtmlElement]):
        """Extract all context definitions."""
        for context in contexts:
            context_id = context.get('id')
            if not context_id:
                continue

            context_data = {
                'id': context_id
            }

            # Extract entity
            entity = self._find_first(context, 'entity')
            if entity is not None:
                identifier = self._find_first(entity, 'identifier')
                if identifier is not None:
                    context_data['entity'] = (identifier.text or '').strip()
                    context_data['scheme'] = identifier.get('scheme')

            # Extract period
            context_data.update(self._extract_period(context))

            # Extract dimensions
            dimensions = self._extract_dimensions(context)
            if dimensions:
                context_data['dimensions'] = dimensions

            self.contexts[context_id] = context_data

    def _extract_period(self, context: HtmlElement) -> Dict[str, Any]:
        """The instant or the start/end pair of a context's period."""
        period = self._find_first(context, 'period')
        if period is None:
            return {}

        instant = self._find_first(period, 'instant')
        if instant is not None:
            return {'instant': (instant.text or '').strip(), 'period_type': 'instant'}

        start = self._find_first(period, 'startdate')
        end = self._find_first(period, 'enddate')
        if start is not None and end is not None:
            return {
                'start_date': (start.text or '').strip(),
                'end_date': (end.text or '').strip(),
                'period_type': 'duration',
            }
        return {}

    def _extract_dimensions(self, context: HtmlElement) -> Dict[str, str]:
        """
        A context's dimensional members, keyed by axis.

        Members are carried in a segment or a scenario; the spec allows either
        and filers use both.
        """
        dimensions: Dict[str, str] = {}
        for container_name in ('segment', 'scenario'):
            container = self._find_first(context, container_name)
            if container is None:
                continue
            for member in self._find_all(container, 'explicitmember'):
                dim = member.get('dimension')
                if dim:
                    dimensions[dim] = (member.text or '').strip()
            for member in self._find_all(container, 'typedmember'):
                dim = member.get('dimension')
                if dim:
                    child = next((c for c in member if isinstance(c.tag, str)), None)
                    dimensions[dim] = (child.text or '').strip() if child is not None else ''
        return dimensions

    def _extract_units(self, units: List[HtmlElement]):
        """Extract all unit definitions."""
        for unit in units:
            unit_id = unit.get('id')
            if not unit_id:
                continue

            # A divide unit also contains measures, so it has to be checked
            # first or "USD per share" would resolve as plain "USD".
            divide = self._find_first(unit, 'divide')
            if divide is not None:
                numerator = self._find_first(divide, 'unitnumerator')
                denominator = self._find_first(divide, 'unitdenominator')
                num_measure = self._find_first(numerator, 'measure') if numerator is not None else None
                den_measure = self._find_first(denominator, 'measure') if denominator is not None else None

                if num_measure is not None and den_measure is not None:
                    num_unit = self._normalize_unit(num_measure.text)
                    den_unit = self._normalize_unit(den_measure.text)
                    self.units[unit_id] = f"{num_unit}/{den_unit}"
                    continue

            # Simple unit, or a measure-only <unit> with several measures.
            measures = self._find_all(unit, 'measure')
            if measures:
                self.units[unit_id] = '*'.join(
                    self._normalize_unit(measure.text) for measure in measures
                )

    def _normalize_unit(self, unit_text: str) -> str:
        """Normalize unit text."""
        if not unit_text:
            return ''

        unit_text = unit_text.strip()

        # Remove namespace prefix
        if ':' in unit_text:
            unit_text = unit_text.split(':')[-1]

        # Common normalizations
        unit_map = {
            'usd': 'USD',
            'shares': 'shares',
            'pure': 'pure',
            'percent': '%'
        }

        return unit_map.get(unit_text.lower(), unit_text)

    def _extract_nonfraction(self, element: HtmlElement) -> Dict[str, Any]:
        """Extract ix:nonFraction element."""
        metadata = {
            'type': 'nonFraction',
            'name': element.get('name'),
            'contextRef': element.get('contextRef') or element.get('contextref'),
            'unitRef': element.get('unitRef') or element.get('unitref'),
            'decimals': element.get('decimals'),
            'scale': element.get('scale'),
            'format': element.get('format'),
            'sign': element.get('sign')
        }

        # Clean None values
        return {k: v for k, v in metadata.items() if v is not None}

    def _extract_nonnumeric(self, element: HtmlElement) -> Dict[str, Any]:
        """Extract ix:nonNumeric element."""
        metadata = {
            'type': 'nonNumeric',
            'name': element.get('name'),
            'contextRef': element.get('contextRef') or element.get('contextref'),
            'format': element.get('format'),
            'escape': self._is_true(element.get('escape')),
            'continuedAt': element.get('continuedAt') or element.get('continuedat')
        }

        # Clean None values
        return {k: v for k, v in metadata.items() if v is not None}

    def _extract_continuation(self, element: HtmlElement) -> Dict[str, Any]:
        """
        Describe an ix:continuation element.

        This only reports what the element is. self.continuations maps an id to
        the continuation ELEMENT and is owned by _initialize_context, because
        resolving a chain needs the element itself to read its content from;
        writing a metadata dict in here would give that map two value types.
        """
        cont_id = element.get('id')
        continued_at = element.get('continuedAt') or element.get('continuedat')

        if not cont_id:
            return {}

        return {
            'type': 'continuation',
            'id': cont_id,
            'continuedAt': continued_at
        }

    def _extract_footnote(self, element: HtmlElement) -> Dict[str, Any]:
        """Extract ix:footnote element."""
        return {
            'type': 'footnote',
            'footnoteRole': element.get('footnoteRole'),
            'footnoteID': element.get('footnoteID')
        }

    def _extract_fraction(self, element: HtmlElement) -> Dict[str, Any]:
        """Extract ix:fraction element."""
        metadata = {
            'type': 'fraction',
            'name': element.get('name'),
            'contextRef': element.get('contextRef'),
            'unitRef': element.get('unitRef')
        }

        # Extract numerator and denominator
        numerator = element.find('.//ix:numerator', namespaces=self.NAMESPACES)
        denominator = element.find('.//ix:denominator', namespaces=self.NAMESPACES)

        if numerator is not None:
            metadata['numerator'] = numerator.text
        if denominator is not None:
            metadata['denominator'] = denominator.text

        return {k: v for k, v in metadata.items() if v is not None}

    @staticmethod
    def _is_true(attr_value: Optional[str]) -> bool:
        """Read an XML boolean attribute."""
        return (attr_value or '').strip().lower() in ('true', '1')

    def _collect_content(self, element: HtmlElement, parts: List[str], escape: bool):
        """
        Append an element's relevant content to ``parts``.

        Relevant content is the element's own text plus that of its descendants
        and their tails. An ``ix:exclude`` subtree contributes nothing, but the
        text FOLLOWING it does, which is the whole point of the construct: it
        marks up display-only material such as a currency symbol sitting inside
        the tagged span.

        With ``escape`` set, child markup is serialized rather than flattened,
        because the fact's value IS that markup (this is how ``*TextBlock``
        concepts carry a formatted disclosure).
        """
        parts.append(element.text or '')

        for child in element:
            if not isinstance(child.tag, str):
                # A comment or processing instruction contributes no content,
                # but the text after it still does.
                parts.append(child.tail or '')
                continue

            if self._get_local_name(child.tag) == 'exclude':
                parts.append(child.tail or '')
                continue

            if escape and not self._is_xbrl_element(child):
                # tostring() already includes the child's tail.
                parts.append(tostring(child, encoding='unicode', method='html'))
            else:
                # An ix: element is not XHTML, so escaped content unwraps it:
                # its own content contributes, its start and end tags do not.
                # Without this the value of a nested *TextBlock came back with
                # "<ix:nonnumeric ...>" wrappers embedded in the markup.
                self._collect_content(child, parts, escape)
                parts.append(child.tail or '')

    def _relevant_content(self, element: HtmlElement, escape: bool = False) -> str:
        """
        Build a fact's full relevant content, following its continuation chain.

        ``element.text`` — which this replaces — is only the text node before
        the element's first child, so descendant markup, tail text and the
        ix:continuation chain were all dropped and the truncated string looked
        like a complete value. continuedAt is how issuers split long narrative
        disclosures, so that truncation fell on exactly the text an LLM reads.
        """
        parts: List[str] = []
        self._collect_content(element, parts, escape)

        # Follow continuedAt to each ix:continuation in chain order. A filing
        # whose chain points back at itself must not spin here.
        seen = {element.get('id')} if element.get('id') else set()
        next_id = element.get('continuedAt') or element.get('continuedat')
        while next_id and next_id not in seen:
            seen.add(next_id)
            continuation = self.continuations.get(next_id)
            if continuation is None:
                logger.debug("iXBRL continuation %r referenced but not found", next_id)
                break
            # The whitespace between an origin element and its continuation
            # lives outside both, so concatenating strictly would glue the last
            # word of one to the first of the next. Escaped content is markup
            # and is joined verbatim.
            if not escape:
                parts.append(' ')
            self._collect_content(continuation, parts, escape)
            next_id = continuation.get('continuedAt') or continuation.get('continuedat')

        content = ''.join(parts)
        # Escaped content is markup: its whitespace is significant.
        return content if escape else ' '.join(content.split())

    def _get_fact_value(self, element: HtmlElement,
                        escape: bool = False) -> Tuple[str, Optional[str]]:
        """
        Get fact value from element with transformations.

        Returns the value and, when the declared format could not be applied, a
        short reason. The reason is recorded on the fact rather than dropped:
        an untransformed display string is indistinguishable from a real value
        once it is in the fact list, which is what made this failure invisible.
        """
        value = self._relevant_content(element, escape=escape)
        issue: Optional[str] = None

        # Apply format transformation if specified
        format_attr = element.get('format')
        if format_attr:
            try:
                value = apply_transform(format_attr, value)
            except UnknownTransformError:
                issue = f"unsupported format {format_attr}"
                self._report_format_issue(format_attr, issue)
            except TransformError as e:
                issue = f"format {format_attr} rejected the content: {e}"
                self._report_format_issue(format_attr, issue)

        # Apply scale if specified. Decimal, not float: the powers of ten this
        # attribute names are not representable in binary, and the error used
        # to be written back into the lexical value (0.006999999999999999 for a
        # filed 0.007), where numeric_value inherited it.
        scale = element.get('scale')
        if scale:
            scaled = apply_scale(value, scale)
            if scaled is not None:
                value = scaled

        # Apply sign if specified
        if element.get('sign') == '-' and value:
            try:
                value = f"{-Decimal(value):f}"
            except (InvalidOperation, ValueError):
                if not value.startswith('-'):
                    value = '-' + value

        return value.strip(), issue

    def _report_format_issue(self, format_attr: str, message: str):
        """Warn once per format, so a filing using one 3,000 times says so once."""
        if format_attr not in self._reported_formats:
            self._reported_formats.add(format_attr)
            logger.warning("Inline XBRL: %s; the raw display text is used instead", message)
