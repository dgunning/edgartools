import pandas as pd
from rich.table import Table
from rich.panel import Panel
from rich.console import Group
from rich import box
from typing import Union
from edgar._rich import repr_rich
import re

__all__ = [
    'Financials',
    'BalanceSheet',
    'CashflowStatement',
    'IncomeStatement',
    ]

gaap_facts = {'Assets': 'Total Assets',
              'AssetsCurrent': 'Current Assets',
              'CashAndCashEquivalentsAtCarryingValue': 'Cash',
              'AccountsReceivableNetCurrent': 'Accounts Receivable',
              'AvailableForSaleSecuritiesDebtSecuritiesCurrent': 'Short Term Investments',
              'Goodwill': 'Goodwill',
              'Liabilities': 'Total Liabilities',
              'LiabilitiesCurrent': 'Current Liabilities',
              'RetainedEarningsAccumulatedDeficit': 'AccumulatedDeficit',
              'StockholdersEquity': 'Stockholders Equity',
              'StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest': 'Stockholders Equity',
              'LiabilitiesAndStockholdersEquity': 'Liabilities & Equity',
              'RevenueFromContractWithCustomerExcludingAssessedTax': 'Total Revenue',
              'CostOfGoodsAndServicesSold': 'Cost of Revenue',
              'GrossProfit': 'Gross Profit',
              'OperatingExpenses': 'Operating Expenses',
              'OperatingIncomeLoss': 'Operating Income or Loss',
              'NetIncomeLoss': 'Net Income',
              'NetCashProvidedByUsedInOperatingActivities': 'Net Cash from Operating Activities'}


def format_currency(value: Union[str, float]):
    if isinstance(value, str):
        if value.isdigit() or re.match("-?\d+\.?\d*", value):
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


BALANCE_SHEET_FACTS = {
    'AssetsCurrent': 'Current Assets',
    'OtherAssetsCurrent': 'Other Current Assets',
    'CashAndCashEquivalentsAtCarryingValue': 'Cash',
    'ShortTermInvestments': 'Short Term Investments',
    'AllowanceForDoubtfulAccountsReceivableCurrent': 'Allowance for Doubtful Accounts',
    'AvailableForSaleSecuritiesDebtSecuritiesCurrent': 'Short Term Investments',
    'AccountsReceivableNetCurrent': 'Accounts Receivable',
    'InventoryNet': 'Inventory',
    'CapitalizedContractCostNetCurrent': 'Contract Assets',
    'PrepaidExpenseAndOtherAssetsCurrent': 'Prepaid Expenses',
    'AvailableForSaleSecuritiesDebtSecuritiesNoncurrent': 'Long Term Investments',
    'PropertyPlantAndEquipmentNet': 'Property, Plant & Equipment',
    'AccumulatedDepreciationDepletionAndAmortizationPropertyPlantAndEquipment': 'Accumulated Depreciation',
    'OperatingLeaseRightOfUseAsset': 'Operating Lease Right of Use Asset',
    'Goodwill': 'Goodwill',
    'FiniteLivedIntangibleAssetsNet': 'Finite Lived Intangible Assets',
    'IntangibleAssetsNetExcludingGoodwill': 'Intangible Assets',
    'CapitalizedContractCostNetNoncurrent': 'Contract Assets',
    'OtherAssetsNoncurrent': 'Other Non Current Assets',
    'Assets': 'Total Assets'
}


class FinancialTable:

    """Base class for financial tables like Balance Sheet, Income Statement, Cashflow Statement"""

    def __init__(self,
                 gaap: pd.DataFrame):
        self.gaap = gaap

    def get_fact(self, fact: str, currency: bool = True):
        res = self.gaap[self.gaap.fact == fact]
        if not res.empty:
            if len(res) > 1:
                #  Get the row in res that has the largest value, numerically
                # Also handle exception if value is not a number
                try:
                    res = res[res.index==res.value.astype(float).idxmax()]
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


class BalanceSheet(FinancialTable):

    """A company's balance sheet"""

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

    def share_holders_equity(self):
        return self.get_value('StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest')

    def __rich__(self):
        assets_table = Table("", "", title='Assets', box=box.ROUNDED)
        self._add_row(assets_table, 'AssetsCurrent')
        self._add_row(assets_table, 'CashAndCashEquivalentsAtCarryingValue')
        self._add_row(assets_table, 'AccountsReceivableNetCurrent')
        self._add_row(assets_table, 'AvailableForSaleSecuritiesDebtSecuritiesCurrent')
        self._add_row(assets_table, 'Goodwill')
        self._add_row(assets_table, 'Assets')

        liab_equity_table = Table("", "", title='Liabilities and Shareholders Equity', box=box.ROUNDED)
        self._add_row(liab_equity_table, 'LiabilitiesCurrent')
        self._add_row(liab_equity_table, 'Liabilities')
        self._add_row(liab_equity_table, 'StockholdersEquity')
        self._add_row(liab_equity_table, 'LiabilitiesAndStockholdersEquity')
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

    def __rich__(self):
        cashflow_table = Table("", "",  box=box.ROUNDED)
        self._add_row(cashflow_table, 'AssetsCurrent')
        self._add_row(cashflow_table, 'DepreciationDepletionAndAmortization')
        self._add_row(cashflow_table, 'OtherNoncashIncomeExpense')
        self._add_row(cashflow_table, 'NetCashProvidedByUsedInOperatingActivities')
        return Panel(
            Group(
                cashflow_table
            ), title="Cash Flow Statement"
        )

    def __str__(self):
        return f"Cash Flow Statement()"
    def __repr__(self):
        return repr_rich(self.__rich__())

    @classmethod
    def from_gaap(cls, gaap: pd.DataFrame):
        return cls(gaap)


class IncomeStatement(FinancialTable):

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
    def net_income(self):
        return self.get_value('NetIncomeLoss')

    @property
    def depreciation_and_amortization(self):
        return self.get_value('DepreciationDepletionAndAmortization')

    @property
    def earnings_per_share(self):
        return self.get_value('EarningsPerShareBasic', currency=False)

    def __rich__(self):
        income_table = Table("", "", box=box.SIMPLE)
        self._add_row(income_table, 'RevenueFromContractWithCustomerExcludingAssessedTax')
        self._add_row(income_table, 'CostOfGoodsAndServicesSold')
        self._add_row(income_table, 'GrossProfit')
        self._add_row(income_table, 'OperatingExpenses')
        self._add_row(income_table, 'OperatingIncomeLoss')
        self._add_row(income_table, 'NetIncomeLoss')
        self._add_row(income_table, 'InterestExpenseIncomeNet')

        return Panel(
            income_table,
            title="Income Statement"
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    def __str__(self):
        return f"Income Statement()"

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
        return f"Company Financials()"

    @classmethod
    def from_gaap(cls,
                  gaap: pd.DataFrame):
        balance_sheet = BalanceSheet.from_gaap(gaap)
        income_statement = IncomeStatement.from_gaap(gaap)
        cash_flow_statement = CashflowStatement.from_gaap(gaap)
        return cls(balance_sheet, cash_flow_statement, income_statement)
