from functools import lru_cache
import sys
import pandas as pd

# Dynamic import based on Python version
if sys.version_info >= (3, 9):
    from importlib import resources
else:
    import importlib_resources as resources


@lru_cache(maxsize=1)
def read_parquet_from_package(parquet_filename: str):
    package_name = 'edgar.reference.data'

    with resources.path(package_name, parquet_filename) as parquet_path:
        df = pd.read_parquet(parquet_path)

    return df


@lru_cache(maxsize=1)
def read_csv_from_package(csv_filename: str):
    package_name = 'edgar.reference.data'

    with resources.path(package_name, csv_filename) as csv_path:
        df = pd.read_csv(csv_path)

    return df
