"""
Derivative instrument models for fund portfolio reporting.

This module contains all the data models for different types of derivative
instruments found in fund portfolios, including forwards, swaps, futures,
options, and swaptions.

XML parsing uses lxml for performance (10-20x faster than BeautifulSoup).
"""
from decimal import Decimal
from typing import Optional, Union

from pydantic import BaseModel


def _text(parent, tag):
    """Get text of a direct child element, or None. lxml equivalent of child_text()."""
    if parent is None:
        return None
    el = parent.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return None


def _opt_decimal(parent, tag):
    """Get optional Decimal from child element text. lxml equivalent of optional_decimal()."""
    text = _text(parent, tag)
    if text:
        try:
            return Decimal(text)
        except (ValueError, TypeError, ArithmeticError):
            return None
    return None


def _opt_decimal_attr(element, attr_name):
    """Get optional Decimal from an element attribute."""
    if element is None:
        return None
    attr_value = element.get(attr_name)
    if not attr_value or attr_value == "N/A":
        return None
    try:
        return Decimal(attr_value)
    except (ValueError, TypeError):
        return None


def _parse_deriv_addl_info(tag):
    """Parse derivAddlInfo block common to forwards and swaps. Returns dict of fields."""
    result = {
        'name': None, 'lei': None, 'title': None, 'cusip': None,
        'identifier': None, 'identifier_type': None, 'balance': None,
        'units': None, 'desc_units': None, 'currency': None,
        'value_usd': None, 'pct_val': None, 'asset_cat': None,
        'issuer_cat': None, 'inv_country': None,
    }
    deriv_addl_info = tag.find("derivAddlInfo")
    if deriv_addl_info is None:
        return result

    result['name'] = _text(deriv_addl_info, "name")
    result['lei'] = _text(deriv_addl_info, "lei")
    result['title'] = _text(deriv_addl_info, "title")
    result['cusip'] = _text(deriv_addl_info, "cusip")
    result['balance'] = _opt_decimal(deriv_addl_info, "balance")
    result['units'] = _text(deriv_addl_info, "units")
    result['desc_units'] = _text(deriv_addl_info, "descOthUnits")
    result['currency'] = _text(deriv_addl_info, "curCd")
    result['value_usd'] = _opt_decimal(deriv_addl_info, "valUSD")
    result['pct_val'] = _opt_decimal(deriv_addl_info, "pctVal")
    result['asset_cat'] = _text(deriv_addl_info, "assetCat")
    result['inv_country'] = _text(deriv_addl_info, "invCountry")

    issuer_cond = deriv_addl_info.find("issuerConditional")
    if issuer_cond is not None:
        result['issuer_cat'] = issuer_cond.get("issuerCat")

    identifiers = deriv_addl_info.find("identifiers")
    if identifiers is not None:
        other_tag = identifiers.find("other")
        if other_tag is not None:
            result['identifier'] = other_tag.get("value")
            result['identifier_type'] = other_tag.get("otherDesc")

    return result


def _parse_counterparties(tag):
    """Parse counterparties block. Returns (name, lei) tuple."""
    counterparties = tag.find("counterparties")
    if counterparties is None:
        return None, None
    return _text(counterparties, "counterpartyName"), _text(counterparties, "counterpartyLei")


def _parse_ref_instrument_identifiers(identifiers_el):
    """Parse identifiers block within a reference instrument. Returns dict."""
    result = {'cusip': None, 'isin': None, 'ticker': None, 'other_id': None, 'other_id_type': None}
    if identifiers_el is None:
        return result
    cusip_tag = identifiers_el.find("cusip")
    if cusip_tag is not None:
        result['cusip'] = cusip_tag.get("value")
    isin_tag = identifiers_el.find("isin")
    if isin_tag is not None:
        result['isin'] = isin_tag.get("value")
    ticker_tag = identifiers_el.find("ticker")
    if ticker_tag is not None:
        result['ticker'] = ticker_tag.get("value")
    other_tag = identifiers_el.find("other")
    if other_tag is not None:
        result['other_id'] = other_tag.get("value")
        result['other_id_type'] = other_tag.get("otherDesc")
    return result


