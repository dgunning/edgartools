# Proposed Improvements to `is_individual` in edgartools

## Background

The `is_individual` classification in edgartools determines whether an SEC entity is a person or a company. There are currently two implementations:

- **`EntityData.is_individual`** (`edgar/entity/data.py:478`) — the primary property used at runtime
- **`is_individual_from_json()`** (`edgar/reference/company_dataset.py:70`) — a standalone function for bulk JSON processing

Both use a decision-tree approach with 5 checks. This proposal suggests improvements based on signals we've validated against the full SEC submissions dataset (~900K entities).

---

## Current Implementation (Summary)

```python
# edgar/entity/data.py (simplified)
@cached_property
def is_individual(self) -> bool:
    if len(self.tickers) > 0 or len(self.exchanges) > 0:
        return False
    elif self.state_of_incorporation:
        if self.cik == 1033331:  # Reed Hastings
            return True
        return False
    elif self.entity_type not in ['', 'other']:
        return False
    elif has_company_filings(self.filings.data['form']):
        if self.cik == 315090:  # Warren Buffett
            return True
        return False
    elif self.ein is None or self.ein == "000000000":
        return True
    else:
        return False
```

---

## Problem: Entities That Fall Through the Cracks

The current logic misclassifies entities in several categories:

### 1. Companies that only file as owners

Holding companies and institutional investors that file SC 13D/13G or Forms 3/4/5 as **owners** — not issuers — may have no tickers, no state of incorporation, entity type `"other"`, and no company-specific forms. The current logic classifies these as individuals.

**Examples**: Family offices, private holding companies, foreign institutional investors.

### 2. Old/inactive companies

Companies that filed decades ago and whose only forms are pre-EDGAR types not in `COMPANY_FORMS`. They have no tickers, no state, entity type `""`, and no matching forms. Their names contain obvious company keywords like "INC" or "CORP" but nothing checks names.

### 3. The EIN final-else branch

The final branch (`else: return False`) fires when an entity has a valid EIN but no other company signals. This correctly classifies most cases, but lacks the Warren Buffett exception — Buffett has an EIN, and if the company-filings check were to miss (e.g., due to `max_filings` truncation in `has_company_filings`), he'd fall through to the EIN check without protection.

### 4. `is_individual_from_json` drift

The JSON version uses a hardcoded set of only 7 forms:

```python
company_forms = {'10-K', '10-Q', '8-K', '10-K/A', '10-Q/A', '20-F', 'S-1'}
```

This misses investment company forms (N-CSR, N-CEN, N-MFP), broker-dealer forms (X-17A-5), proxy materials (DEF 14A), and dozens of others already in `COMPANY_FORMS` in `edgar/entity/constants.py`. The two implementations should share the same form set.

---

## Proposed Changes

### Change 1: Add `insiderTransactionForIssuerExists` as the strongest signal

The SEC submission JSON includes `insiderTransactionForIssuerExists` — a boolean indicating the entity **receives** insider filings (Forms 3/4/5) as the issuer of securities. This is the single strongest company signal: only companies issue securities.

```python
# New first check — strongest signal
if self.insider_transaction_for_issuer_exists is True:
    return False
```

This field is already present in the SEC submission JSON but isn't currently exposed on `EntityData`. It would need to be added as a property.

**Why it matters**: This catches every publicly-traded company and many private ones, regardless of whether they have tickers in the SEC data. Some companies have `insiderTransactionForIssuerExists=True` but empty ticker lists (e.g., pre-IPO companies with insider filings).

### Change 2: Add name-based heuristics as a fallback

After all structured signals are exhausted, check the entity name for company keywords. This catches old/inactive companies and holding companies that lack other signals.

#### Proposed keyword sets

**Loose keywords** (substring match — keyword appears anywhere in name):

```python
COMPANY_NAME_KEYWORDS = {
    # Corporate structure
    "INC", "CORP", "CORPORATION", "LLC", "L.L.C.", "LTD", "LIMITED",
    "LP", "L.P.", "COMPANY", "GROUP", "HOLDINGS",
    "PARTNERS", "PARTNERSHIP",
    # Investment entities
    "TRUST", "FUND", "FUNDS", "CAPITAL", "VENTURES",
    "MANAGEMENT", "ADVISORS", "ADVISERS", "SECURITIES",
    "INVESTMENT", "INVESTMENTS", "PORTFOLIO",
    # Industries
    "TECHNOLOGIES", "SERVICES", "INTERNATIONAL", "GLOBAL",
    "FINANCIAL", "BANK", "INDUSTRIES", "SYSTEMS", "ENTERPRISES",
    # Organizations
    "FOUNDATION", "ASSOCIATION", "AUTHORITY",
}
```

