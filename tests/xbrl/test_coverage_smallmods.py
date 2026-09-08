"""
Coverage tests for small/utility modules that were previously at 0%.

Targets:
- edgar.entity.tools (7 stmts, 3 thin Company wrappers)
- edgar.shelfofferings (6 stmts, 1 takedown-forms helper)
- edgar.forms (72 stmts, dataclasses + lookups; the network downloader
  is exercised lightly via cached fixtures, the rest is pure logic)
- edgar.xbrl.period_data_check (105 stmts, period quality utilities;
  the pure `get_essential_concepts_for_statement` plus mocked
  data-quality flows)

These are unit-style tests with mocks where needed — no network access,
all marked fast.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest


# ---------------------------------------------------------------------------
# edgar.entity.tools — three thin wrappers around Company.<statement>()
# ---------------------------------------------------------------------------

class TestEntityTools:
    @pytest.mark.fast
    def test_income_statement_delegates_to_company(self):
        from edgar.entity import tools

        sentinel = object()
        with patch.object(tools, "Company") as mock_company:
            instance = mock_company.return_value
            instance.income_statement.return_value = sentinel

            result = tools.income_statement("AAPL")

            mock_company.assert_called_once_with("AAPL")
            instance.income_statement.assert_called_once_with(annual=True, periods=4)
            assert result is sentinel

    @pytest.mark.fast
    def test_income_statement_passes_through_kwargs(self):
        from edgar.entity import tools

        with patch.object(tools, "Company") as mock_company:
            instance = mock_company.return_value
            tools.income_statement("MSFT", annual=False, periods=8)

            instance.income_statement.assert_called_once_with(annual=False, periods=8)

    @pytest.mark.fast
    def test_balance_sheet_delegates_to_company(self):
        from edgar.entity import tools

        sentinel = object()
        with patch.object(tools, "Company") as mock_company:
            instance = mock_company.return_value
            instance.balance_sheet.return_value = sentinel

            result = tools.balance_sheet("NVDA", annual=False, periods=2)

            mock_company.assert_called_once_with("NVDA")
            instance.balance_sheet.assert_called_once_with(annual=False, periods=2)
            assert result is sentinel

    @pytest.mark.fast
    def test_cash_flow_statement_delegates_to_company(self):
        from edgar.entity import tools

        sentinel = object()
        with patch.object(tools, "Company") as mock_company:
            instance = mock_company.return_value
            instance.cash_flow_statement.return_value = sentinel

            result = tools.cash_flow_statement("GOOG")

            mock_company.assert_called_once_with("GOOG")
            instance.cash_flow_statement.assert_called_once_with(annual=True, periods=4)
            assert result is sentinel


# ---------------------------------------------------------------------------
# edgar.shelfofferings.list_takedown_forms
# ---------------------------------------------------------------------------

class TestShelfOfferings:
    @pytest.mark.fast
    def test_list_takedown_forms_filters_to_takedown_universe(self):
        from edgar import shelfofferings

        # list_takedown_forms() pulls SecForms from list_forms() and filters
        # by the takedown_forms universe. Mock list_forms to avoid network.
        all_forms_df = pd.DataFrame({
            "Form": ["10-K", "424B1", "424B5", "424A", "497", "8-K", "F-3MEF"],
            "Description": ["Annual", "Prospectus 1", "Prospectus 5",
                            "Prospectus A", "Investment", "Current", "F-3 mod"],
            "Url": [""] * 7,
            "LastUpdated": [""] * 7,
            "SECNumber": [""] * 7,
            "Topics": [""] * 7,
        })
        sec_forms_mock = SimpleNamespace(data=all_forms_df)

        with patch.object(shelfofferings, "list_forms", return_value=sec_forms_mock):
            result = shelfofferings.list_takedown_forms()

        # Should keep only the takedown-universe forms (424A, 424B1, 424B5, 497, F-3MEF)
        # and drop 10-K and 8-K.
        forms_kept = set(result["Form"].tolist())
        assert "10-K" not in forms_kept
        assert "8-K" not in forms_kept
        assert {"424A", "424B1", "424B5", "497", "F-3MEF"}.issubset(forms_kept)

    @pytest.mark.fast
    def test_takedown_forms_universe_is_well_defined(self):
        from edgar.shelfofferings import takedown_forms

        # The 424B family must be fully covered (1-8) plus the named extras.
        assert "424A" in takedown_forms
        for n in range(1, 9):
            assert f"424B{n}" in takedown_forms
        assert "497" in takedown_forms
        assert "486BPOS" in takedown_forms
        assert "F-3MEF" in takedown_forms


# ---------------------------------------------------------------------------
# edgar.forms — SecForm / SecForms / FilingItem / find_section
# ---------------------------------------------------------------------------

class TestForms:
    def _sample_forms_df(self):
        return pd.DataFrame([
            {"Form": "10-K", "Description": "Annual report",
             "Url": "https://sec.gov/forms/10-K", "LastUpdated": "2024-01-01",
             "SECNumber": "SEC1410", "Topics": "Securities"},
            {"Form": "10-Q", "Description": "Quarterly report",
             "Url": "https://sec.gov/forms/10-Q", "LastUpdated": "2024-01-01",
             "SECNumber": "SEC1296", "Topics": "Securities"},
            {"Form": "8-K", "Description": "Current report",
             "Url": "https://sec.gov/forms/8-K", "LastUpdated": "2024-01-01",
             "SECNumber": "SEC0873", "Topics": "Securities"},
        ])

    @pytest.mark.fast
    def test_secforms_get_form_returns_secform(self):
        from edgar.forms import SecForms

        forms = SecForms(self._sample_forms_df())
        item = forms.get_form("10-K")

        assert item is not None
        assert item.form == "10-K"
        assert item.description == "Annual report"
        assert item.sec_number == "SEC1410"
        assert "10-K" in item.url

    @pytest.mark.fast
    def test_secforms_get_form_unknown_returns_none(self):
        from edgar.forms import SecForms

        forms = SecForms(self._sample_forms_df())
        assert forms.get_form("NOT-A-FORM") is None

    @pytest.mark.fast
    def test_secforms_indexing(self):
        from edgar.forms import SecForms

        forms = SecForms(self._sample_forms_df())
        item = forms["10-Q"]

        assert item is not None
        assert item.form == "10-Q"

    @pytest.mark.fast
    def test_secforms_len_and_summary(self):
        from edgar.forms import SecForms

        forms = SecForms(self._sample_forms_df())

        assert len(forms) == 3
        summary = forms.summary()
        assert list(summary.columns) == ["Form", "Description", "Topics"]
        assert len(summary) == 3

    @pytest.mark.fast
    def test_secform_str_formats_form_and_description(self):
        from edgar.forms import SecForm

        sf = SecForm(form="10-K", description="Annual report",
                     url="https://example.com", sec_number="SEC1",
                     topics="Securities")
        assert str(sf) == "Form 10-K: Annual report"

    @pytest.mark.fast
    def test_secform_repr_renders_via_rich(self):
        from edgar.forms import SecForm

        sf = SecForm(form="8-K", description="Current report",
                     url="https://example.com", sec_number="SEC2",
                     topics="Securities")
        text = repr(sf)
        # Rich panel output — must include form name and description fragment
        assert "8-K" in text
        assert "Current report" in text

    @pytest.mark.fast
    def test_secforms_repr_renders_via_rich(self):
        from edgar.forms import SecForms

        forms = SecForms(self._sample_forms_df())
        text = repr(forms)
        assert "SEC Forms" in text
        # Should include at least one form code from the data
        assert any(f in text for f in ["10-K", "10-Q", "8-K"])

    @pytest.mark.fast
    def test_filing_item_str_uses_markdown_heading(self):
        from edgar.forms import FilingItem

        fi = FilingItem(item_num="1.01", text="Material Definitive Agreement.")
        s = str(fi)
        assert "1.01" in s
        assert "Material Definitive Agreement." in s
        # Two pound signs is the Markdown level-2 heading the formatter uses
        assert "## " in s

    @pytest.mark.fast
    def test_find_section_returns_index_and_value(self):
        from edgar.forms import find_section

        sections = [
            "Item 1. Business",
            "Item 1A. Risk Factors",
            "Item 2. Properties",
        ]
        idx, section = find_section(r"risk\s+factors", sections)
        assert idx == 1
        assert "Risk Factors" in section

    @pytest.mark.fast
    def test_find_section_returns_none_when_not_found(self):
        from edgar.forms import find_section

        sections = ["Item 1. Business", "Item 2. Properties"]
        result = find_section("Executive Compensation", sections)
        assert result is None

    @pytest.mark.fast
    def test_secform_open_invokes_webbrowser(self):
        from edgar.forms import SecForm

        sf = SecForm(form="10-K", description="Annual",
                     url="https://example.com/forms/10-K",
                     sec_number="SEC1", topics="Securities")

        with patch("webbrowser.open") as mock_open:
            sf.open()
            mock_open.assert_called_once_with("https://example.com/forms/10-K")


# ---------------------------------------------------------------------------
# edgar.xbrl.period_data_check
# ---------------------------------------------------------------------------

class TestPeriodDataCheck:
    """Tests the period-quality utilities — pure functions and mock-driven flows."""

    @pytest.mark.fast
    def test_essential_concepts_for_balance_sheet(self):
        from edgar.xbrl.period_data_check import get_essential_concepts_for_statement

        bs = get_essential_concepts_for_statement("BalanceSheet")
        assert "Assets" in bs
        assert "Liabilities" in bs
        assert "StockholdersEquity" in bs
        # Should be a set, not a list
        assert isinstance(bs, set)

    @pytest.mark.fast
    def test_essential_concepts_for_income_statement(self):
        from edgar.xbrl.period_data_check import get_essential_concepts_for_statement

        is_ = get_essential_concepts_for_statement("IncomeStatement")
        assert "Revenues" in is_
        assert "NetIncomeLoss" in is_
        assert "GrossProfit" in is_

    @pytest.mark.fast
    def test_essential_concepts_for_cashflow(self):
        from edgar.xbrl.period_data_check import get_essential_concepts_for_statement

        cf = get_essential_concepts_for_statement("CashFlowStatement")
        assert "NetCashProvidedByUsedInOperatingActivities" in cf
        assert "NetCashProvidedByUsedInInvestingActivities" in cf
        assert "NetCashProvidedByUsedInFinancingActivities" in cf

    @pytest.mark.fast
    def test_essential_concepts_unknown_statement_returns_empty_set(self):
        from edgar.xbrl.period_data_check import get_essential_concepts_for_statement

        result = get_essential_concepts_for_statement("UnknownStatement")
        assert result == set()

    def _build_mock_xbrl(self, facts):
        """Build a lightweight xbrl_instance mock with the interface period_data_check expects.

        facts: list of (concept_name, context_period_dict, value) tuples
        """
        xbrl = MagicMock()
        xbrl._facts = {}
        xbrl.contexts = {}
        xbrl.element_catalog = {}

        for i, (concept, period, value) in enumerate(facts):
            ctx_id = f"c{i}"
            elem_id = f"e{i}"

            ctx = MagicMock()
            ctx.model_dump.return_value = {"period": period}
            xbrl.contexts[ctx_id] = ctx

            element = MagicMock()
            element.name = concept
            xbrl.element_catalog[elem_id] = element

            fact = MagicMock()
            fact.context_ref = ctx_id
            fact.element_id = elem_id
            fact.value = value
            xbrl._facts[f"f{i}"] = fact

        return xbrl

    @pytest.mark.fast
    def test_count_facts_for_instant_period(self):
        from edgar.xbrl.period_data_check import count_facts_for_period

        xbrl = self._build_mock_xbrl([
            ("Assets", {"type": "instant", "instant": "2024-12-31"}, 100),
            ("Liabilities", {"type": "instant", "instant": "2024-12-31"}, 50),
            ("Assets", {"type": "instant", "instant": "2023-12-31"}, 90),  # different period
        ])

        count = count_facts_for_period(xbrl, "instant_2024-12-31")
        assert count == 2

    @pytest.mark.fast
    def test_count_facts_for_duration_period(self):
        from edgar.xbrl.period_data_check import count_facts_for_period

        xbrl = self._build_mock_xbrl([
            ("Revenues", {"type": "duration", "startDate": "2024-01-01",
                           "endDate": "2024-12-31"}, 1000),
            ("CostOfRevenue", {"type": "duration", "startDate": "2024-01-01",
                                "endDate": "2024-12-31"}, 600),
            ("Revenues", {"type": "duration", "startDate": "2024-01-01",
                           "endDate": "2024-06-30"}, 500),  # different end
        ])

        count = count_facts_for_period(xbrl, "duration_2024-01-01_2024-12-31")
        assert count == 2

    @pytest.mark.fast
    def test_count_facts_returns_zero_for_unknown_format(self):
        from edgar.xbrl.period_data_check import count_facts_for_period

        xbrl = self._build_mock_xbrl([])
        # Unknown period_key shape
        assert count_facts_for_period(xbrl, "unknown_2024-12-31") == 0
        # Truncated duration key
        assert count_facts_for_period(xbrl, "duration_2024-12-31") == 0

    @pytest.mark.fast
    def test_check_period_data_quality_finds_essentials(self):
        from edgar.xbrl.period_data_check import check_period_data_quality

        xbrl = self._build_mock_xbrl([
            ("Revenues", {"type": "duration", "startDate": "2024-01-01",
                           "endDate": "2024-12-31"}, 1000),
            ("CostOfRevenue", {"type": "duration", "startDate": "2024-01-01",
                                "endDate": "2024-12-31"}, 600),
            ("GrossProfit", {"type": "duration", "startDate": "2024-01-01",
                              "endDate": "2024-12-31"}, 400),
            ("NetIncomeLoss", {"type": "duration", "startDate": "2024-01-01",
                                "endDate": "2024-12-31"}, 200),
        ])

        result = check_period_data_quality(
            xbrl, "duration_2024-01-01_2024-12-31", "IncomeStatement"
        )

        assert "fact_count" in result
        assert result["fact_count"] == 4
        assert result["essential_coverage"] > 0
        assert "NetIncomeLoss" in result["found_essentials"]
        assert isinstance(result["missing_essentials"], list)
        assert isinstance(result["has_meaningful_data"], bool)

    @pytest.mark.fast
    def test_check_period_data_quality_handles_truncated_key(self):
        from edgar.xbrl.period_data_check import check_period_data_quality

        xbrl = self._build_mock_xbrl([])
        # When period_key is malformed, function returns dict with sufficient=False
        result = check_period_data_quality(xbrl, "duration_2024", "IncomeStatement")
        assert result["has_sufficient_data"] is False
        assert result["fact_count"] == 0

    @pytest.mark.fast
    def test_filter_periods_with_data_keeps_only_sufficient(self):
        from edgar.xbrl.period_data_check import filter_periods_with_data

        # Build xbrl with rich facts for one period and no facts for the other
        good_period = "duration_2024-01-01_2024-12-31"
        bad_period = "duration_2099-01-01_2099-12-31"

        # Add 25 facts for good_period to comfortably clear the min_fact_count=10 threshold
        facts = []
        income_stmt_concepts = list(__import__(
            "edgar.xbrl.period_data_check", fromlist=["get_essential_concepts_for_statement"]
        ).get_essential_concepts_for_statement("IncomeStatement"))
        for i, concept in enumerate(income_stmt_concepts[:25]):
            facts.append((
                concept,
                {"type": "duration", "startDate": "2024-01-01", "endDate": "2024-12-31"},
                100 + i,
            ))

        xbrl = self._build_mock_xbrl(facts)

        kept = filter_periods_with_data(
            xbrl,
            [(good_period, "FY 2024"), (bad_period, "FY 2099")],
            "IncomeStatement",
            min_fact_count=10,
        )

        assert (good_period, "FY 2024") in kept
        assert (bad_period, "FY 2099") not in kept


# ---------------------------------------------------------------------------
# edgar.xbrl.standardization.utils — CSV/JSON IO + validation
# ---------------------------------------------------------------------------

class TestStandardizationUtils:
    """Pure-IO + validation tests. The MappingStore-dependent helpers are
    intentionally not exercised here — they need richer fixtures and live in
    a deeper test pass."""

    @pytest.mark.fast
    def test_validation_issue_dataclass_defaults(self):
        from edgar.xbrl.standardization.utils import ValidationIssue

        issue = ValidationIssue(severity="error", category="duplicate", message="Boom")
        assert issue.severity == "error"
        assert issue.category == "duplicate"
        assert issue.message == "Boom"
        assert issue.file is None
        assert issue.line is None
        assert issue.concept is None

    @pytest.mark.fast
    def test_validation_report_categorizes_issues(self):
        from edgar.xbrl.standardization.utils import ValidationIssue, ValidationReport

        report = ValidationReport()
        report.issues.extend([
            ValidationIssue("error", "duplicate", "Dup error"),
            ValidationIssue("warning", "missing", "Warn"),
            ValidationIssue("info", "format", "Info note"),
            ValidationIssue("error", "format", "Another error"),
        ])

        assert len(report.errors) == 2
        assert len(report.warnings) == 1
        assert len(report.info) == 1
        assert report.has_errors is True

    @pytest.mark.fast
    def test_validation_report_summary(self):
        from edgar.xbrl.standardization.utils import ValidationIssue, ValidationReport

        report = ValidationReport()
        report.issues.append(ValidationIssue("error", "duplicate", "x"))
        report.issues.append(ValidationIssue("warning", "missing", "y"))

        summary = report.summary()
        assert "1 errors" in summary
        assert "1 warnings" in summary

    @pytest.mark.fast
    def test_validation_report_print_does_not_raise(self, capsys):
        from edgar.xbrl.standardization.utils import ValidationIssue, ValidationReport

        report = ValidationReport()
        report.issues.extend([
            ValidationIssue("error", "duplicate", "Dup",
                            file="a.csv", line=2, concept="Revenue"),
            ValidationIssue("warning", "missing", "Missing"),
            ValidationIssue("info", "format", "Note"),
        ])

        report.print_report(show_info=True)
        captured = capsys.readouterr().out

        assert "ERRORS:" in captured
        assert "WARNINGS:" in captured
        assert "INFO:" in captured
        assert "Revenue" in captured  # concept included in location line

    @pytest.mark.fast
    def test_validation_report_no_errors_state(self):
        from edgar.xbrl.standardization.utils import ValidationReport

        report = ValidationReport()
        assert report.has_errors is False
        assert report.errors == []
        assert report.warnings == []

    @pytest.mark.fast
    def test_save_and_load_mappings_roundtrip(self, tmp_path):
        from edgar.xbrl.standardization.utils import (
            load_mappings_from_json,
            save_mappings_to_json,
        )

        original = {
            "Revenue": {"us-gaap_Revenue", "us-gaap_SalesRevenueNet"},
            "NetIncome": ["us-gaap_NetIncomeLoss"],
            "metadata": {"version": 1},
        }
        out = tmp_path / "mappings.json"
        save_mappings_to_json(original, str(out))

        loaded = load_mappings_from_json(str(out))
        # Sets get serialized as sorted lists
        assert loaded["Revenue"] == ["us-gaap_Revenue", "us-gaap_SalesRevenueNet"]
        assert loaded["NetIncome"] == ["us-gaap_NetIncomeLoss"]
        assert loaded["metadata"] == {"version": 1}

    @pytest.mark.fast
    def test_save_mappings_creates_parent_dirs(self, tmp_path):
        from edgar.xbrl.standardization.utils import save_mappings_to_json

        out = tmp_path / "nested" / "deep" / "mappings.json"
        save_mappings_to_json({"X": ["us-gaap_X"]}, str(out))
        assert out.exists()

    @pytest.mark.fast
    def test_validate_csv_missing_file_returns_error(self, tmp_path):
        from edgar.xbrl.standardization.utils import validate_csv_mappings

        nonexistent = tmp_path / "does_not_exist.csv"
        report = validate_csv_mappings(str(nonexistent))

        assert report.has_errors is True
        assert any("not found" in i.message for i in report.errors)

    @pytest.mark.fast
    def test_validate_csv_missing_required_columns(self, tmp_path):
        from edgar.xbrl.standardization.utils import validate_csv_mappings

        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("foo,bar\n1,2\n")  # missing standard_concept and company_concept
        report = validate_csv_mappings(str(bad_csv))

        assert report.has_errors is True
        assert any("Missing required CSV columns" in i.message for i in report.errors)

    @pytest.mark.fast
    def test_validate_csv_detects_empty_required_fields(self, tmp_path):
        from edgar.xbrl.standardization.utils import validate_csv_mappings

        csv_text = (
            "standard_concept,company_concept,cik,priority,source\n"
            ",us-gaap_Revenue,,1,core\n"  # empty standard_concept
            "Revenue,,,1,core\n"          # empty company_concept
        )
        bad_csv = tmp_path / "empty_fields.csv"
        bad_csv.write_text(csv_text)
        report = validate_csv_mappings(str(bad_csv))

        msgs = [i.message for i in report.errors]
        assert any("Empty standard_concept" in m for m in msgs)
        assert any("Empty company_concept" in m for m in msgs)

    @pytest.mark.fast
    def test_validate_csv_detects_duplicates(self, tmp_path):
        from edgar.xbrl.standardization.utils import validate_csv_mappings

        csv_text = (
            "standard_concept,company_concept,cik,priority,source\n"
            "Revenue,us-gaap_Revenue,,1,core\n"
            "Revenue,us-gaap_Revenue,,1,core\n"  # duplicate
        )
        dup_csv = tmp_path / "dup.csv"
        dup_csv.write_text(csv_text)
        report = validate_csv_mappings(str(dup_csv))

        warns = [i for i in report.warnings if i.category == "duplicate"]
        assert len(warns) >= 1
        assert "Revenue" in warns[0].message

    @pytest.mark.fast
    def test_validate_csv_detects_invalid_priority(self, tmp_path):
        from edgar.xbrl.standardization.utils import validate_csv_mappings

        csv_text = (
            "standard_concept,company_concept,cik,priority,source\n"
            "Revenue,us-gaap_Revenue,,9,core\n"      # priority out of 1-4 range -> warning
            "Revenue,us-gaap_Sales,,abc,core\n"     # non-numeric priority -> error
        )
        bad_csv = tmp_path / "bad_priority.csv"
        bad_csv.write_text(csv_text)
        report = validate_csv_mappings(str(bad_csv))

        # Out-of-range value is a warning
        assert any("Invalid priority value: 9" in i.message for i in report.warnings)
        # Non-numeric is an error
        assert any("Priority must be a number" in i.message for i in report.errors)

    @pytest.mark.fast
    def test_import_mappings_from_csv_classifies_core_vs_company(self, tmp_path, capsys):
        from edgar.xbrl.standardization.utils import import_mappings_from_csv

        csv_text = (
            "standard_concept,company_concept,cik,priority,source\n"
            "Revenue,us-gaap_Revenue,,1,core\n"
            "Revenue,us-gaap_SalesRevenueNet,,1,core\n"
            "Revenue,tsla_AutomotiveRevenue,1318605,2,company\n"
            "NetIncome,us-gaap_NetIncomeLoss,,1,core\n"
        )
        csv_file = tmp_path / "mappings.csv"
        csv_file.write_text(csv_text)

        result = import_mappings_from_csv(str(csv_file), validate=True)

        # Core mappings consolidate by standard_concept
        assert "Revenue" in result["core_mappings"]
        assert sorted(result["core_mappings"]["Revenue"]) == [
            "us-gaap_Revenue",
            "us-gaap_SalesRevenueNet",
        ]
        assert result["core_mappings"]["NetIncome"] == ["us-gaap_NetIncomeLoss"]

        # Company-specific mappings keyed by CIK
        assert "1318605" in result["company_mappings"]
        tsla = result["company_mappings"]["1318605"]
        assert tsla["metadata"]["cik"] == "1318605"
        assert tsla["concept_mappings"]["Revenue"] == ["tsla_AutomotiveRevenue"]

        # Validation report attached
        assert "validation" in result

    @pytest.mark.fast
    def test_import_mappings_skips_rows_with_blank_required_fields(self, tmp_path):
        from edgar.xbrl.standardization.utils import import_mappings_from_csv

        # Note: the importer requires a numeric `priority` field; a totally blank
        # row would crash on int(''). We test the more common case where the
        # required string fields are blank but other fields are populated.
        csv_text = (
            "standard_concept,company_concept,cik,priority,source\n"
            "Revenue,us-gaap_Revenue,,1,core\n"
            ",us-gaap_Lonely,,1,core\n"  # blank std → skipped
            "Revenue,,,1,core\n"          # blank concept → skipped
        )
        csv_file = tmp_path / "blanks.csv"
        csv_file.write_text(csv_text)

        result = import_mappings_from_csv(str(csv_file), validate=False)

        # Only the one well-formed row should produce a mapping
        assert result["core_mappings"] == {"Revenue": ["us-gaap_Revenue"]}
        # validate=False omits validation key
        assert "validation" not in result

    @pytest.mark.fast
    def test_import_mappings_missing_file_raises(self, tmp_path):
        from edgar.xbrl.standardization.utils import import_mappings_from_csv

        with pytest.raises(FileNotFoundError):
            import_mappings_from_csv(str(tmp_path / "nope.csv"))


# ---------------------------------------------------------------------------
# edgar.xbrl.standardization.unmapped_logger
# ---------------------------------------------------------------------------

class TestUnmappedTagLogger:
    """Coverage for the unmapped/ambiguous tag logger and its public API."""

    @pytest.mark.fast
    def test_unmapped_tag_entry_defaults(self):
        from edgar.xbrl.standardization.unmapped_logger import UnmappedTagEntry

        entry = UnmappedTagEntry(concept="us-gaap:Foo", label="Foo")
        assert entry.concept == "us-gaap:Foo"
        assert entry.label == "Foo"
        assert entry.cik is None
        assert entry.confidence == 0.0
        assert entry.suggested_mapping is None
        # timestamp populated by default factory
        assert entry.timestamp  # truthy ISO-8601 string

    @pytest.mark.fast
    def test_ambiguous_resolution_entry_required_fields(self):
        from edgar.xbrl.standardization.unmapped_logger import (
            AmbiguousResolutionEntry,
        )

        entry = AmbiguousResolutionEntry(
            concept="us-gaap:Bar",
            label="Bar",
            candidates=["A", "B"],
            resolved_to="A",
            resolution_method="section",
        )
        assert entry.candidates == ["A", "B"]
        assert entry.resolved_to == "A"
        assert entry.confidence == 1.0  # default

    @pytest.mark.fast
    def test_logger_log_unmapped_increments_count(self):
        from edgar.xbrl.standardization.unmapped_logger import UnmappedTagLogger

        log = UnmappedTagLogger(auto_suggest=False)
        log.log_unmapped(
            concept="us-gaap:NewConcept",
            label="Total Subscription Revenue",
            cik="1234567",
            statement_type="IncomeStatement",
        )
        assert log.unmapped_count == 1
        assert log._unmapped_entries[0].concept == "us-gaap:NewConcept"

    @pytest.mark.fast
    def test_logger_unmapped_dedup_by_concept_and_statement(self):
        from edgar.xbrl.standardization.unmapped_logger import UnmappedTagLogger

        log = UnmappedTagLogger(auto_suggest=False)
        for _ in range(3):
            log.log_unmapped(concept="us-gaap:Foo", label="Foo",
                             statement_type="IncomeStatement")
        # Same (concept, statement_type) → only first is kept
        assert log.unmapped_count == 1

        # Different statement_type counts as a separate entry
        log.log_unmapped(concept="us-gaap:Foo", label="Foo",
                         statement_type="BalanceSheet")
        assert log.unmapped_count == 2

    @pytest.mark.fast
    def test_logger_log_ambiguous_with_dedup(self):
        from edgar.xbrl.standardization.unmapped_logger import UnmappedTagLogger

        log = UnmappedTagLogger()
        for _ in range(2):
            log.log_ambiguous(
                concept="us-gaap:AccountsPayable",
                label="Trade Payables",
                candidates=["TradePayables", "OtherNonCurrentLiabilities"],
                resolved_to="TradePayables",
                resolution_method="section",
                section="Current Liabilities",
            )
        # Same (concept, section, resolved_to) → only one entry
        assert log.ambiguous_count == 1

    @pytest.mark.fast
    def test_logger_clear_resets_all_state(self):
        from edgar.xbrl.standardization.unmapped_logger import UnmappedTagLogger

        log = UnmappedTagLogger()
        log.log_unmapped(concept="A", label="A")
        log.log_ambiguous(concept="B", label="B", candidates=["X"],
                          resolved_to="X", resolution_method="fallback")

        log.clear()

        assert log.unmapped_count == 0
        assert log.ambiguous_count == 0
        assert log._seen_unmapped == set()
        assert log._seen_ambiguous == set()

    @pytest.mark.fast
    def test_logger_stats(self):
        from edgar.xbrl.standardization.unmapped_logger import UnmappedTagLogger

        log = UnmappedTagLogger(auto_suggest=False)
        log.log_unmapped(concept="us-gaap:A", label="A")
        log.log_unmapped(concept="us-gaap:B", label="B")
        log.log_ambiguous(concept="us-gaap:C", label="C", candidates=["X", "Y"],
                          resolved_to="X", resolution_method="section")

        stats = log.stats
        assert stats == {"unmapped_count": 2, "ambiguous_count": 1, "total_count": 3}

    @pytest.mark.fast
    def test_logger_get_unmapped_by_statement_groups(self):
        from edgar.xbrl.standardization.unmapped_logger import UnmappedTagLogger

        log = UnmappedTagLogger(auto_suggest=False)
        log.log_unmapped(concept="A", label="A", statement_type="IncomeStatement")
        log.log_unmapped(concept="B", label="B", statement_type="BalanceSheet")
        log.log_unmapped(concept="C", label="C", statement_type="IncomeStatement")
        log.log_unmapped(concept="D", label="D")  # no statement_type → 'Unknown'

        grouped = log.get_unmapped_by_statement()
        assert set(grouped.keys()) == {"IncomeStatement", "BalanceSheet", "Unknown"}
        assert len(grouped["IncomeStatement"]) == 2
        assert len(grouped["BalanceSheet"]) == 1
        assert len(grouped["Unknown"]) == 1

    @pytest.mark.fast
    def test_logger_high_confidence_suggestions_filter(self):
        from edgar.xbrl.standardization.unmapped_logger import (
            UnmappedTagEntry,
            UnmappedTagLogger,
        )

        log = UnmappedTagLogger(auto_suggest=False)
        # Manually inject entries with varied confidence
        log._unmapped_entries.extend([
            UnmappedTagEntry(concept="A", label="A", suggested_mapping="X", confidence=0.9),
            UnmappedTagEntry(concept="B", label="B", suggested_mapping="Y", confidence=0.5),
            UnmappedTagEntry(concept="C", label="C", suggested_mapping="Z", confidence=0.75),
            UnmappedTagEntry(concept="D", label="D", suggested_mapping=None, confidence=0.95),
        ])

        # Default threshold 0.7 keeps A and C (B too low, D has no suggestion)
        kept = log.get_high_confidence_suggestions()
        kept_concepts = {e.concept for e in kept}
        assert kept_concepts == {"A", "C"}

        # Higher threshold trims to A only
        kept_strict = log.get_high_confidence_suggestions(min_confidence=0.85)
        assert {e.concept for e in kept_strict} == {"A"}

    @pytest.mark.fast
    def test_logger_save_unmapped_csv_roundtrip(self, tmp_path):
        import csv

        from edgar.xbrl.standardization.unmapped_logger import UnmappedTagLogger

        log = UnmappedTagLogger(auto_suggest=False)
        log.log_unmapped(
            concept="us-gaap:NewConcept", label="Total Subscription Revenue",
            cik="1234567", company_name="Example Corp",
            statement_type="IncomeStatement",
            section="Revenue", calculation_parent="Revenues",
            notes="High-priority candidate",
        )

        out = tmp_path / "unmapped.csv"
        count = log.save_unmapped_csv(str(out))

        assert count == 1
        assert out.exists()

        with open(out) as f:
            rows = list(csv.DictReader(f))

        assert len(rows) == 1
        assert rows[0]["concept"] == "us-gaap:NewConcept"
        assert rows[0]["company_name"] == "Example Corp"
        assert rows[0]["statement_type"] == "IncomeStatement"

    @pytest.mark.fast
    def test_logger_save_unmapped_csv_empty_returns_zero(self, tmp_path):
        from edgar.xbrl.standardization.unmapped_logger import UnmappedTagLogger

        log = UnmappedTagLogger()
        count = log.save_unmapped_csv(str(tmp_path / "empty.csv"))
        assert count == 0

    @pytest.mark.fast
    def test_logger_save_to_csv_creates_both_files(self, tmp_path):
        from edgar.xbrl.standardization.unmapped_logger import UnmappedTagLogger

        log = UnmappedTagLogger(auto_suggest=False)
        log.log_unmapped(concept="us-gaap:A", label="A", statement_type="X")
        log.log_ambiguous(
            concept="us-gaap:B", label="B",
            candidates=["P", "Q"], resolved_to="P", resolution_method="section",
            section="Sec",
        )

        unmapped_n, ambiguous_n = log.save_to_csv(str(tmp_path))

        assert unmapped_n == 1
        assert ambiguous_n == 1
        assert (tmp_path / "unmapped_tags.csv").exists()
        assert (tmp_path / "ambiguous_resolutions.csv").exists()

    @pytest.mark.fast
    def test_logger_rich_renders_panel_with_counts(self):
        from edgar.xbrl.standardization.unmapped_logger import UnmappedTagLogger

        log = UnmappedTagLogger(auto_suggest=False)
        log.log_unmapped(concept="A", label="A")
        log.log_ambiguous(concept="B", label="B", candidates=["X"],
                          resolved_to="X", resolution_method="fallback")

        # __rich__ should not raise; output is a Rich Panel
        panel = log.__rich__()
        assert panel is not None
        # Smoke-render to text via Rich's native mechanism
        from rich.console import Console
        from io import StringIO
        buf = StringIO()
        Console(file=buf, force_terminal=False, width=80).print(panel)
        text = buf.getvalue()
        assert "Unmapped Tags" in text
        assert "Ambiguous Resolutions" in text

    @pytest.mark.fast
    def test_module_singleton_get_unmapped_logger(self):
        from edgar.xbrl.standardization import unmapped_logger as ul

        # Reset singleton state to keep tests isolated
        ul._default_logger = None

        a = ul.get_unmapped_logger()
        b = ul.get_unmapped_logger()
        assert a is b
        assert isinstance(a, ul.UnmappedTagLogger)

    @pytest.mark.fast
    def test_module_convenience_log_functions_route_to_singleton(self):
        from edgar.xbrl.standardization import unmapped_logger as ul

        # Fresh singleton to isolate counts
        ul._default_logger = None

        ul.log_unmapped(concept="us-gaap:Convenience", label="Convenience",
                        statement_type="IncomeStatement")
        ul.log_ambiguous(concept="us-gaap:Conv2", label="Conv2",
                         candidates=["X", "Y"], resolved_to="X",
                         resolution_method="section")

        singleton = ul.get_unmapped_logger()
        assert singleton.unmapped_count == 1
        assert singleton.ambiguous_count == 1
