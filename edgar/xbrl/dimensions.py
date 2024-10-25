from functools import cached_property
from typing import Union, List

import pandas as pd
from rich import box
from rich.panel import Panel
from rich.table import Table

from edgar.richtools import repr_rich

__all__ = ['Member', 'Axis', 'Dimensions']

class Member:
    def __init__(self, concept: str, dimension: str, value: str, xbrl_instance):
        self.concept = concept
        self.dimension = dimension
        self.value = value
        self._xbrl_instance = xbrl_instance

    @cached_property
    def facts(self):
        return self._xbrl_instance.query_facts(concept=self.concept, dimensions={self.dimension: self.value})

    def __repr__(self):
        return f"Member(concept='{self.concept}', dimension='{self.dimension}', value='{self.value}')"

class Axis:
    def __init__(self, name: str, xbrl_instance):
        self.name = name
        self._xbrl_instance = xbrl_instance

    @cached_property
    def facts(self):
        return self._xbrl_instance.query_facts(axis=self.name)

    def list_members(self) -> List[str]:
        return self.facts[self.name].drop_duplicates().tolist()

    def __len__(self):
        return len(self.facts)

    def __rich__(self):
        table = Table(title=f"Axis: {self.name}", show_header=True, header_style="bold magenta", box=box.SIMPLE)
        table.add_column("Values", style="dim")
        for value in self.facts:
            table.add_row(value)
        panel = Panel(table, box=box.ROUNDED)
        return panel

    def __repr__(self):
        return repr_rich(self.__rich__())

class Dimensions:
    def __init__(self, xbrl_instance):
        self._xbrl_instance = xbrl_instance
        self._dimension_values = None

    @cached_property
    def axes(self):
        return [col for col in self._xbrl_instance.facts.index.names if col != 'concept']

    @cached_property
    def items(self) -> pd.DataFrame:
        """
        Returns a DataFrame with columns [concept, axis, axis_value] showing which concepts
        have dimensional values and what those dimensions are.
        """
        # Get index names that are not 'concept'
        axes = [name for name in self._xbrl_instance.facts.index.names if name != 'concept']

        # Create a list to store the dimensional data
        dimensional_data = []

        # Iterate through the MultiIndex
        for idx in self._xbrl_instance.facts.index:
            concept = idx[0]  # First level is always concept
            for axis_name in axes:
                member = idx[self._xbrl_instance.facts.index.names.index(axis_name)]
                if pd.notna(member):  # Only include non-null dimensional values
                    dimensional_data.append({
                        'concept': concept,
                        'axis': axis_name,
                        'member': member
                    })

        # Create DataFrame and drop duplicates
        df = pd.DataFrame(dimensional_data).drop_duplicates()
        return df.sort_values(['concept', 'axis', 'member']).reset_index(drop=True)

    def get_axis(self, axis_name: str) -> Axis:
        if axis_name in self.axes:
            return Axis(axis_name, self._xbrl_instance)

    def __getitem__(self, key: Union[int, str]):
        if isinstance(key, int):
            if 0 <= key < len(self.items):
                row = self.items.iloc[key]
                return Member(row.concept, row.axis, row.member, self._xbrl_instance)
        elif isinstance(key, str):
            return self.get_axis(key)

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        for row in self.items.itertuples():
            yield Member(row.concept, row.axis, row.member, self._xbrl_instance)

    def __rich__(self):
        table = Table(title="Available Dimensions and Values", show_header=True, header_style="bold magenta", box=box.SIMPLE)
        table.add_column("", style="dim")
        table.add_column("Concept")
        table.add_column("Axis")
        table.add_column("Member")
        for index, row in enumerate(self.items.itertuples()):
            table.add_row(str(index), row.concept, row.axis, row.member)
        return table

    def __repr__(self):
        return repr_rich(self.__rich__())

