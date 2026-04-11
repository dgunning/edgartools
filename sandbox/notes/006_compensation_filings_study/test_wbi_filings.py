"""
Test downloading and converting compensation-related SEC filings for WBI.

This script demonstrates:
1. Downloading raw HTML filings
2. Converting HTML to plain text using edgartools' built-in .text() method
3. Saving both HTML and TXT versions

Filing types tested:
- DEF 14A (Proxy Statement) - Executive compensation tables
- 10-K (Annual Report) - Financial data
- 8-K (Current Report) - Material events
- Exhibit 10 (Employment Contracts)
"""

from pathlib import Path
from edgar import Company, set_identity

# Set identity for SEC API access
set_identity("Test User test@example.com")

# Create output directories
OUTPUT_DIR = Path(__file__).parent / "downloaded_filings" / "WBI"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_html_and_text(content_html: str, content_text: str, base_name: str, output_dir: Path):
    """Save both HTML and TXT versions of a filing."""
    # Save HTML
    html_path = output_dir / f"{base_name}.html"
    html_path.write_text(content_html, encoding="utf-8")
    print(f"  💾 Saved HTML: {html_path.name} ({len(content_html):,} bytes)")
    
    # Save TXT
    txt_path = output_dir / f"{base_name}.txt"
    txt_path.write_text(content_text, encoding="utf-8")
    print(f"  💾 Saved TXT:  {txt_path.name} ({len(content_text):,} bytes)")
    
    return html_path, txt_path


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
        else:
            print("     (No structured XBRL data - may be a smaller reporting company)")
    except Exception as e:
        print(f"  ⚠️ Could not parse proxy statement: {e}")
    
    # Download raw HTML and convert to text
    try:
        html_content = filing.html()
        text_content = filing.text()  # Built-in HTML to text conversion
        base_name = f"{ticker}_DEF14A_{filing.filing_date}"
        save_html_and_text(html_content, text_content, base_name, OUTPUT_DIR)
    except Exception as e:
        print(f"  ⚠️ Could not download/convert: {e}")


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
    for i, att in enumerate(attachments_list[:5]):
        desc = att.description[:40] if att.description else "N/A"
        print(f"     {i+1}. {att.document_type}: {desc}...")
    if len(attachments_list) > 5:
        print(f"     ... and {len(attachments_list) - 5} more")
    
    # Download raw HTML and convert to text
    try:
        html_content = filing.html()
        text_content = filing.text()  # Built-in HTML to text conversion
        base_name = f"{ticker}_10K_{filing.filing_date}"
        save_html_and_text(html_content, text_content, base_name, OUTPUT_DIR)
    except Exception as e:
        print(f"  ⚠️ Could not download/convert: {e}")


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
        desc = ex.description[:40] if ex.description else "N/A"
        print(f"       - {ex.document_type}: {desc}...")
    
    # Download main 8-K HTML and text
    try:
        html_content = filing.html()
        text_content = filing.text()
        base_name = f"{ticker}_8K_{filing.filing_date}"
        save_html_and_text(html_content, text_content, base_name, OUTPUT_DIR)
    except Exception as e:
        print(f"  ⚠️ Could not download/convert: {e}")
    
    # Try to find and download Exhibit 99.1 (earnings release)
    ex_99_1 = [ex for ex in exhibits if "99" in str(ex.document_type)]
    if ex_99_1:
        print(f"\n  📰 Found Exhibit 99 attachments:")
        for ex in ex_99_1[:3]:  # Limit to 3
            try:
                html_content = ex.html() if hasattr(ex, 'html') else ""
                text_content = ex.text() if hasattr(ex, 'text') else ""
                if html_content and text_content:
                    safe_type = str(ex.document_type).replace(".", "_")
                    base_name = f"{ticker}_8K_{safe_type}_{filing.filing_date}"
                    save_html_and_text(html_content, text_content, base_name, OUTPUT_DIR)
            except Exception as e:
                print(f"     ⚠️ Could not download/convert {ex.document_type}: {e}")


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
    
    # Download employment-related contracts (look for keywords)
    keywords = ['employment', 'compensation', 'agreement', 'offer', 'separation', 'bonus', 'incentive', 'executive']
    downloaded = 0
    
    for ex in ex_10:
        desc_lower = (ex.description or "").lower()
        if any(kw in desc_lower for kw in keywords) or downloaded == 0:  # At least download one
            try:
                html_content = ex.html() if hasattr(ex, 'html') else ""
                text_content = ex.text() if hasattr(ex, 'text') else ""
                if html_content and text_content:
                    safe_type = str(ex.document_type).replace(".", "_")
                    safe_desc = "".join(c if c.isalnum() else "_" for c in (ex.description or "contract")[:20])
                    base_name = f"{ticker}_{safe_type}_{safe_desc}_{filing.filing_date}"
                    save_html_and_text(html_content, text_content, base_name, OUTPUT_DIR)
                    downloaded += 1
                    if downloaded >= 3:  # Limit to 3 exhibits
                        break
            except Exception as e:
                print(f"  ⚠️ Could not download {ex.document_type}: {e}")


def main():
    """Run all tests for WBI."""
    ticker = "WBI"
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
    print("📂 Files Summary:")
    print("="*60)
    
    if OUTPUT_DIR.exists():
        files = sorted(OUTPUT_DIR.iterdir())
        html_files = [f for f in files if f.suffix == '.html']
        txt_files = [f for f in files if f.suffix == '.txt']
        
        print(f"  Total files: {len(files)}")
        print(f"  HTML files: {len(html_files)}")
        print(f"  TXT files: {len(txt_files)}")
        print(f"\n  Location: {OUTPUT_DIR}")
        
        for f in files:
            size_kb = f.stat().st_size / 1024
            print(f"    - {f.name} ({size_kb:.1f} KB)")
    
    print("\n✅ All tests complete!")


if __name__ == "__main__":
    main()
