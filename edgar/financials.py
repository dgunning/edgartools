import re
from typing import Union, List, Tuple

import pandas as pd
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from edgar._rich import repr_rich

__all__ = [
    'Financials',
    'BalanceSheet',
    'CashflowStatement',
    'IncomeStatement',
    'format_currency'
]

gaap_facts = {'AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment': 'Accumulated Depreciation',
              'AllowanceForDoubtfulAccountsReceivableCurrent': 'Allowance for Doubtful Accounts',
              'Assets': 'Total Assets',
              'AssetsCurrent': 'Current Assets',
              'AccountsReceivableNetCurrent': 'Accounts Receivable',
              'AvailableForSaleSecuritiesDebtSecuritiesCurrent': 'Short Term Investments',
              'CashAndCashEquivalentsAtCarryingValue': 'Cash and Cash Equivalents',
              'CostOfGoodsAndServicesSold': 'Cost of Revenue',
              'Goodwill': 'Goodwill',
              'GrossProfit': 'Gross Profit',
              'Liabilities': 'Total Liabilities',
              'LiabilitiesCurrent': 'Current Liabilities',
              'RetainedEarningsAccumulatedDeficit': 'AccumulatedDeficit',
              'StockholdersEquity': 'Stockholders Equity',
              'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest': 'Stockholders Equity',
              'LiabilitiesAndStockholdersEquity': 'Liabilities & Equity',
              'RevenueFromContractWithCustomerExcludingAssessedTax': 'Total Revenue',
              'PropertyPlantAndEquipmentNet': 'Property, Plant & Equipment',
              'OperatingLeaseRightOfUseAsset': 'Operating Lease Right of Use Asset',
              'OperatingExpenses': 'Operating Expenses',
              'DepreciationDepletionAndAmortization': 'Depreciation & Amortization',
              'OperatingIncomeLoss': 'Operating Income or Loss',
              'NetIncomeLoss': 'Net Income',
              'InvestmentIncomeInterestAndDividend': 'Investment Income Interest and Dividend',
              'RepaymentsOfLongTermDebt': 'Repayments of Long Term Debt',
              'InventoryNet': 'Inventories',
              'DeferredIncomeTaxExpenseBenefit': 'Deferred Income Tax Expense (Benefit)',
              'OtherNoncashIncomeExpense': 'Other Noncash Income (Expense)',
              'FiniteLivedIntangibleAssetsNet': 'Finite Lived Intangible Assets',
              'IntangibleAssetsNetExcludingGoodwill': 'Intangible Assets',
              'CapitalizedContractCostNetNoncurrent': 'Contract Assets',
              'MarketableSecuritiesCurrent': 'Short Term Investments',
              'OtherAssetsCurrent': 'Other Current Assets',
              'PaymentsOfDividends': 'Dividends Paid',
              'InterestExpense': 'Interest Expense',
              'NetCashProvidedByUsedInInvestingActivities': 'Net Cash used in Investing Activities',
              'NetCashProvidedByUsedInFinancingActivities': 'Net Cash used in Financing Activities',
              'PaymentsForProceedsFromOtherInvestingActivities': 'Other Investing Activities',
              'PaymentsToAcquireBusinessesNetOfCashAcquired': 'Acquisitions',
              'PaymentsToAcquirePropertyPlantAndEquipment': 'Investents in Property, Plant & Equipment',
              'NetCashProvidedByUsedInOperatingActivities': 'Net Cash from Operating Activities'}


def format_currency(value: Union[str, float]):
    if isinstance(value, str):
        if value.isdigit() or re.match(r"-?\d+\.?\d*", value):
            value = float(value)
        else:
            return value
    # return the value as a currency string right justified

    return f"${value:,.0f}".rjust(20)


def get_gaap(gaap,
             fact: str):
    res = gaap[gaap.fact == fact]
    if not res.empty:
        row = res.iloc[0]
        return gaap_facts.get(row.fact, row.fact), format_currency(row.value)

    return fact, ""


