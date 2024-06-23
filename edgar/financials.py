import re
from functools import lru_cache
from typing import Optional, Union, List, Any, Tuple

import pandas as pd
from pydantic import BaseModel
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table, Column
from rich.text import Text

from edgar._rich import repr_rich
from edgar._xbrl import FilingXbrl

__all__ = [
    'Financials',
    'BalanceSheet',
    'CashFlowStatement',
    'IncomeStatement',
    'format_currency'
]


def format_currency(value: Union[str, float], format_str: str = '{:>15,.0f}') -> str:
    if isinstance(value, str):
        if value.isdigit() or re.match(r"-?\d+\.?\d*", value):
            value = float(value)
        else:
            return value

    # format the value using the format
    return format_str.format(value)


class FactRow(BaseModel):
    name: Union[str, List[str]]
    label: str
    format: str = "{:>16,.0f}"
    total: bool = False

    def get_values(self, period_facts: pd.DataFrame, apply_format: bool = True) -> Optional[List[Any]]:
        """
        Get the values from facts for the periods
        """
        fact_names = [self.name] if isinstance(self.name, str) else self.name
        for name in fact_names:
            if name in period_facts.index:
                res = period_facts.loc[name]
                values = None
                if isinstance(res, pd.Series):
                    values = res.tolist()
                elif isinstance(res, pd.DataFrame):
                    values = res.iloc[0].tolist()
                if apply_format:
                    return [format_currency(value, format_str=self.format) if not pd.isna(value) else ""
                            for value in values]
                else:
                    return [value if not pd.isna(value) else "" for value in values]


class HeaderRow(BaseModel):
    label: str


class FactTable:
    """
    FactTable is a base class for Financial Tables like BalanceSheet, CashFlowStatement, IncomeStatement
    """

    def __init__(self, filing_xbrl: FilingXbrl, title: str, mapping: List[Union[FactRow, List[FactRow], HeaderRow]]):
        self.title = title
        self.mapping = mapping
        fact_names = self.get_mapped_facts()
        self.period_facts = filing_xbrl.get_fiscal_period_facts(fact_names)

    def get_mapped_facts_and_labels(self) -> List[Tuple[str, str]]:
        """Get the list of all fact names and labels in the mapping even if they are alternates"""
        facts = []
        for row in self.mapping:
            if isinstance(row, FactRow):
                facts.append((row.name, row.label.replace("\t", "").strip()))
            elif isinstance(row, List):
                for fact_row in row:
                    facts.append((fact_row.name, fact_row.label.replace("\t", "").strip()))
        return facts

    def get_mapped_facts(self) -> List[str]:
        """Get the list of all fact names in the mapping even if they are alternates"""
        return [fact for fact, _ in self.get_mapped_facts_and_labels()]

    @property
    def periods(self):
        return self.period_facts.columns.tolist()

    def get_fact_value(self, fact: str) -> Optional[Any]:
        """Get the latest value for a fact in the table"""
        if fact not in self.period_facts.index:
            return None
        # Using .iloc[0] to safely access the first element by position
        value = self.period_facts.loc[fact].iloc[0]
        if value:
            return value

    @lru_cache(maxsize=1)
    def to_dataframe(self) -> pd.DataFrame:
        """Create a dataframe containing the facts in the table"""
        fact_table_df: pd.DataFrame = pd.DataFrame(data=self.get_mapped_facts_and_labels(), columns=['Fact', 'Label'])
        # merge with self.period_facts
        return (fact_table_df.merge(self.period_facts, how='left', left_on='Fact', right_index=True)
                .set_index('Fact').fillna(pd.NA).dropna(axis=0, how='all')
                )

    @staticmethod
    def find_label_and_values_for_row(fact_row: Union[FactRow, List[FactRow]],
                                      period_facts: pd.DataFrame) -> Tuple[str, bool, List[str]]:
        """
        There can be multiple rows mapped to the final table. Select one row for the output.
        If the row is empty return the label, and empty values
        return the label and the values for the row
        """
        if isinstance(fact_row, FactRow):
            values = fact_row.get_values(period_facts)
            return fact_row.label, fact_row.total, values
        else:
            for row in fact_row:
                values = row.get_values(period_facts) if row.name in period_facts.index else None
                if values:
                    return row.label, row.total, values
            return fact_row[0].label, fact_row[0].total, ["" * len(period_facts.columns)]

    @staticmethod
    def format_label(raw_label: str, is_total: bool = False, is_header: bool = False):
        formatted_label = raw_label.replace("\t", "  ")
        if is_header:
            formatted_label = f"{formatted_label.upper()}:"
            return Text(formatted_label, style="bold turquoise4")
        return Text(formatted_label, style="bold deep_sky_blue3") if is_total else Text(formatted_label)

    def __rich__(self):
        periods = self.period_facts.columns.tolist()
        columns = [""] + [Column(period, justify='right') for period in periods]

        table = Table(*columns, box=box.SIMPLE_HEAVY, title=self.title, title_style="bold turquoise4")
        for index, header_or_fact in enumerate(self.mapping):
            # Get the row label
            if isinstance(header_or_fact, HeaderRow):
                label = FactTable.format_label(header_or_fact.label, is_header=True)
                header_values = [label] + [""] * (len(periods))
                table.add_row(*header_values)
            else:
                # Get the label and values for the row
                label, total, fact_values = FactTable.find_label_and_values_for_row(header_or_fact, self.period_facts)
                if not fact_values:
                    # Skip empty rows
                    continue

                label = FactTable.format_label(label, total)
                row_values = [label] + fact_values
                table.add_row(*row_values)
                if total:
                    table.add_section()

        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


