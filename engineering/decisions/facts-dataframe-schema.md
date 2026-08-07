# `FactsQuery.to_dataframe()` declares its schema

**Status**: Decided (2026-08-03) · **Bead**: `edgartools-rsyt` · **Context**: [GH #929](https://github.com/dgunning/edgartools/issues/929)
**Supersedes nothing.** Implementation split across 5.x and 6.0 — see [Shipping](#shipping).

## The problem

A downstream consumer reported that an upgrade changed the null sentinel of the
`decimals` column, silently disabling a filter of theirs. We answered that with a
commitment to schema-diff every performance change during 6.0. Capturing the
baseline for that gate then turned up something worse than the reported
incident: **the schema of this method already varies between two queries against
the same XBRL instance in a single version, with no release involved.** A
consumer's filter can break by filtering differently.

Gating a surface that moves on its own is theatre, so this has to be settled
before the gate means anything.

## What was measured

Foot Locker FY2024 10-K (`0001437749-25-009620`), edgartools 5.45.1, one
`XBRL` instance, several queries. Four independent mechanisms, not one:

| mechanism | site | evidence |
|---|---|---|
| dtype inferred per call | `facts.py:876` — `pd.DataFrame(results)` | `preferred_sign` flips float64 → int64 on **4 of 4** narrowing queries, because narrowing removed the rows that had nulls |
| all-null columns deleted | `facts.py:904` — `dropna(axis=1, how='all')` | `.limit(5)` drops `balance`, `currency`, `decimals`, `unit_ref` and `weight` — not because they don't apply, but because those five rows happened to be null |
| keys added conditionally | `facts.py:1044+` — `_build_facts` | instant-only results have no `period_start`/`period_end` column at all; balance-sheet results have no `fiscal_period`. An absent column where a null belongs |
| empty result | `facts.py:873` | bare `pd.DataFrame()` with zero columns, so `df['decimals']` raises `KeyError` instead of yielding an empty typed column |

Two findings make this cheaper to fix than it first appears:

- **The unfiltered surface is already stable across filings.** All ten XBRL
  entries in the perf corpus produce the identical 24 columns. Declaring the
  schema codifies what the bare query already does rather than inventing a new
  contract.
- **Only the per-axis dimension columns are genuinely open-ended.** With
  `include_dimensions=True` you get five fixed-name columns plus one
  `dim_<axis>` per axis present in that filing. The five can be declared; the
  axis tail is filing-specific and must not be.

## The decision

**The column set and dtypes are a function of the query's *configuration*, never
of the rows that came back.**

That single rule resolves all four mechanisms. A caller who writes
`.by_statement_type("IncomeStatement")` chose a narrower row set, not a
different table shape, and nothing about which rows matched may add a column,
remove one, or change a dtype.

Implementation is a module-level `name → dtype` spec applied once at the end of
`to_dataframe()`:

```python
df = df.reindex(columns=active_spec).astype(active_spec)
```

`reindex` materializes declared columns the rows never populated; `astype` pins
the dtype regardless of what was inferred. Both replace behaviour that is
currently emergent, and the `dropna(axis=1, how='all')` call is deleted rather
than made conditional — it is the mechanism, not a safeguard.

One constraint the spec has to respect, found while implementing the 5.x half:
the declared string dtype must be **probed at import** (`pd.Series([""]).dtype`),
never written as the literal `'str'`. The pandas default changed in 3.0 from
`object` to `str` while the supported floor is still 2.0, and `astype('str')`
turns a null into the *string* `"nan"` — silently converting missing data into
data, on the floor version, in the method whose whole purpose here is to stop
nulls from changing shape.

### The declared core (24 columns)

Order is today's order, so this change alters presence and dtype only.

| column | dtype | column | dtype |
|---|---|---|---|
| `concept` | `str` | `decimals` | `str` |
| `label` | `str` | `statement_type` | `str` |
| `balance` | `str` | `statement_name` | `str` |
| `preferred_sign` | **`Int64`** | `fact_id` | `str` |
| `weight` | `float64` | `context_ref` | `str` |
| `value` | `str` | `unit_ref` | `str` |
| `numeric_value` | `float64` | `currency` | `str` |
| `period_key` | `str` | `period_type` | `str` |
| `period_start` | `str` | `entity_identifier` | `str` |
| `period_end` | `str` | `entity_scheme` | `str` |
| `period_instant` | `str` | `fiscal_period` | `str` |
| `is_dimensioned` | **`boolean`** | `fiscal_year` | **`Int64`** |

Three dtype choices carry the reasoning:

- **`preferred_sign` and `fiscal_year` become nullable `Int64`.** Both are
  integers that can be absent, and float64 was only ever an artifact of NaN
  requiring a float container. `Int64` lets them be integers *and* nullable,
  which is what they actually are.
- **`numeric_value` stays `float64` with `NaN`.** Promoting it to `Float64`
  would move its sentinel to `pd.NA` and break every consumer calling
  `np.isnan`, which is a larger break than the one being fixed and buys nothing:
  it is a genuine float either way.
- **`is_dimensioned` is nullable `boolean`, not `bool`.** `_build_facts` defaults
  it to `False` at `facts.py:1185`, so it should never need materializing — but
  an empty *numpy* bool column materializes as `True`, not null, so declaring
  `bool` would make the one path that fabricates data the path taken when data
  is missing. Fabricating "this fact is dimensioned" is the failure class this
  schema exists to prevent, and `boolean` is the same dtype family, so nothing
  downstream distinguishes them until a value is actually absent.

### Configuration-gated blocks

Present or absent according to the query's flags, and fully determined by them:

| block | flag | columns |
|---|---|---|
| context | `include_contexts` (default `True`) | `context_ref`, `entity_identifier`, `entity_scheme`, `period_type` |
| dimension — fixed | `include_dimensions` (default `False`) | `dimension`, `member`, `dimension_label`, `dimension_member_label`, `full_dimension_label` |
| dimension — axis tail | `include_dimensions` | `dim_<axis>`, one per axis in the filing — **explicitly not declared** |
| element | `include_element_info` (default `True`) | *none are ever built — the flag is inert, tracked separately* |

The positional `*columns` projection and the `skip_columns` drops
(`fact_key`, `original_label`) are unchanged: both are caller- or
code-determined, not data-determined.

### What stays undeclared, and why that is honest

The `dim_<axis>` columns depend on which axes a filer used, so two filings
legitimately produce different sets and a diff across them carries no
information. They are documented as a filing-dependent tail and excluded from
the #929 gate. Declaring them would be a promise the data cannot keep.

## Shipping

Split, because the two halves have very different blast radii.

**5.x — the additive half.** Deleting the `dropna` call, materializing
conditionally-absent columns, and returning a typed zero-row frame for empty
results all *add* columns that used to vanish. A caller that indexes a column
gets a column where it previously got a `KeyError`; a caller that asserts an
exact `df.columns` sees a change, which is the narrow risk and is worth a
changelog entry. Landing this early stops the gate's own reference surface from
moving during 6.0 work.

**6.0 — the dtype half.** `preferred_sign` and `fiscal_year` moving to `Int64`
changes what `.dtype` reports and moves those columns' null sentinel from `NaN`
to `pd.NA`. That is precisely the class of change #929 asked to be told about in
advance, so it goes in the breaking window with a migration-guide entry.

Every schema change here gets its own CHANGELOG entry, per the commitment in
[gh-929 comment 5170334125](https://github.com/dgunning/edgartools/issues/929#issuecomment-5170334125).

## Consequences

- The `07lk.1` schema gate becomes meaningful: a diff against
  `engineering/analysis/perf-baseline/schemas.json` reflects a code change
  rather than which rows a query happened to return.
- The baseline's own capture of this surface should be re-taken after the 5.x
  half lands; the committed 5.45.1 numbers describe the pre-decision behaviour.
- Verification needs a check that is currently missing entirely: several
  distinct queries against one instance must produce identical column sets and
  dtypes. That assertion is what would have caught this.

## Alternatives rejected

**Pin only the columns measured to flip.** Smaller diff, and it fixes today's
evidence, but the next column to acquire a null flips silently and the gate
stays only partly trustworthy. The mechanism is inference itself, so removing
inference is the fix.

**Document the surface as unstable.** Cheapest, and it walks back the spirit of
the #929 commitment — we would be gating a surface we had just declared
unreliable.
