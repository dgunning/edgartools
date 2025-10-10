"""
HTML preprocessor for cleaning and normalizing HTML before parsing.
"""

import re

from edgar.documents.config import ParserConfig
from edgar.documents.utils.html_utils import remove_xml_declaration


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
        
        # Pre-compile regex patterns for performance
        self._compiled_patterns = self._compile_patterns()
    
    def _compile_patterns(self):
        """Pre-compile frequently used regex patterns."""
        return {
            # Encoding and cleanup
            'control_chars': re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]'),

            # Script/style removal
            'script_tags': re.compile(r'<script[^>]*>.*?</script>', re.IGNORECASE | re.DOTALL),
            'style_tags': re.compile(r'<style[^>]*>.*?</style>', re.IGNORECASE | re.DOTALL),
            'link_tags': re.compile(r'<link[^>]*>', re.IGNORECASE),
            'comments': re.compile(r'<!--.*?-->', re.DOTALL),
            'ix_hidden': re.compile(r'<ix:hidden[^>]*>.*?</ix:hidden>', re.IGNORECASE | re.DOTALL),
            'ix_header': re.compile(r'<ix:header[^>]*>.*?</ix:header>', re.IGNORECASE | re.DOTALL),

            # Malformed tags
            'br_tags': re.compile(r'<br(?![^>]*/)>', re.IGNORECASE),
            'img_tags': re.compile(r'<img([^>]+)(?<!/)>', re.IGNORECASE),
            'input_tags': re.compile(r'<input([^>]+)(?<!/)>', re.IGNORECASE),
            'hr_tags': re.compile(r'<hr(?![^>]*/)>', re.IGNORECASE),
            'nested_p_open': re.compile(r'<p>\s*<p>', re.IGNORECASE),
            'nested_p_close': re.compile(r'</p>\s*</p>', re.IGNORECASE),

            # Whitespace normalization
            'multiple_spaces': re.compile(r'[ \t]+'),
            'multiple_newlines': re.compile(r'\n{3,}'),
            'spaces_around_tags': re.compile(r'\s*(<[^>]+>)\s*'),

            # Block element newlines - combined pattern for opening tags
            'block_open_tags': re.compile(
                r'(<(?:div|p|h[1-6]|table|tr|ul|ol|li|blockquote)[^>]*>)',
                re.IGNORECASE
            ),
            # Block element newlines - combined pattern for closing tags
            'block_close_tags': re.compile(
                r'(</(?:div|p|h[1-6]|table|tr|ul|ol|li|blockquote)>)',
                re.IGNORECASE
            ),

            # Empty tags removal - combined pattern for all removable tags
            'empty_tags': re.compile(
                r'<(?:span|div|p|font|b|i|u|strong|em)\b[^>]*>\s*</(?:span|div|p|font|b|i|u|strong|em)>',
                re.IGNORECASE
            ),
            'empty_self_closing': re.compile(
                r'<(?:span|div|p|font|b|i|u|strong|em)\b[^>]*/>\s*',
                re.IGNORECASE
            ),

            # Common issues
            'multiple_br': re.compile(r'(<br\s*/?>[\s\n]*){3,}', re.IGNORECASE),
            'space_before_punct': re.compile(r'\s+([.,;!?])'),
            'missing_space_after_punct': re.compile(r'([.,;!?])([A-Z])'),
        }
    
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
        html = remove_xml_declaration(html)
        
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
        html = self._compiled_patterns['control_chars'].sub('', html)
        
        return html
    
    def _remove_script_style(self, html: str) -> str:
        """Remove script and style tags with content."""
        # Use pre-compiled patterns for better performance
        html = self._compiled_patterns['script_tags'].sub('', html)
        html = self._compiled_patterns['style_tags'].sub('', html)
        html = self._compiled_patterns['link_tags'].sub('', html)
        html = self._compiled_patterns['comments'].sub('', html)
        html = self._compiled_patterns['ix_hidden'].sub('', html)
        html = self._compiled_patterns['ix_header'].sub('', html)

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
        # Use pre-compiled patterns for better performance
        html = self._compiled_patterns['br_tags'].sub('<br/>', html)
        html = self._compiled_patterns['img_tags'].sub(r'<img\1/>', html)
        html = self._compiled_patterns['input_tags'].sub(r'<input\1/>', html)
        html = self._compiled_patterns['hr_tags'].sub('<hr/>', html)
        html = self._compiled_patterns['nested_p_open'].sub('<p>', html)
        html = self._compiled_patterns['nested_p_close'].sub('</p>', html)

        return html
    
    def _normalize_whitespace(self, html: str) -> str:
        """Normalize whitespace in HTML."""
        # Use pre-compiled patterns for better performance
        # Replace multiple spaces with single space
        html = self._compiled_patterns['multiple_spaces'].sub(' ', html)

        # Replace multiple newlines with double newline
        html = self._compiled_patterns['multiple_newlines'].sub('\n\n', html)

        # Remove spaces around tags
        html = self._compiled_patterns['spaces_around_tags'].sub(r'\1', html)

        # Add newlines around block elements for readability
        # Using combined patterns instead of looping over individual tags
        html = self._compiled_patterns['block_open_tags'].sub(r'\n\1', html)
        html = self._compiled_patterns['block_close_tags'].sub(r'\1\n', html)

        # Clean up excessive newlines (apply again after adding newlines)
        html = self._compiled_patterns['multiple_newlines'].sub('\n\n', html)

        return html.strip()
    
    def _remove_empty_tags(self, html: str) -> str:
        """Remove empty tags that don't contribute content."""
        # Use pre-compiled combined patterns instead of looping
        html = self._compiled_patterns['empty_tags'].sub('', html)
        html = self._compiled_patterns['empty_self_closing'].sub('', html)

        return html
    
    def _fix_common_issues(self, html: str) -> str:
        """Fix other common HTML issues."""
        # Use pre-compiled patterns for better performance
        html = self._compiled_patterns['multiple_br'].sub('<br/><br/>', html)
        html = self._compiled_patterns['space_before_punct'].sub(r'\1', html)
        html = self._compiled_patterns['missing_space_after_punct'].sub(r'\1 \2', html)

        # Remove zero-width spaces (simple string replace is faster than regex)
        html = html.replace('\u200b', '')
        html = html.replace('\ufeff', '')

        # Fix common typos in tags (simple string replace is faster than regex)
        html = html.replace('<tabel', '<table')
        html = html.replace('</tabel>', '</table>')

        return html