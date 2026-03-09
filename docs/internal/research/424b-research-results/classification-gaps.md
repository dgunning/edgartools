# 424B Classification Gaps & Improvement Opportunities

**Date**: 2026-03-09
**Context**: After Phase 1-2 implementation, ran 50-filing sample (10 per form) to assess real-world accuracy.

---

## Current Accuracy by Form (10-filing sample each)

| Form | Classified | Notes |
|------|-----------|-------|
| 424B2 | 100% | All structured notes — dominant form by volume (~92%) |
| 424B4 | 100% | Fixed after adding IPO/SPAC prose patterns |
| 424B5 | 90% | 1 unknown — needs investigation |
| 424B1 | 62% | 3 unknowns out of 8 filings |
| 424B3 | 40% | 6 unknowns out of 10 — most heterogeneous form |

## Known Weaknesses

### 424B3 — 40% classification (worst performer)

424B3 is the most heterogeneous form type. It covers:
- PIPE resale (selling stockholders)
- Rights offerings
- Exchange offers
- Shelf registration resale
- Warrant exercise resale
- Merger/acquisition share registration

The classifier currently catches PIPE resale and rights offerings well, but misses:
- **Shelf resale without "selling stockholder"**: Some 424B3s register resale of shares but use different terminology (e.g., "registered holders", "security holders")
- **Warrant exercise registrations**: Shares issuable upon exercise of warrants, not a traditional resale
- **Merger consideration shares**: Shares issued as merger consideration, registered for resale
- **General resale prospectuses**: Broad resale registrations without clear PIPE indicators

### 424B1 — 62% classification

424B1 is typically used for exchange offers and some firm commitments. Gaps:
- **Non-standard exchange offers**: Some 424B1s describe exchange offers without the phrase "offer to exchange"
- **Firm commitment without standard pricing table**: Some IPO-style 424B1s lack the tabular pricing format

### 424B5 — 90% classification

Generally well-covered (ATM, debt, best efforts), but:
- **Mixed offering types**: Some 424B5s combine ATM with shelf takedown features
- **Convertible notes**: May not match debt_offering patterns if they emphasize conversion rather than coupon rate

## Fixes Applied (2026-03-09)

These fixes brought 424B4 from 0% → 100%:

1. **IPO/SPAC prose patterns for firm_commitment**: Added `ipo_text`, `underwriter_option_text`, `prose_price`, `overallotment_underwriter` signals — SPAC 424B4s use prose like "has a price of $10.00" instead of tabular "public offering price $X.XX"
2. **Hyphenated "best-efforts"**: Changed `find('best efforts')` to `re.search(r'best[- ]efforts')` to catch "best-efforts basis"
3. **"selling shareholder" variant**: Added alongside "selling stockholder" for pipe_resale detection
4. **Direct listing resale**: Added `direct_listing_resale_cover` signal for direct listing prospectuses (e.g., FreeCast)

## Improvement Strategy

Priority improvements to increase overall accuracy:

1. **424B3 resale broadening** (highest impact): Expand pipe_resale detection to catch more resale variants — look for "resale" + "no proceeds" combo even without "selling stockholder"
2. **424B3 sub-type detection**: Add warrant exercise, merger consideration, and shelf resale as recognized sub-types
3. **424B1 exchange offer broadening**: Look for additional exchange offer indicators beyond "offer to exchange" (e.g., "exchange ratio", "exchange consideration")
4. **Fallback heuristics**: For filings that match no category, use form-type priors (e.g., 424B3 with "resale" anywhere → likely pipe_resale at medium confidence)
