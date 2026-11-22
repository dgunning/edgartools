"""Build trimmed verbatim viewer-harness fixtures from live SEC filings."""
import json
import re
import sys
from pathlib import Path

from edgar import find

OUT = Path(sys.argv[1])
ONLY = set(sys.argv[2:])  # accessions to rebuild; all when none are given
CASES = {
    '0001628280-20-002543': {'R2.htm': ['us-gaap_Revenues', 'us-gaap_CostOfGoodsAndServicesSold',
                                        'us-gaap_EarningsPerShareBasic'],
                             'R7.htm': ['us-gaap_NetIncomeLoss', 'us-gaap_CommonStockSharesOutstanding']},
    '0001878848-25-000063': {'R3.htm': ['us-gaap_CashAndCashEquivalentsAtCarryingValue'],
                             'R5.htm': ['us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax']},
    '0001410578-23-001531': {'R2.htm': ['us-gaap_CashAndCashEquivalentsAtCarryingValue']},
    '0001174947-24-000443': {'R2.htm': ['us-gaap_CashAndCashEquivalentsAtCarryingValue', 'us-gaap_AssetsCurrent'],
                             'R7.htm': ['us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalentsPeriodIncreaseDecreaseExcludingExchangeRateEffect',
                                        'us-gaap_EffectOfExchangeRateOnCashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
                                        'us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents']},
    '0001564590-22-016827': {'R3.htm': ['us-gaap_LiabilitiesCurrent', 'us-gaap_CommonStockSharesAuthorized',
                                        'us-gaap_CommonStockSharesIssued']},
    '0001299969-24-000010': {'R3.htm': ['us-gaap_CommonStockValue']},
    '0001081316-24-000016': {'R4.htm': ['us-gaap_CashAndCashEquivalentsAtCarryingValue']},
    '0001794783-26-000012': {'R2.htm': ['us-gaap_Goodwill']},
    '0001558370-20-011395': {'R6.htm': ['us-gaap_NetIncomeLoss', 'us-gaap_CashAndCashEquivalentsAtCarryingValue']},
    '0001581068-21-000012': {'R8.htm': ['us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents',
                                        'us-gaap_NetCashProvidedByUsedInOperatingActivities']},
    '0001298946-24-000052': {'R3.htm': ['us-gaap_PreferredStockDividendRatePercentage']},
    '0001493152-26-037707': {'R4.htm': ['us-gaap_InvestmentOwnedBalanceOtherMeasure'],
                             'R8.htm': ['us-gaap_InvestmentCompanyTotalReturn']},
    '0000950170-23-065631': {'R3.htm': ['us-gaap_InvestmentOwnedAtCost'],
                             'R4.htm': ['gxlm_QuantityOfLumens', 'us-gaap_InvestmentOwnedPercentOfNetAssets']},
    '0001713683-20-000163': {'R8.htm': ['us-gaap_CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents']},
    '0001193125-22-052373': {'R4.htm': ['us-gaap_NetIncomeLoss'],
                             'R6.htm': ['us-gaap_NetIncomeLoss', 'us-gaap_NetCashProvidedByUsedInOperatingActivities',
                                        'us-gaap_Cash']},
    # The instance binds the srt namespace to the prefix pf0.
    '0001214659-22-006372': {'R4.htm': ['us-gaap_Revenues']},
    # Member headers name the legal entity only; the facts also carry the partner type.
    '0001562401-24-000082': {'R10.htm': ['us-gaap_CommonUnitIssued', 'us-gaap_CommonUnitOutstanding',
                                         'us-gaap_PreferredUnitsOutstanding', 'us-gaap_PreferredUnitsIssued'],
                             # Statement of equity, whole page: share classes under components, NCI,
                             # quarter and year-to-date movements.
                             'R6.htm': '*'},
    # Statements of equity, whole pages ('*'):
    # 10-Q, two quarterly movements, treasury stock, a "Total" column.
    '0001828016-23-000023': {'R5.htm': '*'},
    # 20-F, IFRS components of equity, amounts in rand printed "R 2,688.6".
    '0001562762-22-000397': {'R4.htm': '*'},
    # 10-K, rows of a movement printed after its closing balance rows.
    '0001834376-26-000049': {'R6.htm': '*',
                             # Cash flows: rows presented with negatedLabel (capital
                             # expenditure, receivables) and a plain total.
                             'R7.htm': ['us-gaap_PaymentsToAcquirePropertyPlantAndEquipment',
                                        'us-gaap_IncreaseDecreaseInAccountsReceivable',
                                        'us-gaap_NetCashProvidedByUsedInOperatingActivities']},
    # 10-K, statement of equity: the tax-withholding concepts have two arcs under one parent
    # (negatedLabel, then label), and each movement prints one row at each.
    '0001437749-23-033895': {'R6.htm': '*'},
    # 40-F, IFRS, opening balance rows naming a restatement member in parentheses.
    '0001193125-21-361301': {'R5.htm': '*'},
    # 10-Q (SPAC), a quarter whose only flow facts are nil: the block still prints.
    '0001104659-21-109339': {'R5.htm': '*'},
    # 10-K, an instant row ("Cumulative-effect adjustment") inside each movement.
    '0000854775-20-000032': {'R7.htm': '*'},
    # 20-F, IFRS: two columns headed "Total" (parent member labelled "Total", then every default).
    '0001213900-26-079236': {'R5.htm': '*'},
    # 40-F, IFRS taxonomy on https, restatement members in row labels, footnote cells ("[1]").
    '0001193125-24-271105': {'R7.htm': '*'},
    # 10-K (SPAC): earnings per share presented with negatedLabel, filed with sign="-".
    '0001193125-24-083443': {'R4.htm': ['us-gaap_EarningsPerShareBasic', 'us-gaap_NetIncomeLoss']},
    # 40-F in CAD: "$ in Thousands" is USD's scale on R2 (CAD has a decimals-0 fact there) and CAD's on R3.
    '0001654954-22-004500': {'R2.htm': '*', 'R3.htm': '*'},
    # 10-Q: cash flows present PaymentsForProceedsFromOtherInvestingActivities twice under one
    # parent, on label and negatedLabel arcs, for each legal entity. The library's tree nodes keep
    # one of the two arcs, so the role's presentation linkbase is kept too (LINKBASES).
    '0000065984-24-000112': {'R3.htm': ['us-gaap_PaymentsForProceedsFromOtherInvestingActivities']},
    # 10-K (BDC): a typed InvestmentIdentifierAxis value with a colon, which the header id writes as '_'.
    '0001213900-25-120913': {'R8.htm': ['us-gaap_InvestmentOwnedAtCost', 'us-gaap_InvestmentOwnedAtFairValue',
                                        'us-gaap_InvestmentOwnedBalancePrincipalAmount']},
    # 10-K (BDC): a member header naming a typed InvestmentIdentifierAxis value with a trailing space.
    '0001803498-26-000014': {'R9.htm': ['us-gaap_InvestmentCompanyFinancialCommitmentToInvesteeFutureAmount']},
    # 20-F in CNY: a balance-sheet cell printed from the less precise of two consistent duplicates.
    '0001193125-25-061847': {'R2.htm': ['us-gaap_RetainedEarningsUnappropriated', 'us-gaap_Liabilities']},
}
# Facts kept although no kept row shows them: periods other concepts carry.
EXTRA_FACTS = {
    # The three facts dated 2019-12-02 to 2020-08-31 (the page's nine months
    # run from 2019-12-01): the stray duration.
    '0001558370-20-011395': ['us-gaap:AccretionExpense', 'us-gaap:AmortizationOfLeaseIncentives',
                             'tmq:DerecognitionOfRightOfUseAsset'],
    # A duration fact, so the columns' periods (and their opening instants) are known.
    '0001713683-20-000163': ['us-gaap:NetCashProvidedByUsedInOperatingActivities'],
}
TR_RE = re.compile(r'<tr\b.*?</tr>', re.S)
DEFREF_RE = re.compile(r"defref_([^'\"]+)")
FACT_COLS = ['concept', 'context_ref', 'period_key', 'period_type', 'value', 'numeric_value',
             'unit_ref', 'currency', 'decimals', 'is_dimensioned']

