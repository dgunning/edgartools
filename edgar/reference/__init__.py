
from edgar.reference.company_dataset import (
    build_company_dataset_duckdb,
    build_company_dataset_parquet,
    get_company_dataset,
    is_individual_from_json,
    to_duckdb,
)
from edgar.reference.company_subsets import (
    # Classes and Enums
    CompanySubset,
    MarketCapTier,
    PopularityTier,
    # Set Operations
    combine_company_sets,
    exclude_companies,
    filter_companies,
    # Core Functions
    get_all_companies,
    get_banking_companies,
    get_biotechnology_companies,
    get_companies_by_exchanges,
    # Industry and State Filtering (Comprehensive Mode)
    get_companies_by_industry,
    get_companies_by_state,
    get_dow_jones_sample,
    # Convenience Functions - General
    get_faang_companies,
    get_insurance_companies,
    get_investment_companies,
    get_oil_gas_companies,
    # Convenience Functions - Industry Specific
    get_pharmaceutical_companies,
    get_popular_companies,
    # Sampling and Filtering
    get_random_sample,
    get_real_estate_companies,
    get_retail_companies,
    get_semiconductor_companies,
    get_software_companies,
    get_stratified_sample,
    get_tech_giants,
    get_top_companies_by_metric,
    intersect_company_sets,
)
from edgar.reference.forms import describe_form
from edgar.reference.tickers import cusip_ticker_mapping, get_icon_from_ticker, get_ticker_from_cusip

# A dict of state abbreviations and their full names
states = {

    "AL": "Alabama",
    "AK": "Alaska",
    "AZ": "Arizona",
    "AR": "Arkansas",
    "CA": "California",
    "CO": "Colorado",
    "CT": "Connecticut",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "HI": "Hawaii",
    "ID": "Idaho",
    "IL": "Illinois",
    "IN": "Indiana",
    "IA": "Iowa",
    "KS": "Kansas",
    "KY": "Kentucky",
    "LA": "Louisiana",
    "ME": "Maine",
    "MD": "Maryland",
    "MA": "Massachusetts",
    "MI": "Michigan",
    "MN": "Minnesota",
    "MS": "Mississippi",
    "MO": "Missouri",
    "MT": "Montana",
    "NE": "Nebraska",
    "NV": "Nevada",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NM": "New Mexico",
    "NY": "New York",
    "NC": "North Carolina",
    "ND": "North Dakota",
    "OH": "Ohio",
    "OK": "Oklahoma",
    "OR": "Oregon",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "SD": "South Dakota",
    "TN": "Tennessee",
    "TX": "Texas",
    "UT": "Utah",
    "VT": "Vermont",
    "VA": "Virginia",
    "WA": "Washington",
    "WV": "West Virginia",
    "WI": "Wisconsin",
    "WY": "Wyoming",
}







