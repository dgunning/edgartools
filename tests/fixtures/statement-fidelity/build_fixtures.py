"""Build trimmed statement-fidelity fixtures from live SEC filings.

For each filing and statement role in CASES this writes, under OUT/<accession>/:

- the role's R page, verbatim;
- xbrl/: the filing's schema and linkbases, and its XBRL instance, cut down to
  what the role's Statement reads: the schema's roleType for the role; the
  presentation, calculation and definition links of the role; the facts of the
  role's concepts (and every dei fact), with the contexts and units they
  reference; and the element declarations and labels of the role's concepts and
  of every axis and member those contexts name. Elements are removed with lxml;
  every kept element is serialized unchanged. Footnote links are dropped. A
  filing in EXTRA_ROLES keeps further roles' statements (not their pages) so
  that the typed getters resolve as live.
- xbrl/MetaLinks.json: the role's report entry and the tag entries of the same
  concepts, axes and members, verbatim (auth_ref dropped).
- manifest.json: filer, form, the role, the R page, and what ``XBRL.from_filing``
  adds from the filing itself (the header's SIC code and period of report, the
  FilingSummary menu category of each kept role), with the page's live access
  path (typed getter or statements[role]).

After building, run compare_live.py beside this script: it checks that every
fixture's outcomes equal the live filing's for the same page, field by field.

Usage: hatch run python tests/fixtures/statement-fidelity/build_fixtures.py OUT [ACCESSION ...]
"""
import json
import sys
from pathlib import Path

from lxml import etree

from edgar import find
from edgar.xbrl.statement_fidelity import _typed_statements
from edgar.xbrl.xbrl import _sic_code_from_header

OUT = Path(sys.argv[1])
ONLY = set(sys.argv[2:])
CASES = {
    '0000065984-24-000112': 'http://www.entergy.com/role/ConsolidatedStatementsOfCashFlows',
    '0001081316-24-000016': 'http://www.brkenergy.com/role/ConsolidatedStatementsofComprehensiveIncomeUnauditedParenthetical',
    '0001562762-22-000397': 'http://www.DRDGold.com/role/CONSOLIDATEDSTATEMENTOFPROFITORLOSSANDOTHERCOMPREHENSIVEINCOME',
    '0001493152-26-037707': 'http://graniteshares.com/role/StatementsOfAssetsAndLiabilities',
    '0001581068-21-000012': 'http://www.brixmor.com/role/CONSOLIDATEDSTATEMENTSOFCASHFLOWS',
    '0001564590-22-016827': 'http://www.chindatagroup.com/20211231/taxonomy/role/StatementConsolidatedBalanceSheets',
    '0001214659-22-006372': 'http://goodtimesburgers.com/role/ConsolidatedCashFlow',
    '0001298946-24-000052': 'http://www.drhc.com/role/CONSOLIDATEDBALANCESHEETSParenthetical',
}
# Further roles whose statements are kept (without their pages) so that the typed getters
# resolve offline as they do live: without BHE's comprehensive income statement,
# comprehensive_income() would claim the parenthetical role, and without DiamondRock's
# balance sheet, balance_sheet() would.
EXTRA_ROLES = {
    '0001081316-24-000016': ['http://www.brkenergy.com/role/ConsolidatedStatementsofComprehensiveIncomeUnaudited'],
    '0001298946-24-000052': ['http://www.drhc.com/role/CONSOLIDATEDBALANCESHEETS'],
}
XLINK = 'http://www.w3.org/1999/xlink'
LINK = 'http://www.xbrl.org/2003/linkbase'
XBRLI = 'http://www.xbrl.org/2003/instance'
XSD = 'http://www.w3.org/2001/XMLSchema'


def write(path: Path, root) -> None:
    path.write_bytes(etree.tostring(root.getroottree(), xml_declaration=True, encoding='utf-8'))


def parse(text: str):
    return etree.fromstring(text.encode('utf-8') if isinstance(text, str) else text,
                            etree.XMLParser(remove_blank_text=False, huge_tree=True))


def trim_links(text: str, roles: set):
    """Keep the extended links of one role (presentation, calculation, definition)."""
    root = parse(text)
    for child in list(root):
        if not isinstance(child.tag, str):
            continue
        local = etree.QName(child).localname
        if local.endswith('Link') and child.get(f'{{{XLINK}}}role') not in roles:
            root.remove(child)
        elif local == 'roleRef' and child.get('roleURI') not in roles:
            root.remove(child)
    return root


def href_id(href: str) -> str:
    return href.rpartition('#')[2]


def trim_labels(text: str, concepts: set):
    root = parse(text)
    for link in root.iter(f'{{{LINK}}}labelLink'):
        locs = {loc.get(f'{{{XLINK}}}label') for loc in link.iter(f'{{{LINK}}}loc')
                if href_id(loc.get(f'{{{XLINK}}}href', '')) in concepts}
        arcs = [arc for arc in link.iter(f'{{{LINK}}}labelArc')]
        keep_to = {arc.get(f'{{{XLINK}}}to') for arc in arcs if arc.get(f'{{{XLINK}}}from') in locs}
        for el in list(link):
            if not isinstance(el.tag, str):
                continue
            local = etree.QName(el).localname
            label = el.get(f'{{{XLINK}}}label')
            keep = ((local == 'loc' and label in locs)
                    or (local == 'labelArc' and el.get(f'{{{XLINK}}}from') in locs)
                    or (local == 'label' and label in keep_to))
            if not keep:
                link.remove(el)
    return root


