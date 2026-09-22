"""A declared cash flow statement must be reachable (edgartools-gi1n).

WHAT WAS BROKEN. Vale S.A.'s 20-F declares exactly one role typed
CashFlowStatement -- "00000005 - Statement - Consolidated Statement of Cash
Flows" -- and ``statements.cashflow_statement()`` returned None for it.
``find_statement("CashFlowStatement")`` raised *"No matching statements found.
No statements available. No statements available in XBRL data"*, while income
statement, balance sheet, comprehensive income and statement of equity all
resolved from the same XBRL. Stitching across filings inherited the hole and
produced an empty statement, which the #683 regression test had been written
to accept as normal.

THE MECHANISM. Not role detection -- the role was found and correctly typed at
every cascade step. It was the essential-concept gate added for issue #659
(``_validate_statement``), which requires a candidate to carry at least half
of the concept groups in ``ESSENTIAL_CONCEPTS[statement_type]``. For cash flow
those groups were "operating" and "cash_change", and Vale's role satisfied
neither:

    operating    wanted  ifrs-full_CashFlowsFromUsedInOperatingActivities
                 has     ifrs-full_CashFlowsFromUsedInOperations       (subtotal
                         before interest and tax, which IAS 7 permits)
                 and     vale_CashFlowFromUsedInOperatingActivities    (the
                         total, in the company's own namespace)

    cash_change  wanted  ifrs-full_IncreaseDecreaseInCashAndCashEquivalents
                 has     ifrs-full_IncreaseDecreaseInCashAndCashEquivalents
                             BeforeEffectOfExchangeRateChanges

So 0 of 2 groups, every candidate filtered out, and a filing that plainly
contains a cash flow statement reported as having none. A filer that puts its
operating TOTAL in an extension concept cannot be matched by any list of
standard concepts, which is why the fix reaches for the standard subtotal
above it rather than trying to enumerate extensions.

THE FIX. Two IFRS elements added to ``ESSENTIAL_CONCEPTS["CashFlowStatement"]``
in ``edgar/xbrl/statement_resolver.py``. Checked against 20 filers (10 IFRS
20-F filers, 10 US GAAP): every one resolved to the same role and the same row
count as before, and Vale went from nothing to its 43-row statement.
"""
import pytest

from edgar.xbrl.statement_resolver import StatementResolver

# Verbatim from Vale's 20-F 0001292814-26-001844: the statement entry
# get_all_statements() produces, and the 32 concepts in its presentation tree.
VALE_STATEMENT = {
    'role': 'http://vale.com/role/StatementOfCashFlows',
    'definition': '00000005 - Statement - Consolidated Statement of Cash Flows',
    'element_count': 32,
    'type': 'CashFlowStatement',
    'primary_concept': 'ifrs-full_StatementOfCashFlowsAbstract',
    'role_name': 'StatementOfCashFlows',
    'category': None,
    'menu_category': 'Statements',
}

VALE_CONCEPTS = [
    'ifrs-full_StatementOfCashFlowsAbstract',
    'ifrs-full_CashFlowsFromUsedInOperations',
    'vale_PaymentOfInterestOnLoansFinancingAndOtherFinancialLiabilities',
    'vale_ReceiptsFromSettlementOfDerivativesNet',
    'vale_PaymentsRelatedToBrumadinhoEventClassifiedAsOperatingActivities',
    'vale_PaymentsRelatedToDeCharacterizationOfDamsClassifiedAsOperatingActivities',
    'vale_InterestOnParticipativeStockholdersDebenturesPaidClassifiedAsOperatingActivities',
    'vale_IncomeTaxesPaidIncludingPaymentsUnderSettlementProgram',
    'vale_CashFlowFromUsedInOperatingActivities',
    'ifrs-full_CashFlowsFromUsedInInvestingActivitiesAbstract',
    'vale_AcquisitionOfPropertyPlantAndEquipmentAndIntangibleAssets',
    'vale_PaymentsRelatedToSamarcoDamFailure',
    'vale_AdvancedPaymentRelatedToRenegotiationOfRailwayConcessionContracts',
    'vale_ProceedsFromCashReceivedPaidFromDisposalAndAcquisitionOfInvestmentsNet',
    'ifrs-full_DividendsReceivedClassifiedAsInvestingActivities',
    'ifrs-full_CashFlowsFromUsedInDecreaseIncreaseInShorttermDepositsAndInvestments',
    'ifrs-full_OtherInflowsOutflowsOfCashClassifiedAsInvestingActivities',
    'ifrs-full_CashFlowsFromUsedInInvestingActivities',
    'ifrs-full_CashFlowsFromUsedInFinancingActivitiesAbstract',
    'vale_NetRepaymentsOfBorrowingsClassifiedAsFinancingActivities',
    'ifrs-full_RepaymentsOfBorrowingsClassifiedAsFinancingActivities',
    'ifrs-full_PaymentsOfLeaseLiabilitiesClassifiedAsFinancingActivities',
    'ifrs-full_DividendsPaidToEquityHoldersOfParentClassifiedAsFinancingActivities',
    'ifrs-full_DividendsPaidToNoncontrollingInterestsClassifiedAsFinancingActivities',
    'ifrs-full_PaymentsToAcquireOrRedeemEntitysShares',
    'vale_IssuanceOfSubordinatedNotes',
    'vale_AcquisitionOfStakeInVopc',
    'ifrs-full_CashFlowsFromUsedInFinancingActivities',
    'ifrs-full_IncreaseDecreaseInCashAndCashEquivalentsBeforeEffectOfExchangeRateChanges',
    'ifrs-full_CashAndCashEquivalents',
    'ifrs-full_EffectOfExchangeRateChangesOnCashAndCashEquivalents',
    'vale_EffectOfDisposalsOfSubsidiariesAndMergerNetOnCashAndCashEquivalents',
]


