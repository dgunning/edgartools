"""
HTML preprocessor for cleaning and normalizing HTML before parsing.
"""

import re
from typing import Optional
from edgar.documents.config import ParserConfig


class HTMLPreprocessor:
    """
    Preprocesses HTML to fix common issues and normalize content.
    
    Handles:
    - Character encoding issues
    - Malformed HTML
    - Excessive whitespace
    - Script/style removal
    - Entity normalization
    """
    
    def __init__(self, config: ParserConfig):
        """Initialize preprocessor with configuration."""
        self.config = config
    
    def process(self, html: str) -> str:
        """
        Preprocess HTML content.
        
        Args:
            html: Raw HTML content
            
        Returns:
            Cleaned HTML ready for parsing
        """
        # Remove BOM if present
        if html.startswith('\ufeff'):
            html = html[1:]
        
        # Remove XML declaration if present
        if html.strip().startswith('<?xml'):
            end_of_decl = html.find('?>')
            if end_of_decl != -1:
                html = html[end_of_decl + 2:].lstrip()
        
        # Fix common character encoding issues
        html = self._fix_encoding_issues(html)
        
        # Remove script and style tags
        html = self._remove_script_style(html)
        
        # Normalize entities
        html = self._normalize_entities(html)
        
        # Fix malformed tags
        html = self._fix_malformed_tags(html)
        
        # Normalize whitespace if not preserving
        if not self.config.preserve_whitespace:
            html = self._normalize_whitespace(html)
        
        # Remove empty tags
        html = self._remove_empty_tags(html)
        
        # Fix common HTML issues
        html = self._fix_common_issues(html)
        
        return html
    
    def _fix_encoding_issues(self, html: str) -> str:
        """Fix common character encoding issues."""
        # Replace Windows-1252 characters with Unicode equivalents
        replacements = {
            '\x91': "'",  # Left single quote
            '\x92': "'",  # Right single quote
            '\x93': '"',  # Left double quote
            '\x94': '"',  # Right double quote
            '\x95': '•',  # Bullet
            '\x96': '–',  # En dash
            '\x97': '—',  # Em dash
            '\xa0': ' ',  # Non-breaking space
        }
        
        for old, new in replacements.items():
            html = html.replace(old, new)
        
        # Remove other control characters
        html = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', html)
        
        return html
    
    def _remove_script_style(self, html: str) -> str:
        """Remove script and style tags with content."""
        # Remove script tags and content
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove style tags and content
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove link tags (stylesheets)
        html = re.sub(r'<link[^>]*>', '', html, flags=re.IGNORECASE)
        
        # Remove comments
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        
        # Remove XBRL hidden content - content marked as hidden should not be displayed
        html = re.sub(r'<ix:hidden[^>]*>.*?</ix:hidden>', '', html, flags=re.IGNORECASE | re.DOTALL)
        
        # Remove entire ix:header section which contains XBRL metadata not meant for display
        html = re.sub(r'<ix:header[^>]*>.*?</ix:header>', '', html, flags=re.IGNORECASE | re.DOTALL)
        
        return html
    
    def _normalize_entities(self, html: str) -> str:
        """Normalize HTML entities."""
        # Common entity replacements
        entities = {
            '&nbsp;': ' ',
            '&ensp;': ' ',
            '&emsp;': '  ',
            '&thinsp;': ' ',
            '&#160;': ' ',
            '&#32;': ' ',
            '&zwj;': '',  # Zero-width joiner
            '&zwnj;': '',  # Zero-width non-joiner
            '&#8203;': '',  # Zero-width space
        }
        
        for entity, replacement in entities.items():
            html = html.replace(entity, replacement)
        
        # Fix double-encoded entities
        html = html.replace('&amp;amp;', '&amp;')
        html = html.replace('&amp;nbsp;', ' ')
        html = html.replace('&amp;lt;', '&lt;')
        html = html.replace('&amp;gt;', '&gt;')
        
        return html
    
    def _fix_malformed_tags(self, html: str) -> str:
        """Fix common malformed tag issues."""
        # Fix unclosed br tags
        html = re.sub(r'<br(?![^>]*/)>', '<br/>', html, flags=re.IGNORECASE)
        
        # Fix unclosed img tags
        html = re.sub(r'<img([^>]+)(?<!/)>', r'<img\1/>', html, flags=re.IGNORECASE)
        
        # Fix unclosed input tags
        html = re.sub(r'<input([^>]+)(?<!/)>', r'<input\1/>', html, flags=re.IGNORECASE)
        
        # Fix unclosed hr tags
        html = re.sub(r'<hr(?![^>]*/)>', '<hr/>', html, flags=re.IGNORECASE)
        
        # Fix nested identical tags (common issue)
        html = re.sub(r'<p>\s*<p>', '<p>', html, flags=re.IGNORECASE)
        html = re.sub(r'</p>\s*</p>', '</p>', html, flags=re.IGNORECASE)
        
        return html
    
    def _normalize_whitespace(self, html: str) -> str:
        """Normalize whitespace in HTML."""
        # Replace multiple spaces with single space
        html = re.sub(r'[ \t]+', ' ', html)
        
        # Replace multiple newlines with double newline
        html = re.sub(r'\n{3,}', '\n\n', html)
        
        # Remove spaces around tags
        html = re.sub(r'\s*(<[^>]+>)\s*', r'\1', html)
        
        # Add newlines around block elements for readability
        block_tags = ['div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                     'table', 'tr', 'ul', 'ol', 'li', 'blockquote']
        
        for tag in block_tags:
            html = re.sub(f'(<{tag}[^>]*>)', r'\n\1', html, flags=re.IGNORECASE)
            html = re.sub(f'(</{tag}>)', r'\1\n', html, flags=re.IGNORECASE)
        
        # Clean up excessive newlines
        html = re.sub(r'\n{3,}', '\n\n', html)
        
        return html.strip()
    
    def _remove_empty_tags(self, html: str) -> str:
        """Remove empty tags that don't contribute content."""
        # Tags that can be removed if empty
        removable_tags = ['span', 'div', 'p', 'font', 'b', 'i', 'u', 'strong', 'em']
        
        for tag in removable_tags:
            # Remove empty tags - use word boundary to match complete tag names
            html = re.sub(f'<{tag}\\b[^>]*>\\s*</{tag}>', '', html, flags=re.IGNORECASE)
            
            # Remove self-closing empty tags - use word boundary to match complete tag names
            html = re.sub(f'<{tag}\\b[^>]*/>\\s*', '', html, flags=re.IGNORECASE)
        
        return html
    
    def _fix_common_issues(self, html: str) -> str:
        """Fix other common HTML issues."""
        # Fix multiple consecutive <br> tags
        html = re.sub(r'(<br\s*/?>[\s\n]*){3,}', '<br/><br/>', html, flags=re.IGNORECASE)
        
        # Fix space before punctuation
        html = re.sub(r'\s+([.,;!?])', r'\1', html)
        
        # Fix missing spaces after punctuation
        html = re.sub(r'([.,;!?])([A-Z])', r'\1 \2', html)
        
        # Remove zero-width spaces
        html = html.replace('\u200b', '')
        html = html.replace('\ufeff', '')
        
        # Fix common typos in tags
        html = html.replace('<tabel', '<table')
        html = html.replace('</tabel>', '</table>')
        
        return html