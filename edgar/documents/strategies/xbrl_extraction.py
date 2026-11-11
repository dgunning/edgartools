"""
XBRL extraction strategy for inline XBRL documents.
"""

import copy
import logging
from typing import Any, Dict, List, Optional, Tuple

from lxml.etree import tostring
from lxml.html import HtmlElement

from edgar.dates import normalize_period_boundary
from edgar.documents.strategies.ixbrl_transforms import (
    TransformError,
    UnknownTransformError,
    apply_scale,
    apply_transform,
    expand_format,
    negate_exactly,
)
from edgar.documents.types import XBRLFact
from edgar.xmltools import is_xsi_nil

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

        # Get fact value. Nil is read first: a nil fact's content is not a value
        # to transform, scale or sign (Inline XBRL 1.1 section 11.2.3).
        is_nil = is_xsi_nil(element)
        if is_nil:
            value, issue = self._relevant_content(element, escape=bool(context.get('escape'))).strip(), None
        else:
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
            precision=context.get('precision'),
            escape=bool(context.get('escape')),
            continued_at=context.get('continuedAt'),
            fact_id=element.get('id'),
            is_nil=is_nil,
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

    def link_footnotes(self, facts: List[XBRLFact], footnotes: List[HtmlElement],
                       relationships: List[HtmlElement]) -> Dict[str, Any]:
        """
        Read each ix:footnote and attach it to the facts its ix:relationships name.

        Returns ``{footnote id: Footnote}``, the lookup ``XBRL.footnotes`` gives
        on the instance path, and fills each linked fact's ``footnotes`` with
        footnote ids, as the instance path's ``Fact.footnotes`` does (GH #1756).
        Which relationship is a footnote link and how a footnote's text and
        language are read are the instance parser's rules, shared through
        ``edgar.xbrl.footnote_links``. Only fact-footnote relationships link;
        any other arcrole relates facts in another way and is not a footnote.
        """
        if not footnotes:
            return {}
        if not self._initialized:
            self._initialize_context(footnotes[0])
        from edgar.xbrl.footnote_links import (
            FOOTNOTE_ROLE,
            fact_footnote_links,
            inherited_lang,
            inline_footnote_text,
        )
        from edgar.xbrl.models import Footnote

        # The tree is lxml.html: attribute names are lower-cased and xml:lang
        # is a literal attribute name (see the class docstring).
        by_id: Dict[str, Footnote] = {}
        for element in footnotes:
            footnote_id = element.get('id')
            if not footnote_id or footnote_id in by_id:
                continue
            by_id[footnote_id] = Footnote(
                footnote_id=footnote_id,
                text=inline_footnote_text(element, self.continuations, ('continuedAt', 'continuedat')),
                lang=inherited_lang(element, 'xml:lang'),
                role=element.get('footnoteRole') or element.get('footnoterole') or FOOTNOTE_ROLE,
            )

        links = fact_footnote_links(
            ((rel.get('arcrole'),
              rel.get('fromRefs') or rel.get('fromrefs'),
              rel.get('toRefs') or rel.get('torefs'))
             for rel in relationships),
            by_id)

        first_fact_by_id: Dict[str, XBRLFact] = {}
        for fact in facts:
            if fact.fact_id:
                first_fact_by_id.setdefault(fact.fact_id, fact)
        for from_ids, to_ids in links:
            for footnote_id in to_ids:
                for fact_id in from_ids:
                    by_id[footnote_id].related_fact_ids.append(fact_id)
                    fact = first_fact_by_id.get(fact_id)
                    if fact is not None and footnote_id not in fact.footnotes:
                        fact.footnotes.append(footnote_id)
        return by_id

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
            nil_dimensions: List[str] = []
            dimensions = self._extract_dimensions(context, nil_dimensions)
            if dimensions:
                context_data['dimensions'] = dimensions
            if nil_dimensions:
                context_data['nil_dimensions'] = nil_dimensions

            self.contexts[context_id] = context_data

    def _extract_period(self, context: HtmlElement) -> Dict[str, Any]:
        """The instant or the start/end pair of a context's period."""
        period = self._find_first(context, 'period')
        if period is None:
            return {}

        # The same reading as the instance parser: whitespace collapsed and a
        # whole-day dateTime folded onto its date (GH #1762).
        instant = self._find_first(period, 'instant')
        if instant is not None:
            return {'instant': normalize_period_boundary(instant.text or '', is_end=True),
                    'period_type': 'instant'}

        start = self._find_first(period, 'startdate')
        end = self._find_first(period, 'enddate')
        if start is not None and end is not None:
            return {
                'start_date': normalize_period_boundary(start.text or '', is_end=False),
                'end_date': normalize_period_boundary(end.text or '', is_end=True),
                'period_type': 'duration',
            }
        return {}

    def _extract_dimensions(self, context: HtmlElement,
                            nil_dimensions: Optional[List[str]] = None) -> Dict[str, str]:
        """
        A context's dimensional members, keyed by axis.

        Members are carried in a segment or a scenario; the spec allows either
        and filers use both. A typed member the filer marked xsi:nil is '' and
        its axis is appended to ``nil_dimensions``, as the instance parser
        records it in ``Context.nil_dimensions`` (GH #1751).
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
                    nil = child is not None and is_xsi_nil(child)
                    dimensions[dim] = (child.text or '').strip() if child is not None and not nil else ''
                    if nil and nil_dimensions is not None and dim not in nil_dimensions:
                        nil_dimensions.append(dim)
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
            'precision': element.get('precision'),
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
            'id': element.get('id'),
            'footnoteRole': element.get('footnoteRole') or element.get('footnoterole'),
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
                parts.append(tostring(self._project_escaped(child), encoding='unicode', method='html'))
            else:
                # An ix: element is not XHTML, so escaped content unwraps it:
                # its own content contributes, its start and end tags do not.
                # Without this the value of a nested *TextBlock came back with
                # "<ix:nonnumeric ...>" wrappers embedded in the markup.
                self._collect_content(child, parts, escape)
                parts.append(child.tail or '')

    def _project_escaped(self, element: HtmlElement) -> HtmlElement:
        """
        The XHTML an escaped fact's child contributes, with the Inline XBRL removed.

        The rules of ``_collect_content`` apply at every depth, not just to the
        fact's direct children (Inline XBRL 1.1 section 11.1, GH #1770): an
        ``ix:exclude`` subtree is dropped with its tail kept, and any other
        ``ix:`` element is replaced by its content. The work happens on a
        detached copy, so the parsed tree other passes read is untouched; an
        element with no ``ix:`` descendant is returned as it is.
        """
        if not any(self._is_xbrl_element(node) for node in element.iterdescendants()):
            return element
        projected = copy.deepcopy(element)
        for node in list(projected.iterdescendants()):
            if self._get_local_name(node.tag) == 'exclude' and self._is_xbrl_element(node):
                node.drop_tree()
        for node in list(projected.iterdescendants()):
            if self._is_xbrl_element(node):
                node.drop_tag()
        return projected

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
            # The chain's content is concatenated with nothing in between
            # (Inline XBRL 1.1, section 4.1.1): the filer decides where the
            # split falls, and it can fall inside a word or a number, as in
            # Cooper's "6" + "101 Bollinger Canyon Road" (GH #1748).
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
                # The format resolves in the registry its prefix is declared
                # for, not by local name under any namespace (GH #1743).
                value = apply_transform(expand_format(element, format_attr), value)
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
            negated = negate_exactly(value)
            if negated is not None:
                value = negated
            elif not value.startswith('-'):
                value = '-' + value

        return value.strip(), issue

    def _report_format_issue(self, format_attr: str, message: str):
        """Warn once per format, so a filing using one 3,000 times says so once."""
        if format_attr not in self._reported_formats:
            self._reported_formats.add(format_attr)
            logger.warning("Inline XBRL: %s; the raw display text is used instead", message)
