"""
N-CEN Fund Census data object.

N-CEN is the Annual Report for Registered Investment Companies — a yearly
census of fund operational data covering series, service providers,
governance, ETF mechanics, broker commissions, and securities lending.
"""
from __future__ import annotations

import logging
from decimal import Decimal
from functools import lru_cache
from typing import Any, List, Optional, Union

import pandas as pd
from lxml import etree
from pydantic import BaseModel
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from edgar.display.formatting import moneyfmt
from edgar.funds.reports import _opt_decimal, _strip_namespaces, _text
from edgar.funds.nmfp3 import _opt_int, _flag
from edgar.richtools import df_to_rich_table, repr_rich

log = logging.getLogger(__name__)

__all__ = ['FundCensus', 'NCEN_FORMS']

NCEN_FORMS = ["N-CEN", "N-CEN/A"]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _opt_decimal_text(text: Optional[str]) -> Optional[Decimal]:
    """Parse a decimal from raw text."""
    if text:
        try:
            return Decimal(text)
        except (ValueError, TypeError, ArithmeticError):
            return None
    return None


def _clean_na(value: Optional[str]) -> Optional[str]:
    """Return None for 'N/A' sentinel values from the XML."""
    if not value or value.strip() == "N/A":
        return None
    return value.strip()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class Director(BaseModel):
    name: str
    crd_number: Optional[str] = None
    is_interested_person: bool = False

    def __str__(self):
        interested = " (interested)" if self.is_interested_person else ""
        return f"{self.name}{interested}"


class Accountant(BaseModel):
    name: str
    pcaob_number: Optional[str] = None
    lei: Optional[str] = None

    def __str__(self):
        return self.name


class ServiceProvider(BaseModel):
    name: str
    role: str
    lei: Optional[str] = None
    file_number: Optional[str] = None
    crd_number: Optional[str] = None
    is_affiliated: bool = False

    def __str__(self):
        return f"{self.name} ({self.role})"


class BrokerDealer(BaseModel):
    name: str
    file_number: Optional[str] = None
    crd_number: Optional[str] = None
    lei: Optional[str] = None
    commission: Optional[Decimal] = None

    def __str__(self):
        return self.name


class PrincipalTransaction(BaseModel):
    name: str
    file_number: Optional[str] = None
    crd_number: Optional[str] = None
    total_purchase_sale: Optional[Decimal] = None

    def __str__(self):
        return self.name


class SecuritiesLending(BaseModel):
    agent_name: Optional[str] = None
    agent_lei: Optional[str] = None
    is_affiliated: bool = False
    is_indemnified: bool = False

    def __str__(self):
        return self.agent_name or ""


class LineOfCredit(BaseModel):
    has_line_of_credit: bool = False
    is_committed: Optional[str] = None
    size: Optional[Decimal] = None
    institution_names: List[str] = []

    def __str__(self):
        if not self.has_line_of_credit:
            return "No"
        return f"Yes ({len(self.institution_names)} institutions)"


class LiquidityProvider(BaseModel):
    name: str
    lei: Optional[str] = None
    is_affiliated: bool = False
    asset_classes: List[str] = []

    def __str__(self):
        return self.name


class AuthorizedParticipant(BaseModel):
    name: str
    lei: Optional[str] = None
    file_number: Optional[str] = None
    crd_number: Optional[str] = None
    purchase_value: Optional[Decimal] = None
    redeem_value: Optional[Decimal] = None

    def __str__(self):
        return self.name


class ETFInfo(BaseModel):
    series_id: str
    fund_name: str
    exchange: Optional[str] = None
    ticker: Optional[str] = None
    creation_unit_size: Optional[Decimal] = None
    avg_pct_purchased_in_kind: Optional[Decimal] = None
    avg_pct_redeemed_in_kind: Optional[Decimal] = None
    std_dev_purchased_in_kind: Optional[Decimal] = None
    std_dev_redeemed_in_kind: Optional[Decimal] = None
    is_in_kind: bool = False
    authorized_participants: List[AuthorizedParticipant] = []

    def __str__(self):
        return f"{self.fund_name} ({self.ticker or self.series_id})"


