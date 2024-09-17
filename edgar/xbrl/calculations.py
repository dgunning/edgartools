from typing import Dict, List, Tuple

from bs4 import BeautifulSoup
from pydantic import BaseModel


class Calculation(BaseModel):
    from_concept: str
    to_concept: str
    weight: float
    order: str


def parse_calculation_linkbase(xml_string: str) -> Dict[str, List[Tuple[str, str, float, int]]]:
    """
    This parser does the following:

    It uses BeautifulSoup to parse the XML content.
    It iterates through all calculationLink elements in the file.
    For each calculationLink, it extracts the role and creates a list to store the calculation relationships for that role.
    It first processes all loc elements to create a mapping from labels to concepts.
    Then it processes all calculationArc elements, which define the calculation relationships between concepts.
    For each arc, it extracts the from and to concepts, the weight, and the order, and stores this information in the list for the current role.
    The result is a dictionary where keys are roles and values are lists of tuples. Each tuple contains (from_concept, to_concept, weight, order).

The resulting calculation_data dictionary will have a structure like this:
    {
    "http://www.apple.com/role/CONSOLIDATEDSTATEMENTSOFOPERATIONS": [
        ("us-gaap_OperatingIncomeLoss", "us-gaap_GrossProfit", 1.0, 1),
        ("us-gaap_OperatingIncomeLoss", "us-gaap_OperatingExpenses", -1.0, 2),
        ("us-gaap_OperatingExpenses", "us-gaap_ResearchAndDevelopmentExpense", 1.0, 1),
        ("us-gaap_OperatingExpenses", "us-gaap_SellingGeneralAndAdministrativeExpense", 1.0, 2),
        # ... other relationships ...
    ],
    # ... other roles ...
}
    """
    soup = BeautifulSoup(xml_string, 'xml')
    calculations = {}

    for calculation_link in soup.find_all('calculationLink'):
        role = calculation_link.get('xlink:role')
        if not role:
            continue
        calculations[role] = []

        locs = {}
        for loc in calculation_link.find_all('loc'):
            label = loc.get('xlink:label') or loc.get('label')
            href = loc.get('xlink:href') or loc.get('href')
            if not label or not href:
                continue
            concept = href.split('#')[-1]
            locs[label] = concept

        for arc in calculation_link.find_all(['calculationArc', 'link:calculationArc']):
            from_label = arc.get('xlink:from') or arc.get('from')
            to_label = arc.get('xlink:to') or arc.get('to')
            weight = arc.get('weight')
            order = arc.get('order')

            if not from_label or not to_label or weight is None or order is None:
                continue

            weight = float(weight)

            if from_label in locs and to_label in locs:
                from_concept = locs[from_label]
                to_concept = locs[to_label]
                calculations[role].append(
                    Calculation(from_concept=from_concept, to_concept=to_concept, weight=weight, order=order))

    return calculations
