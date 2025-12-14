"""
Section extraction from documents.
"""

import re
from typing import Dict, List, Optional, Tuple

from edgar.documents.document import Document, Section
from edgar.documents.nodes import HeadingNode, Node, SectionNode


class SectionExtractor:
    """
    Extracts logical sections from documents.
    
    Identifies document sections like:
    - Business Overview (Item 1)
    - Risk Factors (Item 1A)
    - MD&A (Item 7)
    - Financial Statements (Item 8)
    """

    # Common section patterns for different filing types
    SECTION_PATTERNS = {
        '10-K': {
            'business': [
                (r'^(Item|ITEM)\s+1\.?\s*Business', 'Item 1 - Business'),
                (r'^Business\s*$', 'Business'),
                (r'^Business Overview', 'Business Overview'),
                (r'^Our Business', 'Our Business'),
                (r'^Company Overview', 'Company Overview')
            ],
            'risk_factors': [
                (r'^(Item|ITEM)\s+1A\.?\s*Risk\s+Factors', 'Item 1A - Risk Factors'),
                (r'^Risk\s+Factors', 'Risk Factors'),
                (r'^Factors\s+That\s+May\s+Affect', 'Risk Factors')
            ],
            'properties': [
                (r'^(Item|ITEM)\s+2\.?\s*Properties', 'Item 2 - Properties'),
                (r'^Properties', 'Properties'),
                (r'^Real\s+Estate', 'Real Estate')
            ],
            'legal_proceedings': [
                (r'^(Item|ITEM)\s+3\.?\s*Legal\s+Proceedings', 'Item 3 - Legal Proceedings'),
                (r'^Legal\s+Proceedings', 'Legal Proceedings'),
                (r'^Litigation', 'Litigation')
            ],
            'market_risk': [
                (r'^(Item|ITEM)\s+7A\.?\s*Quantitative.*Disclosures', 'Item 7A - Market Risk'),
                (r'^Market\s+Risk', 'Market Risk'),
                (r'^Quantitative.*Qualitative.*Market\s+Risk', 'Market Risk')
            ],
            'mda': [
                (r'^(Item|ITEM)\s+7\.?\s*Management.*Discussion', 'Item 7 - MD&A'),
                (r'^Management.*Discussion.*Analysis', 'MD&A'),
                (r'^MD&A', 'MD&A')
            ],
            'financial_statements': [
                (r'^(Item|ITEM)\s+8\.?\s*Financial\s+Statements', 'Item 8 - Financial Statements'),
                (r'^Financial\s+Statements', 'Financial Statements'),
                (r'^Consolidated\s+Financial\s+Statements', 'Consolidated Financial Statements')
            ],
            'controls_procedures': [
                (r'^(Item|ITEM)\s+9A\.?\s*Controls.*Procedures', 'Item 9A - Controls and Procedures'),
                (r'^Controls.*Procedures', 'Controls and Procedures'),
                (r'^Internal\s+Control', 'Internal Controls')
            ]
        },
        '10-Q': {
            # PART I - Financial Information
            'part_i_item_1': [
                (r'^(Item|ITEM)\s+1\.?\s*[-–—.]?\s*Financial\s+Statements', 'Item 1 - Financial Statements'),
                (r'^Financial\s+Statements', 'Financial Statements'),
                (r'^Condensed.*Financial\s+Statements', 'Condensed Financial Statements')
            ],
            'part_i_item_2': [
                (r'^(Item|ITEM)\s+2\.?\s*[-–—.]?\s*Management.*Discussion', 'Item 2 - MD&A'),
                (r'^Management.*Discussion.*Analysis', 'MD&A')
            ],
            'part_i_item_3': [
                (r'^(Item|ITEM)\s+3\.?\s*[-–—.]?\s*Quantitative.*Disclosures', 'Item 3 - Market Risk'),
                (r'^Market\s+Risk', 'Market Risk')
            ],
            'part_i_item_4': [
                (r'^(Item|ITEM)\s+4\.?\s*[-–—.]?\s*Controls.*Procedures', 'Item 4 - Controls and Procedures'),
                (r'^Controls.*Procedures', 'Controls and Procedures')
            ],
            # PART II - Other Information
            'part_ii_item_1': [
                (r'^(Item|ITEM)\s+1\.?\s*[-–—.]?\s*Legal\s+Proceedings', 'Item 1 - Legal Proceedings'),
                (r'^Legal\s+Proceedings', 'Legal Proceedings')
            ],
            'part_ii_item_1a': [
                (r'^(Item|ITEM)\s+1A\.?\s*[-–—.]?\s*Risk\s+Factors', 'Item 1A - Risk Factors'),
                (r'^Risk\s+Factors', 'Risk Factors')
            ],
            'part_ii_item_2': [
                (r'^(Item|ITEM)\s+2\.?\s*[-–—.]?\s*Unregistered\s+Sales', 'Item 2 - Unregistered Sales'),
                (r'^Unregistered\s+Sales.*Equity', 'Unregistered Sales')
            ],
            'part_ii_item_3': [
                (r'^(Item|ITEM)\s+3\.?\s*[-–—.]?\s*Defaults', 'Item 3 - Defaults Upon Senior Securities'),
                (r'^Defaults\s+Upon\s+Senior', 'Defaults Upon Senior Securities')
            ],
            'part_ii_item_4': [
                (r'^(Item|ITEM)\s+4\.?\s*[-–—.]?\s*Mine\s+Safety', 'Item 4 - Mine Safety Disclosures'),
                (r'^Mine\s+Safety', 'Mine Safety Disclosures')
            ],
            'part_ii_item_5': [
                (r'^(Item|ITEM)\s+5\.?\s*[-–—.]?\s*Other\s+Information', 'Item 5 - Other Information'),
                (r'^Other\s+Information', 'Other Information')
            ],
            'part_ii_item_6': [
                (r'^(Item|ITEM)\s+6\.?\s*[-–—.]?\s*Exhibits', 'Item 6 - Exhibits'),
                (r'^Exhibits', 'Exhibits')
            ]
        },
        '20-F': {
            # PART I
            'item_1': [
                (r'^(Item|ITEM)\s+1\.?\s*[-–—.]?\s*Identity.*Directors', 'Item 1 - Identity of Directors, Senior Management and Advisers'),
                (r'^Identity.*Directors.*Senior\s+Management', 'Identity of Directors')
            ],
            'item_2': [
                (r'^(Item|ITEM)\s+2\.?\s*[-–—.]?\s*Offer\s+Statistics', 'Item 2 - Offer Statistics and Expected Timetable'),
                (r'^Offer\s+Statistics.*Timetable', 'Offer Statistics')
            ],
            'item_3': [
                (r'^(Item|ITEM)\s+3\.?\s*[-–—.]?\s*Key\s+Information', 'Item 3 - Key Information'),
                (r'^Key\s+Information', 'Key Information'),
                (r'^Risk\s+Factors', 'Risk Factors')
            ],
            'item_4': [
                (r'^(Item|ITEM)\s+4\.?\s*[-–—.]?\s*Information\s+on\s+the\s+Company', 'Item 4 - Information on the Company'),
                (r'^Information\s+on\s+the\s+Company', 'Information on the Company'),
                (r'^Business\s+Overview', 'Business Overview')
            ],
            'item_4a': [
                (r'^(Item|ITEM)\s+4A\.?\s*[-–—.]?\s*Unresolved\s+Staff', 'Item 4A - Unresolved Staff Comments'),
                (r'^Unresolved\s+Staff\s+Comments', 'Unresolved Staff Comments')
            ],
            # PART II
            'item_5': [
                (r'^(Item|ITEM)\s+5\.?\s*[-–—.]?\s*Operating.*Financial\s+Review', 'Item 5 - Operating and Financial Review and Prospects'),
                (r'^Operating.*Financial\s+Review', 'Operating and Financial Review'),
                (r'^Management.*Discussion.*Analysis', 'MD&A')
            ],
            'item_6': [
                (r'^(Item|ITEM)\s+6\.?\s*[-–—.]?\s*Directors.*Senior\s+Management.*Employees', 'Item 6 - Directors, Senior Management and Employees'),
                (r'^Directors.*Senior\s+Management.*Employees', 'Directors and Employees')
            ],
            'item_7': [
                (r'^(Item|ITEM)\s+7\.?\s*[-–—.]?\s*Major\s+Shareholders', 'Item 7 - Major Shareholders and Related Party Transactions'),
                (r'^Major\s+Shareholders.*Related\s+Party', 'Major Shareholders')
            ],
            'item_8': [
                (r'^(Item|ITEM)\s+8\.?\s*[-–—.]?\s*Financial\s+Information', 'Item 8 - Financial Information'),
                (r'^Financial\s+Information', 'Financial Information')
            ],
            'item_9': [
                (r'^(Item|ITEM)\s+9\.?\s*[-–—.]?\s*The\s+Offer\s+and\s+Listing', 'Item 9 - The Offer and Listing'),
                (r'^The\s+Offer\s+and\s+Listing', 'Offer and Listing')
            ],
            # PART III
            'item_10': [
                (r'^(Item|ITEM)\s+10\.?\s*[-–—.]?\s*Additional\s+Information', 'Item 10 - Additional Information'),
                (r'^Additional\s+Information', 'Additional Information')
            ],
            'item_11': [
                (r'^(Item|ITEM)\s+11\.?\s*[-–—.]?\s*Quantitative.*Qualitative.*Market\s+Risk', 'Item 11 - Quantitative and Qualitative Disclosures About Market Risk'),
                (r'^Quantitative.*Qualitative.*Market\s+Risk', 'Market Risk Disclosures')
            ],
            'item_12': [
                (r'^(Item|ITEM)\s+12\.?\s*[-–—.]?\s*Description.*Securities', 'Item 12 - Description of Securities Other Than Equity Securities'),
                (r'^Description.*Securities.*Equity', 'Securities Description')
            ],
            # PART IV
            'item_13': [
                (r'^(Item|ITEM)\s+13\.?\s*[-–—.]?\s*Defaults', 'Item 13 - Defaults, Dividend Arrearages and Delinquencies'),
                (r'^Defaults.*Dividend.*Arrearages', 'Defaults and Arrearages')
            ],
            'item_14': [
                (r'^(Item|ITEM)\s+14\.?\s*[-–—.]?\s*Material\s+Modifications', 'Item 14 - Material Modifications to the Rights of Security Holders'),
                (r'^Material\s+Modifications.*Rights', 'Material Modifications')
            ],
            'item_15': [
                (r'^(Item|ITEM)\s+15\.?\s*[-–—.]?\s*Controls.*Procedures', 'Item 15 - Controls and Procedures'),
                (r'^Controls.*Procedures', 'Controls and Procedures')
            ],
            'item_16': [
                (r'^(Item|ITEM)\s+16\.?\s*[-–—.]?\s*\[?Reserved\]?', 'Item 16 - [Reserved]')
            ],
            'item_16a': [
                (r'^(Item|ITEM)\s+16A\.?\s*[-–—.]?\s*Audit\s+Committee', 'Item 16A - Audit Committee Financial Expert'),
                (r'^Audit\s+Committee\s+Financial\s+Expert', 'Audit Committee Expert')
            ],
            'item_16b': [
                (r'^(Item|ITEM)\s+16B\.?\s*[-–—.]?\s*Code\s+of\s+Ethics', 'Item 16B - Code of Ethics'),
                (r'^Code\s+of\s+Ethics', 'Code of Ethics')
            ],
            'item_16c': [
                (r'^(Item|ITEM)\s+16C\.?\s*[-–—.]?\s*Principal\s+Accountant', 'Item 16C - Principal Accountant Fees and Services'),
                (r'^Principal\s+Accountant\s+Fees', 'Accountant Fees')
            ],
            'item_16d': [
                (r'^(Item|ITEM)\s+16D\.?\s*[-–—.]?\s*Exemptions.*Audit\s+Committees', 'Item 16D - Exemptions from the Listing Standards for Audit Committees'),
                (r'^Exemptions.*Listing\s+Standards', 'Audit Committee Exemptions')
            ],
            'item_16e': [
                (r'^(Item|ITEM)\s+16E\.?\s*[-–—.]?\s*Purchases.*Equity\s+Securities', 'Item 16E - Purchases of Equity Securities by the Issuer'),
                (r'^Purchases.*Equity\s+Securities.*Issuer', 'Equity Purchases')
            ],
            'item_16f': [
                (r'^(Item|ITEM)\s+16F\.?\s*[-–—.]?\s*Change.*Certifying\s+Accountant', 'Item 16F - Change in Registrant\'s Certifying Accountant'),
                (r'^Change.*Certifying\s+Accountant', 'Accountant Change')
            ],
            'item_16g': [
                (r'^(Item|ITEM)\s+16G\.?\s*[-–—.]?\s*Corporate\s+Governance', 'Item 16G - Corporate Governance'),
                (r'^Corporate\s+Governance', 'Corporate Governance')
            ],
            'item_16h': [
                (r'^(Item|ITEM)\s+16H\.?\s*[-–—.]?\s*Mine\s+Safety', 'Item 16H - Mine Safety Disclosure'),
                (r'^Mine\s+Safety\s+Disclosure', 'Mine Safety')
            ],
            'item_16i': [
                (r'^(Item|ITEM)\s+16I\.?\s*[-–—.]?\s*Disclosure.*Foreign\s+Jurisdictions', 'Item 16I - Disclosure Regarding Foreign Jurisdictions That Prevent Inspections'),
                (r'^Disclosure.*Foreign\s+Jurisdictions.*Inspections', 'Foreign Jurisdiction Disclosure'),
                # Fallback: match just "Item 16I" for filings where title is on separate line
                (r'^(Item|ITEM)\s+16I\.?\s*$', 'Item 16I')
            ],
            'item_16j': [
                (r'^(Item|ITEM)\s+16J\.?\s*[-–—.]?\s*Insider\s+Trading', 'Item 16J - Insider Trading Policies'),
                (r'^Insider\s+Trading\s+Policies', 'Insider Trading Policies'),
                # Fallback: match just "Item 16J" for filings where title is on separate line
                (r'^(Item|ITEM)\s+16J\.?\s*$', 'Item 16J')
            ],
            'item_16k': [
                (r'^(Item|ITEM)\s+16K\.?\s*[-–—.]?\s*Cybersecurity', 'Item 16K - Cybersecurity'),
                (r'^Cybersecurity', 'Cybersecurity'),
                # Fallback: match just "Item 16K" for filings where title is on separate line
                (r'^(Item|ITEM)\s+16K\.?\s*$', 'Item 16K')
            ],
            # PART V
            'item_17': [
                (r'^(Item|ITEM)\s+17\.?\s*[-–—.]?\s*Financial\s+Statements', 'Item 17 - Financial Statements'),
            ],
            'item_18': [
                (r'^(Item|ITEM)\s+18\.?\s*[-–—.]?\s*Financial\s+Statements', 'Item 18 - Financial Statements'),
            ],
            'item_19': [
                (r'^(Item|ITEM)\s+19\.?\s*[-–—.]?\s*Exhibits', 'Item 19 - Exhibits'),
                (r'^Exhibits', 'Exhibits')
            ],
            # PARTS
            'part_i': [
                (r'^PART\s+I\s*$', 'Part I')
            ],
            'part_ii': [
                (r'^PART\s+II\s*$', 'Part II')
            ],
            'part_iii': [
                (r'^PART\s+III\s*$', 'Part III')
            ],
            'part_iv': [
                (r'^PART\s+IV\s*$', 'Part IV')
            ],
            'part_v': [
                (r'^PART\s+V\s*$', 'Part V')
            ],
            'signatures': [
                (r'^SIGNATURES?\s*$', 'Signatures')
            ]
        },
        '8-K': {
            # Section 1: Registrant's Business and Operations
            'item_101': [
                (r'^(Item|ITEM)\s+1\.\s*01', 'Item 1.01 - Entry into Material Agreement'),
                (r'^Entry.*Material.*Agreement', 'Material Agreement')
            ],
            'item_102': [
                (r'^(Item|ITEM)\s+1\.\s*02', 'Item 1.02 - Termination of Material Agreement'),
                (r'^Termination.*Material.*Agreement', 'Termination of Agreement')
            ],
            'item_103': [
                (r'^(Item|ITEM)\s+1\.\s*03', 'Item 1.03 - Bankruptcy or Receivership'),
                (r'^Bankruptcy.*Receivership', 'Bankruptcy')
            ],
            'item_104': [
                (r'^(Item|ITEM)\s+1\.\s*04', 'Item 1.04 - Mine Safety'),
                (r'^Mine\s+Safety', 'Mine Safety')
            ],
            'item_105': [
                (r'^(Item|ITEM)\s+1\.\s*05', 'Item 1.05 - Material Cybersecurity Incidents'),
                (r'^Material\s+Cybersecurity', 'Cybersecurity Incidents')
            ],

            # Section 2: Financial Information
            'item_201': [
                (r'^(Item|ITEM)\s+2\.\s*01', 'Item 2.01 - Completion of Acquisition'),
                (r'^Completion.*Acquisition', 'Acquisition')
            ],
            'item_202': [
                (r'^(Item|ITEM)\s+2\.\s*02', 'Item 2.02 - Results of Operations'),
                (r'^Results.*Operations', 'Results of Operations')
            ],
            'item_203': [
                (r'^(Item|ITEM)\s+2\.\s*03', 'Item 2.03 - Creation of Direct Financial Obligation'),
                (r'^Creation.*Financial\s+Obligation', 'Financial Obligation')
            ],
            'item_204': [
                (r'^(Item|ITEM)\s+2\.\s*04', 'Item 2.04 - Triggering Events'),
                (r'^Triggering\s+Events', 'Triggering Events')
            ],
            'item_205': [
                (r'^(Item|ITEM)\s+2\.\s*05', 'Item 2.05 - Costs with Exit or Disposal'),
                (r'^Costs.*Exit.*Disposal', 'Exit or Disposal Costs')
            ],
            'item_206': [
                (r'^(Item|ITEM)\s+2\.\s*06', 'Item 2.06 - Material Impairments'),
                (r'^Material\s+Impairments', 'Material Impairments')
            ],

            # Section 3: Securities and Trading Markets
            'item_301': [
                (r'^(Item|ITEM)\s+3\.\s*01', 'Item 3.01 - Notice of Delisting'),
                (r'^Notice.*Delisting', 'Delisting Notice')
            ],
            'item_302': [
                (r'^(Item|ITEM)\s+3\.\s*02', 'Item 3.02 - Unregistered Sales of Equity'),
                (r'^Unregistered\s+Sales', 'Unregistered Sales')
            ],
            'item_303': [
                (r'^(Item|ITEM)\s+3\.\s*03', 'Item 3.03 - Material Modification to Rights'),
                (r'^Material\s+Modification.*Rights', 'Rights Modification')
            ],

            # Section 4: Accountants and Financial Statements
            'item_401': [
                (r'^(Item|ITEM)\s+4\.\s*01', 'Item 4.01 - Changes in Certifying Accountant'),
                (r'^Changes.*Accountant', 'Accountant Changes')
            ],
            'item_402': [
                (r'^(Item|ITEM)\s+4\.\s*02', 'Item 4.02 - Non-Reliance on Financial Statements'),
                (r'^Non-Reliance.*Financial', 'Non-Reliance')
            ],

            # Section 5: Corporate Governance and Management
            'item_501': [
                (r'^(Item|ITEM)\s+5\.\s*01', 'Item 5.01 - Changes in Control'),
                (r'^Changes.*Control', 'Changes in Control')
            ],
            'item_502': [
                (r'^(Item|ITEM)\s+5\.\s*02', 'Item 5.02 - Departure/Election of Directors'),
                (r'^Departure.*Directors.*Officers', 'Director/Officer Changes')
            ],
            'item_503': [
                (r'^(Item|ITEM)\s+5\.\s*03', 'Item 5.03 - Amendments to Articles/Bylaws'),
                (r'^Amendments.*Articles.*Bylaws', 'Charter Amendments')
            ],
            'item_504': [
                (r'^(Item|ITEM)\s+5\.\s*04', 'Item 5.04 - Temporary Suspension of Trading'),
                (r'^Temporary\s+Suspension', 'Suspension of Trading')
            ],
            'item_505': [
                (r'^(Item|ITEM)\s+5\.\s*05', 'Item 5.05 - Amendment to Code of Ethics'),
                (r'^Amendment.*Code.*Ethics', 'Code of Ethics')
            ],
            'item_506': [
                (r'^(Item|ITEM)\s+5\.\s*06', 'Item 5.06 - Change in Shell Company Status'),
                (r'^Change.*Shell\s+Company', 'Shell Company Status')
            ],
            'item_507': [
                (r'^(Item|ITEM)\s+5\.\s*07', 'Item 5.07 - Submission of Matters to Vote'),
                (r'^Submission.*Vote', 'Shareholder Vote')
            ],
            'item_508': [
                (r'^(Item|ITEM)\s+5\.\s*08', 'Item 5.08 - Shareholder Nominations'),
                (r'^Shareholder\s+Nominations', 'Shareholder Nominations')
            ],

            # Section 6: Asset-Backed Securities
            'item_601': [
                (r'^(Item|ITEM)\s+6\.\s*01', 'Item 6.01 - ABS Informational Material'),
                (r'^ABS\s+Informational', 'ABS Information')
            ],
            'item_602': [
                (r'^(Item|ITEM)\s+6\.\s*02', 'Item 6.02 - Change of Servicer/Trustee'),
                (r'^Change.*Servicer.*Trustee', 'Servicer Change')
            ],
            'item_603': [
                (r'^(Item|ITEM)\s+6\.\s*03', 'Item 6.03 - Change in Credit Enhancement'),
                (r'^Change.*Credit\s+Enhancement', 'Credit Enhancement')
            ],
            'item_604': [
                (r'^(Item|ITEM)\s+6\.\s*04', 'Item 6.04 - Failure to Make Distribution'),
                (r'^Failure.*Distribution', 'Distribution Failure')
            ],
            'item_605': [
                (r'^(Item|ITEM)\s+6\.\s*05', 'Item 6.05 - Securities Act Updating'),
                (r'^Securities\s+Act\s+Updating', 'Securities Act Update')
            ],
            'item_606': [
                (r'^(Item|ITEM)\s+6\.\s*06', 'Item 6.06 - Static Pool'),
                (r'^Static\s+Pool', 'Static Pool')
            ],

            # Section 7: Regulation FD
            'item_701': [
                (r'^(Item|ITEM)\s+7\.\s*01', 'Item 7.01 - Regulation FD Disclosure'),
                (r'^Regulation\s+FD', 'Regulation FD')
            ],

            # Section 8: Other Events
            'item_801': [
                (r'^(Item|ITEM)\s+8\.\s*01', 'Item 8.01 - Other Events'),
                (r'^Other\s+Events', 'Other Events')
            ],

            # Section 9: Financial Statements and Exhibits
            'item_901': [
                (r'^(Item|ITEM)\s+9\.\s*01', 'Item 9.01 - Financial Statements and Exhibits'),
                (r'^Financial.*Exhibits', 'Financial Statements and Exhibits')
            ]
        }
    }

    def __init__(self, form: Optional[str] = None):
        """
        Initialize section extractor.
        
        Args:
            form: Type of filing (10-K, 10-Q, 8-K, etc.)
        """
        self.form = form

    def extract(self, document: Document) -> Dict[str, Section]:
        """
        Extract sections from document.

        Args:
            document: Document to extract sections from

        Returns:
            Dictionary mapping section names to Section objects
        """
        # Get filing type from instance, metadata, or document config
        # NOTE: We no longer auto-detect filing type (expensive and unnecessary)
        form = None

        if self.form:
            form = self.form
        elif document.metadata and document.metadata.form:
            form = document.metadata.form
        elif hasattr(document, '_config') and document._config and document._config.form:
            form = document._config.form

        # Only extract sections for forms that have standard sections
        if not form or form not in ['10-K', '10-Q', '8-K', '20-F']:
            return {}  # No filing type or unsupported form = no section detection

        # Get patterns for filing type
        patterns = self.SECTION_PATTERNS.get(form, {})
        if not patterns:
            return {}  # No patterns defined for this form type

        # Find section headers
        headers = self._find_section_headers(document)

        # For 10-Q, detect Part I/Part II boundaries
        part_context = None
        if form == '10-Q':
            part_context = self._detect_10q_parts(headers)

        # Match headers to sections
        sections = self._match_sections(headers, patterns, document, part_context)

        # Create section objects
        return self._create_sections(sections, document)

    # NOTE: _detect_form() removed - form type should be known from context
    # Filing metadata should be set by the caller (Filing class, TenK/TenQ, etc.)

    # NOTE: _infer_form_from_headers() kept for backward compatibility but not used
    # in normal flow anymore. Form type should always be provided explicitly.
    def _infer_form_from_headers(self, document: Document) -> str:
        """
        Infer filing type from section headers.

        NOTE: This method is kept for backward compatibility but should not be used
        in the normal flow. Form type should be explicitly provided via config or metadata.
        """
        headers = document.headings
        header_texts = [h.text().upper() for h in headers if h.text()]

        # Check for 10-K specific sections
        has_10k_sections = any(
            'ITEM 1.' in text or 'ITEM 1A.' in text or 'ITEM 7.' in text or 'ITEM 8.' in text
            for text in header_texts
        )

        # Check for 10-Q specific sections
        has_10q_sections = any(
            ('ITEM 1.' in text and 'FINANCIAL STATEMENTS' in text) or
            ('ITEM 2.' in text and 'MANAGEMENT' in text) or
            'ITEM 3.' in text or 'ITEM 4.' in text
            for text in header_texts
        )

        # Check for 8-K specific sections
        has_8k_sections = any(
            re.search(r'ITEM \d\.\d{2}', text) for text in header_texts
        )

        if has_10k_sections and not has_10q_sections:
            return '10-K'
        elif has_10q_sections:
            return '10-Q'
        elif has_8k_sections:
            return '8-K'
        else:
            return 'UNKNOWN'

    def _get_general_patterns(self) -> Dict[str, List[Tuple[str, str]]]:
        """Get general section patterns."""
        return {
            'business': [
                (r'^Business', 'Business'),
                (r'^Overview', 'Overview'),
                (r'^Company', 'Company')
            ],
            'financial': [
                (r'^Financial\s+Statements', 'Financial Statements'),
                (r'^Consolidated.*Statements', 'Consolidated Statements')
            ],
            'notes': [
                (r'^Notes\s+to.*Financial\s+Statements', 'Notes to Financial Statements'),
                (r'^Notes\s+to.*Statements', 'Notes')
            ]
        }

    def _is_bold(self, node: Node) -> bool:
        """
        Check if node has bold styling.

        Args:
            node: Node to check for bold styling

        Returns:
            True if node has bold font-weight (>= 700), False otherwise
        """
        if not hasattr(node, 'style') or not node.style:
            return False

        fw = node.style.font_weight
        if not fw:
            return False

        # Check for string values
        if fw in ['bold', '700']:
            return True

        # Handle numeric font-weight values
        try:
            if int(fw) >= 700:
                return True
        except (ValueError, TypeError):
            pass

        return False

    def _find_section_headers(self, document: Document) -> List[Tuple[Node, str, int]]:
        """
        Find all potential section headers.

        Searches for section headers using multiple strategies:
        1. HeadingNode objects (semantic HTML headings)
        2. SectionNode objects with embedded headings
        3. Bold ParagraphNode objects (fallback for filings without semantic headings)
        4. TableNode cells (fallback for filings using table-based layouts)
        5. Plain text ParagraphNode objects (final fallback for filings with no styling)

        Returns:
            List of tuples: (node, text, position)
        """
        headers = []

        # Strategy 1: Find all heading nodes (most reliable)
        heading_nodes = document.root.find(lambda n: isinstance(n, HeadingNode))

        for node in heading_nodes:
            text = node.text()
            if text:
                # Get position in document
                position = self._get_node_position(node, document)
                headers.append((node, text, position))

        # Strategy 2: Also check for section nodes with embedded headings
        section_nodes = document.root.find(lambda n: isinstance(n, SectionNode))
        for node in section_nodes:
            # Get first heading in section
            first_heading = node.find_first(lambda n: isinstance(n, HeadingNode))
            if first_heading:
                text = first_heading.text()
                if text:
                    position = self._get_node_position(node, document)
                    headers.append((node, text, position))

        # Strategy 3: Fallback to bold ParagraphNode objects
        # Many 8-K filings (55%) use bold paragraphs instead of semantic headings
        # Only run if no COMPLETE Item headers found yet
        # A complete header has title text after the Item number (e.g., "Item 3. Key Information")
        # An incomplete header is just "Item 3." without title - common in 20-F headings
        def is_complete_item_header(text):
            """Check if header has title text after Item number."""
            match = re.match(r'^(Item|ITEM)\s+\d+[A-Za-z]?\.?\s*[-–—.]?\s*(.+)?$', text.strip(), re.IGNORECASE)
            if match:
                title = match.group(2)
                # Must have substantive title text (not just punctuation or whitespace)
                return title and len(title.strip()) > 3
            return False

        has_complete_item_headers = any(is_complete_item_header(text) for _, text, _ in headers)
        if not has_complete_item_headers:
            from edgar.documents.nodes import ParagraphNode
            paragraph_nodes = document.root.find(lambda n: isinstance(n, ParagraphNode))

            for node in paragraph_nodes:
                if self._is_bold(node):
                    text = node.text()
                    if text:
                        position = self._get_node_position(node, document)
                        headers.append((node, text, position))

        # Strategy 4: Fallback to table cells with Item patterns
        # Many 8-K filings use tables for layout with Items in table cells
        # Check again after Strategy 3
        has_item_headers = any(re.search(r'Item\s+\d', text, re.IGNORECASE) for _, text, _ in headers)
        if not has_item_headers:
            from edgar.documents.table_nodes import TableNode
            table_nodes = document.root.find(lambda n: isinstance(n, TableNode))

            for table in table_nodes:
                # Look through table rows for Items
                for row in table.rows:
                    # Check each cell for Item pattern
                    row_text_parts = []
                    for cell in row.cells:
                        cell_text = cell.text().strip()
                        if cell_text:
                            row_text_parts.append(cell_text)

                    # Combine cell texts (Items often split across cells)
                    row_text = ' '.join(row_text_parts)

                    # Check if this row contains an Item pattern
                    if re.match(r'^\s*Item\s+\d', row_text, re.IGNORECASE):
                        position = self._get_node_position(table, document)
                        headers.append((table, row_text, position))
                        # Only take the first Item from each table to avoid duplicates
                        break

        # Strategy 5: Final fallback to ANY paragraph with Item pattern (plain text)
        # For filings that use no bold styling, no headings, and no tables
        # This is the last resort - check all paragraphs for Item patterns
        has_item_headers = any(re.search(r'Item\s+\d', text, re.IGNORECASE) for _, text, _ in headers)
        if not has_item_headers:
            from edgar.documents.nodes import ParagraphNode
            paragraph_nodes = document.root.find(lambda n: isinstance(n, ParagraphNode))

            for node in paragraph_nodes:
                text = node.text()
                # Look for Item pattern at start of paragraph (first 100 chars)
                # This catches plain text Items without any styling
                if text and len(text) < 500:  # Reasonable header length
                    text_start = text[:100].strip()
                    # Match Item X.XX at the start
                    if re.match(r'^\s*Item\s+\d', text_start, re.IGNORECASE):
                        position = self._get_node_position(node, document)
                        # Use the full paragraph text for matching
                        headers.append((node, text.strip(), position))

        # Sort by position
        headers.sort(key=lambda x: x[2])

        return headers

    def _get_node_position(self, node: Node, document: Document) -> int:
        """Get position of node in document."""
        position = 0
        for n in document.root.walk():
            if n == node:
                return position
            position += 1
        return position

    def _detect_10q_parts(self, headers: List[Tuple[Node, str, int]]) -> Dict[int, str]:
        """
        Detect Part I and Part II boundaries in 10-Q filings.

        Args:
            headers: List of (node, text, position) tuples

        Returns:
            Dict mapping header index to part name ("Part I" or "Part II")
        """
        part_context = {}
        current_part = None

        part_i_pattern = re.compile(r'^\s*PART\s+I\b', re.IGNORECASE)
        part_ii_pattern = re.compile(r'^\s*PART\s+II\b', re.IGNORECASE)

        for i, (node, text, position) in enumerate(headers):
            text_stripped = text.strip()

            # Check if this is a Part I or Part II header
            if part_i_pattern.match(text_stripped):
                current_part = "Part I"
                part_context[i] = current_part
            elif part_ii_pattern.match(text_stripped):
                current_part = "Part II"
                part_context[i] = current_part
            elif current_part:
                # Headers after a Part declaration belong to that part
                part_context[i] = current_part

        return part_context

    def _match_sections(self,
                       headers: List[Tuple[Node, str, int]],
                       patterns: Dict[str, List[Tuple[str, str]]],
                       document: Document,
                       part_context: Optional[Dict[int, str]] = None) -> Dict[str, Tuple[Node, str, int, int]]:
        """Match headers to section patterns."""
        matched_sections = {}
        used_headers = set()

        # Try to match each pattern
        for section_name, section_patterns in patterns.items():
            for pattern, title in section_patterns:
                for i, (node, text, position) in enumerate(headers):
                    if i in used_headers:
                        continue

                    # For 10-Q part-qualified patterns, validate against part context
                    if part_context and section_name.startswith('part_'):
                        expected_part = "Part I" if section_name.startswith('part_i_') else "Part II"
                        actual_part = part_context.get(i)
                        # Skip if part context doesn't match expected part
                        if actual_part and actual_part != expected_part:
                            continue

                    # Try to match pattern
                    if re.match(pattern, text.strip(), re.IGNORECASE):
                        # Find end position (next section or end of document)
                        end_position = self._find_section_end(i, headers, document)

                        # For 10-Q, prefix with Part I or Part II in title
                        final_title = title
                        if part_context and i in part_context:
                            final_title = f"{part_context[i]} - {title}"

                        # Use section_name as key (already part-qualified for 10-Q)
                        section_key = section_name
                        matched_sections[section_key] = (node, final_title, position, end_position)
                        used_headers.add(i)
                        break

                # If we found a match, move to next section
                if section_name in matched_sections:
                    break

        return matched_sections

    def _find_section_end(self, 
                         section_index: int, 
                         headers: List[Tuple[Node, str, int]],
                         document: Document) -> int:
        """Find where section ends."""
        # Next section starts where next header at same or higher level begins
        if section_index + 1 < len(headers):
            current_node = headers[section_index][0]
            current_level = current_node.level if isinstance(current_node, HeadingNode) else 1

            for i in range(section_index + 1, len(headers)):
                next_node = headers[i][0]
                next_level = next_node.level if isinstance(next_node, HeadingNode) else 1

                # If next header is at same or higher level, that's our end
                if next_level <= current_level:
                    return headers[i][2]

        # Otherwise, section goes to end of document
        return sum(1 for _ in document.root.walk())

    def _create_sections(self, 
                        matched_sections: Dict[str, Tuple[Node, str, int, int]], 
                        document: Document) -> Dict[str, Section]:
        """Create Section objects from matches."""
        sections = {}

        for section_name, (node, title, start_pos, end_pos) in matched_sections.items():
            # Create section node containing all content in range
            section_node = SectionNode(section_name=section_name)

            # Find all nodes in position range - only add top-level nodes
            # (nodes whose parent is outside the range)
            # First collect all nodes in range
            nodes_in_range = []
            position = 0
            for n in document.root.walk():
                if start_pos <= position < end_pos:
                    nodes_in_range.append(n)
                position += 1

            # Now add only top-level nodes (nodes whose parent is not in the range)
            # This prevents adding both a parent and its children as direct section children
            for n in nodes_in_range:
                if n.parent not in nodes_in_range:
                    section_node.add_child(n)

            # Clear text cache to ensure fresh text generation
            # (nodes may have stale cached text from earlier processing)
            if hasattr(section_node, 'clear_text_cache'):
                section_node.clear_text_cache()

            # Parse section name to extract part and item identifiers
            part, item = Section.parse_section_name(section_name)

            # Create Section object
            section = Section(
                name=section_name,
                title=title,
                node=section_node,
                start_offset=start_pos,
                end_offset=end_pos,
                confidence=0.7,  # Pattern-based detection = moderate confidence
                detection_method='pattern',  # Method: regex pattern matching
                part=part,
                item=item
            )

            sections[section_name] = section

        return sections
