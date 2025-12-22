import types

import edgar.llm_extraction as llm


def test_default_selects_all_statements(monkeypatch):
    calls = []

    monkeypatch.setattr(llm, "_is_report_like", lambda filing: False)
    monkeypatch.setattr(llm, "_extract_item_sections", lambda filing, item: [])
    monkeypatch.setattr(llm, "_extract_category_sections", lambda filing, category, max_reports: calls.append(("cat", category)) or [])
    monkeypatch.setattr(
        llm,
        "_extract_statement_sections",
        lambda filing, statement, max_reports: calls.append(("stmt", statement)) or ["S"],
    )

    sections = llm.extract_filing_sections(object())

    assert sections == ["S"]
    assert calls == [("stmt", "AllStatements")]


def test_notes_flag_adds_notes_category(monkeypatch):
    calls = []

    monkeypatch.setattr(llm, "_is_report_like", lambda filing: False)
    monkeypatch.setattr(llm, "_extract_item_sections", lambda filing, item: [])
    monkeypatch.setattr(
        llm,
        "_extract_category_sections",
        lambda filing, category, max_reports: calls.append(("cat", category)) or ["C"],
    )
    monkeypatch.setattr(
        llm,
        "_extract_statement_sections",
        lambda filing, statement, max_reports: calls.append(("stmt", statement)) or ["S"],
    )

    sections = llm.extract_filing_sections(object(), notes=True)

    # categories are processed before statements in extract_filing_sections
    assert sections == ["C", "S"]
    assert calls == [("cat", "Notes"), ("stmt", "AllStatements")]