class FundSeriesInfo(BaseModel):
    name: str
    series_id: str
    lei: Optional[str] = None
    fund_type: Optional[str] = None
    is_diversified: Optional[bool] = None
    avg_net_assets: Optional[Decimal] = None
    aggregate_commission: Optional[Decimal] = None
    is_securities_lending: bool = False
    advisers: List[ServiceProvider] = []
    custodians: List[ServiceProvider] = []
    transfer_agents: List[ServiceProvider] = []
    admins: List[ServiceProvider] = []
    pricing_services: List[ServiceProvider] = []
    shareholder_servicing_agents: List[ServiceProvider] = []
    broker_dealers: List[BrokerDealer] = []
    brokers: List[BrokerDealer] = []
    principal_transactions: List[PrincipalTransaction] = []
    securities_lending: List[SecuritiesLending] = []
    line_of_credit: Optional[LineOfCredit] = None
    liquidity_providers: List[LiquidityProvider] = []
    etf_info: Optional[ETFInfo] = None

    def __str__(self):
        return f"{self.name} ({self.series_id})"


class RegistrantInfo(BaseModel):
    name: str
    cik: str
    lei: Optional[str] = None
    file_number: Optional[str] = None
    street1: Optional[str] = None
    street2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    classification_type: Optional[str] = None
    total_series: Optional[int] = None
    directors: List[Director] = []
    cco_name: Optional[str] = None
    cco_crd: Optional[str] = None
    accountant: Optional[Accountant] = None
    underwriter_name: Optional[str] = None

    def __str__(self):
        return f"{self.name} (CIK: {self.cik})"