class ForwardDerivative(BaseModel):
    counterparty_name: Optional[str]
    counterparty_lei: Optional[str]
    currency_sold: Optional[str]
    amount_sold: Optional[Decimal]
    currency_purchased: Optional[str]
    amount_purchased: Optional[Decimal]
    settlement_date: Optional[str]
    unrealized_appreciation: Optional[Decimal]

    # Additional info from derivAddlInfo (when nested)
    deriv_addl_name: Optional[str]
    deriv_addl_lei: Optional[str]
    deriv_addl_title: Optional[str]
    deriv_addl_cusip: Optional[str]
    deriv_addl_identifier: Optional[str]
    deriv_addl_identifier_type: Optional[str]
    deriv_addl_balance: Optional[Decimal]
    deriv_addl_units: Optional[str]
    deriv_addl_currency: Optional[str]
    deriv_addl_value_usd: Optional[Decimal]
    deriv_addl_pct_val: Optional[Decimal]
    deriv_addl_asset_cat: Optional[str]
    deriv_addl_issuer_cat: Optional[str]
    deriv_addl_inv_country: Optional[str]

    @classmethod
    def from_xml(cls, tag):
        if tag is None:
            return None
        cp_name, cp_lei = _parse_counterparties(tag)
        addl = _parse_deriv_addl_info(tag)

        return cls(
            counterparty_name=cp_name,
            counterparty_lei=cp_lei,
            currency_sold=_text(tag, "curSold"),
            amount_sold=_opt_decimal(tag, "amtCurSold"),
            currency_purchased=_text(tag, "curPur"),
            amount_purchased=_opt_decimal(tag, "amtCurPur"),
            settlement_date=_text(tag, "settlementDt"),
            unrealized_appreciation=_opt_decimal(tag, "unrealizedAppr"),
            deriv_addl_name=addl['name'],
            deriv_addl_lei=addl['lei'],
            deriv_addl_title=addl['title'],
            deriv_addl_cusip=addl['cusip'],
            deriv_addl_identifier=addl['identifier'],
            deriv_addl_identifier_type=addl['identifier_type'],
            deriv_addl_balance=addl['balance'],
            deriv_addl_units=addl['units'],
            deriv_addl_currency=addl['currency'],
            deriv_addl_value_usd=addl['value_usd'],
            deriv_addl_pct_val=addl['pct_val'],
            deriv_addl_asset_cat=addl['asset_cat'],
            deriv_addl_issuer_cat=addl['issuer_cat'],
            deriv_addl_inv_country=addl['inv_country']
        )


