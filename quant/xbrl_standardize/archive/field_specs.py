"""
Income Statement Field Specifications

Defines the canonical income statement structure for standardized mapping.

Each field specification includes:
- standardLabel: Canonical field name (used in output)
- displayLabel: Human-readable label
- semanticType: What this field represents semantically
- derivationPriority: Can it be computed if not found directly?
- candidateConcepts: XBRL concepts that could map to this field
- filters: Constraints for concept selection (prefer_total, exclude_abstracts)
- computeAlternatives: Formulas to derive the field if not found
- sectorRules: Sector-specific overrides
- optional: Whether field is required

Field evaluation follows dependency order to enable computed fields.
"""

from typing import Dict, List, Any

__version__ = "1.0.0"

# ==============================================================================
# INCOME STATEMENT FIELD SPECIFICATIONS
# ==============================================================================

INCOME_STATEMENT_FIELDS: Dict[str, Dict[str, Any]] = {

    # ==========================================================================
    # REVENUE
    # ==========================================================================
    "revenue": {
        "standardLabel": "revenue",
        "displayLabel": "Revenue",
        "semanticType": "topline_revenue",
        "derivationPriority": "direct",  # Must be present, don't compute
        "candidateConcepts": [
            # General corporates (priority order)
            "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
            "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax",
            "us-gaap:Revenues",
            "us-gaap:SalesRevenueNet",
            "us-gaap:RevenuesNetOfInterestExpense",
            "us-gaap:SalesRevenueGoodsNet",
            "us-gaap:SalesRevenueServicesNet",
            # IFRS
            "ifrs-full:Revenue",
            "ifrs-full:RevenueFromContractsWithCustomers",
            "ifrs-full:RevenueFromContractsWithCustomersExcludingAssessedTax",
        ],
        "filters": {
            "prefer_total": True,
            "exclude_abstracts": True,
        },
        "sectorRules": {
            "financials_banking": {
                "computeExpression": {
                    "op": "add",
                    "terms": [
                        "us-gaap:InterestIncomeExpenseNet",
                        "us-gaap:NoninterestIncome"
                    ],
                    "description": "Net Interest Income + Noninterest Income"
                },
                "candidateConcepts": [
                    "us-gaap:InterestAndOtherIncome",
                    "us-gaap:InterestIncomeExpenseNet",
                    "us-gaap:InterestAndDividendIncomeOperating"
                ]
            },
            "energy_utilities": {
                "candidateConcepts": [
                    "us-gaap:RegulatedAndUnregulatedOperatingRevenue",
                    "us-gaap:OperatingRevenues",
                    "us-gaap:Revenues"
                ]
            },
            "financials_realestate": {
                "candidateConcepts": [
                    "us-gaap:RealEstateRevenueNet",
                    "us-gaap:OperatingLeasesIncomeStatementLeaseRevenue",
                    "us-gaap:Revenues"
                ]
            },
            "financials_insurance": {
                "candidateConcepts": [
                    "us-gaap:PremiumsEarnedNet",
                    "us-gaap:Revenues",
                ]
            }
        }
    },

    # ==========================================================================
    # COST OF REVENUE
    # ==========================================================================
    "costOfRevenue": {
        "standardLabel": "costOfRevenue",
        "displayLabel": "Cost of Revenue",
        "semanticType": "direct_costs",
        "derivationPriority": "direct_or_compute",
        "candidateConcepts": [
            "us-gaap:CostOfRevenue",
            "us-gaap:CostOfGoodsAndServicesSold",
            "us-gaap:CostOfGoodsSold",
            "us-gaap:CostOfServices",
            "us-gaap:CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization",
            "ifrs-full:CostOfSales",
        ],
        "computeAlternatives": [
            {
                "op": "subtract",
                "terms": ["revenue", "grossProfit"],
                "description": "Revenue - Gross Profit"
            }
        ],
        "sectorRules": {
            "financials_banking": {
                "notApplicable": True,
                "note": "Banks don't have traditional COGS"
            },
            "financials_insurance": {
                "candidateConcepts": [
                    "us-gaap:PolicyholderBenefitsAndClaimsIncurred",
                    "us-gaap:BenefitsLossesAndExpenses",
                    "us-gaap:LifePolicyholderBenefitsAndClaimsIncurred"
                ]
            }
        }
    },

    # ==========================================================================
    # GROSS PROFIT
    # ==========================================================================
    "grossProfit": {
        "standardLabel": "grossProfit",
        "displayLabel": "Gross Profit",
        "semanticType": "subtotal",
        "derivationPriority": "direct_or_compute",
        "candidateConcepts": [
            "us-gaap:GrossProfit",
            "ifrs-full:GrossProfit",
        ],
        "filters": {
            "prefer_total": True,
        },
        "computeAlternatives": [
            {
                "op": "subtract",
                "terms": ["revenue", "costOfRevenue"],
                "description": "Revenue - Cost of Revenue"
            }
        ],
        "sectorRules": {
            "financials_banking": {
                "notApplicable": True,
                "note": "Banks use net interest income instead"
            }
        }
    },

    # ==========================================================================
    # OPERATING EXPENSES
    # ==========================================================================
    "operatingExpenses": {
        "standardLabel": "operatingExpenses",
        "displayLabel": "Operating Expenses",
        "semanticType": "operating_costs",
        "derivationPriority": "direct_or_compute",
        "candidateConcepts": [
            "us-gaap:OperatingExpenses",
            "us-gaap:OperatingCostsAndExpenses",
            "ifrs-full:OperatingExpense",
        ],
        "computeAlternatives": [
            {
                "op": "add",
                "terms": [
                    "researchAndDevelopmentExpense",
                    "sellingGeneralAndAdministrativeExpense"
                ],
                "description": "R&D + SG&A"
            },
            {
                "op": "add",
                "terms": [
                    "sellingGeneralAndAdministrativeExpense",
                    "generalAndAdministrativeExpense",
                    "sellingAndMarketingExpense"
                ],
                "description": "Sum of individual operating expense categories"
            }
        ],
        "sectorRules": {
            "financials_banking": {
                "candidateConcepts": [
                    "us-gaap:NoninterestExpense",
                ]
            }
        }
    },

    # ==========================================================================
    # R&D EXPENSE
    # ==========================================================================
    "researchAndDevelopmentExpense": {
        "standardLabel": "researchAndDevelopmentExpense",
        "displayLabel": "Research & Development",
        "semanticType": "operating_expense_component",
        "derivationPriority": "direct",
        "candidateConcepts": [
            "us-gaap:ResearchAndDevelopmentExpense",
            "us-gaap:ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost",
            "ifrs-full:ResearchAndDevelopmentExpense",
        ],
        "optional": True,  # Not all companies have R&D
    },

    # ==========================================================================
    # SG&A EXPENSE
    # ==========================================================================
    "sellingGeneralAndAdministrativeExpense": {
        "standardLabel": "sellingGeneralAndAdministrativeExpense",
        "displayLabel": "SG&A Expense",
        "semanticType": "operating_expense_component",
        "derivationPriority": "direct_or_compute",
        "candidateConcepts": [
            "us-gaap:SellingGeneralAndAdministrativeExpense",
            "us-gaap:GeneralAndAdministrativeExpense",
            "ifrs-full:SellingGeneralAndAdministrativeExpense",
        ],
        "computeAlternatives": [
            {
                "op": "add",
                "terms": [
                    "us-gaap:SellingAndMarketingExpense",
                    "us-gaap:GeneralAndAdministrativeExpense"
                ],
                "description": "Selling & Marketing + G&A"
            }
        ]
    },

    # ==========================================================================
    # OPERATING INCOME
    # ==========================================================================
    "operatingIncome": {
        "standardLabel": "operatingIncome",
        "displayLabel": "Operating Income",
        "semanticType": "subtotal",
        "derivationPriority": "direct_or_compute",
        "candidateConcepts": [
            "us-gaap:OperatingIncomeLoss",
            "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
            "ifrs-full:OperatingIncome",
            "ifrs-full:ProfitLossFromOperatingActivities",
        ],
        "filters": {
            "prefer_total": True,
        },
        "computeAlternatives": [
            {
                "op": "subtract",
                "terms": ["grossProfit", "operatingExpenses"],
                "description": "Gross Profit - Operating Expenses"
            },
            {
                "op": "add",
                "terms": ["revenue", "costOfRevenue", "operatingExpenses"],
                "coefficients": [1, -1, -1],
                "description": "Revenue - COGS - OpEx"
            }
        ]
    },

    # ==========================================================================
    # INTEREST EXPENSE
    # ==========================================================================
    "interestExpense": {
        "standardLabel": "interestExpense",
        "displayLabel": "Interest Expense",
        "semanticType": "non_operating_expense",
        "derivationPriority": "direct",
        "candidateConcepts": [
            "us-gaap:InterestExpense",
            "us-gaap:InterestExpenseDebt",
            "us-gaap:InterestExpenseOther",
            "ifrs-full:InterestExpense",
        ],
        "optional": True,
        "sectorRules": {
            "financials_banking": {
                "notApplicable": True,
                "note": "Interest is operating for banks, use InterestIncomeExpenseNet in revenue"
            }
        }
    },

    # ==========================================================================
    # OTHER INCOME/EXPENSE
    # ==========================================================================
    "otherIncomeExpense": {
        "standardLabel": "otherIncomeExpense",
        "displayLabel": "Other Income (Expense), Net",
        "semanticType": "non_operating",
        "derivationPriority": "direct",
        "candidateConcepts": [
            "us-gaap:NonoperatingIncomeExpense",
            "us-gaap:OtherNonoperatingIncomeExpense",
            "us-gaap:OtherIncomeAndExpenses",
            "ifrs-full:OtherIncomeExpenseNet",
        ],
        "optional": True
    },

    # ==========================================================================
    # PRETAX INCOME
    # ==========================================================================
    "incomeBeforeTaxes": {
        "standardLabel": "incomeBeforeTaxes",
        "displayLabel": "Income Before Taxes",
        "semanticType": "subtotal",
        "derivationPriority": "direct_or_compute",
        "candidateConcepts": [
            "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            "us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
            "us-gaap:IncomeLossAttributableToParent",
            "ifrs-full:ProfitLossBeforeTax",
        ],
        "filters": {
            "prefer_total": True,
        },
        "computeAlternatives": [
            {
                "op": "subtract",
                "terms": ["operatingIncome", "interestExpense"],
                "description": "Operating Income - Interest Expense"
            },
            {
                "op": "add",
                "terms": ["netIncome", "incomeTaxExpense"],
                "description": "Net Income + Tax Expense"
            }
        ]
    },

    # ==========================================================================
    # INCOME TAX EXPENSE
    # ==========================================================================
    "incomeTaxExpense": {
        "standardLabel": "incomeTaxExpense",
        "displayLabel": "Income Tax Expense",
        "semanticType": "tax",
        "derivationPriority": "direct_or_compute",
        "candidateConcepts": [
            "us-gaap:IncomeTaxExpenseBenefit",
            "us-gaap:IncomeTaxesPaid",
            "us-gaap:CurrentIncomeTaxExpenseBenefit",
            "ifrs-full:IncomeTaxExpenseContinuingOperations",
        ],
        "computeAlternatives": [
            {
                "op": "subtract",
                "terms": ["incomeBeforeTaxes", "netIncome"],
                "description": "Pretax Income - Net Income"
            }
        ]
    },

    # ==========================================================================
    # NET INCOME
    # ==========================================================================
    "netIncome": {
        "standardLabel": "netIncome",
        "displayLabel": "Net Income",
        "semanticType": "bottom_line",
        "derivationPriority": "direct",
        "candidateConcepts": [
            "us-gaap:NetIncomeLoss",
            "us-gaap:ProfitLoss",
            "us-gaap:NetIncomeLossAvailableToCommonStockholdersBasic",
            "ifrs-full:ProfitLoss",
            "ifrs-full:ProfitLossAttributableToOwnersOfParent",
        ],
        "filters": {
            "prefer_total": True,
        }
    },

    # ==========================================================================
    # EARNINGS PER SHARE
    # ==========================================================================
    "earningsPerShareBasic": {
        "standardLabel": "earningsPerShareBasic",
        "displayLabel": "EPS - Basic",
        "semanticType": "per_share_metric",
        "derivationPriority": "direct_or_compute",
        "candidateConcepts": [
            "us-gaap:EarningsPerShareBasic",
            "ifrs-full:BasicEarningsLossPerShare",
        ],
        "computeAlternatives": [
            {
                "op": "divide",
                "terms": ["netIncome", "weightedAverageSharesOutstandingBasic"],
                "description": "Net Income / Weighted Average Shares"
            }
        ]
    },

    "earningsPerShareDiluted": {
        "standardLabel": "earningsPerShareDiluted",
        "displayLabel": "EPS - Diluted",
        "semanticType": "per_share_metric",
        "derivationPriority": "direct",
        "candidateConcepts": [
            "us-gaap:EarningsPerShareDiluted",
            "ifrs-full:DilutedEarningsLossPerShare",
        ]
    },

    # ==========================================================================
    # SHARES OUTSTANDING
    # ==========================================================================
    "weightedAverageSharesOutstandingBasic": {
        "standardLabel": "weightedAverageSharesOutstandingBasic",
        "displayLabel": "Weighted Avg Shares - Basic",
        "semanticType": "shares",
        "derivationPriority": "direct",
        "candidateConcepts": [
            "us-gaap:WeightedAverageNumberOfSharesOutstandingBasic",
            "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding",
        ]
    },

    # ==========================================================================
    # EBIT (COMPUTED METRIC)
    # ==========================================================================
    "ebit": {
        "standardLabel": "ebit",
        "displayLabel": "EBIT",
        "semanticType": "computed_metric",
        "derivationPriority": "compute_only",  # Always compute, never direct
        "computeAlternatives": [
            {
                "op": "add",
                "terms": ["operatingIncome"],
                "description": "Operating Income (for non-financials)"
            },
            {
                "op": "add",
                "terms": ["incomeBeforeTaxes", "interestExpense"],
                "description": "Pretax Income + Interest Expense"
            }
        ],
        "sectorRules": {
            "financials_banking": {
                "computeExpression": {
                    "op": "add",
                    "terms": ["incomeBeforeTaxes"],
                    "description": "Pretax Income (interest is operating for banks)"
                }
            }
        }
    },

    # ==========================================================================
    # EBITDA (COMPUTED METRIC)
    # ==========================================================================
    "ebitda": {
        "standardLabel": "ebitda",
        "displayLabel": "EBITDA",
        "semanticType": "computed_metric",
        "derivationPriority": "compute_only",
        "computeAlternatives": [
            {
                "op": "add",
                "terms": [
                    "ebit",
                    "depreciationAndAmortization"
                ],
                "description": "EBIT + D&A"
            }
        ]
    },

    # ==========================================================================
    # DEPRECIATION & AMORTIZATION
    # ==========================================================================
    "depreciationAndAmortization": {
        "standardLabel": "depreciationAndAmortization",
        "displayLabel": "Depreciation & Amortization",
        "semanticType": "non_cash_expense",
        "derivationPriority": "direct",
        "candidateConcepts": [
            "us-gaap:DepreciationDepletionAndAmortization",
            "us-gaap:Depreciation",
            "us-gaap:DepreciationAndAmortization",
            "ifrs-full:DepreciationAndAmortisationExpense",
        ],
        "optional": True
    },
}

