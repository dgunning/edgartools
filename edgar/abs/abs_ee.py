"""
Form ABS-EE Asset Data Parser.

Form ABS-EE (Asset-Backed Securities - Exchange Act) provides asset-level data
for securitized assets. This module parses the EX-102 XML exhibits.

Supported Asset Types:
- Auto Lease (autolease schema) - BMW Vehicle Lease Trust, etc.
- Auto Loan (autoloan schema)

Usage:
    from edgar import find
    from edgar.abs.abs_ee import AutoLeaseAssetData

    filing = find('0000929638-25-004537')  # BMW ABS-EE
    parser = AutoLeaseAssetData.from_filing(filing)

    # Access as DataFrame
    df = parser.assets
    print(df[['vehicle_manufacturer', 'vehicle_model', 'credit_score']].head())

    # Get summary
    summary = parser.summary()
    print(f"Total assets: {summary.num_assets:,}")
    print(f"Total value: ${summary.total_acquisition_cost:,.0f}")
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, Optional
from xml.etree import ElementTree as ET

import pandas as pd
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich

__all__ = ['AutoLeaseAssetData', 'AutoLeaseSummary']


# Namespace mappings for ABS-EE XML
NAMESPACES = {
    'autolease': 'http://www.sec.gov/edgar/document/absee/autolease/assetdata',
    'autoloan': 'http://www.sec.gov/edgar/document/absee/autoloan/assetdata',
}


@dataclass
class AutoLeaseSummary:
    """Summary statistics for auto lease asset data."""
    num_assets: int = 0
    total_acquisition_cost: float = 0.0
    total_residual_value: float = 0.0
    avg_credit_score: Optional[float] = None
    avg_lease_term: Optional[float] = None

    # Vehicle distribution
    vehicle_makes: Dict[str, int] = field(default_factory=dict)
    vehicle_types: Dict[str, int] = field(default_factory=dict)
    model_years: Dict[int, int] = field(default_factory=dict)

    # Geographic distribution
    states: Dict[str, int] = field(default_factory=dict)


class AutoLeaseAssetData:
    """
    Parser for Auto Lease ABS-EE EX-102 XML asset data.

    Extracts asset-level lease data including vehicle information,
    lessee credit data, and lease terms from BMW and similar auto
    lease securitizations.

    Example:
        >>> from edgar import find
        >>> from edgar.abs.abs_ee import AutoLeaseAssetData
        >>> filing = find('0000929638-25-004537')
        >>> parser = AutoLeaseAssetData.from_filing(filing)
        >>> print(f"Loaded {len(parser)} assets")
        >>> df = parser.assets
    """

    # Field mappings: XML tag -> (DataFrame column, parser function)
    ASSET_FIELDS = {
        'assetNumber': ('asset_id', str),
        'assetTypeNumber': ('asset_type', str),
        'reportingPeriodBeginDate': ('period_start', '_parse_date'),
        'reportingPeriodEndDate': ('period_end', '_parse_date'),
        'originatorName': ('originator', str),
        'originationDate': ('origination_date', '_parse_month_year'),
        'acquisitionCost': ('acquisition_cost', float),
        'originalLeaseTermNumber': ('original_term_months', int),
        'scheduledTerminationDate': ('termination_date', '_parse_month_year'),
        'originalFirstPaymentDate': ('first_payment_date', '_parse_month_year'),
        'gracePeriod': ('grace_period_days', int),
        'paymentTypeCode': ('payment_type_code', str),
        # Vehicle fields
        'vehicleManufacturerName': ('vehicle_manufacturer', str),
        'vehicleModelName': ('vehicle_model', str),
        'vehicleNewUsedCode': ('vehicle_new_used', str),
        'vehicleModelYear': ('vehicle_year', int),
        'vehicleTypeCode': ('vehicle_type_code', str),
        'vehicleValueAmount': ('vehicle_value', float),
        'baseResidualValue': ('base_residual_value', float),
        'contractResidualValue': ('contract_residual_value', float),
        # Lessee credit fields
        'lesseeCreditScoreType': ('credit_score_type', str),
        'lesseeCreditScore': ('credit_score', int),
        'lesseeIncomeVerificationLevelCode': ('income_verification_code', str),
        'lesseeEmploymentVerificationCode': ('employment_verification_code', str),
        'paymentToIncomePercentage': ('payment_to_income_ratio', float),
        'lesseeGeographicLocation': ('lessee_state', str),
        'coLesseePresentIndicator': ('has_co_lessee', '_parse_bool'),
        # Payment/status fields
        'scheduledPaymentAmount': ('scheduled_payment', float),
        'actualPaymentAmount': ('actual_payment', float),
        'paidThroughDate': ('paid_through_date', '_parse_month_year'),
        'zeroBalanceCode': ('zero_balance_code', str),
        'zeroBalanceEffectiveDate': ('zero_balance_date', '_parse_month_year'),
        'currentDelinquencyStatus': ('delinquency_status', int),
        'remainingTermToMaturityNumber': ('remaining_term_months', int),
        'securitizationLeaseBalance': ('securitization_balance', float),
        'reportingPeriodBeginningLeaseBalanceAmount': ('beginning_balance', float),
        'reportingPeriodEndingActualBalance': ('ending_balance', float),
    }

    # Vehicle type code mappings
    VEHICLE_TYPE_CODES = {
        '1': 'Passenger Car',
        '2': 'SUV',
        '3': 'Light Truck',
        '4': 'Motorcycle',
        '5': 'Recreational Vehicle',
        '98': 'Other',
        '99': 'Unknown',
    }

    def __init__(self, xml_content: str):
        """
        Initialize from XML content.

        Args:
            xml_content: Raw XML string from EX-102 exhibit
        """
        self._xml_content = xml_content
        self._assets_df: Optional[pd.DataFrame] = None
        self._parse()

    @classmethod
    def from_filing(cls, filing) -> Optional['AutoLeaseAssetData']:
        """
        Create parser from an ABS-EE filing.

        Args:
            filing: Filing object (ABS-EE form)

        Returns:
            AutoLeaseAssetData or None if no EX-102 exhibit found
        """
        for attachment in filing.attachments:
            if attachment.document_type and 'EX-102' in attachment.document_type.upper():
                xml_content = attachment.text()
                if xml_content:
                    return cls(xml_content)
        return None

    def _parse(self):
        """Parse the XML content into a DataFrame."""
        try:
            root = ET.fromstring(self._xml_content)
        except ET.ParseError:
            self._assets_df = pd.DataFrame()
            return

        # Detect namespace
        ns = None
        for prefix, uri in NAMESPACES.items():
            if uri in self._xml_content:
                ns = {'ns': uri}
                break

        # Find all asset elements
        if ns:
            assets = root.findall('.//ns:assets', ns)
        else:
            assets = root.findall('.//assets')

        if not assets:
            self._assets_df = pd.DataFrame()
            return

        # Parse each asset
        rows = []
        for asset in assets:
            row = {}
            for xml_tag, (col_name, parser) in self.ASSET_FIELDS.items():
                if ns:
                    elem = asset.find(f'ns:{xml_tag}', ns)
                else:
                    elem = asset.find(xml_tag)

                if elem is not None and elem.text:
                    value = elem.text.strip()
                    if parser == str:
                        row[col_name] = value
                    elif parser == int:
                        row[col_name] = self._safe_int(value)
                    elif parser == float:
                        row[col_name] = self._safe_float(value)
                    elif parser == '_parse_date':
                        row[col_name] = self._parse_date(value)
                    elif parser == '_parse_month_year':
                        row[col_name] = self._parse_month_year(value)
                    elif parser == '_parse_bool':
                        row[col_name] = self._parse_bool(value)
                else:
                    row[col_name] = None

            rows.append(row)

        self._assets_df = pd.DataFrame(rows)

    @staticmethod
    def _safe_int(value: str) -> Optional[int]:
        """Safely parse integer, returning None on failure."""
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_float(value: str) -> Optional[float]:
        """Safely parse float, returning None on failure."""
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        """Parse date in MM-DD-YYYY format."""
        from datetime import datetime
        try:
            return datetime.strptime(value, '%m-%d-%Y').date()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_month_year(value: str) -> Optional[str]:
        """Parse MM/YYYY format, returning as string."""
        # Keep as string for month/year only values
        if value and '/' in value:
            return value.strip()
        return None

    @staticmethod
    def _parse_bool(value: str) -> Optional[bool]:
        """Parse boolean string."""
        if value:
            return value.lower() in ('true', '1', 'yes')
        return None

    @property
    def assets(self) -> pd.DataFrame:
        """
        Asset-level data as a DataFrame.

        Returns DataFrame with columns including:
        - asset_id, originator, origination_date
        - vehicle_manufacturer, vehicle_model, vehicle_year
        - credit_score, lessee_state
        - acquisition_cost, residual values
        - payment and balance information
        """
        return self._assets_df if self._assets_df is not None else pd.DataFrame()

    def __len__(self) -> int:
        """Number of assets in the dataset."""
        return len(self.assets)

    def summary(self) -> AutoLeaseSummary:
        """
        Calculate summary statistics for the asset data.

        Returns:
            AutoLeaseSummary with aggregate metrics
        """
        df = self.assets

        if df.empty:
            return AutoLeaseSummary()

        summary = AutoLeaseSummary(num_assets=len(df))

        # Financial totals
        if 'acquisition_cost' in df.columns:
            summary.total_acquisition_cost = df['acquisition_cost'].sum()

        if 'contract_residual_value' in df.columns:
            summary.total_residual_value = df['contract_residual_value'].sum()

        # Averages
        if 'credit_score' in df.columns:
            scores = df['credit_score'].dropna()
            if len(scores) > 0:
                summary.avg_credit_score = scores.mean()

        if 'original_term_months' in df.columns:
            terms = df['original_term_months'].dropna()
            if len(terms) > 0:
                summary.avg_lease_term = terms.mean()

        # Vehicle distribution
        if 'vehicle_manufacturer' in df.columns:
            summary.vehicle_makes = df['vehicle_manufacturer'].value_counts().to_dict()

        if 'vehicle_type_code' in df.columns:
            type_counts = df['vehicle_type_code'].value_counts()
            summary.vehicle_types = {
                self.VEHICLE_TYPE_CODES.get(str(k), str(k)): v
                for k, v in type_counts.items()
            }

        if 'vehicle_year' in df.columns:
            summary.model_years = df['vehicle_year'].value_counts().to_dict()

        # Geographic distribution
        if 'lessee_state' in df.columns:
            summary.states = df['lessee_state'].value_counts().to_dict()

        return summary

    def __str__(self) -> str:
        return f"AutoLeaseAssetData({len(self):,} assets)"

    def __repr__(self) -> str:
        return repr_rich(self.__rich__())

    def __rich__(self):
        """Rich console representation."""
        summary = self.summary()

        title = Text.assemble(
            ("Auto Lease Asset Data", "bold deep_sky_blue1"),
            (" ", ""),
            (f"({summary.num_assets:,} assets)", "dim"),
        )

        # Info table
        info_table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
        info_table.add_column("Label", style="grey70")
        info_table.add_column("Value")

        info_table.add_row("Total Assets", f"{summary.num_assets:,}")
        info_table.add_row("Acquisition Cost", f"${summary.total_acquisition_cost:,.0f}")
        info_table.add_row("Residual Value", f"${summary.total_residual_value:,.0f}")

        if summary.avg_credit_score:
            info_table.add_row("Avg Credit Score", f"{summary.avg_credit_score:.0f}")

        if summary.avg_lease_term:
            info_table.add_row("Avg Lease Term", f"{summary.avg_lease_term:.0f} months")

        # Top vehicle makes
        if summary.vehicle_makes:
            info_table.add_row("", "")
            top_makes = sorted(summary.vehicle_makes.items(), key=lambda x: -x[1])[:3]
            makes_str = ", ".join(f"{make.strip()}: {count:,}" for make, count in top_makes)
            info_table.add_row("Top Makes", makes_str)

        # Top states
        if summary.states:
            top_states = sorted(summary.states.items(), key=lambda x: -x[1])[:5]
            states_str = ", ".join(f"{state}: {count:,}" for state, count in top_states)
            info_table.add_row("Top States", states_str)

        panel = Panel(
            Group(info_table),
            title=title,
            box=box.ROUNDED,
        )
        return panel
