from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from edgar.core import log
from edgar.richtools import repr_rich
from edgar.xbrl import XBRL, XBRLS, Statement
from edgar.xbrl.presentation import ViewType
from edgar.xbrl.statements import StitchedStatement
from edgar.xbrl.xbrl import XBRLFilingWithNoXbrlData

# Columns produced by RenderedStatement.to_dataframe() that are metadata, not
# period values.
_NON_PERIOD_COLUMNS = frozenset(
    {'concept', 'label', 'level', 'abstract', 'dimension', 'is_breakdown', 'unit', 'point_in_time'}
)


def _parse_iso_date(value):
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _duration_bucket(days: int) -> str:
    """Bucket a duration (in days) into a reporting-period class so that a
    period_offset walk stays within one series (quarter-to-quarter, or
    year-to-year) instead of interleaving 3-month and YTD columns."""
    if days <= 130:
        return 'q'   # ~3 months
    if days <= 220:
        return 'h'   # ~6 months (YTD at Q2)
    if days <= 310:
        return 't'   # ~9 months (YTD at Q3)
    return 'y'       # annual


def _order_period_columns(rendered, df_period_columns: List[str]) -> List[str]:
    """Order a rendered statement's period columns most-relevant-first.

    Fixes GH #885: ``RenderedStatement.to_dataframe()`` column order is not
    sorted by recency, so selecting ``period_columns[period_offset]``
    positionally could return a prior-year or wrong-duration value (e.g.
    ``get_revenue()`` returning the comparative FY2024 Q2 figure on a FY2025 Q2
    10-Q). We rebuild the order from each period's metadata: the current
    reporting period first (the shortest duration at the latest end date — the
    reporting quarter for a 10-Q, the year for a 10-K), then the rest of that
    same-duration series backwards in time, then other durations, then instant
    periods — all by end date descending. Columns whose period metadata can't be
    resolved keep their original relative order at the end, so the result is
    never worse than the previous positional behavior.
    """
    periods = getattr(rendered, 'periods', None) or []
    valid = set(df_period_columns)

    entries = []
    for period in periods:
        # Reconstruct the column name to_dataframe() assigns to this period.
        if period.end_date:
            name = f"{period.end_date} ({period.quarter})" if period.quarter else period.end_date
        else:
            name = period.label
        if name not in valid:
            continue
        end = _parse_iso_date(period.end_date)
        start = _parse_iso_date(period.start_date)
        days = (end - start).days if (end and start) else None
        entries.append({
            'name': name,
            'end': end,
            'is_duration': bool(period.is_duration or start is not None),
            'days': days,
            'bucket': _duration_bucket(days) if days is not None else None,
        })

    # If period metadata is missing/unusable, preserve the original order.
    if not entries or all(e['end'] is None for e in entries):
        return list(df_period_columns)

    durations = [e for e in entries if e['is_duration'] and e['end'] is not None]
    instants = [e for e in entries if not e['is_duration'] and e['end'] is not None]

    ordered = []
    if durations:
        current_end = max(e['end'] for e in durations)
        at_current_end = [e for e in durations if e['end'] == current_end]
        # The current reporting metric is the shortest duration at the latest
        # end date (3-month for a 10-Q quarter; the only/annual duration for a
        # 10-K; the YTD-only duration when a filer reports no 3-month column).
        current = min(at_current_end, key=lambda e: e['days'] if e['days'] is not None else 10 ** 9)
        target_bucket = current['bucket']
        same_bucket = sorted([e for e in durations if e['bucket'] == target_bucket],
                             key=lambda e: e['end'], reverse=True)
        other_durations = sorted([e for e in durations if e['bucket'] != target_bucket],
                                 key=lambda e: e['end'], reverse=True)
        ordered.extend(same_bucket)
        ordered.extend(other_durations)
    ordered.extend(sorted(instants, key=lambda e: e['end'], reverse=True))

    # Emit ordered names, de-duplicated, then append any df columns we couldn't
    # map (unknown period metadata) so nothing is silently dropped.
    seen = set()
    result = []
    for entry in ordered:
        if entry['name'] not in seen:
            seen.add(entry['name'])
            result.append(entry['name'])
    for name in df_period_columns:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


