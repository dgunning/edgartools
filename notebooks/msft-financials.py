from edgar import Company, set_identity
from edgar.xbrl.xbrl import XBRL
from edgar.xbrl.facts import FactQuery
import pandas as pd
import os
from datetime import date

TAG_MAP = {
"Diluted Shares": "us-gaap:WeightedAverageNumberOfDilutedSharesOutstanding",
"Operating Cash Flow": "us-gaap:NetCashProvidedByUsedInOperatingActivities",
"CapEx": "us-gaap:PaymentsToAcquirePropertyPlantAndEquipment"
}

QUARTER_END = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}

def scale_val(raw, dec):
    return None if raw is None or dec is None else raw * (10 ** dec)

def extract_quarterly_via_factquery(ticker: str, start_year: int = 2011) -> pd.DataFrame:
    c = Company(ticker)
    filings = sorted(
    c.get_filings(form=["10-Q", "10-K"])
        .filter(filing_date=f"{start_year}-01-01:"),
        key=lambda f: f.filing_date
    )
    print(f"Found {len(filings)} filings for {ticker}")

    prev_ytd = {m: 0.0 for m in TAG_MAP}
    last_year = None
    rows = []

    for f in filings:
        try:
            x = XBRL.from_filing(f)
        except Exception as e:
            print(f"Skipping {f.filing_date}: {e}")
            continue

        # Derive period
        d = f.filing_date
        year = d.year
        quarter = 4 if f.form == '10-K' else (d.month - 1) // 3 + 1
        ym, yd = QUARTER_END[quarter]
        period_end = date(year, ym, yd)

        # Use FactQuery on facts view
        fq = FactQuery(x.facts)
        ytd_vals = {}
        for metric, tag in TAG_MAP.items():
            try:
                dfq = fq.by_concept(tag).execute()
                rec = next((r for r in dfq if r.get('period_end') == period_end.isoformat()), None)
                if rec is None:
                    rec = max(
                        (r for r in dfq if r.get('period_start', '').startswith(f"{year}-01-01") and date.fromisoformat(
                            r['period_end']) <= period_end),
                        key=lambda r: r['period_end'], default=None
                    )
                val = float(rec['numeric_value']) if rec else 0.0
            except Exception:
                val = 0.0
            ytd_vals[metric] = val

        # Reset at new year
        if year != last_year:
            prev_ytd = {m: 0.0 for m in TAG_MAP}
            last_year = year

        # Compute quarter-only
        row = {"Year": year, "Quarter": f"Q{quarter}"}
        for m in TAG_MAP:
            yv = ytd_vals[m]
            qv = yv - prev_ytd[m]
            row[m] = qv
            prev_ytd[m] = yv
        rows.append(row)

    df = pd.DataFrame(rows)
    df.sort_values(["Year", "Quarter"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df

def run_demo():
    from edgar import Company, set_identity
    from edgar.xbrl.xbrl import XBRL
    from edgar.xbrl.facts import FactQuery
    import pandas as pd
    import os
    from datetime import date




if __name__ == '__main__':
    c = Company("T")
    filing = c.get_filings(form="10-Q", filing_date=f"2012-01-01:2012-06-30").latest()
    xb = XBRL.from_filing(filing)
    res = xb.query().by_concept("WeightedAverageNumberOfDilutedSharesOutstanding").execute()
    print(res)