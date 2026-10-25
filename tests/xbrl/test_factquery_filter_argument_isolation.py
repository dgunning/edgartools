"""A period selection captures its caller's list when the filter is added.

Source: Golub Capital BDC's March 31, 2025 10-Q, accession
0001476765-25-000040, retained in tests/fixtures/xbrl/gbdc.
The ordinary owner parses a disclosed minimal wrapper of original nodes; the
stitched owner replaces only statement provision with the same observations.
Neither arrangement claims a full-filing parse or native multi-filing stitching.
The tests mutate only caller-owned filter lists, never source/query internals.
"""

from copy import deepcopy
from types import SimpleNamespace

import pandas as pd
import pytest
from lxml import etree

from edgar.xbrl import XBRL, XBRLS
from tests.paths import FIXTURES_DIR

pytestmark = pytest.mark.fast

_XBRLI = "http://www.xbrl.org/2003/instance"
_US_GAAP = "http://fasb.org/us-gaap/2024"
_COLUMNS = ("concept", "period_start", "period_end", "numeric_value")
_KEYS = (
    "duration_2024-10-01_2025-03-31",
    "duration_2023-10-01_2024-03-31",
)
_EXPECTED = [
    ("us-gaap:InterestPaidNet", "2024-10-01", "2025-03-31", 133282000),
    ("us-gaap:InterestPaidNet", "2023-10-01", "2024-03-31", 71205000),
]


@pytest.fixture(scope="module")
def source_pair():
    """Retain selected original nodes, stopping after the second source fact."""
    path = FIXTURES_DIR / "xbrl/gbdc/gbdc-20250331_htm.xml"
    wanted = {"c-1", "c-26", "usd", "f-501", "f-502"}
    selected = {}
    namespaces = None
    with path.open("rb") as source:
        for _, node in etree.iterparse(
            source, events=("end",), resolve_entities=False, no_network=True,
        ):
            if node.get("id") in wanted:
                selected[node.get("id")] = deepcopy(node)
                namespaces = node.getroottree().getroot().nsmap
            parent = node.getparent()
            if parent is not None and parent.tag == f"{{{_XBRLI}}}xbrl":
                node.clear()
                while node.getprevious() is not None:
                    del parent[0]
            if selected.keys() == wanted:
                break
    assert selected.keys() == wanted

    measure = selected["usd"].findtext(f"{{{_XBRLI}}}measure").strip()
    prefix, _, currency = measure.rpartition(":")
    assert (namespaces[prefix], currency) == ("http://www.xbrl.org/2003/iso4217", "USD")
    observations = []
    for index, (fact_id, context_id) in enumerate((("f-501", "c-1"), ("f-502", "c-26"))):
        concept, start, end, amount = _EXPECTED[index]
        fact = selected[fact_id]
        assert (fact.tag, fact.get("contextRef"), fact.get("unitRef"), fact.get("decimals")) == (
            f"{{{_US_GAAP}}}InterestPaidNet", context_id, "usd", "-3",
        )
        assert int(fact.text.strip()) == amount
        context = selected[context_id]
        assert context.findtext(f"{{{_XBRLI}}}entity/{{{_XBRLI}}}identifier").strip() == "0001476765"
        assert context.findtext(f"{{{_XBRLI}}}period/{{{_XBRLI}}}startDate").strip() == start
        assert context.findtext(f"{{{_XBRLI}}}period/{{{_XBRLI}}}endDate").strip() == end
        observations.append({
            "fact_id": fact_id, "context_ref": context_id, "unit_ref": "usd",
            "concept": concept, "period_start": start, "period_end": end,
            "numeric_value": amount, "period_key": _KEYS[index], "decimals": -3,
        })

    wrapper = etree.Element(f"{{{_XBRLI}}}xbrl", nsmap=namespaces)
    for node_id in ("c-1", "c-26", "usd", "f-501", "f-502"):
        wrapper.append(selected[node_id])
    return etree.tostring(wrapper, encoding="unicode"), observations


