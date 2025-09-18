"""
Module for converting HTML tables from filing reports to pandas DataFrames.
This provides an alternative to XBRL parsing by extracting data directly from
company-formatted HTML tables.
"""

import re
from dataclasses import dataclass
from typing import Optional, Union

import pandas as pd

from edgar.files.html import Document, TableNode
from edgar.files.tables import ProcessedTable


@dataclass
class TableMetadata:
    """Metadata extracted from table headers and content"""
    currency: Optional[str] = None
    units: Optional[str] = None
    scaling_factor: Optional[int] = None
    period_type: Optional[str] = None  # 'instant' or 'duration'


class FinancialTableExtractor:
    """Extract financial tables from HTML reports as pandas DataFrames"""

    # Common patterns for financial data
    # More comprehensive currency patterns
    CURRENCY_PATTERN = re.compile(
        r'\$|USD|EUR|GBP|JPY|CNY|CAD|AUD|CHF|'
        r'£|€|¥|₹|'  # Currency symbols
        r'\bDollars?\b|\bPounds?\b|\bEuros?\b|\bYen\b',
        re.IGNORECASE
    )
    # More flexible units pattern
    UNITS_PATTERN = re.compile(
        r'(?:in\s+)?(?:thousands?|millions?|billions?|000s?|000,000s?|mln|mil|bn)',
        re.IGNORECASE
    )
    SCALING_PATTERN = re.compile(r'(\d+(?:,\d{3})*)\s*=\s*\$?1')
    # More flexible date patterns to handle various formats
    PERIOD_PATTERN = re.compile(
        r'(\d{1,2}[\s/\-]\w{3,}[\s/\-]\d{2,4}|'  # 31-Dec-2024, 31/December/24
        r'\w{3,}\.?\s+\d{1,2},?\s+\d{4}|'        # December 31, 2024
        r'\d{4}[\s/\-]\d{1,2}[\s/\-]\d{1,2}|'    # 2024-12-31
        r'\d{1,2}[\s/\-]\d{1,2}[\s/\-]\d{2,4}|'  # 12/31/2024, 31-12-24
        r'Q[1-4]\s*\d{2,4}|'                      # Q1 2024, Q12024
        r'\d{1}Q\s*\d{2,4}|'                      # 1Q 2024, 1Q24
        r'FY\s*\d{2,4}|'                          # FY 2024, FY24
        r'Fiscal\s+\d{4}|'                        # Fiscal 2024
        r'Year\s+Ended)',                         # Year Ended
        re.IGNORECASE
    )

    @classmethod
    def extract_table_to_dataframe(cls, table_node: TableNode) -> pd.DataFrame:
        """
        Convert a TableNode to a pandas DataFrame with appropriate data types.

        Args:
            table_node: The TableNode containing financial data

        Returns:
            pd.DataFrame with financial data, periods as columns, line items as index
        """
        try:
            # Get processed table
            processed_table = table_node._processed
            if not processed_table:
                return pd.DataFrame()

            # Extract metadata from headers
            metadata = cls._extract_metadata(table_node, processed_table)

            # Build DataFrame
            df = cls._build_dataframe(processed_table, metadata)

            # Apply data transformations
            df = cls._apply_transformations(df, metadata)

            return df

        except Exception:
            # Log error but return empty DataFrame to allow processing to continue
            return pd.DataFrame()

    @classmethod
    def _extract_metadata(cls, table_node: TableNode, processed_table: ProcessedTable) -> TableMetadata:
        """Extract metadata from table headers and first few rows"""
        metadata = TableMetadata()

        # Check headers for currency and units
        if processed_table.headers:
            header_text = ' '.join(processed_table.headers)

            # Extract currency
            currency_match = cls.CURRENCY_PATTERN.search(header_text)
            if currency_match:
                metadata.currency = currency_match.group(0)

            # Extract units
            units_match = cls.UNITS_PATTERN.search(header_text)
            if units_match:
                unit_text = units_match.group(0).lower()
                if any(x in unit_text for x in ['thousand', '000s', '000,']):
                    metadata.scaling_factor = 1000
                    metadata.units = 'thousands'
                elif any(x in unit_text for x in ['million', 'mln', 'mil', '000,000']):
                    metadata.scaling_factor = 1000000
                    metadata.units = 'millions'
                elif any(x in unit_text for x in ['billion', 'bn']):
                    metadata.scaling_factor = 1000000000
                    metadata.units = 'billions'

        # Check if periods are durations or instants
        if processed_table.headers:
            period_headers = [h for h in processed_table.headers if cls.PERIOD_PATTERN.search(h)]
            if period_headers:
                # If headers contain "ended" it's likely duration periods
                if any('ended' in h.lower() for h in period_headers):
                    metadata.period_type = 'duration'
                else:
                    metadata.period_type = 'instant'

        return metadata

    @classmethod
    def _build_dataframe(cls, processed_table: ProcessedTable, metadata: TableMetadata) -> pd.DataFrame:
        """Build initial DataFrame from processed table"""
        if not processed_table.data_rows:
            return pd.DataFrame()

        # Identify period columns and line item column
        headers = processed_table.headers or []
        period_cols = []
        line_item_col = 0

        # Check if this is a "vertical" table (like Cover Page)
        # where first column is labels and all others are data
        is_vertical_table = False
        if len(headers) >= 2:
            # Check if first column has label-like patterns
            first_header_lower = headers[0].lower() if headers[0] else ''
            first_is_label = any(pattern in first_header_lower for pattern in 
                               ['entity', 'line item', 'information', 'abstract', 'cover page',
                                'detail', 'description', 'item'])

            # Check if this looks like a cover page or entity info table
            # by examining the first few data rows
            looks_like_entity_info = False
            if processed_table.data_rows and len(processed_table.data_rows) > 2:
                # Check if first column has entity/document field names
                first_col_values = []
                for row in processed_table.data_rows[:10]:  # Check more rows
                    if len(row) > 0 and isinstance(row[0], str):
                        first_col_values.append(row[0].lower())

                # More comprehensive patterns for vertical tables
                entity_patterns = ['entity', 'document', 'registrant', 'address', 
                                 'file number', 'incorporation', 'fiscal', 'telephone',
                                 'securities', 'trading', 'exchange', 'ticker']

                # Count how many rows match entity patterns
                pattern_matches = sum(
                    any(pattern in val for pattern in entity_patterns) 
                    for val in first_col_values
                )

                # If more than 30% of rows have entity-like labels, it's probably vertical
                looks_like_entity_info = pattern_matches >= len(first_col_values) * 0.3

            is_vertical_table = first_is_label or looks_like_entity_info

        if is_vertical_table:
            # For vertical tables, first column is index, rest are data
            line_item_col = 0
            period_cols = list(range(1, len(headers)))
            # Ensure we don't include the line item column
            if line_item_col in period_cols:
                period_cols.remove(line_item_col)
        else:
            # For standard tables, identify period columns
            for i, header in enumerate(headers):
                if cls.PERIOD_PATTERN.search(header):
                    period_cols.append(i)
                elif i == 0:  # First column is usually line items
                    line_item_col = i

        # Extract data
        data = []
        index = []

        for row in processed_table.data_rows:
            if len(row) > line_item_col:
                line_item = row[line_item_col].strip()
                if line_item and not line_item.isspace():
                    index.append(line_item)
                    row_data = []
                    for col_idx in period_cols:
                        if col_idx < len(row):
                            row_data.append(row[col_idx])
                        else:
                            row_data.append('')
                    data.append(row_data)

        # Create DataFrame
        if data:
            column_names = []
            for i, col_idx in enumerate(period_cols):
                if col_idx < len(headers):
                    # Clean up column name and make unique if needed
                    col_name = headers[col_idx].strip()
                    # If duplicate, append index
                    if col_name in column_names:
                        col_name = f"{col_name}_{i}"
                    column_names.append(col_name)
                else:
                    column_names.append(f'Col_{i}')

            df = pd.DataFrame(data, index=index, columns=column_names)
        else:
            df = pd.DataFrame()

        return df

    @classmethod
    def _apply_transformations(cls, df: pd.DataFrame, metadata: TableMetadata) -> pd.DataFrame:
        """Apply data type conversions and scaling"""
        if df.empty:
            return df

        # Convert numeric columns
        for col in df.columns:
            df[col] = df[col].apply(cls._parse_financial_value)

        # Apply scaling if specified
        if metadata.scaling_factor:
            numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
            df[numeric_cols] = df[numeric_cols] * metadata.scaling_factor

        # Add metadata as attributes
        df.attrs['currency'] = metadata.currency
        df.attrs['units'] = metadata.units
        df.attrs['scaling_factor'] = metadata.scaling_factor
        df.attrs['period_type'] = metadata.period_type

        return df

    @staticmethod
    def _parse_financial_value(value: str) -> Union[float, str]:
        """Parse a financial value string to float or keep as string"""
        if not isinstance(value, str):
            return value

        # Clean the value
        clean_value = value.strip()

        # Check for special markers and empty values
        empty_markers = ['—', '-', '–', '—', '‒', 'N/A', 'n/a', 'NA', 'nm', 'NM', '*', '**']
        if clean_value in empty_markers or not clean_value:
            return 0.0

        # Remove currency symbols, whitespace, and other common symbols
        # Keep negative sign and decimal points
        clean_value = re.sub(r'[£€¥₹$,\s]', '', clean_value)

        # Handle various negative formats
        if clean_value.startswith('(') and clean_value.endswith(')'):
            clean_value = '-' + clean_value[1:-1]
        elif clean_value.endswith('-'):  # Some companies put negative sign at end
            clean_value = '-' + clean_value[:-1]

        # Handle percentage values (remove % but keep the number)
        clean_value = clean_value.replace('%', '')

        # Try to convert to float
        try:
            return float(clean_value)
        except ValueError:
            # If it contains any digits, try harder to extract them
            if re.search(r'\d', clean_value):
                # Extract just the numeric part
                numeric_match = re.search(r'-?\d+\.?\d*', clean_value)
                if numeric_match:
                    try:
                        return float(numeric_match.group(0))
                    except ValueError:
                        pass

            # Return original if not numeric
            return value


