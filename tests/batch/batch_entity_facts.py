from edgar.entity import EntityFacts
from edgar.entity.parser import EntityFactsParser
from edgar.reference.tickers import get_company_tickers
from edgar.entity.entity_facts import download_company_facts_from_sec, load_company_facts_from_local, NoCompanyFactsFound
from tqdm.auto import tqdm
from edgar import *


use_local_storage()

def sample_entity_facts(sample=100):
    company_tickers = get_company_tickers().sample(sample)
    for t in tqdm(company_tickers.itertuples(), desc="Processing company tickers"):
        c = Company(t.cik)
        try:
            company_facts_json = load_company_facts_from_local(c.cik)
            entity_facts = EntityFactsParser.parse_company_facts(company_facts_json)
            print(entity_facts)
            if not(entity_facts):
                assert len(company_facts_json.get('facts', [])) == 0, "Expected no facts for CIK: {}".format(c.cik)
            else:
                income_statement = entity_facts.income_statement()
                print(income_statement)
                balance_sheet = entity_facts.balance_sheet()
        except NoCompanyFactsFound:
            print("No company facts found for CIK:", c.cik)
        except Exception as e:
            print(f"Error processing CIK {c.cik}: {e}")
            raise


def load_entity_facts(cik: str) -> EntityFacts:
    """
    Load entity facts for a given CIK.

    Args:
        cik: The company CIK

    Returns:
        EntityFacts: The parsed entity facts
    """
    company_facts_json = load_company_facts_from_local(cik)
    if not company_facts_json:
        raise NoCompanyFactsFound(f"No facts found for CIK {cik}")

    return EntityFactsParser.parse_company_facts(company_facts_json)



if __name__ == '__main__':
    sample_entity_facts(1000)
    #load_entity_facts(5094)
    # entity_facts = EntityFacts('0000320193')  # Apple Inc.
    # print(entity_facts)
    # print(entity_facts.get_fact('us-gaap:AssetsCurrent'))
    # print(entity_facts.get_fact('us-gaap:LiabilitiesCurrent'))
    # print(entity_facts.get_fact('us-gaap:StockholdersEquity'))
    # print(entity_facts.get_fact('us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax'))