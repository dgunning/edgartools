from functools import lru_cache
from importlib import resources

import pandas as pd
import pyarrow.parquet as pq

__all__ = ['read_parquet_from_package', 'read_pyarrow_from_package', 'read_csv_from_package']


@lru_cache(maxsize=1)
def read_parquet_from_package(parquet_filename: str):
    package_name = 'edgar.reference.data'

    ref = resources.files(package_name).joinpath(parquet_filename)
    with resources.as_file(ref) as parquet_path:
        df = pd.read_parquet(parquet_path)

    return df


def read_pyarrow_from_package(parquet_filename: str):
    package_name = 'edgar.reference.data'

    ref = resources.files(package_name).joinpath(parquet_filename)
    with resources.as_file(ref) as parquet_path:
        # Read a pyarrow table from a parquet file
        table = pq.read_table(parquet_path)
    return table


def read_csv_from_package(csv_filename: str, **pandas_kwargs):
    package_name = 'edgar.reference.data'

    ref = resources.files(package_name).joinpath(csv_filename)
    with resources.as_file(ref) as csv_path:
        df = pd.read_csv(csv_path, **pandas_kwargs)

    return df
