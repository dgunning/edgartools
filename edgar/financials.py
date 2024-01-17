import re
from functools import lru_cache
from typing import Optional
from typing import Union, List

import pandas as pd
from pydantic import BaseModel
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table, Column

from edgar._rich import repr_rich
from edgar._xbrl import XbrlFacts, FilingXbrl

__all__ = [
    'Financials',
    'BalanceSheet',
    'CashFlowStatement',
    'IncomeStatement',
    'format_currency'
]


def format_currency(value: Union[str, float], format_str: str = '{:,.0f}') -> str:
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
    format: str = "{:,.0f}"
    total: bool = False

    def get_value(self, facts: XbrlFacts, end_date: str, apply_format: bool = True):
        fact_names = [self.name] if isinstance(self.name, str) else self.name
        value: Optional[str] = None
        for name in fact_names:
            value = facts.get_fact(fact=name, namespace='us-gaap', end_date=end_date)
            if value:
                break
        if apply_format:
            display_value = format_currency(value, format_str=self.format) if value else ""
        else:
            display_value = value
        return display_value


class HeaderRow(BaseModel):
    label: str


class FactTable:
    mapping = []
    title = ""

    def __init__(self, facts: XbrlFacts, end_date: str = None):
        self.facts: XbrlFacts = facts
        self.end_date: str = end_date or self.facts.period_end_date

    def to_dict(self):
        return {row.label: self.facts.get_fact(fact=row.name, namespace='us-gaap', end_date=self.end_date)
                for row in self.mapping}

    def select_row_with_value(self, rows: List[FactRow]):
        for row in rows:
            value = row.get_value(self.facts, self.end_date)
            if value:
                return row

    def get_fact_value(self, fact: str):
        df = self.to_dataframe()
        res = df[df.fact == fact]
        if not res.empty:
            return res.value.item()

    @lru_cache(maxsize=2)
    def to_dataframe(self):
        rows = []
        for row in self.mapping:
            if isinstance(row, list):
                row = self.select_row_with_value(row)
                if not row:
                    continue
            if isinstance(row, FactRow):
                value = row.get_value(self.facts, self.end_date, apply_format=False)
                rows.append((row.name, row.label, value))
        df = pd.DataFrame(rows, columns=['fact', 'label', 'value'])
        return df

    def __rich__(self):
        table = Table("",
                      Column(self.end_date, justify="right"),
                      box=box.SIMPLE_HEAVY,
                      title=self.title,
                      )
        for index, row in enumerate(self.mapping):
            if isinstance(row, list):
                row = self.select_row_with_value(row)
                if not row:
                    continue
            label = row.label.replace("\t", "  ")
            if isinstance(row, HeaderRow):
                table.add_row(f"{label.upper()}:", "")
            elif isinstance(row, FactRow):
                value = row.get_value(self.facts, self.end_date)
                if value:
                    style = "bold deep_sky_blue1" if row.total else None
                    table.add_row(label, value, style=style)
                    if row.total:
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
        FactRow(name="ShortTermInvestments", label="\tShort-term Investments"),
        FactRow(name="OtherAssetsCurrent", label="\tOther Current Assets"),
        FactRow(name="AssetsCurrent", label="\tCurrent Assets", total=True),
        HeaderRow(label='Noncurrent Assets'),
        FactRow(name="MarketableSecuritiesNoncurrent", label="\tMarketable Securities"),
        FactRow(name="PropertyPlantAndEquipmentNet", label="\tProperty, Plant and Equipment"),
        FactRow(name="OtherAssetsNoncurrent", label="\tOther Noncurrent Assets"),
        FactRow(name="AssetsNoncurrent", label="\tTotal Noncurrent Assets", total=True),
        FactRow(name="Assets", label="Total Assets", total=True),

        HeaderRow(label='Liabilities and Stockholders\' Equity'),
        HeaderRow(label='Current Liabilities'),
        FactRow(name="AccountsPayableCurrent", label="\tAccounts Payable"),
        FactRow(name="OtherLiabilitiesCurrent", label="\tOther Current Liabilities"),
        [FactRow(name="DeferredRevenueCurrent", label="\tDeferred Revenue"),
         FactRow(name="ContractWithCustomerLiabilityCurrent", label="\tDeferred Revenue"),
         ],
        FactRow(name="CommercialPaper", label="\tCommercial Paper"),
        FactRow(name="LongTermDebtCurrent", label="\tTerm Debt"),
        FactRow(name="AccruedLiabilitiesCurrent", label="\tAccrued Liabilities"),

        FactRow(name="LiabilitiesCurrent", label="\tTotal Current Liabilities", total=True),

        HeaderRow(label='Noncurrent Liabilities'),
        FactRow(name="LongTermDebtNoncurrent", label="\tNon-current Long Term Debt"),
        FactRow(name="OtherLiabilitiesNoncurrent", label="\tOther Noncurrent Liabilities"),
        FactRow(name="LiabilitiesNoncurrent", label="\tTotal Noncurrent Liabilities", total=True),
        FactRow(name="Liabilities", label="Total Liabilities", total=True),
        HeaderRow(label='Stockholders\' Equity'),
        [
            FactRow(name="CommonStocksIncludingAdditionalPaidInCapital", label="\tCommon Stock and paid-in Capital"),
            FactRow(name="CommonStockValue", label="\tCommon Stock"),
        ],
        FactRow(name="RetainedEarningsAccumulatedDeficit", label="\tRetained Earnings"),
        FactRow(name="AccumulatedOtherComprehensiveIncomeLossNetOfTax", label="\tAccumulated Other Comprehensive Income"),
        FactRow(name="StockholdersEquity", label="\tTotal Stockholders' Equity", total=True),
        FactRow(name="LiabilitiesAndStockholdersEquity", label="Total Liabilities and Stockholders' Equity", total=True),
    ]

    def __init__(self, facts: XbrlFacts, end_date: str = None):
        super().__init__(facts, end_date)


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
        FactRow(name="NetCashProvidedByUsedInOperatingActivities", label="\tNet Cash Provided by Operating Activities",
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
        FactRow(name="NetCashProvidedByUsedInInvestingActivities", label="\tNet Cash Provided by Investing Activities",
                total=True),

        HeaderRow(label='Financing Activities'),
        FactRow(name="PaymentsRelatedToTaxWithholdingForShareBasedCompensation",
                label="\tPayments of Tax for Share-based Compensation"),
        FactRow(name="PaymentsOfDividends", label="\tDividends Paid"),
        FactRow(name="PaymentsForRepurchaseOfCommonStock", label="\tRepurchases of Common Stock"),
        FactRow(name="ProceedsFromIssuanceOfCommonStock", label="\tProceeds from Issuance of Common Stock"),
        FactRow(name="RepaymentsOfLongTermDebt", label="\tRepayments of Long-term Debt"),
        FactRow(name="NetCashProvidedByUsedInFinancingActivities", label="\tNet Cash Provided by Financing Activities",
                total=True),

        FactRow(
            name="CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
            label="Changes in Cash, cash equivalents and restricted cash"),
        FactRow(name="CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
                label="Cash, cash equivalents and restricted cash", total=True),
    ]

    def __init__(self, facts: XbrlFacts, end_date: str = None):
        super().__init__(facts, end_date)


