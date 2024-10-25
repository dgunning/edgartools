from typing import Dict, List

from bs4 import BeautifulSoup
from pydantic import BaseModel

class Calculation(BaseModel):
    from_concept: str
    to_concept: str
    weight: float
    order: str

class CalculationLinkbase:

    def __init__(self,
                 calculations_by_role:Dict[str, List[Calculation]],
                 concept_relationships:Dict[str,str],
                 concept_calculations:Dict[str, Calculation]):
        self.calculations_by_role = calculations_by_role
        self.concept_relationships = concept_relationships
        self.concept_calculations = concept_calculations


    def get_calculations_for_role(self, role:str):
        return self.calculations_by_role.get(role, [])

    def get_calculation(self, concept:str):
        return self.concept_calculations.get(concept.replace(':','_',1), None)

    @classmethod
    def parse(cls, calculation_xml:str):
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
        soup = BeautifulSoup(calculation_xml, 'xml')
        calculations_by_role:Dict[str, List[Calculation]] = dict()
        concept_relationships:Dict[str,str] = dict()
        concept_calculations:Dict[str, Calculation] = dict()

        for calculation_link in soup.find_all('calculationLink'):
            role = calculation_link.get('xlink:role')
            if not role:
                continue
            calculations_by_role[role] = []

            locs = {}
            for loc in calculation_link.find_all('loc'):
                label = loc.get('xlink:label') or loc.get('label')
                href = loc.get('xlink:href') or loc.get('href')
                if not label or not href:
                    continue
                concept = href.split('#')[-1]
                locs[label] = concept

            for arc in calculation_link.find_all(['calculationArc', 'link:calculationArc']):
                from_concept = arc.get('xlink:from') or arc.get('from')
                to_concept = arc.get('xlink:to') or arc.get('to')
                weight = arc.get('weight')
                order = arc.get('order')

                if not from_concept or not to_concept or weight is None or order is None:
                    continue

                weight = float(weight)

                # Add a counter to see if we have duplicate to_concepts
                if from_concept in locs and to_concept in locs:
                    from_concept = locs[from_concept]
                    to_concept = locs[to_concept]

                    calculation = Calculation(from_concept=from_concept, to_concept=to_concept, weight=weight, order=order)
                    # Calculations by role
                    calculations_by_role[role].append(calculation)
                    # Add the relationship
                    concept_relationships[to_concept] = from_concept
                    # Concept to calculation
                    concept_calculations[to_concept] = calculation

        return cls(calculations_by_role, concept_relationships, concept_calculations)