**Strict keywords** (whole-word match only, to avoid false positives like "SCOTT" matching "CO"):

```python
COMPANY_NAME_KEYWORDS_STRICT = {
    "CO",   # Company — but not "SCOTT" or "COHEN"
    "NA",   # National Association (banks)
    "PLC",  # Public Limited Company
    "SA",   # Sociedad Anonima
}
```

#### Implementation

```python
import re

def _name_suggests_company(name: str) -> bool:
    """Check if entity name contains company keywords."""
    if not name:
        return False
    upper = name.upper()

    # Loose keyword match (substring)
    if any(kw in upper for kw in COMPANY_NAME_KEYWORDS):
        return True

    # Strict keyword match (whole word only)
    words = set(re.split(r"\W+", upper))
    if words & COMPANY_NAME_KEYWORDS_STRICT:
        return True

    # SEC filing suffixes like /ADR/, /BD/, /TA/ indicate companies
    if re.search(r"/[A-Z0-9-]{2,}(?:/|\s|$)", name):
        return True

    return False
```

This should be checked **after** the EIN check and **before** the final default:

```python
elif _name_suggests_company(self.name):
    return False
```

### Change 3: Add the `insiderTransactionForOwnerExists` signal

The SEC submission JSON also includes `insiderTransactionForOwnerExists` — True when the entity files Forms 3/4/5 as a reporting **owner**. While weaker than the issuer flag (companies can also be owners), it provides a useful positive signal for individuals when combined with the absence of company signals.

```python
# After name heuristics, before final default
elif (self.insider_transaction_for_owner_exists is True
      and self.insider_transaction_for_issuer_exists is not True):
    return True
```

This is a weak signal and should be placed late in the priority chain — only used when no company signals have been found.

### Change 4: Unify `is_individual_from_json` with the constants

Replace the hardcoded 7-form set in `is_individual_from_json` with the shared `COMPANY_FORMS` constant:

```python
# Before (company_dataset.py)
company_forms = {'10-K', '10-Q', '8-K', '10-K/A', '10-Q/A', '20-F', 'S-1'}

# After
from edgar.entity.constants import COMPANY_FORMS
```

And add the same name heuristic and insider flag checks to keep both implementations consistent.

### Change 5: Guard the EIN branch against known exceptions

The current code handles the Warren Buffett exception on the company-filings branch but not on the EIN branch. If `has_company_filings` returns `False` (e.g., due to `max_filings` truncation), Buffett falls through to the EIN check with no protection.

```python
# Current (no exception handling on EIN)
elif not hasattr(self, 'ein') or self.ein is None or self.ein == "000000000":
    return True
else:
    return False  # Has valid EIN → company (but Buffett has a valid EIN!)

# Proposed
elif not hasattr(self, 'ein') or self.ein is None or self.ein == "000000000":
    return True
elif self.ein and self.ein != "000000000":
    if self.cik == 315090:  # Warren Buffett
        return True
    return False
```

---

## Proposed Signal Priority (Complete)

| Priority | Signal | Classification | Rationale |
|----------|--------|----------------|-----------|
| 1 | `insiderTransactionForIssuerExists` | Company | Receives insider filings = issues securities |
| 2 | Has tickers or exchanges | Company | Traded securities |
| 3 | State of incorporation | Company | Incorporated entities (exception: CIK 1033331) |
| 4 | Entity type in {operating, investment, fund, asset_backed} | Company | SEC-assigned type |
| 5 | Company-specific forms in filing history | Company | Filed 10-K, 8-K, N-CSR, etc. (exception: CIK 315090) |
| 6 | Valid EIN (not "000000000") | Company | Has employer ID (exception: CIK 315090) |
| 7 | Name contains company keywords | Company | INC, CORP, LLC, FUND, etc. |
| 8 | `insiderTransactionForOwnerExists` (without issuer) | Individual | Files as insider owner only |
| 9 | Entity type is None/empty/"other" | Individual | Default for unclassified entities |

