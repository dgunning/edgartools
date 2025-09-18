"""
Filtering utilities for SEC EDGAR data.

This module provides functions for filtering pyarrow Tables containing SEC EDGAR data
based on various criteria like dates, forms, CIK numbers, etc.
"""
import datetime
from typing import List, Union

import pyarrow as pa
import pyarrow.compute as pc

from edgar.core import IntString, listify
from edgar.dates import extract_dates


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
    """Return the data filtered by CIK"""
    # Ensure that CIKs is a list of integers
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
    """Return the data filtered by ticker"""
    # Ensure that tickers is a list of strings
    from edgar.reference.tickers import get_cik_tickers
    company_tickers = get_cik_tickers()
    tickers = listify(ticker)
    filtered_tickers = company_tickers[company_tickers.ticker.isin(tickers)]
    ciks = filtered_tickers.cik.tolist()
    return filter_by_cik(data, cik=ciks)


def filter_by_year(data: pa.Table, 
                   year: Union[int, List[int]], 
                   date_col: str = 'filing_date') -> pa.Table:
    """Filter data by year(s)

    Args:
        data: PyArrow table to filter
        year: Year or list of years to filter by
        date_col: Name of the date column to filter on

    Returns:
        Filtered PyArrow table
    """
    years = listify(year)

    # Get the data type of the date column
    date_column_type = data.schema.field(date_col).type

    # Create year-based filters
    year_filters = []
    for y in years:
        start_date = f"{y}-01-01"
        end_date = f"{y}-12-31"

        # Convert dates to appropriate type for comparison
        if pa.types.is_date32(date_column_type) or pa.types.is_timestamp(date_column_type):
            # For date/timestamp columns, cast the date column to string for comparison
            date_field_as_string = pc.strftime(pc.field(date_col), format='%Y-%m-%d')
            year_filter = (date_field_as_string >= pc.scalar(start_date)) & \
                         (date_field_as_string <= pc.scalar(end_date))
        else:
            # For string dates, use direct comparison
            year_filter = (pc.field(date_col) >= pc.scalar(start_date)) & \
                         (pc.field(date_col) <= pc.scalar(end_date))

        year_filters.append(year_filter)

    # Combine with OR logic
    if len(year_filters) == 1:
        combined_filter = year_filters[0]
    else:
        combined_filter = year_filters[0]
        for f in year_filters[1:]:
            combined_filter = combined_filter | f

    return data.filter(combined_filter)


def filter_by_quarter(data: pa.Table, 
                      year: Union[int, List[int]], 
                      quarter: Union[int, List[int]], 
                      date_col: str = 'filing_date') -> pa.Table:
    """Filter data by specific year-quarter combinations

    Args:
        data: PyArrow table to filter
        year: Year or list of years
        quarter: Quarter or list of quarters (1-4)
        date_col: Name of the date column to filter on

    Returns:
        Filtered PyArrow table
    """
    years = listify(year)
    quarters = listify(quarter)

    # Quarter date ranges
    quarter_ranges = {
        1: ("01-01", "03-31"),
        2: ("04-01", "06-30"), 
        3: ("07-01", "09-30"),
        4: ("10-01", "12-31")
    }

    # Get the data type of the date column
    date_column_type = data.schema.field(date_col).type

    # Create filters for each year-quarter combination
    filters = []
    for y in years:
        for q in quarters:
            if q not in quarter_ranges:
                continue
            start_month_day, end_month_day = quarter_ranges[q]
            start_date = f"{y}-{start_month_day}"
            end_date = f"{y}-{end_month_day}"

            # Convert dates to appropriate type for comparison
            if pa.types.is_date32(date_column_type) or pa.types.is_timestamp(date_column_type):
                # For date/timestamp columns, cast the date column to string for comparison
                date_field_as_string = pc.strftime(pc.field(date_col), format='%Y-%m-%d')
                quarter_filter = (date_field_as_string >= pc.scalar(start_date)) & \
                               (date_field_as_string <= pc.scalar(end_date))
            else:
                # For string dates, use direct comparison
                quarter_filter = (pc.field(date_col) >= pc.scalar(start_date)) & \
                               (pc.field(date_col) <= pc.scalar(end_date))
            filters.append(quarter_filter)

    # Combine with OR logic
    if not filters:
        return data

    combined_filter = filters[0]
    for f in filters[1:]:
        combined_filter = combined_filter | f

    return data.filter(combined_filter)


def filter_by_year_quarter(data: pa.Table,
                          year: Union[int, List[int]] = None,
                          quarter: Union[int, List[int]] = None,
                          date_col: str = 'filing_date') -> pa.Table:
    """Filter by year and optionally quarter

    Args:
        data: PyArrow table to filter
        year: Year or list of years to filter by
        quarter: Quarter or list of quarters (1-4). If None, filters by full year(s)
        date_col: Name of the date column to filter on

    Returns:
        Filtered PyArrow table
    """
    if year is None:
        return data

    if quarter is None:
        return filter_by_year(data, year, date_col)
    else:
        return filter_by_quarter(data, year, quarter, date_col)