class BalanceSheet(FactTable):
    title = "Balance Sheet"

    mapping = [
        HeaderRow(label='Assets'),
        HeaderRow(label='Current Assets'),
        FactRow(name="CashAndCashEquivalentsAtCarryingValue", label="\tCash and Cash Equivalents"),
        FactRow(name="MarketableSecuritiesCurrent", label="\tMarketable Securities"),
        FactRow(name="AccountsReceivableNetCurrent", label="\tAccounts Receivable, net"),
        FactRow(name="NontradeReceivablesCurrent", label="\tVendor non-trade Receivables"),
        FactRow(name="InventoryNet", label="\tInventories"),
        FactRow(name="OtherAssetsCurrent", label="\tOther Current Assets"),
        FactRow(name="AssetsCurrent", label="\tTotal Current Assets", total=True),

        HeaderRow(label='Noncurrent Assets'),
        FactRow(name="PropertyPlantAndEquipmentNet", label="\tProperty and Equipment, net"),
        FactRow(name="IntangibleAssetsNet", label="\tIntangible Assets, net"),
        FactRow(name="Goodwill", label="\tGoodwill"),
        FactRow(name="MarketableSecuritiesNoncurrent", label="\tMarketable Securities"),
        FactRow(name="OtherAssetsNoncurrent", label="\tOther Long-Term Assets"),
        FactRow(name="AssetsNoncurrent", label="\tTotal Noncurrent Assets", total=True),
        FactRow(name="Assets", label="Total Assets", total=True),

        HeaderRow(label='Liabilities and Stockholders\' Equity'),
        HeaderRow(label='Current Liabilities'),
        FactRow(name="AccountsPayableCurrent", label="\tAccounts Payable"),
        FactRow(name="EmployeeRelatedAccruedExpenses", label="\tEmployee Related Accrued Expenses"),
        FactRow(name="RelatedPartyPayable", label="\tRelated Party Payable"),
        FactRow(name="OtherLiabilitiesCurrent", label="\tOther Current Liabilities"),
        [FactRow(name="DeferredRevenueCurrent", label="\tDeferred Revenue"),
         FactRow(name="ContractWithCustomerLiabilityCurrent", label="\tDeferred Revenue"),
         ],
        FactRow(name="CommercialPaper", label="\tCommercial Paper"),
        FactRow(name="LongTermDebtCurrent", label="\tTerm Debt"),
        FactRow(name="AccruedLiabilitiesCurrent", label="\tAccrued Liabilities"),

        FactRow(name="LiabilitiesCurrent", label="\tTotal Current Liabilities", total=True),

        HeaderRow(label='Noncurrent Liabilities'),
        FactRow(name="AccruedEmployeeBenefitsNoncurrent", label="\tLong-term Employee Benefits"),
        FactRow(name="DeferredTaxLiabilities", label="\tDeferred Tax Liabilities"),
        FactRow(name="LongTermDebtNoncurrent", label="\tNon-current Long Term Debt"),
        FactRow(name="OtherLiabilitiesNoncurrent", label="\tOther Long-Term Liabilities"),
        FactRow(name="LiabilitiesNoncurrent", label="\tTotal Noncurrent Liabilities", total=True),
        FactRow(name="Liabilities", label="Total Liabilities", total=True),

        HeaderRow(label='Stockholders\' Equity'),
        FactRow(name="CommonStockSharesIssued", label="\tCommon Stock, shares issued"),
        [
            FactRow(name="CommonStocksIncludingAdditionalPaidInCapital", label="\tCommon Stock and paid-in Capital"),
            FactRow(name="CommonStockValue", label="\tCommon Stock"),
        ],
        FactRow(name="AdditionalPaidInCapital", label="\tAdditional Paid-in Capital"),
        FactRow(name="RetainedEarningsAccumulatedDeficit", label="\tRetained Earnings"),
        FactRow(name="AccumulatedOtherComprehensiveIncomeLossNetOfTax",
                label="\tAccumulated Other Comprehensive Income"),
        FactRow(name="StockholdersEquity", label="\tTotal Stockholders' Equity", total=True),
        FactRow(name="LiabilitiesAndStockholdersEquity", label="Total Liabilities and Stockholders Equity",
                total=True),
    ]

    def __init__(self, filing_xbrl: FilingXbrl):
        super().__init__(filing_xbrl, title=self.title, mapping=self.mapping)


