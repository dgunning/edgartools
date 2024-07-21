from datetime import datetime
from typing import List, Optional, Union, Any, Dict

import pandas as pd
from pydantic import BaseModel, Field
from pydantic import field_validator

__all__ = ['Concept', 'PresentationElement', 'ConceptTableItem', 'ConceptTable', 'Context', 'DEI_CONCEPTS']


class Concept(BaseModel):
    name: str
    label: str
    value: Any
    unit: Optional[str] = None
    decimals: Optional[Union[int, str]] = None

    @property
    def periods(self):
        return list(self.value.keys())

    @property
    def values(self):
        return list(self.value.values())

    @field_validator('decimals')
    @classmethod
    def validate_decimals(cls, v: Optional[Union[int, str]]) -> Optional[Union[int, str]]:
        if v is None or v == 'INF':
            return v
        try:
            return int(v)
        except ValueError:
            raise ValueError(f"Invalid value for decimals: {v}")

    model_config = {
        "arbitrary_types_allowed": True
    }


class PresentationElement:
    def __init__(self, label: str, href: str, order: float, concept: str = None):
        self.label = label
        self.href = href
        self.order = order
        self.concept = concept if concept else label  # Use label as fallback if concept is not provided
        self.level = 0
        self.children = []


class ConceptTableItem(BaseModel):
    concept: str
    label: str
    value: Optional[Union[float, str]] = None
    is_abstract: bool = False
    children: List['ConceptTableItem'] = Field(default_factory=list)
    level: int = 0

    def add_child(self, child: 'ConceptTableItem'):
        child.level = self.level + 1
        self.children.append(child)

    def dict(self, *args, **kwargs):
        return {
            'concept': self.concept,
            'label': self.label,
            'value': self.value,
            'is_abstract': self.is_abstract,
            'level': self.level,
            'children': [child.dict(*args, **kwargs) for child in self.children]
        }


class ConceptTable(BaseModel):
    root: ConceptTableItem
    title: str

    def to_list(self):
        def flatten(item):
            result = [item]
            for child in item.children:
                result.extend(flatten(child))
            return result

        return flatten(self.root)[1:]  # Exclude the root item itself

    def to_dataframe(self):
        items = self.to_list()
        df = pd.DataFrame([
            {
                'Label': '  ' * item.level + item.label,
                'Value': item.value if not item.is_abstract else ''
            }
            for item in items
        ])
        return df


def build_concept_table(presentation_structure, facts, labels, role):
    def build_item(element, level=0):
        concept = element.href.split('#')[-1]
        label = labels.get(concept, concept)
        value = facts.get(concept, None)
        item = ConceptTableItem(concept=concept, label=label, value=value, is_abstract='Abstract' in concept,
                                level=level)

        for child in element.children:
            item.add_child(build_item(child, level + 1))

        return item

    root = presentation_structure.roles[role]
    return ConceptTable(root=build_item(root), title=role.split('/')[-1])


class Context(BaseModel):
    id: str
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    instant: Optional[datetime] = None
    dimensions: Dict[str, str] = Field(default_factory=dict)


DEI_CONCEPTS = [
    'dei:DocumentType',
    'dei:DocumentPeriodEndDate',
    'dei:AmendmentFlag',
    'dei:AmendmentDescription',
    'dei:DocumentFiscalYearFocus',
    'dei:DocumentFiscalPeriodFocus',
    'dei:EntityRegistrantName',
    'dei:EntityCentralIndexKey',
    'dei:CurrentFiscalYearEndDate',
    'dei:EntityFilerCategory',
    'dei:EntityCommonStockSharesOutstanding',
    'dei:EntityPublicFloat',
    'dei:EntityCurrentReportingStatus',
    'dei:EntityVoluntaryFilers',
    'dei:EntityWellKnownSeasonedIssuer'
]
