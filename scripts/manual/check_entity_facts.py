from edgar.entity import EntityFacts
from edgar.entity.query import FactQuery
from edgar.entity.parser import EntityFactsParser, FinancialFact
from edgar.entity.entity_facts import load_company_facts_from_local
from tqdm.auto import tqdm
from edgar import *
import pandas as pd
pd.options.display.max_rows = 1000

def load_entity_facts(cik: str) -> EntityFacts:
    """
    Load entity facts for a given CIK.

    Args:
        cik: The company CIK

    Returns:
        EntityFacts: The parsed entity facts
    """
    for ticker in ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NFLX", "NVDA", "BRK.A", "V"]:
        print(f"Loading entity facts for {ticker}...")
        c = Company(ticker)
        company_facts_json = load_company_facts_from_local(c.cik)

        entity_facts = EntityFactsParser.parse_company_facts(company_facts_json)
        print(f"Entity facts for {ticker} loaded successfully.")
        print(entity_facts.balance_sheet())
        print(entity_facts.cash_flow())
        print(entity_facts.income_statement())



if __name__ == '__main__':
    load_entity_facts(1640147)