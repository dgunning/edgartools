"""
CMBS (Commercial Mortgage-Backed Securities) asset data parsing.

Parses EX-102 XML asset data files from 10-D filings for CMBS securitizations.
The XML follows the SEC schema: http://www.sec.gov/edgar/document/absee/cmbs/assetdata

CMBSAssetData reads through edgar.abs.AssetData (the streaming ABS-EE reader)
and keeps its own column names for TenD; AssetData has every field typed from
SEC's XSD under its snake_case XSD name.
"""

from dataclasses import dataclass
from functools import cached_property
from typing import Dict, Optional

import pandas as pd
from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.abs.abs_ee import _legacy_frame
from edgar.abs.absee_schemas import SCHEMAS
from edgar.exceptions import DataObjectError, ParsingError
from edgar.richtools import repr_rich

__all__ = ['CMBSAssetData', 'CMBSSummary']

_SPEC = SCHEMAS['cmbs']['tables']

@dataclass
class CMBSSummary:
    """Summary statistics for CMBS asset data."""
    num_loans: int
    num_properties: int
    total_loan_balance: float
    total_original_loan_amount: float
    avg_interest_rate: Optional[float]
    avg_dscr: Optional[float]
    avg_occupancy: Optional[float]
    property_types: Dict[str, int]  # Property type code -> count
    states: Dict[str, int]  # State -> count
    delinquent_loans: int
    modified_loans: int

    def __rich__(self):
        """Rich console representation."""
        table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
        table.add_column("Label", style="grey70")
        table.add_column("Value")

        table.add_row("Loans", f"{self.num_loans:,}")
        table.add_row("Properties", f"{self.num_properties:,}")
        table.add_row("Total Balance", f"${self.total_loan_balance:,.0f}")
        table.add_row("Original Amount", f"${self.total_original_loan_amount:,.0f}")

        if self.avg_interest_rate is not None:
            table.add_row("Avg Interest Rate", f"{self.avg_interest_rate:.2%}")
        if self.avg_dscr is not None:
            table.add_row("Avg DSCR", f"{self.avg_dscr:.2f}")
        if self.avg_occupancy is not None:
            table.add_row("Avg Occupancy", f"{self.avg_occupancy:.1%}")

        # Top property types
        if self.property_types:
            top_types = sorted(self.property_types.items(), key=lambda x: -x[1])[:3]
            types_str = ", ".join(f"{t}: {c}" for t, c in top_types)
            table.add_row("Property Types", types_str)

        # Top states
        if self.states:
            top_states = sorted(self.states.items(), key=lambda x: -x[1])[:3]
            states_str = ", ".join(f"{s}: {c}" for s, c in top_states)
            table.add_row("Top States", states_str)

        if self.delinquent_loans > 0:
            table.add_row("Delinquent", Text(f"{self.delinquent_loans}", style="red"))
        if self.modified_loans > 0:
            table.add_row("Modified", f"{self.modified_loans}")

        return Panel(table, title="CMBS Summary", box=box.ROUNDED)