# ==============================================================================
# FIELD EVALUATION ORDER
# ==============================================================================
# Order matters for computed fields - dependencies must be evaluated first

FIELD_EVALUATION_ORDER: List[str] = [
    # Level 1: Direct from XBRL (no dependencies)
    "revenue",
    "costOfRevenue",
    "researchAndDevelopmentExpense",
    "sellingGeneralAndAdministrativeExpense",
    "depreciationAndAmortization",
    "interestExpense",
    "incomeTaxExpense",
    "netIncome",
    "weightedAverageSharesOutstandingBasic",
    "earningsPerShareBasic",
    "earningsPerShareDiluted",

    # Level 2: May be computed from Level 1
    "grossProfit",  # Can use revenue - COGS
    "operatingExpenses",  # Can use R&D + SG&A
    "operatingIncome",  # Can use grossProfit - opex
    "otherIncomeExpense",

    # Level 3: May be computed from Level 2
    "incomeBeforeTaxes",  # Can use operatingIncome - interest

    # Level 4: Always computed
    "ebit",    # Always derived from operatingIncome or pretax + interest
    "ebitda",  # Always derived from EBIT + D&A
]

# ==============================================================================
# METADATA
# ==============================================================================

FIELD_SPEC_METADATA: Dict[str, Any] = {
    "version": __version__,
    "statement_type": "IncomeStatement",
    "total_fields": len(INCOME_STATEMENT_FIELDS),
    "required_fields": [
        "revenue",
        "netIncome"  # Minimum viable income statement
    ],
    "computed_fields": [
        "ebit",
        "ebitda"  # Always derived, never direct
    ],
    "sector_specific_fields": {
        "financials_banking": [
            "interestIncomeExpenseNet",
            "noninterestIncome",
            "noninterestExpense"
        ],
        "financials_insurance": [
            "premiumsEarnedNet",
            "claimsIncurred"
        ],
        "energy_utilities": [
            "regulatedOperatingRevenue"
        ],
    },
    "description": "Income statement field specifications for SEC filers across all sectors",
    "supports_ifrs": True,
    "supports_us_gaap": True,
}

