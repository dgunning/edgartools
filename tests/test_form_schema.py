"""
Tests for the per-form section schema (edgartools-fhno).

The schema replaces the scattered ``if self.form in (...)`` branches in
TOCAnalyzer with declarative data. These tests pin the schema's resolution,
bare-item caps, and text-keyword matching — including the deliberately-preserved
exclusion asymmetry between name normalization and sort ordering.
"""
import pytest

from edgar.documents.form_schema import (
    DEFAULT_SCHEMA,
    TEN_K_SCHEMA,
    TEN_Q_SCHEMA,
    FormSchema,
    TextItemRule,
    get_form_schema,
)


# --- resolution -------------------------------------------------------------

@pytest.mark.parametrize("form,expected", [
    ("10-K", TEN_K_SCHEMA),
    ("10-K/A", TEN_K_SCHEMA),
    (None, TEN_K_SCHEMA),          # legacy default: unspecified form == 10-K
    ("10-Q", TEN_Q_SCHEMA),
    ("10-Q/A", TEN_Q_SCHEMA),
    ("20-F", DEFAULT_SCHEMA),
    ("S-1", DEFAULT_SCHEMA),
    ("DEF 14A", DEFAULT_SCHEMA),
])
def test_get_form_schema(form, expected):
    assert get_form_schema(form) is expected


def test_bare_item_caps():
    assert TEN_Q_SCHEMA.max_bare_item == 6     # Items 1-6 only
    assert TEN_K_SCHEMA.max_bare_item == 15
    assert DEFAULT_SCHEMA.max_bare_item == 15


# --- 10-K text mapping (ground truth) ---------------------------------------

@pytest.mark.parametrize("text,item", [
    ("business", "Item 1"),
    ("risk factors", "Item 1A"),
    ("properties", "Item 2"),
    ("legal proceedings", "Item 3"),
    ("management's discussion and analysis", "Item 7"),
    ("financial statements", "Item 8"),
    ("exhibits", "Item 15"),
])
def test_ten_k_text_rules(text, item):
    assert TEN_K_SCHEMA.match_text(text) == item


def test_ten_k_exclusion_blocks_when_item_present():
    # "business" with the word "item" present is NOT mapped under normalization
    # rules (an explicit "Item N" regex handles those earlier).
    assert TEN_K_SCHEMA.match_text("item 1 business", use_exclusions=True) is None


def test_exclusion_asymmetry_preserved():
    """The sort-order path ignores exclusions (historical behaviour) — so the
    same text that normalization skips still resolves for ordering."""
    text = "item 1 business"
    assert TEN_K_SCHEMA.match_text(text, use_exclusions=True) is None
    assert TEN_K_SCHEMA.match_text(text, use_exclusions=False) == "Item 1"


# --- 10-Q: only the Risk-Factors overlap, skip the rest ---------------------

def test_ten_q_keeps_only_risk_factors():
    assert TEN_Q_SCHEMA.match_text("risk factors") == "Item 1A"
    # 10-K-shaped mappings are absent on 10-Q.
    assert TEN_Q_SCHEMA.match_text("financial statements") is None
    assert TEN_Q_SCHEMA.match_text("business") is None


def test_ten_q_skips_unmatched_text():
    assert TEN_Q_SCHEMA.skip_unmatched_text is True
    assert TEN_K_SCHEMA.skip_unmatched_text is False


# --- seed part (repeating-item forms) ---------------------------------------

def test_ten_q_seeds_part_i():
    """A 10-Q's items repeat across parts, so a document-order TOC walk must open
    in Part I — items before any Part header are Part I (edgartools-3usf)."""
    assert TEN_Q_SCHEMA.repeating_parts == ("I", "II")
    assert TEN_Q_SCHEMA.seed_part == "Part I"


def test_unique_item_forms_have_no_seed_part():
    """10-K (and unknown forms) infer the part from the item number, so their
    walk starts with no part context — no seed."""
    assert TEN_K_SCHEMA.repeating_parts == ()
    assert TEN_K_SCHEMA.seed_part is None
    assert DEFAULT_SCHEMA.seed_part is None


# --- silence / other forms --------------------------------------------------

def test_default_schema_has_no_rules():
    # 20-F etc.: no 10-K vocabulary, returns raw text upstream (None here).
    assert DEFAULT_SCHEMA.match_text("financial statements") is None
    assert DEFAULT_SCHEMA.text_rules == ()


def test_text_item_rule_matching():
    rule = TextItemRule("Item 7", ("management", "discussion"))
    assert rule.matches("management's discussion and analysis")
    assert not rule.matches("management report")  # missing "discussion"

    excl = TextItemRule("Item 1", ("business",), ("item",))
    assert excl.matches("our business overview")
    assert not excl.matches("item 1 business", use_exclusions=True)
    assert excl.matches("item 1 business", use_exclusions=False)