# Filings whose presentation linkbase is kept, trimmed to the kept reports' roles, so a test can
# parse it with the library's PresentationParser.
LINKBASES = {'0000065984-24-000112'}
# Pages with thousands of member headers: keep only the header each kept row sits under.
NEAREST_HEADER_ONLY = {'0001803498-26-000014', '0001213900-25-120913'}
LINK_RE = re.compile(r'<link:presentationLink\b[^>]*xlink:role="([^"]+)"[^>]*>.*?</link:presentationLink>', re.S)

for acc, pages in CASES.items():
    if ONLY and acc not in ONLY:
        continue
    f = find(acc)
    sgml = f.sgml()
    x = f.xbrl()
    df = x.facts.to_dataframe()
    d = OUT / acc
    d.mkdir(parents=True, exist_ok=True)
    concepts = set()
    member_tags = set()  # the axes and members the kept member headers name
    whole_pages = set()  # pages kept whole: statements of equity
    for fname, keep in pages.items():
        html = sgml.get_content(fname)
        out, pos = [], 0
        pending_rh = None  # (text before, row) of a member header not yet followed by a kept row
        for m in TR_RE.finditer(html):
            seg = m.group(0)
            ref = DEFREF_RE.search(seg)
            is_head = ref is None and '<th' in seg
            is_rh = seg.startswith('<tr class="rh"')
            keep_it = keep == '*' or is_head or is_rh or (ref is not None and ref.group(1) in keep)
            out.append(html[pos:m.start()])
            if is_rh and acc in NEAREST_HEADER_ONLY and keep != '*':
                # Keep a member header only when a kept row follows it before the next header:
                # the rows under it take their context from the nearest header above.
                pending_rh = (seg, ref)
                pos = m.end()
                continue
            if keep_it:
                if pending_rh is not None and not is_head:
                    out.append(pending_rh[0])
                    if pending_rh[1] is not None:
                        member_tags.update(pending_rh[1].group(1).split('='))
                    pending_rh = None
                out.append(seg)
                if is_rh and ref is not None:
                    member_tags.update(ref.group(1).split('='))
            pos = m.end()
        out.append(html[pos:])
        (d / fname).write_text(''.join(out))
        if keep == '*':
            whole_pages.add(fname)
            concepts.update(r for r in DEFREF_RE.findall(html) if '=' not in r)
        else:
            concepts.update(keep)
    # For a whole page, every element of its presentation tree: its primary
    # items (their facts give the statement's movements), axes and members.
    ml = json.loads(sgml.get_content('MetaLinks.json'))
    ikey = next(iter(ml['instance']))
    inst = ml['instance'][ikey]
    whole_roles = [v['role'] for r, v in inst['report'].items() if f'{r}.htm' in whole_pages]
    tree_ids = set()
    for role in whole_roles:
        tree = x.presentation_trees.get(role)
        if tree is not None:
            tree_ids.update(tree.all_nodes)
    member_tags |= tree_ids
    # facts for the kept concepts, every context
    qn = ({c.replace('_', ':', 1) for c in concepts | tree_ids} if whole_pages else
          {c.replace('_', ':', 1) for c in concepts}) | set(EXTRA_FACTS.get(acc, []))
    sub = df[df.concept.isin(qn)]
    facts = []
    for rec in sub[FACT_COLS].to_dict('records'):
        rec = {k: (None if (isinstance(v, float) and v != v) else v) for k, v in rec.items()}
        rec['dimensions'] = dict(x.contexts[rec['context_ref']].dimensions)
        facts.append(rec)
    (d / 'facts.json').write_text(json.dumps(facts, indent=1, default=str))
    # MetaLinks: the kept reports and tags, verbatim entries
    trimmed = {'version': ml.get('version'), 'instance': {ikey: {
        'tag': {t: inst['tag'][t] for t in sorted(concepts | member_tags) if t in inst['tag']},
        'report': {r: v for r, v in inst['report'].items() if f'{r}.htm' in pages},
    }}}
    for t in trimmed['instance'][ikey]['tag'].values():
        t.pop('auth_ref', None)
    (d / 'MetaLinks.json').write_text(json.dumps(trimmed, indent=1, ensure_ascii=False))
    # Presentation trees of the kept reports: every node's children and the
    # preferred label of each child reference, so arc roles can be read offline.
    trees = {}
    for rdata in trimmed['instance'][ikey]['report'].values():
        tree = x.presentation_trees.get(rdata['role'])
        if tree is None:
            continue
        trees[rdata['role']] = {
            'roots': list(tree.root_element_ids or [tree.root_element_id]),
            'nodes': {eid: {'children': list(n.children),
                            'child_preferred_labels': list(n.child_preferred_labels)}
                      for eid, n in tree.all_nodes.items() if n.children},
            # The role's network as filed (PresentationTree.relationships): every arc, a second
            # arc to a concept under the same parent included. [parent, child, order, preferred label]
            'relationships': [[r.parent_id, r.child_id, r.order, r.preferred_label]
                              for r in (tree.relationships or [])],
        }
    (d / 'presentation.json').write_text(json.dumps(trees, indent=1))
    # The filing's namespace bindings (URI -> prefix) and typed dimensions, so
    # dimension QNames resolve offline as they do on the live XBRL object.
    (d / 'namespaces.json').write_text(json.dumps({
        'namespace_prefixes': dict(sorted(x.parser.namespace_prefixes.items())),
        'typed_dimensions': sorted(x.parser.typed_dimensions),
    }, indent=1))
    if whole_pages:
        # Labels of every element in the whole pages' trees, by role, and the
        # axes of those roles with their default members.
        (d / 'labels.json').write_text(json.dumps(
            {eid: dict(sorted((x.element_catalog[eid].labels or {}).items()))
             for eid in sorted(tree_ids) if eid in x.element_catalog}, indent=1, ensure_ascii=False))
        axes = {}
        for role in whole_roles:
            axes[role] = {eid: {'default_member_id': a.default_member_id,
                                'is_typed_dimension': a.is_typed_dimension}
                          for eid, a in sorted(x.axes_for_role(role).items())}
        axes['merged'] = {eid: {'default_member_id': a.default_member_id,
                                'is_typed_dimension': a.is_typed_dimension}
                          for eid, a in sorted(x.axes.items()) if eid in tree_ids}
        (d / 'dimensions.json').write_text(json.dumps(axes, indent=1))
    if acc in LINKBASES:
        name = next(a.document for a in f.attachments if a.document.endswith('_pre.xml'))
        content = sgml.get_content(name)
        roles = {v['role'] for v in trimmed['instance'][ikey]['report'].values()}
        head = content[:content.index('<link:presentationLink')]
        links = [m.group(0) for m in LINK_RE.finditer(content) if m.group(1) in roles]
        (d / 'presentation_linkbase.xml').write_text(head + '\n'.join(links) + '\n</link:linkbase>\n')
    print(acc, f.company, f.form, f.filing_date, len(facts), 'facts')  # noqa: T201
