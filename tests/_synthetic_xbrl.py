"""A tiny synthetic XBRL filing for offline statement and Facts API tests.

``write_two_role_filing(directory)`` writes an instance, presentation,
calculation and label linkbase in which two concepts are presented in both an
income statement role and a segment note role, with the note role carrying
what the income statement does not:

* us-gaap:InterestExpenseDebt has a negatedLabel only in the note
  (GH #1677: the Facts API used to take it for the income statement's facts).
* us-gaap:WeightedAverageNumberOfSharesOutstandingBasic has a calculation arc
  (weight 1.0 under diluted shares) only in the note
  (GH #1702: the income statement row used to borrow it).

The income statement link comes first, so the facts are assigned to it. No
values come from a real filing; tests that need one use a cassette.
"""
import pathlib

OPS = "http://example.com/role/ConsolidatedStatementsOfOperations"
NOTE = "http://example.com/role/SegmentDetails"
NS = 'xmlns:link="http://www.xbrl.org/2003/linkbase" xmlns:xlink="http://www.w3.org/1999/xlink"'
G = "https://xbrl.fasb.org/us-gaap/2024/elts/us-gaap-2024.xsd#"

def loc(c):
    return f'<link:loc xlink:type="locator" xlink:href="{G}us-gaap_{c}" xlink:label="{c}"/>'
def parc(f, t, o, pl=None):
    p = f' preferredLabel="{pl}"' if pl else ""
    return f'<link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child" xlink:from="{f}" xlink:to="{t}" order="{o}"{p}/>'
def carc(f, t, o, w):
    return f'<link:calculationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item" xlink:from="{f}" xlink:to="{t}" order="{o}" weight="{w}"/>'

def write_two_role_filing(d):
    d = pathlib.Path(d)
    concepts = ["IncomeStatementAbstract", "Revenues", "InterestExpenseDebt", "NetIncomeLoss",
                "WeightedAverageNumberOfSharesOutstandingBasic", "WeightedAverageNumberOfDilutedSharesOutstanding",
                "SegmentReportingAbstract"]
    locs = "".join(loc(c) for c in concepts)
    neg = "http://www.xbrl.org/2009/role/negatedLabel"
    (d / "x-20251231_pre.xml").write_text(f"""<?xml version="1.0"?><link:linkbase {NS}>
<link:presentationLink xlink:type="extended" xlink:role="{OPS}">{locs}
{parc("IncomeStatementAbstract", "Revenues", 1)}
{parc("IncomeStatementAbstract", "InterestExpenseDebt", 2)}
{parc("IncomeStatementAbstract", "NetIncomeLoss", 3)}
{parc("IncomeStatementAbstract", "WeightedAverageNumberOfSharesOutstandingBasic", 4)}
</link:presentationLink>
<link:presentationLink xlink:type="extended" xlink:role="{NOTE}">{locs}
{parc("SegmentReportingAbstract", "InterestExpenseDebt", 1, neg)}
{parc("SegmentReportingAbstract", "WeightedAverageNumberOfDilutedSharesOutstanding", 2)}
{parc("SegmentReportingAbstract", "WeightedAverageNumberOfSharesOutstandingBasic", 3)}
</link:presentationLink></link:linkbase>""")
    (d / "x-20251231_cal.xml").write_text(f"""<?xml version="1.0"?><link:linkbase {NS}>
<link:calculationLink xlink:type="extended" xlink:role="{OPS}">{locs}
{carc("NetIncomeLoss", "Revenues", 1, "1.0")}
{carc("NetIncomeLoss", "InterestExpenseDebt", 2, "-1.0")}
</link:calculationLink>
<link:calculationLink xlink:type="extended" xlink:role="{NOTE}">{locs}
{carc("WeightedAverageNumberOfDilutedSharesOutstanding", "WeightedAverageNumberOfSharesOutstandingBasic", 1, "1.0")}
</link:calculationLink></link:linkbase>""")
    labels = {"Revenues": "Revenues", "InterestExpenseDebt": "Interest Expense", "NetIncomeLoss": "Net Income",
              "WeightedAverageNumberOfSharesOutstandingBasic": "Basic shares",
              "WeightedAverageNumberOfDilutedSharesOutstanding": "Diluted shares",
              "IncomeStatementAbstract": "Income Statement [Abstract]", "SegmentReportingAbstract": "Segments [Abstract]"}
    res = "".join(
        f'<link:label xlink:type="resource" xlink:label="lab_{c}" xlink:role="http://www.xbrl.org/2003/role/label" xml:lang="en-US">{t}</link:label>'
        f'<link:labelArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label" xlink:from="{c}" xlink:to="lab_{c}"/>'
        for c, t in labels.items())
    res += (f'<link:label xlink:type="resource" xlink:label="neg_InterestExpenseDebt" xlink:role="{neg}" xml:lang="en-US">Interest expense (negated)</link:label>'
            f'<link:labelArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/concept-label" xlink:from="InterestExpenseDebt" xlink:to="neg_InterestExpenseDebt"/>')
    (d / "x-20251231_lab.xml").write_text(f"""<?xml version="1.0"?><link:linkbase {NS}>
<link:labelLink xlink:type="extended" xlink:role="http://www.xbrl.org/2003/role/link">{locs}{res}</link:labelLink></link:linkbase>""")
    facts = {"Revenues": ("1000", "USD"), "InterestExpenseDebt": ("40", "USD"), "NetIncomeLoss": ("960", "USD"),
             "WeightedAverageNumberOfSharesOutstandingBasic": ("100", "shares"),
             "WeightedAverageNumberOfDilutedSharesOutstanding": ("110", "shares")}
    fx = "".join(f'<us-gaap:{c} contextRef="FY2025" unitRef="{u}" decimals="0">{v}</us-gaap:{c}>' for c, (v, u) in facts.items())
    (d / "x-20251231_htm.xml").write_text(f"""<?xml version="1.0"?>
<xbrl xmlns="http://www.xbrl.org/2003/instance" xmlns:us-gaap="http://fasb.org/us-gaap/2024" xmlns:dei="http://xbrl.sec.gov/dei/2024"
 xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:xbrli="http://www.xbrl.org/2003/instance">
<context id="FY2025"><entity><identifier scheme="http://www.sec.gov/CIK">0000000001</identifier></entity>
<period><startDate>2025-01-01</startDate><endDate>2025-12-31</endDate></period></context>
<unit id="USD"><measure>iso4217:USD</measure></unit><unit id="shares"><measure>xbrli:shares</measure></unit>
<dei:DocumentType contextRef="FY2025">10-K</dei:DocumentType>
<dei:DocumentPeriodEndDate contextRef="FY2025">2025-12-31</dei:DocumentPeriodEndDate>
{fx}</xbrl>""")

