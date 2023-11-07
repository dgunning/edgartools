from functools import lru_cache

import pandas as pd

from edgar.core import get_resource, Result

data_dir = get_resource('data')

__all__ = [
    'Gaap',
    'get_gaap',
    'exists_in_gaap'
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


def exists_in_gaap(prefix: str, name: str) -> bool:
    """return True if the prefix and name exists in gaap"""
    try:
        gaap = Gaap.load()
        gaap_item = f"{prefix}:{name}"
        return Result.Ok(value=gaap_item in gaap)
    except TypeError as err:
        return Result.Fail(f"Cannot load the GAAP data .. error was {err}")
    except FileNotFoundError as err:
        return Result.Fail(f"Cannot load the GAAP data .. {err}")


@lru_cache(maxsize=2)
def get_gaap():
    return Gaap.load()