class SwapDerivative(BaseModel):
    # Basic derivative info
    counterparty_name: Optional[str]
    counterparty_lei: Optional[str]
    notional_amount: Optional[Decimal]
    currency: Optional[str]
    unrealized_appreciation: Optional[Decimal]
    termination_date: Optional[str]
    upfront_payment: Optional[Decimal]
    payment_currency: Optional[str]
    upfront_receipt: Optional[Decimal]
    receipt_currency: Optional[str]
    reference_entity_name: Optional[str]
    reference_entity_title: Optional[str]
    reference_entity_cusip: Optional[str]
    reference_entity_isin: Optional[str]
    reference_entity_ticker: Optional[str]
    swap_flag: Optional[str]

    # Additional info from derivAddlInfo (when nested)
    deriv_addl_name: Optional[str]
    deriv_addl_lei: Optional[str]
    deriv_addl_title: Optional[str]
    deriv_addl_cusip: Optional[str]
    deriv_addl_identifier: Optional[str]
    deriv_addl_identifier_type: Optional[str]
    deriv_addl_balance: Optional[Decimal]
    deriv_addl_units: Optional[str]
    deriv_addl_desc_units: Optional[str]
    deriv_addl_currency: Optional[str]
    deriv_addl_value_usd: Optional[Decimal]
    deriv_addl_pct_val: Optional[Decimal]
    deriv_addl_asset_cat: Optional[str]
    deriv_addl_issuer_cat: Optional[str]
    deriv_addl_inv_country: Optional[str]

    # DIRECTIONAL RECEIVE LEG (what we receive)
    fixed_rate_receive: Optional[Decimal]
    fixed_amount_receive: Optional[Decimal]
    fixed_currency_receive: Optional[str]
    floating_index_receive: Optional[str]
    floating_spread_receive: Optional[Decimal]
    floating_amount_receive: Optional[Decimal]
    floating_currency_receive: Optional[str]
    floating_tenor_receive: Optional[str]
    floating_tenor_unit_receive: Optional[str]
    floating_reset_date_tenor_receive: Optional[str]
    floating_reset_date_unit_receive: Optional[str]
    other_description_receive: Optional[str]
    other_type_receive: Optional[str]  # fixedOrFloating attribute

    # Additional upfront payment/receipt info
    upfront_payment: Optional[Decimal]
    payment_currency: Optional[str]
    upfront_receipt: Optional[Decimal]
    receipt_currency: Optional[str]

    # DIRECTIONAL PAYMENT LEG (what we pay)
    fixed_rate_pay: Optional[Decimal]
    fixed_amount_pay: Optional[Decimal]
    fixed_currency_pay: Optional[str]
    floating_index_pay: Optional[str]
    floating_spread_pay: Optional[Decimal]
    floating_amount_pay: Optional[Decimal]
    floating_currency_pay: Optional[str]
    floating_tenor_pay: Optional[str]
    floating_tenor_unit_pay: Optional[str]
    floating_reset_date_tenor_pay: Optional[str]
    floating_reset_date_unit_pay: Optional[str]
    other_description_pay: Optional[str]
    other_type_pay: Optional[str]  # fixedOrFloating attribute

    @classmethod
    def _parse_floating_leg(cls, floating_desc):
        """Parse a floating receive or payment leg element."""
        if floating_desc is None:
            return {}
        result = {
            'index': floating_desc.get("floatingRtIndex"),
            'spread': _opt_decimal_attr(floating_desc, "floatingRtSpread"),
            'amount': _opt_decimal_attr(floating_desc, "pmntAmt"),
            'currency': floating_desc.get("curCd"),
            'tenor': None, 'tenor_unit': None,
            'reset_date_tenor': None, 'reset_date_unit': None,
        }
        rate_reset_tenors = floating_desc.find("rtResetTenors")
        if rate_reset_tenors is not None:
            rate_reset_tenor = rate_reset_tenors.find("rtResetTenor")
            if rate_reset_tenor is not None:
                result['tenor'] = rate_reset_tenor.get("rateTenor")
                result['tenor_unit'] = rate_reset_tenor.get("rateTenorUnit")
                result['reset_date_tenor'] = rate_reset_tenor.get("resetDt")
                result['reset_date_unit'] = rate_reset_tenor.get("resetDtUnit")
        return result

    @classmethod
    def _parse_other_leg(cls, other_desc):
        """Parse an other receive or payment leg element."""
        if other_desc is None:
            return None, None
        other_type = other_desc.get("fixedOrFloating")
        if other_type == "Other":
            return other_desc.text, other_type
        return other_type, other_type

    @classmethod
    def from_xml(cls, tag):
        if tag is None:
            return None
        cp_name, cp_lei = _parse_counterparties(tag)
        addl = _parse_deriv_addl_info(tag)

        # Reference instrument info (for CDS)
        ref_name = ref_title = ref_cusip = ref_isin = ref_ticker = None
        desc_ref = tag.find("descRefInstrmnt")
        if desc_ref is not None:
            other_ref = desc_ref.find("otherRefInst")
            if other_ref is not None:
                ref_name = _text(other_ref, "issuerName")
                ref_title = _text(other_ref, "issueTitle")
                ids = _parse_ref_instrument_identifiers(other_ref.find("identifiers"))
                ref_cusip, ref_isin, ref_ticker = ids['cusip'], ids['isin'], ids['ticker']

        # Receive leg
        fixed_rec = tag.find("fixedRecDesc")
        float_rec = cls._parse_floating_leg(tag.find("floatingRecDesc"))
        other_rec_desc, other_rec_type = cls._parse_other_leg(tag.find("otherRecDesc"))

        # Payment leg
        fixed_pmnt = tag.find("fixedPmntDesc")
        float_pmnt = cls._parse_floating_leg(tag.find("floatingPmntDesc"))
        other_pmnt_desc, other_pmnt_type = cls._parse_other_leg(tag.find("otherPmntDesc"))

        return cls(
            counterparty_name=cp_name,
            counterparty_lei=cp_lei,
            notional_amount=_opt_decimal(tag, "notionalAmt"),
            currency=_text(tag, "curCd"),
            unrealized_appreciation=_opt_decimal(tag, "unrealizedAppr"),
            termination_date=_text(tag, "terminationDt"),
            upfront_payment=_opt_decimal(tag, "upfrontPmnt"),
            payment_currency=_text(tag, "pmntCurCd"),
            upfront_receipt=_opt_decimal(tag, "upfrontRcpt"),
            receipt_currency=_text(tag, "rcptCurCd"),
            reference_entity_name=ref_name,
            reference_entity_title=ref_title,
            reference_entity_cusip=ref_cusip,
            reference_entity_isin=ref_isin,
            reference_entity_ticker=ref_ticker,
            swap_flag=_text(tag, "swapFlag"),
            deriv_addl_name=addl['name'],
            deriv_addl_lei=addl['lei'],
            deriv_addl_title=addl['title'],
            deriv_addl_cusip=addl['cusip'],
            deriv_addl_identifier=addl['identifier'],
            deriv_addl_identifier_type=addl['identifier_type'],
            deriv_addl_balance=addl['balance'],
            deriv_addl_units=addl['units'],
            deriv_addl_desc_units=addl.get('desc_units'),
            deriv_addl_currency=addl['currency'],
            deriv_addl_value_usd=addl['value_usd'],
            deriv_addl_pct_val=addl['pct_val'],
            deriv_addl_asset_cat=addl['asset_cat'],
            deriv_addl_issuer_cat=addl['issuer_cat'],
            deriv_addl_inv_country=addl['inv_country'],
            # Receive leg
            fixed_rate_receive=_opt_decimal_attr(fixed_rec, "fixedRt") if fixed_rec is not None else None,
            fixed_amount_receive=_opt_decimal_attr(fixed_rec, "amount") if fixed_rec is not None else None,
            fixed_currency_receive=fixed_rec.get("curCd") if fixed_rec is not None else None,
            floating_index_receive=float_rec.get('index'),
            floating_spread_receive=float_rec.get('spread'),
            floating_amount_receive=float_rec.get('amount'),
            floating_currency_receive=float_rec.get('currency'),
            floating_tenor_receive=float_rec.get('tenor'),
            floating_tenor_unit_receive=float_rec.get('tenor_unit'),
            floating_reset_date_tenor_receive=float_rec.get('reset_date_tenor'),
            floating_reset_date_unit_receive=float_rec.get('reset_date_unit'),
            other_description_receive=other_rec_desc,
            other_type_receive=other_rec_type,
            # Payment leg
            fixed_rate_pay=_opt_decimal_attr(fixed_pmnt, "fixedRt") if fixed_pmnt is not None else None,
            fixed_amount_pay=_opt_decimal_attr(fixed_pmnt, "amount") if fixed_pmnt is not None else None,
            fixed_currency_pay=fixed_pmnt.get("curCd") if fixed_pmnt is not None else None,
            floating_index_pay=float_pmnt.get('index'),
            floating_spread_pay=float_pmnt.get('spread'),
            floating_amount_pay=float_pmnt.get('amount'),
            floating_currency_pay=float_pmnt.get('currency'),
            floating_tenor_pay=float_pmnt.get('tenor'),
            floating_tenor_unit_pay=float_pmnt.get('tenor_unit'),
            floating_reset_date_tenor_pay=float_pmnt.get('reset_date_tenor'),
            floating_reset_date_unit_pay=float_pmnt.get('reset_date_unit'),
            other_description_pay=other_pmnt_desc,
            other_type_pay=other_pmnt_type
        )


