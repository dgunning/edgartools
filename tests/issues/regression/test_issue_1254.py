"""Parsed XBRL facts keep the filer's xsi:nil marker.

GitHub Issue: https://github.com/dgunning/edgartools/issues/1254

A filed nil item (``xsi:nil="true"``) and a non-nil element with empty
content both parse to ``value=''`` and ``numeric_value=None``. Before this
change nothing on the fact, its query row or its DataFrame row told them
apart, and the DataFrame de-duplication kept whichever came first.

``Fact.is_nil`` records the marker and nothing more: it does not mean zero,
not-applicable or a retraction. The attribute is read by its expanded name
``{http://www.w3.org/2001/XMLSchema-instance}nil`` through the parser's
existing ``_is_nil()`` rule, so the prefix a filer chose does not matter.
That rule is lenient about case (``TRUE`` counts), which is kept here.

Real filing: Apple Inc. FY2023 Form 10-K, accession 0000320193-23-000106,
instance ``tests/fixtures/xbrl/aapl/10k_2023/aapl-20230930_htm.xml``, read
by hand before parsing:

- f-194 and f-195, ``us-gaap:CommitmentsAndContingencies``, unitRef ``usd``,
  ``xsi:nil="true"``, contexts c-22 (instant 2023-09-30) and c-23 (instant
  2022-09-24).
- f-403, ``us-gaap:RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionPeriod1``,
  context c-62, no unit, ``xsi:nil="true"``.
- f-397, the same concept, context c-59, value ``P1Y``, no nil attribute.
- f-172, ``us-gaap:Assets``, context c-22, value ``352583000000`` USD.

Those three are the only nil items in the instance.
"""
import pandas as pd
import pytest

from edgar.xbrl import XBRL
from edgar.xbrl.facts import _CORE_COLUMNS, _DEDUP_OPTIONAL
from edgar.xbrl.models import Fact
from edgar.xbrl.parsers.instance import InstanceParser

pytestmark = pytest.mark.fast

APPLE = "tests/fixtures/xbrl/aapl/10k_2023"
COMMITMENTS = "us-gaap:CommitmentsAndContingencies"
TIMING = "us-gaap:RevenueRemainingPerformanceObligationExpectedTimingOfSatisfactionPeriod1"


# ---------------------------------------------------------------------------
# Real filing
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def apple():
    return XBRL.from_directory(APPLE)


def _by_fact_id(xbrl):
    return {fact.fact_id: fact for fact in xbrl._facts.values() if fact.fact_id}


def test_apple_nil_facts_on_the_model(apple):
    facts = _by_fact_id(apple)

    for fact_id, context in (("f-194", "c-22"), ("f-195", "c-23")):
        fact = facts[fact_id]
        assert (fact.element_id, fact.context_ref, fact.unit_ref) == (COMMITMENTS, context, "usd")
        assert fact.is_nil is True
        assert fact.value == ""
        assert fact.numeric_value is None

    nil_text = facts["f-403"]
    assert (nil_text.element_id, nil_text.context_ref, nil_text.unit_ref) == (TIMING, "c-62", None)
    assert nil_text.is_nil is True
    assert nil_text.value == ""

    control = facts["f-397"]
    assert (control.element_id, control.context_ref, control.value) == (TIMING, "c-59", "P1Y")
    assert control.is_nil is False

    assets = facts["f-172"]
    assert (assets.element_id, assets.context_ref, assets.numeric_value) == (
        "us-gaap:Assets", "c-22", 352583000000.0)
    assert assets.is_nil is False

    assert sorted(f.fact_id for f in apple._facts.values() if f.is_nil) == ["f-194", "f-195", "f-403"]


def test_apple_nil_facts_in_query_rows_and_frames(apple):
    query = apple.query().by_concept(COMMITMENTS, exact=True)

    rows = sorted(query.execute(), key=lambda row: row["fact_id"])
    assert [(r["fact_id"], r["value"], r["numeric_value"], r["is_nil"], r["period_instant"])
            for r in rows] == [
        ("f-194", "", None, True, "2023-09-30"),
        ("f-195", "", None, True, "2022-09-24"),
    ]

    df = query.to_dataframe("fact_id", "value", "numeric_value", "is_nil")
    df = df.sort_values("fact_id").reset_index(drop=True)
    assert list(df.columns) == ["fact_id", "value", "numeric_value", "is_nil"]
    assert df["fact_id"].tolist() == ["f-194", "f-195"]
    assert df["value"].tolist() == ["", ""]
    assert df["numeric_value"].isna().all()
    assert df["is_nil"].dtype == "boolean"
    assert df["is_nil"].tolist() == [True, True]


