from typing import Dict
from bs4 import BeautifulSoup

__all__ = [
    'parse_label_linkbase'
]


def remove_namespace(s: str) -> str:
    return s.split('_', 1)[-1] if '_' in s else s


def parse_label_linkbase(xml_string: str) -> Dict[str, Dict[str, str]]:
    """
        Parse an XBRL label linkbase XML string and extract label information.

        This function takes an XML string representing an XBRL label linkbase and
        processes it to extract label information for each concept. It organizes
        the labels by concept and role.

        Parameters:
        xml_string (str): A string containing the XML content of the XBRL label linkbase.

        Returns:
        Dict[str, Dict[str, str]]: A nested dictionary where:
            - The outer key is the concept name (without the 'lab_' prefix).
            - The inner key is the role of the label (last part of the role URI).
            - The value is the text content of the label.

        Example:
        {
            'Assets': {
                'label': 'Assets',
                'terseLabel': 'Assets',
                'totalLabel': 'Total Assets'
            },
            'Liabilities': {
                'label': 'Liabilities',
                'terseLabel': 'Liabilities'
            }
        }

        Note:
        - This function assumes the XML is well-formed and follows the XBRL label linkbase structure.
        - It uses BeautifulSoup with the 'xml' parser to process the XML.
        - The function removes the 'lab_' prefix from concept names and extracts only the last part of the role URI.
        """
    soup = BeautifulSoup(xml_string, 'xml')
    labels = {}
    label_arcs = {}

    # First, parse all labels
    for label in soup.find_all('label'):
        label_id = label.get('xlink:label')
        role = label.get('xlink:role')
        if role:
            role = role.split('/')[-1]
        text = label.text
        label_id_no_ns = remove_namespace(label_id)
        if label_id_no_ns not in labels:
            labels[label_id_no_ns] = {}
        labels[label_id_no_ns][role] = text

    # Then, parse label arcs
    for arc in soup.find_all('labelArc'):
        from_concept = arc.get('xlink:from')
        to_label = arc.get('xlink:to')
        to_label_no_ns = remove_namespace(to_label)
        label_arcs[from_concept] = to_label_no_ns

    # Combine the information
    combined_labels = {}
    for concept, label_id in label_arcs.items():
        concept_no_ns = remove_namespace(concept)
        if label_id in labels:
            combined_labels[concept] = labels[label_id]
        elif concept_no_ns in labels:  # Direct matching for cases like AAPL
            combined_labels[concept_no_ns] = labels[concept_no_ns]

    # Add any labels not referenced by arcs (for cases like AAPL)
    for label_id, label_info in labels.items():
        if label_id not in combined_labels:
            combined_labels[label_id] = label_info

    return combined_labels