class FutureDerivative(BaseModel):
    counterparty_name: Optional[str]
    counterparty_lei: Optional[str]
    payoff_profile: Optional[str]
    expiration_date: Optional[str]
    notional_amount: Optional[Decimal]
    currency: Optional[str]
    unrealized_appreciation: Optional[Decimal]
    reference_entity_name: Optional[str]
    reference_entity_title: Optional[str]
    # Identifiers
    reference_entity_cusip: Optional[str]
    reference_entity_isin: Optional[str]
    reference_entity_ticker: Optional[str]
    reference_entity_other_id: Optional[str]
    reference_entity_other_id_type: Optional[str]

    @classmethod
    def from_xml(cls, tag):
        if tag is None:
            return None
        cp_name, cp_lei = _parse_counterparties(tag)

        ref_name = ref_title = None
        ids = {'cusip': None, 'isin': None, 'ticker': None, 'other_id': None, 'other_id_type': None}
        desc_ref = tag.find("descRefInstrmnt")
        if desc_ref is not None:
            other_ref = desc_ref.find("otherRefInst")
            if other_ref is not None:
                ref_name = _text(other_ref, "issuerName")
                ref_title = _text(other_ref, "issueTitle")
                ids = _parse_ref_instrument_identifiers(other_ref.find("identifiers"))

        return cls(
            counterparty_name=cp_name,
            counterparty_lei=cp_lei,
            payoff_profile=_text(tag, "payOffProf"),
            expiration_date=_text(tag, "expDate"),
            notional_amount=_opt_decimal(tag, "notionalAmt"),
            currency=_text(tag, "curCd"),
            unrealized_appreciation=_opt_decimal(tag, "unrealizedAppr"),
            reference_entity_name=ref_name,
            reference_entity_title=ref_title,
            reference_entity_cusip=ids['cusip'],
            reference_entity_isin=ids['isin'],
            reference_entity_ticker=ids['ticker'],
            reference_entity_other_id=ids['other_id'],
            reference_entity_other_id_type=ids['other_id_type']
        )


