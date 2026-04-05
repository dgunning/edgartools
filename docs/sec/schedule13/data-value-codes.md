# Schedule 13D/G Data Value Codes

This document contains all enumerated values and codes used in Schedule 13D and 13G XML submissions.

## Submission Types

### Schedule 13D

| Value | Description |
|-------|-------------|
| `SCHEDULE 13D` | Report acquisition of beneficial ownership of more than 5% |
| `SCHEDULE 13D/A` | Amendment to Schedule 13D |

### Schedule 13G

| Value | Description |
|-------|-------------|
| `SCHEDULE 13G` | Report beneficial ownership by passive/institutional/exempt investors |
| `SCHEDULE 13G/A` | Amendment to Schedule 13G |

---

## Common Codes

### LIVE_TEST_TYPE

Used in `<liveTestFlag>` element:

| Value | Description |
|-------|-------------|
| `LIVE` | Live/production submission |
| `TEST` | Test submission |

### YES_NO_TYPE

Used in various flag elements:

| Value | Description |
|-------|-------------|
| `Y` | Yes |
| `N` | No |

### TRUE_FALSE_TYPE

Used in boolean elements like `<previouslyFiledFlag>`, `<overrideInternetFlag>`:

| Value | Description |
|-------|-------------|
| `true` | True |
| `false` | False |
| `1` | True (alternative) |
| `0` | False (alternative) |

---

## Schedule 13D Specific Codes

### MEMBER_TYPE

Used in `<memberOfGroup>` element:

| Value | Description |
|-------|-------------|
| `a` | Check if the person filing is a member of a group |
| `b` | Check if the person filing disclaims being a member of a group |

### FUND_TYPE

Used in `<fundType>` element (max 6 occurrences):

| Code | Description |
|------|-------------|
| `SC` | Subject Company - Company whose securities are being acquired |
| `BK` | Bank |
| `AF` | Affiliate - Affiliate of reporting person |
| `WC` | Working Capital - Working Capital of reporting person |
| `PF` | Personal Funds - Personal Funds of reporting person |
| `OO` | Other |

### TYPE_OF_REPORTING_PERSON (13D)

Used in `<typeOfReportingPerson>` element (max 13 occurrences):

| Code | Description |
|------|-------------|
| `BD` | Broker Dealer |
| `BK` | Bank |
| `CP` | Church Plan |
| `CO` | Corporation |
| `EP` | Employee Benefit Plan or Endowment Fund |
| `IN` | Individual |
| `IA` | Investment Adviser |
| `IC` | Insurance Company |
| `IV` | Investment Company |
| `HC` | Parent Holding Company/Control Person |
| `PN` | Partnership |
| `SA` | Savings Association |
| `OO` | Other |

---

## Schedule 13G Specific Codes

### RULE_TYPE

Used in `<designateRulePursuantThisScheduleFiled>` element:

| Value | Description |
|-------|-------------|
| `Rule 13d-1(b)` | Qualified institutional investors (banks, broker-dealers, insurance companies, etc.) |
| `Rule 13d-1(c)` | Passive investors (own less than 20% and have no intent to influence) |
| `Rule 13d-1(d)` | Exempt investors |

### GROUP_TYPE

Used in `<memberGroup>` element:

| Value | Description |
|-------|-------------|
| `a` | Member of a group |
| `b` | Disclaims being member of a group |

### TYPE_OF_REPORTING_PERSON (13G)

Used in `<typeOfReportingPerson>` element (max 14 occurrences):

| Code | Description |
|------|-------------|
| `BD` | Broker Dealer |
| `BK` | Bank |
| `CP` | Church Plan |
| `CO` | Corporation |
| `EP` | Employee Benefit Plan or Endowment Fund |
| `FI` | Non-U.S. Institution |
| `HC` | Parent Holding Company/Control Person |
| `IA` | Investment Adviser |
| `IC` | Insurance Company |
| `IN` | Individual |
| `IV` | Investment Company |
| `PN` | Partnership |
| `SA` | Savings Association |
| `OO` | Other |

### BUSINESS_ENGAGED_TYPE

Used in `<typeOfPersonFiling>` element in Item 3 (max 11 occurrences):

