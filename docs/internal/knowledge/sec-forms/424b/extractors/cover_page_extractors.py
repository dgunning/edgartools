"""
Cover Page Field Extractors for 424B Prospectus Filings

This module contains extractors for high-priority cover page fields including
offering amount, security type, offering price, and share counts.

Week 2 Research - 424B5/424B3 Data Extraction Feasibility Assessment
"""

import re
from decimal import Decimal
from typing import Any, Dict, Optional


class CoverPageExtractor:
    """Extract cover page fields from 424B prospectus filings."""

    def __init__(self, html: str):
        """
        Initialize extractor with HTML content.

        Args:
            html: Full HTML content of filing
        """
        self.html = html
        self.cover_page = html[:10000]  # Expanded from 5000 for better coverage

    def extract_offering_amount(self) -> Dict[str, Any]:
        """
        Extract aggregate offering amount from cover page.

        Returns:
            Dictionary with:
                - amount: Numeric value (as string)
                - currency: Currency code (USD assumed)
                - confidence: High/Medium/Low
                - raw_text: Original matched text
        """
        patterns = [
            # Pattern 1: $XXX,XXX,XXX format (exact amount)
            (r'\$\s*([\d,]+)\s*(?!million|billion)', 'exact', 'High'),

            # Pattern 2: $XX million or $XX.X million
            (r'\$\s*([\d,]+(?:\.\d+)?)\s*million', 'million', 'High'),

            # Pattern 3: $XX billion or $X.XX billion
            (r'\$\s*([\d,]+(?:\.\d+)?)\s*billion', 'billion', 'High'),

            # Pattern 4: Up to $XX million (greenshoe/max)
            (r'[Uu]p\s+to\s+\$\s*([\d,]+(?:\.\d+)?)\s*million', 'million', 'Medium'),

            # Pattern 5: Aggregate offering price up to $XXX
            (r'[Aa]ggregate\s+[Oo]ffering\s+[Pp]rice.*?\$\s*([\d,]+(?:\.\d+)?)', 'exact', 'Medium'),
        ]

        for pattern, multiplier, confidence in patterns:
            match = re.search(pattern, self.cover_page, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                amount = Decimal(amount_str)

                # Apply multiplier
                if multiplier == 'million':
                    amount = amount * 1_000_000
                elif multiplier == 'billion':
                    amount = amount * 1_000_000_000

                return {
                    'amount': str(amount),
                    'currency': 'USD',
                    'confidence': confidence,
                    'raw_text': match.group(0),
                    'multiplier': multiplier
                }

        return {
            'amount': None,
            'currency': 'USD',
            'confidence': 'None',
            'raw_text': None,
            'multiplier': None
        }

    def extract_security_type(self) -> Dict[str, Any]:
        """
        Extract security type (Common Stock, Preferred Stock, Notes, etc.).

        Returns:
            Dictionary with:
                - security_type: Type of security
                - confidence: High/Medium/Low
                - raw_text: Original matched text
        """
        patterns = [
            # Pattern 1: Shares of Common Stock/Preferred Stock
            (r'(?:shares?\s+of\s+)?([Cc]ommon\s+[Ss]tock)', 'High'),
            (r'(?:shares?\s+of\s+)?([Pp]referred\s+[Ss]tock)', 'High'),
            (r'(?:shares?\s+of\s+)?([Cc]lass\s+[A-Z]\s+[Cc]ommon\s+[Ss]tock)', 'High'),

            # Pattern 2: Notes/Bonds
            (r'(\d+(?:\.\d+)?%\s+[Ss]enior\s+[Nn]otes?\s+due\s+\d{4})', 'High'),
            (r'([Ss]enior\s+[Nn]otes?)', 'Medium'),
            (r'([Cc]onvertible\s+[Nn]otes?)', 'High'),
            (r'([Ss]ubordinated\s+[Nn]otes?)', 'High'),

            # Pattern 3: Warrants
            (r'([Ww]arrants?\s+to\s+[Pp]urchase)', 'High'),
            (r'([Ww]arrants?)', 'Low'),  # Too generic

            # Pattern 4: Units
            (r'([Uu]nits?\s+consisting\s+of)', 'High'),

            # Pattern 5: ADR/ADS
            (r'([Aa]merican\s+[Dd]epositary\s+[Ss]hares?)', 'High'),
            (r'(ADS)', 'Medium'),
        ]

        for pattern, confidence in patterns:
            match = re.search(pattern, self.cover_page)
            if match:
                return {
                    'security_type': match.group(1),
                    'confidence': confidence,
                    'raw_text': match.group(0)
                }

        return {
            'security_type': None,
            'confidence': 'None',
            'raw_text': None
        }

    def extract_offering_price(self) -> Dict[str, Any]:
        """
        Extract offering price per share/security.

        Returns:
            Dictionary with:
                - price: Price per share (as string)
                - currency: Currency code
                - price_type: fixed/market/range
                - confidence: High/Medium/Low
                - raw_text: Original matched text
        """
        patterns = [
            # Pattern 1: Fixed price: $XX.XX per share
            (r'\$\s*([\d,]+(?:\.\d+)?)\s+per\s+share', 'fixed', 'High'),

            # Pattern 2: Price range: $XX.XX to $XX.XX per share
            (r'\$\s*([\d,]+(?:\.\d+)?)\s+to\s+\$\s*([\d,]+(?:\.\d+)?)\s+per\s+share', 'range', 'High'),

            # Pattern 3: Market price/ATM: "at market prices"
            (r'at\s+market\s+prices?', 'market', 'Medium'),
            (r'at-the-market', 'market', 'High'),

            # Pattern 4: Public offering price: $XX.XX
            (r'[Pp]ublic\s+[Oo]ffering\s+[Pp]rice.*?\$\s*([\d,]+(?:\.\d+)?)', 'fixed', 'Medium'),
        ]

        for pattern, price_type, confidence in patterns:
            match = re.search(pattern, self.cover_page, re.IGNORECASE)
            if match:
                if price_type == 'range':
                    return {
                        'price': match.group(1),
                        'price_high': match.group(2),
                        'currency': 'USD',
                        'price_type': price_type,
                        'confidence': confidence,
                        'raw_text': match.group(0)
                    }
                elif price_type == 'market':
                    return {
                        'price': 'market',
                        'currency': 'USD',
                        'price_type': price_type,
                        'confidence': confidence,
                        'raw_text': match.group(0)
                    }
                else:
                    return {
                        'price': match.group(1).replace(',', ''),
                        'currency': 'USD',
                        'price_type': price_type,
                        'confidence': confidence,
                        'raw_text': match.group(0)
                    }

        return {
            'price': None,
            'currency': 'USD',
            'price_type': None,
            'confidence': 'None',
            'raw_text': None
        }

    def extract_share_count(self) -> Dict[str, Any]:
        """
        Extract number of shares/securities offered.

        Returns:
            Dictionary with:
                - share_count: Number of shares
                - confidence: High/Medium/Low
                - raw_text: Original matched text
        """
        patterns = [
            # Pattern 1: Exact count: XXX,XXX,XXX shares
            (r'([\d,]+)\s+shares?\s+of', 'High'),

            # Pattern 2: Up to XXX,XXX shares
            (r'[Uu]p\s+to\s+([\d,]+)\s+shares?', 'Medium'),

            # Pattern 3: XXX,XXX shares of Common Stock
            (r'([\d,]+)\s+shares?\s+of\s+(?:[Cc]ommon|[Pp]referred)', 'High'),
        ]

        for pattern, confidence in patterns:
            match = re.search(pattern, self.cover_page)
            if match:
                share_count = match.group(1).replace(',', '')
                return {
                    'share_count': share_count,
                    'confidence': confidence,
                    'raw_text': match.group(0)
                }

        return {
            'share_count': None,
            'confidence': 'None',
            'raw_text': None
        }

    def extract_gross_proceeds(self) -> Dict[str, Any]:
        """
        Extract gross proceeds from offering.

        Returns:
            Dictionary with:
                - amount: Gross proceeds amount
                - currency: Currency code
                - confidence: High/Medium/Low
                - raw_text: Original matched text
        """
        patterns = [
            # Pattern 1: Explicit gross proceeds
            (r'[Gg]ross\s+[Pp]roceeds.*?\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion)?', 'High'),

            # Pattern 2: Total gross proceeds (in table context)
            (r'[Tt]otal\s+[Gg]ross\s+[Pp]roceeds.*?\$\s*([\d,]+(?:\.\d+)?)', 'High'),
        ]

        for pattern, confidence in patterns:
            match = re.search(pattern, self.cover_page[:20000], re.IGNORECASE)  # Extended search
            if match:
                amount_str = match.group(1).replace(',', '')
                amount = Decimal(amount_str)

                # Check for multiplier
                if len(match.groups()) > 1 and match.group(2):
                    if 'million' in match.group(2).lower():
                        amount = amount * 1_000_000
                    elif 'billion' in match.group(2).lower():
                        amount = amount * 1_000_000_000

                return {
                    'amount': str(amount),
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

    def extract_net_proceeds(self) -> Dict[str, Any]:
        """
        Extract net proceeds (after expenses/discounts).

        Returns:
            Dictionary with:
                - amount: Net proceeds amount
                - currency: Currency code
                - confidence: High/Medium/Low
                - raw_text: Original matched text
        """
        patterns = [
            # Pattern 1: Explicit net proceeds
            (r'[Nn]et\s+[Pp]roceeds.*?\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion)?', 'High'),

            # Pattern 2: Total net proceeds
            (r'[Tt]otal\s+[Nn]et\s+[Pp]roceeds.*?\$\s*([\d,]+(?:\.\d+)?)', 'High'),

            # Pattern 3: After deducting (implies net)
            (r'[Aa]fter\s+[Dd]educting.*?\$\s*([\d,]+(?:\.\d+)?)\s*(million|billion)?', 'Medium'),
        ]

        for pattern, confidence in patterns:
            match = re.search(pattern, self.cover_page[:20000], re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                amount = Decimal(amount_str)

                # Check for multiplier
                if len(match.groups()) > 1 and match.group(2):
                    if 'million' in match.group(2).lower():
                        amount = amount * 1_000_000
                    elif 'billion' in match.group(2).lower():
                        amount = amount * 1_000_000_000

                return {
                    'amount': str(amount),
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

    def extract_registration_number(self) -> Dict[str, Any]:
        """
        Extract SEC registration number (333-XXXXXX).

        Returns:
            Dictionary with:
                - registration_number: Registration number
                - confidence: High/Medium/Low
                - raw_text: Original matched text
        """
        patterns = [
            (r'Registration\s+(?:No\.|Number)\s+(333-\d+)', 'High'),
            (r'File\s+No\.\s+(333-\d+)', 'High'),
        ]

        for pattern, confidence in patterns:
            match = re.search(pattern, self.cover_page, re.IGNORECASE)
            if match:
                return {
                    'registration_number': match.group(1),
                    'confidence': confidence,
                    'raw_text': match.group(0)
                }

        return {
            'registration_number': None,
            'confidence': 'None',
            'raw_text': None
        }

    def extract_atm_indicator(self) -> Dict[str, Any]:
        """
        Detect if this is an at-the-market (ATM) offering.

        Returns:
            Dictionary with:
                - is_atm: Boolean indicator
                - confidence: High/Medium/Low
                - raw_text: Original matched text
        """
        patterns = [
            (r'at-the-market', 'High'),
            (r'ATM\s+[Oo]ffering', 'High'),
            (r'at\s+the\s+market\s+offering', 'High'),
            (r'sales\s+agreement.*at\s+market\s+prices', 'Medium'),
        ]

        for pattern, confidence in patterns:
            match = re.search(pattern, self.cover_page[:15000], re.IGNORECASE)
            if match:
                return {
                    'is_atm': True,
                    'confidence': confidence,
                    'raw_text': match.group(0)
                }

        return {
            'is_atm': False,
            'confidence': 'High',  # High confidence in absence
            'raw_text': None
        }

    def extract_all(self) -> Dict[str, Any]:
        """
        Extract all cover page fields.

        Returns:
            Dictionary with all extracted fields
        """
        return {
            'offering_amount': self.extract_offering_amount(),
            'security_type': self.extract_security_type(),
            'offering_price': self.extract_offering_price(),
            'share_count': self.extract_share_count(),
            'gross_proceeds': self.extract_gross_proceeds(),
            'net_proceeds': self.extract_net_proceeds(),
            'registration_number': self.extract_registration_number(),
            'atm_indicator': self.extract_atm_indicator(),
        }


if __name__ == '__main__':
    # Example usage
    from edgar import Filing

    # Test with a sample filing
    filing = Filing(form='424B5', accession_number='0001104659-24-041120')
    html = filing.html()

    extractor = CoverPageExtractor(html)
    results = extractor.extract_all()

    print("Cover Page Extraction Results:")
    print("=" * 60)
    for field, data in results.items():
        print(f"\n{field}:")
        for key, value in data.items():
            print(f"  {key}: {value}")