class SwaptionDerivative(BaseModel):
    """Swaption derivative (SWO) - option on a swap"""
    counterparty_name: Optional[str]
    counterparty_lei: Optional[str]
    put_or_call: Optional[str]
    written_or_purchased: Optional[str]
    share_number: Optional[Decimal]
    exercise_price: Optional[Decimal]
    exercise_price_currency: Optional[str]
    expiration_date: Optional[str]
    delta: Optional[Union[Decimal, str]]  # Can be numeric or 'XXXX'
    unrealized_appreciation: Optional[Decimal]
    # The underlying swap
    nested_swap: Optional['SwapDerivative']

    @classmethod
    def from_xml(cls, tag):
        if tag is None:
            return None
        cp_name, cp_lei = _parse_counterparties(tag)

        nested_swap = None
        desc_ref = tag.find("descRefInstrmnt")
        if desc_ref is not None:
            nested_deriv_info = desc_ref.find("nestedDerivInfo")
            if nested_deriv_info is not None:
                swap_tag = nested_deriv_info.find("swapDeriv")
                if swap_tag is not None:
                    nested_swap = SwapDerivative.from_xml(swap_tag)

        return cls(
            counterparty_name=cp_name,
            counterparty_lei=cp_lei,
            put_or_call=_text(tag, "putOrCall"),
            written_or_purchased=_text(tag, "writtenOrPur"),
            share_number=_opt_decimal(tag, "shareNo"),
            exercise_price=_opt_decimal(tag, "exercisePrice"),
            exercise_price_currency=_text(tag, "exercisePriceCurCd"),
            expiration_date=_text(tag, "expDt"),
            delta=_text(tag, "delta"),
            unrealized_appreciation=_opt_decimal(tag, "unrealizedAppr"),
            nested_swap=nested_swap
        )