# ==============================================================================
# VALIDATION UTILITIES
# ==============================================================================

def get_field_spec(field_name: str) -> Dict[str, Any]:
    """Get field specification by name."""
    return INCOME_STATEMENT_FIELDS.get(field_name, {})

def get_required_fields() -> List[str]:
    """Get list of required fields."""
    return FIELD_SPEC_METADATA["required_fields"]

def get_computed_fields() -> List[str]:
    """Get list of always-computed fields."""
    return FIELD_SPEC_METADATA["computed_fields"]

def get_field_candidates(field_name: str, sector: str = None) -> List[str]:
    """
    Get candidate XBRL concepts for a field, optionally sector-specific.

    Args:
        field_name: Field to get candidates for
        sector: Optional sector key for sector-specific candidates

    Returns:
        List of XBRL concept names (with namespace prefixes)
    """
    field_spec = get_field_spec(field_name)
    if not field_spec:
        return []

    # Check for sector-specific candidates
    if sector and "sectorRules" in field_spec:
        sector_rules = field_spec["sectorRules"].get(sector, {})
        if "candidateConcepts" in sector_rules:
            return sector_rules["candidateConcepts"]

    # Return general candidates
    return field_spec.get("candidateConcepts", [])

def validate_field_spec() -> Dict[str, Any]:
    """
    Validate field specifications for consistency.

    Returns:
        Dict with validation results
    """
    issues = []

    # Check evaluation order covers all fields
    all_fields = set(INCOME_STATEMENT_FIELDS.keys())
    ordered_fields = set(FIELD_EVALUATION_ORDER)
    missing = all_fields - ordered_fields
    if missing:
        issues.append(f"Fields not in evaluation order: {missing}")

    extra = ordered_fields - all_fields
    if extra:
        issues.append(f"Unknown fields in evaluation order: {extra}")

    # Check required fields exist
    for field in FIELD_SPEC_METADATA["required_fields"]:
        if field not in INCOME_STATEMENT_FIELDS:
            issues.append(f"Required field '{field}' not defined")

    # Check computed fields exist
    for field in FIELD_SPEC_METADATA["computed_fields"]:
        if field not in INCOME_STATEMENT_FIELDS:
            issues.append(f"Computed field '{field}' not defined")
        elif INCOME_STATEMENT_FIELDS[field].get("derivationPriority") != "compute_only":
            issues.append(f"Computed field '{field}' has wrong derivationPriority")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "total_fields": len(INCOME_STATEMENT_FIELDS),
        "evaluation_order_length": len(FIELD_EVALUATION_ORDER),
    }

# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    '__version__',
    'INCOME_STATEMENT_FIELDS',
    'FIELD_EVALUATION_ORDER',
    'FIELD_SPEC_METADATA',
    'get_field_spec',
    'get_required_fields',
    'get_computed_fields',
    'get_field_candidates',
    'validate_field_spec',
]