class SignatureInfo(BaseModel):
    registrant_name: Optional[str] = None
    signed_date: Optional[str] = None
    signer: Optional[str] = None
    title: Optional[str] = None

    def __str__(self):
        return f"{self.signer}, {self.title} ({self.signed_date})"


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class FundCensus:
    """
    Annual Report for Registered Investment Companies (N-CEN).

    N-CEN is a yearly census of fund operational data including series,
    service providers, governance, ETF mechanics, broker commissions,
    and securities lending information.

    Usage:
        >>> filing = Filing(form='N-CEN', ...)
        >>> census = filing.obj()
        >>> census.num_series
        3
        >>> census.series_data()
    """

    def __init__(self,
                 report_date: str,
                 is_period_lt_12_months: bool,
                 registrant: RegistrantInfo,
                 series: List[FundSeriesInfo],
                 signature_info: Optional[SignatureInfo] = None):
        self.report_date = report_date
        self.is_period_lt_12_months = is_period_lt_12_months
        self.registrant = registrant
        self.series = series
        self.signature_info = signature_info

    def __str__(self):
        return f"FundCensus({self.name}, {self.report_date}, {self.num_series} series)"

    @property
    def name(self) -> str:
        return self.registrant.name

    @property
    def cik(self) -> str:
        return self.registrant.cik

    @property
    def lei(self) -> Optional[str]:
        return self.registrant.lei

    @property
    def num_series(self) -> int:
        return len(self.series)

    @property
    def total_series(self) -> Optional[int]:
        return self.registrant.total_series

    @property
    def classification_type(self) -> Optional[str]:
        return self.registrant.classification_type

    @property
    def is_etf_company(self) -> bool:
        return any(s.etf_info is not None for s in self.series)

    # -------------------------------------------------------------------
    # DataFrame methods
    # -------------------------------------------------------------------

    @lru_cache(maxsize=1)
    def series_data(self) -> pd.DataFrame:
        """Summary of all fund series."""
        data = []
        for s in self.series:
            data.append({
                "name": s.name,
                "series_id": s.series_id,
                "lei": s.lei,
                "fund_type": s.fund_type,
                "avg_net_assets": s.avg_net_assets,
                "aggregate_commission": s.aggregate_commission,
                "num_advisers": len(s.advisers),
                "num_custodians": len(s.custodians),
                "has_etf": s.etf_info is not None,
            })
        return pd.DataFrame(data)

    @lru_cache(maxsize=1)
    def service_providers(self) -> pd.DataFrame:
        """All service providers flattened across series."""
        data = []
        for s in self.series:
            for provider in (s.advisers + s.custodians + s.transfer_agents +
                             s.admins + s.pricing_services + s.shareholder_servicing_agents):
                data.append({
                    "series_name": s.name,
                    "series_id": s.series_id,
                    "role": provider.role,
                    "provider_name": provider.name,
                    "lei": provider.lei,
                    "affiliated": provider.is_affiliated,
                })
        return pd.DataFrame(data)

    @lru_cache(maxsize=1)
    def broker_data(self) -> pd.DataFrame:
        """Broker-dealer and broker commission data across series."""
        data = []
        for s in self.series:
            for bd in s.broker_dealers:
                data.append({
                    "series_name": s.name,
                    "series_id": s.series_id,
                    "type": "broker-dealer",
                    "broker_name": bd.name,
                    "lei": bd.lei,
                    "commission": bd.commission,
                })
            for b in s.brokers:
                data.append({
                    "series_name": s.name,
                    "series_id": s.series_id,
                    "type": "broker",
                    "broker_name": b.name,
                    "lei": b.lei,
                    "commission": b.commission,
                })
        return pd.DataFrame(data)

    @lru_cache(maxsize=1)
    def director_data(self) -> pd.DataFrame:
        """Board of directors."""
        data = []
        for d in self.registrant.directors:
            data.append({
                "name": d.name,
                "crd_number": d.crd_number,
                "interested_person": d.is_interested_person,
            })
        return pd.DataFrame(data)

    @lru_cache(maxsize=1)
    def etf_data(self) -> pd.DataFrame:
        """ETF-specific data for series that are exchange-traded."""
        data = []
        for s in self.series:
            if s.etf_info is not None:
                etf = s.etf_info
                data.append({
                    "series_name": s.name,
                    "series_id": s.series_id,
                    "exchange": etf.exchange,
                    "ticker": etf.ticker,
                    "creation_unit_size": etf.creation_unit_size,
                    "avg_pct_purchased_in_kind": etf.avg_pct_purchased_in_kind,
                    "avg_pct_redeemed_in_kind": etf.avg_pct_redeemed_in_kind,
                    "is_in_kind": etf.is_in_kind,
                    "num_authorized_participants": len(etf.authorized_participants),
                })
        return pd.DataFrame(data)

    # -------------------------------------------------------------------
    # Rich display
    # -------------------------------------------------------------------

    @property
    def _summary_table(self) -> Table:
        table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
        table.add_column("Field", style="bold")
        table.add_column("Value")

        table.add_row("Registrant", self.registrant.name)
        table.add_row("CIK", self.registrant.cik)
        table.add_row("Report Date", self.report_date)
        table.add_row("Classification", self.registrant.classification_type or "N/A")
        table.add_row("Series in Filing", str(self.num_series))
        table.add_row("Total Series", str(self.registrant.total_series or "N/A"))
        table.add_row("Directors", str(len(self.registrant.directors)))

        if self.registrant.accountant:
            table.add_row("Accountant", self.registrant.accountant.name)

        return table

    @property
    def _series_table(self) -> Table:
        df = self.series_data()
        if df.empty:
            return Table(title="Fund Series")
        display = df.copy()
        display["avg_net_assets"] = display["avg_net_assets"].apply(
            lambda v: moneyfmt(v, curr="$", places=0) if pd.notna(v) else ""
        )
        display["has_etf"] = display["has_etf"].map({True: "Yes", False: "No"})
        display = display[["name", "series_id", "fund_type", "avg_net_assets", "has_etf"]].rename(columns={
            "name": "Fund Name",
            "series_id": "Series ID",
            "fund_type": "Type",
            "avg_net_assets": "Avg Net Assets",
            "has_etf": "ETF",
        })
        return df_to_rich_table(
            display,
            title="Fund Series",
            title_style="bold deep_sky_blue1",
            max_rows=30,
        )

    @property
    def _directors_table(self) -> Table:
        df = self.director_data()
        if df.empty:
            return Table(title="Directors")
        display = df.copy()
        display["crd_number"] = display["crd_number"].fillna("")
        display["interested_person"] = display["interested_person"].map({True: "Yes", False: "No"})
        display = display.rename(columns={
            "name": "Name",
            "crd_number": "CRD",
            "interested_person": "Interested",
        })
        return df_to_rich_table(
            display,
            title="Directors",
            title_style="bold deep_sky_blue1",
            max_rows=20,
        )

    def __rich__(self):
        title = f"{self.registrant.name}  {self.report_date}"
        return Panel(
            Group(
                self._summary_table,
                self._series_table,
                self._directors_table,
            ),
            title=title,
            subtitle=f"Fund Census (N-CEN)  {self.report_date}",
        )

    def __repr__(self):
        return repr_rich(self.__rich__())

    # -------------------------------------------------------------------
    # Parsing
    # -------------------------------------------------------------------

    @classmethod
    def from_filing(cls, filing) -> Optional['FundCensus']:
        """Create a FundCensus from a Filing object."""
        xml = filing.xml()
        if not xml:
            return None
        return cls._parse_xml(xml)

    @classmethod
    def _parse_xml(cls, xml: Union[str, Any]) -> 'FundCensus':
        """Parse N-CEN XML into a FundCensus object."""
        if isinstance(xml, str):
            xml_bytes = xml.encode('utf-8')
        else:
            xml_bytes = xml

        try:
            root = etree.fromstring(xml_bytes)
        except etree.XMLSyntaxError:
            parser = etree.XMLParser(recover=True)
            root = etree.fromstring(xml_bytes, parser=parser)

        _strip_namespaces(root)

        if root.tag != "edgarSubmission":
            found = root.find(".//edgarSubmission")
            if found is not None:
                root = found

        form_data = root.find("formData")

        # ----- General Info (attributes only) -----
        gen = form_data.find("generalInfo")
        report_date = gen.get("reportEndingPeriod", "") if gen is not None else ""
        is_lt_12 = gen.get("isReportPeriodLt12", "N") == "Y" if gen is not None else False

        # ----- Registrant Info -----
        registrant = _parse_registrant(form_data.find("registrantInfo"))

        # ----- Management Investment Question Series -----
        series_list = []
        mgmt_container = form_data.find("managementInvestmentQuestionSeriesInfo")
        if mgmt_container is not None:
            for q_el in mgmt_container.findall("managementInvestmentQuestion"):
                series_list.append(_parse_fund_series(q_el))

        # ----- Exchange Series (ETFs) — merge into matching management series -----
        exch_container = form_data.find("exchangeSeriesInfo")
        if exch_container is not None:
            etf_map = {}
            for etf_el in exch_container.findall("exchangeTradedFund"):
                etf_info = _parse_etf_info(etf_el)
                etf_map[etf_info.series_id] = etf_info

            for s in series_list:
                if s.series_id in etf_map:
                    s.etf_info = etf_map[s.series_id]

        # ----- Signature -----
        sig_el = form_data.find("signature")
        signature_info = None
        if sig_el is not None:
            signature_info = SignatureInfo(
                registrant_name=sig_el.get("registrantSignedName"),
                signed_date=sig_el.get("signedDate"),
                signer=sig_el.get("signature"),
                title=sig_el.get("title"),
            )

        return cls(
            report_date=report_date,
            is_period_lt_12_months=is_lt_12,
            registrant=registrant,
            series=series_list,
            signature_info=signature_info,
        )


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_registrant(reg_el) -> RegistrantInfo:
    """Parse registrantInfo element."""
    if reg_el is None:
        return RegistrantInfo(name="", cik="")

    # Directors
    directors = []
    directors_el = reg_el.find("directors")
    if directors_el is not None:
        for d_el in directors_el.findall("director"):
            directors.append(Director(
                name=_text(d_el, "directorName") or "",
                crd_number=_clean_na(_text(d_el, "crdNumber")),
                is_interested_person=_text(d_el, "isDirectorInterestedPerson") == "Y",
            ))

    # CCO
    cco_name = None
    cco_crd = None
    cco_container = reg_el.find("chiefComplianceOfficers")
    if cco_container is not None:
        cco_el = cco_container.find("chiefComplianceOfficer")
        if cco_el is not None:
            cco_name = _text(cco_el, "ccoName")
            cco_crd = _clean_na(_text(cco_el, "crdNumber"))

    # Accountant
    accountant = None
    acct_container = reg_el.find("publicAccountants")
    if acct_container is not None:
        acct_el = acct_container.find("publicAccountant")
        if acct_el is not None:
            accountant = Accountant(
                name=_text(acct_el, "publicAccountantName") or "",
                pcaob_number=_text(acct_el, "pcaobNumber"),
                lei=_text(acct_el, "publicAccountantLei"),
            )

    # Underwriter
    underwriter_name = None
    uw_container = reg_el.find("principalUnderwriters")
    if uw_container is not None:
        uw_el = uw_container.find("principalUnderwriter")
        if uw_el is not None:
            underwriter_name = _text(uw_el, "principalUnderwriterName")

    return RegistrantInfo(
        name=_text(reg_el, "registrantFullName") or "",
        cik=_text(reg_el, "registrantCik") or "",
        lei=_text(reg_el, "registrantLei"),
        file_number=_text(reg_el, "investmentCompFileNo"),
        street1=_text(reg_el, "registrantstreet1"),
        street2=_text(reg_el, "registrantstreet2"),
        city=_text(reg_el, "registrantcity"),
        state=_text(reg_el, "registrantstate"),
        country=_text(reg_el, "registrantcountry"),
        zip_code=_text(reg_el, "registrantzipCode"),
        phone=_text(reg_el, "registrantphoneNumber"),
        classification_type=_text(reg_el, "registrantClassificationType"),
        total_series=_opt_int(reg_el, "totalSeries"),
        directors=directors,
        cco_name=cco_name,
        cco_crd=cco_crd,
        accountant=accountant,
        underwriter_name=underwriter_name,
    )