class OptionDerivative(BaseModel):
    """Option derivative (OPT) - can have nested forward, future, or other derivatives"""
    counterparty_name: Optional[str]
    counterparty_lei: Optional[str]
    put_or_call: Optional[str]
    written_or_purchased: Optional[str]
    share_number: Optional[Decimal]
    exercise_price: Optional[Decimal]
    exercise_price_currency: Optional[str]
    expiration_date: Optional[str]
    delta: Optional[Union[Decimal, str]]  # Can be numeric or 'XXXX'
    unrealized_appreciation: Optional[Decimal]
    # Reference entity (for options on individual securities)
    reference_entity_name: Optional[str]
    reference_entity_title: Optional[str]
    reference_entity_cusip: Optional[str]
    reference_entity_isin: Optional[str]
    reference_entity_ticker: Optional[str]
    reference_entity_other_id: Optional[str]
    reference_entity_other_id_type: Optional[str]
    # Index reference (for options on indices like S&P 500)
    index_name: Optional[str]
    index_identifier: Optional[str]
    # For options with nested derivatives
    nested_forward: Optional['ForwardDerivative']
    nested_future: Optional['FutureDerivative']
    nested_swap: Optional['SwapDerivative']

    @classmethod
    def from_xml(cls, tag):
        if tag is None:
            return None
        cp_name, cp_lei = _parse_counterparties(tag)

        ref_name = ref_title = None
        ids = {'cusip': None, 'isin': None, 'ticker': None, 'other_id': None, 'other_id_type': None}
        index_name = index_identifier = None
        nested_forward = nested_future = nested_swap_nested = None

        desc_ref = tag.find("descRefInstrmnt")
        if desc_ref is not None:
            nested_deriv_info = desc_ref.find("nestedDerivInfo")
            if nested_deriv_info is not None:
                fwd_tag = nested_deriv_info.find("fwdDeriv")
                if fwd_tag is not None:
                    nested_forward = ForwardDerivative.from_xml(fwd_tag)
                fut_tag = nested_deriv_info.find("futrDeriv")
                if fut_tag is not None:
                    nested_future = FutureDerivative.from_xml(fut_tag)
                swap_tag = nested_deriv_info.find("swapDeriv")
                if swap_tag is not None:
                    nested_swap_nested = SwapDerivative.from_xml(swap_tag)
            else:
                index_basket = desc_ref.find("indexBasketInfo")
                if index_basket is not None:
                    index_name = _text(index_basket, "indexName")
                    index_identifier = _text(index_basket, "indexIdentifier")

                other_ref = desc_ref.find("otherRefInst")
                if other_ref is not None:
                    ref_name = _text(other_ref, "issuerName")
                    ref_title = _text(other_ref, "issueTitle")
                    ids = _parse_ref_instrument_identifiers(other_ref.find("identifiers"))

        return cls(
            counterparty_name=cp_name,
            counterparty_lei=cp_lei,
            put_or_call=_text(tag, "putOrCall"),
            written_or_purchased=_text(tag, "writtenOrPur"),
            share_number=_opt_decimal(tag, "shareNo"),
            exercise_price=_opt_decimal(tag, "exercisePrice"),
            exercise_price_currency=_text(tag, "exercisePriceCurCd"),
            expiration_date=_text(tag, "expDt"),
            delta=_text(tag, "delta"),
            unrealized_appreciation=_opt_decimal(tag, "unrealizedAppr"),
            reference_entity_name=ref_name,
            reference_entity_title=ref_title,
            reference_entity_cusip=ids['cusip'],
            reference_entity_isin=ids['isin'],
            reference_entity_ticker=ids['ticker'],
            reference_entity_other_id=ids['other_id'],
            reference_entity_other_id_type=ids['other_id_type'],
            index_name=index_name,
            index_identifier=index_identifier,
            nested_forward=nested_forward,
            nested_future=nested_future,
            nested_swap=nested_swap_nested
        )


class DerivativeInfo(BaseModel):
    derivative_category: Optional[str]  # FWD, SWP, FUT, OPT, SWO, WAR
    forward_derivative: Optional[ForwardDerivative]
    swap_derivative: Optional[SwapDerivative]
    future_derivative: Optional[FutureDerivative]
    option_derivative: Optional[OptionDerivative]
    swaption_derivative: Optional[SwaptionDerivative]

    @classmethod
    def from_xml(cls, tag):
        if tag is None:
            return None
        # lxml .find() already searches only direct children
        fwd_tag = tag.find("fwdDeriv")
        swap_tag = tag.find("swapDeriv")
        future_tag = tag.find("futrDeriv")
        option_tag = tag.find("optionSwaptionWarrantDeriv")

        deriv_cat = None
        option_deriv = None
        swaption_deriv = None

        if fwd_tag is not None:
            deriv_cat = fwd_tag.get("derivCat")
        elif swap_tag is not None:
            deriv_cat = swap_tag.get("derivCat")
        elif future_tag is not None:
            deriv_cat = future_tag.get("derivCat")
        elif option_tag is not None:
            deriv_cat = option_tag.get("derivCat")
            if deriv_cat == "SWO":
                swaption_deriv = SwaptionDerivative.from_xml(option_tag)
            else:
                option_deriv = OptionDerivative.from_xml(option_tag)

        return cls(
            derivative_category=deriv_cat,
            forward_derivative=ForwardDerivative.from_xml(fwd_tag) if fwd_tag is not None else None,
            swap_derivative=SwapDerivative.from_xml(swap_tag) if swap_tag is not None else None,
            future_derivative=FutureDerivative.from_xml(future_tag) if future_tag is not None else None,
            option_derivative=option_deriv,
            swaption_derivative=swaption_deriv
        )
