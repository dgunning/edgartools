# Bundled XBRL taxonomy data

## taxonomy_elements.parquet

The element declarations of the FASB US GAAP Financial Reporting Taxonomy
(`us-gaap`, 2011-2026) and the SEC Reporting Taxonomy (`srt`, 2018-2026): one
row per `prefix:name`, about 24,400 elements in roughly 310 KB.

| Column | Source attribute |
|---|---|
| `prefix` | `us-gaap` or `srt` |
| `name` | `xs:element/@name` |
| `type` | `xs:element/@type` |
| `balance` | `xs:element/@xbrli:balance` (`debit`, `credit` or null) |
| `period_type` | `xs:element/@xbrli:periodType` |
| `abstract` | `xs:element/@abstract == "true"` |
| `substitution_group` | `xs:element/@substitutionGroup` |
| `last_year` | the newest taxonomy year that declares the element |

Values are copied unchanged from the published schemas. When several years
declare an element, the newest year's declaration is kept, so deprecated
concepts that older filings still use keep the declaration of the last year
they were published in.

A filing imports these taxonomies instead of declaring their elements, so the
element catalog parsed from a filing has no balance for a standard concept.
`edgar.xbrl.parsers.concepts.get_balance_type` reads this table when the filing
declares none (GitHub issue #1728).

Rebuild with `scripts/build_taxonomy_elements.py`, which downloads the schemas
from https://xbrl.fasb.org/.

## Notice: Authorized Uses

The data in `taxonomy_elements.parquet` is taken from the US GAAP Financial
Reporting Taxonomy and the SEC Reporting Taxonomy, which carry the following
notices (https://xbrl.fasb.org/terms/TaxonomiesTermsConditions.html and
https://xbrl.fasb.org/terms/SRT_TermsConditions.html).

### US GAAP Financial Reporting Taxonomy

© 2010-2027 Financial Accounting Foundation; © 2007-2010 XBRL US, Inc.; © 2020-2027 XBRL US, Inc. All Rights Reserved.

To meet the mission requirements of the U.S. Securities and Exchange Commission
(the "Commission"), the US GAAP Financial Reporting Taxonomy (the "Taxonomy")
may be used by the public, royalty-free, in reporting financial statements
under U.S. generally accepted accounting principles ("GAAP"), and may be
incorporated without change, in whole or in part, in other works (the
"Permitted Works") that comment on, explain, or assist in the use or
implementation of the Taxonomy. Permitted Works may be copied, published and
distributed by its creator without restriction of any kind imposed hereby;
provided, this Authorized Uses notice is included on the first page thereof.
Under no circumstances may the Taxonomy, or any part of it, be modified in any
way, such as by removing the copyright notice or references to the copyright
holder, except as required to translate it into languages other than English
or with the prior written consent of Financial Accounting Foundation ("FAF").

Copyright in some of the content available in this Taxonomy belongs to third
parties, including XBRL International, Inc. and XBRL US, Inc. (such third party
content, "Third Party Documents"), and such content has been produced on this
website (and in this Taxonomy) with the permission of the Third Party Documents
copyright holders, including XBRL International, Inc. and XBRL US, Inc. Please
check copyright notices on or in respect of individual Third Party Documents.
With respect to XBRL International, Inc., their Third Party Documents may only
be used in accordance with the terms and conditions of the XBRL International,
Inc. Intellectual Property Policy located at
http://www.xbrl.org/Legal2/XBRL-IP-Policy-2007-02-20.pdf (as the same may be
amended from time to time). With respect to XBRL US, Inc., their Third Party
Documents may only be used in accordance with the terms and conditions of the
XBRL US, Inc. Intellectual Property Policy located at
https://xbrl.us/wp-content/uploads/2007/09/ip-policy.pdf (as the same may be
amended from time to time). The content located at such websites, or in any
other copyright notices for Third Party Document copyright holders is the sole
property of such Third Party Document copyright holder(s) and is provided
therein by such Third Party Document copyright holder(s), "as is" without
warranty of any kind, either express or implied by FAF, and FAF has no
responsibility for the content or obligations therein.

WARRANTY DISCLAIMER

THE TAXONOMY, THE INFORMATION CONTAINED HEREIN, AND ALL INFORMATION PROVIDED AS
PART OF THIS TAXONOMY AND ITS ASSOCIATED FILES ARE PROVIDED ON AN "AS-IS,
WHERE-IS AND WITH ALL FAULTS" BASIS, AND THE FINANCIAL ACCOUNTING FOUNDATION,
XBRL INTERNATIONAL, INC., AND ALL OTHER COPYRIGHT HOLDERS DISCLAIM ALL
WARRANTIES, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTY OF
MERCHANTABILITY, FITNESS FOR ANY PARTICULAR PURPOSE, OR TITLE; OR ANY WARRANTY
THAT THE USE OF THE CONTENTS OF THE TAXONOMY OR ITS ASSOCIATED FILES WILL NOT
INFRINGE ANY THIRD PARTY PATENTS, COPYRIGHTS, TRADEMARKS OR OTHER RIGHTS.

LIMITATION OF LIABILITY

