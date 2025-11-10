"""
Instance parser for XBRL documents.

This module handles parsing of XBRL instance documents including facts, contexts,
units, footnotes, and entity information extraction.
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union

from lxml import etree as ET

from edgar.core import log
from edgar.xbrl.core import NAMESPACES, classify_duration
from edgar.xbrl.models import Context, Fact, XBRLProcessingError

from .base import BaseParser


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

    def _create_normalized_fact_key(self, element_id: str, context_ref: str, instance_id: int = None) -> str:
        """
        Create a normalized fact key using underscore format.

        Args:
            element_id: The element ID
            context_ref: The context reference
            instance_id: Optional instance ID for duplicate facts

        Returns:
            Normalized key in format: element_id_context_ref[_instance_id]
        """
        normalized_element_id = element_id
        if ':' in element_id:
            prefix, name = element_id.split(':', 1)
            normalized_element_id = f"{prefix}_{name}"
        if instance_id is not None:
            return f"{normalized_element_id}_{context_ref}_{instance_id}"
        return f"{normalized_element_id}_{context_ref}"

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
            parser = ET.XMLParser(remove_blank_text=True, recover=True, huge_tree=True)

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
        parser = ET.XMLParser(remove_blank_text=True, recover=True, huge_tree=True)

        # Convert to bytes for faster parsing if not already
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content

        # Parse content with optimized settings
        root = ET.XML(content_bytes, parser)

        # Fast path to identify non-fact elements to skip
        skip_tag_endings = {'}context', '}unit', '}schemaRef'}

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
            for ending in skip_tag_endings:
                if tag.endswith(ending):
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
                # Try to extract prefix from the namespace
                parts = namespace.split('/')
                prefix = parts[-1] if parts else ''

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
                        # Extract explicit dimensions
                        for dim_elem in segment_elem.findall('.//{http://xbrl.org/2006/xbrldi}explicitMember'):
                            dimension = dim_elem.get('dimension')
                            value = dim_elem.text
                            if dimension and value:
                                context.dimensions[dimension] = value

                        # Extract typed dimensions
                        for dim_elem in segment_elem.findall('.//{http://xbrl.org/2006/xbrldi}typedMember'):
                            dimension = dim_elem.get('dimension')
                            if dimension:
                                # The typed dimension value is the text content of the first child element
                                for child in dim_elem:
                                    # Extract the text content, which contains the actual typed member value
                                    if child.text and child.text.strip():
                                        context.dimensions[dimension] = child.text.strip()
                                    else:
                                        # Fallback to tag if no text content
                                        context.dimensions[dimension] = child.tag
                                    break

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

    def _extract_units(self, root: ET.Element) -> None:
        """Extract units from instance document."""
        try:
            # Find all unit elements
            for unit_elem in root.findall('.//{http://www.xbrl.org/2003/instance}unit'):
                unit_id = unit_elem.get('id')
                if not unit_id:
                    continue

                # Check for measure
                measure_elem = unit_elem.find('.//{http://www.xbrl.org/2003/instance}measure')
                if measure_elem is not None and measure_elem.text:
                    self.units[unit_id] = {
                        'type': 'simple',
                        'measure': measure_elem.text
                    }
                    continue

                # Check for divide
                divide_elem = unit_elem.find('.//{http://www.xbrl.org/2003/instance}divide')
                if divide_elem is not None:
                    # Get numerator
                    numerator_elem = divide_elem.find('.//{http://www.xbrl.org/2003/instance}unitNumerator')
                    denominator_elem = divide_elem.find('.//{http://www.xbrl.org/2003/instance}unitDenominator')

                    if numerator_elem is not None and denominator_elem is not None:
                        # Get measures
                        numerator_measures = [elem.text for elem in numerator_elem.findall('.//{http://www.xbrl.org/2003/instance}measure') if elem.text]
                        denominator_measures = [elem.text for elem in denominator_elem.findall('.//{http://www.xbrl.org/2003/instance}measure') if elem.text]

                        self.units[unit_id] = {
                            'type': 'divide',
                            'numerator': numerator_measures,
                            'denominator': denominator_measures
                        }

        except Exception as e:
            raise XBRLProcessingError(f"Error extracting units: {str(e)}") from e

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

            # Initialize counters and tracking
            fact_count = 0
            facts_dict = {}
            base_keys = {}

            # Fast path to identify non-fact elements to skip - compile as set for O(1) lookup
            skip_tag_endings = {
                'schemaRef',
                'roleRef',
                'arcroleRef',
                'linkbaseRef',
                'context',
                'unit'
            }

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
                for ending in skip_tag_endings:
                    if tag.endswith(ending):
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
                        parts = namespace.split('/')
                        prefix = parts[-1] if parts else ''
                else:
                    element_name = tag
                    prefix = ''

                # Construct element ID with optimized string concatenation
                element_id = f"{prefix}:{element_name}" if prefix else element_name

                # Get unit reference
                unit_ref = element.get('unitRef')

                # Get value - optimize string handling
                value = element.text
                if not value or not value.strip():
                    # Only check children if text is empty - use direct iteration for speed
                    for sub_elem in element:
                        sub_text = sub_elem.text
                        if sub_text and sub_text.strip():
                            value = sub_text
                            break

                # Optimize string handling - inline conditional
                value = value.strip() if value else ""

                # Get decimals attribute - direct access
                decimals = element.get('decimals')

                # Optimize numeric conversion with faster try/except
                numeric_value = None
                if value:
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

        Footnotes in XBRL are linked to facts via footnoteLink elements that contain:
        1. footnote elements with the actual text content
        2. footnoteArc elements that connect fact IDs to footnote IDs
        """
        try:
            from edgar.xbrl.models import Footnote

            # Track undefined footnotes for deduplication
            undefined_footnotes = set()

            # Find all footnoteLink elements
            for footnote_link in root.findall('.//{http://www.xbrl.org/2003/linkbase}footnoteLink'):
                # First, extract all footnote definitions
                for footnote_elem in footnote_link.findall('{http://www.xbrl.org/2003/linkbase}footnote'):
                    # Prioritize xlink:label over id attribute for footnote identification.
                    # FootnoteArcs reference footnotes using xlink:to, which corresponds to xlink:label.
                    # In pre-2016 filings, these attributes often differ (e.g., xlink:label="lbl_footnote_0"
                    # vs id="FN_0"), so we must use xlink:label to match arc references correctly.
                    footnote_id = footnote_elem.get('{http://www.w3.org/1999/xlink}label') or footnote_elem.get('id')
                    if not footnote_id:
                        continue

                    # Get footnote attributes
                    lang = footnote_elem.get('{http://www.w3.org/XML/1998/namespace}lang', 'en-US')
                    role = footnote_elem.get('{http://www.w3.org/1999/xlink}role')

                    # Extract text content, handling XHTML formatting
                    footnote_text = ""
                    # Check for XHTML content
                    xhtml_divs = footnote_elem.findall('.//{http://www.w3.org/1999/xhtml}div')
                    if xhtml_divs:
                        # Concatenate all text within XHTML elements
                        for div in xhtml_divs:
                            footnote_text += "".join(div.itertext()).strip()
                    else:
                        # Fall back to direct text content
                        footnote_text = "".join(footnote_elem.itertext()).strip()

                    # Create Footnote object
                    footnote = Footnote(
                        footnote_id=footnote_id,
                        text=footnote_text,
                        lang=lang,
                        role=role,
                        related_fact_ids=[]
                    )
                    self.footnotes[footnote_id] = footnote

                # Second, process footnoteArc elements to link facts to footnotes
                for arc_elem in footnote_link.findall('{http://www.xbrl.org/2003/linkbase}footnoteArc'):
                    fact_id = arc_elem.get('{http://www.w3.org/1999/xlink}from')
                    footnote_id = arc_elem.get('{http://www.w3.org/1999/xlink}to')

                    if fact_id and footnote_id:
                        # Add fact ID to footnote's related facts
                        if footnote_id in self.footnotes:
                            self.footnotes[footnote_id].related_fact_ids.append(fact_id)
                        else:
                            # Track undefined footnote (common in older filings due to naming inconsistencies)
                            if footnote_id not in undefined_footnotes:
                                undefined_footnotes.add(footnote_id)
                                log.debug(f"Footnote arc references undefined footnote: {footnote_id}")

                        # Also update the fact's footnotes list if we can find it
                        # This requires finding the fact by its fact_id
                        for fact in self.facts.values():
                            if fact.fact_id == fact_id:
                                if footnote_id not in fact.footnotes:
                                    fact.footnotes.append(footnote_id)
                                break

            # Summary message for undefined footnotes (non-critical)
            if undefined_footnotes:
                log.debug(f"{len(undefined_footnotes)} footnote arc references could not be resolved (non-critical)")

            log.debug(f"Extracted {len(self.footnotes)} footnotes")

        except Exception as e:
            # Log the error but don't fail - footnotes are optional
            log.warning(f"Error extracting footnotes: {str(e)}")

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

            # Collect all DEI facts into a dict: concept -> Fact
            self.dei_facts: Dict[str, Fact] = {}
            for fact in self.facts.values():
                eid = fact.element_id
                if eid.startswith('dei:'):
                    concept = eid.split(':', 1)[1]
                elif eid.startswith('dei_'):
                    concept = eid.split('_', 1)[1]
                else:
                    continue
                self.dei_facts[concept] = fact

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

            # Flags based on document_type
            dt_val = self.entity_info['document_type'] or ''
            self.entity_info['annual_report']    = (dt_val == '10-K')
            self.entity_info['quarterly_report'] = (dt_val == '10-Q')
            self.entity_info['amendment']        = ('/A' in dt_val)

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

                    # Calculate duration in days
                    days = (end_obj - start_obj).days

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
