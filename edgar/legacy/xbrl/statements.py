from pydantic import BaseModel
from typing import List


class StandardConcept(BaseModel):
    concept: str
    label: str


class StandardStatement(BaseModel):
    statement_name: str
    primary_concept: str
    display_name: str
    concepts: List[StandardConcept]


BalanceSheet = StandardStatement(statement_name="BALANCE_SHEET",
                                 primary_concept="us-gaap_StatementOfFinancialPositionAbstract",
                                 display_name="Consolidated Balance Sheets",
                                 concepts=[
                                     StandardConcept(concept="us-gaap_AssetsAbstract", label="Assets"),
                                     StandardConcept(concept="us-gaap_AssetsCurrentAbstract", label="Current Assets:"),
                                     StandardConcept(concept="us-gaap_CashAndCashEquivalentsAtCarryingValue",
                                                     label="Cash & Equivalents"),
                                     StandardConcept(concept="us-gaap_AccountsReceivableNetCurrent",
                                                     label="Accounts Receivable"),
                                     StandardConcept(concept="us-gaap_InventoryNet", label="Inventory"),
                                     StandardConcept(concept="us-gaap_AssetsCurrent", label="Total Current Assets"),
                                     StandardConcept(concept="us-gaap_PropertyPlantAndEquipmentNet",
                                                     label="Property, Plant and Equipment"),
                                     StandardConcept(concept="us-gaap_Goodwill", label="Goodwill"),
                                     StandardConcept(concept="us-gaap_OtherAssetsNoncurrent", label="Other Assets"),
                                     StandardConcept(concept="us-gaap_Assets", label="Total Assets"),
                                     StandardConcept(concept="us-gaap_LiabilitiesAndStockholdersEquityAbstract",
                                                     label="Liabilities & Equity"),
                                     StandardConcept(concept="us-gaap_LiabilitiesCurrentAbstract",
                                                     label="Current Liabilities:"),
                                     StandardConcept(concept="us-gaap_AccountsPayableCurrent",
                                                     label="Accounts Payable"),
                                     StandardConcept(concept="us-gaap_LiabilitiesCurrent",
                                                     label="Total Current Liabilities"),
                                     StandardConcept(concept="us-gaap_OtherLiabilitiesNoncurrent",
                                                     label="Long-term Liabilities"),
                                     StandardConcept(concept="us-gaap_Liabilities", label="Total Liabilities"),
                                     StandardConcept(concept="us-gaap_CommitmentsAndContingencies",
                                                     label="Commitments & Contingencies"),
                                     StandardConcept(concept="us-gaap_StockholdersEquityAbstract",
                                                     label="Stockholders' Equity:"),
                                     StandardConcept(concept="us-gaap_CommonStockValue", label="Common Stock"),
                                     StandardConcept(concept="us-gaap_RetainedEarningsAccumulatedDeficit",
                                                     label="Retained Earnings"),
                                     StandardConcept(concept="us-gaap_AccumulatedOtherComprehensiveIncomeLossNetOfTax",
                                                     label="Other Comprehensive Income"),
                                     StandardConcept(concept="us-gaap_StockholdersEquity",
                                                     label="Total Stockholders' Equity"),
                                     StandardConcept(concept="us-gaap_LiabilitiesAndStockholdersEquity",
                                                     label="Total Liabilities & Equity"),
                                 ]
                                 )
