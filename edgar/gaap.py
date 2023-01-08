import pandas as pd
from edgar.core import get_resource
from functools import lru_cache

data_dir = get_resource('data')

__all__ = [
    'Gaap',
    'get_gaap'
]


class Gaap:
    """
    Contains information about GAAP
    """

    def __init__(self,
                 gaap_data: pd.DataFrame):
        self.data = gaap_data

    @classmethod
    def load(cls):
        data = pd.read_csv(data_dir / 'GAAP_Taxonomy_2022.csv')
        return Gaap(gaap_data=data)

    def __contains__(self, item: str):
        parts = item.split(":")
        if len(parts) == 2:
            prefix, name = parts[0], parts[1]
            return prefix in self.data.prefix.unique() and name in self.data.name.unique()
        elif len(parts) == 1:
            return item in self.data.prefix.unique()


@lru_cache(maxsize=2)
def get_gaap():
    return Gaap.load()
