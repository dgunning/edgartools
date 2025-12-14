"""
Table-Based Field Extractors for 424B Prospectus Filings

This module extracts data from tables including:
- Underwriter syndicate and compensation (424B5)
- Selling shareholders (424B3)
- Offering terms tables
- Dilution tables

Week 2 Research - 424B5/424B3 Data Extraction Feasibility Assessment
"""

import re
from typing import Any, Dict, List, Optional

from edgar.documents.parser import HTMLParser


class UnderwriterExtractor:
    """Extract underwriter information from 424B5 filings."""

    # Comprehensive list of underwriter name patterns
    UNDERWRITER_KEYWORDS = [
        # Major investment banks
        'Goldman Sachs', 'Goldman, Sachs', 'Goldman',
        'Morgan Stanley',
        'JP Morgan', 'J.P. Morgan', 'JPMorgan',
        'BofA Securities', 'Bank of America', 'Merrill Lynch',
        'Citigroup', 'Citi',
        'Barclays',
        'Wells Fargo',
        'Deutsche Bank',
        'Credit Suisse',
        'UBS',

        # Mid-tier and specialized
        'Jefferies', 'Jefferies LLC',
        'Cowen', 'Cowen and Company',
        'Piper Sandler', 'Piper Jaffray',
        'Stifel', 'Stifel Nicolaus',
        'William Blair',
        'Raymond James',
        'RBC Capital Markets',
        'BMO Capital Markets',
        'TD Securities',
        'Canaccord Genuity',
        'Oppenheimer',
        'Needham', 'Needham & Company',

        # Healthcare/Biotech specialized
        'Leerink Partners', 'SVB Leerink', 'SVB Securities',
        'Guggenheim Securities',
        'H.C. Wainwright', 'Wainwright',
        'Ladenburg Thalmann',
        'Maxim Group',
        'BTIG',
        'Roth Capital Partners',

        # International
        'Nomura',
        'HSBC',
        'BNP Paribas',
        'Societe Generale',
    ]

    def __init__(self, html: str, document=None):
        """
        Initialize underwriter extractor.

        Args:
            html: Full HTML content of filing
            document: Optional Document object from HTMLParser
        """
        self.html = html
        self.document = document

    def extract_from_section(self) -> Dict[str, Any]:
        """
        Extract underwriters from Underwriting section using text search.

        Returns:
            Dictionary with:
                - underwriters: List of underwriter names found
                - lead_underwriters: List of lead/book-running managers
                - confidence: High/Medium/Low
        """
        # Find underwriting section
        underwriting_match = re.search(
            r'<[^>]*>.*?[Uu][Nn][Dd][Ee][Rr][Ww][Rr][Ii][Tt][Ii][Nn][Gg].*?</[^>]*>',
            self.html[:50000],
            re.IGNORECASE | re.DOTALL
        )

        if not underwriting_match:
            return {
                'underwriters': [],
                'lead_underwriters': [],
                'confidence': 'None',
                'section_found': False
            }

        # Extract 10000 chars after "Underwriting" section
        start_pos = underwriting_match.start()
        underwriting_content = self.html[start_pos:start_pos + 10000]

        # Search for underwriter names
        underwriters_found = []
        for keyword in self.UNDERWRITER_KEYWORDS:
            # Create flexible pattern (handles "&", "and", commas, etc.)
            pattern = re.escape(keyword)
            if re.search(pattern, underwriting_content, re.IGNORECASE):
                underwriters_found.append(keyword)

        # Look for lead underwriters
        lead_patterns = [
            r'([^<>\n]+?),?\s+as\s+(?:sole\s+)?book[- ]?running\s+manager',
            r'([^<>\n]+?),?\s+as\s+(?:lead\s+)?book[- ]?runner',
            r'([^<>\n]+?),?\s+as\s+lead\s+manager',
            r'([^<>\n]+?),?\s+as\s+representative',
        ]

        lead_underwriters = []
        for pattern in lead_patterns:
            matches = re.findall(pattern, underwriting_content, re.IGNORECASE)
            for match in matches:
                # Clean up HTML tags and whitespace
                clean_match = re.sub(r'<[^>]+>', '', match).strip()
                if clean_match and len(clean_match) < 100:  # Reasonable name length
                    lead_underwriters.append(clean_match)

        # Determine confidence
        confidence = 'None'
        if underwriters_found:
            confidence = 'High' if len(underwriters_found) >= 2 else 'Medium'

        return {
            'underwriters': list(set(underwriters_found)),  # Remove duplicates
            'lead_underwriters': list(set(lead_underwriters)),
            'confidence': confidence,
            'section_found': True
        }

    def extract_from_table(self) -> Dict[str, Any]:
        """
        Extract underwriters from underwriting table.

        Returns:
            Dictionary with:
                - underwriters: List of dicts with name and share allocation
                - total_shares: Total shares in syndicate
                - confidence: High/Medium/Low
        """
        if not self.document:
            return {
                'underwriters': [],
                'total_shares': None,
                'confidence': 'None',
                'table_found': False
            }

        # Look for underwriting table in document tables
        underwriting_tables = []
        for table in self.document.tables:
            # Check if table contains underwriting keywords
            table_text = str(table).lower()
            if 'underwriter' in table_text or 'book-running' in table_text:
                underwriting_tables.append(table)

        if not underwriting_tables:
            return {
                'underwriters': [],
                'total_shares': None,
                'confidence': 'None',
                'table_found': False
            }

        # Parse first matching table
        table = underwriting_tables[0]
        underwriters_data = []

        # Tables typically have: Underwriter | Number of Shares
        # Try to extract rows with underwriter names
        for row in table.rows:
            row_text = ' '.join([str(cell) for cell in row.cells])

            # Check if row contains an underwriter name
            for keyword in self.UNDERWRITER_KEYWORDS[:20]:  # Check major ones
                if keyword.lower() in row_text.lower():
                    # Try to extract share count from same row
                    share_match = re.search(r'([\d,]+)', row_text)
                    share_count = share_match.group(1).replace(',', '') if share_match else None

                    underwriters_data.append({
                        'name': keyword,
                        'shares': share_count
                    })
                    break

        confidence = 'High' if underwriters_data else 'Low'

        return {
            'underwriters': underwriters_data,
            'total_shares': None,  # TODO: Calculate from table
            'confidence': confidence,
            'table_found': True
        }

    def extract_underwriting_discount(self) -> Dict[str, Any]:
        """
        Extract underwriting discount/commission percentage.

        Returns:
            Dictionary with:
                - discount_percent: Percentage (as float)
                - discount_per_share: Dollar amount per share
                - confidence: High/Medium/Low
        """
        patterns = [
            # Pattern 1: Underwriting discount: X.XX%
            (r'[Uu]nderwriting\s+[Dd]iscount.*?([\d.]+)%', 'High'),

            # Pattern 2: $X.XX per share discount
            (r'[Dd]iscount.*?\$\s*([\d.]+)\s+per\s+share', 'High'),

            # Pattern 3: Commission of X.XX%
            (r'[Cc]ommission.*?([\d.]+)%', 'Medium'),

            # Pattern 4: X.XX% of the gross proceeds
            (r'([\d.]+)%\s+of\s+(?:the\s+)?gross\s+proceeds', 'Medium'),
        ]

        for pattern, confidence in patterns:
            match = re.search(pattern, self.html[:30000], re.IGNORECASE)
            if match:
                value = match.group(1)

                # Determine if it's percentage or dollar amount
                if '$' in match.group(0):
                    return {
                        'discount_percent': None,
                        'discount_per_share': value,
                        'confidence': confidence,
                        'raw_text': match.group(0)
                    }
                else:
                    return {
                        'discount_percent': value,
                        'discount_per_share': None,
                        'confidence': confidence,
                        'raw_text': match.group(0)
                    }

        return {
            'discount_percent': None,
            'discount_per_share': None,
            'confidence': 'None',
            'raw_text': None
        }

    def extract_all(self) -> Dict[str, Any]:
        """Extract all underwriter-related fields."""
        return {
            'from_section': self.extract_from_section(),
            'from_table': self.extract_from_table(),
            'underwriting_discount': self.extract_underwriting_discount(),
        }


