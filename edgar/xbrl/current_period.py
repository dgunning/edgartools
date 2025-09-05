"""
Current Period API - Convenient access to current period financial data.

This module provides the CurrentPeriodView class that offers simplified access 
to the most recent period's financial data without comparative information,
addressing GitHub issue #425.

Key features:
- Automatic detection of the current (most recent) period
- Direct access to balance sheet, income statement, and cash flow data
- Support for raw XBRL concept names (unprocessed)
- Notes and disclosures access
- Beginner-friendly API design
"""

import pandas as pd
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date

from edgar.core import log
from edgar.xbrl.exceptions import StatementNotFound


class CurrentPeriodView:
    """
    Convenient access to current period financial data.
    
    This class provides simplified access to the most recent period's
    financial data without comparative information. It automatically
    detects the current period and provides easy access to key statements.
    
    Example usage:
        >>> xbrl = filing.xbrl()
        >>> current = xbrl.current_period
        >>> balance_sheet = current.balance_sheet()
        >>> income_statement = current.income_statement(raw_concepts=True)
    """
    
    def __init__(self, xbrl):
        """
        Initialize CurrentPeriodView with an XBRL object.
        
        Args:
            xbrl: XBRL object containing parsed financial data
        """
        self.xbrl = xbrl
        self._current_period_key = None
        self._current_period_label = None
    
    @property
    def period_key(self) -> str:
        """
        Get the current period key (most recent period).
        
        The current period is determined by:
        1. Document period end date if available
        2. Most recent period in reporting periods
        3. Fallback to any available period
        
        Returns:
            Period key string (e.g., "instant_2024-12-31" or "duration_2024-01-01_2024-12-31")
        """
        if self._current_period_key is None:
            self._current_period_key = self._detect_current_period()
        return self._current_period_key
    
    @property
    def period_label(self) -> str:
        """
        Get the human-readable label for the current period.
        
        Returns:
            Human-readable period label (e.g., "December 31, 2024" or "Year Ended December 31, 2024")
        """
        if self._current_period_label is None:
            self._detect_current_period()  # This sets both key and label
        return self._current_period_label or self.period_key
    
    def _detect_current_period(self) -> str:
        """
        Detect the current (most recent) period from available data.
        
        Strategy:
        1. Use document period end date to find matching instant period
        2. If no instant match, find most recent duration period ending on document period end
        3. Fall back to most recent period by end date
        4. Final fallback to first available period
        
        Returns:
            Period key for the current period
        """
        if not self.xbrl.reporting_periods:
            log.warning("No reporting periods found in XBRL data")
            return ""
        
        # Try to use document period end date if available
        document_period_end = None
        if hasattr(self.xbrl, 'period_of_report') and self.xbrl.period_of_report:
            try:
                if isinstance(self.xbrl.period_of_report, str):
                    document_period_end = datetime.strptime(self.xbrl.period_of_report, '%Y-%m-%d').date()
                elif isinstance(self.xbrl.period_of_report, (date, datetime)):
                    document_period_end = self.xbrl.period_of_report
                    if isinstance(document_period_end, datetime):
                        document_period_end = document_period_end.date()
            except (ValueError, TypeError):
                log.debug(f"Could not parse document period end date: {self.xbrl.period_of_report}")
        
        # Sort periods by end date (most recent first)
        periods_by_date = []
        for period in self.xbrl.reporting_periods:
            period_key = period['key']
            period_label = period.get('label', period_key)
            end_date = None
            
            try:
                if period_key.startswith('instant_'):
                    # Format: "instant_2024-12-31"
                    date_str = period_key.split('_', 1)[1]
                    end_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                elif period_key.startswith('duration_'):
                    # Format: "duration_2024-01-01_2024-12-31"
                    parts = period_key.split('_')
                    if len(parts) >= 3:
                        date_str = parts[2]  # End date
                        end_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                
                if end_date:
                    periods_by_date.append((end_date, period_key, period_label))
            except (ValueError, IndexError):
                log.debug(f"Could not parse period key: {period_key}")
                continue
        
        if not periods_by_date:
            # Fallback to first available period if no dates could be parsed
            first_period = self.xbrl.reporting_periods[0]
            self._current_period_key = first_period['key']
            self._current_period_label = first_period.get('label', first_period['key'])
            log.debug(f"Using fallback period: {self._current_period_key}")
            return self._current_period_key
        
        # Sort by date (most recent first)
        periods_by_date.sort(key=lambda x: x[0], reverse=True)
        
        # Strategy 1: If we have document period end, look for exact matches
        # Prefer instant periods over duration periods when both match document end date
        if document_period_end:
            instant_match = None
            duration_match = None
            
            for end_date, period_key, period_label in periods_by_date:
                if end_date == document_period_end:
                    if period_key.startswith('instant_'):
                        instant_match = (period_key, period_label)
                    elif period_key.startswith('duration_'):
                        duration_match = (period_key, period_label)
            
            # Prefer instant match if available
            if instant_match:
                self._current_period_key = instant_match[0]
                self._current_period_label = instant_match[1]
                log.debug(f"Found instant period matching document end date: {instant_match[0]}")
                return self._current_period_key
            elif duration_match:
                self._current_period_key = duration_match[0]
                self._current_period_label = duration_match[1]
                log.debug(f"Found duration period matching document end date: {duration_match[0]}")
                return self._current_period_key
        
        # Strategy 2: Use most recent period
        most_recent = periods_by_date[0]
        self._current_period_key = most_recent[1]
        self._current_period_label = most_recent[2]
        
        log.debug(f"Selected most recent period: {self._current_period_key} ({self._current_period_label})")
        return self._current_period_key
    
    def balance_sheet(self, raw_concepts: bool = False) -> pd.DataFrame:
        """
        Get current period balance sheet data.
        
        Args:
            raw_concepts: If True, preserve original XBRL concept names 
                         (e.g., "us-gaap:Assets" instead of "Assets")
        
        Returns:
            pandas DataFrame with balance sheet data for current period only
            
        Example:
            >>> df = xbrl.current_period.balance_sheet()
            >>> assets = df[df['label'].str.contains('Assets', case=False)]['value'].iloc[0]
        """
        return self._get_statement_dataframe('BalanceSheet', raw_concepts=raw_concepts)
    
    def income_statement(self, raw_concepts: bool = False) -> pd.DataFrame:
        """
        Get current period income statement data.
        
        Args:
            raw_concepts: If True, preserve original XBRL concept names
                         (e.g., "us-gaap:Revenues" instead of "Revenue")
        
        Returns:
            pandas DataFrame with income statement data for current period only
            
        Example:
            >>> df = xbrl.current_period.income_statement(raw_concepts=True)
            >>> revenue = df[df['concept'].str.contains('Revenues')]['value'].iloc[0]
        """
        return self._get_statement_dataframe('IncomeStatement', raw_concepts=raw_concepts)
    
    def cashflow_statement(self, raw_concepts: bool = False) -> pd.DataFrame:
        """
        Get current period cash flow statement data.
        
        Args:
            raw_concepts: If True, preserve original XBRL concept names
                         (e.g., "us-gaap:NetCashProvidedByUsedInOperatingActivities")
        
        Returns:
            pandas DataFrame with cash flow data for current period only
            
        Example:
            >>> df = xbrl.current_period.cashflow_statement()
            >>> operating_cf = df[df['label'].str.contains('Operating')]['value'].iloc[0]
        """
        return self._get_statement_dataframe('CashFlowStatement', raw_concepts=raw_concepts)
    
    def statement_of_equity(self, raw_concepts: bool = False) -> pd.DataFrame:
        """
        Get current period statement of equity data.
        
        Args:
            raw_concepts: If True, preserve original XBRL concept names
        
        Returns:
            pandas DataFrame with equity statement data for current period only
        """
        return self._get_statement_dataframe('StatementOfEquity', raw_concepts=raw_concepts)
    
    def comprehensive_income(self, raw_concepts: bool = False) -> pd.DataFrame:
        """
        Get current period comprehensive income statement data.
        
        Args:
            raw_concepts: If True, preserve original XBRL concept names
        
        Returns:
            pandas DataFrame with comprehensive income data for current period only
        """
        return self._get_statement_dataframe('ComprehensiveIncome', raw_concepts=raw_concepts)
    
    def _get_statement_dataframe(self, statement_type: str, raw_concepts: bool = False) -> pd.DataFrame:
        """
        Internal method to get statement data as DataFrame for current period.
        
        Args:
            statement_type: Type of statement ('BalanceSheet', 'IncomeStatement', etc.)
            raw_concepts: Whether to preserve raw XBRL concept names
            
        Returns:
            pandas DataFrame with statement data filtered to current period
            
        Raises:
            StatementNotFound: If the requested statement type is not available
        """
        try:
            # Get raw statement data filtered to current period
            statement_data = self.xbrl.get_statement(statement_type, period_filter=self.period_key)
            
            if not statement_data:
                entity_name = getattr(self.xbrl, 'entity_name', 'Unknown')
                raise StatementNotFound(
                    statement_type=statement_type,
                    confidence=0.0,
                    found_statements=[],
                    entity_name=entity_name,
                    reason=f"No data found for {statement_type} in period {self.period_label}"
                )
            
            # Convert to DataFrame
            rows = []
            for item in statement_data:
                # Get the value for current period
                values = item.get('values', {})
                current_value = values.get(self.period_key)
                
                if current_value is not None:
                    row = {
                        'concept': self._get_concept_name(item, raw_concepts),
                        'label': item.get('label', ''),
                        'value': current_value,
                        'level': item.get('level', 0),
                        'is_abstract': item.get('is_abstract', False)
                    }
                    
                    # Add original concept name if raw_concepts is requested
                    if raw_concepts:
                        row['standardized_label'] = item.get('label', '')
                        # Try to get original concept names from all_names
                        all_names = item.get('all_names', [])
                        if all_names:
                            row['original_concept'] = all_names[0]  # First is usually original
                    
                    # Add dimension information if present
                    if item.get('is_dimension', False):
                        row['dimension_label'] = item.get('full_dimension_label', '')
                        row['is_dimension'] = True
                    
                    rows.append(row)
            
            if not rows:
                # Create empty DataFrame with expected structure
                columns = ['concept', 'label', 'value', 'level', 'is_abstract']
                if raw_concepts:
                    columns.extend(['standardized_label', 'original_concept'])
                return pd.DataFrame(columns=columns)
            
            return pd.DataFrame(rows)
            
        except Exception as e:
            log.error(f"Error retrieving {statement_type} for current period: {str(e)}")
            entity_name = getattr(self.xbrl, 'entity_name', 'Unknown')
            raise StatementNotFound(
                statement_type=statement_type,
                confidence=0.0,
                found_statements=[],
                entity_name=entity_name,
                reason=f"Failed to retrieve {statement_type}: {str(e)}"
            )
    
    def _get_concept_name(self, item: Dict[str, Any], raw_concepts: bool) -> str:
        """
        Get the appropriate concept name based on raw_concepts flag.
        
        Args:
            item: Statement line item dictionary
            raw_concepts: Whether to use raw XBRL concept names
            
        Returns:
            Concept name (raw or processed)
        """
        if raw_concepts:
            # Try to get original concept name
            all_names = item.get('all_names', [])
            if all_names:
                # Return first name, converting underscores back to colons for XBRL format
                original = all_names[0]
                if '_' in original and ':' not in original:
                    # This looks like a normalized name, try to restore colon format
                    parts = original.split('_', 1)
                    if len(parts) == 2 and parts[0] in ['us-gaap', 'dei', 'srt']:
                        return f"{parts[0]}:{parts[1]}"
                return original
            return item.get('concept', '')
        else:
            # Use processed concept name
            return item.get('concept', '')
    
    def notes(self, section_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get notes to financial statements for the current period.
        
        Args:
            section_name: Optional specific note section to retrieve
                         (e.g., "inventory", "revenue recognition")
        
        Returns:
            List of note sections with their content
            
        Note:
            This is a placeholder implementation. Full notes access would require
            additional development to parse and structure note content.
        """
        # Get all statements and filter for notes
        all_statements = self.xbrl.get_all_statements()
        note_statements = []
        
        for stmt in all_statements:
            stmt_type = (stmt.get('type') or '').lower()
            definition = (stmt.get('definition') or '').lower()
            
            # Check if this looks like a note section
            if ('note' in stmt_type or 'note' in definition or 
                'disclosure' in stmt_type or 'disclosure' in definition):
                
                # If specific section requested, filter by name
                if section_name:
                    if section_name.lower() in definition or section_name.lower() in stmt_type:
                        note_statements.append({
                            'section_name': stmt.get('definition', 'Untitled Note'),
                            'type': stmt.get('type', ''),
                            'role': stmt.get('role', ''),
                            'element_count': stmt.get('element_count', 0)
                        })
                else:
                    # Return all note sections
                    note_statements.append({
                        'section_name': stmt.get('definition', 'Untitled Note'),
                        'type': stmt.get('type', ''),
                        'role': stmt.get('role', ''),
                        'element_count': stmt.get('element_count', 0)
                    })
        
        return note_statements
    
    def get_fact(self, concept: str, raw_concept: bool = False) -> Any:
        """
        Get a specific fact value for the current period.
        
        Args:
            concept: XBRL concept name to look up
            raw_concept: If True, treat concept as raw XBRL name (with colons)
        
        Returns:
            Fact value if found, None otherwise
            
        Example:
            >>> revenue = xbrl.current_period.get_fact('Revenues')
            >>> revenue_raw = xbrl.current_period.get_fact('us-gaap:Revenues', raw_concept=True)
        """
        try:
            # Normalize concept name if needed
            if raw_concept and ':' in concept:
                # Convert colon format to underscore for internal lookup
                concept = concept.replace(':', '_')
            
            # Use XBRL's fact finding method with current period filter
            facts = self.xbrl._find_facts_for_element(concept, period_filter=self.period_key)
            
            if facts:
                # Return the first matching fact's value
                for context_id, wrapped_fact in facts.items():
                    fact = wrapped_fact['fact']
                    return fact.numeric_value if fact.numeric_value is not None else fact.value
            
            return None
            
        except Exception as e:
            log.debug(f"Error retrieving fact {concept}: {str(e)}")
            return None
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert current period data to a dictionary format.
        
        Returns:
            Dictionary with current period information and key financial data
        """
        result = {
            'period_key': self.period_key,
            'period_label': self.period_label,
            'entity_name': getattr(self.xbrl, 'entity_name', None),
            'document_type': getattr(self.xbrl, 'document_type', None),
            'statements': {}
        }
        
        # Try to get key statements
        statement_types = ['BalanceSheet', 'IncomeStatement', 'CashFlowStatement']
        for stmt_type in statement_types:
            try:
                df = self._get_statement_dataframe(stmt_type, raw_concepts=False)
                if not df.empty:
                    # Convert DataFrame to list of dicts for JSON serialization
                    result['statements'][stmt_type] = df.to_dict('records')
            except StatementNotFound:
                result['statements'][stmt_type] = None
        
        return result
    
    def __repr__(self) -> str:
        """String representation showing current period info."""
        entity_name = getattr(self.xbrl, 'entity_name', 'Unknown Entity')
        return f"CurrentPeriodView(entity='{entity_name}', period='{self.period_label}')"
    
    def __str__(self) -> str:
        """User-friendly string representation."""
        entity_name = getattr(self.xbrl, 'entity_name', 'Unknown Entity')
        return f"Current Period Data for {entity_name}\nPeriod: {self.period_label}"