def trim_schema(text: str, roles: set, concepts: set):
    root = parse(text)
    for el in list(root.iter(f'{{{XSD}}}element')):
        if el.getparent() is root and el.get('id') not in concepts:
            root.remove(el)
    for rt in list(root.iter(f'{{{LINK}}}roleType')):
        if rt.get('roleURI') not in roles:
            rt.getparent().remove(rt)
    return root


def trim_instance(text: str, concepts: set):
    root = parse(text)
    prefixes = {ns: p for p, ns in root.nsmap.items() if p}
    contexts, units = set(), set()
    for el in list(root):
        if not isinstance(el.tag, str):
            continue
        qn = etree.QName(el)
        if qn.namespace in (XBRLI, LINK):
            continue
        prefix = prefixes.get(qn.namespace, '')
        if f'{prefix}_{qn.localname}' in concepts or prefix == 'dei':
            contexts.add(el.get('contextRef'))
            if el.get('unitRef'):
                units.add(el.get('unitRef'))
        else:
            root.remove(el)
    for el in list(root):
        if not isinstance(el.tag, str):
            continue
        qn = etree.QName(el)
        if (qn.namespace == XBRLI and qn.localname == 'context' and el.get('id') not in contexts) or \
                (qn.namespace == XBRLI and qn.localname == 'unit' and el.get('id') not in units) or \
                (qn.namespace == LINK and qn.localname == 'footnoteLink'):
            root.remove(el)
    return root


XBRLDI = 'http://xbrl.org/2006/xbrldi'


def context_elements(instance_root) -> set:
    """Element ids (prefix_local) of every axis and explicit member the kept contexts name."""
    ids = set()
    for el in instance_root.iter(f'{{{XBRLDI}}}explicitMember', f'{{{XBRLDI}}}typedMember'):
        ids.add(el.get('dimension', '').replace(':', '_', 1))
        if etree.QName(el).localname == 'explicitMember' and el.text:
            ids.add(el.text.strip().replace(':', '_', 1))
    return ids


for acc, role in CASES.items():
    if ONLY and acc not in ONLY:
        continue
    f = find(acc)
    sgml = f.sgml()
    x = f.xbrl()
    roles = {role, *EXTRA_ROLES.get(acc, [])}
    concepts = set().union(*(x.presentation_trees[r].all_nodes for r in roles))
    d = OUT / acc
    (d / 'xbrl').mkdir(parents=True, exist_ok=True)
    ml = json.loads(sgml.get_content('MetaLinks.json'))
    ikey = next(iter(ml['instance']))
    inst = ml['instance'][ikey]
    rkey, report = next((k, v) for k, v in inst['report'].items() if v['role'] == role)
    page = f'{rkey}.htm'
    (d / page).write_text(sgml.get_content(page))
    documents = [(a.document, sgml.get_content(a.document)) for a in f.attachments
                 if a.document.endswith(('.xsd', '.xml')) and a.document != 'FilingSummary.xml']
    # The instance first: the axes and members of its kept contexts keep their labels and
    # declarations, so a library row's member label reads as it does live.
    trimmed, named = {}, set(concepts)
    for name, content in documents:
        if content and not name.endswith(('.xsd', '_lab.xml', '_pre.xml', '_cal.xml', '_def.xml')) \
                and '<xbrl' in content[:5000]:
            trimmed[name] = trim_instance(content, concepts)
            named |= context_elements(trimmed[name])
    for name, content in documents:
        if not content or name in trimmed:
            continue
        if name.endswith('.xsd'):
            trimmed[name] = trim_schema(content, roles, named)
        elif name.endswith('_lab.xml'):
            trimmed[name] = trim_labels(content, named)
        elif name.endswith(('_pre.xml', '_cal.xml', '_def.xml')):
            trimmed[name] = trim_links(content, roles)
    for name, root in trimmed.items():
        write(d / 'xbrl' / name, root)
    tags = {t: dict(v) for t, v in inst['tag'].items() if t in named}
    for v in tags.values():
        v.pop('auth_ref', None)
    (d / 'xbrl' / 'MetaLinks.json').write_text(json.dumps(
        {'version': ml.get('version'), 'instance': {ikey: {'tag': tags, 'report': {rkey: report}}}},
        indent=1, ensure_ascii=False))
    sic = None
    header = sgml.header
    if header and header.filers and header.filers[0].company_information:
        sic = _sic_code_from_header(header.filers[0].company_information.sic)
    (d / 'manifest.json').write_text(json.dumps({
        'accession': acc, 'filer': f.company, 'form': f.form, 'filing_date': str(f.filing_date),
        'role': role, 'page': page, 'short_name': report.get('shortName'), 'sic': sic,
        'period_of_report': getattr(x, '_sgml_period_of_report', None),
        # FilingSummary's menu category of each kept role, as XBRL._apply_filing_summary reads it
        'menu_categories': {r: x._filing_summary_menu_categories.get(r) for r in sorted(roles)},
        # How the page's statement is reached live (compare_statements_to_viewer's access)
        'access': next((g for g, r in _typed_statements(x)[1] if r == role), 'statements[role]'),
    }, indent=1))
    print(acc, f.company, page, sum(p.stat().st_size for p in d.rglob('*') if p.is_file()) // 1024, 'KB')  # noqa: T201
