"""
TOC Section Detection Evaluation Suite.

Measures section extraction accuracy across filing agents (Workiva, Donnelley,
Toppan Merrill, Novaworks) using a fixed corpus of 20 10-K filings.

Run:  python -m pytest tests/evaluation/test_toc_evaluation.py -xvs
"""

import pytest
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from collections import defaultdict

from edgar import Filing
from edgar.documents.agents import detect_filing_agent

# Standard 10-K items that every filing should have
STANDARD_10K_ITEMS = [
    ('1', 'Business'),
    ('1A', 'Risk Factors'),
    ('1B', 'Unresolved Staff Comments'),
    ('1C', 'Cybersecurity'),
    ('2', 'Properties'),
    ('3', 'Legal Proceedings'),
    ('4', 'Mine Safety Disclosures'),
    ('5', 'Market Information'),
    ('6', 'Reserved'),
    ('7', 'MD&A'),
    ('7A', 'Quantitative Disclosures'),
    ('8', 'Financial Statements'),
    ('9', 'Disagreements with Accountants'),
    ('9A', 'Controls and Procedures'),
    ('9B', 'Other Information'),
    ('9C', 'Foreign Jurisdictions'),
    ('10', 'Directors and Officers'),
    ('11', 'Executive Compensation'),
    ('12', 'Security Ownership'),
    ('13', 'Certain Relationships'),
    ('14', 'Accountant Fees'),
    ('15', 'Exhibits'),
]

# Items that should have substantive content (not just incorporated by reference)
CONTENT_ITEMS = {'1', '1A', '1C', '7', '7A', '8', '9A', '15'}


@dataclass
class FilingTestCase:
    ticker: str
    cik: int
    company: str
    form: str
    filing_date: str
    accession_no: str
    agent: str


@dataclass
class SectionResult:
    item: str
    title: str
    found: bool = False
    has_content: bool = False
    content_length: int = 0
    detection_method: Optional[str] = None
    confidence: float = 0.0


@dataclass
class FilingResult:
    test_case: FilingTestCase
    detected_agent: Optional[str] = None
    sections: Dict[str, SectionResult] = field(default_factory=dict)
    total_items: int = 0
    found_items: int = 0
    items_with_content: int = 0
    detection_rate: float = 0.0
    content_rate: float = 0.0


# ---- Test Corpus ----

WORKIVA_FILINGS = [
    FilingTestCase('AAPL', 320193, 'Apple Inc.', '10-K', '2025-10-31', '0000320193-25-000079', 'Workiva'),
    FilingTestCase('GOOGL', 1652044, 'Alphabet Inc.', '10-K', '2026-02-05', '0001652044-26-000018', 'Workiva'),
    FilingTestCase('AMZN', 1018724, 'AMAZON COM INC', '10-K', '2026-02-06', '0001018724-26-000004', 'Workiva'),
    FilingTestCase('JPM', 19617, 'JPMORGAN CHASE & CO', '10-K', '2026-02-13', '0001628280-26-008131', 'Workiva'),
    FilingTestCase('TSLA', 1318605, 'Tesla, Inc.', '10-K', '2026-01-29', '0001628280-26-003952', 'Workiva'),
]

DONNELLEY_FILINGS = [
    FilingTestCase('MSFT', 789019, 'MICROSOFT CORP', '10-K', '2025-07-30', '0000950170-25-100235', 'Donnelley'),
    FilingTestCase('ORCL', 1341439, 'ORACLE CORP', '10-K', '2025-06-18', '0000950170-25-087926', 'Donnelley'),
    FilingTestCase('BLK', 2012383, 'BlackRock, Inc.', '10-K', '2026-02-25', '0001193125-26-071966', 'Donnelley'),
    FilingTestCase('BRKR', 1109354, 'BRUKER CORP', '10-K', '2026-02-27', '0001193125-26-082523', 'Donnelley'),
    FilingTestCase('ACHC', 1520697, 'Acadia Healthcare Company, Inc.', '10-K', '2026-02-27', '0001193125-26-078266', 'Donnelley'),
]

