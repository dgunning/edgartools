"""Test ix:hidden handling with real Apple 10-K file."""

from pathlib import Path
from edgar.documents import parse_html

# Load Apple 10-K
apple_10k_path = Path("data/html/Apple.10-K.html")
if apple_10k_path.exists():
    html_content = apple_10k_path.read_text()
    
    # Check if there are ix:hidden tags
    hidden_count = html_content.lower().count('<ix:hidden')
    print(f"Found {hidden_count} ix:hidden tags in Apple 10-K")
    
    # Parse the document
    doc = parse_html(html_content)
    
    # Get text
    text = doc.text()
    
    # Check that hidden content is not in the text
    # Look for typical hidden content patterns (raw numeric values)
    import re
    
    # Find content within ix:hidden tags
    hidden_pattern = re.compile(r'<ix:hidden[^>]*>(.*?)</ix:hidden>', re.IGNORECASE | re.DOTALL)
    hidden_matches = hidden_pattern.findall(html_content)
    
    print(f"\nFound {len(hidden_matches)} hidden sections")
    
    # Sample first few hidden contents
    for i, hidden in enumerate(hidden_matches[:5]):
        print(f"\nHidden content {i+1} (first 100 chars):")
        print(hidden[:100].strip())
        
        # Check if this content appears in the parsed text
        # Use a small portion to avoid false negatives due to formatting
        test_portion = hidden[:20].strip()
        if test_portion and test_portion in text:
            print(f"WARNING: Hidden content '{test_portion}' found in parsed text!")
        else:
            print(f"✓ Hidden content not found in parsed text")
    
    print(f"\nTotal document text length: {len(text)} characters")
else:
    print(f"Apple 10-K file not found at {apple_10k_path}")