def test_apple_default_frame_and_exports(apple):
    full = apple.query().to_dataframe()
    assert full["is_nil"].dtype == "boolean"
    flagged = full.loc[full["is_nil"].fillna(False), "fact_id"]
    assert sorted(flagged) == ["f-194", "f-195", "f-403"]
    assets = full.loc[full["fact_id"] == "f-172"].iloc[0]
    assert (assets["numeric_value"], assets["period_instant"], bool(assets["is_nil"])) == (
        352583000000.0, "2023-09-30", False)
    p1y = full.loc[full["fact_id"] == "f-397"].iloc[0]
    assert (p1y["value"], bool(p1y["is_nil"])) == ("P1Y", False)

    view_df = apple.facts.to_dataframe()
    assert sorted(view_df.loc[view_df["is_nil"], "fact_id"]) == ["f-194", "f-195", "f-403"]

    export = apple.to_pandas()["facts"]
    cols = list(export.columns)
    assert cols.index("is_nil") == cols.index("fact_id") + 1
    assert sorted(export.loc[export["is_nil"], "fact_id"]) == ["f-194", "f-195", "f-403"]


# ---------------------------------------------------------------------------
# Synthetic instances
# ---------------------------------------------------------------------------

_HEAD = """<?xml version="1.0" encoding="utf-8"?>
<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
            xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
            xmlns:inst="http://www.w3.org/2001/XMLSchema-instance"
            xmlns:other="http://example.com/not-xsi"
            xmlns:iso4217="http://www.xbrl.org/2003/iso4217"
            xmlns:my="http://example.com/my">
  <xbrli:context id="C1">
    <xbrli:entity><xbrli:identifier scheme="http://www.sec.gov/CIK">0000000001</xbrli:identifier></xbrli:entity>
    <xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period>
  </xbrli:context>
  <xbrli:unit id="usd"><xbrli:measure>iso4217:USD</xbrli:measure></xbrli:unit>
"""
_TAIL = "</xbrli:xbrl>\n"

ATTRIBUTE_CASES = """
  <my:nilTrue contextRef="C1" unitRef="usd" xsi:nil="true"/>
  <my:nilOne contextRef="C1" unitRef="usd" xsi:nil="1"/>
  <my:nilSpaced contextRef="C1" unitRef="usd" xsi:nil=" &#10;true&#9; "/>
  <my:nilAltPrefix contextRef="C1" unitRef="usd" inst:nil="true"/>
  <my:nilUpper contextRef="C1" unitRef="usd" xsi:nil="TRUE"/>
  <my:nilFalse contextRef="C1" unitRef="usd" xsi:nil="false"/>
  <my:nilZero contextRef="C1" unitRef="usd" xsi:nil="0"/>
  <my:nilInvalid contextRef="C1" unitRef="usd" xsi:nil="yes"/>
  <my:noAttribute contextRef="C1" unitRef="usd"/>
  <my:wrongNamespace contextRef="C1" unitRef="usd" other:nil="true"/>
  <my:unqualified contextRef="C1" unitRef="usd" nil="true"/>
  <my:emptyText contextRef="C1"></my:emptyText>
  <my:zero contextRef="C1" unitRef="usd" decimals="0">0</my:zero>
  <my:nilWithContent contextRef="C1" unitRef="usd" decimals="0" xsi:nil="true">5</my:nilWithContent>
"""


def _parse(body):
    facts = {}
    InstanceParser({}, facts, {}, {}, {}, {}, [], {}).parse_instance_content(_HEAD + body + _TAIL)
    return {key.split("|")[0]: fact for key, fact in facts.items()}


def _xbrl(body):
    xbrl = XBRL()
    xbrl.parser.parse_instance_content(_HEAD + body + _TAIL)
    return xbrl


