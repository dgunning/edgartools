from edgar import get_cik_lookup_data, Entity, Company
from tqdm import tqdm
from rich import print
import time


def view_entities():
    entities = get_cik_lookup_data().sample(200)
    for entity in tqdm(entities.itertuples(), total=len(entities)):
        try:
            entity = Entity(entity.cik, include_old_filings=False)
            print()
            print(entity)
        except Exception as e:
            print(f"Error when displaying {entity.cik} {entity.name}")
            print(e)
            raise


if __name__ == '__main__':
    view_entities()