class Financials:
    def __init__(self, xb: Optional[XBRL]):
        self.xb: XBRL = xb

    @classmethod
    def extract(cls, filing) -> Optional["Financials"]:
        try:
            xb = XBRL.from_filing(filing)
            return Financials(xb)
        except XBRLFilingWithNoXbrlData as e:
            # Handle the case where the filing does not have XBRL data
            log.warning(f"Filing {filing} does not contain XBRL data: {e}")
            return None

    def balance_sheet(self, include_dimensions: bool = None, view: ViewType = None):
        """
        Get the balance sheet.

        Args:
            include_dimensions: Default setting for whether to include dimensional segment data
                              when rendering or converting to DataFrame (default: False)
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation matching SEC Viewer (display default)
                  DETAILED: All dimensional data included (to_dataframe default)
                  SUMMARY: Non-dimensional totals only

        Returns:
            A Statement object for the balance sheet, or None if not available
        """
        if self.xb is None:
            return None
        return self.xb.statements.balance_sheet(include_dimensions=include_dimensions, view=view)

    def income_statement(self, include_dimensions: bool = None, view: ViewType = None):
        """
        Get the income statement.

        Args:
            include_dimensions: Default setting for whether to include dimensional segment data
                              when rendering or converting to DataFrame (default: False)
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation matching SEC Viewer (display default)
                  DETAILED: All dimensional data included (to_dataframe default)
                  SUMMARY: Non-dimensional totals only

        Returns:
            A Statement object for the income statement, or None if not available
        """
        if self.xb is None:
            return None
        return self.xb.statements.income_statement(include_dimensions=include_dimensions, view=view)

    def cashflow_statement(self, include_dimensions: bool = None, view: ViewType = None):
        """
        Get the cash flow statement.

        Args:
            include_dimensions: Default setting for whether to include dimensional segment data
                              when rendering or converting to DataFrame (default: False)
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation matching SEC Viewer (display default)
                  DETAILED: All dimensional data included (to_dataframe default)
                  SUMMARY: Non-dimensional totals only

        Returns:
            A Statement object for the cash flow statement, or None if not available
        """
        if self.xb is None:
            return None
        return self.xb.statements.cashflow_statement(include_dimensions=include_dimensions, view=view)

    def cash_flow_statement(self, **kwargs):
        """Alias for cashflow_statement()."""
        return self.cashflow_statement(**kwargs)

    def statement_of_equity(self, include_dimensions: bool = None, view: ViewType = None):
        """
        Get the statement of equity.

        Args:
            include_dimensions: Default setting for whether to include dimensional segment data
                              when rendering or converting to DataFrame (default: False)
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation matching SEC Viewer (display default)
                  DETAILED: All dimensional data included (to_dataframe default)
                  SUMMARY: Non-dimensional totals only

        Returns:
            A Statement object for the statement of equity, or None if not available
        """
        if self.xb is None:
            return None
        return self.xb.statements.statement_of_equity(include_dimensions=include_dimensions, view=view)

    def comprehensive_income(self, include_dimensions: bool = None, view: ViewType = None):
        """
        Get the comprehensive income statement.

        Args:
            include_dimensions: Default setting for whether to include dimensional segment data
                              when rendering or converting to DataFrame (default: False)
            view: StatementView controlling dimensional data display.
                  STANDARD: Face presentation matching SEC Viewer (display default)
                  DETAILED: All dimensional data included (to_dataframe default)
                  SUMMARY: Non-dimensional totals only

        Returns:
            A Statement object for the comprehensive income statement, or None if not available
        """
        if self.xb is None:
            return None
        return self.xb.statements.comprehensive_income(include_dimensions=include_dimensions, view=view)

    def cover(self):
        """
        Get the cover page.

        Returns:
            A Statement object for the cover page, or None if not available
        """
        if self.xb is None:
            return None
        return self.xb.statements.cover_page()

    # Standardized Financial Data Accessor Methods
    # These methods provide easy access to common financial metrics
    # using standardized labels across different companies

    def _get_standardized_concept_by_xbrl(self, statement_type: str,
                                          standard_concept_names: List[str],
                                          period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Robust helper method to extract concept values by XBRL concept names.

        This method uses the standardization system's concept mappings to search
        by XBRL concept names (e.g., 'us-gaap_RevenueFromContractWithCustomer...')
        rather than display labels, making it more reliable across companies.

        Args:
            statement_type: Type of statement ('income', 'balance', 'cashflow')
            standard_concept_names: List of standardized concept names to try in order
                                   (e.g., ['Contract Revenue', 'Revenue'])
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            The concept value if found, None otherwise
        """
        if self.xb is None:
            return None

        try:
            # Load the standardization mappings
            from edgar.xbrl.standardization import get_default_store
            standardizer = get_default_store()

            # Get the appropriate statement
            if statement_type == 'income':
                statement = self.income_statement()
            elif statement_type == 'balance':
                statement = self.balance_sheet()
            elif statement_type == 'cashflow':
                statement = self.cashflow_statement()
            else:
                return None

            if statement is None:
                return None

            # Render the statement
            rendered = statement.render(standard=True)
            df = rendered.to_dataframe()

            if df.empty or 'concept' not in df.columns:
                return None

            # Filter out abstract rows - they never have values
            if 'abstract' in df.columns:
                df = df[~df['abstract']].copy()

            # Get period columns, ordered most-recent-first by period metadata
            # (positional df order is not recency-sorted — GH #885).
            period_columns = [col for col in df.columns if col not in _NON_PERIOD_COLUMNS]
            period_columns = _order_period_columns(rendered, period_columns)

            if len(period_columns) <= period_offset:
                return None

            period_col = period_columns[period_offset]

            def _strip_ns(name: str) -> str:
                # Normalize a concept name to its bare local-name for exact comparison.
                # Strips the standard taxonomy namespaces edgartools maps against
                # (us-gaap, dei, ifrs-full). Company-specific prefixes are left
                # intact on both sides of the comparison and still match exactly.
                return (str(name)
                        .replace('us-gaap_', '')
                        .replace('us-gaap:', '')
                        .replace('dei_', '')
                        .replace('dei:', '')
                        .replace('ifrs-full_', '')
                        .replace('ifrs-full:', ''))

            concept_local = df['concept'].astype(str).map(_strip_ns).str.lower()

            # Try each standard concept name in order
            for std_concept_name in standard_concept_names:
                # Get all XBRL concepts that map to this standard concept.
                # The standardizer stores these as a set, so we sort to make
                # iteration order deterministic across runs (otherwise a filer
                # whose statement contains multiple mapped concepts can return
                # different values depending on Python hash randomization).
                xbrl_concepts = sorted(standardizer.mappings.get(std_concept_name, []))

                # Search for any of these concepts in the dataframe
                for xbrl_concept in xbrl_concepts:
                    # Exact local-name match (case-insensitive). Substring matching
                    # is unsafe here: e.g. 'NetIncome' substring-matches the
                    # NetIncomeLossAttributableToNoncontrollingInterest row and
                    # produces wrong values (Issue #814).
                    target = _strip_ns(xbrl_concept).lower()
                    matches = df[concept_local == target]

                    if not matches.empty:
                        # Try each match until we find one with a valid value
                        for idx in range(len(matches)):
                            value = matches.iloc[idx][period_col]

                            # Skip empty/NA values
                            if pd.isna(value) or value == '':
                                continue

                            # Convert to numeric
                            try:
                                return float(value) if '.' in str(value) else int(value)
                            except (ValueError, TypeError):
                                continue

            return None

        except Exception as e:
            log.debug(f"Error getting standardized concept by XBRL: {e}")
            return None

    def _get_standardized_concept_value(self, statement_type: str, concept_patterns: list,
                                      period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Helper method to extract standardized concept values from financial statements.

        Args:
            statement_type: Type of statement ('income', 'balance', 'cashflow')
            concept_patterns: List of label patterns to search for (case-insensitive)
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            The concept value if found, None otherwise
        """
        if self.xb is None:
            return None

        try:
            # Get the appropriate statement
            if statement_type == 'income':
                statement = self.income_statement()
            elif statement_type == 'balance':
                statement = self.balance_sheet()
            elif statement_type == 'cashflow':
                statement = self.cashflow_statement()
            else:
                return None

            if statement is None:
                return None

            # Render with standardization enabled
            rendered = statement.render(standard=True)
            df = rendered.to_dataframe()

            if df.empty:
                return None

            # Filter out abstract rows - they never have values
            if 'abstract' in df.columns:
                df = df[~df['abstract']].copy()

            # Find the concept using pattern matching
            for pattern in concept_patterns:
                matches = df[df['label'].str.contains(pattern, case=False, na=False)]
                if not matches.empty:
                    # Get available period columns, ordered most-recent-first by
                    # period metadata (positional df order is not recency-sorted
                    # — GH #885).
                    period_columns = [col for col in df.columns if col not in _NON_PERIOD_COLUMNS]
                    period_columns = _order_period_columns(rendered, period_columns)

                    if len(period_columns) > period_offset:
                        period_col = period_columns[period_offset]

                        # Try each match until we find one with a valid value
                        for idx in range(len(matches)):
                            value = matches.iloc[idx][period_col]

                            # Skip empty/NA values
                            if pd.isna(value) or value == '':
                                continue

                            # Convert to numeric
                            try:
                                return float(value) if '.' in str(value) else int(value)
                            except (ValueError, TypeError):
                                continue

            return None

        except Exception as e:
            log.debug(f"Error getting standardized concept value: {e}")
            return None

    def get_revenue(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get revenue from the income statement using standardized XBRL concepts.

        This method uses a robust concept-based search that works across different
        companies regardless of how they label their revenue in presentations.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Revenue value if found, None otherwise

        Example:
            >>> company = Company('AAPL')
            >>> financials = company.get_financials()
            >>> revenue = financials.get_revenue()  # Most recent revenue
            >>> prev_revenue = financials.get_revenue(1)  # Previous period revenue
        """
        # First try concept-based search using standardization mappings
        # Try "Contract Revenue" first (more specific), then "Revenue" (more general)
        result = self._get_standardized_concept_by_xbrl(
            'income',
            ['Contract Revenue', 'Revenue'],
            period_offset
        )

        if result is not None:
            return result

        # Fallback to label-based search for edge cases
        patterns = [
            r'Revenue$',           # Exact match for "Revenue"
            r'^Revenue',           # Starts with "Revenue"
            r'Contract Revenue',   # Common standardized label
            r'Sales Revenue',      # Alternative form
            r'Total Revenue',      # Comprehensive revenue
            r'Net Revenue'         # Net form
        ]
        return self._get_standardized_concept_value('income', patterns, period_offset)

    def get_net_income(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get net income from the income statement using standardized XBRL concepts.

        Concept-based lookup runs first so the canonical
        ``us-gaap:NetIncomeLoss`` is preferred over rows that happen to be
        labeled "Net income ..." (e.g. noncontrolling-interest lines).

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Net income value if found, None otherwise

        Example:
            >>> company = Company('AAPL')
            >>> financials = company.get_financials()
            >>> net_income = financials.get_net_income()
        """
        # First try concept-based search using standardization mappings.
        # 'Net Income' covers us-gaap_NetIncome / us-gaap_NetIncomeLoss (the
        # parent-attributable line for US GAAP filers reporting NCI).
        # 'Profit or Loss' covers us-gaap_ProfitLoss and the IFRS variants
        # (ifrs-full_ProfitLoss, ifrs-full_ProfitLossAttributableToOwnersOfParent)
        # used by 20-F filers — these would otherwise miss when the row label
        # is not "Net income" (e.g. "Profit after tax").
        result = self._get_standardized_concept_by_xbrl(
            'income',
            ['Net Income', 'Profit or Loss'],
            period_offset
        )
        if result is not None:
            return result

        # Fallback to label-based search for filers whose concept isn't in
        # the standardization map. Includes 'Net Loss' variants (filer reporting
        # a loss labels the row "Net loss attributable to ...") and 'Profit/Loss'
        # for IFRS labels like "Profit (loss) for the year". All patterns
        # explicitly exclude "noncontrolling" so we don't pick the NCI row.
        patterns = [
            r'Net Income$',
            r'^Net Income(?!.*[Nn]oncontrolling)',
            r'^Net Loss(?!.*[Nn]oncontrolling)',
            r'Net Income.*Common',
            r'Net Income.*Shareholders',
            r'Net Loss.*Common',
            r'Net Loss.*Shareholders',
            r'Net Earnings',
            r'Profit.*Loss(?!.*[Nn]oncontrolling)',
        ]
        return self._get_standardized_concept_value('income', patterns, period_offset)

    def get_operating_income(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get operating income from the income statement using standardized XBRL concepts.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Operating income value if found, None otherwise

        Example:
            >>> company = Company('AAPL')
            >>> financials = company.get_financials()
            >>> operating_income = financials.get_operating_income()
        """
        # First try concept-based search using standardization mappings
        result = self._get_standardized_concept_by_xbrl(
            'income',
            ['Operating Income'],
            period_offset
        )
        if result is not None:
            return result

        # Fallback to label-based search for edge cases
        patterns = [
            r'Operating Income$',
            r'^Operating Income',
            r'Income.*Operations',
            r'Operating.*Income.*Loss',
        ]
        return self._get_standardized_concept_value('income', patterns, period_offset)

    def get_total_assets(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get total assets from the balance sheet using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Total assets value if found, None otherwise

        Example:
            >>> company = Company('AAPL')
            >>> financials = company.get_financials()
            >>> total_assets = financials.get_total_assets()
        """
        patterns = [
            r'Total Assets$',      # Exact match
            r'^Total Assets',      # Starts with
            r'Assets$'             # Just "Assets"
        ]
        return self._get_standardized_concept_value('balance', patterns, period_offset)

    def get_total_liabilities(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get total liabilities from the balance sheet using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Total liabilities value if found, None otherwise
        """
        patterns = [
            r'Total Liabilities$',
            r'^Total Liabilities',
            r'Liabilities$'
        ]
        return self._get_standardized_concept_value('balance', patterns, period_offset)

    def get_stockholders_equity(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get stockholders' equity from the balance sheet using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Stockholders' equity value if found, None otherwise
        """
        patterns = [
            r'Total.*Stockholders.*Equity',
            r'Stockholders.*Equity$',
            r'Shareholders.*Equity',
            r'Total.*Equity$',
            r'^Equity$'
        ]
        return self._get_standardized_concept_value('balance', patterns, period_offset)

    def get_operating_cash_flow(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get operating cash flow from the cash flow statement using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Operating cash flow value if found, None otherwise
        """
        patterns = [
            r'^Net Cash from Operating',          # Most specific - matches "Net Cash from Operating Activities"
            r'^Net Cash Provided by Operating',   # Alternative phrasing
            r'Net Cash.*Operating Activities$',   # Anchored to end
            r'Operating.*Cash.*Flow',
            r'Net Cash.*Operations$',             # Avoid matching "adjustments to reconcile..."
        ]
        return self._get_standardized_concept_value('cashflow', patterns, period_offset)

    def get_free_cash_flow(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Calculate free cash flow (Operating Cash Flow - Capital Expenditures).

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Free cash flow if both components found, None otherwise
        """
        operating_cf = self.get_operating_cash_flow(period_offset)
        capex = self.get_capital_expenditures(period_offset)

        if operating_cf is not None and capex is not None:
            # CapEx is usually negative, so we subtract it (making FCF = OCF - |CapEx|)
            return operating_cf - abs(capex)
        return None

    def get_capital_expenditures(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get capital expenditures from the cash flow statement using standardized XBRL concepts.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Capital expenditures value if found, None otherwise
        """
        # First try concept-based search using standardization mappings
        result = self._get_standardized_concept_by_xbrl(
            'cashflow',
            ['Payments for Property, Plant and Equipment'],
            period_offset
        )

        if result is not None:
            return result

        # Fallback to label-based search for edge cases
        patterns = [
            r'Capital Expenditures',
            r'Additions.*property.*equipment',  # MSFT: "Additions to property and equipment"
            r'Purchase.*Property',
            r'Capex'
        ]
        return self._get_standardized_concept_value('cashflow', patterns, period_offset)

    def get_current_assets(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get current assets from the balance sheet using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Current assets value if found, None otherwise
        """
        patterns = [
            r'Total Current Assets',
            r'^Current Assets',
            r'Assets Current'
        ]
        return self._get_standardized_concept_value('balance', patterns, period_offset)

    def get_current_liabilities(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get current liabilities from the balance sheet using standardized labels.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Current liabilities value if found, None otherwise
        """
        patterns = [
            r'Total Current Liabilities',
            r'^Current Liabilities',
            r'Liabilities Current'
        ]
        return self._get_standardized_concept_value('balance', patterns, period_offset)

    def _get_concept_value(self, statement_type: str, concept_patterns: List[str], period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Helper method to extract values by XBRL concept name (not label).

        This is more reliable than label-based search for concepts like shares outstanding
        where the display label varies by company but the XBRL concept is standardized.

        Args:
            statement_type: Type of statement ('income', 'balance', 'cashflow')
            concept_patterns: List of concept name patterns to search for (case-insensitive regex)
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            The concept value if found, None otherwise
        """
        if self.xb is None:
            return None

        try:
            # Get the appropriate statement
            if statement_type == 'income':
                statement = self.income_statement()
            elif statement_type == 'balance':
                statement = self.balance_sheet()
            elif statement_type == 'cashflow':
                statement = self.cashflow_statement()
            else:
                return None

            if statement is None:
                return None

            # Render with standardization enabled
            rendered = statement.render(standard=True)
            df = rendered.to_dataframe()

            if df.empty or 'concept' not in df.columns:
                return None

            # Find the concept using pattern matching on concept column
            for pattern in concept_patterns:
                matches = df[df['concept'].str.contains(pattern, case=False, na=False)]
                if not matches.empty:
                    # Get available period columns, ordered most-recent-first by
                    # period metadata (positional df order is not recency-sorted
                    # — GH #885).
                    period_columns = [col for col in df.columns if col not in _NON_PERIOD_COLUMNS]
                    period_columns = _order_period_columns(rendered, period_columns)

                    if len(period_columns) > period_offset:
                        period_col = period_columns[period_offset]
                        value = matches.iloc[0][period_col]

                        # Skip empty/NA values - try next pattern
                        if pd.isna(value) or value == '':
                            continue

                        # Convert to numeric
                        try:
                            return float(value) if '.' in str(value) else int(value)
                        except (ValueError, TypeError):
                            # Non-numeric value, try next pattern
                            continue

            return None

        except Exception as e:
            log.debug(f"Error getting concept value: {e}")
            return None

    def get_shares_outstanding_basic(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get weighted average basic shares outstanding from the income statement.

        This returns the weighted average number of basic shares outstanding used
        in computing basic earnings per share (EPS).

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Basic shares outstanding if found, None otherwise

        Example:
            >>> company = Company('AAPL')
            >>> financials = company.get_financials()
            >>> shares = financials.get_shares_outstanding_basic()
            >>> print(f"Basic shares: {shares:,.0f}")

            >>> # Get previous period
            >>> prev_shares = financials.get_shares_outstanding_basic(period_offset=1)

            >>> # Also works with quarterly financials
            >>> quarterly = company.get_quarterly_financials()
            >>> q_shares = quarterly.get_shares_outstanding_basic()
        """
        # Search by XBRL concept name - more reliable than label matching
        concept_patterns = [
            r'WeightedAverageNumberOfSharesOutstandingBasic',
            r'CommonStockSharesOutstanding',  # Fallback for some filings
        ]
        return self._get_concept_value('income', concept_patterns, period_offset)

    def get_shares_outstanding_diluted(self, period_offset: int = 0) -> Optional[Union[int, float]]:
        """
        Get weighted average diluted shares outstanding from the income statement.

        This returns the weighted average number of diluted shares outstanding used
        in computing diluted earnings per share (EPS). Diluted shares include the
        effect of stock options, convertible securities, and other dilutive instruments.

        Args:
            period_offset: Which period to get (0=most recent, 1=previous, etc.)

        Returns:
            Diluted shares outstanding if found, None otherwise

        Example:
            >>> company = Company('AAPL')
            >>> financials = company.get_financials()
            >>> diluted_shares = financials.get_shares_outstanding_diluted()
            >>> print(f"Diluted shares: {diluted_shares:,.0f}")

            >>> # Compare basic vs diluted
            >>> basic = financials.get_shares_outstanding_basic()
            >>> diluted = financials.get_shares_outstanding_diluted()
            >>> dilution = (diluted - basic) / basic * 100 if basic else None
            >>> print(f"Dilution effect: {dilution:.2f}%")
        """
        # Search by XBRL concept name - more reliable than label matching
        concept_patterns = [
            r'WeightedAverageNumberOfDilutedSharesOutstanding',
            r'WeightedAverageNumberOfSharesOutstandingDiluted',  # Alternative naming
        ]
        return self._get_concept_value('income', concept_patterns, period_offset)

    def get_financial_metrics(self) -> Dict[str, Any]:
        """
        Get a dictionary of common financial metrics using standardized labels.

        Returns:
            Dictionary containing available financial metrics

        Example:
            >>> company = Company('AAPL')
            >>> financials = company.get_financials()
            >>> metrics = financials.get_financial_metrics()
            >>> print(f"Revenue: ${metrics.get('revenue', 'N/A'):,}")
        """
        metrics = {}

        # Income Statement Metrics
        metrics['revenue'] = self.get_revenue()
        metrics['operating_income'] = self.get_operating_income()
        metrics['net_income'] = self.get_net_income()

        # Balance Sheet Metrics
        metrics['total_assets'] = self.get_total_assets()
        metrics['total_liabilities'] = self.get_total_liabilities()
        metrics['stockholders_equity'] = self.get_stockholders_equity()
        metrics['current_assets'] = self.get_current_assets()
        metrics['current_liabilities'] = self.get_current_liabilities()

        # Cash Flow Metrics
        metrics['operating_cash_flow'] = self.get_operating_cash_flow()
        metrics['capital_expenditures'] = self.get_capital_expenditures()
        metrics['free_cash_flow'] = self.get_free_cash_flow()

        # Share Metrics
        metrics['shares_outstanding_basic'] = self.get_shares_outstanding_basic()
        metrics['shares_outstanding_diluted'] = self.get_shares_outstanding_diluted()

        # Calculate basic ratios if we have the data
        if metrics['current_assets'] and metrics['current_liabilities']:
            try:
                metrics['current_ratio'] = metrics['current_assets'] / metrics['current_liabilities']
            except (TypeError, ZeroDivisionError):
                metrics['current_ratio'] = None
        else:
            metrics['current_ratio'] = None

        if metrics['total_liabilities'] and metrics['total_assets']:
            try:
                metrics['debt_to_assets'] = metrics['total_liabilities'] / metrics['total_assets']
            except (TypeError, ZeroDivisionError):
                metrics['debt_to_assets'] = None
        else:
            metrics['debt_to_assets'] = None

        return metrics

    def __str__(self):
        """Concise string representation for LLMs and logging."""
        if self.xb is None:
            return "Financials(No data)"

        info = self.xb.entity_info
        name = info.get('entity_name', 'Unknown')
        ticker = info.get('ticker', '')
        doc_type = info.get('document_type', '')
        fiscal_year = info.get('fiscal_year', '')
        fiscal_period = info.get('fiscal_period', '')

        # Build period string (e.g., "FY2025" or "Q3 2025")
        period_str = f"{fiscal_period}{fiscal_year}" if fiscal_period and fiscal_year else ""

        # Fact count
        fact_count = len(self.xb.facts) if self.xb.facts else 0

        parts = [name]
        if ticker:
            parts.append(f"[{ticker}]")
        if doc_type:
            parts.append(doc_type)
        if period_str:
            parts.append(period_str)
        parts.append(f"• {fact_count:,} facts")

        return f"Financials({' '.join(parts)})"

    def get_currency_symbol(self) -> str:
        """
        Get the reporting currency symbol for this filing.

        Detects the most common monetary unit from the XBRL units dict.
        Returns '$' as default if currency cannot be determined.
        """
        if self.xb is None:
            return "$"
        try:
            from collections import Counter
            from edgar.xbrl.core import get_currency_symbol as _get_sym
            # Count currency measures across all unit definitions
            currencies = Counter()
            for unit_info in self.xb.units.values():
                if unit_info.get('type') == 'simple':
                    measure = unit_info.get('measure', '')
                    if measure.startswith('iso4217:'):
                        currencies[measure] += 1
            if currencies:
                most_common = currencies.most_common(1)[0][0]
                return _get_sym(most_common)
        except Exception:
            pass
        return "$"

    def to_context(self) -> str:
        """
        Return context string for LLMs with available actions.

        This guides AI agents on what they can do with this Financials object,
        focusing on the high-level Financials API rather than raw XBRL access.
        """
        if self.xb is None:
            return "Financials: No data available"

        info = self.xb.entity_info
        name = info.get('entity_name', 'Unknown')
        ticker = info.get('ticker', '')
        doc_type = info.get('document_type', '')
        fiscal_year = info.get('fiscal_year', '')
        fiscal_period = info.get('fiscal_period', '')

        ticker_part = f" [{ticker}]" if ticker else ""
        period_str = f"{fiscal_period}{fiscal_year}" if fiscal_period and fiscal_year else ""

        lines = [
            f"Financials: {name}{ticker_part} {doc_type} {period_str}".strip(),
            "",
            "AVAILABLE STATEMENTS:",
            "  financials.income_statement()",
            "  financials.balance_sheet()",
            "  financials.cashflow_statement()",
            "  financials.statement_of_equity()",
            "  financials.comprehensive_income()",
            "",
            "QUICK METRICS (returns value or None):",
            "  financials.get_revenue()",
            "  financials.get_operating_income()",
            "  financials.get_net_income()",
            "  financials.get_total_assets()",
            "  financials.get_stockholders_equity()",
            "  financials.get_operating_cash_flow()",
            "  financials.get_free_cash_flow()",
            "",
            "ALL METRICS:",
            "  financials.get_financial_metrics()  # Dict with 14 metrics + ratios",
        ]

        return "\n".join(lines)

    def __rich__(self):
        if self.xb is None:
            return "No XBRL data available"
        return self.xb.__rich__()

    def __repr__(self):
        return repr_rich(self.__rich__())


class MultiFinancials:
    """
    Merges the financial statements from multiple periods into a single financials.
    """

    def __init__(self, xbs: XBRLS):
        self.xbs = xbs

    @classmethod
    def extract(cls, filings) -> "MultiFinancials":
        return cls(XBRLS.from_filings(filings))

    def balance_sheet(self, view: ViewType = None) -> Optional[StitchedStatement]:
        return self.xbs.statements.balance_sheet(view=view)

    def income_statement(self, view: ViewType = None) -> Optional[StitchedStatement]:
        return self.xbs.statements.income_statement(view=view)

    def cashflow_statement(self, view: ViewType = None) -> Optional[StitchedStatement]:
        return self.xbs.statements.cashflow_statement(view=view)

    def cash_flow_statement(self, **kwargs):
        """Alias for cashflow_statement()."""
        return self.cashflow_statement(**kwargs)

    def __rich__(self):
        return self.xbs.__rich__()

    def __repr__(self):
        return repr_rich(self.__rich__())