class FinancialTable:
    """Base class for financial tables like Balance Sheet, Income Statement, Cashflow Statement"""

    def __init__(self,
                 gaap: pd.DataFrame):
        self.gaap = gaap
        self.fields = []

    def get_fact(self, fact: str, currency: bool = True):
        res = self.gaap[self.gaap.fact == fact]
        if not res.empty:
            if len(res) > 1:
                #  Get the row in res that has the largest value, numerically
                # Also handle exception if value is not a number
                try:
                    res = res[res.index == res.value.astype(float).idxmax()]
                except ValueError:
                    res = res.iloc[0]
            return gaap_facts.get(fact, fact), format_currency(res.iloc[0].value) if currency else res.iloc[0].value

    def get_value(self, fact: str, currency: bool = True):
        fact = self.get_fact(fact, currency=currency)
        if fact:
            return fact[1].lstrip()

    def _add_row(self, table: Table, fact: str, currency: bool = True):
        fact_row = self.get_fact(fact, currency=currency)
        if fact_row:
            table.add_row(*fact_row)

    def _get_facts(self, facts: List[str]) -> List[Tuple[str, object]]:
        for fact in facts:
            fact_row = self.get_fact(fact)
            if fact_row:
                yield fact_row

    def _get_facts_dataframe(self, facts: List[str]):
        return pd.DataFrame(list(self._get_facts(facts)),
                            columns=['Fact', 'Value']).dropna().reset_index(drop=True)