class IncomeStatement(FactTable):
    title = "Consolidated Statement of Operations"
    mapping = [
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
        FactRow(name='MarketingExpense', label='\tMarketing Expense'),
        FactRow(name='ResearchAndDevelopmentExpense', label='\tResearch and Development Expenses'),
        [
            FactRow(name='GeneralAndAdministrativeExpense', label='\tGeneral and Administrative Expenses'),
            FactRow(name='SellingGeneralAndAdministrativeExpense',
                    label='\tSelling General and Administrative Expenses'),
        ],
        FactRow(name='OperatingExpenses', label='Total Operating Expenses', total=True),
        FactRow(name='OperatingIncomeLoss', label='Operating Income', total=True),
        HeaderRow(label='Other Income/Expense'),
        FactRow(name='InterestExpense', label='\tInterest Expense'),
        FactRow(name='NonoperatingIncomeExpense', label='\tNonoperating Income'),
        FactRow(name='IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest',
                label='Income Before Taxes', total=True),
        FactRow(name='IncomeTaxExpenseBenefit', label='Income Tax Expense'),

        FactRow(name='NetIncomeLoss', label='Net Income', total=True),
        HeaderRow(label='Earnings Per Share'),
        FactRow(name='EarningsPerShareBasic', label='\tBasic', format="{:,.2f}"),
        FactRow(name='EarningsPerShareDiluted', label='\tDiluted', format="{:,.2f}"),
        HeaderRow(label='Weighted Average Shares Outstanding'),
        FactRow(name='WeightedAverageNumberOfSharesOutstandingBasic', label='\tBasic'),
        FactRow(name='WeightedAverageNumberOfDilutedSharesOutstanding', label='\tDiluted')
    ]

    def __init__(self, facts: XbrlFacts, end_date: str = None):
        super().__init__(facts, end_date)


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
        balance_sheet = BalanceSheet(xbrl.facts)
        income_statement = IncomeStatement(xbrl.facts)
        cash_flow_statement = CashFlowStatement(xbrl.facts)
        return cls(balance_sheet, cash_flow_statement, income_statement)
