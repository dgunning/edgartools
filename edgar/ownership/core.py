from decimal import Decimal
import re
from typing import Union, Any, Optional, Tuple
from pathlib import Path

import numpy as np
import pandas as pd
from lxml import etree

__all__ = ['is_numeric', 'compute_average_price', 'compute_total_value', 
           'format_currency', 'format_amount', 'safe_numeric', 'format_numeric',
           'form4_to_html']


def is_numeric(series: pd.Series) -> bool:
    if np.issubdtype(series.dtype, np.number):
        return True
    try:
        series.astype(float)
        return True
    except ValueError:
        return False

def compute_average_price(shares: pd.Series, price: pd.Series) -> Decimal:
    """
    Compute the average price of the trades
    :param shares: The number of shares as a series
    :param price: The price per share as a series
    :return:
    """
    if is_numeric(shares) and is_numeric(price):
        shares = pd.to_numeric(shares)
        price = pd.to_numeric(price)
        value = (shares * price).sum() / shares.sum()
        return Decimal(str(value)).quantize(Decimal('0.01'))


def compute_total_value(shares: pd.Series, price: pd.Series) -> Decimal:
    """
    Compute the total value of the trades
    :param shares: The number of shares as a series
    :param price: The price per share as a series
    :return:
    """
    if is_numeric(shares) and is_numeric(price):
        shares = pd.to_numeric(shares)
        price = pd.to_numeric(price)
        value = (shares * price).sum()
        return Decimal(str(value)).quantize(Decimal('0.01'))

def format_currency(amount: Union[int, float]) -> str:
    if amount is None or np.isnan(amount):
        return ""
    if isinstance(amount, (int, float)):
        return f"${amount:,.2f}"
    return str(amount)


def format_amount(amount: Union[int, float]) -> str:
    if amount is None:
        return ""
    if isinstance(amount, (int, float)):
        # Can it be formatted as an integer?
        if amount == int(amount):
            return f"{amount:,.0f}"
        return f"{amount:,.2f}"
    return str(amount)


def safe_numeric(value: Any) -> Optional[Union[int, float]]:
    """
    Safely convert a value to a number, handling footnote references and other special cases.

    Args:
        value: The value to convert (could be string, int, float, or None)

    Returns:
        Numeric value if conversion is possible, None otherwise
    """
    if value is None or pd.isna(value):
        return None

    # If already a number, return as is
    if isinstance(value, (int, float)) and not np.isnan(value):
        return value

    # Handle string cases
    if isinstance(value, str):
        # Remove commas, dollar signs, and whitespace
        cleaned = value.replace(',', '').replace('$', '').strip()

        # Remove footnote references like [F1], [1], etc.
        cleaned = re.sub(r'\[\w+]', '', cleaned)

        # Try numeric conversion
        try:
            # Check if it's an integer
            if '.' not in cleaned:
                return int(cleaned)
            else:
                return float(cleaned)
        except (ValueError, TypeError):
            return None

    return None


def format_numeric(value: Any, currency: bool = False, default: str = "N/A") -> str:
    """
    Format a potentially non-numeric value for display, handling special cases.

    Args:
        value: The value to format
        currency: Whether to format as currency with $ symbol
        default: Default string to return if value can't be converted to number

    Returns:
        Formatted string representation
    """
    number = safe_numeric(value)

    if number is None:
        # If the original value was a string with content, return it instead of default
        if isinstance(value, str) and value.strip():
            return value.strip()
        return default

    if currency:
        return f"${number:,.2f}"
    else:
        # Format integers without decimal places
        if isinstance(number, int) or (isinstance(number, float) and number.is_integer()):
            return f"{int(number):,}"
        return f"{number:,.2f}"

  # Add a dedicated currency formatter
def format_price(value: Any, default: str = "N/A") -> str:
    """Format a price value with currency symbol"""
    return format_numeric(value, currency=True, default=default)