@pytest.mark.parametrize("name, expected", [
    ("nilTrue", True),
    ("nilOne", True),
    ("nilSpaced", True),
    ("nilAltPrefix", True),
    # _is_nil() lower-cases the token; the lenient reading is kept on purpose.
    ("nilUpper", True),
    ("nilFalse", False),
    ("nilZero", False),
    ("nilInvalid", False),
    ("noAttribute", False),
    ("wrongNamespace", False),
    ("unqualified", False),
    ("emptyText", False),
    ("zero", False),
])
def test_nil_attribute_forms(name, expected):
    fact = _parse(ATTRIBUTE_CASES)[f"my_{name}"]
    assert fact.is_nil is expected


def test_nil_does_not_change_value_parsing():
    facts = _parse(ATTRIBUTE_CASES)

    nil = facts["my_nilTrue"]
    assert (nil.value, nil.numeric_value, nil.is_nil) == ("", None, True)

    empty = facts["my_emptyText"]
    assert (empty.value, empty.numeric_value, empty.is_nil) == ("", None, False)

    zero = facts["my_zero"]
    assert (zero.value, zero.numeric_value, zero.is_nil) == ("0", 0.0, False)

    # Malformed: nil-marked with content. The marker is source metadata, not a
    # validity claim, so both it and the parsed content are kept.
    malformed = facts["my_nilWithContent"]
    assert (malformed.value, malformed.numeric_value, malformed.is_nil) == ("5", 5.0, True)


# ---------------------------------------------------------------------------
# De-duplication: nil and empty are different facts
# ---------------------------------------------------------------------------

_NIL = '<my:pair contextRef="C1" unitRef="usd" id="{id}" xsi:nil="true"/>\n'
_EMPTY = '<my:pair contextRef="C1" unitRef="usd" id="{id}"/>\n'
_VALUED = '<my:pair contextRef="C1" unitRef="usd" id="{id}">0</my:pair>\n'


def _pair(first, second):
    return first.format(id="a") + second.format(id="b")


def test_is_nil_is_part_of_the_dedup_identity():
    assert "is_nil" in _DEDUP_OPTIONAL


@pytest.mark.parametrize("first, second", [(_NIL, _EMPTY), (_EMPTY, _NIL)],
                         ids=["nil-first", "empty-first"])
def test_nil_empty_pair_survives_in_every_frame(first, second):
    xbrl = _xbrl(_pair(first, second))
    expected_nil = {"a": first is _NIL, "b": second is _NIL}

    full = xbrl.query().to_dataframe()
    assert sorted(full["fact_id"]) == ["a", "b"]
    assert dict(zip(full["fact_id"], full["is_nil"].tolist(), strict=True)) == expected_nil

    narrow = xbrl.query().to_dataframe("fact_id", "is_nil")
    assert dict(zip(narrow["fact_id"], narrow["is_nil"].tolist(), strict=True)) == expected_nil

    # A projection that does not show is_nil still de-duplicates with it.
    assert len(xbrl.query().to_dataframe("concept", "value")) == 2
    assert sorted(xbrl.query().to_dataframe("fact_id", "value")["fact_id"]) == ["a", "b"]

    assert sorted(xbrl.facts.to_dataframe()["fact_id"]) == ["a", "b"]


@pytest.mark.parametrize("first, second, rows", [
    (_NIL, _NIL, 1),
    (_EMPTY, _EMPTY, 1),
    (_NIL, _VALUED, 2),
], ids=["nil-nil", "empty-empty", "nil-valued"])
def test_dedup_controls(first, second, rows):
    xbrl = _xbrl(_pair(first, second))
    assert len(xbrl.query().to_dataframe()) == rows
    assert len(xbrl.query().to_dataframe("concept", "value")) == rows
    assert len(xbrl.facts.to_dataframe()) == rows


def test_nil_and_valued_zero_stay_distinct():
    xbrl = _xbrl(_pair(_NIL, _VALUED))
    df = xbrl.query().to_dataframe().set_index("fact_id")
    assert (df.loc["a", "value"], pd.isna(df.loc["a", "numeric_value"]), df.loc["a", "is_nil"]) == ("", True, True)
    assert (df.loc["b", "value"], df.loc["b", "numeric_value"], df.loc["b", "is_nil"]) == ("0", 0.0, False)


# ---------------------------------------------------------------------------
# Defaults, old payloads and schema
# ---------------------------------------------------------------------------

