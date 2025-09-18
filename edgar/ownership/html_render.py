# html_render.py - HTML rendering module for ownership forms

import os
import re
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from edgar.ownership.core import Ownership

import pandas as pd
from jinja2 import Environment, FileSystemLoader

from edgar.ownership.core import format_numeric, format_price


def _format_date(date_str: str) -> str:
    if not date_str or pd.isna(date_str):
        return "N/A"
    try:
        return pd.to_datetime(date_str).strftime('%m/%d/%Y')
    except (ValueError, TypeError):
        return str(date_str) # Return original if parsing fails

def _escape_html(value: Any) -> str:
    """Escape HTML special characters in a string."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "N/A"
    s_val = str(value)
    # Only escape HTML special characters (Jinja2 will handle this automatically in templates)
    # but we still need it for our cell content preparation
    return s_val.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def format_owner_name(owner_name: Optional[str]) -> str:
    """Format owner name for display."""
    if not owner_name:
        return ""
    return _escape_html(owner_name)

def format_address(street1: Optional[str], street2: Optional[str], city: Optional[str], state: Optional[str], zip_code: Optional[str]) -> str:
    """Format address components into a HTML address string."""
    parts = []
    if street1:
        parts.append(_escape_html(street1))
    if street2:
        parts.append(_escape_html(street2))

    city_state_zip_line_parts = []
    if city:
        city_state_zip_line_parts.append(_escape_html(city))
    if state:
        city_state_zip_line_parts.append(_escape_html(state))
    if zip_code:
        city_state_zip_line_parts.append(_escape_html(zip_code))

    if city_state_zip_line_parts:
        parts.append(" ".join(city_state_zip_line_parts).strip())

    return "<br>".join(part for part in parts if part)


def ownership_to_html(ownership: 'Ownership') -> str:
    """Convert an Ownership object to HTML format matching official SEC layout.

    Args:
        ownership: Ownership object containing SEC form data

    Returns:
        HTML string representation
    """
    # Set up Jinja2 environment
    template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('ownership_form.html')

    # Extract basic information and prepare context
    form_type = ownership.form

    # Prepare context dictionary for template rendering
    context = {'form_type': form_type, 'html_title': f"SEC Form {form_type}", 'form_name_display': f"FORM {form_type}",
               'form_title_display': {
                   '3': "INITIAL STATEMENT OF BENEFICIAL OWNERSHIP OF SECURITIES",
                   '4': "STATEMENT OF CHANGES IN BENEFICIAL OWNERSHIP",
                   '5': "ANNUAL STATEMENT OF CHANGES IN BENEFICIAL OWNERSHIP"
               }.get(form_type, "STATEMENT OF OWNERSHIP"),
               'issuer_name': _escape_html(ownership.issuer.name if ownership.issuer else "N/A"),
               'ticker': _escape_html(ownership.issuer.ticker if ownership.issuer else "N/A"),
               'reporting_period': _format_date(ownership.reporting_period) if ownership.reporting_period else ''}

    # Issuer information

    # Reporting owner information
    reporting_owner = ownership.reporting_owners.owners[0] if ownership.reporting_owners.owners else None
    if reporting_owner:
        context['reporting_owner_name_str'] = format_owner_name(reporting_owner.name)
        context['reporting_owner_address_str'] = format_address(
            reporting_owner.address.street1 if reporting_owner.address else None,
            reporting_owner.address.street2 if reporting_owner.address else None,
            reporting_owner.address.city if reporting_owner.address else None,
            reporting_owner.address.state_or_country if reporting_owner.address else None,
            reporting_owner.address.zipcode if reporting_owner.address else None
        )

        # Reporting owner relationship
        context['is_director'] = 'X' if reporting_owner.is_director else ''
        context['is_officer'] = 'X' if reporting_owner.is_officer else ''
        context['is_ten_pct'] = 'X' if reporting_owner.is_ten_pct_owner else ''
        context['is_other'] = 'X' if reporting_owner.is_other else ''
        context['officer_title'] = _escape_html(reporting_owner.officer_title) if reporting_owner.officer_title else ''

    # Remarks
    context['remarks'] = _escape_html(ownership.remarks) if ownership.remarks else ''

    # Footnotes
    if ownership.footnotes and ownership.footnotes._footnotes:
        footnotes_list = []
        for footnote in ownership.footnotes._footnotes:
            footnotes_list.append(f"<p>{_escape_html(footnote)}</p>")
        context['footnotes_html'] = "\n".join(footnotes_list)
    else:
        context['footnotes_html'] = ''

    # Signature
    if ownership.signatures and ownership.signatures.signatures:
        first_signature = ownership.signatures.signatures[0]
        if first_signature.signature:
            context['sig_name'] = _escape_html(first_signature.signature)

        if first_signature.date:
            if isinstance(first_signature.date, str):
                context['sig_date'] = _escape_html(_format_date(first_signature.date))
            else:
                context['sig_date'] = _escape_html(str(first_signature.date))

    # Process Table I - Non-Derivative Securities
    non_deriv_rows = []
    non_derivative_table = getattr(ownership, 'non_derivative_table', None)
    if non_derivative_table:
        # Form 3 - Initial holdings
        if form_type == '3' and hasattr(non_derivative_table, 'holdings') and non_derivative_table.holdings is not None and not non_derivative_table.holdings.empty:
            for holding_tuple in non_derivative_table.holdings.data.itertuples(index=False):
                # Convert tuple to dictionary for easier access with default values
                holding = {col: getattr(holding_tuple, col, '') for col in holding_tuple._fields}

                # Extract values using dictionary get() with defaults
                security_title = str(holding.get('Security', ''))
                shares_owned = format_numeric(str(holding.get('Shares', '')))
                direct_indirect_code = str(holding.get('DirectIndirect', ''))
                nature_of_ownership = str(holding.get('NatureOfOwnership', ''))

                # Clean footnotes from values for table display
                security_title_clean = re.sub(r'<[Ss][Uu][Pp]>.*?</[Ss][Uu][Pp]>', '', security_title).strip()

                row = [
                    f'<td class="TableCell">{security_title_clean}</td>',
                    f'<td class="TableCell Right">{shares_owned}</td>',
                    f'<td class="TableCell Centered">{direct_indirect_code}</td>',
                    f'<td class="TableCell">{nature_of_ownership}</td>'
                ]
                non_deriv_rows.append(row)

        # Form 4/5 - Transactions
        elif form_type in ['4', '5'] and hasattr(non_derivative_table, 'transactions') and non_derivative_table.transactions is not None and not non_derivative_table.transactions.empty:
            for transaction_tuple in non_derivative_table.transactions.data.itertuples(index=False):
                # Convert tuple to dictionary for easier access with default values
                transaction = {col: getattr(transaction_tuple, col, '') for col in transaction_tuple._fields}

                # Extract values using dictionary get() with defaults
                security_title = str(transaction.get('Security', ''))
                transaction_date = _format_date(transaction.get('Date', ''))
                deemed_date = _format_date(transaction.get('DeemedDate', ''))
                transaction_code = str(transaction.get('Code', ''))
                transaction_v = str(transaction.get('V', ''))
                shares = format_numeric(str(transaction.get('Shares', '')))
                acquired_disposed = str(transaction.get('AcquiredDisposed', ''))
                price = format_price(transaction.get('Price', ''))
                owned_after_transaction = format_numeric(str(transaction.get('Remaining', '')))
                direct_indirect_code = str(transaction.get('DirectIndirect', ''))
                nature_of_ownership = str(transaction.get('NatureOfOwnership', ''))

                # Clean footnotes from values for table display
                security_title_clean = re.sub(r'<[Ss][Uu][Pp]>.*?</[Ss][Uu][Pp]>', '', security_title).strip()

                row = [
                    f'<td class="TableCell">{security_title_clean}</td>',
                    f'<td class="TableCell">{transaction_date}</td>',
                    f'<td class="TableCell">{deemed_date}</td>',
                    f'<td class="TableCell">{transaction_code}</td>',
                    f'<td class="TableCell">{transaction_v}</td>',
                    f'<td class="TableCell Right">{shares}</td>',
                    f'<td class="TableCell Centered">{acquired_disposed}</td>',
                    f'<td class="TableCell Right">{price}</td>',
                    f'<td class="TableCell Right">{owned_after_transaction}</td>',
                    f'<td class="TableCell Centered">{direct_indirect_code}</td>',
                    f'<td class="TableCell">{nature_of_ownership}</td>'
                ]
                non_deriv_rows.append(row)

            # Process Holdings for Forms 4/5
            if hasattr(non_derivative_table, 'holdings') and non_derivative_table.holdings is not None and not non_derivative_table.holdings.empty:
                for holding_tuple in non_derivative_table.holdings.data.itertuples(index=False):
                    # Convert tuple to dictionary for easier access with default values
                    holding = {col: getattr(holding_tuple, col, '') for col in holding_tuple._fields}

                    # Extract values using dictionary get() with defaults
                    security_title = str(holding.get('Security', ''))
                    shares_owned = format_numeric(str(holding.get('Shares', '')))
                    direct_indirect_code = str(holding.get('DirectIndirect', ''))
                    nature_of_ownership = str(holding.get('NatureOfOwnership', ''))

                    # Clean footnotes from values for table display
                    security_title_clean = re.sub(r'<[Ss][Uu][Pp]>.*?</[Ss][Uu][Pp]>', '', security_title).strip()

                    row = [
                        f'<td class="TableCell">{security_title_clean}</td>',
                        '<td class="TableCell"></td>',  # Transaction Date
                        '<td class="TableCell"></td>',  # Deemed Execution Date
                        '<td class="TableCell"></td>',  # Transaction Code
                        '<td class="TableCell"></td>',  # V
                        '<td class="TableCell"></td>',  # Amount
                        '<td class="TableCell"></td>',  # A/D
                        '<td class="TableCell"></td>',  # Price
                        f'<td class="TableCell Right">{shares_owned}</td>',
                        f'<td class="TableCell Centered">{direct_indirect_code}</td>',
                        f'<td class="TableCell">{nature_of_ownership}</td>'
                    ]
                    non_deriv_rows.append(row)

    # Add non_deriv_rows to context
    context['non_deriv_rows'] = non_deriv_rows

    # Process Table II - Derivative Securities
    deriv_rows = []
    derivative_table = getattr(ownership, 'derivative_table', None)
    if derivative_table:
        # Form 3 - Initial derivative holdings
        if form_type == '3' and hasattr(derivative_table, 'holdings') and derivative_table.holdings is not None and not derivative_table.holdings.empty:
            for holding_tuple in derivative_table.holdings.data.itertuples(index=False):
                # Convert tuple to dictionary for easier access with default values
                holding = {col: getattr(holding_tuple, col, '') for col in holding_tuple._fields}

                # Extract values using dictionary get() with defaults
                security_title = str(holding.get('Security', ''))
                conversion_price = format_price(holding.get('ExercisePrice', ''))
                exercisable_date = _format_date(holding.get('ExerciseDate', ''))
                expiration_date = _format_date(holding.get('ExpirationDate', ''))
                exercisable_expiration = f"{exercisable_date} - {expiration_date}"
                underlying_title = str(holding.get('Underlying', ''))
                underlying_shares = format_numeric(holding.get('UnderlyingShares', ''))
                title_amount_underlying = f"{underlying_title} - {underlying_shares}"
                direct_indirect_code = holding.get('DirectIndirect', '')
                nature_of_ownership = str(holding.get('Nature Of Ownership', ''))

                # Clean footnotes from values for table display
                security_title_clean = re.sub(r'<[Ss][Uu][Pp]>.*?</[Ss][Uu][Pp]>', '', security_title).strip()
                exercisable_expiration_clean = re.sub(r'<[Ss][Uu][Pp]>.*?</[Ss][Uu][Pp]>', '', exercisable_expiration).strip()
                title_amount_underlying_clean = re.sub(r'<[Ss][Uu][Pp]>.*?</[Ss][Uu][Pp]>', '', title_amount_underlying).strip()

                row = [
                    f'<td class="TableCell">{security_title_clean}</td>',
                    f'<td class="TableCell Right">{conversion_price}</td>',
                    '<td class="TableCell">N/A</td>',  # Transaction Date (blank for F3 initial holding)
                    '<td class="TableCell">N/A</td>',  # Deemed Execution Date (blank for F3 initial holding)
                    '<td class="TableCell">N/A</td>',  # Transaction Code (blank for F3 initial holding)
                    '<td class="TableCell">N/A</td>',  # V (blank for F3 initial holding)
                    '<td class="TableCell">N/A</td>',  # Shares in transaction (blank for F3 initial holding)
                    '<td class="TableCell">N/A</td>',  # A/D (blank for F3 initial holding)
                    f'<td class="TableCell">{exercisable_expiration_clean}</td>',
                    f'<td class="TableCell">{title_amount_underlying_clean}</td>',
                    '<td class="TableCell">N/A</td>',  # Price (blank for F3 initial holding)
                    '<td class="TableCell">N/A</td>',  # Amount owned after transaction (blank for F3 initial holding)
                    f'<td class="TableCell Centered">{direct_indirect_code}</td>',
                    f'<td class="TableCell">{nature_of_ownership}</td>'
                ]
                deriv_rows.append(row)

        # Form 4/5 - Derivative Transactions
        elif form_type in ['4', '5'] and hasattr(derivative_table, 'transactions') and derivative_table.transactions is not None and not derivative_table.transactions.empty:
            for transaction_tuple in derivative_table.transactions.data.itertuples(index=False):
                # Convert tuple to dictionary for easier access with default values
                transaction = {col: getattr(transaction_tuple, col, '') for col in transaction_tuple._fields}

                # Extract values using dictionary get() with defaults
                security_title = str(transaction.get('Security', ''))
                conversion_price = format_price(transaction.get('ExercisePrice', ''))
                transaction_date = _format_date(transaction.get('Date', ''))
                deemed_date = _format_date(transaction.get('DeemedDate', ''))
                transaction_code = str(transaction.get('Code', ''))
                transaction_v = str(transaction.get('V', ''))
                shares = format_numeric(str(transaction.get('Shares', '')))
                acquired_disposed = str(transaction.get('AcquiredDisposed', ''))
                exercisable_date = _format_date(transaction.get('ExerciseDate', ''))
                expiration_date = _format_date(transaction.get('ExpirationDate', ''))
                exercisable_expiration = f"{exercisable_date} - {expiration_date}"
                underlying_title = str(transaction.get('Underlying', ''))
                underlying_shares = format_numeric(transaction.get('UnderlyingShares', ''))
                title_amount_underlying = f"{underlying_title} - {underlying_shares}"
                price = format_price(transaction.get('Price', ''))
                owned_after_transaction = format_numeric(str(transaction.get('Remaining', '')))
                direct_indirect_code = str(transaction.get('DirectIndirect', ''))
                nature_of_ownership = str(transaction.get('NatureOfOwnership', ''))

                # Clean footnotes from values for table display
                security_title_clean = re.sub(r'<[Ss][Uu][Pp]>.*?</[Ss][Uu][Pp]>', '', security_title).strip()
                exercisable_expiration_clean = re.sub(r'<[Ss][Uu][Pp]>.*?</[Ss][Uu][Pp]>', '', exercisable_expiration).strip()
                title_amount_underlying_clean = re.sub(r'<[Ss][Uu][Pp]>.*?</[Ss][Uu][Pp]>', '', title_amount_underlying).strip()

                row = [
                    f'<td class="TableCell">{security_title_clean}</td>',
                    f'<td class="TableCell Right">{conversion_price}</td>',
                    f'<td class="TableCell">{transaction_date}</td>',
                    f'<td class="TableCell">{deemed_date}</td>',
                    f'<td class="TableCell">{transaction_code}</td>',
                    f'<td class="TableCell">{transaction_v}</td>',
                    f'<td class="TableCell Right">{shares}</td>',
                    f'<td class="TableCell Centered">{acquired_disposed}</td>',
                    f'<td class="TableCell">{exercisable_expiration_clean}</td>',
                    f'<td class="TableCell">{title_amount_underlying_clean}</td>',
                    f'<td class="TableCell Right">{price}</td>',
                    f'<td class="TableCell Right">{owned_after_transaction}</td>',
                    f'<td class="TableCell Centered">{direct_indirect_code}</td>',
                    f'<td class="TableCell">{nature_of_ownership}</td>'
                ]
                deriv_rows.append(row)

            # Process Holdings for Forms 4/5
            if hasattr(derivative_table, 'holdings') and derivative_table.holdings:
                for holding_tuple in derivative_table.holdings.data.itertuples(index=False):
                    # Convert tuple to dictionary for easier access with default values
                    holding = {col: getattr(holding_tuple, col, '') for col in holding_tuple._fields}

                    # Extract values using dictionary get() with defaults
                    security_title = str(holding.get('Security', ''))
                    conversion_price = format_price(holding.get('ExercisePrice', ''))
                    exercisable_date = _format_date(holding.get('ExerciseDate', ''))
                    expiration_date = _format_date(holding.get('ExpirationDate', ''))
                    exercisable_expiration = f"{exercisable_date} - {expiration_date}"
                    underlying_title = str(holding.get('Underlying', ''))
                    underlying_shares = format_numeric(holding.get('UnderlyingShares', ''))
                    title_amount_underlying = f"{underlying_title} - {underlying_shares}"
                    owned_after_transaction = format_numeric(holding.get('Remaining', ''))
                    direct_indirect_code = holding.get('DirectIndirect', '')
                    nature_of_ownership = str(holding.get('NatureOfOwnership', ''))

                    # Clean footnotes from values for table display
                    security_title_clean = re.sub(r'<[Ss][Uu][Pp]>.*?</[Ss][Uu][Pp]>', '', security_title).strip()
                    exercisable_expiration_clean = re.sub(r'<[Ss][Uu][Pp]>.*?</[Ss][Uu][Pp]>', '', exercisable_expiration).strip()
                    title_amount_underlying_clean = re.sub(r'<[Ss][Uu][Pp]>.*?</[Ss][Uu][Pp]>', '', title_amount_underlying).strip()

                    row = [
                        f'<td class="TableCell">{security_title_clean}</td>',
                        f'<td class="TableCell Right">{conversion_price}</td>',
                        '<td class="TableCell"></td>',  # Transaction Date
                        '<td class="TableCell"></td>',  # Deemed Execution Date
                        '<td class="TableCell"></td>',  # Transaction Code
                        '<td class="TableCell"></td>',  # V
                        '<td class="TableCell"></td>',  # Shares in transaction
                        '<td class="TableCell"></td>',  # A/D
                        f'<td class="TableCell">{exercisable_expiration_clean}</td>',
                        f'<td class="TableCell">{title_amount_underlying_clean}</td>',
                        '<td class="TableCell"></td>',  # Price
                        f'<td class="TableCell Right">{owned_after_transaction}</td>',
                        f'<td class="TableCell Centered">{direct_indirect_code}</td>',
                        f'<td class="TableCell">{nature_of_ownership}</td>'
                    ]
                    deriv_rows.append(row)
    # Add deriv_rows to context
    context['deriv_rows'] = deriv_rows

    # Render the template with the context
    return template.render(**context)

def _parse_name(name: str):
    """Parse a full name into (last, first, middle) components"""
    if not name:
        return '', '', ''

    # Check for comma format: "Last, First Middle"
    if ',' in name:
        last, rest = name.split(',', 1)
        parts = rest.strip().split()
        first = parts[0] if parts else ''
        middle = ' '.join(parts[1:]) if len(parts) > 1 else ''
    else:
        # Assume format "First Middle Last"
        parts = name.split()
        last = parts[-1] if parts else ''
        first = parts[0] if parts else ''
        middle = ' '.join(parts[1:-1]) if len(parts) > 1 else ''

    return last.strip(), first.strip(), middle.strip()