---

## Proposed Implementation

```python
@cached_property
def is_individual(self) -> bool:
    """
    Determine if this entity is an individual person rather than a company.

    Uses a priority-based signal system. Stronger signals (tickers, entity type,
    issuer flag) take precedence over weaker ones (name keywords, owner flag).
    """

    # 1. Strongest: receives insider filings as ISSUER → definitely a company
    if getattr(self, 'insider_transaction_for_issuer_exists', None) is True:
        return False

    # 2. Has tickers or exchanges → traded company
    if len(self.tickers) > 0 or len(self.exchanges) > 0:
        return False

    # 3. State of incorporation → company (with exception)
    state = getattr(self, 'state_of_incorporation', None)
    if state and state.strip():
        if self.cik == 1033331:  # Reed Hastings
            return True
        return False

    # 4. Entity type indicates company
    entity_type = getattr(self, 'entity_type', '')
    if entity_type and entity_type not in ('', 'other'):
        return False

    # 5. Company-specific forms in filing history
    has_company_filings_fn = lazy_import('edgar.entity.core.has_company_filings')
    if has_company_filings_fn(self.filings.data['form']):
        if self.cik == 315090:  # Warren Buffett
            return True
        return False

    # 6. Valid EIN → company (with exception)
    ein = getattr(self, 'ein', None)
    if ein and ein != "000000000":
        if self.cik == 315090:  # Warren Buffett
            return True
        return False

    # 7. Name contains company keywords → company
    if _name_suggests_company(self.name):
        return False

    # 8. Files as insider owner (without being issuer) → individual
    if getattr(self, 'insider_transaction_for_owner_exists', None) is True:
        return True

    # 9. Default: unclassified entity type → individual
    return True
```

---

## Impact Assessment

Based on analysis of the full SEC submissions dataset (~900K entities):

| Category | Estimated affected entities | Current classification | Proposed classification |
|----------|-----------------------------|------------------------|-------------------------|
| Holding companies filing as owners only | ~2,000-5,000 | Individual (incorrect) | Company (correct) |
| Old/inactive companies with name keywords | ~3,000-8,000 | Individual (incorrect) | Company (correct) |
| Entities with `insiderTransactionForIssuerExists` but no tickers | ~500-1,000 | Depends on other signals | Company (faster, more reliable) |
| Warren Buffett via EIN branch | 1 | Company (incorrect) | Individual (correct) |

The name heuristic is the highest-impact change. Entities like "ACME INDUSTRIES INC" with entity type `""`, no tickers, no state, and no recent filings are currently classified as individuals. The keyword check fixes these with minimal false-positive risk — individuals rarely have "INC" or "CORP" in their SEC-registered names.

---

## Change 6: Expand `COMPANY_FORMS` in `edgar/entity/constants.py`

The current `COMPANY_FORMS` set in edgartools has ~50 forms but is missing amendments and several form families. The recommended set below adds 27 forms (marked with `# NEW`) that we've validated against the full submissions dataset.