def test_constructor_and_old_payload_default_to_not_nil():
    assert Fact(element_id="my:a", context_ref="C1", value="").is_nil is False
    old_payload = {"element_id": "my:a", "context_ref": "C1", "value": "", "fact_id": "x"}
    assert Fact.model_validate(old_payload).is_nil is False
    assert Fact(element_id="my:a", context_ref="C1", value="", is_nil=True).is_nil is True


def test_serialization_appends_the_key_after_fact_id():
    keys = list(Fact(element_id="my:a", context_ref="C1", value="").model_dump())
    assert keys[-2:] == ["fact_id", "is_nil"]


def test_is_nil_is_the_last_core_column():
    assert list(_CORE_COLUMNS)[-2:] == ["fiscal_year", "is_nil"]
    assert _CORE_COLUMNS["is_nil"] == "boolean"


def test_column_position_and_dtype_across_configurations():
    xbrl = _xbrl(_pair(_NIL, _EMPTY))

    default = xbrl.query().to_dataframe()
    assert list(default.columns)[-1] == "is_nil"
    assert default["is_nil"].dtype == "boolean"

    with_dims = xbrl.query().with_dimensions().to_dataframe()
    columns = list(with_dims.columns)
    assert columns.index("is_nil") == columns.index("fiscal_year") + 1
    assert columns.index("is_nil") < columns.index("dimension")

    no_contexts = xbrl.query().exclude_contexts().to_dataframe()
    assert list(no_contexts.columns)[-1] == "is_nil"

    projected = xbrl.query().to_dataframe("is_nil", "fact_id")
    assert list(projected.columns) == ["is_nil", "fact_id"]
    assert projected["is_nil"].dtype == "boolean"

    assert xbrl.query().to_pandas("fact_id", "is_nil")["is_nil"].dtype == "boolean"


def test_empty_results_declare_the_column():
    xbrl = _xbrl(_pair(_NIL, _EMPTY))
    empty = xbrl.query().by_concept("my:NoSuchConcept").to_dataframe()
    assert len(empty) == 0
    assert list(empty.columns)[-1] == "is_nil"
    assert empty["is_nil"].dtype == "boolean"

    projected = xbrl.query().by_concept("my:NoSuchConcept").to_dataframe("fact_id", "is_nil")
    assert list(projected.columns) == ["fact_id", "is_nil"]
    assert projected["is_nil"].dtype == "boolean"


def test_ordinary_and_empty_queries_still_display(apple):
    # A real filing: the synthetic instance has no entity name for the title.
    assert "f-194" not in repr(apple.query().by_concept("us-gaap:NoSuchConcept"))
    assert repr(apple.query().by_concept(COMMITMENTS, exact=True))


def test_rows_without_the_key_are_not_given_a_nil_value():
    """Manually supplied rows and derived aggregates carry no nil marker."""
    xbrl = _xbrl(_pair(_NIL, _EMPTY))
    view = xbrl.facts
    view._facts_cache = [
        {"concept": "my:a", "context_ref": "C1", "value": "1", "decimals": None,
         "numeric_value": 1.0, "fact_id": "m1", "dim_Seg": "x"},
        {"concept": "my:a", "context_ref": "C2", "value": "2", "decimals": None,
         "numeric_value": 2.0, "fact_id": "m2", "dim_Seg": "x"},
    ]
    df = view.query().to_dataframe()
    assert df["is_nil"].dtype == "boolean"
    assert df["is_nil"].isna().all()

    aggregated = view.query().aggregate("Seg").execute()
    assert aggregated and all("is_nil" not in row for row in aggregated)
    agg_df = view.query().aggregate("Seg").to_dataframe()
    assert agg_df["is_nil"].isna().all()


def test_cleared_view_refreshes_retained_query():
    xbrl = _xbrl(_EMPTY.format(id="a"))
    view = xbrl.facts
    query = view.query()
    before = query.to_dataframe()
    assert before["is_nil"].tolist() == [False]
    assert [row["is_nil"] for row in query.execute()] == [False]

    next(iter(xbrl.parser.facts.values())).is_nil = True
    view.clear_cache()

    assert [row["is_nil"] for row in query.execute()] == [True]
    assert query.to_dataframe()["is_nil"].tolist() == [True]
    assert before["is_nil"].tolist() == [False]
