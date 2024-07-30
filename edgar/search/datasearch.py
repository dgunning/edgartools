import hashlib
import re
from functools import lru_cache
from typing import List, Dict, Callable, Any

import pyarrow as pa
from rapidfuzz import fuzz
from unidecode import unidecode


class FastSearch:
    def __init__(self, data: pa.Table, columns: List[str], preprocess_func: Callable[[str], str] = None,
                 score_func: Callable[[str, str, str], float] = None):
        self.data = data
        self.columns = columns
        self.preprocess = preprocess_func or self._default_preprocess
        self.calculate_score = score_func or self._default_calculate_score
        self.indices = {column: self._build_index(column) for column in columns}

        # Calculate and store the hash of the data structure
        self._data_hash = self._compute_data_hash()

    @staticmethod
    def _default_preprocess(text: str) -> str:
        text = unidecode(text.lower())
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    def _build_index(self, column: str) -> Dict[str, List[int]]:
        index = {}
        for i, value in enumerate(self.data[column].to_pylist()):
            processed_value = self.preprocess(str(value))
            for word in processed_value.split():
                if word not in index:
                    index[word] = []
                index[word].append(i)
        return index

    @staticmethod
    def _default_calculate_score(query: str, value: str) -> float:
        return fuzz.ratio(query, value)

    def search(self, query: str, top_n: int = 10, threshold: float = 60) -> List[Dict[str, Any]]:
        processed_query = self.preprocess(query)
        query_words = processed_query.split()

        candidate_indices = set()
        for column in self.columns:
            for word in query_words:
                candidate_indices.update(self.indices[column].get(word, []))

            if len(query) <= 5:  # Assume it's a ticker query
                for indexed_word in self.indices[column]:
                    if indexed_word.startswith(query.lower()):
                        candidate_indices.update(self.indices[column][indexed_word])

        scores = []
        for idx in candidate_indices:
            record = {column: self.data[column][idx].as_py() for column in self.data.schema.names}
            best_score = max(
                self.calculate_score(processed_query, self.preprocess(str(record[column])), column) for column in
                self.columns)
            if best_score >= threshold:
                record['score'] = best_score
                scores.append(record)

        return sorted(scores, key=lambda x: x['score'], reverse=True)[:top_n]

    def _compute_data_hash(self) -> int:
        # Create a string representation of the data structure
        data_repr = f"Shape: {self.data.shape}, "
        data_repr += f"Columns: {','.join(self.data.column_names)}, "
        data_repr += f"Types: {','.join(str(field.type) for field in self.data.schema)}, "
        data_repr += f"Index Columns: {','.join(self.columns)}"

        # Use SHA256 to create a hash of the data representation
        return int(hashlib.sha256(data_repr.encode()).hexdigest(), 16)

    def __hash__(self) -> int:
        return self._data_hash

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, FastSearch):
            return NotImplemented
        return self._data_hash == other._data_hash


def create_search_index(data: pa.Table, columns: List[str], preprocess_func: Callable[[str], str] = None,
                        score_func: Callable[[str, str, str], float] = None) -> FastSearch:
    return FastSearch(data, columns, preprocess_func, score_func)


def search(index: FastSearch, query: str, top_n: int = 10) -> List[Dict[str, str]]:
    return index.search(query, top_n)


@lru_cache(maxsize=128)
def cached_search(index: FastSearch, query: str, top_n: int = 10):
    return index.search(query, top_n)


# Example usage for company and ticker search
def company_ticker_preprocess(text: str) -> str:
    text = FastSearch._default_preprocess(text)
    common_terms = ['llc', 'inc', 'corp', 'ltd', 'limited', 'company']
    return ' '.join(word for word in text.split() if word not in common_terms)


def company_ticker_score(query: str, value: str, column: str) -> float:
    query = query.upper()
    value = value.upper()

    # Check if it's likely a ticker (5 characters or less)
    if len(query) <= 5 and column == 'ticker':
        if query == value:
            return 100  # Exact match
        elif value.startswith(query):
            return 90 + (10 * len(query) / len(value))  # Partial match, score based on completeness
        else:
            return 0  # No match for tickers
    else:
        # For company names, use the default scoring method
        return FastSearch._default_calculate_score(query, value)


def preprocess_company_name(company_name: str) -> str:
    company_name = unidecode(company_name.lower())
    company_name = re.sub(r'[^\w\s]', '', company_name)
    company_name = re.sub(r'\s+', ' ', company_name).strip()
    return company_name



