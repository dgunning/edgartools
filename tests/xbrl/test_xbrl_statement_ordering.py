"""Statement ordering for stitched multi-period statements, asserted.

WHAT THIS FILE WAS (edgartools-8m2n). 535 lines, 57 ``print`` calls and ZERO
assertions. Every check computed a boolean, printed "✓ PASS" or "✗ FAIL", and
the test ``return``ed whether they all held -- and a test that returns instead
of asserting always passes, however damning the value it returns. So the suite
was reporting five green tests for statement ordering while three of the checks
inside them printed ✗ FAIL on every run, and nobody was reading the output.

A sixth defect sat in ``test_section_identification``: it built the expected
per-share section and then simply ended, comparing nothing. Neither the
existence-only rule nor the returns-a-value rule in
``test_assertion_strength_ratchet.py`` could see it, because it did not assert
and did not return.

THE THREE FAILING CHECKS WERE TEST BUGS, NOT PRODUCT BUGS. Both were worth
running down rather than deleting, and neither implicated the ordering code:

1. "Gross Profit < Operating Expenses" and "Income Tax < Net Income", in the
   old ``test_apple_ordering_fix``, were fed concepts like ``'Revenue'`` and
   ``'COGS'`` -- bare names in no namespace. ``get_template_position`` returns
   None for every one of them, so the manager had nothing to order by and fell
   back to input order, which the test had deliberately scrambled. Given the
   real ``us-gaap:`` concepts those rows carry in an actual filing, the same
   seven rows come out in exactly canonical order. Both behaviours are now
   asserted: the ordering, and the fallback.

2. "Operating Expenses < R&D Expense (hierarchy preserved)", in
   ``test_presentation_tree``, indexed positions by ``node.label``. Two rows
   share the label "Operating Expenses" -- the abstract parent and the total,
   whose ``latest_label`` is also "Operating Expenses" -- so the dict kept the
   later one and the parent appeared to sit after its own children. The tree
   was right all along; positions are keyed on ``node.concept`` here, which is
   unique.

ALSO REMOVED: three network round-trips. The old file fetched NVDA and AAPL
10-Ks, stitched them, printed the rendered tables and never asserted a thing
about them -- and since nothing here was marked ``network``, those fetches ran
in the fast lane. Every test below is offline and deterministic.
"""
import pytest

from edgar.xbrl.stitching.ordering import (
    FinancialStatementTemplates,
    StatementOrderingManager,
)
from edgar.xbrl.stitching.presentation import VirtualPresentationTree


def ordering_for(rows):
    """Positions the manager assigns to one simulated income statement."""
    manager = StatementOrderingManager("IncomeStatement")
    return manager.determine_ordering(
        [{'statement_type': 'IncomeStatement', 'data': rows}])


@pytest.mark.fast
class TestTemplateMatchingIsConceptBased:
    """A concept in a known taxonomy gets a position; a company extension does not."""

    @pytest.fixture
    def templates(self):
        return FinancialStatementTemplates()

    @pytest.mark.parametrize("concept, label, expected_position", [
        ("us-gaap:Revenue", "Contract Revenue", 6.0),
        ("us-gaap:CostOfGoodsAndServicesSold", "Cost of Goods and Services Sold", 103.0),
        ("us-gaap:ResearchAndDevelopmentExpense", "Research and Development Expense", 301.0),
        ("us-gaap:OperatingIncomeLoss", "Operating Income", 400.0),
        ("us-gaap:NetIncome", "Net Income", 802.0),
    ])
    def test_standard_concepts_get_their_template_position(
            self, templates, concept, label, expected_position):
        assert templates.get_template_position(
            concept, label, "IncomeStatement") == expected_position

    @pytest.mark.parametrize("concept, label", [
        ("aapl:ServicesRevenue", "Services Revenue"),   # company extension
        (None, "Some Random Label"),                    # no concept at all
    ])
    def test_unknown_concepts_get_no_position(self, templates, concept, label):
        """The label alone must not earn a position -- that is the label-based
        matching this system replaced, and it put 'Services Revenue' wherever
        the word 'Revenue' happened to sort."""
        assert templates.get_template_position(concept, label, "IncomeStatement") is None

    @pytest.mark.parametrize("raw, normalized", [
        ("us-gaap:Revenue", "us-gaap_revenue"),
        ("us-gaap_Revenue", "us-gaap_revenue"),
        ("usgaap:Revenue", "us-gaap_revenue"),
        ("gaap:Revenue", "us-gaap_revenue"),
        ("AAPL:CustomConcept", "aapl_customconcept"),
    ])
    def test_concept_normalization(self, templates, raw, normalized):
        assert templates._normalize_xbrl_concept(raw) == normalized