def _parse_fund_series(q_el) -> FundSeriesInfo:
    """Parse a single managementInvestmentQuestion element."""
    # Non-diversified means the flag is "Y"
    non_div_text = _text(q_el, "isNonDiversifiedCompany")
    is_diversified = non_div_text == "N" if non_div_text else None

    # Service providers
    advisers = _parse_service_providers(q_el.find("investmentAdvisers"), "investmentAdviser", "adviser",
                                        name_tag="investmentAdviserName",
                                        lei_tag="investmentAdviserLei",
                                        file_tag="investmentAdviserFileNo",
                                        crd_tag="investmentAdviserCrdNo",
                                        aff_tag="isInvestmentAdviserHired")

    custodians = _parse_service_providers(q_el.find("custodians"), "custodian", "custodian",
                                          name_tag="custodianName",
                                          lei_tag="custodianLei",
                                          aff_tag="isCustodianAffiliated")

    transfer_agents = _parse_service_providers(q_el.find("transferAgents"), "transferAgent", "transfer agent",
                                               name_tag="transferAgentName",
                                               lei_tag="transferAgentLei",
                                               file_tag="transferAgentFileNo",
                                               aff_tag="isTransferAgentAffiliated")

    admins = _parse_service_providers(q_el.find("admins"), "admin", "administrator",
                                      name_tag="adminName",
                                      lei_tag="adminLei",
                                      aff_tag="isAdminAffiliated")

    pricing_services = _parse_service_providers(q_el.find("pricingServices"), "pricingService", "pricing service",
                                                name_tag="pricingServiceName",
                                                lei_tag="pricingServiceLei",
                                                aff_tag="isPricingServiceAffiliated")

    shareholder_agents = _parse_service_providers(
        q_el.find("shareholderServicingAgents"), "shareholderServicingAgent", "shareholder servicing",
        name_tag="shareholderServiceAgentName",
        lei_tag="shareholderServiceAgentLei",
        aff_tag="isShareholderServiceAgentAffiliated")

    # Broker-dealers
    broker_dealers = []
    bd_container = q_el.find("brokerDealers")
    if bd_container is not None:
        for bd_el in bd_container.findall("brokerDealer"):
            broker_dealers.append(BrokerDealer(
                name=_text(bd_el, "brokerDealerName") or "",
                file_number=_text(bd_el, "brokerDealerFileNo"),
                crd_number=_clean_na(_text(bd_el, "brokerDealerCrdNo")),
                lei=_text(bd_el, "brokerDealerLei"),
                commission=_opt_decimal(bd_el, "brokerDealerCommission"),
            ))

    # Brokers (separate from broker-dealers in N-CEN)
    brokers = []
    br_container = q_el.find("brokers")
    if br_container is not None:
        for br_el in br_container.findall("broker"):
            brokers.append(BrokerDealer(
                name=_text(br_el, "brokerName") or "",
                file_number=_text(br_el, "brokerFileNo"),
                crd_number=_clean_na(_text(br_el, "brokerCrdNo")),
                lei=_text(br_el, "brokerLei"),
                commission=_opt_decimal(br_el, "grossCommission"),
            ))

    # Principal transactions
    principal_transactions = []
    pt_container = q_el.find("principalTransactions")
    if pt_container is not None:
        for pt_el in pt_container.findall("principalTransaction"):
            principal_transactions.append(PrincipalTransaction(
                name=_text(pt_el, "principalName") or "",
                file_number=_text(pt_el, "principalFileNo"),
                crd_number=_clean_na(_text(pt_el, "principalCrdNo")),
                total_purchase_sale=_opt_decimal(pt_el, "principalTotalPurchaseSale"),
            ))

    # Securities lending
    securities_lending = []
    sl_container = q_el.find("securityLendings")
    if sl_container is not None:
        for sl_el in sl_container.findall("securityLending"):
            indemnity_el = sl_el.find("securityAgentIdemnity")
            is_indemnified = False
            if indemnity_el is not None:
                is_indemnified = indemnity_el.get("isSecurityAgentIdemnity") == "Y"
            securities_lending.append(SecuritiesLending(
                agent_name=_text(sl_el, "securitiesAgentName"),
                agent_lei=_text(sl_el, "securitiesAgentLei"),
                is_affiliated=_text(sl_el, "isSecuritiesAgentAffiliated") == "Y",
                is_indemnified=is_indemnified,
            ))

    # Line of credit
    line_of_credit = None
    loc_el = q_el.find("lineOfCredit")
    if loc_el is not None:
        has_loc = loc_el.get("hasLineOfCredit") == "Y"
        is_committed = None
        size = None
        institution_names = []

        details_container = loc_el.find("lineOfCreditDetails")
        if details_container is not None:
            detail = details_container.find("lineOfCreditDetail")
            if detail is not None:
                is_committed = _text(detail, "isCreditLineCommitted")
                size = _opt_decimal(detail, "lineOfCreditSize")
                inst_container = detail.find("lineOfCreditInstitutions")
                if inst_container is not None:
                    for inst in inst_container.findall("lineOfCreditInstitution"):
                        inst_name = inst.get("creditInstitutionName")
                        if inst_name:
                            institution_names.append(inst_name)

        line_of_credit = LineOfCredit(
            has_line_of_credit=has_loc,
            is_committed=is_committed,
            size=size,
            institution_names=institution_names,
        )

    # Liquidity classification services
    liquidity_providers = []
    liq_container = q_el.find("liquidityClassifications")
    if liq_container is not None:
        for liq_el in liq_container.findall("liquidityClassificationService"):
            asset_classes = [
                el.text.strip() for el in liq_el.findall("assetClassType")
                if el.text and el.text.strip()
            ]
            liquidity_providers.append(LiquidityProvider(
                name=_text(liq_el, "liquidityName") or "",
                lei=_text(liq_el, "liquidityLei"),
                is_affiliated=_text(liq_el, "isAffiliatedPerson") == "Y",
                asset_classes=asset_classes,
            ))

    return FundSeriesInfo(
        name=_text(q_el, "mgmtInvFundName") or "",
        series_id=_text(q_el, "mgmtInvSeriesId") or "",
        lei=_text(q_el, "mgmtInvLei"),
        fund_type=_text(q_el, "fundType"),
        is_diversified=is_diversified,
        avg_net_assets=_opt_decimal(q_el, "mnthlyAvgNetAssets"),
        aggregate_commission=_opt_decimal(q_el, "aggregateCommission"),
        is_securities_lending=_flag(q_el, "isFundSecuritiesLending"),
        advisers=advisers,
        custodians=custodians,
        transfer_agents=transfer_agents,
        admins=admins,
        pricing_services=pricing_services,
        shareholder_servicing_agents=shareholder_agents,
        broker_dealers=broker_dealers,
        brokers=brokers,
        principal_transactions=principal_transactions,
        securities_lending=securities_lending,
        line_of_credit=line_of_credit,
        liquidity_providers=liquidity_providers,
    )


