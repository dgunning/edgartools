"""
Derivative instrument models for fund portfolio reporting.

This module contains all the data models for different types of derivative
instruments found in fund portfolios, including forwards, swaps, futures,
options, and swaptions.
"""
from decimal import Decimal
from typing import Optional, Union

from pydantic import BaseModel

from edgar.xmltools import child_text, optional_decimal


def optional_decimal_attr(element, attr_name):
    """Helper function to parse optional decimal attributes from XML elements"""
    if element is None:
        return None

    attr_value = element.attrs.get(attr_name)
    if not attr_value or attr_value == "N/A":
        return None

    try:
        return Decimal(attr_value)
    except (ValueError, TypeError):
        return None


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
        if tag and tag.name == "fwdDeriv":
            counterparties = tag.find("counterparties")
            counterparty_name = child_text(counterparties, "counterpartyName") if counterparties else None
            counterparty_lei = child_text(counterparties, "counterpartyLei") if counterparties else None

            # Check for derivAddlInfo (when nested in options)
            deriv_addl_name = None
            deriv_addl_lei = None
            deriv_addl_title = None
            deriv_addl_cusip = None
            deriv_addl_identifier = None
            deriv_addl_identifier_type = None
            deriv_addl_balance = None
            deriv_addl_units = None
            deriv_addl_currency = None
            deriv_addl_value_usd = None
            deriv_addl_pct_val = None
            deriv_addl_asset_cat = None
            deriv_addl_issuer_cat = None
            deriv_addl_inv_country = None

            deriv_addl_info = tag.find("derivAddlInfo")
            if deriv_addl_info:
                deriv_addl_name = child_text(deriv_addl_info, "name")
                deriv_addl_lei = child_text(deriv_addl_info, "lei")
                deriv_addl_title = child_text(deriv_addl_info, "title")
                deriv_addl_cusip = child_text(deriv_addl_info, "cusip")
                deriv_addl_balance = optional_decimal(deriv_addl_info, "balance")
                deriv_addl_units = child_text(deriv_addl_info, "units")
                deriv_addl_currency = child_text(deriv_addl_info, "curCd")
                deriv_addl_value_usd = optional_decimal(deriv_addl_info, "valUSD")
                deriv_addl_pct_val = optional_decimal(deriv_addl_info, "pctVal")
                deriv_addl_asset_cat = child_text(deriv_addl_info, "assetCat")
                deriv_addl_inv_country = child_text(deriv_addl_info, "invCountry")

                # Parse issuer conditional
                issuer_cond = deriv_addl_info.find("issuerConditional")
                if issuer_cond:
                    deriv_addl_issuer_cat = issuer_cond.attrs.get("issuerCat")

                # Parse identifiers
                identifiers = deriv_addl_info.find("identifiers")
                if identifiers:
                    other_tag = identifiers.find("other")
                    if other_tag:
                        deriv_addl_identifier = other_tag.attrs.get("value")
                        deriv_addl_identifier_type = other_tag.attrs.get("otherDesc")

            return cls(
                counterparty_name=counterparty_name,
                counterparty_lei=counterparty_lei,
                currency_sold=child_text(tag, "curSold"),
                amount_sold=optional_decimal(tag, "amtCurSold"),
                currency_purchased=child_text(tag, "curPur"),
                amount_purchased=optional_decimal(tag, "amtCurPur"),
                settlement_date=child_text(tag, "settlementDt"),
                unrealized_appreciation=optional_decimal(tag, "unrealizedAppr"),

                # Additional info from derivAddlInfo
                deriv_addl_name=deriv_addl_name,
                deriv_addl_lei=deriv_addl_lei,
                deriv_addl_title=deriv_addl_title,
                deriv_addl_cusip=deriv_addl_cusip,
                deriv_addl_identifier=deriv_addl_identifier,
                deriv_addl_identifier_type=deriv_addl_identifier_type,
                deriv_addl_balance=deriv_addl_balance,
                deriv_addl_units=deriv_addl_units,
                deriv_addl_currency=deriv_addl_currency,
                deriv_addl_value_usd=deriv_addl_value_usd,
                deriv_addl_pct_val=deriv_addl_pct_val,
                deriv_addl_asset_cat=deriv_addl_asset_cat,
                deriv_addl_issuer_cat=deriv_addl_issuer_cat,
                deriv_addl_inv_country=deriv_addl_inv_country
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
    def from_xml(cls, tag):
        if tag and tag.name == "swapDeriv":
            # Basic counterparty and reference info
            counterparties = tag.find("counterparties")
            counterparty_name = child_text(counterparties, "counterpartyName") if counterparties else None
            counterparty_lei = child_text(counterparties, "counterpartyLei") if counterparties else None

            # Check for derivAddlInfo (when nested in swaptions)
            deriv_addl_name = None
            deriv_addl_lei = None
            deriv_addl_title = None
            deriv_addl_cusip = None
            deriv_addl_identifier = None
            deriv_addl_identifier_type = None
            deriv_addl_balance = None
            deriv_addl_units = None
            deriv_addl_desc_units = None
            deriv_addl_currency = None
            deriv_addl_value_usd = None
            deriv_addl_pct_val = None
            deriv_addl_asset_cat = None
            deriv_addl_issuer_cat = None
            deriv_addl_inv_country = None

            deriv_addl_info = tag.find("derivAddlInfo")
            if deriv_addl_info:
                deriv_addl_name = child_text(deriv_addl_info, "name")
                deriv_addl_lei = child_text(deriv_addl_info, "lei")
                deriv_addl_title = child_text(deriv_addl_info, "title")
                deriv_addl_cusip = child_text(deriv_addl_info, "cusip")
                deriv_addl_balance = optional_decimal(deriv_addl_info, "balance")
                deriv_addl_units = child_text(deriv_addl_info, "units")
                deriv_addl_desc_units = child_text(deriv_addl_info, "descOthUnits")
                deriv_addl_currency = child_text(deriv_addl_info, "curCd")
                deriv_addl_value_usd = optional_decimal(deriv_addl_info, "valUSD")
                deriv_addl_pct_val = optional_decimal(deriv_addl_info, "pctVal")
                deriv_addl_asset_cat = child_text(deriv_addl_info, "assetCat")
                deriv_addl_inv_country = child_text(deriv_addl_info, "invCountry")

                # Parse issuer conditional
                issuer_cond = deriv_addl_info.find("issuerConditional")
                if issuer_cond:
                    deriv_addl_issuer_cat = issuer_cond.attrs.get("issuerCat")

                # Parse identifiers
                identifiers = deriv_addl_info.find("identifiers")
                if identifiers:
                    other_tag = identifiers.find("other")
                    if other_tag:
                        deriv_addl_identifier = other_tag.attrs.get("value")
                        deriv_addl_identifier_type = other_tag.attrs.get("otherDesc")

            # Get reference instrument info (for CDS)
            ref_entity_name = None
            ref_entity_title = None
            ref_entity_cusip = None
            ref_entity_isin = None
            ref_entity_ticker = None
            desc_ref = tag.find("descRefInstrmnt")
            if desc_ref:
                other_ref = desc_ref.find("otherRefInst")
                if other_ref:
                    ref_entity_name = child_text(other_ref, "issuerName")
                    ref_entity_title = child_text(other_ref, "issueTitle")
                    identifiers = other_ref.find("identifiers")
                    if identifiers:
                        cusip_tag = identifiers.find("cusip")
                        if cusip_tag:
                            ref_entity_cusip = cusip_tag.attrs.get("value")
                        isin_tag = identifiers.find("isin")
                        if isin_tag:
                            ref_entity_isin = isin_tag.attrs.get("value")
                        ticker_tag = identifiers.find("ticker")
                        if ticker_tag:
                            ref_entity_ticker = ticker_tag.attrs.get("value")

            # DIRECTIONAL RECEIVE LEG PARSING
            fixed_rec_desc = tag.find("fixedRecDesc")
            floating_rec_desc = tag.find("floatingRecDesc")
            other_rec_desc = tag.find("otherRecDesc")

            # Fixed receive leg
            fixed_rate_receive = None
            fixed_amount_receive = None
            fixed_currency_receive = None
            if fixed_rec_desc:
                fixed_rate_receive = optional_decimal_attr(fixed_rec_desc, "fixedRt")
                fixed_amount_receive = optional_decimal_attr(fixed_rec_desc, "amount")
                fixed_currency_receive = fixed_rec_desc.attrs.get("curCd")

            # Floating receive leg
            floating_index_receive = None
            floating_spread_receive = None
            floating_amount_receive = None
            floating_currency_receive = None
            floating_tenor_receive = None
            floating_tenor_unit_receive = None
            floating_reset_date_tenor_receive = None
            floating_reset_date_unit_receive = None
            if floating_rec_desc:
                floating_index_receive = floating_rec_desc.attrs.get("floatingRtIndex")
                floating_spread_receive = optional_decimal_attr(floating_rec_desc, "floatingRtSpread")
                floating_amount_receive = optional_decimal_attr(floating_rec_desc, "pmntAmt")
                floating_currency_receive = floating_rec_desc.attrs.get("curCd")

                # Rate reset tenors for receive leg
                rate_reset_tenors = floating_rec_desc.find("rtResetTenors")
                if rate_reset_tenors:
                    rate_reset_tenor = rate_reset_tenors.find("rtResetTenor")
                    if rate_reset_tenor:
                        floating_tenor_receive = rate_reset_tenor.attrs.get("rateTenor")
                        floating_tenor_unit_receive = rate_reset_tenor.attrs.get("rateTenorUnit")
                        floating_reset_date_tenor_receive = rate_reset_tenor.attrs.get("resetDt")
                        floating_reset_date_unit_receive = rate_reset_tenor.attrs.get("resetDtUnit")

            # Other receive leg
            other_description_receive = None
            other_type_receive = None
            if other_rec_desc:
                other_type_receive = other_rec_desc.attrs.get("fixedOrFloating")
                if other_type_receive == "Other":
                    other_description_receive = other_rec_desc.text
                else:
                    other_description_receive = other_type_receive

            # DIRECTIONAL PAYMENT LEG PARSING
            fixed_pmnt_desc = tag.find("fixedPmntDesc")
            floating_pmnt_desc = tag.find("floatingPmntDesc")
            other_pmnt_desc = tag.find("otherPmntDesc")

            # Fixed payment leg
            fixed_rate_pay = None
            fixed_amount_pay = None
            fixed_currency_pay = None
            if fixed_pmnt_desc:
                fixed_rate_pay = optional_decimal_attr(fixed_pmnt_desc, "fixedRt")
                fixed_amount_pay = optional_decimal_attr(fixed_pmnt_desc, "amount")
                fixed_currency_pay = fixed_pmnt_desc.attrs.get("curCd")

            # Floating payment leg
            floating_index_pay = None
            floating_spread_pay = None
            floating_amount_pay = None
            floating_currency_pay = None
            floating_tenor_pay = None
            floating_tenor_unit_pay = None
            floating_reset_date_tenor_pay = None
            floating_reset_date_unit_pay = None
            if floating_pmnt_desc:
                floating_index_pay = floating_pmnt_desc.attrs.get("floatingRtIndex")
                floating_spread_pay = optional_decimal_attr(floating_pmnt_desc, "floatingRtSpread")
                floating_amount_pay = optional_decimal_attr(floating_pmnt_desc, "pmntAmt")
                floating_currency_pay = floating_pmnt_desc.attrs.get("curCd")

                # Rate reset tenors for payment leg
                rate_reset_tenors = floating_pmnt_desc.find("rtResetTenors")
                if rate_reset_tenors:
                    rate_reset_tenor = rate_reset_tenors.find("rtResetTenor")
                    if rate_reset_tenor:
                        floating_tenor_pay = rate_reset_tenor.attrs.get("rateTenor")
                        floating_tenor_unit_pay = rate_reset_tenor.attrs.get("rateTenorUnit")
                        floating_reset_date_tenor_pay = rate_reset_tenor.attrs.get("resetDt")
                        floating_reset_date_unit_pay = rate_reset_tenor.attrs.get("resetDtUnit")

            # Other payment leg
            other_description_pay = None
            other_type_pay = None
            if other_pmnt_desc:
                other_type_pay = other_pmnt_desc.attrs.get("fixedOrFloating")
                if other_type_pay == "Other":
                    other_description_pay = other_pmnt_desc.text
                else:
                    other_description_pay = other_type_pay

            return cls(
                # Basic info
                counterparty_name=counterparty_name,
                counterparty_lei=counterparty_lei,
                notional_amount=optional_decimal(tag, "notionalAmt"),
                currency=child_text(tag, "curCd"),
                unrealized_appreciation=optional_decimal(tag, "unrealizedAppr"),
                termination_date=child_text(tag, "terminationDt"),
                # Upfront payment/receipt info
                upfront_payment=optional_decimal(tag, "upfrontPmnt"),
                payment_currency=child_text(tag, "pmntCurCd"),
                upfront_receipt=optional_decimal(tag, "upfrontRcpt"),
                receipt_currency=child_text(tag, "rcptCurCd"),
                reference_entity_name=ref_entity_name,
                reference_entity_title=ref_entity_title,
                reference_entity_cusip=ref_entity_cusip,
                reference_entity_isin=ref_entity_isin,
                reference_entity_ticker=ref_entity_ticker,
                swap_flag=child_text(tag, "swapFlag"),

                # Additional info from derivAddlInfo
                deriv_addl_name=deriv_addl_name,
                deriv_addl_lei=deriv_addl_lei,
                deriv_addl_title=deriv_addl_title,
                deriv_addl_cusip=deriv_addl_cusip,
                deriv_addl_identifier=deriv_addl_identifier,
                deriv_addl_identifier_type=deriv_addl_identifier_type,
                deriv_addl_balance=deriv_addl_balance,
                deriv_addl_units=deriv_addl_units,
                deriv_addl_desc_units=deriv_addl_desc_units,
                deriv_addl_currency=deriv_addl_currency,
                deriv_addl_value_usd=deriv_addl_value_usd,
                deriv_addl_pct_val=deriv_addl_pct_val,
                deriv_addl_asset_cat=deriv_addl_asset_cat,
                deriv_addl_issuer_cat=deriv_addl_issuer_cat,
                deriv_addl_inv_country=deriv_addl_inv_country,

                # RECEIVE LEG
                fixed_rate_receive=fixed_rate_receive,
                fixed_amount_receive=fixed_amount_receive,
                fixed_currency_receive=fixed_currency_receive,
                floating_index_receive=floating_index_receive,
                floating_spread_receive=floating_spread_receive,
                floating_amount_receive=floating_amount_receive,
                floating_currency_receive=floating_currency_receive,
                floating_tenor_receive=floating_tenor_receive,
                floating_tenor_unit_receive=floating_tenor_unit_receive,
                floating_reset_date_tenor_receive=floating_reset_date_tenor_receive,
                floating_reset_date_unit_receive=floating_reset_date_unit_receive,
                other_description_receive=other_description_receive,
                other_type_receive=other_type_receive,

                # PAYMENT LEG
                fixed_rate_pay=fixed_rate_pay,
                fixed_amount_pay=fixed_amount_pay,
                fixed_currency_pay=fixed_currency_pay,
                floating_index_pay=floating_index_pay,
                floating_spread_pay=floating_spread_pay,
                floating_amount_pay=floating_amount_pay,
                floating_currency_pay=floating_currency_pay,
                floating_tenor_pay=floating_tenor_pay,
                floating_tenor_unit_pay=floating_tenor_unit_pay,
                floating_reset_date_tenor_pay=floating_reset_date_tenor_pay,
                floating_reset_date_unit_pay=floating_reset_date_unit_pay,
                other_description_pay=other_description_pay,
                other_type_pay=other_type_pay
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
        if tag and tag.name == "futrDeriv":
            counterparties = tag.find("counterparties")
            counterparty_name = child_text(counterparties, "counterpartyName") if counterparties else None
            counterparty_lei = child_text(counterparties, "counterpartyLei") if counterparties else None

            # Get reference instrument info
            ref_entity_name = None
            ref_entity_title = None
            ref_entity_cusip = None
            ref_entity_isin = None
            ref_entity_ticker = None
            ref_entity_other_id = None
            ref_entity_other_id_type = None

            desc_ref = tag.find("descRefInstrmnt")
            if desc_ref:
                other_ref = desc_ref.find("otherRefInst")
                if other_ref:
                    ref_entity_name = child_text(other_ref, "issuerName")
                    ref_entity_title = child_text(other_ref, "issueTitle")

                    # Parse identifiers
                    identifiers = other_ref.find("identifiers")
                    if identifiers:
                        cusip_tag = identifiers.find("cusip")
                        if cusip_tag:
                            ref_entity_cusip = cusip_tag.attrs.get("value")

                        isin_tag = identifiers.find("isin")
                        if isin_tag:
                            ref_entity_isin = isin_tag.attrs.get("value")

                        ticker_tag = identifiers.find("ticker")
                        if ticker_tag:
                            ref_entity_ticker = ticker_tag.attrs.get("value")

                        other_tag = identifiers.find("other")
                        if other_tag:
                            ref_entity_other_id = other_tag.attrs.get("value")
                            ref_entity_other_id_type = other_tag.attrs.get("otherDesc")

            return cls(
                counterparty_name=counterparty_name,
                counterparty_lei=counterparty_lei,
                payoff_profile=child_text(tag, "payOffProf"),
                expiration_date=child_text(tag, "expDate"),
                notional_amount=optional_decimal(tag, "notionalAmt"),
                currency=child_text(tag, "curCd"),
                unrealized_appreciation=optional_decimal(tag, "unrealizedAppr"),
                reference_entity_name=ref_entity_name,
                reference_entity_title=ref_entity_title,
                reference_entity_cusip=ref_entity_cusip,
                reference_entity_isin=ref_entity_isin,
                reference_entity_ticker=ref_entity_ticker,
                reference_entity_other_id=ref_entity_other_id,
                reference_entity_other_id_type=ref_entity_other_id_type
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
        if tag and tag.name == "optionSwaptionWarrantDeriv":
            counterparties = tag.find("counterparties")
            counterparty_name = child_text(counterparties, "counterpartyName") if counterparties else None
            counterparty_lei = child_text(counterparties, "counterpartyLei") if counterparties else None

            # Parse nested swap from descRefInstrmnt > nestedDerivInfo
            nested_swap = None
            desc_ref = tag.find("descRefInstrmnt")
            if desc_ref:
                nested_deriv_info = desc_ref.find("nestedDerivInfo")
                if nested_deriv_info:
                    swap_tag = nested_deriv_info.find("swapDeriv")
                    if swap_tag:
                        nested_swap = SwapDerivative.from_xml(swap_tag)

            return cls(
                counterparty_name=counterparty_name,
                counterparty_lei=counterparty_lei,
                put_or_call=child_text(tag, "putOrCall"),
                written_or_purchased=child_text(tag, "writtenOrPur"),
                share_number=optional_decimal(tag, "shareNo"),
                exercise_price=optional_decimal(tag, "exercisePrice"),
                exercise_price_currency=child_text(tag, "exercisePriceCurCd"),
                expiration_date=child_text(tag, "expDt"),
                delta=child_text(tag, "delta"),
                unrealized_appreciation=optional_decimal(tag, "unrealizedAppr"),
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
        if tag and tag.name == "optionSwaptionWarrantDeriv":
            counterparties = tag.find("counterparties")
            counterparty_name = child_text(counterparties, "counterpartyName") if counterparties else None
            counterparty_lei = child_text(counterparties, "counterpartyLei") if counterparties else None

            # Get reference instrument info
            ref_entity_name = None
            ref_entity_title = None
            ref_entity_cusip = None
            ref_entity_isin = None
            ref_entity_ticker = None
            ref_entity_other_id = None
            ref_entity_other_id_type = None
            index_name = None
            index_identifier = None
            nested_forward = None

            desc_ref = tag.find("descRefInstrmnt")
            if desc_ref:
                # Check for nested derivative info (e.g., option on forward, future, swap)
                nested_deriv_info = desc_ref.find("nestedDerivInfo")
                nested_future = None
                nested_swap_nested = None
                if nested_deriv_info:
                    # Parse any type of nested derivative
                    fwd_tag = nested_deriv_info.find("fwdDeriv")
                    if fwd_tag:
                        nested_forward = ForwardDerivative.from_xml(fwd_tag)

                    fut_tag = nested_deriv_info.find("futrDeriv")
                    if fut_tag:
                        nested_future = FutureDerivative.from_xml(fut_tag)

                    swap_tag = nested_deriv_info.find("swapDeriv")
                    if swap_tag:
                        nested_swap_nested = SwapDerivative.from_xml(swap_tag)
                else:
                    # Regular option - parse reference instrument
                    # Check for index reference first
                    index_basket = desc_ref.find("indexBasketInfo")
                    if index_basket:
                        index_name = child_text(index_basket, "indexName")
                        index_identifier = child_text(index_basket, "indexIdentifier")

                    # Then check for other reference instrument
                    other_ref = desc_ref.find("otherRefInst")
                    if other_ref:
                        ref_entity_name = child_text(other_ref, "issuerName")
                        ref_entity_title = child_text(other_ref, "issueTitle")
                        identifiers = other_ref.find("identifiers")
                        if identifiers:
                            cusip_tag = identifiers.find("cusip")
                            if cusip_tag:
                                ref_entity_cusip = cusip_tag.attrs.get("value")
                            isin_tag = identifiers.find("isin")
                            if isin_tag:
                                ref_entity_isin = isin_tag.attrs.get("value")
                            ticker_tag = identifiers.find("ticker")
                            if ticker_tag:
                                ref_entity_ticker = ticker_tag.attrs.get("value")

                            other_tag = identifiers.find("other")
                            if other_tag:
                                ref_entity_other_id = other_tag.attrs.get("value")
                                ref_entity_other_id_type = other_tag.attrs.get("otherDesc")

            return cls(
                counterparty_name=counterparty_name,
                counterparty_lei=counterparty_lei,
                put_or_call=child_text(tag, "putOrCall"),
                written_or_purchased=child_text(tag, "writtenOrPur"),
                share_number=optional_decimal(tag, "shareNo"),
                exercise_price=optional_decimal(tag, "exercisePrice"),
                exercise_price_currency=child_text(tag, "exercisePriceCurCd"),
                expiration_date=child_text(tag, "expDt"),
                delta=child_text(tag, "delta"),
                unrealized_appreciation=optional_decimal(tag, "unrealizedAppr"),
                reference_entity_name=ref_entity_name,
                reference_entity_title=ref_entity_title,
                reference_entity_cusip=ref_entity_cusip,
                reference_entity_isin=ref_entity_isin,
                reference_entity_ticker=ref_entity_ticker,
                reference_entity_other_id=ref_entity_other_id,
                reference_entity_other_id_type=ref_entity_other_id_type,
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
        if tag and tag.name == "derivativeInfo":
            # Use direct children only to avoid finding nested derivatives
            fwd_tag = tag.find("fwdDeriv", recursive=False)
            swap_tag = tag.find("swapDeriv", recursive=False)
            future_tag = tag.find("futrDeriv", recursive=False)
            option_tag = tag.find("optionSwaptionWarrantDeriv", recursive=False)

            deriv_cat = None
            option_deriv = None
            swaption_deriv = None

            if fwd_tag:
                deriv_cat = fwd_tag.attrs.get("derivCat")
            elif swap_tag:
                deriv_cat = swap_tag.attrs.get("derivCat")
            elif future_tag:
                deriv_cat = future_tag.attrs.get("derivCat")
            elif option_tag:
                deriv_cat = option_tag.attrs.get("derivCat")
                # Determine if it's a swaption (SWO) or regular option (OPT/WAR)
                if deriv_cat == "SWO":
                    swaption_deriv = SwaptionDerivative.from_xml(option_tag)
                else:
                    option_deriv = OptionDerivative.from_xml(option_tag)

            return cls(
                derivative_category=deriv_cat,
                forward_derivative=ForwardDerivative.from_xml(fwd_tag) if fwd_tag else None,
                swap_derivative=SwapDerivative.from_xml(swap_tag) if swap_tag else None,
                future_derivative=FutureDerivative.from_xml(future_tag) if future_tag else None,
                option_derivative=option_deriv,
                swaption_derivative=swaption_deriv
            )