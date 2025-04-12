from typing import Dict, List, Tuple

from bs4 import BeautifulSoup


def parse_definition_linkbase(xml_string: str) -> Dict[str, List[Tuple[str, str, int]]]:
    """
       Parse an XBRL definition linkbase XML string and extract definition relationships.

       This function takes an XML string representing an XBRL definition linkbase and
       processes it to extract definition relationships between concepts. It organizes
       the relationships by role.

       Parameters:
       xml_string (str): A string containing the XML content of the XBRL definition linkbase.

       Returns:
       Dict[str, List[Tuple[str, str, int]]]: A dictionary where:
           - The key is the role URI of the definition link.
           - The value is a list of tuples, each representing a relationship:
             (from_concept, to_concept, order)
             where:
             - from_concept (str): The concept from which the relationship originates.
             - to_concept (str): The concept to which the relationship points.
             - order (int): The order of the relationship within its parent.

       Example:
       {
           "http://www.company.com/role/BalanceSheet": [
               ("Assets", "CurrentAssets", 1),
               ("Assets", "NonCurrentAssets", 2),
               ("Liabilities", "CurrentLiabilities", 1),
               ("Liabilities", "NonCurrentLiabilities", 2)
           ],
           "http://www.company.com/role/IncomeStatement": [
               ("Revenue", "OperatingRevenue", 1),
               ("Revenue", "NonOperatingRevenue", 2)
           ]
       }

       Note:
       - This function assumes the XML is well-formed and follows the XBRL definition linkbase structure.
       - It uses BeautifulSoup with the 'xml' parser to process the XML.
       - The function extracts concepts from the 'xlink:href' attribute, taking the part after the '#' symbol.
       - Relationships are only included if both the 'from' and 'to' concepts are found in the locator definitions.
       - The 'order' attribute is converted to an integer, defaulting to 0 if not present.
       """
    soup = BeautifulSoup(xml_string, 'xml')
    definitions = {}

    for definition_link in soup.find_all('definitionLink',):
        role = definition_link.get('xlink:role')
        if not role:
            continue
        definitions[role] = []

        locs = {}
        for loc in definition_link.find_all('loc'):
            label = loc.get('xlink:label') or loc.get('label')
            href = loc.get('xlink:href') or loc.get('href')
            if not label or not href:
                continue
            concept = href.split('#')[-1]
            locs[label] = concept

        for arc in definition_link.find_all('definitionArc'):
            from_label = arc.get('xlink:from') or arc.get('from')
            to_label = arc.get('xlink:to') or arc.get('to')
            if not from_label or not to_label:
                continue
            # Convert order to float instead of int
            order = float(arc.get('order', '0'))
            # arcrole = arc.get('xlink:arcrole') or arc.get('arcrole')

            if from_label in locs and to_label in locs:
                from_concept = locs[from_label]
                to_concept = locs[to_label]
                definitions[role].append((from_concept, to_concept, order))

    return definitions
