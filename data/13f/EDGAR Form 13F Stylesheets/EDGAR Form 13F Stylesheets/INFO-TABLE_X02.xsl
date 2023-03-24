<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0"
xmlns:xsl="http://www.w3.org/1999/XSL/Transform" 
xmlns:xs="http://www.w3.org/2001/XMLSchema" 
xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable"
xmlns:n1="http://www.sec.gov/edgar/document/thirteenf/informationtable"
xmlns:ns1="http://www.sec.gov/edgar/common">
 <xsl:output method="html" 
 doctype-system="http://www.w3.org/TR/html4/strict.dtd" 
 doctype-public="-//W3C//DTD HTML 4.01//EN" 
 indent="yes"/> 
<xsl:template match="/">
<html>
<head>
<style type="text/css">
					<xsl:comment>
  /* INFO TABLE CSS */
.infoTable {
	border:1px solid #606020;
	table-layout:fixed !important;
	font-size:0.7em;
	overflow:hidden !important;
}
.infoTable th {
	border:1px solid #606020;
	white-space:nowrap !important;
	text-align:center;
	padding:4px 2px;
	border-bottom:1px solid #404040;
	text-transform:inherit;
	word-break:break-all;
	font-size:0.8em;
	letter-spacing: -1px;
}
.infoTable th td {
	border:1px solid #606020;
	border-bottom:1px solid #404040;
}
.infoTable tr td {
	border:1px solid #606020;
	border-bottom:1px solid #404040;
	white-space:nowrap !important;
	overflow:hidden !important;
	color:#000088;
}
.infoTable tr td:hover {
	border:1px solid #606020;
	border-bottom:2px solid #606020;
	white-space:normal !important;
	overflow:auto !important;
	background-color:#FF9;
	font-size:1.2em;
	color:#000088;
}
.infoTable td {
	margin:4px 2px;
}
.infoCol1 {
	width:auto
}
.infoCol2 {
	width:auto;
}
.infoCol3 {
	text-align:right;
	width:auto
}
.infoCol4 {
	text-align:right;
}
.infoCol5 {
	width:auto;
}
.infoCol5a {
	text-align:right;
	width:auto
}
.infoCol5b {
	text-align:center;
}
.infoCol5c {
	text-align:center;
	width:auto
}
.infoCol6 {
}
.infoCol7 {
	width:auto
}
.infoCol8 {
	width:300px;
}
.infoCol8a {
	text-align:center;
	width:auto;
}
.infoCol8b {
	text-align:center;
	width:auto
}
.infoCol8c {
	text-align:center;
	width:auto;
}
.fullwidth {
	width:1000px;
}
</xsl:comment>
				</style>