class CashFlowStatement(FactTable):
    title = "Cashflow Statement"
    mapping = [
        HeaderRow(label='Operating Activities'),
        FactRow(name="NetIncomeLoss", label="\tNet Income"),
        FactRow(name="DepreciationDepletionAndAmortization", label="\tDepreciation and Amortization"),
        FactRow(name="ShareBasedCompensation", label="\tStock-based Compensation"),
        FactRow(name="ForeignCurrencyTransactionGainLossBeforeTax", label="\tForeign Currency Transaction Gain/Loss"),
        FactRow(name="OtherNoncashIncomeExpense", label="\tOther Noncash Income/Expense"),
        FactRow(name="IncreaseDecreaseInOtherCurrentAssets", label="\tChanges in Other Current Assets"),
        FactRow(name="IncreaseDecreaseInAccountsPayable", label="\tChanges in Accounts Payable"),
        FactRow(name="IncreaseDecreaseInInventories", label="\tChanges in Inventories"),
        FactRow(name="IncreaseDecreaseInContractWithCustomerLiability", label="\tChanges in Deferred Revenue"),
        FactRow(name="NetCashProvidedByUsedInOperatingActivities", label="\tNet Cash From Operating Activities",
                total=True),

        HeaderRow(label='Investing Activities'),
        FactRow(name="PaymentsToAcquireAvailableForSaleSecuritiesDebt", label="\tPurchases of Marketable Securities"),
        FactRow(name="ProceedsFromMaturitiesPrepaymentsAndCallsOfAvailableForSaleSecurities",
                label="\tProceeds from Maturities of Marketable Securities"),
        FactRow(name="ProceedsFromSaleOfAvailableForSaleSecuritiesDebt",
                label="\tProceeds from Sale of Marketable Securities"),
        FactRow(name="PaymentsToAcquirePropertyPlantAndEquipment",
                label="\tPurchases of Property, Plant and Equipment"),
        FactRow(name="PaymentsToAcquireInvestments", label="\tPayments to Acquire Investments"),

        FactRow(name="PaymentsToAcquireBusinessesNetOfCashAcquired", label="\tPayments to Acquire Businesses"),
        FactRow(name="IncreaseDecreaseInContractWithCustomerLiability", label="\tDeferred Revenue"),
        FactRow(name="PaymentsForProceedsFromOtherInvestingActivities", label="\tOther Investing Activities"),
        FactRow(name="NetCashProvidedByUsedInInvestingActivities", label="\tNet Cash From Investing Activities",
                total=True),

        HeaderRow(label='Financing Activities'),
        FactRow(name="PaymentsRelatedToTaxWithholdingForShareBasedCompensation",
                label="\tPayments of Tax for Share-based Compensation"),
        FactRow(name="PaymentsOfDividends", label="\tDividends Paid"),
        FactRow(name="PaymentsForRepurchaseOfCommonStock", label="\tRepurchases of Common Stock"),
        FactRow(name="ProceedsFromIssuanceOfCommonStock", label="\tProceeds from Issuance of Common Stock"),
        FactRow(name="RepaymentsOfLongTermDebt", label="\tRepayments of Long-term Debt"),
        FactRow(name="NetCashProvidedByUsedInFinancingActivities", label="\tNet Cash From Financing Activities",
                total=True),

        FactRow(
            name="CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
            label="Changes in Cash and Cash equivalents"),
        FactRow(name="CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
                label="Cash, cash equivalents and restricted cash", total=True),
    ]

    def __init__(self, filing_xbrl: FilingXbrl):
        super().__init__(filing_xbrl, title=self.title, mapping=self.mapping)


