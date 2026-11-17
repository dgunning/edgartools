"""
Deprecated: auto lease ABS-EE parser, kept for compatibility.

Use :class:`edgar.abs.AssetData` (or ``filing.obj()`` on an ABS-EE filing),
which reads every ABS-EE schema, streams large files, and types its columns
from SEC's XSDs. ``AutoLeaseAssetData`` is now a thin view over it that keeps
the old column names; it is removed in 7.0.

Changes from 6.2 (see docs/upgrade/6.1.md): six of the old tag names did not
exist in the auto lease schema and are now read from the schema's real tags,
so ``scheduled_payment``, ``actual_payment``, ``paid_through_date``,
``remaining_term_months``, ``securitization_balance`` and ``ending_balance``
are filled; ``beginning_balance`` is gone because the schema has no such field;
dates are datetime64 rather than strings; and vehicle type codes are decoded
with SEC's meanings (2 is Truck, 3 is SUV).
"""

import warnings
from dataclasses import dataclass, field
from typing import Dict, Optional

import pandas as pd
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.abs.absee_schemas import CODE_MEANINGS, SCHEMAS
from edgar.exceptions import DataObjectError, ParsingError
from edgar.richtools import repr_rich

__all__ = ['AutoLeaseAssetData', 'AutoLeaseSummary']


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


def _legacy_frame(curated: Optional[pd.DataFrame], spec_table: Dict, field_map: Dict[str, str]) -> pd.DataFrame:
    """Select and rename curated columns to a legacy class's names (XML tag -> legacy name)."""
    if curated is None:
        return pd.DataFrame(columns=list(field_map.values()))
    data = {}
    for tag, legacy in field_map.items():
        column = spec_table[tag][0] if tag in spec_table else legacy
        data[legacy] = curated[column] if column in curated.columns else pd.Series([None] * len(curated), dtype=object)
    return pd.DataFrame(data)


