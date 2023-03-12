import re
from typing import List, Callable

import pandas as pd
import textdistance
from rank_bm25 import BM25Okapi
from rich import box
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel

from edgar._markdown import convert_table
from edgar._rich import repr_rich

PUNCTUATION = re.compile('[%s]' % re.escape(r"""!"#&'()*+,-/:;<=>?@[\]^`{|}~"""))

__all__ = [
    'SimilaritySearchIndex',
    'SearchResults',
    'BM25SearchIndex',
    'preprocess'
]


class SimilaritySearchIndex:

    def __init__(self,
                 data: pd.DataFrame,
                 search_column: str):
        self.data: pd.DataFrame = data
        self._search_column = search_column

    def similar(self,
                query: str,
                threshold=0.6,
                topn=20):
        query = query.lower()
        df = (self
              .data.assign(match=self.data[self._search_column].apply(textdistance.jaro, s2=query).round(2))
              )
        df = df[df.match > threshold]
        df['matches_start'] = df[self._search_column].str.startswith(query[0])
        df = (df.sort_values(['match'], ascending=[False]).head(topn)
              .sort_values(['matches_start', 'match'], ascending=[False, False]))
        cols = [col for col in df if col not in [self._search_column, 'matches_start']]
        return df[cols]

    def __repr__(self):
        return f"SimilaritySearchIndex(search_column='{self.search_column}')"


Corpus = List[str]


def tokenize(text):
    return text.split()


def lowercase_filter(tokens):
    return [token.lower() for token in tokens]


def punctuation_filter(tokens):
    return [PUNCTUATION.sub('', token) for token in tokens]


STOPWORDS = set(['the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have',
                 'i', 'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you',
                 'do', 'at', 'this', 'but', 'his', 'by', 'from'])


def stopword_filter(tokens):
    return [token for token in tokens if token not in STOPWORDS]


def convert_items_to_tokens(text: str):
    """Change 'Item 4.' to item_4. This keeps this in the filnal text"""
    return re.sub(r"item\s+(\d+\.\d+|\d+)\.?", r"item_\1", text, flags=re.IGNORECASE)


def numeric_shape(tokens: List[str]) -> List[str]:
    """Replace numbers with xx.x """
    toks = []
    for token in tokens:
        if re.fullmatch(r"(\d+[\d,.]*)%?|([,.]\d+)%?", token):
            toks.append(re.sub(r'\d', 'x', token))
        else:
            toks.append(token)
    return toks


def preprocess(text: str):
    text = text.lower()
    text = convert_items_to_tokens(text)
    tokens = tokenize(text)
    tokens = punctuation_filter(tokens)
    tokens = stopword_filter(tokens)
    tokens = numeric_shape(tokens)
    return tokens


def preprocess_documents(documents: List[str]) -> Corpus:
    return [preprocess(document) for document in documents]


class SearchResults:

    def __init__(self,
                 query: str,
                 result_sections: List[str],
                 tables: bool = True
                 ):
        self.query: str = query
        self.result_sections: List[str] = result_sections
        self._show_tables = tables

    def __len__(self):
        return len(self.result_sections)

    def __rich__(self):
        _md = ""
        renderables = []
        title = f"Search results for '{self.query}'"
        for section in self.result_sections:
            if section.startswith("|  |") and self._show_tables:
                table = convert_table(section)
                renderables.append(table)
            else:
                renderables.append(Markdown(section + "\n\n---"))
        return Panel(
            Group(*renderables), title=title, subtitle=title, box=box.ROUNDED
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class BM25SearchIndex:

    def __init__(self,
                 document_objs: List[object],
                 text_fn: Callable = None):
        if text_fn:
            self.corpus: Corpus = [preprocess(text_fn(doc)) for doc in document_objs]
        else:
            self.corpus: Corpus = [preprocess(doc) for doc in document_objs]
        self.document_objs = document_objs
        self.bm25: BM25Okapi = BM25Okapi(self.corpus)

    def __len__(self):
        return len(self.document_objs)

    def search(self,
               query: str,
               tables: bool = True):
        preprocessed_query = preprocess(query)
        scores = self.bm25.get_scores(preprocessed_query)
        doc_scores = zip(self.document_objs, scores)
        doc_scores_sorted = sorted([doc for doc in doc_scores if doc[1] > 0], key=lambda t: t[1])[::-1]
        return SearchResults(query=query,
                             result_sections=[doc[0] for doc in doc_scores_sorted if doc[1] > 0],
                             tables=tables)