class IncomeStatement(FactTable):
    title = "Consolidated Statement of Operations"
    mapping = [
        HeaderRow(label='Sales'),
        [
            FactRow(name="Revenues", label="Revenue", total=True),
            FactRow(name="RevenueFromContractWithCustomerExcludingAssessedTax", label="Total Net Sales", total=True),
        ],
        HeaderRow(label='Cost of Sales'),
        [
            FactRow(name="CostOfRevenue", label="\tCost of Revenue"),
            FactRow(name="CostOfGoodsAndServicesSold", label="Cost Goods and Services Sold", total=True)
        ],
        FactRow(name="GrossProfit", label="Gross Profit", total=True),
        HeaderRow(label="Operating Expenses"),
        FactRow(name='ResearchAndDevelopmentExpense', label='\tResearch & Development Expenses'),
        [
            FactRow(name='MarketingExpense', label='\tMarketing Expense'),
            FactRow(name='SellingAndMarketingExpense', label='\tSales and Marketing Expenses'),
        ],
        [
            FactRow(name='GeneralAndAdministrativeExpense', label='\tGeneral & Administrative Expenses'),
            FactRow(name='SellingGeneralAndAdministrativeExpense',
                    label='\tSelling, General & Admin Expenses'),
        ],
        FactRow(name='OperatingExpenses', label='Total Operating Expenses', total=True),
        FactRow(name='OperatingIncomeLoss', label='Operating Income', total=True),

        HeaderRow(label='Other Income/Expense'),
        FactRow(name='InterestExpense', label='\tInterest Expense'),
        FactRow(name='NonoperatingIncomeExpense', label='\tNonoperating Income'),
        FactRow(name='InterestIncomeOperating', label='\tInterest Income'),
        FactRow(name='OtherFinancialIncomeExpenseNet', label='\tOther Financial Income (expense)'),
        FactRow(name='IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
                label='Income Before Taxes', total=True),
        FactRow(name='IncomeTaxExpenseBenefit', label='Income Tax Expense'),

        FactRow(name='NetIncomeLoss', label='Net Income', total=True),
        HeaderRow(label='Earnings Per Share'),
        FactRow(name='EarningsPerShareBasic', label='\tBasic', format="{:,.2f}"),
        FactRow(name='EarningsPerShareDiluted', label='\tDiluted', format="{:,.2f}"),

        HeaderRow(label='Weighted Average Shares Outstanding'),
        FactRow(name='WeightedAverageNumberOfSharesOutstandingBasic', label='\tBasic'),
        FactRow(name='WeightedAverageNumberOfDilutedSharesOutstanding', label='\tDiluted'),
    ]

    def __init__(self, filing_xbrl: FilingXbrl):
        super().__init__(filing_xbrl, title=self.title, mapping=self.mapping)


class Financials:

    # Financials is a base class for IncomeStatement, BalanceSheet, CashFlowStatement
    def __init__(self,
                 balance_sheet: BalanceSheet,
                 cash_flow_statement: CashFlowStatement,
                 income_statement: IncomeStatement):
        self.balance_sheet: BalanceSheet = balance_sheet
        self.cash_flow_statement: CashFlowStatement = cash_flow_statement
        self.income_statement: IncomeStatement = income_statement

    def __rich__(self):
        return Panel(
            Group(self.balance_sheet,
                  self.cash_flow_statement,
                  self.income_statement),
            box=box.MINIMAL
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return "Company Financials()"

    @classmethod
    def from_xbrl(cls,
                  xbrl: FilingXbrl):
        balance_sheet = BalanceSheet(xbrl)
        income_statement = IncomeStatement(xbrl)
        cash_flow_statement = CashFlowStatement(xbrl)
        return cls(balance_sheet, cash_flow_statement, income_statement)