@pytest.mark.fast
class TestScrambledStatementIsRestoredToCanonicalOrder:
    """The reason this machinery exists: filings disagree on row order."""

    SCRAMBLED = [
        {'concept': 'us-gaap:NetIncomeLoss', 'label': 'Net Income'},
        {'concept': 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
         'label': 'Contract Revenue'},
        {'concept': 'us-gaap:OperatingExpenses', 'label': 'Operating Expenses'},
        {'concept': 'us-gaap:CostOfGoodsAndServicesSold',
         'label': 'Cost of Goods and Services Sold'},
        {'concept': 'us-gaap:OperatingIncomeLoss', 'label': 'Operating Income'},
        {'concept': 'us-gaap:IncomeTaxExpenseBenefit', 'label': 'Income Tax Expense'},
        {'concept': 'us-gaap:GrossProfit', 'label': 'Gross Profit'},
    ]

    def test_positions_are_the_canonical_sequence(self):
        """Exact positions, not just relative order -- a run that assigned every
        row the same position would satisfy "revenue before net income" for
        half the pairs by luck."""
        ordering = ordering_for(self.SCRAMBLED)
        by_concept = {c: p for c, p in ordering.items() if c.startswith('us-gaap:')}
        assert by_concept == {
            'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax': 0.0,
            'us-gaap:CostOfGoodsAndServicesSold': 100.0,
            'us-gaap:GrossProfit': 200.0,
            'us-gaap:OperatingExpenses': 300.0,
            'us-gaap:OperatingIncomeLoss': 400.0,
            'us-gaap:IncomeTaxExpenseBenefit': 700.0,
            'us-gaap:NetIncomeLoss': 800.0,
        }

    def test_income_statement_reads_top_to_bottom(self):
        """The same claim as a reader would state it."""
        ordering = ordering_for(self.SCRAMBLED)
        sequence = [c for c, _ in sorted(
            ((c, p) for c, p in ordering.items() if c.startswith('us-gaap:')),
            key=lambda item: item[1])]
        assert sequence.index('us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax') \
            < sequence.index('us-gaap:CostOfGoodsAndServicesSold') \
            < sequence.index('us-gaap:GrossProfit') \
            < sequence.index('us-gaap:OperatingIncomeLoss') \
            < sequence.index('us-gaap:IncomeTaxExpenseBenefit') \
            < sequence.index('us-gaap:NetIncomeLoss')

    def test_unmatchable_concepts_fall_back_to_input_order(self):
        """Documented because it was mistaken for a bug for as long as this file
        has existed. Concepts outside any known taxonomy give the manager
        nothing to order by, so it preserves the order it was handed rather
        than inventing one."""
        rows = [{'concept': c, 'label': label} for c, label in [
            ('NetIncome', 'Net Income'), ('Revenue', 'Contract Revenue'),
            ('OpExp', 'Operating Expenses'), ('COGS', 'Cost of Goods and Services Sold'),
        ]]
        ordering = ordering_for(rows)
        assert [ordering[r['concept']] for r in rows] == [0.0, 1.0, 2.0, 3.0]


