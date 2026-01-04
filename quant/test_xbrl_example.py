from quant.xbrl_standardize.extractors.ic import Evaluator
import json
from pathlib import Path

# Load income statement schema
schema_path = Path('xbrl_standardize/schemas/income-statement.json')
with open(schema_path) as f:
    schema = json.load(f)

# Extract standardized fields from raw XBRL facts
# Note: Concepts must include the taxonomy prefix (us-gaap:)
facts = {
    'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax': 100000000,
    'us-gaap:NetIncomeLoss': 20000000,
    'us-gaap:EarningsPerShareBasic': 2.50
}

evaluator = Evaluator(mapping=schema, facts=facts)
result = evaluator.standardize()
print(result['revenue'])  # 100000000
print(result['netIncome'])  # 20000000
