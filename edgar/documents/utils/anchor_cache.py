"""
Lightweight anchor analysis cache to avoid re-parsing HTML.

This provides a middle-ground approach that caches anchor analysis results
while minimizing memory overhead.
"""
import re
from typing import Dict, Set, Optional
from collections import Counter
import hashlib
import pickle
from pathlib import Path


class AnchorCache:
    """
    Cache for anchor link analysis results.
    
    Stores navigation patterns by HTML hash to avoid re-analysis.
    """
    
    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path.home() / '.edgar_cache' / 'anchors'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache = {}  # In-memory cache for current session
    
    def _get_html_hash(self, html_content: str) -> str:
        """Get hash of HTML content for caching."""
        return hashlib.md5(html_content.encode('utf-8')).hexdigest()
    
    def get_navigation_patterns(self, html_content: str) -> Optional[Set[str]]:
        """
        Get cached navigation patterns for HTML content.
        
        Args:
            html_content: HTML to analyze
            
        Returns:
            Set of navigation patterns or None if not cached
        """
        html_hash = self._get_html_hash(html_content)
        
        # Check in-memory cache first
        if html_hash in self._memory_cache:
            return self._memory_cache[html_hash]
        
        # Check disk cache
        cache_file = self.cache_dir / f"{html_hash}.pkl"
        if cache_file.exists():
            try:
                with open(cache_file, 'rb') as f:
                    patterns = pickle.load(f)
                self._memory_cache[html_hash] = patterns
                return patterns
            except:
                # Corrupted cache file, remove it
                cache_file.unlink(missing_ok=True)
        
        return None
    
    def cache_navigation_patterns(self, html_content: str, patterns: Set[str]) -> None:
        """
        Cache navigation patterns for HTML content.
        
        Args:
            html_content: HTML content
            patterns: Navigation patterns to cache
        """
        html_hash = self._get_html_hash(html_content)
        
        # Store in memory
        self._memory_cache[html_hash] = patterns
        
        # Store on disk (async to avoid blocking)
        try:
            cache_file = self.cache_dir / f"{html_hash}.pkl"
            with open(cache_file, 'wb') as f:
                pickle.dump(patterns, f)
        except:
            # Ignore cache write errors
            pass
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._memory_cache.clear()
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink(missing_ok=True)


# Global cache instance
_anchor_cache = AnchorCache()


def get_cached_navigation_patterns(html_content: str, 
                                 force_analyze: bool = False) -> Set[str]:
    """
    Get navigation patterns with caching.
    
    Args:
        html_content: HTML to analyze
        force_analyze: Force re-analysis even if cached
        
    Returns:
        Set of navigation link texts to filter
    """
    if not force_analyze:
        cached_patterns = _anchor_cache.get_navigation_patterns(html_content)
        if cached_patterns is not None:
            return cached_patterns
    
    # Need to analyze - use minimal approach
    patterns = _analyze_navigation_minimal(html_content)
    
    # Cache results
    _anchor_cache.cache_navigation_patterns(html_content, patterns)
    
    return patterns


def _analyze_navigation_minimal(html_content: str, min_frequency: int = 5) -> Set[str]:
    """
    Minimal navigation analysis using regex instead of full HTML parsing.
    
    This avoids BeautifulSoup overhead by using regex to find anchor patterns.
    """
    patterns = set()
    
    # Find all anchor links with regex (faster than BeautifulSoup)
    anchor_pattern = re.compile(r'<a[^>]*href\s*=\s*["\']#([^"\']*)["\'][^>]*>(.*?)</a>', 
                               re.IGNORECASE | re.DOTALL)
    
    link_counts = Counter()
    
    for match in anchor_pattern.finditer(html_content):
        anchor_id = match.group(1).strip()
        link_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()  # Remove HTML tags
        link_text = ' '.join(link_text.split())  # Normalize whitespace
        
        if link_text and len(link_text) < 100:  # Reasonable link text length
            link_counts[link_text] += 1
    
    # Add frequently occurring links
    for text, count in link_counts.items():
        if count >= min_frequency:
            patterns.add(text)
    
    return patterns


def filter_with_cached_patterns(text: str, html_content: str = None) -> str:
    """
    Filter text using cached navigation patterns.
    
    Preserves first occurrences of patterns (document structure headers)
    while filtering out repeated navigation links.
    
    Args:
        text: Text to filter
        html_content: HTML for pattern analysis (optional)
        
    Returns:
        Filtered text
    """
    if not text:
        return text
    
    # Get patterns (cached or analyze)
    if html_content:
        patterns = get_cached_navigation_patterns(html_content)
    else:
        # Fallback to common SEC patterns
        patterns = {
            'Table of Contents',
            'Index to Financial Statements',
            'Index to Exhibits'
        }
    
    if not patterns:
        return text
    
    # Smart filtering: preserve first few occurrences, filter out repetitions
    lines = text.split('\n')
    filtered_lines = []
    pattern_counts = {}  # Track how many times we've seen each pattern
    
    # Allow first few occurrences of each pattern (document structure headers)
    max_allowed_per_pattern = 2  # Allow up to 2 occurrences of each pattern
    
    for line in lines:
        stripped_line = line.strip()
        
        if stripped_line in patterns:
            # This line matches a navigation pattern
            count = pattern_counts.get(stripped_line, 0)
            
            if count < max_allowed_per_pattern:
                # Keep this occurrence (likely a document structure header)
                filtered_lines.append(line)
                pattern_counts[stripped_line] = count + 1
            # else: skip this line (it's a repetitive navigation link)
        else:
            # Not a navigation pattern, always keep
            filtered_lines.append(line)
    
    return '\n'.join(filtered_lines)