@pytest.mark.fast
class TestPerShareDataStaysGroupedAtTheEnd:
    """NVIDIA-shaped input: per-share rows interleaved with the main statement.

    They must end up together, after net income, whatever order they arrive in.
    """

    ROWS = [
        {'concept': 'us-gaap:Revenue', 'label': 'Revenue'},
        {'concept': 'us-gaap:InterestIncomeExpenseNet', 'label': 'Interest income'},
        {'concept': 'us-gaap:IncomeLossBeforeIncomeTaxes', 'label': 'Income before income tax'},
        # Per-share rows arriving early, which is what used to scatter them
        {'concept': 'us-gaap:WeightedAverageNumberOfSharesOutstandingBasic',
         'label': 'Shares Outstanding (Basic)'},
        {'concept': 'us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding',
         'label': 'Shares Outstanding (Diluted)'},
        {'concept': 'us-gaap:CostOfRevenue', 'label': 'Total Cost of Revenue'},
        {'concept': 'us-gaap:GrossProfit', 'label': 'Gross Profit'},
        {'concept': 'us-gaap:ResearchAndDevelopmentExpense', 'label': 'Research and Development Expense'},
        {'concept': 'us-gaap:OperatingIncomeLoss', 'label': 'Operating Income'},
        {'concept': 'us-gaap:NetIncome', 'label': 'Net Income'},
        {'concept': 'us-gaap:EarningsPerShareBasic', 'label': 'Earnings Per Share (Basic)'},
        {'concept': 'us-gaap:EarningsPerShareDiluted', 'label': 'Earnings Per Share (Diluted)'},
    ]

    PER_SHARE = [
        'us-gaap:EarningsPerShareBasic',
        'us-gaap:EarningsPerShareDiluted',
        'us-gaap:WeightedAverageNumberOfSharesOutstandingBasic',
        'us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding',
    ]

    @pytest.fixture
    def ordering(self):
        return ordering_for(self.ROWS)

    def test_main_statement_order(self, ordering):
        assert ordering['us-gaap:Revenue'] == 0.0
        assert ordering['us-gaap:CostOfRevenue'] == 100.0
        assert ordering['us-gaap:GrossProfit'] == 200.0
        assert ordering['us-gaap:OperatingIncomeLoss'] == 400.0
        assert ordering['us-gaap:NetIncome'] == 800.0

    def test_per_share_rows_come_after_every_other_row(self, ordering):
        per_share = [ordering[c] for c in self.PER_SHARE]
        others = [p for c, p in ordering.items()
                  if c.startswith('us-gaap:') and c not in self.PER_SHARE]
        assert min(per_share) > max(others), (
            f"per-share rows at {sorted(per_share)} are not all after the last "
            f"statement row at {max(others)}"
        )

    def test_per_share_rows_are_contiguous_and_in_order(self, ordering):
        """The old check allowed a gap of up to 2.0 between the two EPS rows and
        skipped itself entirely if either was missing. The positions are
        deterministic, so they are asserted."""
        assert [ordering[c] for c in self.PER_SHARE] == [950.0, 950.2, 950.4, 950.6]


@pytest.mark.fast
class TestSectionIdentification:
    """Completes the test that computed an expectation and never compared it."""

    TEMPLATE_POSITIONED = {
        'us-gaap:Revenue': 6.0,
        'us-gaap:CostOfRevenue': 100.0,
        'us-gaap:GrossProfit': 200.0,
        'us-gaap:ResearchAndDevelopmentExpense': 301.0,
        'us-gaap:OperatingIncomeLoss': 400.0,
        'us-gaap:NetIncome': 802.0,
        'us-gaap:EarningsPerShareBasic': 901.0,
        'us-gaap:EarningsPerShareDiluted': 902.0,
        'us-gaap:WeightedAverageNumberOfSharesOutstandingBasic': 904.0,
        'us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding': 905.0,
    }

    def test_sections(self):
        manager = StatementOrderingManager("IncomeStatement")
        sections = manager._identify_template_sections(self.TEMPLATE_POSITIONED)
        assert sections == {
            'revenue_section': ['us-gaap:Revenue'],
            'cost_section': ['us-gaap:CostOfRevenue'],
            'gross_profit': ['us-gaap:GrossProfit'],
            'operating_expenses': ['us-gaap:ResearchAndDevelopmentExpense'],
            'operating_income': ['us-gaap:OperatingIncomeLoss'],
            'net_income': ['us-gaap:NetIncome'],
            'per_share': [
                'us-gaap:EarningsPerShareBasic',
                'us-gaap:EarningsPerShareDiluted',
                'us-gaap:WeightedAverageNumberOfSharesOutstandingBasic',
                'us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding',
            ],
        }