```python
# edgar/entity/constants.py — recommended COMPANY_FORMS
COMPANY_FORMS = {
    # Registration statements
    "S-1", "S-3", "S-4", "S-8", "S-11",

    # Foreign issuers registration forms
    "F-1", "F-3", "F-4", "F-6", "F-7", "F-8", "F-9", "F-10", "F-80",

    # Foreign form amendments and effectiveness
    "F-6EF", "F-6 POS", "F-3ASR", "F-4MEF", "F-10EF", "F-3D", "F-3MEF",

    # Exchange Act registration
    "10-12B", "10-12G",

    # Periodic reports
    "10-K", "10-Q", "10-K/A", "10-Q/A",
    "10-KSB",      # NEW — small business annual report (pre-2008)
    "10-KSB/A",    # NEW — small business annual report amendment
    "10-QSB",      # NEW — small business quarterly report (pre-2008)
    "10-QSB/A",    # NEW — small business quarterly report amendment
    "20-F",        # Foreign issuers
    "20-F/A",      # NEW — foreign annual report amendment
    "40-F",        # Foreign issuers
    "40-F/A",      # NEW — foreign annual report amendment
    "11-K",        # Employee benefit plans
    "11-K/A",      # NEW — employee benefit plan amendment

    # Current reports
    "8-K",
    "8-K/A",       # NEW — current report amendment
    "6-K",         # Foreign issuers
    "6-K/A",       # NEW — foreign current report amendment

    # Proxy materials
    "DEF 14A", "PRE 14A", "DEFA14A", "DEFM14A",
    "DEF 14C",     # NEW — information statement (no vote required)
    "DEFR14A",     # NEW — definitive revised proxy
    "PREM14A",     # NEW — preliminary merger proxy
    "PREC14A",     # NEW — preliminary revised consent solicitation

    # Prospectus supplements
    "424B1", "424B2", "424B3", "424B4", "424B5",

    # Annual reports and notices
    "ARS", "NT 10-K", "NT 10-Q",

    # Tender offers
    "SC TO-I", "SC TO-T",
    "SD",          # Specialized disclosures
    "PX14A6G",

    # Investment company forms
    "N-CSR",
    "N-CSR/A",     # NEW — certified shareholder report amendment
    "N-CSRS",      # NEW — semi-annual certified shareholder report
    "N-CSRS/A",    # NEW — semi-annual certified shareholder report amendment
    "N-Q",
    "N-Q/A",       # NEW — quarterly schedule of holdings amendment
    "N-MFP",       # Money market funds
    "N-CEN",       # Investment company census
    "N-1A",        # NEW — open-end fund registration
    "N-1A/A",      # NEW — open-end fund registration amendment
    "N-2",         # NEW — closed-end fund registration
    "N-2/A",       # NEW — closed-end fund registration amendment
    "N-14",        # NEW — fund merger/reorganization registration
    "N-14/A",      # NEW — fund merger registration amendment
    "N-PX",        # NEW — annual proxy voting record
    "N-8A",        # NEW — notification of registration (Investment Company Act)
    "485APOS",     # NEW — post-effective amendment (auto-effective)
    "485BPOS",     # NEW — post-effective amendment (immediate)
    "497",         # NEW — definitive materials (fund prospectus supplements)
    "497K",        # NEW — summary prospectus

    # Broker-dealer and transfer agent
    "X-17A-5", "17-H",
    "TA-1", "TA-2",
    "ATS-N",

    # Corporate disclosures
    "EFFECT", "FWP", "425", "CB",
    "POS AM", "CORRESP", "UPLOAD",
    "NO ACT",      # NEW — no-action letter
}
```

### Why these additions matter

| Category | Forms added | Impact |
|----------|-------------|--------|
| Small business reports | `10-KSB`, `10-KSB/A`, `10-QSB`, `10-QSB/A` | ~15,000 entities used these pre-2008 forms. Without them, small companies that only filed SB variants are missed by the forms check. |
| Amendments (`/A` variants) | `20-F/A`, `40-F/A`, `11-K/A`, `8-K/A`, `6-K/A` | Entities that amended filings but whose original form was purged from the recent-filings window. The amendment is the only remaining evidence. |
| Additional proxy forms | `DEF 14C`, `DEFR14A`, `PREM14A`, `PREC14A` | Companies using consent solicitations or revised proxies instead of standard DEF 14A. |
| Investment company registration | `N-1A`, `N-2`, `N-14`, `N-8A`, `485APOS`, `485BPOS`, `497`, `497K` | Mutual funds and ETFs that register via these forms. Without them, funds without N-CSR/N-CEN filings in the recent window are missed. |
| Investment company amendments | `N-CSR/A`, `N-CSRS`, `N-CSRS/A`, `N-Q/A` | Semi-annual reports and amendments for investment companies. |
| Proxy voting records | `N-PX` | Annual proxy voting disclosure required of all registered investment companies. |
| No-action letters | `NO ACT` | Companies requesting SEC staff guidance. Only companies request no-action letters. |

---

## Migration Notes

- The `insiderTransactionForIssuerExists` and `insiderTransactionForOwnerExists` fields need to be parsed from the SEC submission JSON and exposed as properties on `EntityData`. They are present in every submission file.
- The name heuristic function and keyword constants can live in `edgar/entity/constants.py` alongside `COMPANY_FORMS`.
- The `is_individual_from_json` function in `company_dataset.py` should be updated to match the new logic and share the same constants.
- These changes are backward-compatible at the API level — `is_individual` remains a `bool` property. Some entities will change classification, which downstream consumers should be aware of.
