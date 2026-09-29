"""
Tests for text preprocessing utilities (edgar.documents.ranking.preprocessing).

Pure text processing — no network calls.
"""

from edgar.documents.ranking.preprocessing import (
    preprocess_text,
    tokenize,
    extract_query_terms,
    normalize_financial_term,
    get_ngrams,
    STOPWORDS,
)


class TestPreprocessText:

    def test_lowercase(self):
        assert preprocess_text("Hello World") == "hello world"

    def test_no_lowercase(self):
        assert preprocess_text("Hello World", lowercase=False) == "Hello World"

    def test_whitespace_normalized(self):
        assert preprocess_text("  hello   world  ") == "hello world"

    def test_remove_punctuation(self):
        result = preprocess_text("price: $5.00!", remove_punctuation=True)
        assert ":" not in result
        assert "!" not in result

    def test_empty_string(self):
        assert preprocess_text("") == ""

    def test_none_returns_empty(self):
        assert preprocess_text(None) == ""


class TestTokenize:

    def test_basic_tokenization(self):
        tokens = tokenize("total revenue increased")
        assert "total" in tokens
        assert "revenue" in tokens

    def test_min_token_length(self):
        tokens = tokenize("a big deal", min_token_length=2)
        assert "a" not in tokens
        assert "big" in tokens

    def test_remove_stopwords(self):
        tokens = tokenize("the total revenue for the year", remove_stopwords=True)
        assert "the" not in tokens
        assert "revenue" in tokens

    def test_empty_string(self):
        assert tokenize("") == []

    def test_none_returns_empty(self):
        assert tokenize(None) == []

    def test_financial_terms_kept(self):
        tokens = tokenize("revenue $5B growth")
        assert any("5" in t for t in tokens)


class TestExtractQueryTerms:

    def test_extracts_amounts(self):
        terms = extract_query_terms("revenue of $5B in 2024")
        assert "$5B" in terms

    def test_extracts_percentages(self):
        terms = extract_query_terms("grew 15% year over year")
        assert "15%" in terms

    def test_extracts_years(self):
        terms = extract_query_terms("fiscal year 2024")
        assert "2024" in terms

    def test_extracts_item_references(self):
        terms = extract_query_terms("see Item 1A for risk factors")
        assert any("item" in t.lower() and "1a" in t.lower() for t in terms)

    def test_no_duplicates(self):
        terms = extract_query_terms("2024 revenue 2024")
        assert terms.count("2024") == 1


class TestNormalizeFinancialTerm:

    def test_remove_commas(self):
        assert normalize_financial_term("5,000,000") == "5000000"

    def test_billion_to_b(self):
        assert normalize_financial_term("$5 billion") == "$5b"

    def test_million_to_m(self):
        assert normalize_financial_term("$10 million") == "$10m"

    def test_thousand_to_k(self):
        assert normalize_financial_term("$100 thousand") == "$100k"

    def test_item_reference(self):
        assert normalize_financial_term("Item 1A") == "item1a"

    def test_whitespace_stripped(self):
        assert normalize_financial_term("  hello  world  ") == "hello world"


class TestGetNgrams:

    def test_bigrams(self):
        result = get_ngrams(["total", "revenue", "increased"], n=2)
        assert "total revenue" in result
        assert "revenue increased" in result
        assert len(result) == 2

    def test_trigrams(self):
        result = get_ngrams(["a", "b", "c", "d"], n=3)
        assert "a b c" in result
        assert "b c d" in result
        assert len(result) == 2

    def test_too_few_tokens(self):
        assert get_ngrams(["only"], n=2) == []

    def test_exact_n_tokens(self):
        result = get_ngrams(["a", "b"], n=2)
        assert result == ["a b"]

    def test_empty_list(self):
        assert get_ngrams([], n=2) == []


class TestStopwords:

    def test_common_stopwords_present(self):
        assert "the" in STOPWORDS
        assert "and" in STOPWORDS
        assert "of" in STOPWORDS

    def test_financial_terms_not_in_stopwords(self):
        # Financial terms should NOT be stopwords
        assert "revenue" not in STOPWORDS
        assert "income" not in STOPWORDS
        assert "total" not in STOPWORDS