IncomeStatement = StandardStatement(statement_name="INCOME_STATEMENT",
                                    primary_concept="us-gaap_IncomeStatementAbstract",
                                    display_name="Income Statements",
                                    concepts=[
                                        StandardConcept(concept="us-gaap_IncomeStatementAbstract",
                                                        label="Income Statement"),
                                        StandardConcept(
                                            concept="us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax",
                                            label="Revenue"),
                                        StandardConcept(concept="us-gaap_CostOfGoodsAndServicesSold",
                                                        label="Cost of Sales"),
                                        StandardConcept(concept="us-gaap_OperatingExpensesAbstract",
                                                        label="Operating Expenses"),
                                        StandardConcept(concept="us-gaap_ResearchAndDevelopmentExpense",
                                                        label="Research & Development"),
                                        StandardConcept(concept="us-gaap_SellingGeneralAndAdministrativeExpense",
                                                        label="Selling, General & Admin"),
                                        StandardConcept(concept="us-gaap_OperatingExpenses",
                                                        label="Total Operating Expenses"),

                                        StandardConcept(concept="us-gaap_OperatingIncomeLoss",
                                                        label="Operating Income"),
                                        StandardConcept(
                                            concept="us-gaap_IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                                            label="Pre-tax Income"),
                                        StandardConcept(concept="us-gaap_IncomeTaxExpenseBenefit",
                                                        label="Income Tax"),
                                        StandardConcept(concept="us-gaap_NetIncomeLoss",
                                                        label="Net Income"),
                                        StandardConcept(concept="us-gaap_EarningsPerShareBasic",
                                                        label="EPS Basic"),
                                        StandardConcept(concept="us-gaap_EarningsPerShareDiluted",
                                                        label="EPS Diluted"),
                                        StandardConcept(
                                            concept="us-gaap_WeightedAverageNumberOfSharesOutstandingBasic",
                                            label="Shares Basic"),
                                        StandardConcept(
                                            concept="us-gaap_WeightedAverageNumberOfDilutedSharesOutstanding",
                                            label="Shares Diluted"),
                                    ]
                                    )
CashFlowStatement = StandardStatement(statement_name="CASH_FLOW",
                                      primary_concept="us-gaap_StatementOfCashFlowsAbstract",
                                      display_name="Consolidated Statement of Cash Flows",
                                      concepts=[
                                          StandardConcept(
                                              concept="us-gaap_NetCashProvidedByUsedInOperatingActivitiesAbstract",
                                              label="Operating Activities:"),
                                          StandardConcept(
                                              concept="us-gaap_AdjustmentsToReconcileNetIncomeLossToCashProvidedByUsedInOperatingActivitiesAbstract",
                                              label="Adjustments to Net Income:"),
                                          StandardConcept(concept="us-gaap_ShareBasedCompensation",
                                                          label="Stock-based Compensation"),
                                          StandardConcept(concept="us-gaap_IncreaseDecreaseInOperatingCapitalAbstract",
                                                          label="Changes in Working Capital:"),
                                          StandardConcept(concept="us-gaap_IncreaseDecreaseInInventories",
                                                          label="Inventories"),
                                          StandardConcept(concept="us-gaap_NetCashProvidedByUsedInOperatingActivities",
                                                          label="Net Cash from Operations"),
                                          StandardConcept(
                                              concept="us-gaap_NetCashProvidedByUsedInInvestingActivitiesAbstract",
                                              label="Investing Activities:"),
                                          StandardConcept(concept="us-gaap_PaymentsToAcquirePropertyPlantAndEquipment",
                                                          label="Capital Expenditures"),
                                          StandardConcept(concept="us-gaap_NetCashProvidedByUsedInInvestingActivities",
                                                          label="Net Cash from Investing"),
                                          StandardConcept(
                                              concept="us-gaap_NetCashProvidedByUsedInFinancingActivitiesAbstract",
                                              label="Financing Activities:"),
                                          StandardConcept(concept="us-gaap_PaymentsForRepurchaseOfCommonStock",
                                                          label="Stock Repurchases"),
                                          StandardConcept(concept="us-gaap_NetCashProvidedByUsedInFinancingActivities",
                                                          label="Net Cash from Financing"),
                                          StandardConcept(
                                              concept="us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
                                              label="Total Cash and Equivalents"),
                                          StandardConcept(
                                              concept="us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseIncludingExchangeRateEffect",
                                              label="Net Change in Cash"),
                                      ]
                                      )
StatementOfChangesInEquity = StandardStatement(statement_name="EQUITY",
                                               primary_concept="us-gaap_StatementOfStockholdersEquityAbstract",
                                               display_name="Consolidated Statement of Shareholders Equity",
                                               concepts=[
                                                   StandardConcept(concept="us-gaap_CommonStockMember",
                                                                   label="Common Stock"),
                                                   StandardConcept(concept="us-gaap_AdditionalPaidInCapitalMember",
                                                                   label="Additional Paid-in Capital"),
                                                   StandardConcept(
                                                       concept="us-gaap_AccumulatedOtherComprehensiveIncomeMember",
                                                       label="Accumulated Other Comprehensive Income (Loss)"),
                                                   StandardConcept(concept="us-gaap_RetainedEarningsMember",
                                                                   label="Retained Earnings"),
                                                   StandardConcept(concept="us-gaap_StatementLineItems",
                                                                   label="Statement [Line Items]"),
                                                   StandardConcept(
                                                       concept="us-gaap_IncreaseDecreaseInStockholdersEquityRollForward",
                                                       label="Increase (Decrease) in Stockholders' Equity [Roll Forward]"),
                                                   StandardConcept(
                                                       concept="us-gaap_AdjustmentsToAdditionalPaidInCapitalSharebasedCompensationRequisiteServicePeriodRecognitionValue",
                                                       label="Stock-based compensation"),
                                               ]
                                               )
StatementOfComprehensiveIncome = StandardStatement(statement_name="COMPREHENSIVE_INCOME",
                                                   primary_concept="us-gaap_StatementOfIncomeAndComprehensiveIncomeAbstract"
                                                   , display_name="Comprehensive Income Statement",
                                                   concepts=[
                                                       StandardConcept(
                                                           concept="us-gaap_StatementOfIncomeAndComprehensiveIncomeAbstract",
                                                           label="Statement of Comprehensive Income"),
                                                       StandardConcept(concept="us-gaap_ComprehensiveIncomeNetOfTax",
                                                                       label="Comprehensive income"),
                                                   ]
                                                   )
cover_page = StandardStatement(statement_name="COVER_PAGE",
                               primary_concept="dei_CoverAbstract",
                               display_name="Cover Page",
                               concepts=[])