class AutoLeaseAssetData:
    """
    Deprecated view of auto lease ABS-EE asset data; use :class:`edgar.abs.AssetData`.

    Example:
        >>> from edgar import find
        >>> data = find('0000929638-25-004537').obj()   # AssetData
        >>> data.assets[['vehicle_manufacturer_name', 'lessee_credit_score']]
    """

    # XML tag -> legacy column name
    ASSET_FIELDS = {
        'assetNumber': 'asset_id',
        'assetTypeNumber': 'asset_type',
        'reportingPeriodBeginDate': 'period_start',
        'reportingPeriodEndDate': 'period_end',
        'originatorName': 'originator',
        'originationDate': 'origination_date',
        'acquisitionCost': 'acquisition_cost',
        'originalLeaseTermNumber': 'original_term_months',
        'scheduledTerminationDate': 'termination_date',
        'originalFirstPaymentDate': 'first_payment_date',
        'gracePeriod': 'grace_period_days',
        'paymentTypeCode': 'payment_type_code',
        'vehicleManufacturerName': 'vehicle_manufacturer',
        'vehicleModelName': 'vehicle_model',
        'vehicleNewUsedCode': 'vehicle_new_used',
        'vehicleModelYear': 'vehicle_year',
        'vehicleTypeCode': 'vehicle_type_code',
        'vehicleValueAmount': 'vehicle_value',
        'baseResidualValue': 'base_residual_value',
        'contractResidualValue': 'contract_residual_value',
        'lesseeCreditScoreType': 'credit_score_type',
        'lesseeCreditScore': 'credit_score',
        'lesseeIncomeVerificationLevelCode': 'income_verification_code',
        'lesseeEmploymentVerificationCode': 'employment_verification_code',
        'paymentToIncomePercentage': 'payment_to_income_ratio',
        'lesseeGeographicLocation': 'lessee_state',
        'coLesseePresentIndicator': 'has_co_lessee',
        'reportingPeriodScheduledPaymentAmount': 'scheduled_payment',
        'totalActualAmountPaid': 'actual_payment',
        'paidThroughDate': 'paid_through_date',
        'zeroBalanceCode': 'zero_balance_code',
        'zeroBalanceEffectiveDate': 'zero_balance_date',
        'currentDelinquencyStatus': 'delinquency_status',
        'remainingTermNumber': 'remaining_term_months',
        'reportingPeriodSecuritizationValueAmount': 'securitization_balance',
        'reportingPeriodEndingActualBalanceAmount': 'ending_balance',
    }

    # SEC's meanings for vehicleTypeCode in the auto lease schema
    VEHICLE_TYPE_CODES = CODE_MEANINGS['autolease']['vehicle_type_code']

    def __init__(self, xml_content: str):
        """
        Initialize from the XML of an auto lease EX-102 exhibit.

        XML that is not auto lease asset data gives an empty object, as before;
        :class:`edgar.abs.AssetData` raises instead.
        """
        warnings.warn(
            "AutoLeaseAssetData is deprecated and will be removed in 7.0. Use edgar.abs.AssetData, "
            "or filing.obj() on an ABS-EE filing; its columns are the XSD names in snake_case.",
            DeprecationWarning, stacklevel=2)
        from edgar.abs.asset_data import AssetData

        self._xml_content = xml_content
        curated = None
        try:
            data = AssetData.from_xml(xml_content)
            if data.schema == 'autolease':
                curated = data.assets
        except (ParsingError, DataObjectError):
            pass
        self._assets_df = _legacy_frame(curated, SCHEMAS['autolease']['tables']['assets'], self.ASSET_FIELDS)

    @classmethod
    def from_filing(cls, filing) -> Optional['AutoLeaseAssetData']:
        """
        Create parser from an ABS-EE filing.

        Returns:
            AutoLeaseAssetData or None if no EX-102 exhibit found
        """
        for attachment in filing.attachments:
            if attachment.document_type and 'EX-102' in attachment.document_type.upper():
                xml_content = attachment.text()
                if xml_content:
                    return cls(xml_content)
        return None

    @property
    def assets(self) -> pd.DataFrame:
        """Asset-level data as a DataFrame, with the legacy column names."""
        return self._assets_df

    def __len__(self) -> int:
        return len(self.assets)

    def summary(self) -> AutoLeaseSummary:
        """Summary statistics for the asset data."""
        df = self.assets
        if df.empty:
            return AutoLeaseSummary()

        summary = AutoLeaseSummary(num_assets=len(df))
        summary.total_acquisition_cost = float(df['acquisition_cost'].sum())
        summary.total_residual_value = float(df['contract_residual_value'].sum())

        scores = df['credit_score'].dropna()
        if len(scores) > 0:
            summary.avg_credit_score = float(scores.mean())
        terms = df['original_term_months'].dropna()
        if len(terms) > 0:
            summary.avg_lease_term = float(terms.mean())

        summary.vehicle_makes = {str(k): int(v) for k, v in df['vehicle_manufacturer'].value_counts().items()}
        summary.vehicle_types = {
            self.VEHICLE_TYPE_CODES.get(str(k), str(k)): int(v)
            for k, v in df['vehicle_type_code'].value_counts().items()
        }
        summary.model_years = {int(k): int(v) for k, v in df['vehicle_year'].value_counts().items()}
        summary.states = {str(k): int(v) for k, v in df['lessee_state'].value_counts().items()}
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

        if summary.vehicle_makes:
            info_table.add_row("", "")
            top_makes = sorted(summary.vehicle_makes.items(), key=lambda x: -x[1])[:3]
            info_table.add_row("Top Makes", ", ".join(f"{make.strip()}: {count:,}" for make, count in top_makes))

        if summary.states:
            top_states = sorted(summary.states.items(), key=lambda x: -x[1])[:5]
            info_table.add_row("Top States", ", ".join(f"{state}: {count:,}" for state, count in top_states))

        return Panel(Group(info_table), title=title, box=box.ROUNDED)
