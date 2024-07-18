import concurrent.futures
import datetime
from decimal import Decimal
from typing import Tuple, Union

import numpy as np
import pandas as pd
from tqdm import tqdm

from edgar import Filing, Filings
from edgar.core import reverse_name
from edgar.headers import ReportingOwner

__all__ = ['describe_filing', 'describe_filings', 'is_numeric', 'compute_average_price',
           'compute_total_value', 'format_currency', 'format_amount']


def describe_filing(filing: Filing) -> Tuple[str, datetime.datetime]:
    index_headers = filing.index_headers
    reporting_owner: ReportingOwner = index_headers.reporting_owner
    reporting_owner_name = reporting_owner.owner_data.name
    if reporting_owner.company_data is None:
        reporting_owner_name = reverse_name(reporting_owner_name)
    return reporting_owner_name, index_headers.acceptance_datetime


def describe_filings(filings: Filings):
    results = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Map filings to describe_filing function
        future_to_filing = {executor.submit(describe_filing, filing): filing for filing in filings}

        # Collect results as they complete
        for future in tqdm(concurrent.futures.as_completed(future_to_filing), total=len(filings)):
            result = future.result()
            results.append(result)

    # Return the owner names only sorted by acceptance datetime descending
    results = [r[0]
               for r in
               sorted(results, key=lambda x: x[1], reverse=True)
               ]
    return results


def is_numeric(series: pd.Series) -> bool:
    if np.issubdtype(series.dtype, np.number):
        return True
    try:
        series.astype(float)
        return True
    except ValueError:
        return False

def compute_average_price(shares: pd.Series, price: pd.Series) -> Decimal:
    """
    Compute the average price of the trades
    :param shares: The number of shares as a series
    :param price: The price per share as a series
    :return:
    """
    if is_numeric(shares) and is_numeric(price):
        shares = pd.to_numeric(shares)
        price = pd.to_numeric(price)
        value = (shares * price).sum() / shares.sum()
        return Decimal(str(value)).quantize(Decimal('0.01'))


def compute_total_value(shares: pd.Series, price: pd.Series) -> Decimal:
    """
    Compute the total value of the trades
    :param shares: The number of shares as a series
    :param price: The price per share as a series
    :return:
    """
    if is_numeric(shares) and is_numeric(price):
        shares = pd.to_numeric(shares)
        price = pd.to_numeric(price)
        value = (shares * price).sum()
        return Decimal(str(value)).quantize(Decimal('0.01'))

def format_currency(amount: Union[int, float]) -> str:
    if amount is None or np.isnan(amount):
        return ""
    if isinstance(amount, (int, float)):
        return f"${amount:,.2f}"
    return str(amount)


def format_amount(amount: Union[int, float]) -> str:
    if amount is None:
        return ""
    if isinstance(amount, (int, float)):
        # Can it be formatted as an integer?
        if amount == int(amount):
            return f"{amount:,.0f}"
        return f"{amount:,.2f}"
    return str(amount)


