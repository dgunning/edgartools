"""
A total standard concept is returned only for its listed members.

``ReverseIndex.lookup()`` used to keep a part from resolving to a total by two signals: the
concept's display name starting with "Total" and the entry's ``is_total`` flag, which is a
usage statistic rather than a property of the element. Totals named otherwise ("Net Cash
from Operating Activities", "Revenue", "Operating Income") were unguarded, and 94 component
keys still resolved to a total on main 88c33194: IFRS cash-flow adjustments to the operating
total, ``WarrantLiability`` to "Total Liabilities", ``LimitedPartnersCapitalAccount`` to
"Total Stockholders' Equity", contra-revenue to "Revenue".

Each total concept now has a closed membership list in
``edgar/xbrl/standardization/total_membership.json``. The fixture
``tests/fixtures/standardization/total_concept_membership.json`` holds the same lists with a
classification per member, the KNOWN_WRONG components the guard blocks, and the members the
older ``is_total``/display-text guard already dropped. A regenerated ``gaap_mappings.json``
that maps a new key to a total fails here; so does a member that stops resolving, and a
KNOWN_WRONG entry whose mapping the data no longer carries (remove it from the fixture in the
PR that fixes the data, which is the visible proof).

GitHub Issue: https://github.com/dgunning/edgartools/issues/1444
"""

import json
from collections import defaultdict
from pathlib import Path

import pytest

from edgar.httprequests import download_file
from edgar.xbrl import XBRL
from edgar.xbrl.standardization import reverse_index as reverse_index_module
from edgar.xbrl.standardization.reverse_index import ReverseIndex

_STANDARDIZATION = Path(reverse_index_module.__file__).parent
FIXTURE = json.loads(
    (Path(__file__).parents[2] / "fixtures" / "standardization" / "total_concept_membership.json").read_text(encoding="utf-8")
)
CODE_MEMBERSHIP = json.loads((_STANDARDIZATION / "total_membership.json").read_text(encoding="utf-8"))["totals"]
GAAP_MAPPINGS = json.loads((_STANDARDIZATION / "gaap_mappings.json").read_text(encoding="utf-8"))
GAAP_MAPPINGS.pop("_metadata", None)
SECTIONS = json.loads((_STANDARDIZATION / "section_membership.json").read_text(encoding="utf-8"))
SECTIONS.pop("_metadata", None)

TOTALS = FIXTURE["totals"]
KNOWN_WRONG = {(e["tag"], e["total"]): e for e in FIXTURE["known_wrong"]}
ALREADY_BLOCKED = {(e["tag"], e["total"]): e for e in FIXTURE["already_blocked"]}


@pytest.fixture(scope="module")
def index():
    # A fresh index, so no other test's patched singleton is measured.
    return ReverseIndex()


def _spellings(key):
    """Every spelling a filing can use for a gaap_mappings key, so ifrs-full: forms are covered."""
    if key.startswith("ifrs-full_"):
        name = key[len("ifrs-full_"):]
        return [key, f"ifrs-full:{name}", f"ifrs:{name}"]
    if key.startswith(("ifrs:", "ifrs_")):
        return [key]
    return [key, f"us-gaap:{key}", f"us-gaap_{key}"]


def _industries():
    """None, plus every industry an override names (there are none since #1537; a regenerated file may add them)."""
    names = {name for entry in GAAP_MAPPINGS.values() for name in (entry.get("industry_overrides") or {})}
    return [None, *sorted(names)]


def _contexts():
    contexts = [None, {"is_total": True}]
    for statement, sections in SECTIONS.items():
        contexts.extend({"section": section, "statement_type": statement} for section in sections)
    return contexts


