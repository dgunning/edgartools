"""Declared DataFrame schemas for the EntityFacts surfaces.

The rule, decided for the XBRL path in
``engineering/decisions/facts-dataframe-schema.md`` (edgartools-rsyt) and extended
here to the entity path (edgartools-7wtj): **the column set and dtypes of a
``to_dataframe()`` result are a function of the query's configuration, never of the
rows that came back.**

Narrowing a query chooses fewer rows, not a different table shape. Before this,
``pd.DataFrame(records)`` inferred both from whatever rows matched, so

* ``query().by_concept('Revenues')`` returned ``value`` as ``int64`` where the
  unfiltered query returned ``float64`` — measured on 16 of 36 narrowing queries
  across 12 companies — changing division semantics and the null sentinel for a
  consumer who only filtered differently, and
* a query matching nothing returned a bare frame with **zero columns**, so
  ``df['value']`` raised ``KeyError`` instead of yielding an empty typed column.
  A real query reaches this: Main Street Capital reports no ``Revenues`` concept.

Dtypes below are applied to columns that had to be materialized, plus the names
in ``PINNED``, so a materialized column is indistinguishable from a populated one.

``value`` was pinned in 5.x. The unfiltered surface was already ``float64``/``NaN``
on all 12 companies measured (a Python ``float`` in 100% of 344,769 rows), so the
pin made narrowed queries match the default. ``fiscal_year``, ``is_audited`` and
``is_estimated`` were pinned in 6.0 (edgartools-7wtj.1) as nullable ``Int64`` and
``boolean``. Their 5.x dtypes, ``int64`` and ``bool``, cannot hold a null, so a
column that no returned row populated came back as ``float64`` or ``boolean``
where a populated one came back ``int64`` or ``bool``.
"""

from typing import Any, Dict

from edgar.datatools import STR_DTYPE

__all__ = ['FACT_QUERY_COLUMNS', 'PINNED', 'ENTITY_FACTS_CORE',
           'ENTITY_FACTS_PIT', 'ENTITY_FACTS_METADATA', 'entity_facts_columns']

# An empty result carries these same dtypes, so it is dtype-identical to a
# populated one.
#
# `scale`, the date columns and `filing_date` are `object` because that is what
# they hold today: Optional[int] and datetime.date are not pandas-native here.

# edgar/entity/query.py :: FactQuery.to_dataframe(), in emission order.
FACT_QUERY_COLUMNS: Dict[str, Any] = {
    'concept': STR_DTYPE,
    'label': STR_DTYPE,
    'value': 'float64',
    'numeric_value': 'float64',
    'unit': STR_DTYPE,
    'scale': 'object',
    'period_start': 'object',
    'period_end': 'object',
    'period_type': STR_DTYPE,
    'fiscal_year': 'Int64',
    'fiscal_period': STR_DTYPE,
    'filing_date': 'object',
    'form_type': STR_DTYPE,
    'accession': STR_DTYPE,
    'data_quality': STR_DTYPE,
    'confidence_score': 'float64',
    'is_audited': 'boolean',
    'is_estimated': 'boolean',
    'statement_type': STR_DTYPE,
}

# Applied to populated columns too, not only materialized ones.
PINNED = frozenset({'value', 'fiscal_year', 'is_audited', 'is_estimated'})

# edgar/entity/entity_facts.py :: EntityFacts.to_dataframe(), whose column set is
# gated by its own arguments — the same "configuration determines the shape" rule.
ENTITY_FACTS_CORE: Dict[str, Any] = {
    'concept': STR_DTYPE,
    'label': STR_DTYPE,
    'value': 'float64',
    'numeric_value': 'float64',
    'unit': STR_DTYPE,
    'period_type': STR_DTYPE,
    'period_start': 'object',
    'period_end': 'object',
    'fiscal_year': 'Int64',
    'fiscal_period': STR_DTYPE,
}

ENTITY_FACTS_PIT: Dict[str, Any] = {
    'filing_date': 'object',
    'form_type': STR_DTYPE,
}

ENTITY_FACTS_METADATA: Dict[str, Any] = {
    'accession': STR_DTYPE,
    'filing_date': 'object',
    'form_type': STR_DTYPE,
    'statement_type': STR_DTYPE,
    'taxonomy': STR_DTYPE,
    'scale': 'object',
    'data_quality': STR_DTYPE,
    'is_audited': 'boolean',
    'confidence_score': 'float64',
}


def entity_facts_columns(pit_mode: bool, include_metadata: bool) -> Dict[str, Any]:
    """The declared columns for one EntityFacts.to_dataframe() configuration.

    Order mirrors the record dict the method builds. `filing_date` and `form_type`
    appear in both the PIT and metadata blocks; a dict keeps a repeated key in its
    first position, so with both flags set they stay where PIT put them.
    """
    declared: Dict[str, Any] = dict(ENTITY_FACTS_CORE)
    if pit_mode:
        declared.update(ENTITY_FACTS_PIT)
    if include_metadata:
        for name, dtype in ENTITY_FACTS_METADATA.items():
            declared.setdefault(name, dtype)
    return declared
