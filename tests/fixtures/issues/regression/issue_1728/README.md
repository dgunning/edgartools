# GH #1728 fixture: Comcast 10-Q, the us-gaap concepts it reports in USD

`cmcsa_10q_usd_concepts.txt` lists, one per line, the 135 distinct `us-gaap` concepts
that Comcast's 10-Q for the quarter ended 2026-06-30 (filed 2026-07-23) (CIK 1166691, accession
0001628280-26-049360) reports with unit `USD`, as read from the filing's XBRL instance
on 2026-11-12. Only the concept names are kept: the regression test checks the balance
the bundled taxonomy table gives each of them, which needs no amounts.

To rebuild:

```python
from edgar import Filing
from edgar.xbrl import XBRL

f = Filing(form="10-Q", filing_date="2026-07-23", company="COMCAST CORP",
           cik=1166691, accession_no="0001628280-26-049360")
df = XBRL.from_filing(f).facts.to_dataframe()
usd = df[df["concept"].str.startswith("us-gaap:") & (df["unit_ref"].astype(str).str.upper() == "USD")]
print("\n".join(sorted(usd["concept"].unique())))
```