class SellingShareholderExtractor:
    """Extract selling shareholder information from 424B3 filings."""

    def __init__(self, html: str, document=None):
        """
        Initialize selling shareholder extractor.

        Args:
            html: Full HTML content of filing
            document: Optional Document object from HTMLParser
        """
        self.html = html
        self.document = document

    def extract_from_section(self) -> Dict[str, Any]:
        """
        Detect selling shareholders section.

        Returns:
            Dictionary with:
                - section_found: Boolean
                - section_text: First 2000 chars of section
                - confidence: High/Medium/Low
        """
        patterns = [
            r'SELLING\s+SHAREHOLDERS?',
            r'SELLING\s+STOCKHOLDERS?',
            r'SELLING\s+SECURITY\s+HOLDERS?',
            r'THE\s+SELLING\s+SHAREHOLDERS?',
        ]

        for pattern in patterns:
            match = re.search(pattern, self.html, re.IGNORECASE)
            if match:
                start_pos = match.start()
                section_text = self.html[start_pos:start_pos + 2000]

                return {
                    'section_found': True,
                    'section_text': section_text[:500],  # Preview
                    'confidence': 'High',
                    'pattern_matched': pattern
                }

        return {
            'section_found': False,
            'section_text': None,
            'confidence': 'None',
            'pattern_matched': None
        }

    def extract_from_table(self) -> Dict[str, Any]:
        """
        Extract selling shareholders from table.

        Returns:
            Dictionary with:
                - shareholders: List of dicts with name, shares, ownership %
                - total_shares: Total shares being resold
                - confidence: High/Medium/Low
        """
        if not self.document:
            return {
                'shareholders': [],
                'total_shares': None,
                'confidence': 'None',
                'table_found': False
            }

        # Look for selling shareholder table
        shareholder_tables = []
        for table in self.document.tables:
            table_text = str(table).lower()
            if 'selling' in table_text and ('shareholder' in table_text or 'stockholder' in table_text):
                shareholder_tables.append(table)

        if not shareholder_tables:
            return {
                'shareholders': [],
                'total_shares': None,
                'confidence': 'None',
                'table_found': False
            }

        # Parse first matching table
        table = shareholder_tables[0]
        shareholders_data = []

        # Tables typically have: Name | Shares Owned | Shares Offered | % Before | % After
        # We'll extract what we can find
        for i, row in enumerate(table.rows):
            if i == 0:  # Skip header row
                continue

            cells = [str(cell).strip() for cell in row.cells]
            if len(cells) >= 2:
                # First cell is typically name
                name = cells[0]

                # Look for share counts in remaining cells
                shares_offered = None
                for cell in cells[1:]:
                    share_match = re.search(r'([\d,]+)', cell)
                    if share_match:
                        shares_offered = share_match.group(1).replace(',', '')
                        break

                if name and len(name) < 200:  # Reasonable name length
                    shareholders_data.append({
                        'name': name,
                        'shares_offered': shares_offered
                    })

        confidence = 'High' if shareholders_data else 'Low'

        return {
            'shareholders': shareholders_data[:20],  # Limit to first 20
            'total_shares': None,  # TODO: Calculate
            'confidence': confidence,
            'table_found': True
        }

    def extract_resale_amount(self) -> Dict[str, Any]:
        """
        Extract total resale amount (424B3 specific).

        Returns:
            Dictionary with:
                - amount: Total resale amount
                - currency: Currency code
                - confidence: High/Medium/Low
        """
        patterns = [
            (r'[Rr]esale.*?\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion)?', 'High'),
            (r'[Aa]ggregate.*?resale.*?\$\s*([\d,]+(?:\.\d+)?)', 'Medium'),
        ]

        for pattern, confidence in patterns:
            match = re.search(pattern, self.html[:10000], re.IGNORECASE)
            if match:
                amount = match.group(1).replace(',', '')

                # Apply multiplier if present
                if len(match.groups()) > 1 and match.group(2):
                    multiplier = match.group(2).lower()
                    if 'million' in multiplier:
                        amount = str(int(float(amount) * 1_000_000))
                    elif 'billion' in multiplier:
                        amount = str(int(float(amount) * 1_000_000_000))

                return {
                    'amount': amount,
                    'currency': 'USD',
                    'confidence': confidence,
                    'raw_text': match.group(0)
                }

        return {
            'amount': None,
            'currency': 'USD',
            'confidence': 'None',
            'raw_text': None
        }

    def extract_all(self) -> Dict[str, Any]:
        """Extract all selling shareholder fields."""
        return {
            'section_detection': self.extract_from_section(),
            'table_extraction': self.extract_from_table(),
            'resale_amount': self.extract_resale_amount(),
        }