def _members_by_lookup(index):
    """total -> {gaap_mappings key whose lookup() or contextual resolution, in any spelling, can return it}."""
    members = defaultdict(set)
    contexts = _contexts()
    for key in GAAP_MAPPINGS:
        for spelling in _spellings(key):
            resolved_key = index._normalize_tag(spelling)
            if resolved_key is None:
                continue
            for industry in _industries():
                result = index.lookup(spelling, industry=industry)
                for concept in result.standard_concepts if result else []:
                    members[concept].add(resolved_key)
                for context in contexts:
                    concept = index.get_standard_concept(spelling, context, industry=industry)
                    if concept:
                        members[concept].add(resolved_key)
    return members


def test_every_total_concept_has_a_membership_list(index):
    """A concept displayed "Total ..." or filed in a *Totals section must be listed, and every listed one must exist."""
    concepts = {t for entry in GAAP_MAPPINGS.values() for t in entry.get("standard_tags", [])}
    expected = {c for c in concepts if index.concept_to_display_name(c).strip().lower().startswith("total")}
    for sections in SECTIONS.values():
        for section, section_concepts in sections.items():
            if section.endswith("Totals"):
                expected.update(c for c in section_concepts if c in concepts)
    expected -= set(FIXTURE["not_totals"])
    problems = [f"unlisted total: {c} ({index.concept_to_display_name(c)})" for c in sorted(expected - set(TOTALS))]
    problems += [f"listed total is no longer a standard concept: {c}" for c in sorted(set(TOTALS) - concepts)]
    problems += [
        f"{c}: display name is now {index.concept_to_display_name(c)!r}, fixture says {TOTALS[c]['display_name']!r}"
        for c in sorted(set(TOTALS) & concepts)
        if index.concept_to_display_name(c) != TOTALS[c]["display_name"]
    ]
    assert not problems, "\n".join(problems)
    assert len(TOTALS) == 28


def test_the_guard_reads_the_pinned_membership():
    """The code's membership file and the fixture name the same members, so neither can change alone."""
    problems = []
    for total in sorted(set(TOTALS) | set(CODE_MEMBERSHIP)):
        code = set(CODE_MEMBERSHIP.get(total, []))
        pinned = set(TOTALS.get(total, {}).get("allowed", {}))
        if code != pinned:
            problems.append(f"{total}: only in total_membership.json {sorted(code - pinned)}, only in fixture {sorted(pinned - code)}")
    assert not problems, "\n".join(problems)


def test_each_total_resolves_from_exactly_its_allowed_members(index):
    """No key resolves to a total unless listed, and every listed member still resolves (with or without context)."""
    members = _members_by_lookup(index)
    problems = []
    for total, spec in sorted(TOTALS.items()):
        allowed = set(spec["allowed"])
        actual = members.get(total, set())
        problems += [f"{total}: NEW member {key}" for key in sorted(actual - allowed)]
        problems += [f"{total}: member {key} no longer resolves to it (update the fixture)" for key in sorted(allowed - actual)]
    assert not problems, "\n".join(problems)
    assert sum(len(spec["allowed"]) for spec in TOTALS.values()) == 217


def test_mapped_members_are_allowed_known_wrong_or_already_blocked():
    """gaap_mappings.json itself: every key that maps to a total is accounted for, and every listed exception is still mapped.

    This is the check a regenerated mapping file trips: the guard blocks a new part from being
    returned, and this names it. A KNOWN_WRONG entry whose mapping the data dropped is reported
    too, so the fixture records the fix.
    """
    mapped = defaultdict(set)
    for key, entry in GAAP_MAPPINGS.items():
        tags = list(entry.get("standard_tags", []))
        for override in (entry.get("industry_overrides") or {}).values():
            tags += override.get("standard_tags", [])
        for tag in tags:
            if tag in TOTALS:
                mapped[tag].add(key)
    problems = []
    for total, spec in sorted(TOTALS.items()):
        accounted = set(spec["allowed"]) | {k for k, t in KNOWN_WRONG if t == total} | {k for k, t in ALREADY_BLOCKED if t == total}
        problems += [f"{total}: {key} maps to it and is not listed" for key in sorted(mapped[total] - accounted)]
    for key, total in sorted(set(KNOWN_WRONG) | set(ALREADY_BLOCKED)):
        if key not in mapped[total]:
            problems.append(f"{key} -> {total} is no longer in gaap_mappings.json: remove it from the fixture")
    for key, total in sorted(KNOWN_WRONG):
        if key in TOTALS[total]["allowed"]:
            problems.append(f"{key} -> {total} is both allowed and KNOWN_WRONG")
    assert not problems, "\n".join(problems)
    assert len(KNOWN_WRONG) == 94
    assert len(ALREADY_BLOCKED) == 14