def _parse_service_providers(
    container_el, child_tag: str, role: str,
    name_tag: str, lei_tag: str = "",
    file_tag: str = "", crd_tag: str = "",
    aff_tag: str = "",
) -> List[ServiceProvider]:
    """Parse a container of service provider elements."""
    providers = []
    if container_el is None:
        return providers

    for el in container_el.findall(child_tag):
        providers.append(ServiceProvider(
            name=_text(el, name_tag) or "",
            role=role,
            lei=_text(el, lei_tag) if lei_tag else None,
            file_number=_text(el, file_tag) if file_tag else None,
            crd_number=_clean_na(_text(el, crd_tag)) if crd_tag else None,
            is_affiliated=_text(el, aff_tag) == "Y" if aff_tag else False,
        ))
    return providers


def _parse_etf_info(etf_el) -> ETFInfo:
    """Parse a single exchangeTradedFund element."""
    # Authorized participants (data in attributes)
    authorized_participants = []
    ap_container = etf_el.find("authorizedParticipants")
    if ap_container is not None:
        for ap_el in ap_container.findall("authorizedParticipant"):
            authorized_participants.append(AuthorizedParticipant(
                name=ap_el.get("authorizedParticipantName", ""),
                lei=ap_el.get("authorizedParticipantLei"),
                file_number=ap_el.get("authorizedParticipantFileNo"),
                crd_number=_clean_na(ap_el.get("authorizedParticipantCrdNo")),
                purchase_value=_opt_decimal_text(ap_el.get("authorizedParticipantPurchaseValue")),
                redeem_value=_opt_decimal_text(ap_el.get("authorizedParticipantRedeemValue")),
            ))

    # Exchange info
    exchange = None
    ticker = None
    se_container = etf_el.find("securityExchanges")
    if se_container is not None:
        se_el = se_container.find("securityExchange")
        if se_el is not None:
            exchange = se_el.get("fundExchange")
            ticker = se_el.get("fundsTickerSymbol")

    return ETFInfo(
        series_id=_text(etf_el, "etfSeriesId") or "",
        fund_name=_text(etf_el, "fundName") or "",
        exchange=exchange,
        ticker=ticker,
        creation_unit_size=_opt_decimal(etf_el, "creationUnitNumOfShares"),
        avg_pct_purchased_in_kind=_opt_decimal(etf_el, "creationUnitPurchasedInKind"),
        avg_pct_redeemed_in_kind=_opt_decimal(etf_el, "creationUnitPercentageRedeemedInKind"),
        std_dev_purchased_in_kind=_opt_decimal(etf_el, "creationUnitPurchasedSDInKind"),
        std_dev_redeemed_in_kind=_opt_decimal(etf_el, "creationUnitSDRedeemedInKind"),
        is_in_kind=_text(etf_el, "isInKindETF") == "Y",
        authorized_participants=authorized_participants,
    )