class OfferingTermsExtractor:
    """Extract offering terms from tables (greenshoe, allocation, etc.)."""

    def __init__(self, html: str, document=None):
        """
        Initialize offering terms extractor.

        Args:
            html: Full HTML content of filing
            document: Optional Document object from HTMLParser
        """
        self.html = html
        self.document = document

    def extract_greenshoe(self) -> Dict[str, Any]:
        """
        Extract over-allotment (greenshoe) option details.

        Returns:
            Dictionary with:
                - has_greenshoe: Boolean
                - greenshoe_shares: Number of shares
                - greenshoe_percent: Percentage (typically 15%)
                - confidence: High/Medium/Low
        """
        patterns = [
            # Pattern 1: over-allotment option
            (r'over-allotment\s+option.*?([\d,]+)\s+(?:additional\s+)?shares?', 'High'),

            # Pattern 2: option to purchase additional shares
            (r'option\s+to\s+purchase.*?([\d,]+)\s+additional\s+shares?', 'High'),

            # Pattern 3: 15% overallotment (standard)
            (r'(15)%.*?over-allotment', 'Medium'),

            # Pattern 4: greenshoe option (less common term)
            (r'greenshoe.*?([\d,]+)\s+shares?', 'Medium'),
        ]

        for pattern, confidence in patterns:
            match = re.search(pattern, self.html[:15000], re.IGNORECASE)
            if match:
                value = match.group(1).replace(',', '')

                # Check if it's a percentage or share count
                if '%' in match.group(0) or int(value) < 100:
                    return {
                        'has_greenshoe': True,
                        'greenshoe_shares': None,
                        'greenshoe_percent': value,
                        'confidence': confidence,
                        'raw_text': match.group(0)
                    }
                else:
                    return {
                        'has_greenshoe': True,
                        'greenshoe_shares': value,
                        'greenshoe_percent': None,
                        'confidence': confidence,
                        'raw_text': match.group(0)
                    }

        return {
            'has_greenshoe': False,
            'greenshoe_shares': None,
            'greenshoe_percent': None,
            'confidence': 'High',  # High confidence in absence
            'raw_text': None
        }

    def extract_all(self) -> Dict[str, Any]:
        """Extract all offering terms fields."""
        return {
            'greenshoe': self.extract_greenshoe(),
        }


if __name__ == '__main__':
    # Example usage
    from edgar import Filing

    # Test 424B5 (underwriters)
    print("Testing 424B5 Underwriter Extraction:")
    print("=" * 60)
    filing_b5 = Filing(form='424B5', accession_number='0001104659-24-041120')
    html_b5 = filing_b5.html()
    doc_b5 = filing_b5.document()

    underwriter_extractor = UnderwriterExtractor(html_b5, doc_b5)
    results_b5 = underwriter_extractor.extract_all()

    for key, value in results_b5.items():
        print(f"\n{key}:")
        print(value)

    # Test 424B3 (selling shareholders)
    print("\n\nTesting 424B3 Selling Shareholder Extraction:")
    print("=" * 60)
    filing_b3 = Filing(form='424B3', accession_number='0001104659-24-132173')
    html_b3 = filing_b3.html()
    doc_b3 = filing_b3.document()

    shareholder_extractor = SellingShareholderExtractor(html_b3, doc_b3)
    results_b3 = shareholder_extractor.extract_all()

    for key, value in results_b3.items():
        print(f"\n{key}:")
        print(value)
