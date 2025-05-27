"""
Filtering utilities for SEC EDGAR data.

This module provides functions for filtering pyarrow Tables containing SEC EDGAR data
based on various criteria like dates, forms, CIK numbers, etc.
"""
import datetime
from typing import Union, List

import pyarrow as pa
import pyarrow.compute as pc
from edgar.dates import extract_dates
from edgar.core import IntString, listify


def filter_by_date(data: pa.Table,
                   date: Union[str, datetime.datetime],
                   date_col: str) -> pa.Table:
    # If datetime convert to string
    if isinstance(date, datetime.date) or isinstance(date, datetime.datetime):
        date = date.strftime('%Y-%m-%d')

    # Extract the date parts ... this should raise an exception if we cannot
    date_parts = extract_dates(date)
    start_date, end_date, is_range = date_parts
    if is_range:
        filtered_data = data
        if start_date:
            filtered_data = filtered_data.filter(pc.field(date_col) >= pc.scalar(start_date))
        if end_date:
            filtered_data = filtered_data.filter(pc.field(date_col) <= pc.scalar(end_date))
    else:
        # filter by filings on date
        filtered_data = data.filter(pc.field(date_col) == pc.scalar(start_date))
    return filtered_data


def filter_by_accession_number(data: pa.Table,
                               accession_number: Union[IntString, List[IntString]]) -> pa.Table:
    """Return the data filtered by accession number"""
    # Ensure that forms is a list of strings ... it can accept int like form 3, 4, 5
    accession_numbers = [str(el) for el in listify(accession_number)]
    data = data.filter(pc.is_in(data['accession_number'], pa.array(accession_numbers)))
    return data



def filter_by_form(data: pa.Table,
                   form: Union[str, List[str]],
                   amendments: bool = True) -> pa.Table:
    """Return the data filtered by form"""
    # Ensure that forms is a list of strings ... it can accept int like form 3, 4, 5
    forms = [str(el) for el in listify(form)]
    if amendments:
        forms = list(set(forms + [f"{val}/A" for val in forms]))
    else:
        forms = list(set([val.replace("/A", "") for val in forms]))
    data = data.filter(pc.is_in(data['form'], pa.array(forms)))
    return data


def filter_by_cik(data: pa.Table,
                  cik: Union[IntString, List[IntString]]) -> pa.Table:
    """Return the data filtered by form"""
    # Ensure that forms is a list of strings ... it can accept int like form 3, 4, 5
    ciks = [int(el) for el in listify(cik)]
    data = data.filter(pc.is_in(data['cik'], pa.array(ciks)))
    return data

def filter_by_exchange(data: pa.Table, exchange: Union[str, List[str]]) -> pa.Table:
    """Return the data filtered by exchange"""
    # Ensure that forms is a list of strings ... it can accept int like form 3, 4, 5
    from edgar.reference.tickers import get_company_ticker_name_exchange
    exchanges = [str(el).upper() for el in listify(exchange)]
    exchange_df = get_company_ticker_name_exchange()
    exchange_df = exchange_df[exchange_df.exchange.str.upper().isin(exchanges)]
    return filter_by_cik(data, exchange_df.cik.tolist())



def filter_by_ticker(data: pa.Table,
                     ticker: Union[str, List[str]]) -> pa.Table:
    """Return the data filtered by form"""
    # Ensure that forms is a list of strings ... it can accept int like form 3, 4, 5
    from edgar.reference.tickers import get_cik_tickers
    company_tickers = get_cik_tickers()
    tickers = listify(ticker)
    filtered_tickers = company_tickers[company_tickers.ticker.isin(tickers)]
    ciks = filtered_tickers.cik.tolist()
    return filter_by_cik(data, cik=ciks)