def test_known_wrong_components_fall_back_and_real_totals_stay(index):
    """Spot values: the blocked part takes its other candidate or none, and the canonical totals are untouched."""
    assert index.lookup("us-gaap:WarrantLiability") is None
    assert index.lookup("us-gaap:LimitedPartnersCapitalAccount") is None
    assert index.lookup("ifrs-full:IssuedCapital") is None
    assert index.lookup("AdjustmentsForDepreciationExpense") is None
    assert index.lookup("us-gaap:SalesReturnsGoods") is None

    partners = index.lookup("us-gaap:PartnersCapital")
    assert partners.standard_concepts == ["CommonEquity"]
    assert partners.display_names == ["Total Stockholders' Equity"]
    for tag, concept in [
        ("us-gaap:Liabilities", "Liabilities"),
        ("ifrs-full:Liabilities", "Liabilities"),
        ("us-gaap:NetCashProvidedByUsedInOperatingActivities", "NetCashFromOperatingActivities"),
        ("ifrs-full:CashFlowsFromUsedInOperatingActivities", "NetCashFromOperatingActivities"),
        ("us-gaap:Revenues", "Revenue"),
        ("ifrs-full:Revenue", "Revenue"),
        ("us-gaap:OperatingIncomeLoss", "OperatingIncomeLoss"),
    ]:
        assert index.lookup(tag).standard_concepts == [concept], tag


def _rows(frame, standard_concept, column):
    selected = frame[frame["standard_concept"] == standard_concept]
    return dict(zip(selected["concept"], selected[column], strict=True))


# Cheniere Energy Partners' FY2025 10-K: schema, instance, presentation and label linkbases
# (without the label linkbase the rendered frame has no period columns).
CQP_10K_FOLDER = "https://www.sec.gov/Archives/edgar/data/1383650/000138365026000005/"
CQP_10K_XBRL_FILES = ("cqp-20251231.xsd", "cqp-20251231_htm.xml", "cqp-20251231_pre.xml", "cqp-20251231_lab.xml")


@pytest.mark.vcr
def test_cheniere_partners_capital_accounts_are_not_total_equity(tmp_path):
    """Cheniere Energy Partners, L.P. FY2025 10-K, 0001383650-26-000005, balance sheet at 2025-12-31.

    Filed: common unitholders' interest $3,156M, general partner's interest $(2,742)M, total
    partners' equity $414M. All three rows were "Total Stockholders' Equity" (CommonEquity);
    only the total is now.
    """
    for name in CQP_10K_XBRL_FILES:
        (tmp_path / name).write_text(download_file(CQP_10K_FOLDER + name), encoding="utf-8")
    frame = XBRL.from_directory(tmp_path).statements["BalanceSheet"].render(standard=True).to_dataframe()
    frame = frame[~frame["dimension"]]

    assert _rows(frame, "CommonEquity", "2025-12-31") == {"us-gaap_PartnersCapital": 414_000_000}
    assert _rows(frame, "CommonEquity", "2024-12-31") == {"us-gaap_PartnersCapital": -509_000_000}
    parts = frame[frame["concept"].isin(["us-gaap_LimitedPartnersCapitalAccount", "us-gaap_GeneralPartnersCapitalAccount"])]
    assert parts["2025-12-31"].tolist() == [3_156_000_000, -2_742_000_000]
    assert parts["standard_concept"].isna().all()
