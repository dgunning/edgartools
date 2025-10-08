"""
Anchor-based navigation link filter.

This approach detects repetitive navigation links by analyzing their HTML structure
and frequency patterns, rather than hardcoding specific text patterns.
"""
import re
from typing import Dict, List, Set, Tuple
from collections import Counter
from bs4 import BeautifulSoup


def identify_navigation_links(html_content: str, min_frequency: int = 5) -> Set[str]:
    """
    Identify repetitive navigation link texts by analyzing anchor link frequency.
    
    This detects navigation links structurally by finding internal anchor links
    that appear multiple times throughout the document.
    
    Args:
        html_content: HTML content to analyze
        min_frequency: Minimum times a link must appear to be considered navigation
        
    Returns:
        Set of link texts that are identified as navigation
    """
    if not html_content:
        return set()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Count frequency of internal anchor link texts
    link_text_counts = Counter()
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '').strip()
        text = link.get_text().strip()
        
        # Only consider internal anchor links
        if href.startswith('#') and text:
            # Normalize text (remove extra whitespace)
            normalized_text = ' '.join(text.split())
            link_text_counts[normalized_text] += 1
    
    # Return texts that appear frequently (likely navigation)
    navigation_texts = {
        text for text, count in link_text_counts.items()
        if count >= min_frequency
    }
    
    return navigation_texts


def identify_structural_navigation(html_content: str) -> Set[str]:
    """
    Identify navigation links based on anchor targets that point to structural elements.
    
    Args:
        html_content: HTML content to analyze
        
    Returns:
        Set of link texts that link to structural elements
    """
    if not html_content:
        return set()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Patterns that indicate structural/navigational targets
    structural_patterns = [
        r'toc',  # table of contents
        r'index',  # index sections  
        r'part\w*\d+',  # part I, part II, etc.
        r'item\w*\d+',  # item 1, item 2, etc.
        r'exhibit',  # exhibits
        r'financial.*statement',  # financial statements
        r'beginning|top|start',  # document navigation
    ]
    
    structural_texts = set()
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '').strip()
        text = link.get_text().strip()
        
        if href.startswith('#') and text:
            anchor_id = href[1:]  # Remove the #
            
            # Check if anchor ID matches structural patterns
            for pattern in structural_patterns:
                if re.search(pattern, anchor_id, re.IGNORECASE):
                    normalized_text = ' '.join(text.split())
                    structural_texts.add(normalized_text)
                    break
    
    return structural_texts


def filter_navigation_links_by_anchors(text: str, html_content: str = None, 
                                     min_frequency: int = 5) -> str:
    """
    Filter out navigation links detected through anchor analysis.
    
    This is a more sophisticated approach that analyzes the original HTML
    to detect navigation patterns, then filters the extracted text.
    
    Args:
        text: Extracted text to filter
        html_content: Original HTML content for analysis (if available)
        min_frequency: Minimum frequency for navigation detection
        
    Returns:
        Text with navigation links filtered out
    """
    if not text:
        return text
    
    navigation_texts = set()
    
    # If HTML is available, use anchor analysis
    if html_content:
        # Method 1: Frequency-based detection
        freq_navigation = identify_navigation_links(html_content, min_frequency)
        navigation_texts.update(freq_navigation)
        
        # Method 2: Structural pattern detection  
        structural_navigation = identify_structural_navigation(html_content)
        navigation_texts.update(structural_navigation)
    
    # Fallback: Use known SEC navigation patterns if no HTML available
    if not navigation_texts:
        navigation_texts = {
            'Table of Contents',
            'Index to Financial Statements', 
            'Index to Exhibits'
        }
    
    # Filter text lines
    if not navigation_texts:
        return text
    
    lines = text.split('\n')
    filtered_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        
        # Check if line matches any identified navigation text
        should_filter = False
        for nav_text in navigation_texts:
            if stripped_line == nav_text:
                should_filter = True
                break
        
        if not should_filter:
            filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)


def get_navigation_analysis(html_content: str) -> Dict:
    """
    Get detailed analysis of navigation patterns for debugging.
    
    Args:
        html_content: HTML content to analyze
        
    Returns:
        Dict with navigation analysis details
    """
    if not html_content:
        return {'error': 'No HTML content provided'}
    
    # Run both detection methods
    freq_navigation = identify_navigation_links(html_content, min_frequency=3)
    structural_navigation = identify_structural_navigation(html_content)
    
    # Get frequency counts for all internal links
    soup = BeautifulSoup(html_content, 'html.parser')
    link_counts = Counter()
    
    for link in soup.find_all('a', href=True):
        href = link.get('href', '').strip()
        text = link.get_text().strip()
        
        if href.startswith('#') and text:
            normalized_text = ' '.join(text.split())
            link_counts[normalized_text] += 1
    
    return {
        'frequency_based': list(freq_navigation),
        'structural_based': list(structural_navigation),
        'combined': list(freq_navigation | structural_navigation),
        'all_link_frequencies': dict(link_counts.most_common(20)),
        'total_internal_links': sum(link_counts.values()),
        'unique_link_texts': len(link_counts)
    }