class _Tree:
    def __init__(self, concepts):
        self.all_nodes = dict.fromkeys(concepts)


class _StubXBRL:
    """The two surfaces the resolver reads: the statement list and the trees."""

    entity_name = 'VALE S.A.'
    cik = 917851
    period_of_report = '2025-12-31'

    def __init__(self, statements, trees):
        self._statements = statements
        self.presentation_trees = trees

    def get_all_statements(self):
        return self._statements


@pytest.mark.fast
class TestValidationAcceptsTheIFRSCashFlowShape:
    """Offline, from the concepts alone — no filing fetched."""

    @pytest.fixture
    def resolver(self):
        return StatementResolver(_StubXBRL(
            [VALE_STATEMENT],
            {VALE_STATEMENT['role']: _Tree(VALE_CONCEPTS)},
        ))

    def test_validation_passes(self, resolver):
        is_valid, confidence, reason = resolver._validate_statement(
            VALE_STATEMENT, 'CashFlowStatement')
        assert is_valid, f"cash flow role rejected: {reason}"
        assert confidence == 1.0, (
            f"only {confidence:.0%} of the essential groups matched ({reason}). "
            "Both should: the operating subtotal is CashFlowsFromUsedInOperations "
            "and the change in cash is the before-exchange-rate-effect element."
        )

    def test_find_statement_returns_the_role(self, resolver):
        """The bug in one call: this raised StatementNotFound."""
        statements, role, canonical, conf = resolver.find_statement('CashFlowStatement')
        assert role == 'http://vale.com/role/StatementOfCashFlows'
        assert canonical == 'CashFlowStatement'
        assert [s['definition'] for s in statements] == [VALE_STATEMENT['definition']]
        assert conf >= 0.7, f"resolved at only {conf} confidence"

    def test_a_role_with_neither_group_is_still_rejected(self, resolver):
        """The gate must still do its job — this is what #659 added it for.

        A disclosure that merely mentions cash, with none of the section
        totals, must not become the cash flow statement.
        """
        note = dict(VALE_STATEMENT, role='http://vale.com/role/CashNote')
        resolver.xbrl.presentation_trees[note['role']] = _Tree([
            'ifrs-full_CashAndCashEquivalents',
            'ifrs-full_EffectOfExchangeRateChangesOnCashAndCashEquivalents',
        ])
        is_valid, confidence, _reason = resolver._validate_statement(
            note, 'CashFlowStatement')
        assert not is_valid
        assert confidence == 0.0


@pytest.mark.network
@pytest.mark.regression
class TestValeCashFlowIsReachable:
    """Against the filing, with the figures Vale reported.

    Vale's 20-F for FY2025 (0001292814-26-001844), in millions of US dollars:

        cash flows from operations              13,401
        net cash generated by operating          8,801
        net cash used in investing              (6,864)
        net cash generated by financing            270
        net increase in cash                     2,207
        cash and cash equivalents, year end      7,372

    The three activity totals sum to the net increase, which is the check that
    no line was dropped or misparsed: 8,801 - 6,864 + 270 = 2,207.
    """

    ACCESSION = '0001292814-26-001844'
    FY2025 = '2025-12-31 (FY)'

    @pytest.fixture(scope="class")
    def cashflow_df(self):
        from edgar import get_by_accession_number
        filing = get_by_accession_number(self.ACCESSION)
        assert filing is not None, f"could not fetch {self.ACCESSION}"
        statement = filing.xbrl().statements.cashflow_statement()
        assert statement is not None, (
            "cashflow_statement() returned None for a filing that declares a "
            "Consolidated Statement of Cash Flows — edgartools-gi1n has returned"
        )
        return statement.to_dataframe()

    def value(self, df, concept):
        rows = df[df['concept'] == concept]
        assert len(rows) == 1, f"expected one {concept} row, found {len(rows)}"
        return rows.iloc[0][self.FY2025]

    def test_section_totals(self, cashflow_df):
        assert self.value(cashflow_df, 'ifrs-full_CashFlowsFromUsedInOperations') == 13_401_000_000
        assert self.value(cashflow_df, 'vale_CashFlowFromUsedInOperatingActivities') == 8_801_000_000
        assert self.value(cashflow_df, 'ifrs-full_CashFlowsFromUsedInInvestingActivities') == -6_864_000_000
        assert self.value(cashflow_df, 'ifrs-full_CashFlowsFromUsedInFinancingActivities') == 270_000_000

    def test_the_totals_reconcile(self, cashflow_df):
        operating = self.value(cashflow_df, 'vale_CashFlowFromUsedInOperatingActivities')
        investing = self.value(cashflow_df, 'ifrs-full_CashFlowsFromUsedInInvestingActivities')
        financing = self.value(cashflow_df, 'ifrs-full_CashFlowsFromUsedInFinancingActivities')
        net_change = self.value(
            cashflow_df,
            'ifrs-full_IncreaseDecreaseInCashAndCashEquivalentsBeforeEffectOfExchangeRateChanges')
        assert operating + investing + financing == net_change == 2_207_000_000, (
            f"{operating:,} + {investing:,} + {financing:,} does not reconcile "
            f"to the reported net change of {net_change:,}"
        )
