"""
Text preprocessing for search.

Provides tokenization and text normalization for BM25 and semantic analysis.
"""

import re
from typing import List, Set


# Common English stopwords (minimal set for financial documents)
# We keep many financial terms that might be stopwords in other contexts
STOPWORDS: Set[str] = {
    'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for',
    'from', 'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on',
    'that', 'the', 'to', 'was', 'will', 'with'
}


def preprocess_text(text: str,
                   lowercase: bool = True,
                   remove_punctuation: bool = False) -> str:
    """
    Preprocess text for search.

    Args:
        text: Raw text
        lowercase: Convert to lowercase
        remove_punctuation: Remove punctuation (keep for financial data)

    Returns:
        Preprocessed text
    """
    if not text:
        return ""

    # Normalize whitespace
    text = ' '.join(text.split())

    # Lowercase (important for BM25 matching)
    if lowercase:
        text = text.lower()

    # Optionally remove punctuation (usually keep for "$5B", "Item 1A", etc.)
    if remove_punctuation:
        text = re.sub(r'[^\w\s]', ' ', text)
        text = ' '.join(text.split())  # Clean up extra spaces

    return text


def tokenize(text: str,
            remove_stopwords: bool = False,
            min_token_length: int = 2) -> List[str]:
    """
    Tokenize text for BM25 indexing.

    Args:
        text: Text to tokenize
        remove_stopwords: Remove common stopwords
        min_token_length: Minimum token length to keep

    Returns:
        List of tokens
    """
    if not text:
        return []

    # Split on whitespace and punctuation boundaries
    # Keep alphanumeric + some special chars for financial terms
    tokens = re.findall(r'\b[\w$%]+\b', text.lower())

    # Filter by length
    tokens = [t for t in tokens if len(t) >= min_token_length]

    # Optionally remove stopwords
    if remove_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS]

    return tokens


def extract_query_terms(query: str) -> List[str]:
    """
    Extract important terms from query for boosting.

    Identifies key financial terms, numbers, and important phrases.

    Args:
        query: Search query

    Returns:
        List of important query terms
    """
    # Tokenize
    tokens = tokenize(query, remove_stopwords=True)

    # Extract important patterns
    important = []

    # Financial amounts: $5B, $1.2M, etc.
    amounts = re.findall(r'\$[\d,.]+[BMK]?', query, re.IGNORECASE)
    important.extend(amounts)

    # Percentages: 15%, 3.5%
    percentages = re.findall(r'\d+\.?\d*%', query)
    important.extend(percentages)

    # Years: 2023, 2024
    years = re.findall(r'\b(19|20)\d{2}\b', query)
    important.extend(years)

    # Item references: Item 1A, Item 7
    items = re.findall(r'item\s+\d+[a-z]?', query, re.IGNORECASE)
    important.extend(items)

    # Add all tokens
    important.extend(tokens)

    # Remove duplicates while preserving order
    seen = set()
    result = []
    for term in important:
        term_lower = term.lower()
        if term_lower not in seen:
            seen.add(term_lower)
            result.append(term)

    return result


def normalize_financial_term(term: str) -> str:
    """
    Normalize financial terms for consistent matching.

    Examples:
        "$5 billion" -> "$5b"
        "5,000,000" -> "5000000"
        "Item 1A" -> "item1a"

    Args:
        term: Financial term

    Returns:
        Normalized term
    """
    term = term.lower().strip()

    # Remove commas from numbers
    term = term.replace(',', '')

    # Normalize billion/million/thousand
    term = re.sub(r'\s*billion\b', 'b', term)
    term = re.sub(r'\s*million\b', 'm', term)
    term = re.sub(r'\s*thousand\b', 'k', term)

    # Remove spaces in compound terms
    term = re.sub(r'(item|section|part)\s+(\d+[a-z]?)', r'\1\2', term)

    # Remove extra whitespace
    term = ' '.join(term.split())

    return term


def get_ngrams(tokens: List[str], n: int = 2) -> List[str]:
    """
    Generate n-grams from tokens.

    Useful for phrase matching in BM25.

    Args:
        tokens: List of tokens
        n: N-gram size

    Returns:
        List of n-grams as strings
    """
    if len(tokens) < n:
        return []

    ngrams = []
    for i in range(len(tokens) - n + 1):
        ngram = ' '.join(tokens[i:i + n])
        ngrams.append(ngram)

    return ngrams
