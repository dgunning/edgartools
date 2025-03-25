"""
Data transformation functions for XBRL data.

This module provides functions for transforming XBRL data into various formats
and performing calculations and aggregations on financial data.
"""

from typing import Dict, List, Any, Optional, Tuple

import pandas as pd
from edgar.xbrl2.core import format_value


def to_dataframe(
    statement_data: List[Dict[str, Any]],
    periods_to_display: Optional[List[Tuple[str, str]]] = None,
    include_metadata: bool = True,
    standardize_values: bool = True
) -> Optional[Any]:
    """
    Convert statement data to a pandas DataFrame.
    
    Args:
        statement_data: List of statement items with values and metadata
        periods_to_display: Optional list of period keys and labels to include
        include_metadata: Whether to include metadata columns (level, is_abstract, etc.)
        standardize_values: Whether to standardize numeric values using scale factors
        
    Returns:
        pd.DataFrame: DataFrame with statement data
    """
    # Extract period keys if not provided
    if not periods_to_display:
        # Get unique period keys from all items
        period_keys = set()
        for item in statement_data:
            period_keys.update(item.get('values', {}).keys())
        periods_to_display = [(key, key) for key in sorted(period_keys)]
    
    # Prepare data for DataFrame
    rows = []
    for item in statement_data:
        row = {
            'concept': item.get('concept', ''),
            'label': item.get('label', ''),
            'original_label': item.get('original_label', item.get('label', '')),
        }
        
        # Add metadata if requested
        if include_metadata:
            row.update({
                'level': item.get('level', 0),
                'is_abstract': item.get('is_abstract', False),
                'is_dimension': item.get('is_dimension', False),
                'has_children': bool(item.get('children')),
                'has_dimension_children': item.get('has_dimension_children', False),
                'dimension_metadata': item.get('dimension_metadata', {}),
                'decimals': item.get('decimals', {}),
                'units': item.get('units', {}),
            })
        
        # Add values for each period
        values = item.get('values', {})
        if standardize_values:
            # Get scale from decimals attribute
            scale = None
            for period_key, _ in periods_to_display:
                decimals = item.get('decimals', {}).get(period_key)
                if isinstance(decimals, int):
                    scale = decimals
                    break
            
            # Format values with scale
            for period_key, period_label in periods_to_display:
                value = values.get(period_key)
                try:
                    if scale is not None:
                        row[period_label] = format_value(value, scale=scale, is_monetary=True)
                    else:
                        row[period_label] = value
                except (ValueError, TypeError):
                    row[period_label] = value
        else:
            # Use raw values
            for period_key, period_label in periods_to_display:
                row[period_label] = values.get(period_key)
        
        rows.append(row)

    return pd.DataFrame(rows)

def calculate_ratios(
    statement_data: List[Dict[str, Any]],
    periods_to_display: Optional[List[Tuple[str, str]]] = None
) -> Dict[str, Dict[str, float]]:
    """
    Calculate common financial ratios from statement data.
    
    Args:
        statement_data: List of statement items with values
        periods_to_display: Optional list of period keys and labels to include
        
    Returns:
        Dict[str, Dict[str, float]]: Dictionary of ratio names to period values
    """
    df = to_dataframe(statement_data, periods_to_display, include_metadata=False)
    if df is None:
        return {}
        
    # Get period columns (exclude metadata columns)
    period_cols = [col for col in df.columns if col not in ['concept', 'label', 'original_label']]
    
    # Initialize results
    ratios = {}
    
    # Helper function to get value for a concept
    def get_concept_value(concept: str, period: str) -> Optional[float]:
        try:
            value = df[df['concept'] == concept][period].iloc[0]
            if isinstance(value, str):
                value = float(value.replace(',', ''))
            return value
        except (IndexError, ValueError, TypeError):
            return None
    
    # Calculate ratios for each period
    for period in period_cols:
        period_ratios = {}
        
        # Current Ratio
        current_assets = get_concept_value('us-gaap_CurrentAssets', period)
        current_liabilities = get_concept_value('us-gaap_CurrentLiabilities', period)
        if current_assets is not None and current_liabilities and current_liabilities != 0:
            period_ratios['current_ratio'] = current_assets / current_liabilities
        
        # Quick Ratio
        inventory = get_concept_value('us-gaap_Inventory', period)
        if current_assets is not None and inventory is not None and current_liabilities and current_liabilities != 0:
            period_ratios['quick_ratio'] = (current_assets - inventory) / current_liabilities
        
        # Debt to Equity
        total_debt = get_concept_value('us-gaap_LongTermDebt', period)
        total_equity = get_concept_value('us-gaap_StockholdersEquity', period)
        if total_debt is not None and total_equity and total_equity != 0:
            period_ratios['debt_to_equity'] = total_debt / total_equity
        
        # Net Profit Margin
        net_income = get_concept_value('us-gaap_NetIncomeLoss', period)
        revenue = get_concept_value('us-gaap_Revenues', period)
        if net_income is not None and revenue and revenue != 0:
            period_ratios['net_profit_margin'] = net_income / revenue
        
        # Return on Assets (ROA)
        total_assets = get_concept_value('us-gaap_Assets', period)
        if net_income is not None and total_assets and total_assets != 0:
            period_ratios['return_on_assets'] = net_income / total_assets
        
        # Return on Equity (ROE)
        if net_income is not None and total_equity and total_equity != 0:
            period_ratios['return_on_equity'] = net_income / total_equity
        
        ratios[period] = period_ratios
    
    return ratios