| Code | Description |
|------|-------------|
| `BD` | Broker or dealer registered under section 15 of the Act (15 U.S.C. 78o) |
| `BK` | Bank as defined in section 3(a)(6) of the Act (15 U.S.C. 78c) |
| `CP` | A church plan excluded from definition of investment company under section 3(c)(14) of the Investment Company Act of 1940 |
| `EP` | An employee benefit plan or endowment fund in accordance with § 240.13d-1(b)(1)(ii)(F) |
| `FI` | A non-U.S. institution in accordance with § 240.13d-1(b)(1)(ii)(J) |
| `HC` | A parent holding company or control person in accordance with § 240.13d-1(b)(1)(ii)(G) |
| `IA` | An investment adviser in accordance with § 240.13d-1(b)(1)(ii)(E) |
| `IC` | Insurance company as defined in section 3(a)(19) of the Act (15 U.S.C. 78c) |
| `IV` | Investment company registered under section 8 of the Investment Company Act of 1940 |
| `SA` | A savings association as defined in Section 3(b) of the Federal Deposit Insurance Act (12 U.S.C. 1813) |
| `OO` | Group, in accordance with § 240.13d-1(b)(1)(ii)(K) |

---

## State and Country Codes

Used in `<stateOrCountry>` and `<citizenshipOrOrganization>` elements.

### U.S. States

| Code | State |
|------|-------|
| `AK` | Alaska |
| `AL` | Alabama |
| `AR` | Arkansas |
| `AZ` | Arizona |
| `CA` | California |
| `CO` | Colorado |
| `CT` | Connecticut |
| `DC` | District of Columbia |
| `DE` | Delaware |
| `FL` | Florida |
| `GA` | Georgia |
| `HI` | Hawaii |
| `IA` | Iowa |
| `ID` | Idaho |
| `IL` | Illinois |
| `IN` | Indiana |
| `KS` | Kansas |
| `KY` | Kentucky |
| `LA` | Louisiana |
| `MA` | Massachusetts |
| `MD` | Maryland |
| `ME` | Maine |
| `MI` | Michigan |
| `MN` | Minnesota |
| `MO` | Missouri |
| `MS` | Mississippi |
| `MT` | Montana |
| `NC` | North Carolina |
| `ND` | North Dakota |
| `NE` | Nebraska |
| `NH` | New Hampshire |
| `NJ` | New Jersey |
| `NM` | New Mexico |
| `NV` | Nevada |
| `NY` | New York |
| `OH` | Ohio |
| `OK` | Oklahoma |
| `OR` | Oregon |
| `PA` | Pennsylvania |
| `RI` | Rhode Island |
| `SC` | South Carolina |
| `SD` | South Dakota |
| `TN` | Tennessee |
| `TX` | Texas |
| `UT` | Utah |
| `VA` | Virginia |
| `VT` | Vermont |
| `WA` | Washington |
| `WI` | Wisconsin |
| `WV` | West Virginia |
| `WY` | Wyoming |

### U.S. Territories

| Code | Territory |
|------|-----------|
| `GU` | Guam |
| `PR` | Puerto Rico |
| `VI` | Virgin Islands, U.S. |
| `X1` | United States |

### Canadian Provinces

| Code | Province |
|------|----------|
| `A0` | Alberta, Canada |
| `A1` | British Columbia, Canada |
| `A2` | Manitoba, Canada |
| `A3` | New Brunswick, Canada |
| `A4` | Newfoundland, Canada |
| `A5` | Nova Scotia, Canada |
| `A6` | Ontario, Canada |
| `A7` | Prince Edward Island, Canada |
| `A8` | Quebec, Canada |
| `A9` | Saskatchewan, Canada |
| `B0` | Yukon, Canada |
| `Z4` | Canada (Federal Level) |

### Major Countries

| Code | Country |
|------|---------|
| `C3` | Australia |
| `C4` | Austria |
| `C9` | Belgium |
| `D5` | Brazil |
| `F4` | China |
| `F5` | Taiwan |
| `G7` | Denmark |
| `H9` | Finland |
| `I0` | France |
| `2M` | Germany |
| `J3` | Greece |
| `K3` | Hong Kong |
| `K5` | Hungary |
| `K7` | India |
| `K8` | Indonesia |
| `L2` | Ireland |
| `L3` | Israel |
| `L6` | Italy |
| `M0` | Japan |
| `M5` | Korea, Republic of |
| `N4` | Luxembourg |
| `N8` | Malaysia |
| `O5` | Mexico |
| `P7` | Netherlands |
| `Q2` | New Zealand |
| `Q8` | Norway |
| `R6` | Philippines |
| `R9` | Poland |
| `S1` | Portugal |
| `1Z` | Russian Federation |
| `U0` | Singapore |
| `T3` | South Africa |
| `U3` | Spain |
| `V7` | Sweden |
| `V8` | Switzerland |
| `W8` | Turkey |
| `X0` | United Kingdom |
| `XX` | Unknown |

### Other Countries

See the full list in [Appendix A of the SEC specification](Schedule13Dand13GTechnicalSpecification.pdf) for complete country code listings (200+ codes).

---

## Document Types

Used in `<conformedDocumentType>` element:

Common document types include:
- `COVER` - Cover letter
- `EX-99` - Exhibits
- `FULL` - Full document
- Various exhibit types following SEC document type conventions
