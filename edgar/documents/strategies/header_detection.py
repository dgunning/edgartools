"""
Multi-strategy header detection for document structure.
"""

import re
from abc import ABC, abstractmethod
from typing import Optional, List, Dict

from lxml.html import HtmlElement

from edgar.documents.config import ParserConfig
from edgar.documents.types import HeaderInfo, ParseContext


class HeaderDetector(ABC):
    """Abstract base class for header detectors."""
    
    @abstractmethod
    def detect(self, element: HtmlElement, context: ParseContext) -> Optional[HeaderInfo]:
        """Detect if element is a header."""
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Detector name."""
        pass


class StyleBasedDetector(HeaderDetector):
    """Detect headers based on CSS styles."""
    
    @property
    def name(self) -> str:
        return "style"
    
    def detect(self, element: HtmlElement, context: ParseContext) -> Optional[HeaderInfo]:
        """Detect headers based on style attributes."""
        # Get element style
        style = context.get_current_style()
        
        # Skip if no style info
        if not style:
            return None
        
        # Get text content
        text = element.text_content().strip()
        if not text or len(text) > 200:  # Skip very long text
            return None
        
        confidence = 0.0
        level = 3  # Default level
        
        # Check font size
        if style.font_size and context.base_font_size:
            size_ratio = style.font_size / context.base_font_size
            
            if size_ratio >= 2.0:
                confidence += 0.8
                level = 1
            elif size_ratio >= 1.5:
                confidence += 0.7
                level = 2
            elif size_ratio >= 1.2:
                confidence += 0.5
                level = 3
            elif size_ratio >= 1.1:
                confidence += 0.3
                level = 4
        
        # Check font weight
        if style.is_bold:
            confidence += 0.3
            if level == 3:  # Adjust level for bold text
                level = 2
        
        # Check text alignment
        if style.is_centered:
            confidence += 0.2
        
        # Check for uppercase
        if text.isupper() and len(text.split()) <= 10:
            confidence += 0.2
        
        # Check margins (headers often have larger margins)
        if style.margin_top and style.margin_top > 20:
            confidence += 0.1
        if style.margin_bottom and style.margin_bottom > 10:
            confidence += 0.1
        
        # Normalize confidence
        confidence = min(confidence, 1.0)
        
        if confidence > 0.4:  # Threshold for style-based detection
            return HeaderInfo.from_text(text, level, confidence, self.name)
        
        return None


class PatternBasedDetector(HeaderDetector):
    """Detect headers based on text patterns."""
    
    # Common header patterns in SEC filings
    HEADER_PATTERNS = [
        # Item patterns
        (r'^(Item|ITEM)\s+(\d+[A-Z]?)[.\s]+(.+)$', 1, 0.95),
        (r'^Part\s+[IVX]+[.\s]*$', 1, 0.9),
        (r'^PART\s+[IVX]+[.\s]*$', 1, 0.9),
        
        # Section patterns
        (r'^(BUSINESS|RISK FACTORS|PROPERTIES|LEGAL PROCEEDINGS)$', 2, 0.85),
        (r'^(Management\'?s?\s+Discussion|MD&A)', 2, 0.85),
        (r'^(Financial\s+Statements|Consolidated\s+Financial\s+Statements)$', 2, 0.85),
        
        # Numbered sections
        (r'^\d+\.\s+[A-Z][A-Za-z\s]+$', 3, 0.7),
        (r'^[A-Z]\.\s+[A-Z][A-Za-z\s]+$', 3, 0.7),
        (r'^\([a-z]\)\s+[A-Z][A-Za-z\s]+$', 4, 0.6),
        
        # Title case headers
        (r'^[A-Z][A-Za-z\s]+[A-Za-z]$', 3, 0.5),
        
        # All caps headers
        (r'^[A-Z\s]+$', 3, 0.6),
    ]
    
    @property
    def name(self) -> str:
        return "pattern"
    
    def detect(self, element: HtmlElement, context: ParseContext) -> Optional[HeaderInfo]:
        """Detect headers based on text patterns."""
        text = element.text_content().strip()
        
        # Skip empty or very long text
        if not text or len(text) > 200:
            return None
        
        # Skip single punctuation - never headers
        if len(text) == 1 and text in '.,!?;:()[]{}':
            return None
        
        # Skip if text contains multiple sentences (likely paragraph)
        if text.count('.') > 2:
            return None
        
        # Check against patterns
        for pattern, level, base_confidence in self.HEADER_PATTERNS:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                # Adjust confidence based on context
                confidence = base_confidence
                
                # Boost confidence if element is alone in parent
                if len(element.getparent()) == 1:
                    confidence += 0.1
                
                # Boost confidence if followed by substantial text
                next_elem = element.getnext()
                if next_elem is not None and len(next_elem.text_content()) > 100:
                    confidence += 0.1
                
                confidence = min(confidence, 1.0)
                
                return HeaderInfo.from_text(text, level, confidence, self.name)
        
        return None


class StructuralDetector(HeaderDetector):
    """Detect headers based on DOM structure."""
    
    @property
    def name(self) -> str:
        return "structural"
    
    def detect(self, element: HtmlElement, context: ParseContext) -> Optional[HeaderInfo]:
        """Detect headers based on structural cues."""
        text = element.text_content().strip()
        
        # Skip empty or very long text
        if not text or len(text) > 200:
            return None
        
        # Skip single punctuation - never headers
        if len(text) == 1 and text in '.,!?;:()[]{}':
            return None
        
        confidence = 0.0
        level = 3
        
        # Check if element is in a header tag
        tag = element.tag.lower()
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            confidence = 1.0
            level = int(tag[1])
            return HeaderInfo.from_text(text, level, confidence, self.name)
        
        # Check parent structure
        parent = element.getparent()
        if parent is not None:
            parent_tag = parent.tag.lower()
            
            # Check if in header-like container
            if parent_tag in ['header', 'thead', 'caption']:
                confidence += 0.6
                level = 2
            
            # Check if parent has few children (isolated element)
            if len(parent) <= 3:
                confidence += 0.3
            
            # Check if parent is centered
            parent_align = parent.get('align')
            if parent_align == 'center':
                confidence += 0.2
        
        # Check element properties
        if tag in ['strong', 'b']:
            confidence += 0.3
        
        if element.get('align') == 'center':
            confidence += 0.2
        
        # Check if followed by block content
        next_elem = element.getnext()
        if next_elem is not None:
            next_tag = next_elem.tag.lower()
            if next_tag in ['p', 'div', 'table', 'ul', 'ol']:
                confidence += 0.2
        
        # Check text characteristics
        words = text.split()
        if 1 <= len(words) <= 10:  # Short text
            confidence += 0.1
        
        # Normalize confidence
        confidence = min(confidence, 1.0)
        
        if confidence > 0.5:
            return HeaderInfo.from_text(text, level, confidence, self.name)
        
        return None


class ContextualDetector(HeaderDetector):
    """Detect headers based on surrounding context."""
    
    @property
    def name(self) -> str:
        return "contextual"
    
    def detect(self, element: HtmlElement, context: ParseContext) -> Optional[HeaderInfo]:
        """Detect headers based on contextual clues."""
        text = element.text_content().strip()
        
        # Skip empty or very long text
        if not text or len(text) > 200:
            return None
        
        # Skip single punctuation - never headers
        if len(text) == 1 and text in '.,!?;:()[]{}':
            return None
        
        confidence = 0.0
        level = 3
        
        # Check if text looks like a header
        if self._looks_like_header(text):
            confidence += 0.4
        
        # Check relationship to previous content
        prev_elem = element.getprevious()
        if prev_elem is not None:
            prev_text = prev_elem.text_content().strip()
            
            # Check if previous was also a header (section hierarchy)
            if prev_text and self._looks_like_header(prev_text):
                confidence += 0.3
                # Adjust level based on comparison
                if len(text) > len(prev_text):
                    level = 2
                else:
                    level = 3
        
        # Check relationship to next content
        next_elem = element.getnext()
        if next_elem is not None:
            next_text = next_elem.text_content().strip()
            
            # Headers are often followed by longer content
            if len(next_text) > len(text) * 3:
                confidence += 0.3
            
            # Check if next element is indented or styled differently
            next_style = next_elem.get('style', '')
            if 'margin-left' in next_style or 'padding-left' in next_style:
                confidence += 0.2
        
        # Check position in document
        if context.current_section is None and context.depth < 5:
            # Early in document, more likely to be header
            confidence += 0.2
        
        # Normalize confidence
        confidence = min(confidence, 1.0)
        
        if confidence > 0.5:
            return HeaderInfo.from_text(text, level, confidence, self.name)
        
        return None
    
    def _looks_like_header(self, text: str) -> bool:
        """Check if text looks like a header."""
        # Short text
        if len(text.split()) > 15:
            return False
        
        # No ending punctuation (except colon)
        if text.rstrip().endswith(('.', '!', '?', ';')):
            return False
        
        # Title case or all caps
        if text.istitle() or text.isupper():
            return True
        
        # Starts with capital letter
        if text and text[0].isupper():
            return True
        
        return False


class HeaderDetectionStrategy:
    """
    Multi-strategy header detection.
    
    Combines multiple detection methods with weighted voting.
    """
    
    def __init__(self, config: ParserConfig):
        """Initialize with configuration."""
        self.config = config
        self.detectors = self._init_detectors()
    
    def _init_detectors(self) -> List[HeaderDetector]:
        """Initialize enabled detectors."""
        detectors = []
        
        # Always include basic detectors
        detectors.extend([
            StyleBasedDetector(),
            PatternBasedDetector(),
            StructuralDetector(),
            ContextualDetector()
        ])
        
        # Add ML detector if enabled
        if self.config.features.get('ml_header_detection'):
            # Would add MLBasedDetector here
            pass
        
        return detectors
    
    def detect(self, element: HtmlElement, context: ParseContext) -> Optional[HeaderInfo]:
        """
        Detect if element is a header using multiple strategies.
        
        Args:
            element: HTML element to check
            context: Current parsing context
            
        Returns:
            HeaderInfo if element is detected as header, None otherwise
        """
        # Skip if element has no text
        text = element.text_content().strip()
        if not text:
            return None
        
        # Collect results from all detectors
        results: List[HeaderInfo] = []
        
        for detector in self.detectors:
            try:
                result = detector.detect(element, context)
                if result:
                    results.append(result)
            except Exception:
                # Don't let one detector failure stop others
                continue
        
        if not results:
            return None
        
        # If only one detector fired, use its result if confident enough
        if len(results) == 1:
            if results[0].confidence >= self.config.header_detection_threshold:
                return results[0]
            return None
        
        # Multiple detectors - combine results
        return self._combine_results(results, text)
    
    def _combine_results(self, results: List[HeaderInfo], text: str) -> HeaderInfo:
        """Combine multiple detection results."""
        # Weight different detectors
        detector_weights = {
            'style': 0.3,
            'pattern': 0.4,
            'structural': 0.2,
            'contextual': 0.1,
            'ml': 0.5  # Would be highest if available
        }
        
        # Calculate weighted confidence
        total_confidence = 0.0
        total_weight = 0.0
        
        # Group by level
        level_votes: Dict[int, float] = {}
        
        for result in results:
            weight = detector_weights.get(result.detection_method, 0.1)
            total_confidence += result.confidence * weight
            total_weight += weight
            
            # Vote for level
            if result.level not in level_votes:
                level_votes[result.level] = 0.0
            level_votes[result.level] += result.confidence * weight
        
        # Normalize confidence
        final_confidence = total_confidence / total_weight if total_weight > 0 else 0.0
        
        # Choose most voted level
        final_level = max(level_votes.items(), key=lambda x: x[1])[0]
        
        # Check if any detector found this is an item
        is_item = any(r.is_item for r in results)
        item_number = next((r.item_number for r in results if r.item_number), None)
        
        return HeaderInfo(
            level=final_level,
            confidence=final_confidence,
            text=text,
            detection_method='combined',
            is_item=is_item,
            item_number=item_number
        )