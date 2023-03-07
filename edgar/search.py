import pandas as pd
import textdistance
from rank_bm25 import BM25Okapi
from typing import List, Callable
import re
import string

PUNCTUATION = re.compile('[%s]' % re.escape(string.punctuation))

__all__ = [
    'SimilaritySearchIndex'
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


def preprocess(text: str):
    tokens = tokenize(text)
    tokens = lowercase_filter(tokens)
    tokens = punctuation_filter(tokens)
    tokens = stopword_filter(tokens)
    return tokens


def preprocess_documents(documents: List[str]) -> Corpus:
    return [preprocess(document) for document in documents]


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

    def search(self, query: str, topn=20):
        preprocessed_query = preprocess(query)
        scores = self.bm25.get_scores(preprocessed_query)
        doc_scores = zip(self.document_objs, scores)
        doc_scores_sorted = sorted([doc for doc in doc_scores if doc[1] > 0], key=lambda t: t[1])[::-1]
        return [doc[0] for doc in doc_scores_sorted if doc[1] > 0]
