import pandas as pd
import textdistance

__all__ = [
    'TextSearchIndex'
]


class TextSearchIndex:

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
              .data.assign(score=self.data[self._search_column].apply(textdistance.jaro, s2=query).round(2))
              )
        df = df[df.score > threshold]
        df['matches_start'] = df[self._search_column].str.startswith(query[0])
        df = (df.sort_values(['score'], ascending=[False]).head(topn)
              .sort_values(['matches_start', 'score'], ascending=[False, False]))
        cols = [col for col in df if col not in [self._search_column, 'matches_start']]
        return df[cols]

    def __repr__(self):
        return f"TextSearchIndex(search_column='{self.search_column}')"
