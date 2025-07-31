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
    c = Company("TSLA")
    company_facts_json = load_company_facts_from_local(c.cik)

    entity_facts = EntityFactsParser.parse_company_facts(company_facts_json)
    print(entity_facts)
    print(entity_facts.income_statement())
    print(entity_facts.dei_facts())
    fact:FinancialFact = entity_facts._facts[-1]
    fact_query:FactQuery = entity_facts.query().by_concept("GrossProfit")
    print(fact_query.to_dataframe('concept', 'label',  'period_start', 'period_end', 'value','fiscal_year', 'fiscal_period', 'filing_date',))



if __name__ == '__main__':
    load_entity_facts(1640147)