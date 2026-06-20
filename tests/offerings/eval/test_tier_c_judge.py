"""Unit tests for the offerings Tier C LLM-judge module (pure functions only).

The prompt builder and verdict parser are network-free and deterministic, so they
are tested here in the fast suite. Evidence gathering and get_judge_tasks touch
the network and are exercised manually / in the network suite.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from tier_c_judge import (  # noqa: E402
    OfferingVerdict,
    build_offering_judge_prompt,
    parse_offering_judge_verdict,
    summarize_verdicts,
)


class TestPromptBuilding:
    def test_prompt_includes_value_facet_and_evidence(self):
        prompt = build_offering_judge_prompt(
            "lead_bookrunner", "0001-25-1", "BofA Securities, Inc.",
            "Selling Agent: BofAS",
        )
        assert "BofA Securities, Inc." in prompt
        assert "lead bookrunner" in prompt
        assert "Selling Agent: BofAS" in prompt
        assert "0001-25-1" in prompt
        assert '"verdict"' in prompt  # the response contract is spelled out

    def test_none_value_is_shown_explicitly(self):
        prompt = build_offering_judge_prompt("lead_bookrunner", "x", None, "evidence")
        assert "no value extracted" in prompt

    def test_empty_evidence_is_labeled_not_blank(self):
        prompt = build_offering_judge_prompt("fee_capacity", "x", 1e8, "")
        assert "no evidence gathered" in prompt

    def test_unknown_facet_fails_loudly(self):
        with pytest.raises(KeyError):
            build_offering_judge_prompt("not_a_facet", "x", "v", "e")


class TestVerdictParsing:
    def test_raw_json_correct(self):
        text = '{"verdict": "correct", "judged_value": null, "confidence": "high", "rationale": "named on cover"}'
        v = parse_offering_judge_verdict(text, "lead_bookrunner", "acc", "BofA Securities, Inc.")
        assert v.verdict == "correct"
        assert v.confidence == "high"
        assert v.judged_value is None
        assert not v.disagrees

    def test_markdown_fenced_incorrect_is_a_disagreement(self):
        text = ('```json\n{"verdict": "incorrect", "judged_value": "Jefferies LLC", '
                '"confidence": "high", "rationale": "Jefferies is the lead; the extracted firm is a co-manager"}\n```')
        v = parse_offering_judge_verdict(text, "lead_bookrunner", "acc", "Wrong Co.")
        assert v.verdict == "incorrect"
        assert v.judged_value == "Jefferies LLC"
        assert v.disagrees is True

    def test_low_confidence_incorrect_is_not_a_disagreement(self):
        text = '{"verdict": "incorrect", "judged_value": "?", "confidence": "low", "rationale": "unsure"}'
        v = parse_offering_judge_verdict(text, "fee_capacity", "acc", 1e8)
        assert v.verdict == "incorrect"
        assert v.disagrees is False  # low confidence does not count as confirmed

    def test_prose_around_json_still_parses(self):
        text = 'Here is my ruling:\n{"verdict": "uncertain", "confidence": "low", "rationale": "evidence truncated"}\nThanks!'
        v = parse_offering_judge_verdict(text, "shelf_status", "acc", "effective")
        assert v.verdict == "uncertain"

    def test_garbage_response_defaults_to_uncertain_not_incorrect(self):
        v = parse_offering_judge_verdict("the model said something unparseable",
                                         "lead_bookrunner", "acc", "X")
        assert v.verdict == "uncertain"
        assert v.disagrees is False
        assert "parse error" in v.rationale

    def test_unknown_verdict_value_is_uncertain(self):
        text = '{"verdict": "maybe", "confidence": "high"}'
        v = parse_offering_judge_verdict(text, "fee_capacity", "acc", 1e8)
        assert v.verdict == "uncertain"

    def test_invalid_confidence_falls_back_to_low(self):
        text = '{"verdict": "correct", "confidence": "extremely-sure"}'
        v = parse_offering_judge_verdict(text, "fee_capacity", "acc", 1e8)
        assert v.confidence == "low"


class TestReporting:
    def test_summary_tallies_and_lists_only_confirmed_disagreements(self):
        verdicts = [
            OfferingVerdict("lead_bookrunner", "a1", "BofA", "correct", None, "high", "ok"),
            OfferingVerdict("lead_bookrunner", "a2", "Wrong", "incorrect", "Right Co.", "high", "mislabeled"),
            OfferingVerdict("lead_bookrunner", "a3", "Maybe", "incorrect", "?", "low", "unsure"),
            OfferingVerdict("fee_capacity", "a4", 1e8, "uncertain", None, "low", "no evidence"),
        ]
        report = summarize_verdicts(verdicts)
        assert "lead_bookrunner" in report
        assert "Right Co." in report          # the high-confidence disagreement is cataloged
        assert "a3" not in report             # the low-confidence one is not
        assert "Confirmed disagreements" in report

    def test_summary_clean_when_no_disagreements(self):
        verdicts = [OfferingVerdict("fee_capacity", "a1", 1e8, "correct", None, "high", "matches table")]
        assert "No confirmed disagreements." in summarize_verdicts(verdicts)
