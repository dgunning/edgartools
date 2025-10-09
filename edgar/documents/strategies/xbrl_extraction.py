"""
XBRL extraction strategy for inline XBRL documents.
"""

from typing import Dict, Any, Optional

from lxml.html import HtmlElement

from edgar.documents.types import XBRLFact


class XBRLExtractor:
    """
    Extracts XBRL facts from inline XBRL (iXBRL) documents.
    
    Handles:
    - ix:nonFraction, ix:nonNumeric facts
    - Context and unit resolution
    - Continuation handling
    - Transformation rules
    """
    
    # XBRL namespaces
    NAMESPACES = {
        'ix': 'http://www.xbrl.org/2013/inlineXBRL',
        'xbrli': 'http://www.xbrl.org/2003/instance',
        'xbrldi': 'http://xbrl.org/2006/xbrldi',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }
    
    # Common transformation formats
    TRANSFORMATIONS = {
        'ixt:numdotdecimal': lambda x: x.replace(',', ''),
        'ixt:numcommadecimal': lambda x: x.replace('.', '_').replace(',', '.').replace('_', ','),
        'ixt:zerodash': lambda x: '0' if x == '-' else x,
        'ixt:datedoteu': lambda x: x.replace('.', '-'),
        'ixt:datedotus': lambda x: x.replace('.', '/'),
    }
    
    def __init__(self):
        """Initialize XBRL extractor."""
        self.contexts: Dict[str, Dict[str, Any]] = {}
        self.units: Dict[str, str] = {}
        self.continuations: Dict[str, str] = {}
        self._initialized = False
    
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
        """Extract XBRL fact from element."""
        context = self.extract_context(element)
        if not context:
            return None
        
        # Get fact value
        value = self._get_fact_value(element)
        
        # Create fact
        fact = XBRLFact(
            concept=context.get('name', ''),
            value=value,
            context_ref=context.get('contextRef'),
            unit_ref=context.get('unitRef'),
            decimals=context.get('decimals'),
            scale=context.get('scale'),
            format=context.get('format'),
            sign=context.get('sign')
        )
        
        # Resolve references
        if fact.context_ref and fact.context_ref in self.contexts:
            fact.context = self.contexts[fact.context_ref]
        
        if fact.unit_ref and fact.unit_ref in self.units:
            fact.unit = self.units[fact.unit_ref]
        
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
    
    def _get_local_name(self, tag: str) -> str:
        """Get local name from qualified tag."""
        if '}' in tag:
            return tag.split('}')[1].lower()
        elif ':' in tag:
            return tag.split(':')[1].lower()
        return tag.lower()
    
    def _initialize_context(self, element: HtmlElement):
        """Initialize context and unit information from document."""
        # Find root element
        root = element.getroottree().getroot()
        
        # Extract contexts
        self._extract_contexts(root)
        
        # Extract units
        self._extract_units(root)
        
        self._initialized = True
    
    def _extract_contexts(self, root: HtmlElement):
        """Extract all context definitions."""
        # Look for xbrli:context elements
        for context in root.xpath('//xbrli:context', namespaces=self.NAMESPACES):
            context_id = context.get('id')
            if not context_id:
                continue
            
            context_data = {
                'id': context_id
            }
            
            # Extract entity
            entity = context.find('.//xbrli:entity', namespaces=self.NAMESPACES)
            if entity is not None:
                identifier = entity.find('.//xbrli:identifier', namespaces=self.NAMESPACES)
                if identifier is not None:
                    context_data['entity'] = identifier.text
                    context_data['scheme'] = identifier.get('scheme')
            
            # Extract period
            period = context.find('.//xbrli:period', namespaces=self.NAMESPACES)
            if period is not None:
                instant = period.find('.//xbrli:instant', namespaces=self.NAMESPACES)
                if instant is not None:
                    context_data['instant'] = instant.text
                    context_data['period_type'] = 'instant'
                else:
                    start = period.find('.//xbrli:startDate', namespaces=self.NAMESPACES)
                    end = period.find('.//xbrli:endDate', namespaces=self.NAMESPACES)
                    if start is not None and end is not None:
                        context_data['start_date'] = start.text
                        context_data['end_date'] = end.text
                        context_data['period_type'] = 'duration'
            
            # Extract dimensions
            segment = context.find('.//xbrli:segment', namespaces=self.NAMESPACES)
            if segment is not None:
                dimensions = {}
                for member in segment.findall('.//xbrldi:explicitMember', namespaces=self.NAMESPACES):
                    dim = member.get('dimension')
                    if dim:
                        dimensions[dim] = member.text
                if dimensions:
                    context_data['dimensions'] = dimensions
            
            self.contexts[context_id] = context_data
    
    def _extract_units(self, root: HtmlElement):
        """Extract all unit definitions."""
        # Look for xbrli:unit elements
        for unit in root.xpath('//xbrli:unit', namespaces=self.NAMESPACES):
            unit_id = unit.get('id')
            if not unit_id:
                continue
            
            # Check for simple measure
            measure = unit.find('.//xbrli:measure', namespaces=self.NAMESPACES)
            if measure is not None:
                self.units[unit_id] = self._normalize_unit(measure.text)
                continue
            
            # Check for complex unit (divide)
            divide = unit.find('.//xbrli:divide', namespaces=self.NAMESPACES)
            if divide is not None:
                numerator = divide.find('.//xbrli:unitNumerator/xbrli:measure', namespaces=self.NAMESPACES)
                denominator = divide.find('.//xbrli:unitDenominator/xbrli:measure', namespaces=self.NAMESPACES)
                
                if numerator is not None and denominator is not None:
                    num_unit = self._normalize_unit(numerator.text)
                    den_unit = self._normalize_unit(denominator.text)
                    self.units[unit_id] = f"{num_unit}/{den_unit}"
    
    def _normalize_unit(self, unit_text: str) -> str:
        """Normalize unit text."""
        if not unit_text:
            return ''
        
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
            'format': element.get('format')
        }
        
        # Clean None values
        return {k: v for k, v in metadata.items() if v is not None}
    
    def _extract_continuation(self, element: HtmlElement) -> Dict[str, Any]:
        """Extract ix:continuation element."""
        cont_id = element.get('id')
        continued_at = element.get('continuedAt')
        
        if cont_id and continued_at:
            # Map continuation to original
            if continued_at in self.continuations:
                original = self.continuations[continued_at]
                self.continuations[cont_id] = original
                return original
            else:
                # Store for later resolution
                metadata = {
                    'type': 'continuation',
                    'id': cont_id,
                    'continuedAt': continued_at
                }
                self.continuations[cont_id] = metadata
                return metadata
        
        return {}
    
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
    
    def _get_fact_value(self, element: HtmlElement) -> str:
        """Get fact value from element with transformations."""
        # Get raw value
        value = element.text or ''
        
        # Apply format transformation if specified
        format_attr = element.get('format')
        if format_attr and format_attr in self.TRANSFORMATIONS:
            transform = self.TRANSFORMATIONS[format_attr]
            value = transform(value)
        
        # Apply scale if specified
        scale = element.get('scale')
        if scale:
            try:
                scale_factor = int(scale)
                numeric_value = float(value.replace(',', ''))
                scaled_value = numeric_value * (10 ** scale_factor)
                value = str(scaled_value)
            except (ValueError, TypeError):
                pass
        
        # Apply sign if specified
        sign = element.get('sign')
        if sign == '-':
            if value and not value.startswith('-'):
                value = '-' + value
        
        return value.strip()