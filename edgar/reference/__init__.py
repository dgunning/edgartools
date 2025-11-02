
from edgar.reference.company_subsets import (
    # Classes and Enums
    CompanySubset,
    MarketCapTier,
    PopularityTier,
    # Core Functions
    get_all_companies,
    get_companies_by_exchanges,
    get_popular_companies,
    # Industry and State Filtering (Comprehensive Mode)
    get_companies_by_industry,
    get_companies_by_state,
    # Sampling and Filtering
    get_random_sample,
    get_stratified_sample,
    get_top_companies_by_metric,
    filter_companies,
    exclude_companies,
    # Set Operations
    combine_company_sets,
    intersect_company_sets,
    # Convenience Functions - General
    get_faang_companies,
    get_tech_giants,
    get_dow_jones_sample,
    # Convenience Functions - Industry Specific
    get_pharmaceutical_companies,
    get_biotechnology_companies,
    get_software_companies,
    get_semiconductor_companies,
    get_banking_companies,
    get_investment_companies,
    get_insurance_companies,
    get_real_estate_companies,
    get_oil_gas_companies,
    get_retail_companies,
)
from edgar.reference.company_dataset import (
    get_company_dataset,
    build_company_dataset_parquet,
    build_company_dataset_duckdb,
    is_individual_from_json,
    to_duckdb,
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