@pytest.mark.fast
class TestPresentationTreePreservesHierarchy:
    """An abstract parent keeps its children, and a total stays below them."""

    METADATA = {
        'Contract Revenue': {'level': 0, 'latest_label': 'Contract Revenue', 'is_abstract': False,
                             'is_total': False, 'original_concept': 'Revenue'},
        'Cost of Goods and Services Sold': {'level': 0, 'latest_label': 'Cost of Goods and Services Sold',
                                            'is_abstract': False, 'is_total': False, 'original_concept': 'COGS'},
        'Gross Profit': {'level': 0, 'latest_label': 'Gross Profit', 'is_abstract': False,
                         'is_total': False, 'original_concept': 'GrossProfit'},
        'Operating Expenses': {'level': 0, 'latest_label': 'Operating Expenses', 'is_abstract': True,
                               'is_total': False, 'original_concept': 'OpExpenses'},
        'Research and Development Expense': {'level': 1, 'latest_label': 'Research and Development Expense',
                                             'is_abstract': False, 'is_total': False, 'original_concept': 'RnD'},
        'Selling, General and Administrative Expense': {
            'level': 1, 'latest_label': 'Selling, General and Administrative Expense',
            'is_abstract': False, 'is_total': False, 'original_concept': 'SGA'},
        'Total Operating Expenses': {'level': 0, 'latest_label': 'Operating Expenses', 'is_abstract': False,
                                     'is_total': True, 'original_concept': 'TotalOpExp'},
        'Operating Income': {'level': 0, 'latest_label': 'Operating Income', 'is_abstract': False,
                             'is_total': False, 'original_concept': 'OpIncome'},
        'Net Income': {'level': 0, 'latest_label': 'Net Income', 'is_abstract': False,
                       'is_total': False, 'original_concept': 'NetIncome'},
        'Earnings Per Share (Basic)': {'level': 1, 'latest_label': 'Earnings Per Share (Basic)',
                                       'is_abstract': False, 'is_total': False, 'original_concept': 'EPSBasic'},
        'Earnings Per Share (Diluted)': {'level': 1, 'latest_label': 'Earnings Per Share (Diluted)',
                                         'is_abstract': False, 'is_total': False, 'original_concept': 'EPSDiluted'},
    }

    ORIGINAL_ORDER = [
        'Contract Revenue',
        'Cost of Goods and Services Sold',
        'Gross Profit',
        'Operating Expenses',                          # abstract parent
        'Research and Development Expense',            # child
        'Selling, General and Administrative Expense',  # child
        'Total Operating Expenses',                    # total for the section
        'Operating Income',
        'Net Income',
        'Earnings Per Share (Basic)',
        'Earnings Per Share (Diluted)',
    ]

    CONCEPT_ORDERING = {
        'Contract Revenue': 0.0,
        'Cost of Goods and Services Sold': 100.0,
        'Gross Profit': 200.0,
        'Operating Expenses': 300.0,
        'Research and Development Expense': 300.1,
        'Selling, General and Administrative Expense': 300.2,
        'Total Operating Expenses': 300.9,
        'Operating Income': 400.0,
        'Net Income': 800.0,
        'Earnings Per Share (Basic)': 900.1,
        'Earnings Per Share (Diluted)': 900.2,
    }

    @pytest.fixture
    def nodes(self):
        tree = VirtualPresentationTree(StatementOrderingManager("IncomeStatement"))
        return tree.build_tree(self.METADATA, self.CONCEPT_ORDERING, self.ORIGINAL_ORDER)

    def test_every_row_survives_the_tree(self, nodes):
        assert len(nodes) == len(self.ORIGINAL_ORDER)

    def test_rendered_sequence(self, nodes):
        """Keyed on node.concept, which is unique. The old version keyed on
        node.label, and 'Operating Expenses' names two different rows."""
        assert [(n.concept, n.level) for n in nodes] == [
            ('Contract Revenue', 0),
            ('Cost of Goods and Services Sold', 0),
            ('Gross Profit', 0),
            ('Operating Expenses', 0),                            # abstract parent
            ('Research and Development Expense', 1),              # its children,
            ('Selling, General and Administrative Expense', 1),   # indented
            ('Total Operating Expenses', 0),                      # the total, below them
            ('Operating Income', 0),
            ('Net Income', 0),
            ('Earnings Per Share (Basic)', 1),
            ('Earnings Per Share (Diluted)', 1),
        ]

    def test_children_sit_between_their_parent_and_its_total(self, nodes):
        """The hierarchy claim on its own, so a failure says which rule broke."""
        at = {n.concept: i for i, n in enumerate(nodes)}
        assert at['Operating Expenses'] < at['Research and Development Expense']
        assert at['Research and Development Expense'] < at['Selling, General and Administrative Expense']
        assert at['Selling, General and Administrative Expense'] < at['Total Operating Expenses']
        assert at['Total Operating Expenses'] < at['Operating Income'] < at['Net Income']