def _get_xml_value(elem: etree._Element, xpath: str, with_footnote: bool = True) -> str:
    """Helper to safely get text from XML element with value tag and optional footnote
    
    Args:
        elem: XML element to search within
        xpath: XPath expression to find target element
        with_footnote: Whether to include footnote references in output
        
    Returns:
        Text value with optional footnote reference
    """
    # Handle both direct text elements and those with <value> wrapper
    nodes = elem.xpath(xpath)
    if not nodes:
        return ''
        
    node = nodes[0]
    
    # Try to get text from <value> child first
    value = node.find('value')
    if value is not None:
        text = value.text if value.text else ''
    else:
        # If no <value> tag, get direct text content
        text = node.text if node.text else ''
    
    # Add footnote reference if present and requested
    if with_footnote:
        footnote = node.find('footnoteId')
        if footnote is not None:
            footnote_id = footnote.get('id', '')
            if footnote_id:
                text = f"{text}<sup>({footnote_id})</sup>"
                
    return text.strip()


def _parse_name(name: str) -> Tuple[str, str, str]:
    """Parse a full name into (last, first, middle) components"""
    # Remove any extra whitespace
    name = ' '.join(name.split())
    parts = name.split(' ')
    
    if len(parts) == 1:
        return (parts[0], '', '')
    elif len(parts) == 2:
        return (parts[1], parts[0], '')
    else:
        return (parts[-1], parts[0], ' '.join(parts[1:-1]))

def _format_xml_date(date_str: str) -> str:
    """Format YYYY-MM-DD to MM/DD/YYYY"""
    if not date_str:
        return ''
    try:
        year, month, day = date_str.split('-')
        return f"{month}/{day}/{year}"
    except ValueError:
        return date_str


