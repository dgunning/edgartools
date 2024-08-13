from typing import Dict, Any
from typing import Optional
from typing import Union, Tuple, List

import pandas as pd
from rich.table import Table

from edgar.richtools import repr_rich

__all__ = ['DimensionValue', 'Dimension', 'Dimensions', 'DimensionMetadata', 'DimensionAccessor']


class DimensionValue:
    def __init__(self, dimension: str, value: str, xbrl_instance):
        self.dimension = dimension
        self.value = value
        self._xbrl_instance = xbrl_instance

    def get_facts(self):
        return self._xbrl_instance.query_facts(dimensions={self.dimension: self.value})

    def __repr__(self):
        return f"DimensionValue(dimension='{self.dimension}', value='{self.value}')"


class Dimension:
    def __init__(self, name: str, xbrl_instance):
        self.name = name
        self._xbrl_instance = xbrl_instance

    @property
    def values(self):
        return self._xbrl_instance.facts['dimensions'].apply(
            lambda x: x.get(self.name) if isinstance(x, dict) else None
        ).dropna().unique().tolist()

    def __getitem__(self, value):
        if value in self.values:
            return DimensionValue(self.name, value, self._xbrl_instance)
        raise KeyError(f"Value '{value}' not found in dimension '{self.name}'")

    def get_facts(self, value=None):
        if value is None:
            # Combine facts for all values of this dimension
            all_facts = pd.concat([self._xbrl_instance.query_facts(dimensions={self.name: val})
                                   for val in self.values])

            # Identify columns that uniquely define a fact (excluding 'dimensions')
            id_columns = [col for col in all_facts.columns if col != 'dimensions']

            # Drop duplicates based on these identifying columns
            return all_facts.drop_duplicates(subset=id_columns)

        elif value in self.values:
            return self._xbrl_instance.query_facts(dimensions={self.name: value})
        else:
            raise ValueError(f"Value '{value}' not found in dimension '{self.name}'")

    def __repr__(self):
        return f"Dimension(name='{self.name}', values={self.values})"


class Dimensions:
    def __init__(self, xbrl_instance):
        self._xbrl_instance = xbrl_instance
        self._dimension_values = None

    @property
    def _dimensions(self):
        if self._dimension_values is None:
            self._dimension_values = []
            for _, dims in self._xbrl_instance.facts['dimensions'].items():
                if isinstance(dims, dict):
                    for dim, value in dims.items():
                        self._dimension_values.append((dim, value))
            self._dimension_values = sorted(set(self._dimension_values))
        return self._dimension_values

    def __getitem__(self, key: Union[int, str, Tuple[str, str], List[Tuple[str, str]]]):
        if isinstance(key, int):
            if 0 <= key < len(self._dimensions):
                dim, value = self._dimensions[key]
                return DimensionValue(dim, value, self._xbrl_instance)
            else:
                raise IndexError("DimensionValue index out of range")
        elif isinstance(key, str):
            return Dimension(key, self._xbrl_instance)
        elif isinstance(key, tuple) and len(key) == 2:
            dim, value = key
            if (dim, value) in self._dimensions:
                return DimensionValue(dim, value, self._xbrl_instance)
            raise KeyError(f"DimensionValue {key} not found")
        elif isinstance(key, list):
            return [self[k] for k in key if isinstance(k, tuple) and len(k) == 2]
        raise KeyError(f"Invalid key type: {type(key)}")

    def __len__(self):
        return len(self._dimensions)

    def __iter__(self):
        for dim, value in self._dimensions:
            yield DimensionValue(dim, value, self._xbrl_instance)

    def __rich__(self):
        table = Table(title="Available Dimensions and Values", show_header=True, header_style="bold magenta")
        table.add_column("Index", style="dim", width=10)
        table.add_column("Dimension", style="dim", width=40)
        table.add_column("Value", style="dim")

        for index, (dim, value) in enumerate(self._dimensions):
            table.add_row(str(index), dim, value)

        return table

    def __repr__(self):
        return repr_rich(self.__rich__())


class DimensionMetadata:
    def __init__(self):
        self.dimensions = {}

    def add_dimension(self, name: str, description: str, data_type: str):
        self.dimensions[name] = {'description': description, 'data_type': data_type}

    def get_dimension_info(self, name: str) -> Optional[Dict[str, str]]:
        return self.dimensions.get(name)

    def get_dimension_hierarchy(self, facts: pd.DataFrame, top_level_dimension: str) -> Dict:
        hierarchy = {}
        for _, row in facts.iterrows():
            if top_level_dimension in row['dimensions']:
                current = hierarchy
                for dim, value in row['dimensions'].items():
                    if dim not in current:
                        current[dim] = {}
                    current = current[dim]
                    if value not in current:
                        current[value] = {}
                    current = current[value]
        return hierarchy


@pd.api.extensions.register_dataframe_accessor("dim")
class DimensionAccessor:
    def __init__(self, pandas_obj):
        self._obj = pandas_obj

    def _check_dimensions_column(self):
        if 'dimensions' not in self._obj.columns:
            raise AttributeError("This DataFrame does not have a 'dimensions' column.")

    def get(self, dimension):
        self._check_dimensions_column()
        return self._obj[self._obj['dimensions'].apply(lambda x: dimension in x if isinstance(x, dict) else False)]

    def value(self, dimension, value):
        self._check_dimensions_column()
        return self._obj[
            self._obj['dimensions'].apply(lambda x: x.get(dimension) == value if isinstance(x, dict) else False)]

    def match(self, dimensions: Dict[str, Any]):
        """
        Match rows where all specified dimensions match the given values.

        Args:
            dimensions (Dict[str, Any]): A dictionary of dimension names and their values to match.

        Returns:
            pd.DataFrame: A DataFrame with rows matching all specified dimensions.
        """
        self._check_dimensions_column()
        return self._obj[self._obj['dimensions'].apply(
            lambda x: all(x.get(k) == v for k, v in dimensions.items()) if isinstance(x, dict) else False
        )]

    def has_dimensions(self):
        return 'dimensions' in self._obj.columns

    def list_dimensions(self):
        """
        List all unique dimensions present in the DataFrame.

        Returns:
            set: A set of all unique dimension names.
        """
        self._check_dimensions_column()
        return set().union(*self._obj['dimensions'].apply(lambda x: x.keys() if isinstance(x, dict) else set()))

    def get_values(self, dimension):
        """
        Get all unique values for a specific dimension.

        Args:
            dimension (str): The name of the dimension.

        Returns:
            set: A set of all unique values for the specified dimension.
        """
        self._check_dimensions_column()
        return set(
            self._obj['dimensions'].apply(lambda x: x.get(dimension) if isinstance(x, dict) else None).dropna())