class BalanceSheet(FinancialTable):
    """A company's balance sheet"""

    ASSET_FACTS = [
        'CashAndCashEquivalentsAtCarryingValue',
        'MarketableSecuritiesCurrent',
        'AccountsReceivableNetCurrent',
        'InventoryNet',
        'OtherAssetsCurrent',
        'AssetsCurrent',
        'AvailableForSaleSecuritiesDebtSecuritiesCurrent',
        'Goodwill',
        'Assets'
    ]
    LIABILITY_EQUITY_FACTS = [
        "LiabilitiesCurrent",
        "LiabilitiesNoncurrent",
        "Liabilities",
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "LiabilitiesAndStockholdersEquity"
    ]

    def __init__(self,
                 gaap: pd.DataFrame):
        super().__init__(gaap)

    @property
    def cash_and_cash_equivalents(self):
        return self.get_value('CashAndCashEquivalentsAtCarryingValue')

    @property
    def short_term_investments(self):
        return self.get_value('MarketableSecuritiesCurrent')

    @property
    def long_term_investments(self):
        return self.get_value('MarketableSecuritiesNoncurrent')

    @property
    def property_plant_and_equipment(self):
        return self.get_value('PropertyPlantAndEquipmentNet')

    @property
    def goodwill(self):
        return self.get_value('Goodwill')

    @property
    def inventories(self):
        return self.get_value('InventoryNet')

    @property
    def total_assets(self):
        return self.get_value('Assets')

    @property
    def total_liabilities(self):
        return self.get_value('Liabilities')

    @property
    def total_current_assets(self):
        return self.get_value('AssetsCurrent')

    @property
    def other_current_assets(self):
        return self.get_value('OtherAssetsCurrent')

    @property
    def total_non_current_assets(self):
        return self.get_value('AssetsNoncurrent')

    @property
    def other_non_current_assets(self):
        return self.get_value('OtherAssetsNoncurrent')

    @property
    def share_holders_equity(self):
        return self.get_value('StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest')

    @property
    def asset_dataframe(self):
        return self._get_facts_dataframe(BalanceSheet.ASSET_FACTS)

    @property
    def liability_equity_dataframe(self):
        return self._get_facts_dataframe(BalanceSheet.LIABILITY_EQUITY_FACTS)

    def __rich__(self):
        assets_table = Table("", "", box=box.ROUNDED, title='Assets', title_style='bold deep_sky_blue1')
        for row in self.asset_dataframe.itertuples():
            assets_table.add_row(row.Fact, row.Value)

        liab_equity_table = Table("", "", box=box.ROUNDED, title='Liabilities and Shareholders Equity',
                                  title_style='bold deep_sky_blue1')
        for row in self.liability_equity_dataframe.itertuples():
            liab_equity_table.add_row(row.Fact, row.Value)

        return Panel(
            Group(
                assets_table,
                liab_equity_table
            ), title="Balance Sheet"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return "Balance Sheet()"

    @classmethod
    def from_gaap(cls, gaap: pd.DataFrame):
        return cls(gaap)


class CashflowStatement(FinancialTable):
    CASHFLOW_FACTS = [
        'NetIncomeLoss',
        'DepreciationDepletionAndAmortization',
        'DeferredIncomeTaxExpenseBenefit',
        'OtherNoncashIncomeExpense',
        'NetCashProvidedByUsedInOperatingActivities',
        'PaymentsToAcquirePropertyPlantAndEquipment',
        'PaymentsToAcquireBusinessesNetOfCashAcquired',
        'PaymentsForProceedsFromOtherInvestingActivities',
        'NetCashProvidedByUsedInInvestingActivities',
        'RepaymentsOfLongTermDebt',
        'NetCashProvidedByUsedInFinancingActivities',
        'PaymentsOfDividends'
    ]

    def __init__(self,
                 gaap: pd.DataFrame):
        super().__init__(gaap)

    @property
    def net_income(self):
        return self.get_value('NetIncomeLoss')

    @property
    def depreciation_and_amortization(self):
        return self.get_value('DepreciationDepletionAndAmortization')

    @property
    def deffered_income_tax(self):
        return self.get_value('DeferredIncomeTax')

    @property
    def stock_based_compensation(self):
        return self.get_value('StockBasedCompensation')

    @property
    def other_non_cash_items(self):
        return self.get_value('OtherNoncashIncomeExpense')

    @property
    def net_cash_provided_by_operating_activities(self):
        return self.get_value('NetCashProvidedByUsedInOperatingActivities')

    @property
    def cashflow_dataframe(self):
        return self._get_facts_dataframe(CashflowStatement.CASHFLOW_FACTS)

    def __rich__(self):
        cashflow_table = Table("", "", box=box.ROUNDED)
        for row in self.cashflow_dataframe.itertuples():
            cashflow_table.add_row(row.Fact, row.Value)
        return Panel(
            Group(
                cashflow_table
            ), title="Cash Flow Statement"
        )

    def __str__(self):
        return "Cash Flow Statement()"

    def __repr__(self):
        return repr_rich(self.__rich__())

    @classmethod
    def from_gaap(cls, gaap: pd.DataFrame):
        return cls(gaap)


class IncomeStatement(FinancialTable):
    INCOME_STATEMENT_FACTS = [
        'RevenueFromContractWithCustomerExcludingAssessedTax',
        'CostOfGoodsAndServicesSold',
        'GrossProfit',
        'OperatingExpenses',
        'OperatingIncomeLoss',
        'InvestmentIncomeInterestAndDividend',
        'NetIncomeLoss',
        'InterestExpense',
    ]

    def __init__(self,
                 gaap: pd.DataFrame):
        super().__init__(gaap)

    @property
    def revenue(self):
        return self.get_value('RevenueFromContractWithCustomerExcludingAssessedTax')

    @property
    def cost_of_revenue(self):
        return self.get_value('CostOfGoodsAndServicesSold')

    @property
    def research_and_development_expenses(self):
        return self.get_value('ResearchAndDevelopmentExpense')

    @property
    def selling_general_and_administrative_expenses(self):
        return self.get_value('SellingGeneralAndAdministrativeExpense')

    @property
    def income_before_tax(self):
        return self.get_value(
            'IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest')

    @property
    def income_tax_expense(self):
        return self.get_value('IncomeTaxExpenseBenefit')

    @property
    def gross_profit(self):
        return self.get_value('GrossProfit')

    @property
    def operating_income(self):
        return self.get_value('OperatingIncomeLoss')

    @property
    def operating_expenses(self):
        return self.get_value('OperatingExpenses')

    @property
    def net_income(self):
        return self.get_value('NetIncomeLoss')

    @property
    def interest_and_dividend_incoms(self):
        return self.get_value('InvestmentIncomeInterestAndDividend')

    @property
    def depreciation_and_amortization(self):
        return self.get_value('DepreciationDepletionAndAmortization')

    @property
    def earnings_per_share(self):
        return self.get_value('EarningsPerShareBasic', currency=False)

    @property
    def interest_expense(self):
        return self.get_value('InterestExpense')

    @property
    def income_statement_dataframe(self):
        return self._get_facts_dataframe(IncomeStatement.INCOME_STATEMENT_FACTS)

    def __rich__(self):
        income_table = Table("", "", box=box.ROUNDED)
        for row in self.income_statement_dataframe.itertuples():
            income_table.add_row(row.Fact, row.Value)

        return Panel(
            income_table,
            title="Income Statement"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return "Income Statement()"

    @classmethod
    def from_gaap(cls, gaap: pd.DataFrame):
        return cls(gaap)


class Financials:

    # Financials is a base class for IncomeStatement, BalanceSheet, CashFlowStatement
    def __init__(self,
                 balance_sheet: BalanceSheet,
                 cash_flow_statement: CashflowStatement,
                 income_statement: IncomeStatement):
        self.balance_sheet: BalanceSheet = balance_sheet
        self.cash_flow_statement: CashflowStatement = cash_flow_statement
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
    def from_gaap(cls,
                  gaap: pd.DataFrame):
        balance_sheet = BalanceSheet.from_gaap(gaap)
        income_statement = IncomeStatement.from_gaap(gaap)
        cash_flow_statement = CashflowStatement.from_gaap(gaap)
        return cls(balance_sheet, cash_flow_statement, income_statement)
