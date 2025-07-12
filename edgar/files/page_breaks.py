"""Page break detection utilities for SEC documents.

This module provides shared page break detection functionality that can be used
by both the edgar library and external projects that need to detect page breaks
in SEC HTML documents.
"""

from bs4 import Tag
from typing import List, Dict, Any, Optional
import re


class PageBreakDetector:
    """Detects page breaks in SEC HTML documents."""
    
    # CSS page break selectors
    PAGE_BREAK_SELECTORS = [
        'p[style*="page-break-before:always"]',
        'p[style*="page-break-after:always"]', 
        'hr[style*="page-break-after:always"]',
        'div[style*="page-break-before:always"]',
        'div[style*="page-break-after:always"]',
        # Handle variations with spaces in CSS
        'p[style*="page-break-before: always"]',
        'p[style*="page-break-after: always"]',
        'hr[style*="page-break-after: always"]',
        'div[style*="page-break-before: always"]',
        'div[style*="page-break-after: always"]'
    ]
    
    # Class-based page break selectors
    CLASS_BASED_SELECTORS = [
        'div.BRPFPageBreak',
        'div.pagebreak',
        'div.page-break'
    ]
    
    # HR elements with specific styling
    HR_PAGE_BREAK_SELECTORS = [
        'hr[style*="height:3px"]',
        'hr[style*="height: 3px"]'
    ]
    
    @staticmethod
    def find_page_breaks(element: Tag) -> List[Dict[str, Any]]:
        """Find all page break elements in the document.
        
        Args:
            element: BeautifulSoup Tag element to search for page breaks
            
        Returns:
            List of dictionaries containing page break information:
            - element: Tag name of the page break element
            - selector: CSS selector that matched this element
            - style: Style attributes of the element
            - classes: CSS classes of the element
            - is_page_div: Whether this is a page-like div
        """
        page_breaks = []
        
        # Find CSS page break elements
        for selector in PageBreakDetector.PAGE_BREAK_SELECTORS:
            elements = element.select(selector)
            for el in elements:
                page_breaks.append({
                    'element': el.name,
                    'selector': selector,
                    'style': el.get('style', ''),
                    'classes': el.get('class', []),
                    'is_page_div': False
                })
        
        # Find class-based page breaks
        for selector in PageBreakDetector.CLASS_BASED_SELECTORS:
            elements = element.select(selector)
            for el in elements:
                page_breaks.append({
                    'element': el.name,
                    'selector': selector,
                    'style': el.get('style', ''),
                    'classes': el.get('class', []),
                    'is_page_div': False
                })
        
        # Find HR page breaks
        for selector in PageBreakDetector.HR_PAGE_BREAK_SELECTORS:
            elements = element.select(selector)
            for el in elements:
                page_breaks.append({
                    'element': el.name,
                    'selector': selector,
                    'style': el.get('style', ''),
                    'classes': el.get('class', []),
                    'is_page_div': False
                })
        
        # Find page-like divs
        page_divs = PageBreakDetector._find_page_like_divs(element)
        page_breaks.extend(page_divs)
        
        return page_breaks
    
    @staticmethod
    def _find_page_like_divs(element: Tag) -> List[Dict[str, Any]]:
        """Find div elements with page-like dimensions."""
        page_divs = []
        divs = element.find_all('div')
        
        for div in divs:
            style = div.get('style', '')
            if not style:
                continue
                
            if PageBreakDetector._is_page_like_div(style):
                page_divs.append({
                    'element': div.name,
                    'selector': 'page-like-div',
                    'style': style,
                    'classes': div.get('class', []),
                    'is_page_div': True
                })
        
        return page_divs
    
    @staticmethod
    def _is_page_like_div(style: str) -> bool:
        """Check if a div has page-like dimensions based on its style.
        
        Args:
            style: CSS style string to analyze
            
        Returns:
            True if the div has page-like dimensions and styling
        """
        # Parse the style string to extract key properties
        style_props = {}
        for prop in style.split(';'):
            if ':' in prop:
                key, value = prop.split(':', 1)
                style_props[key.strip().lower()] = value.strip().lower()
        
        # Check for page-like dimensions
        height = style_props.get('height', '')
        width = style_props.get('width', '')
        position = style_props.get('position', '')
        overflow = style_props.get('overflow', '')
        
        # Look for typical page dimensions
        # Common page heights: 842.4pt (A4), 792pt (Letter), 1008pt (Legal)
        # Common page widths: 597.6pt (A4), 612pt (Letter), 612pt (Legal)
        page_heights = ['842.4pt', '792pt', '1008pt']
        page_widths = ['597.6pt', '612pt']
        
        has_page_height = any(ph in height for ph in page_heights)
        has_page_width = any(pw in width for pw in page_widths)
        has_position = position in ['relative', 'absolute']
        has_overflow = 'hidden' in overflow
        
        # Consider it a page div if it has both page-like dimensions
        # and typical page styling properties
        return has_page_height and has_page_width and (has_position or has_overflow)
    

    
    @staticmethod
    def mark_page_breaks(element: Tag) -> None:
        """Mark page break elements with a special attribute for detection.
        
        This method adds '_is_page_break' attributes to elements that represent
        page breaks, which can be used by other parts of the system.
        
        Args:
            element: BeautifulSoup Tag element to mark
        """
        # Mark CSS page break elements
        for selector in PageBreakDetector.PAGE_BREAK_SELECTORS:
            page_breaks = element.select(selector)
            for pb in page_breaks:
                pb['_is_page_break'] = 'true'
        
        # Mark class-based page breaks
        for selector in PageBreakDetector.CLASS_BASED_SELECTORS:
            page_breaks = element.select(selector)
            for pb in page_breaks:
                pb['_is_page_break'] = 'true'
                # Also mark parent containers that contain page breaks
                if pb.parent and pb.parent.name == 'div':
                    parent_classes = pb.parent.get('class', [])
                    if any('pagebreak' in cls.lower() for cls in parent_classes):
                        pb.parent['_is_page_break'] = 'true'
        
        # Mark HR page breaks
        for selector in PageBreakDetector.HR_PAGE_BREAK_SELECTORS:
            page_breaks = element.select(selector)
            for pb in page_breaks:
                pb['_is_page_break'] = 'true'
        
        # Mark page-like divs
        divs = element.find_all('div')
        for div in divs:
            style = div.get('style', '')
            if style and PageBreakDetector._is_page_like_div(style):
                div['_is_page_break'] = 'true'


def detect_page_breaks(html_content: str) -> List[Dict[str, Any]]:
    """Detect page breaks in HTML content.
    
    This is the main public function for external use.
    
    Args:
        html_content: HTML string to analyze
        
    Returns:
        List of dictionaries containing page break information
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html_content, 'html.parser')
    return PageBreakDetector.find_page_breaks(soup)


def mark_page_breaks(html_content: str) -> str:
    """Mark page breaks in HTML content and return the modified HTML.
    
    Args:
        html_content: HTML string to process
        
    Returns:
        Modified HTML string with page break markers added
    """
    from bs4 import BeautifulSoup
    
    soup = BeautifulSoup(html_content, 'html.parser')
    PageBreakDetector.mark_page_breaks(soup)
    return str(soup)


 