class SourceStatements(XBRLS):
    """Controlled statement provision; query ownership and execution stay native."""

    def __init__(self, observations):
        super().__init__([SimpleNamespace(
            entity_info={"document_type": "10-Q"}, entity_name="Golub Capital BDC, Inc.",
        )])
        self.observations = observations

    def get_statement(self, statement_type, max_periods=8, standard=True, **kwargs):
        assert statement_type == "CashFlowStatement"
        assert standard is False
        return {
            "periods": [(row["period_key"], row["period_end"]) for row in self.observations],
            "statement_data": [{
                "concept": "us-gaap:InterestPaidNet", "label": "Interest paid, net",
                "is_abstract": False, "has_values": True,
                "values": {row["period_key"]: row["numeric_value"] for row in self.observations},
                "decimals": {row["period_key"]: row["decimals"] for row in self.observations},
            }],
            "period_sources": {row["period_key"]: 0 for row in self.observations},
        }


@pytest.fixture(params=["ordinary", "stitched"])
def query_factory(request, source_pair):
    document, observations = source_pair
    if request.param == "ordinary":
        xbrl = XBRL()
        xbrl.parser.parse_instance_content(document)
        facts = {fact.fact_id: fact for fact in xbrl.parser.facts.values()}
        assert set(facts) == {"f-501", "f-502"}
        for row in observations:
            fact = facts[row["fact_id"]]
            assert (fact.context_ref, fact.unit_ref, fact.numeric_value) == (
                row["context_ref"], row["unit_ref"], row["numeric_value"],
            )
        return xbrl.facts.query
    owner = SourceStatements(observations)
    return lambda: owner.query(statement_types=["CashFlowStatement"], standardize=False)


def _rows(result):
    records = result.to_dict("records") if isinstance(result, pd.DataFrame) else result
    return [tuple(row[column] for column in _COLUMNS) for row in records]


def test_list_edit_does_not_make_execution_and_conversion_disagree(query_factory):
    """The original defect, without assuming a live-list or snapshot policy."""
    keys = [_KEYS[0]]
    query = query_factory().by_period_keys(keys)
    assert _rows(query.to_dataframe(*_COLUMNS)) == _EXPECTED[:1]
    keys.append(_KEYS[1])

    assert _rows(query_factory().by_period_keys(keys).to_dataframe(*_COLUMNS)) == _EXPECTED
    assert _rows(query.execute()) == _rows(query.to_dataframe(*_COLUMNS))


@pytest.mark.parametrize("conversion", ["to_dataframe", "to_pandas"])
@pytest.mark.parametrize("mutation", ["append", "remove", "clear"])
def test_warmed_filter_keeps_its_call_time_selection(query_factory, conversion, mutation):
    keys = [_KEYS[0]] if mutation == "append" else list(_KEYS)
    original_keys = list(keys)
    expected = _EXPECTED[:1] if mutation == "append" else _EXPECTED
    query = query_factory().by_period_keys(keys)
    warm = getattr(query, conversion)(*_COLUMNS)
    assert _rows(warm) == expected

    if mutation == "append":
        keys.append(_KEYS[1])
        updated = _EXPECTED
    elif mutation == "remove":
        keys.remove(_KEYS[0])
        updated = _EXPECTED[1:]
    else:
        keys.clear()
        updated = []

    # New queries capture the list supplied to their own calls.
    assert _rows(query_factory().by_period_keys(keys).execute()) == updated
    assert _rows(query_factory().by_period_keys(original_keys).execute()) == expected
    assert getattr(query, conversion)(*_COLUMNS) is warm
    assert _rows(query.execute()) == _rows(warm) == expected


@pytest.mark.parametrize("conversion", ["to_dataframe", "to_pandas"])
def test_mutating_the_list_before_first_read_does_not_reconfigure_the_query(query_factory, conversion):
    keys = [_KEYS[0]]
    query = query_factory().by_period_keys(keys)
    keys.append(_KEYS[1])

    assert _rows(query_factory().by_period_keys(keys).execute()) == _EXPECTED
    assert _rows(query.execute()) == _EXPECTED[:1]
    assert _rows(getattr(query, conversion)(*_COLUMNS)) == _EXPECTED[:1]


def test_reusing_one_list_captures_each_querys_selection_separately(query_factory):
    keys = [_KEYS[0]]
    first = query_factory().by_period_keys(keys)
    keys.append(_KEYS[1])
    both = query_factory().by_period_keys(keys)
    keys.remove(_KEYS[0])
    second = query_factory().by_period_keys(keys)
    keys.clear()

    for query, expected in ((first, _EXPECTED[:1]), (both, _EXPECTED), (second, _EXPECTED[1:])):
        assert _rows(query.execute()) == expected
        assert _rows(query.to_dataframe(*_COLUMNS)) == expected


