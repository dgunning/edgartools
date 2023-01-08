from pathlib import Path
import pandas as pd

here = Path(__file__).parent

__all__ = [
    'Gaap',
    'gaap'
]


class Gaap:

    def __init__(self,
                 gaap_data: pd.DataFrame):
        self.data = gaap_data

    @classmethod
    def load(cls):
        data = pd.read_csv(here / 'data' / 'GAAP_Taxonomy_2022.csv')
        return Gaap(gaap_data=data)

    def __contains__(self, item: str):
        parts = item.split(":")
        if len(parts) == 2:
            prefix, name = parts[0], parts[1]
            return prefix in self.data.prefix.unique() and name in self.data.name.unique()
        elif len(parts) == 1:
            return item in self.data.prefix.unique()


gaap = Gaap.load()