TOPPAN_FILINGS = [
    FilingTestCase('BHB', 743367, 'BAR HARBOR BANKSHARES', '10-K', '2026-03-13', '0001104659-26-027217', 'Toppan Merrill'),
    FilingTestCase('LOCO', 1606366, 'El Pollo Loco Holdings, Inc.', '10-K', '2026-03-13', '0001606366-26-000017', 'Toppan Merrill'),
    FilingTestCase('ANVS', 1477845, 'Annovis Bio, Inc.', '10-K', '2026-03-13', '0001104659-26-027751', 'Toppan Merrill'),
    FilingTestCase('ELUT', 1708527, 'ELUTIA INC.', '10-K', '2026-03-13', '0001104659-26-027664', 'Toppan Merrill'),
    FilingTestCase('EP', 887396, 'EMPIRE PETROLEUM CORP', '10-K', '2026-03-13', '0001104659-26-027675', 'Toppan Merrill'),
]

NOVAWORKS_FILINGS = [
    FilingTestCase('BMNM', 1275477, 'BIMINI CAPITAL MANAGEMENT, INC.', '10-K', '2026-03-13', '0001437749-26-008139', 'Novaworks'),
    FilingTestCase('CRVO', 1053691, 'CervoMed Inc.', '10-K', '2026-03-13', '0001437749-26-008259', 'Novaworks'),
    FilingTestCase('CDIO', 1870144, 'Cardio Diagnostics Holdings, Inc.', '10-K', '2026-03-13', '0001553350-26-000023', 'Novaworks'),
    FilingTestCase('CLOQ', 1437517, 'CYBERLOQ TECHNOLOGIES, INC.', '10-K', '2026-03-13', '0001493152-26-010037', 'Novaworks'),
    FilingTestCase('BAYVU', 1969475, 'Bayview Acquisition Corp', '10-K', '2026-03-13', '0001493152-26-010101', 'Novaworks'),
]

ALL_FILINGS = WORKIVA_FILINGS + DONNELLEY_FILINGS + TOPPAN_FILINGS + NOVAWORKS_FILINGS


def evaluate_filing(test_case: FilingTestCase) -> FilingResult:
    """Evaluate section detection for a single filing."""
    filing = Filing(
        cik=test_case.cik,
        company=test_case.company,
        form=test_case.form,
        filing_date=test_case.filing_date,
        accession_no=test_case.accession_no,
    )

    result = FilingResult(test_case=test_case)
    result.detected_agent = filing.agent

    # Parse sections via the document pipeline
    try:
        from edgar.documents.parser import HTMLParser
        from edgar.documents.config import ParserConfig

        html_content = filing.html()
        if not html_content:
            return result

        config = ParserConfig(form='10-K', detect_sections=True)
        parser = HTMLParser(config)
        document = parser.parse(html_content)
        sections = document.sections
    except Exception as e:
        print(f"  ERROR parsing {test_case.ticker}: {e}")
        return result

    # Evaluate each standard item
    for item_num, item_title in STANDARD_10K_ITEMS:
        sr = SectionResult(item=item_num, title=item_title)

        section = sections.get_item(item_num) if sections else None
        if section:
            sr.found = True
            sr.detection_method = section.detection_method
            sr.confidence = section.confidence
            try:
                text = section.text()
                if text and len(text.strip()) > 50:
                    sr.has_content = True
                    sr.content_length = len(text)
            except Exception:
                pass

        result.sections[item_num] = sr

    # Compute summary metrics
    result.total_items = len(STANDARD_10K_ITEMS)
    result.found_items = sum(1 for s in result.sections.values() if s.found)
    result.items_with_content = sum(1 for s in result.sections.values() if s.has_content)
    result.detection_rate = result.found_items / result.total_items if result.total_items else 0
    result.content_rate = (
        sum(1 for item in CONTENT_ITEMS if result.sections.get(item, SectionResult(item=item, title='')).has_content)
        / len(CONTENT_ITEMS)
    )

    return result