def form4_to_html(xml_path: Union[str, Path], output_path: Optional[Union[str, Path]] = None) -> str:
    """Convert Form 4 XML to HTML format matching official SEC layout.
    
    Args:
        xml_path: Path to Form 4 XML file
        output_path: Optional path to write HTML output. If not provided, returns HTML string
        
    Returns:
        HTML string if output_path is None, otherwise None
    """
    """Convert Form 4 XML to HTML format.
    
    Args:
        xml_path: Path to Form 4 XML file
        output_path: Optional path to write HTML output. If not provided, returns HTML string
        
    Returns:
        HTML string if output_path is None, otherwise None
    """
    # Parse XML with lxml
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(str(xml_path), parser)
    root = tree.getroot()
    
    # Extract key data
    issuer_name = _get_xml_value(root, './/issuerName')
    issuer_cik = _get_xml_value(root, './/issuerCik')
    issuer_ticker = _get_xml_value(root, './/issuerTradingSymbol')
    owner_name = _get_xml_value(root, './/rptOwnerName')
    owner_cik = _get_xml_value(root, './/rptOwnerCik')
    owner_street1 = _get_xml_value(root, './/rptOwnerStreet1')
    owner_street2 = _get_xml_value(root, './/rptOwnerStreet2')
    owner_city = _get_xml_value(root, './/rptOwnerCity')
    owner_state = _get_xml_value(root, './/rptOwnerState')
    owner_zip = _get_xml_value(root, './/rptOwnerZipCode')
    last_name, first_name, middle_name = _parse_name(owner_name)
    
    # Get owner relationship
    is_director = _get_xml_value(root, './/isDirector', with_footnote=False) == 'true'
    is_officer = _get_xml_value(root, './/isOfficer', with_footnote=False) == 'true'
    is_ten_pct = _get_xml_value(root, './/isTenPercentOwner', with_footnote=False) == 'true'
    is_other = _get_xml_value(root, './/isOther', with_footnote=False) == 'true'
    officer_title = _get_xml_value(root, './/officerTitle', with_footnote=False)
    relationships = []
    if is_director:
        relationships.append('Director')
    if is_officer:
        relationships.append(officer_title if officer_title else 'Officer')
    if is_ten_pct:
        relationships.append('10% Owner')
    if is_other:
        relationships.append('Other')
    
    # Check for Rule 10b5-1 trades
    rule_10b51 = root.findtext('aff10b5One') == 'true'
    
    # Build non-derivative transactions table
    non_deriv_rows = []
    for trans in root.xpath('.//nonDerivativeTransaction'):
        security_title = _get_xml_value(trans, './/securityTitle')
        date = _format_xml_date(_get_xml_value(trans, './/transactionDate'))
        shares = format_numeric(_get_xml_value(trans, './/transactionShares'))
        price = format_numeric(_get_xml_value(trans, './/transactionPricePerShare'), currency=True)
        acq_disp = _get_xml_value(trans, './/transactionAcquiredDisposedCode')
        owned_after = format_numeric(_get_xml_value(trans, './/sharesOwnedFollowingTransaction'))
        direct = _get_xml_value(trans, './/directOrIndirectOwnership')
        ownership = _get_xml_value(trans, './/natureOfOwnership')
        code_elem = trans.find('.//transactionCoding')
        if code_elem is not None:
            code = code_elem.findtext('transactionCode', '')
            equity_swap = code_elem.findtext('equitySwapInvolved') == 'true'
            code = f"{code} (swap)" if equity_swap else code
        else:
            code = ''
        acquired = _get_xml_value(trans, './/transactionAcquiredDisposedCode')
        nature = _get_xml_value(trans, './/natureOfOwnership', with_footnote=False)
        ownership = f"{ownership} - {nature}" if nature else ownership
        shares_owned = format_numeric(_get_xml_value(trans, './/sharesOwnedFollowingTransaction'))
        
        non_deriv_rows.append(f'''
        <tr>
            <td class="TableCell">{security_title}</td>
            <td class="TableCell">{date}</td>
            <td class="TableCell">{code}</td>
            <td class="TableCell">{shares} {acq_disp}</td>
            <td class="TableCell">{price}</td>
            <td class="TableCell">{owned_after}</td>
            <td class="TableCell">{direct} - {ownership}</td>
        </tr>''')
    
    # Build derivative transactions table
    deriv_rows = []
    for trans in root.xpath('.//derivativeTransaction'):
        security_title = _get_xml_value(trans, './/securityTitle')
        conv_price = format_numeric(_get_xml_value(trans, './/conversionOrExercisePrice'), currency=True)
        date = _format_xml_date(_get_xml_value(trans, './/transactionDate'))
        shares = format_numeric(_get_xml_value(trans, './/transactionShares'))
        price = format_numeric(_get_xml_value(trans, './/transactionPricePerShare'), currency=True)
        acq_disp = _get_xml_value(trans, './/transactionAcquiredDisposedCode')
        exercisable = _format_xml_date(_get_xml_value(trans, './/exerciseDate'))
        expiration = _format_xml_date(_get_xml_value(trans, './/expirationDate'))
        underlying = _get_xml_value(trans, './/underlyingSecurityTitle')
        underlying_shares = format_numeric(_get_xml_value(trans, './/underlyingSecurityShares'))
        owned_after = format_numeric(_get_xml_value(trans, './/sharesOwnedFollowingTransaction'))
        direct = _get_xml_value(trans, './/directOrIndirectOwnership')
        ownership = _get_xml_value(trans, './/natureOfOwnership')
        code_elem = trans.find('.//transactionCoding')
        if code_elem is not None:
            code = code_elem.findtext('transactionCode', '')
            equity_swap = code_elem.findtext('equitySwapInvolved') == 'true'
            code = f"{code} (swap)" if equity_swap else code
        else:
            code = ''
        acquired = _get_xml_value(trans, './/transactionAcquiredDisposedCode')
        nature = _get_xml_value(trans, './/natureOfOwnership', with_footnote=False)
        ownership = f"{ownership} - {nature}" if nature else ownership
        shares_owned = format_numeric(_get_xml_value(trans, './/sharesOwnedFollowingTransaction'))
        
        deriv_rows.append(f'''
        <tr>
            <td class="TableCell"><span class="FormData">{security}</span></td>
            <td class="TableCell"><span class="FormData">{format_price(exercise_price)}</span></td>
            <td class="TableCell"><span class="FormData">{date}</span></td>
            <td class="TableCell"><span class="FormData">{code}</span></td>
            <td class="TableCell"><span class="FormData">{shares} {acquired}</span></td>
            <td class="TableCell">
                <span class="FormData">Date Exercisable: {exercise_date}<br>Expiration Date: {expiration}</span>
            </td>
            <td class="TableCell">
                <span class="FormData">{underlying}<br>Amount: {underlying_shares}</span>
            </td>
            <td class="TableCell"><span class="FormData">{format_price(price)}</span></td>
            <td class="TableCell"><span class="FormData">{shares_owned}</span></td>
            <td class="TableCell"><span class="FormData">{ownership}</span></td>
            <td class="TableCell"><span class="FormData">{nature if ownership == 'I' else ''}</span></td>
        </tr>''')
    
    # Get remarks
    remarks = root.findtext('remarks', '')
    
    # Get footnotes
    footnotes = []
    for note in root.xpath('.//footnotes/footnote'):
        note_id = note.get('id', '')
        footnotes.append(f'<tr><td class="FootnoteData">({note_id}) {note.text}</td></tr>')
    
    # Get signature info
    sig_name = _get_xml_value(root, './/signatureName', with_footnote=False)
    sig_date = _get_xml_value(root, './/signatureDate', with_footnote=False)
    
    # Build complete HTML
    html = f'''<!DOCTYPE html>
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">
<title>SEC FORM 4</title>
<style type="text/css">
    body {{font-family: Arial, sans-serif; margin: 20px;}}
    .FormData {{font-size: 11px;}}
    .FormTitle {{font-size: 14px; font-weight: bold;}}
    .FootnoteData {{font-size: 10px; color: #444;}}
    .FormHeader {{font-size: 12px;}}
    .Remarks {{font-style: italic; color: #666;}}
    .SectionTitle {{font-size: 12px; font-weight: bold; margin-top: 15px;}}
    .TableHeader {{background-color: #f5f5f5; font-weight: bold;}}
    .TableCell {{padding: 4px; border: 1px solid #ccc;}}
    .BoxedSection {{border: 1px solid #000; padding: 10px; margin: 10px 0;}}
    .ColumnLabel {{font-size: 10px; color: #666; vertical-align: top;}}
</style>
</head>
<body>
<table width="100%" border="0" cellspacing="0" cellpadding="0">
    <tr>
        <td width="33%">SEC Form 4</td>
        <td width="34%" align="center">
            <div class="FormTitle">FORM 4</div>
            <div>UNITED STATES SECURITIES AND EXCHANGE COMMISSION<br>Washington, D.C. 20549</div>
            <div style="margin-top:10px">STATEMENT OF CHANGES IN BENEFICIAL OWNERSHIP</div>
            <div style="font-size:10px">Filed pursuant to Section 16(a) of the Securities Exchange Act of 1934<br>or Section 30(h) of the Investment Company Act of 1940</div>
        </td>
        <td width="33%" align="right">
            <div class="BoxedSection" style="text-align:left">
                <div>OMB Number: 3235-0287</div>
                <div>Expires: January 31, 2025</div>
                <div>SEC USE ONLY</div>
            </div>
        </td>
    </tr>
</table>

<div class="BoxedSection">
    <table width="100%" cellspacing="0" cellpadding="4">
        <tr>
            <td width="50%" valign="top">
                <div class="SectionTitle">1. Name and Address of Reporting Person*</div>
                <div class="FormData">{last_name} {first_name} {middle_name}</div>
                <div class="FormData" style="margin-top:10px"><i>({last_name}) ({first_name}) ({middle_name})</i></div>
            </td>
            <td width="50%" valign="top">
                <div class="SectionTitle">2. Issuer Name and Ticker or Trading Symbol</div>
                <div class="FormData">{issuer_name} [{issuer_ticker}]</div>
            </td>
        </tr>
    </table>
</div>

<div class="BoxedSection">
    <div class="SectionTitle">3. Statement for Month/Day/Year</div>
    <div class="FormData">{root.findtext('.//periodOfReport', '')}</div>
    
    <div class="SectionTitle">4. Relationship of Reporting Person(s) to Issuer</div>
    <table width="100%" cellspacing="0" cellpadding="4">
        <tr>
            {''.join(f'<td><input type="checkbox" {"checked" if rel in relationships else ""}> {rel}</td>' for rel in ['Director', '10% Owner', 'Officer (give title below)', 'Other (specify below)'])}
        </tr>
        <tr>
            <td colspan="4" class="FormData">{next((r.split(' - ')[1] for r in relationships if r.startswith('Officer - ')), '')}</td>
        </tr>
    </table>
</div>

<div class="SectionTitle">Table I - Non-Derivative Securities Acquired, Disposed of, or Beneficially Owned</div>
<table width="100%" cellspacing="0" cellpadding="4" style="border-collapse: collapse;">
    <thead>
        <tr class="TableHeader">
            <th class="TableCell" width="15%">1. Title of Security<br><span class="ColumnLabel">(Instr. 3)</span></th>
            <th class="TableCell" width="10%">2. Transaction Date<br><span class="ColumnLabel">(Month/Day/Year)</span></th>
            <th class="TableCell" width="10%">3. Transaction Code<br><span class="ColumnLabel">(Instr. 8)</span></th>
            <th class="TableCell" width="15%">4. Securities Acquired (A) or Disposed of (D)<br><span class="ColumnLabel">(Instr. 3, 4 and 5)</span></th>
            <th class="TableCell" width="10%">5. Price<br><span class="ColumnLabel">(Instr. 8)</span></th>
            <th class="TableCell" width="20%">6. Ownership Form<br><span class="ColumnLabel">(Instr. 4)</span></th>
            <th class="TableCell" width="20%">7. Nature of Indirect Beneficial Ownership<br><span class="ColumnLabel">(Instr. 4)</span></th>
        </tr>
    </thead>
    <tbody>{''.join(non_deriv_rows) if non_deriv_rows else '<tr><td colspan="7" align="center">No non-derivative transactions reported</td></tr>'}</tbody>
</table>

<div class="SectionTitle">Table II - Derivative Securities Acquired, Disposed of, or Beneficially Owned<br><span style="font-weight:normal">(e.g., puts, calls, warrants, options, convertible securities)</span></div>
<table width="100%" cellspacing="0" cellpadding="4" style="border-collapse: collapse;">
    <thead>
        <tr class="TableHeader">
            <th class="TableCell" width="12%">1. Title of Derivative Security<br><span class="ColumnLabel">(Instr. 3)</span></th>
            <th class="TableCell" width="8%">2. Conversion or Exercise Price</th>
            <th class="TableCell" width="8%">3. Transaction Date<br><span class="ColumnLabel">(Month/Day/Year)</span></th>
            <th class="TableCell" width="8%">4. Transaction Code<br><span class="ColumnLabel">(Instr. 8)</span></th>
            <th class="TableCell" width="12%">5. Number of Derivative Securities Acquired (A) or Disposed of (D)<br><span class="ColumnLabel">(Instr. 3, 4, and 5)</span></th>
            <th class="TableCell" width="8%">6. Date Exercisable and Expiration Date<br><span class="ColumnLabel">(Month/Day/Year)</span></th>
            <th class="TableCell" width="15%">7. Title and Amount of Securities Underlying Derivative Security<br><span class="ColumnLabel">(Instr. 3 and 4)</span></th>
            <th class="TableCell" width="8%">8. Price of Derivative Security<br><span class="ColumnLabel">(Instr. 5)</span></th>
            <th class="TableCell" width="8%">9. Number of Derivative Securities Beneficially Owned Following Reported Transaction(s)<br><span class="ColumnLabel">(Instr. 4)</span></th>
            <th class="TableCell" width="8%">10. Ownership Form of Derivative Security<br><span class="ColumnLabel">(Instr. 4)</span></th>
            <th class="TableCell" width="5%">11. Nature of Indirect Beneficial Ownership<br><span class="ColumnLabel">(Instr. 4)</span></th>
        </tr>
    </thead>
    <tbody>{''.join(deriv_rows) if deriv_rows else '<tr><td colspan="11" align="center">No derivative transactions reported</td></tr>'}</tbody>
</table>

{f'<h3>Remarks</h3><p class="Remarks">{remarks}</p>' if remarks else ''}

<h3>Footnotes</h3>
<table border="0">{''.join(footnotes)}</table>

<div class="BoxedSection">
    <div class="SectionTitle">Explanation of Responses:</div>
    <table border="0" cellspacing="0" cellpadding="4" width="100%">
        {''.join(footnotes)}
    </table>
</div>

<div class="BoxedSection">
    <div class="SectionTitle">Reminder: Report on a separate line for each class of securities beneficially owned directly or indirectly.</div>
    <div class="FormData" style="margin-top:10px">
        * If the form is filed by more than one reporting person, see Instruction 4(b)(v).<br>
        ** Intentional misstatements or omissions of facts constitute Federal Criminal Violations. See 18 U.S.C. 1001 and 15 U.S.C. 78ff(a).<br>
        Note: File three copies of this Form, one of which must be manually signed. If space is insufficient, see Instruction 6 for procedure.
    </div>
</div>

<div class="BoxedSection">
    <div class="SectionTitle">Signatures:</div>
    <div class="FormData">
        <p>{sig_name}<br>
        <span style="margin-left:20px">Signature of Reporting Person</span></p>
        <p>{sig_date}<br>
        <span style="margin-left:20px">Date</span></p>
    </div>
</div>
</body>
</html>'''

    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
    else:
        return html