</head>
  <body class="fullwidth">
   <div class="content">
    <h2>FORM 13F INFORMATION TABLE</h2>
    
     <xsl:if test="count(informationTable/additionalHeaderInfo) &gt; 0">
	   Filer Name: <xsl:value-of select="informationTable/additionalHeaderInfo/institutionalInvestmentManagerName"/>
	   <br/>
	   Form 13F Filer Number: <xsl:value-of select="informationTable/additionalHeaderInfo/form13FFileNumber"/>
	   <br/>
	   Report for Calendar Quarter: <xsl:value-of select="informationTable/additionalHeaderInfo/reportCalendarOrQuarter"/>
	   <br/>
	   <br/>
    </xsl:if>
   <table border="0" class="infoTable" cellpadding="0" cellspacing="0">
      
    <tr>
      <th valign="top" class="infoCol1">COLUMN 1</th>
      <th valign="top" class="infoCol2">COLUMN 2</th>
      <th colspan="2" valign="top" class="infoCol5">COLUMN 3</th>
      <th valign="top" class="infoCol4">COLUMN 4</th>
      <th colspan="3" valign="top" class="infoCol5">COLUMN 5</th>
      <th valign="top" class="infoCol6">COLUMN 6</th>
      <th valign="top" class="infoCol7">COLUMN 7</th>
      <th colspan="3" valign="top" class="infoCol8">COLUMN 8</th>
    </tr>
    <tr>
      <th rowspan="2" class="infoCol1">NAME &#160; OF &#160; ISSUER<br>
       </br></th>
      <th rowspan="2" class="infoCol2">TITLE&#160; OF<br>
        CLASS</br></th>
      <th rowspan="2" class="infoCol5a">CUSIP</th>
      <th rowspan="2" class="infoCol5c">FIGI</th>
      <th rowspan="2" class="infoCol4">VALUE<br>
        (to the nearest dollar)</br></th>
      <th rowspan="2" class="infoCol5a">SHRS &#160; or<br>
        PRN AMT</br></th>
      <th rowspan="2" class="infoCol5b">SH &#160; or<br>
        PRN</br></th>
      <th rowspan="2" class="infoCol5c">PUT /<br>
        CALL</br></th>
      <th rowspan="2" class="infoCol6">INVESTMENT<br>
        DISCRETION</br></th>
      <th rowspan="2" class="infoCol7">OTHER<br>
        MANAGER</br></th>
      <th colspan="3" class="infoCol8">VOTING &#160; AUTHORITY</th>
    </tr> 
	<tr>
      <th class="infoCol8a">SOLE</th>
      <th class="infoCol8b">SHARED</th>
      <th class="infoCol8c">NONE</th>
    </tr>
    <xsl:for-each select="informationTable/infoTable">
    <tr>
		<xsl:choose>
			<xsl:when test="string-length(nameOfIssuer)!=0">
				<td valign="top" class="infoCol1">
					<xsl:value-of select="nameOfIssuer"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol1">-</td>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:choose>
			<xsl:when test="string-length(titleOfClass)!=0">
				<td valign="top" class="infoCol2">
					<xsl:value-of select="titleOfClass"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol2">-</td>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:choose>
			<xsl:when test="string-length(cusip)!=0">
				<td valign="top" class="infoCol5a">
					<xsl:value-of select="cusip"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol5a">-</td>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:choose>
			<xsl:when test="string-length(figi)!=0">
				<td valign="top" class="infoCol5c">
					<xsl:value-of select="figi"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol5c">-</td>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:choose>
			<xsl:when test="string-length(value)!=0">
				<td valign="top" class="infoCol4">
					<xsl:value-of select="value"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol4">-</td>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:choose>
			<xsl:when test="string-length(shrsOrPrnAmt/sshPrnamt)!=0">
				<td valign="top" class="infoCol5a">
					<xsl:value-of select="shrsOrPrnAmt/sshPrnamt"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol5a">-</td>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:choose>
			<xsl:when test="string-length(shrsOrPrnAmt/sshPrnamtType)!=0">
				<td valign="top" class="infoCol5b">
					<xsl:value-of select="shrsOrPrnAmt/sshPrnamtType"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol5b">-</td>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:choose>
			<xsl:when test="string-length(putCall)!=0">
				<td valign="top" class="infoCol5c">
					<xsl:value-of select="putCall"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol5c">-</td>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:choose>
			<xsl:when test="string-length(investmentDiscretion)!=0">
				<td valign="top" class="infoCol6">
					<xsl:value-of select="investmentDiscretion"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol6">-</td>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:choose>
			<xsl:when test="string-length(otherManager)!=0">
				<td valign="top" class="infoCol7">
					<xsl:value-of select="otherManager"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol7">-</td>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:choose>
			<xsl:when test="string-length(votingAuthority/Sole)!=0">
				<td valign="top" class="infoCol8a">
					<xsl:value-of select="votingAuthority/Sole"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol8a">-</td>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:choose>
			<xsl:when test="string-length(votingAuthority/Shared)!=0">
				<td valign="top" class="infoCol8b">
					<xsl:value-of select="votingAuthority/Shared"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol8b">-</td>
			</xsl:otherwise>
		</xsl:choose>
		<xsl:choose>
			<xsl:when test="string-length(votingAuthority/None)!=0">
				<td valign="top" class="infoCol8c">
					<xsl:value-of select="votingAuthority/None"/>
				</td>
			</xsl:when>
			<xsl:otherwise>
				<td valign="top" class="infoCol8c">-</td>
			</xsl:otherwise>
		</xsl:choose>
	</tr>
    </xsl:for-each>
    </table>
	<p>[Repeat as Necessary]</p>
  </div> 	
  </body>
</html>
</xsl:template>
</xsl:stylesheet>

