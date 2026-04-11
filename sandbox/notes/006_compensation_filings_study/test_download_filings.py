"""
Test downloading compensation-related SEC filings using edgartools.

This script demonstrates downloading:
1. DEF 14A (Proxy Statement) - Executive compensation tables
2. 10-K (Annual Report) - Financial data and executive compensation
3. 8-K (Current Report) - Material events including compensation changes
4. Exhibit 10 (Employment Contracts) - From 10-K filings
"""

from pathlib import Path
from edgar import Company, set_identity

# Set identity for SEC API access
set_identity("Test User test@example.com")

# Create output directories
OUTPUT_DIR = Path(__file__).parent / "downloaded_filings"
OUTPUT_DIR.mkdir(exist_ok=True)


def test_def14a(company: Company, ticker: str):
    """Test downloading DEF 14A (Proxy Statement)."""
    print("\n" + "="*60)
    print(f"1. DEF 14A (Proxy Statement) for {ticker}")
    print("="*60)
    
    filing = company.get_filings(form="DEF 14A").latest()
    if not filing:
        print("  ❌ No DEF 14A filing found")
        return
    
    print(f"  ✅ Found: {filing.form} filed on {filing.filing_date}")
    print(f"     Accession: {filing.accession_no}")
    
    # Try to get structured data via ProxyStatement
    try:
        proxy = filing.obj()
        print(f"\n  📊 Proxy Statement Data:")
        print(f"     Has XBRL: {proxy.has_xbrl}")
        if proxy.has_xbrl:
            print(f"     CEO Name: {proxy.peo_name}")
            if proxy.peo_total_comp:
                print(f"     CEO Total Comp: ${proxy.peo_total_comp:,.0f}")
    except Exception as e:
        print(f"  ⚠️ Could not parse proxy statement: {e}")
    
    # Download raw HTML
    try:
        html_content = filing.html()
        output_path = OUTPUT_DIR / f"{ticker}_DEF14A_{filing.filing_date}.html"
        output_path.write_text(html_content, encoding="utf-8")
        print(f"\n  💾 Downloaded raw HTML to: {output_path.name}")
    except Exception as e:
        print(f"  ⚠️ Could not download HTML: {e}")


def test_10k(company: Company, ticker: str):
    """Test downloading 10-K (Annual Report)."""
    print("\n" + "="*60)
    print(f"2. 10-K (Annual Report) for {ticker}")
    print("="*60)
    
    filing = company.get_filings(form="10-K").latest()
    if not filing:
        print("  ❌ No 10-K filing found")
        return
    
    print(f"  ✅ Found: {filing.form} filed on {filing.filing_date}")
    print(f"     Accession: {filing.accession_no}")
    
    # List all attachments
    attachments_list = list(filing.attachments)
    print(f"\n  📎 Attachments ({len(attachments_list)} total):")
    for i, att in enumerate(attachments_list[:10]):
        print(f"     {i+1}. {att.document_type}: {att.description[:50] if att.description else 'N/A'}...")
    if len(attachments_list) > 10:
        print(f"     ... and {len(attachments_list) - 10} more")
    
    # Download raw HTML
    try:
        html_content = filing.html()
        output_path = OUTPUT_DIR / f"{ticker}_10K_{filing.filing_date}.html"
        output_path.write_text(html_content, encoding="utf-8")
        print(f"\n  💾 Downloaded raw HTML to: {output_path.name}")
    except Exception as e:
        print(f"  ⚠️ Could not download HTML: {e}")


