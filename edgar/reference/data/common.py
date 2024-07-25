import sys
from functools import lru_cache

import pandas as pd
import pyarrow.parquet as pq

# Dynamic import based on Python version
if sys.version_info >= (3, 9):
    from importlib import resources
else:
    import importlib_resources as resources

__all__ = ['read_parquet_from_package', 'read_pyarrow_from_package', 'read_csv_from_package']


@lru_cache(maxsize=1)
def read_parquet_from_package(parquet_filename: str):
    package_name = 'edgar.reference.data'

    with resources.path(package_name, parquet_filename) as parquet_path:
        df = pd.read_parquet(parquet_path)

    return df


def read_pyarrow_from_package(parquet_filename: str):
    package_name = 'edgar.reference.data'

    with resources.path(package_name, parquet_filename) as parquet_path:
        # Read a pyarrow table from a parquet file
        table = pq.read_table(parquet_path)
    return table


@lru_cache(maxsize=1)
def read_csv_from_package(csv_filename: str):
    package_name = 'edgar.reference.data'

    with resources.path(package_name, csv_filename) as csv_path:
        df = pd.read_csv(csv_path)

    return df