class CMBSAssetData:
    """
    Parser for CMBS EX-102 XML asset data.

    Provides access to loan-level and property-level data from CMBS 10-D filings.

    Example:
        >>> cmbs = CMBSAssetData(xml_content)
        >>> cmbs.loans  # DataFrame of loan data
        >>> cmbs.properties  # DataFrame of property data
        >>> cmbs.summary()  # Summary statistics
    """

    # Loan-level fields to extract (tag_name -> output_column_name)
    LOAN_FIELDS = {
        'assetNumber': 'loan_id',
        'assetTypeNumber': 'loan_id_type',
        'reportingPeriodBeginningDate': 'period_start',
        'reportingPeriodEndDate': 'period_end',
        'originatorName': 'originator',
        'originationDate': 'origination_date',
        'originalLoanAmount': 'original_amount',
        'originalTermLoanNumber': 'original_term_months',
        'maturityDate': 'maturity_date',
        'originalInterestRatePercentage': 'original_rate',
        'interestRateSecuritizationPercentage': 'securitization_rate',
        'interestAccrualMethodCode': 'accrual_method',
        'originalInterestRateTypeCode': 'rate_type',
        'originalInterestOnlyTermNumber': 'io_term_months',
        'firstLoanPaymentDueDate': 'first_payment_date',
        'lienPositionSecuritizationCode': 'lien_position',
        'loanStructureCode': 'loan_structure',
        'paymentTypeCode': 'payment_type',
        'scheduledPrincipalBalanceSecuritizationAmount': 'scheduled_balance',
        'paymentFrequencyCode': 'payment_frequency',
        'NumberPropertiesSecuritization': 'num_properties_securitization',
        'NumberProperties': 'num_properties',
        'graceDaysAllowedNumber': 'grace_days',
        'interestOnlyIndicator': 'is_interest_only',
        'balloonIndicator': 'is_balloon',
        'prepaymentPremiumIndicator': 'has_prepayment_premium',
        'negativeAmortizationIndicator': 'has_negative_amortization',
        'modifiedIndicator': 'is_modified',
        'prepaymentLockOutEndDate': 'lockout_end_date',
        'yieldMaintenanceEndDate': 'yield_maintenance_end_date',
        'prepaymentPremiumsEndDate': 'prepayment_premium_end_date',
        'reportPeriodBeginningScheduleLoanBalanceAmount': 'period_begin_balance',
        'totalScheduledPrincipalInterestDueAmount': 'scheduled_pi_due',
        'reportPeriodInterestRatePercentage': 'current_rate',
        'servicerTrusteeFeeRatePercentage': 'servicer_fee_rate',
        'scheduledInterestAmount': 'scheduled_interest',
        'scheduledPrincipalAmount': 'scheduled_principal',
        'unscheduledPrincipalCollectedAmount': 'unscheduled_principal',
        'reportPeriodEndActualBalanceAmount': 'actual_balance',
        'reportPeriodEndScheduledLoanBalanceAmount': 'scheduled_end_balance',
        'paidThroughDate': 'paid_through_date',
        'servicingAdvanceMethodCode': 'servicing_advance_method',
        'totalPrincipalInterestAdvancedOutstandingAmount': 'pi_advances_outstanding',
        'totalTaxesInsuranceAdvancesOutstandingAmount': 'ti_advances_outstanding',
        'otherExpensesAdvancedOutstandingAmount': 'other_advances_outstanding',
        'paymentStatusLoanCode': 'payment_status',
        'primaryServicerName': 'primary_servicer',
        'assetSubjectDemandIndicator': 'subject_to_demand',
    }

    # Property-level fields to extract
    PROPERTY_FIELDS = {
        'propertyName': 'name',
        'propertyAddress': 'address',
        'propertyCity': 'city',
        'propertyState': 'state',
        'propertyZip': 'zip',
        'propertyCounty': 'county',
        'propertyTypeCode': 'property_type',
        'unitsBedsRoomsNumber': 'units',
        'unitsBedsRoomsSecuritizationNumber': 'units_securitization',
        'netRentableSquareFeetNumber': 'sqft',
        'netRentableSquareFeetSecuritizationNumber': 'sqft_securitization',
        'yearBuiltNumber': 'year_built',
        'yearLastRenovated': 'year_renovated',
        'valuationSecuritizationAmount': 'valuation',
        'valuationSourceSecuritizationCode': 'valuation_source',
        'valuationSecuritizationDate': 'valuation_date',
        'physicalOccupancySecuritizationPercentage': 'occupancy_securitization',
        'mostRecentPhysicalOccupancyPercentage': 'occupancy_current',
        'propertyStatusCode': 'status',
        'DefeasedStatusCode': 'defeased_status',
        'largestTenant': 'tenant_1_name',
        'squareFeetLargestTenantNumber': 'tenant_1_sqft',
        'leaseExpirationLargestTenantDate': 'tenant_1_lease_exp',
        'secondLargestTenant': 'tenant_2_name',
        'squareFeetSecondLargestTenantNumber': 'tenant_2_sqft',
        'leaseExpirationSecondLargestTenantDate': 'tenant_2_lease_exp',
        'thirdLargestTenant': 'tenant_3_name',
        'squareFeetThirdLargestTenantNumber': 'tenant_3_sqft',
        'leaseExpirationThirdLargestTenantDate': 'tenant_3_lease_exp',
        'financialsSecuritizationDate': 'financials_date_securitization',
        'mostRecentFinancialsStartDate': 'financials_start_date',
        'mostRecentFinancialsEndDate': 'financials_end_date',
        'revenueSecuritizationAmount': 'revenue_securitization',
        'mostRecentRevenueAmount': 'revenue_current',
        'operatingExpensesSecuritizationAmount': 'opex_securitization',
        'operatingExpensesAmount': 'opex_current',
        'netOperatingIncomeSecuritizationAmount': 'noi_securitization',
        'mostRecentNetOperatingIncomeAmount': 'noi_current',
        'netCashFlowFlowSecuritizationAmount': 'ncf_securitization',
        'mostRecentNetCashFlowAmount': 'ncf_current',
        'mostRecentDebtServiceAmount': 'debt_service_current',
        'debtServiceCoverageNetOperatingIncomeSecuritizationPercentage': 'dscr_noi_securitization',
        'mostRecentDebtServiceCoverageNetOperatingIncomePercentage': 'dscr_noi_current',
        'debtServiceCoverageNetCashFlowSecuritizationPercentage': 'dscr_ncf_securitization',
        'mostRecentDebtServiceCoverageNetCashFlowpercentage': 'dscr_ncf_current',
    }

    def __init__(self, xml_content: str):
        """
        Initialize CMBS asset data parser.

        Args:
            xml_content: Raw XML content from EX-102 exhibit
        """
        self._xml_content = xml_content

    @cached_property
    def _asset_data(self):
        """The EX-102 read by edgar.abs.AssetData, or None when it is not CMBS asset data."""
        from edgar.abs.asset_data import AssetData
        try:
            data = AssetData.from_xml(self._xml_content)
        except (ParsingError, DataObjectError):
            return None
        return data if data.schema == 'cmbs' else None

    @cached_property
    def loans(self):
        """
        Loan-level data as a pandas DataFrame.

        Read through :class:`edgar.abs.AssetData` and renamed to this class's
        column names (``LOAN_FIELDS``); ``AssetData(...).assets`` has every CMBS
        field under its XSD name.

        Returns:
            DataFrame with columns:
                - loan_id: Prospectus loan identifier
                - originator: Loan originator name
                - original_amount: Original loan amount
                - actual_balance: Current actual balance
                - maturity_date: Loan maturity date
                - current_rate: Current interest rate
                - payment_status: Payment status code
                - is_modified: Whether loan has been modified
                - primary_servicer: Primary servicer name
                - ... and many more fields
        """
        data = self._asset_data
        if data is None or data.assets.empty:
            return pd.DataFrame()
        return _legacy_frame(data.assets, _SPEC['assets'], self.LOAN_FIELDS)

    @cached_property
    def properties(self):
        """
        Property-level data as a pandas DataFrame, keyed to loans by ``loan_id``.

        Returns:
            DataFrame with columns:
                - loan_id: Associated loan identifier
                - name: Property name
                - address, city, state, zip, county: Location
                - property_type: Property type code (MF, OF, RT, etc.)
                - valuation: Property valuation
                - occupancy_securitization: Occupancy at securitization
                - noi_securitization: Net Operating Income at securitization
                - dscr_noi_securitization: DSCR based on NOI
                - ... and many more fields
        """
        data = self._asset_data
        if data is None or data.properties is None or data.properties.empty:
            return pd.DataFrame()
        frame = _legacy_frame(data.properties, _SPEC['property'], self.PROPERTY_FIELDS)
        frame.insert(0, 'loan_id', data.properties['asset_number'])
        return frame

    def summary(self) -> CMBSSummary:
        """
        Calculate summary statistics for the CMBS pool.

        Returns:
            CMBSSummary with aggregate metrics
        """
        loans_df = self.loans
        props_df = self.properties

        # Calculate loan metrics
        num_loans = len(loans_df)
        num_properties = len(props_df)

        total_balance = loans_df['actual_balance'].sum() if 'actual_balance' in loans_df.columns else 0
        total_original = loans_df['original_amount'].sum() if 'original_amount' in loans_df.columns else 0

        # Average interest rate (weighted by balance would be better, but simple avg for now)
        avg_rate = None
        if 'current_rate' in loans_df.columns:
            rates = loans_df['current_rate'].dropna()
            if len(rates) > 0:
                avg_rate = rates.mean()

        # Average DSCR from properties
        avg_dscr = None
        if 'dscr_noi_securitization' in props_df.columns:
            dscr_values = props_df['dscr_noi_securitization'].dropna()
            if len(dscr_values) > 0:
                avg_dscr = dscr_values.mean()

        # Average occupancy
        avg_occupancy = None
        if 'occupancy_securitization' in props_df.columns:
            occ_values = props_df['occupancy_securitization'].dropna()
            if len(occ_values) > 0:
                avg_occupancy = occ_values.mean()

        # Property types distribution
        property_types = {}
        if 'property_type' in props_df.columns:
            type_counts = props_df['property_type'].dropna().value_counts()
            property_types = type_counts.to_dict()

        # State distribution
        states = {}
        if 'state' in props_df.columns:
            state_counts = props_df['state'].dropna()
            # Filter out 'NA' values
            state_counts = state_counts[state_counts != 'NA'].value_counts()
            states = state_counts.to_dict()

        # Delinquent loans (payment_status != 0)
        delinquent = 0
        if 'payment_status' in loans_df.columns:
            status = loans_df['payment_status'].dropna()
            delinquent = int((status != '0').sum())

        # Modified loans
        modified = 0
        if 'is_modified' in loans_df.columns:
            modified = int(loans_df['is_modified'].sum())

        return CMBSSummary(
            num_loans=num_loans,
            num_properties=num_properties,
            total_loan_balance=total_balance or 0,
            total_original_loan_amount=total_original or 0,
            avg_interest_rate=avg_rate,
            avg_dscr=avg_dscr,
            avg_occupancy=avg_occupancy,
            property_types=property_types,
            states=states,
            delinquent_loans=delinquent,
            modified_loans=modified,
        )

    def __len__(self) -> int:
        """Return number of loans."""
        return len(self.loans)

    def __str__(self):
        return f"CMBSAssetData({len(self)} loans, {len(self.properties)} properties)"

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __rich__(self):
        """Rich console representation."""
        summary = self.summary()

        title = Text.assemble(
            ("CMBS Asset Data", "bold deep_sky_blue1"),
            (" ", ""),
            (f"({len(self)} loans)", "dim"),
        )

        table = Table(show_header=False, box=None, padding=(0, 2, 0, 0))
        table.add_column("Label", style="grey70")
        table.add_column("Value")

        table.add_row("Loans", f"{summary.num_loans:,}")
        table.add_row("Properties", f"{summary.num_properties:,}")
        table.add_row("Total Balance", f"${summary.total_loan_balance:,.0f}")

        if summary.avg_interest_rate is not None:
            table.add_row("Avg Rate", f"{summary.avg_interest_rate:.2%}")
        if summary.avg_dscr is not None:
            table.add_row("Avg DSCR", f"{summary.avg_dscr:.2f}")
        if summary.avg_occupancy is not None:
            table.add_row("Avg Occupancy", f"{summary.avg_occupancy:.1%}")

        if summary.property_types:
            top_types = sorted(summary.property_types.items(), key=lambda x: -x[1])[:5]
            types_str = ", ".join(f"{t}: {c}" for t, c in top_types)
            table.add_row("Property Types", types_str)

        return Panel(table, title=title, box=box.ROUNDED)