def test_8k(company: Company, ticker: str):
    """Test downloading 8-K (Current Report)."""
    print("\n" + "="*60)
    print(f"3. 8-K (Current Report) for {ticker}")
    print("="*60)
    
    filings = company.get_filings(form="8-K").latest(5)
    if not filings:
        print("  ❌ No 8-K filings found")
        return
    
    print(f"  ✅ Found {len(filings)} recent 8-K filings:")
    for f in filings:
        print(f"     - {f.filing_date}: {f.accession_no}")
    
    # Get the latest one with details
    filing = filings[0]
    print(f"\n  📎 Latest 8-K Attachments:")
    
    # List exhibits
    exhibits = list(filing.exhibits)
    print(f"     Exhibits found: {len(exhibits)}")
    for ex in exhibits[:5]:
        print(f"       - {ex.document_type}: {ex.description[:40] if ex.description else 'N/A'}...")
    
    # Try to find Exhibit 99.1 (earnings release)
    ex_99_1 = [ex for ex in exhibits if "99.1" in str(ex.document_type)]
    if ex_99_1:
        print(f"\n  📰 Found Exhibit 99.1 (Earnings Release):")
        ex = ex_99_1[0]
        try:
            content = ex.text()[:500] if hasattr(ex, 'text') else "N/A"
            print(f"     Preview: {content[:200]}...")
            
            # Download
            html_content = ex.html() if hasattr(ex, 'html') else None
            if html_content:
                output_path = OUTPUT_DIR / f"{ticker}_8K_EX99.1_{filing.filing_date}.html"
                output_path.write_text(html_content, encoding="utf-8")
                print(f"\n  💾 Downloaded Exhibit 99.1 to: {output_path.name}")
        except Exception as e:
            print(f"     ⚠️ Could not read exhibit: {e}")


def test_exhibit_10(company: Company, ticker: str):
    """Test downloading Exhibit 10 (Employment Contracts) from 10-K."""
    print("\n" + "="*60)
    print(f"4. Exhibit 10 (Employment Contracts) for {ticker}")
    print("="*60)
    
    filing = company.get_filings(form="10-K").latest()
    if not filing:
        print("  ❌ No 10-K filing found")
        return
    
    # Find Exhibit 10.x attachments
    exhibits = list(filing.exhibits)
    ex_10 = [ex for ex in exhibits if str(ex.document_type).startswith("EX-10")]
    
    if not ex_10:
        print("  ⚠️ No Exhibit 10 attachments found")
        return
    
    print(f"  ✅ Found {len(ex_10)} Exhibit 10 documents:")
    for ex in ex_10[:10]:
        desc = ex.description[:60] if ex.description else "No description"
        print(f"     - {ex.document_type}: {desc}...")
    
    if len(ex_10) > 10:
        print(f"     ... and {len(ex_10) - 10} more")
    
    # Download first employment-related contract (look for keywords)
    keywords = ['employment', 'compensation', 'agreement', 'offer letter', 'separation']
    for ex in ex_10:
        desc_lower = (ex.description or "").lower()
        if any(kw in desc_lower for kw in keywords):
            try:
                html_content = ex.html()
                safe_desc = "".join(c if c.isalnum() else "_" for c in (ex.description or "contract")[:30])
                output_path = OUTPUT_DIR / f"{ticker}_EX10_{safe_desc}_{filing.filing_date}.html"
                output_path.write_text(html_content, encoding="utf-8")
                print(f"\n  💾 Downloaded employment contract to: {output_path.name}")
                break
            except Exception as e:
                print(f"  ⚠️ Could not download {ex.document_type}: {e}")


def main():
    """Run all tests for a sample company."""
    ticker = "AAPL"  # Apple Inc.
    print(f"\n{'#'*60}")
    print(f"# Testing Compensation Filings Download for {ticker}")
    print(f"{'#'*60}")
    
    company = Company(ticker)
    print(f"\nCompany: {company.name}")
    print(f"CIK: {company.cik}")
    
    # Run all tests
    test_def14a(company, ticker)
    test_10k(company, ticker)
    test_8k(company, ticker)
    test_exhibit_10(company, ticker)
    
    print("\n" + "="*60)
    print(f"✅ All tests complete! Files saved to: {OUTPUT_DIR}")
    print("="*60)


if __name__ == "__main__":
    main()