def print_summary(results: List[FilingResult]):
    """Print a summary table of evaluation results."""
    print()
    print("=" * 110)
    print(f"{'Ticker':<8} {'Agent':<16} {'Detected':<16} {'Found':>5} {'/ Tot':>5} {'Rate':>6} {'Content':>8} {'Methods'}")
    print("-" * 110)

    by_agent = defaultdict(list)
    for r in results:
        by_agent[r.test_case.agent].append(r)
        methods = set(s.detection_method for s in r.sections.values() if s.found and s.detection_method)
        method_str = ', '.join(sorted(methods)) if methods else '-'
        print(
            f"{r.test_case.ticker:<8} {r.test_case.agent:<16} {str(r.detected_agent or '?'):<16} "
            f"{r.found_items:>5} / {r.total_items:<3}  {r.detection_rate:>5.0%}  "
            f"{r.items_with_content:>5}     {method_str}"
        )

    print("-" * 110)
    print("\nPer-agent averages:")
    print(f"{'Agent':<16} {'Avg Detection':>14} {'Avg Content':>12} {'Filings':>8}")
    print("-" * 55)
    for agent in ['Workiva', 'Donnelley', 'Toppan Merrill', 'Novaworks']:
        agent_results = by_agent.get(agent, [])
        if agent_results:
            avg_det = sum(r.detection_rate for r in agent_results) / len(agent_results)
            avg_cont = sum(r.content_rate for r in agent_results) / len(agent_results)
            print(f"{agent:<16} {avg_det:>13.0%} {avg_cont:>11.0%} {len(agent_results):>8}")

    overall_det = sum(r.detection_rate for r in results) / len(results) if results else 0
    overall_cont = sum(r.content_rate for r in results) / len(results) if results else 0
    print(f"{'OVERALL':<16} {overall_det:>13.0%} {overall_cont:>11.0%} {len(results):>8}")
    print("=" * 110)


# ---- Tests ----

@pytest.mark.network
class TestTOCEvaluation:
    """Evaluation suite — run with: pytest tests/evaluation/test_toc_evaluation.py -xvs"""

    @pytest.fixture(scope='class')
    def all_results(self) -> List[FilingResult]:
        results = []
        for tc in ALL_FILINGS:
            print(f"\nEvaluating {tc.ticker} ({tc.agent})...")
            result = evaluate_filing(tc)
            print(f"  Detected: {result.detected_agent}, Found: {result.found_items}/{result.total_items}, Content: {result.items_with_content}")
            results.append(result)
        print_summary(results)
        return results

    def test_agent_detection_correct(self, all_results: List[FilingResult]):
        """Every filing's detected agent should match the expected agent."""
        for r in all_results:
            assert r.detected_agent == r.test_case.agent, (
                f"{r.test_case.ticker}: expected agent '{r.test_case.agent}', "
                f"got '{r.detected_agent}'"
            )

    def test_minimum_detection_rate(self, all_results: List[FilingResult]):
        """Most filings should detect at least 5 sections (baseline sanity)."""
        low_detection = [r for r in all_results if r.found_items < 5]
        # Allow up to 25% of filings to have low detection (known baseline gaps)
        max_allowed = len(all_results) // 4
        assert len(low_detection) <= max_allowed, (
            f"{len(low_detection)} filings below 5 sections (max allowed {max_allowed}): "
            + ", ".join(f"{r.test_case.ticker}={r.found_items}" for r in low_detection)
        )

    def test_content_items_have_text(self, all_results: List[FilingResult]):
        """Key content items (1, 1A, 7, 8) should have text when detected."""
        key_items = {'1', '1A', '7', '8'}
        for r in all_results:
            for item in key_items:
                sr = r.sections.get(item)
                if sr and sr.found:
                    # Warn but don't fail — this is a baseline measurement
                    if not sr.has_content:
                        print(f"  WARN: {r.test_case.ticker} Item {item} found but no content")

    def test_overall_summary(self, all_results: List[FilingResult]):
        """Print overall summary (always passes — this is for capturing the baseline)."""
        print_summary(all_results)