def extract_statement_dataframe(report_content: str) -> pd.DataFrame:
    """
    Convenience function to extract a DataFrame from report HTML content.

    Args:
        report_content: HTML content from a report

    Returns:
        pd.DataFrame containing the financial data
    """
    # Parse HTML document
    document = Document.parse(report_content)

    if not document.tables:
        return pd.DataFrame()

    # Try each table to find one with financial data
    for table_node in document.tables:
        # Skip tables that are too small (likely headers or metadata)
        if table_node.row_count < 3:
            continue

        # Check if table has numeric data
        if _table_has_financial_data(table_node):
            df = FinancialTableExtractor.extract_table_to_dataframe(table_node)
            if not df.empty:
                return df

    # If no suitable table found, try the first table anyway
    if document.tables:
        return FinancialTableExtractor.extract_table_to_dataframe(document.tables[0])

    return pd.DataFrame()


def _table_has_financial_data(table_node: TableNode) -> bool:
    """Check if a table contains financial data by looking for numeric patterns"""
    if not table_node.content:
        return False

    # Check first few rows for numeric data
    numeric_count = 0
    total_cells = 0

    for _i, row in enumerate(table_node.content[:10]):  # Check first 10 rows
        for cell in row.cells:
            total_cells += 1
            if isinstance(cell.content, str):
                # Check for financial number patterns
                if re.search(r'\$?\s*\d+[,.]?\d*', cell.content):
                    numeric_count += 1

    # If more than 20% of cells have numbers, likely a financial table
    return total_cells > 0 and (numeric_count / total_cells) > 0.2
