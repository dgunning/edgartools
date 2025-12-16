"""
CMBS (Commercial Mortgage-Backed Securities) asset data parsing.

Parses EX-102 XML asset data files from 10-D filings for CMBS securitizations.
The XML follows the SEC schema: http://www.sec.gov/edgar/document/absee/cmbs/assetdata
"""

from dataclasses import dataclass
from datetime import date
from functools import cached_property
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree as ET

from rich import box
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from edgar.richtools import repr_rich

__all__ = ['CMBSAssetData', 'CMBSSummary']

# XML namespace for CMBS asset data
CMBS_NS = {'cmbs': 'http://www.sec.gov/edgar/document/absee/cmbs/assetdata'}


def _parse_xml_date(date_str: Optional[str]) -> Optional[date]:
    """Parse date string in MM-DD-YYYY format."""
    if not date_str:
        return None
    try:
        parts = date_str.split('-')
        if len(parts) == 3:
            month, day, year = int(parts[0]), int(parts[1]), int(parts[2])
            return date(year, month, day)
    except (ValueError, IndexError):
        pass
    return None


def _parse_decimal(value: Optional[str]) -> Optional[float]:
    """Parse decimal string to float."""
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _parse_int(value: Optional[str]) -> Optional[int]:
    """Parse integer string to int."""
    if not value:
        return None
    try:
        return int(float(value))  # Handle "0.00" style
    except ValueError:
        return None


def _parse_bool(value: Optional[str]) -> Optional[bool]:
    """Parse boolean string."""
    if not value:
        return None
    return value.lower() == 'true'


def _get_element_text(element: ET.Element, tag: str, ns: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Get text content from a child element."""
    if ns:
        child = element.find(f"cmbs:{tag}", ns)
    else:
        # Try without namespace first (for elements using default namespace)
        child = element.find(tag)
        if child is None:
            # Try with namespace
            for key, uri in (ns or {}).items():
                child = element.find(f"{{{uri}}}{tag}")
                if child is not None:
                    break
    return child.text if child is not None else None


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

    # Fields that should be parsed as dates
    DATE_FIELDS = {
        'period_start', 'period_end', 'origination_date', 'maturity_date',
        'first_payment_date', 'lockout_end_date', 'yield_maintenance_end_date',
        'prepayment_premium_end_date', 'paid_through_date', 'valuation_date',
        'tenant_1_lease_exp', 'tenant_2_lease_exp', 'tenant_3_lease_exp',
        'financials_date_securitization', 'financials_start_date', 'financials_end_date',
    }

    # Fields that should be parsed as floats
    DECIMAL_FIELDS = {
        'original_amount', 'original_rate', 'securitization_rate', 'scheduled_balance',
        'period_begin_balance', 'scheduled_pi_due', 'current_rate', 'servicer_fee_rate',
        'scheduled_interest', 'scheduled_principal', 'unscheduled_principal',
        'actual_balance', 'scheduled_end_balance', 'pi_advances_outstanding',
        'ti_advances_outstanding', 'other_advances_outstanding',
        'valuation', 'occupancy_securitization', 'occupancy_current',
        'revenue_securitization', 'revenue_current', 'opex_securitization', 'opex_current',
        'noi_securitization', 'noi_current', 'ncf_securitization', 'ncf_current',
        'debt_service_current', 'dscr_noi_securitization', 'dscr_noi_current',
        'dscr_ncf_securitization', 'dscr_ncf_current',
    }

    # Fields that should be parsed as integers
    INT_FIELDS = {
        'original_term_months', 'io_term_months', 'num_properties_securitization',
        'num_properties', 'grace_days', 'units', 'units_securitization',
        'sqft', 'sqft_securitization', 'year_built', 'year_renovated',
        'tenant_1_sqft', 'tenant_2_sqft', 'tenant_3_sqft',
    }

    # Fields that should be parsed as booleans
    BOOL_FIELDS = {
        'is_interest_only', 'is_balloon', 'has_prepayment_premium',
        'has_negative_amortization', 'is_modified', 'subject_to_demand',
    }

    def __init__(self, xml_content: str):
        """
        Initialize CMBS asset data parser.

        Args:
            xml_content: Raw XML content from EX-102 exhibit
        """
        self._xml_content = xml_content
        self._loans_data: Optional[List[Dict[str, Any]]] = None
        self._properties_data: Optional[List[Dict[str, Any]]] = None

    def _parse_value(self, value: Optional[str], field_name: str) -> Any:
        """Parse a value based on the field type."""
        if value is None:
            return None
        if field_name in self.DATE_FIELDS:
            return _parse_xml_date(value)
        if field_name in self.DECIMAL_FIELDS:
            return _parse_decimal(value)
        if field_name in self.INT_FIELDS:
            return _parse_int(value)
        if field_name in self.BOOL_FIELDS:
            return _parse_bool(value)
        return value

    def _parse_xml(self):
        """Parse the XML content into loans and properties data."""
        if self._loans_data is not None:
            return  # Already parsed

        self._loans_data = []
        self._properties_data = []

        try:
            root = ET.fromstring(self._xml_content)
        except ET.ParseError:
            return

        # Find all asset elements
        # Handle both namespaced and non-namespaced XML
        assets = root.findall('.//assets') or root.findall('.//{http://www.sec.gov/edgar/document/absee/cmbs/assetdata}assets')

        for asset in assets:
            # Extract loan-level data
            loan_data = {}
            for xml_tag, output_name in self.LOAN_FIELDS.items():
                # Try without namespace
                elem = asset.find(xml_tag)
                if elem is None:
                    # Try with namespace
                    elem = asset.find(f'{{http://www.sec.gov/edgar/document/absee/cmbs/assetdata}}{xml_tag}')
                value = elem.text if elem is not None else None
                loan_data[output_name] = self._parse_value(value, output_name)

            self._loans_data.append(loan_data)

            # Extract property-level data
            properties = asset.findall('property') or asset.findall('{http://www.sec.gov/edgar/document/absee/cmbs/assetdata}property')
            for prop in properties:
                prop_data = {'loan_id': loan_data.get('loan_id')}
                for xml_tag, output_name in self.PROPERTY_FIELDS.items():
                    elem = prop.find(xml_tag)
                    if elem is None:
                        elem = prop.find(f'{{http://www.sec.gov/edgar/document/absee/cmbs/assetdata}}{xml_tag}')
                    value = elem.text if elem is not None else None
                    prop_data[output_name] = self._parse_value(value, output_name)
                self._properties_data.append(prop_data)

    @cached_property
    def loans(self):
        """
        Loan-level data as a pandas DataFrame.

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
        import pandas as pd

        self._parse_xml()
        if not self._loans_data:
            return pd.DataFrame()

        df = pd.DataFrame(self._loans_data)
        return df

    @cached_property
    def properties(self):
        """
        Property-level data as a pandas DataFrame.

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
        import pandas as pd

        self._parse_xml()
        if not self._properties_data:
            return pd.DataFrame()

        df = pd.DataFrame(self._properties_data)
        return df

    def summary(self) -> CMBSSummary:
        """
        Calculate summary statistics for the CMBS pool.

        Returns:
            CMBSSummary with aggregate metrics
        """
        self._parse_xml()

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
