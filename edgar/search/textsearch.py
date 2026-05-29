import re
from typing import Callable, List, Tuple, Optional

import pandas as pd
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from edgar._markdown import convert_table
from edgar.richtools import repr_rich

PUNCTUATION = re.compile('[%s]' % re.escape(r"""!"#&'()*+,-/:;<=>?@[\]^`{|}~"""))

__all__ = [
    'SimilaritySearchIndex',
    'SearchResults',
    'BM25Search',
    'RegexSearch',
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
        import textdistance
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
        return f"SimilaritySearchIndex(search_column='{self._search_column}')"


Corpus = List[List[str]]


def tokenize(text):
    return text.split()


def lowercase_filter(tokens):
    return [token.lower() for token in tokens]


def punctuation_filter(tokens):
    return [PUNCTUATION.sub('', token) for token in tokens]


STOPWORDS = {'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i', 'it', 'for', 'not', 'on', 'with', 'he',
             'as', 'you', 'do', 'at', 'this', 'but', 'his', 'by', 'from'}


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


def return_spaces_to_items(tokens: List[str]) -> List[str]:
    toks = []
    pattern = r"item_(\d+(\.\d+)?)"
    for token in tokens:
        if re.fullmatch(pattern, token):
            toks += re.sub(pattern, r"item \1", token).split(" ")
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
    tokens = return_spaces_to_items(tokens)
    return tokens


def preprocess_documents(documents: List[str]) -> Corpus:
    return [preprocess(document) for document in documents]


LocAndDoc = Tuple[int, str]


class DocSection:

    def __init__(self,
                 loc: int,
                 doc: str,
                 score: float = 0.0
                 ):
        self.loc: int = loc
        self.doc: str = doc
        self.score: float = score

    # Make this class sortable by loc
    def __lt__(self, other):
        return self.loc < other.loc

    def __hash__(self):
        return hash(self.doc)

    def json(self):
        return {
            'loc': self.loc,
            'doc': self.doc,
            'score': self.score
        }

    def __repr__(self):
        return f"{self.loc}\n{self.doc}"


class SearchResults:

    def __init__(self,
                 query: str,
                 sections: List[DocSection],
                 tables: bool = True,
                 regex: bool = False
                 ):
        self.query: str = query
        self.sections: List[DocSection] = sections
        self._show_tables = tables
        self._regex = regex
        self._highlight_pattern = self._build_highlight_pattern()

    def __len__(self):
        return len(self.sections)

    @property
    def empty(self):
        return len(self) == 0

    def __getitem__(self, item):
        # return none instead of error
        if 0 > item >= len(self.sections):
            return None
        return self.sections[item]

    def json(self):
        return {
            'query': self.query,
            'sections': [section.json() for section in self.sections],
            'tables': self._show_tables
        }

    # Style applied to matched query terms in the rendered output.
    HIGHLIGHT_STYLE = "bold red"

    def _build_highlight_pattern(self) -> Optional["re.Pattern"]:
        """Compile a regex that matches the query terms, for highlighting.

        For ``regex`` searches the query is itself the pattern. For the default
        BM25 search we highlight each meaningful query word (stopwords removed)
        as a case-insensitive substring, so "repurchase" also lights up
        "repurchases".
        """
        if self._regex:
            try:
                return re.compile(self.query, re.IGNORECASE)
            except re.error:
                return None
        words = [w for w in re.split(r"\s+", self.query.strip()) if w]
        words = [w for w in words if w.lower() not in STOPWORDS]
        if not words:
            return None
        pattern = "|".join(re.escape(word) for word in words)
        return re.compile(pattern, re.IGNORECASE)

    def _highlight(self, text: str) -> "Text":
        """Wrap text in a rich Text with matched query terms styled."""
        rich_text = Text(text)
        if self._highlight_pattern is not None:
            rich_text.highlight_regex(self._highlight_pattern, style=self.HIGHLIGHT_STYLE)
        return rich_text

    def __rich__(self):
        renderables = []
        title = f"Searching for '{self.query}'"
        subtitle = f"{len(self)} result(s)" if not self.empty else "No results"
        sorted_sections = sorted(self.sections, key=lambda s: s.score, reverse=True)
        for doc_section in sorted_sections:
            if doc_section.doc.startswith("|  |") and self._show_tables:
                section = convert_table(doc_section.doc, cell_highlighter=self._highlight)
            else:
                section = self._highlight(doc_section.doc)
            # Title is the section index in the source corpus, not the display rank.
            # Otherwise BM25 (sorts by score) and regex (no score) disagree on what "0" means.
            renderables.append(Panel(section, box=box.ROUNDED, title=f"{doc_section.loc}"))
        return Panel(
            Group(*renderables), title=title, subtitle=subtitle, box=box.SIMPLE
        )

    def __repr__(self):
        return repr_rich(self.__rich__())


class BM25Search:

    def __init__(self,
                 document_objs: List[str],
                 text_fn: Optional[Callable] = None):
        from rank_bm25 import BM25Okapi
        if text_fn:
            self.corpus: Corpus = [BM25Search.preprocess(text_fn(doc)) for doc in document_objs]
        else:
            self.corpus: Corpus = [BM25Search.preprocess(doc) for doc in document_objs]
        self.document_objs = document_objs
        self.bm25: BM25Okapi = BM25Okapi(self.corpus)

    def __len__(self):
        return len(self.document_objs)

    @staticmethod
    def preprocess(text: str):
        text = text.lower()
        text = convert_items_to_tokens(text)
        tokens = tokenize(text)
        tokens = punctuation_filter(tokens)
        tokens = stopword_filter(tokens)
        tokens = numeric_shape(tokens)
        tokens = return_spaces_to_items(tokens)
        return tokens

    def search(self,
               query: str,
               tables: bool = True):
        preprocessed_query = preprocess(query)
        scores = self.bm25.get_scores(preprocessed_query)
        doc_scores = zip(self.document_objs, scores, strict=False)
        # doc_scores_sorted = sorted([doc for doc in doc_scores if doc[1] > 0], key=lambda t: t[1])[::-1]
        # Return the list of location and document
        return SearchResults(query=query,
                             sections=[DocSection(loc=loc, doc=doc_and_score[0], score=doc_and_score[1])
                                       for loc, doc_and_score in enumerate(doc_scores)
                                       if doc_and_score[1] > 0],
                             tables=tables)


class RegexSearch:

    def __init__(self,
                 documents: List[str]):
        self.document_objs = [RegexSearch.preprocess(document) for document in documents]

    def __len__(self):
        return len(self.document_objs)

    @staticmethod
    def preprocess(text: str):
        text = text.replace("&#160;", " ")
        return text

    def search(self,
               query: str,
               tables: bool = True):
        return SearchResults(
            query=query,
            sections=[DocSection(loc=loc, doc=doc)
                      for loc, doc in enumerate(self.document_objs)
                      if re.search(query, doc, flags=re.IGNORECASE)],
            tables=tables,
            regex=True
        )