IN NO EVENT WILL THE FINANCIAL ACCOUNTING FOUNDATION, XBRL INTERNATIONAL, INC.,
OR ANY OTHER COPYRIGHT HOLDER BE LIABLE TO ANY USER OR ANY THIRD PARTY FOR THE
COST OF PROCURING SUBSTITUTE GOODS OR SERVICES, LOST PROFITS, LOSS OF USE, LOSS
OF DATA OR ANY DIRECT, INDIRECT, CONSEQUENTIAL, INCIDENTAL, PUNITIVE OR SPECIAL
DAMAGES, WHETHER UNDER CONTRACT, TORT, WARRANTY OR OTHERWISE, ARISING IN ANY WAY
OUT OF THE USE OF THIS TAXONOMY OR ITS ASSOCIATED FILES, OR THE PERFORMANCE OR
IMPLEMENTATION OF THE CONTENTS THEREOF OF ANY TYPE WHATSOEVER, WHETHER OR NOT
SUCH PARTY HAD ADVANCE NOTICE OF THE POSSIBILITY OF SUCH DAMAGES.

This Taxonomy includes by import the SEC Reporting Taxonomy (the "SRT").

### SEC Reporting Taxonomy

© 2010-2027 Financial Accounting Foundation; © 2007-2010 XBRL US, Inc. All Rights Reserved.

To meet the mission requirements of the U.S. Securities and Exchange Commission
(the "Commission"), the SEC Reporting Taxonomy (the "SRT") may be used by the
public, royalty-free, for reporting purposes in connection with financial
statements under U.S. generally accepted accounting principles ("GAAP") or as
otherwise provided for by the Commission, and may be incorporated without
change, in whole or in part, in other works (the "Permitted Works") that
comment on, explain, or assist in the use or implementation of the SRT.
Permitted Works may be copied, published and distributed by its creator without
restriction of any kind imposed hereby; provided, this Authorized Uses notice
is included on the first page thereof. Under no circumstances may the SRT, or
any part of it, be modified in any way, such as by removing the copyright
notice or references to the copyright holder, except as required to translate
it into languages other than English or with the prior written consent of
Financial Accounting Foundation ("FAF").

Copyright in some of the content available in this SRT belongs to third
parties, including XBRL International, Inc. (such third party content, "Third
Party Documents"), and such content has been produced on this website (and in
this SRT) with the permission of the Third Party Documents copyright holders,
including XBRL International, Inc. Please check copyright notices on or in
respect of individual Third Party Documents. With respect to XBRL
International, Inc., their Third Party Documents may only be used in accordance
with the terms and conditions of the XBRL International, Inc. Intellectual
Property Policy located at http://www.xbrl.org/Legal2/XBRL-IP-Policy-2007-02-20.pdf
(as the same may be amended from time to time). The content located at such
website, or in any other copyright notices for Third Party Document copyright
holders is the sole property of such Third Party Document copyright holder(s)
and is provided therein by such Third Party Document copyright holder(s), "as
is" without warranty of any kind, either express or implied by FAF, and FAF has
no responsibility for the content or obligations therein.

WARRANTY DISCLAIMER

THE SRT, THE INFORMATION CONTAINED HEREIN, AND ALL INFORMATION PROVIDED AS PART
OF THIS SRT AND ITS ASSOCIATED FILES ARE PROVIDED ON AN "AS-IS, WHERE-IS AND
WITH ALL FAULTS" BASIS, AND THE FINANCIAL ACCOUNTING FOUNDATION, XBRL
INTERNATIONAL, INC., AND ALL OTHER COPYRIGHT HOLDERS DISCLAIM ALL WARRANTIES,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO ANY WARRANTY OF
MERCHANTABILITY, FITNESS FOR ANY PARTICULAR PURPOSE, OR TITLE; OR ANY WARRANTY
THAT THE USE OF THE CONTENTS OF THE SRT OR ITS ASSOCIATED FILES WILL NOT
INFRINGE ANY THIRD PARTY PATENTS, COPYRIGHTS, TRADEMARKS OR OTHER RIGHTS.

LIMITATION OF LIABILITY

IN NO EVENT WILL THE FINANCIAL ACCOUNTING FOUNDATION, XBRL INTERNATIONAL, INC.,
OR ANY OTHER COPYRIGHT HOLDER BE LIABLE TO ANY USER OR ANY THIRD PARTY FOR THE
COST OF PROCURING SUBSTITUTE GOODS OR SERVICES, LOST PROFITS, LOSS OF USE, LOSS
OF DATA OR ANY DIRECT, INDIRECT, CONSEQUENTIAL, INCIDENTAL, PUNITIVE OR SPECIAL
DAMAGES, WHETHER UNDER CONTRACT, TORT, WARRANTY OR OTHERWISE, ARISING IN ANY WAY
OUT OF THE USE OF THIS SRT OR ITS ASSOCIATED FILES, OR THE PERFORMANCE OR
IMPLEMENTATION OF THE CONTENTS THEREOF OF ANY TYPE WHATSOEVER, WHETHER OR NOT
SUCH PARTY HAD ADVANCE NOTICE OF THE POSSIBILITY OF SUCH DAMAGES.