def calculate_growth_rates(
    statement_data: List[Dict[str, Any]],
    periods_to_display: Optional[List[Tuple[str, str]]] = None,
    concepts: Optional[List[str]] = None
) -> Dict[str, Dict[str, float]]:
    """
    Calculate period-over-period growth rates for specified concepts.
    
    Args:
        statement_data: List of statement items with values
        periods_to_display: Optional list of period keys and labels to include
        concepts: Optional list of concepts to calculate growth rates for
        
    Returns:
        Dict[str, Dict[str, float]]: Dictionary of concept names to period growth rates
    """
    df = to_dataframe(statement_data, periods_to_display, include_metadata=False)
    if df is None:
        return {}
        
    # Get period columns in chronological order
    period_cols = [col for col in df.columns if col not in ['concept', 'label', 'original_label']]
    
    # Use all concepts if none specified
    if concepts is None:
        concepts = df['concept'].unique().tolist()
    
    # Initialize results
    growth_rates = {}
    
    # Calculate growth rates for each concept
    if concepts is None:
        return {}
        
    for concept in concepts:
        concept_data = df[df['concept'] == concept]
        if len(concept_data) == 0:
            continue
        
        rates = {}
        for i in range(1, len(period_cols)):
            current_period = period_cols[i]
            prev_period = period_cols[i-1]
            
            try:
                current_value = float(str(concept_data[current_period].iloc[0]).replace(',', ''))
                prev_value = float(str(concept_data[prev_period].iloc[0]).replace(',', ''))
                
                if prev_value != 0:
                    growth_rate = (current_value - prev_value) / abs(prev_value)
                    rates[current_period] = growth_rate
            except (ValueError, TypeError, IndexError):
                continue
        
        if rates:
            growth_rates[concept] = rates
    
    return growth_rates

def aggregate_by_dimension(
    statement_data: List[Dict[str, Any]],
    dimension_name: str,
    aggregation: str = 'sum'
) -> Dict[str, Dict[str, Any]]:
    """
    Aggregate values by a specific dimension.
    
    Args:
        statement_data: List of statement items with values
        dimension_name: Name of the dimension to aggregate by
        aggregation: Aggregation function ('sum' or 'average')
        
    Returns:
        Dict[str, Dict[str, Any]]: Aggregated values by dimension member
    """
    # Group items by dimension member
    dimension_groups = {}
    
    for item in statement_data:
        # Skip items without dimension metadata
        if not item.get('dimension_metadata'):
            continue
        
        # Get dimension value for this item
        dimension_value = None
        for dim in item.get('dimension_metadata', []):
            if dim.get('dimension') == dimension_name:
                dimension_value = dim.get('member')
                break
        
        if not dimension_value:
            continue
        
        # Initialize group if needed
        if dimension_value not in dimension_groups:
            dimension_groups[dimension_value] = []
        
        dimension_groups[dimension_value].append(item)
    
    # Aggregate values for each group
    results = {}
    for member, items in dimension_groups.items():
        # Get all unique periods
        periods = set()
        for item in items:
            periods.update(item.get('values', {}).keys())
        
        # Initialize aggregated values
        aggregated_values = {period: [] for period in periods}
        
        # Collect values for each period
        for item in items:
            for period, value in item.get('values', {}).items():
                try:
                    if isinstance(value, str):
                        value = float(value.replace(',', ''))
                    if value is not None:
                        aggregated_values[period].append(value)
                except (ValueError, TypeError):
                    continue
        
        # Perform aggregation
        results[member] = {
            'values': {},
            'item_count': len(items)
        }
        
        for period, values in aggregated_values.items():
            if values:
                if aggregation == 'average':
                    results[member]['values'][period] = sum(values) / len(values)
                else:  # sum
                    results[member]['values'][period] = sum(values)
    
    return results
