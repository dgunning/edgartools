# Sample XML strings for testing
SAMPLE_INSTANCE_XML = """
<xbrl xmlns="http://www.xbrl.org/2003/instance"
      xmlns:dei="http://xbrl.sec.gov/dei/2023"
      xmlns:us-gaap="http://fasb.org/us-gaap/2023">
    <context id="AsOf2023">
        <entity><identifier scheme="http://www.sec.gov/CIK">0000320193</identifier></entity>
        <period><instant>2023-09-30</instant></period>
    </context>
    <context id="Duration2023">
        <entity><identifier scheme="http://www.sec.gov/CIK">0000320193</identifier></entity>
        <period>
            <startDate>2023-07-01</startDate>
            <endDate>2023-09-30</endDate>
        </period>
    </context>

    <!-- Entity Information -->
    <dei:EntityRegistrantName contextRef="AsOf2023">APPLE INC</dei:EntityRegistrantName>
    <dei:DocumentPeriodEndDate contextRef="AsOf2023">2023-09-30</dei:DocumentPeriodEndDate>

    <!-- Balance Sheet Items -->
    <us-gaap:AssetsCurrent contextRef="AsOf2023" unitRef="USD" decimals="-6">154770000000</us-gaap:AssetsCurrent>
    <us-gaap:CashAndCashEquivalentsAtCarryingValue contextRef="AsOf2023" unitRef="USD" decimals="-6">29965000000</us-gaap:CashAndCashEquivalentsAtCarryingValue>
    <us-gaap:MarketableSecuritiesCurrent contextRef="AsOf2023" unitRef="USD" decimals="-6">31590000000</us-gaap:MarketableSecuritiesCurrent>
</xbrl>
"""

SAMPLE_PRESENTATION_XML = """
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
    <link:roleRef roleURI="http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS" 
                  xlink:type="simple" 
                  xlink:href="role/BalanceSheets"/>

    <link:presentationLink xlink:role="http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS" xlink:type="extended">
        <!-- Statement Structure -->
        <link:loc xlink:type="locator" xlink:label="loc_BalanceSheetAbstract" 
                 xlink:href="http://fasb.org/us-gaap/2023#us-gaap_StatementOfFinancialPositionAbstract"/>

        <!-- Table -->
        <link:loc xlink:type="locator" xlink:label="loc_BalanceSheetTable" 
                 xlink:href="http://fasb.org/us-gaap/2023#us-gaap_StatementTable"/>
        <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
                             xlink:from="loc_BalanceSheetAbstract" xlink:to="loc_BalanceSheetTable" order="1"/>

        <!-- Line Items Container -->
        <link:loc xlink:type="locator" xlink:label="loc_LineItems" 
                 xlink:href="http://fasb.org/us-gaap/2023#us-gaap_StatementLineItems"/>
        <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
                             xlink:from="loc_BalanceSheetTable" xlink:to="loc_LineItems" order="1"/>

        <!-- Assets Section -->
        <link:loc xlink:type="locator" xlink:label="loc_AssetsAbstract" 
                 xlink:href="http://fasb.org/us-gaap/2023#us-gaap_AssetsAbstract"/>
        <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
                             xlink:from="loc_LineItems" xlink:to="loc_AssetsAbstract" order="1"/>

        <!-- Current Assets -->
        <link:loc xlink:type="locator" xlink:label="loc_AssetsCurrent" 
                 xlink:href="http://fasb.org/us-gaap/2023#us-gaap_AssetsCurrent"/>
        <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
                             xlink:from="loc_AssetsAbstract" xlink:to="loc_AssetsCurrent" order="1"/>

        <link:loc xlink:type="locator" xlink:label="loc_CashAndCashEquivalents" 
                 xlink:href="http://fasb.org/us-gaap/2023#us-gaap_CashAndCashEquivalentsAtCarryingValue"/>
        <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
                             xlink:from="loc_AssetsCurrent" xlink:to="loc_CashAndCashEquivalents" order="1"/>

        <link:loc xlink:type="locator" xlink:label="loc_MarketableSecurities" 
                 xlink:href="http://fasb.org/us-gaap/2023#us-gaap_MarketableSecuritiesCurrent"/>
        <link:presentationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/parent-child"
                             xlink:from="loc_AssetsCurrent" xlink:to="loc_MarketableSecurities" order="2"/>
    </link:presentationLink>
</link:linkbase>
"""

SAMPLE_CALCULATION_XML = """
<link:linkbase xmlns:link="http://www.xbrl.org/2003/linkbase"
               xmlns:xlink="http://www.w3.org/1999/xlink">
    <link:roleRef roleURI="http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS" 
                  xlink:type="simple" 
                  xlink:href="role/BalanceSheets"/>

    <link:calculationLink xlink:role="http://www.apple.com/role/CONSOLIDATEDBALANCESHEETS" xlink:type="extended">
        <!-- Current Assets Calculation -->
        <link:loc xlink:type="locator" xlink:label="loc_AssetsCurrent" 
                 xlink:href="http://fasb.org/us-gaap/2023#us-gaap_AssetsCurrent"/>

        <link:loc xlink:type="locator" xlink:label="loc_CashAndCashEquivalents" 
                 xlink:href="http://fasb.org/us-gaap/2023#us-gaap_CashAndCashEquivalentsAtCarryingValue"/>
        <link:calculationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
                            xlink:from="loc_AssetsCurrent" xlink:to="loc_CashAndCashEquivalents" 
                            order="1" weight="1.0"/>

        <link:loc xlink:type="locator" xlink:label="loc_MarketableSecurities" 
                 xlink:href="http://fasb.org/us-gaap/2023#us-gaap_MarketableSecuritiesCurrent"/>
        <link:calculationArc xlink:type="arc" xlink:arcrole="http://www.xbrl.org/2003/arcrole/summation-item"
                            xlink:from="loc_AssetsCurrent" xlink:to="loc_MarketableSecurities" 
                            order="2" weight="1.0"/>
    </link:calculationLink>
</link:linkbase>
"""