def test_repeated_period_filter_calls_add_an_and_constraint(query_factory):
    query = query_factory().by_period_keys([_KEYS[0]])
    assert _rows(query.to_dataframe(*_COLUMNS)) == _EXPECTED[:1]
    assert query.by_period_keys([_KEYS[1]]) is query
    assert _rows(query.execute()) == []
    assert _rows(query.to_dataframe(*_COLUMNS)) == []


@pytest.mark.parametrize("keys,expected", [([], []), ([_KEYS[1], _KEYS[0], _KEYS[1]], _EXPECTED)])
def test_empty_and_duplicate_keys_preserve_membership_and_source_order(query_factory, keys, expected):
    query = query_factory().by_period_keys(keys)
    assert _rows(query.execute()) == expected
    assert _rows(query.to_dataframe(*_COLUMNS)) == expected


def test_supported_value_range_already_captures_its_bounds(query_factory):
    bounds = [100000000, 200000000]
    query = query_factory().by_value(bounds)
    bounds[:] = [0, 100000000]
    assert _rows(query.execute()) == _EXPECTED[:1]
    assert _rows(query.to_dataframe(*_COLUMNS)) == _EXPECTED[:1]
    assert _rows(query_factory().by_value(bounds).execute()) == _EXPECTED[1:]


def test_custom_predicates_keep_their_existing_callable_behavior(query_factory):
    keys = [_KEYS[0]]
    query = query_factory().by_custom(lambda fact: fact["period_key"] in keys)
    assert _rows(query.execute()) == _EXPECTED[:1]
    keys.append(_KEYS[1])
    assert _rows(query.execute()) == _EXPECTED


def test_captured_periods_survive_owner_refresh_and_projection_reentry(source_pair):
    """Refreshing staged source rows must not replace captured filter criteria."""
    document, _ = source_pair
    first_document = etree.fromstring(document.encode())
    second_document = deepcopy(first_document)
    # These are staged subsets of the same filing, with original nodes intact.
    for root, omitted_fact in ((first_document, "f-502"), (second_document, "f-501")):
        for node in list(root):
            if node.get("id") == omitted_fact:
                root.remove(node)

    xbrl = XBRL()
    xbrl.parser.parse_instance_content(etree.tostring(first_document, encoding="unicode"))
    owner = xbrl.facts
    keys = list(_KEYS)
    query = (owner.query().by_period_keys(keys)
             .sort_by("numeric_value", ascending=False).limit(2))
    identity_columns = ("fact_id", "context_ref", "unit_ref", "numeric_value")
    expected_identities = [
        ("f-501", "c-1", "usd", 133282000),
        ("f-502", "c-26", "usd", 71205000),
    ]
    warm = query.to_dataframe(*_COLUMNS)
    assert _rows(warm) == _EXPECTED[:1]
    assert list(query.to_dataframe(*identity_columns).itertuples(index=False, name=None)) == expected_identities[:1]

    keys.remove(_KEYS[0])
    xbrl.parser.parse_instance_content(etree.tostring(second_document, encoding="unicode"))
    owner.clear_cache()

    # Ask for a new projection first, then revisit both warmed projections.
    refreshed = query.to_dataframe("fact_id", "period_key", "numeric_value")
    assert list(refreshed.itertuples(index=False, name=None)) == [
        ("f-501", _KEYS[0], 133282000),
        ("f-502", _KEYS[1], 71205000),
    ]
    assert _rows(query.execute()) == _EXPECTED
    assert _rows(query.to_pandas(*_COLUMNS)) == _EXPECTED
    assert list(query.to_dataframe(*identity_columns).itertuples(index=False, name=None)) == expected_identities
    assert _rows(warm) == _EXPECTED[:1]
    assert _rows(owner.query().by_period_keys(keys).to_dataframe(*_COLUMNS)) == _EXPECTED[1:]

    query.sort_by("numeric_value").limit(1)
    assert _rows(query.execute()) == _rows(query.to_dataframe(*_COLUMNS)) == _EXPECTED[1:]
    query.sort_by("numeric_value", ascending=False).limit(2)
    assert _rows(query.execute()) == _rows(query.to_dataframe(*_COLUMNS)) == _EXPECTED
