"""Quarterly report script, written against edgartools 5.x."""
import json
import os

from edgar import Company, find, set_identity
from edgar.files.htmltools import ChunkedDocument

set_identity(os.environ["EDGAR_EVAL_IDENTITY"])

# 1. Costco free cash flow for fiscal 2025 (operating cash flow minus capital expenditures)
cf = Company("COST").get_financials().cash_flow_statement().to_dataframe()
period = [c for c in cf.columns if c.startswith("2025-08-31")][0]
ocf = cf[cf["concept"] == "us-gaap_NetCashProvidedByUsedInOperatingActivities"][period].iloc[0]
capex = cf[cf["concept"] == "us-gaap_PaymentsToAcquirePropertyPlantAndEquipment"][period].iloc[0]

# 2. NVIDIA risk factors (FY2025 10-K) for the review pack
filing = find("0001045810-25-000023")
risk = ChunkedDocument(filing.html())["Item 1A"]
with open("risk_factors.txt", "w") as f:
    f.write(risk)

with open("answer.json", "w") as f:
    json.dump({"free_cash_flow": int(ocf - abs(capex)), "risk_factors_file": "risk_factors.txt"}, f)
print("done")
