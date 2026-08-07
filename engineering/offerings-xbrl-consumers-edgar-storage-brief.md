# 424B Offerings — EX-FILING-FEES Consumers: Brief for edgar-storage

**Audience:** the edgar-storage backfill that builds offering datasets from
edgartools data objects.
**Purpose:** document what changed in the 424B offering surface, what to
consume, and — critically — the **coverage ceilings and confidence tiers** so
the dataset is built on the right trust assumptions.
**Status:** merged to `main` (post-5.38.0; ships in the next release). Commits
`f30d5bf7`, `871af8ef`, `6feacaac`, `9848bf89`. Origin: the edgar-storage
offerings deep read (beads edgartools-s9uo / 2l2i / ejk5, now closed).

---

## 1. What changed (one sentence)

The parsed EX-FILING-FEES inline-XBRL exhibit on `Prospectus424B.filing_fees`
was a dead-end accessor; it is now wired into deal-sizing and offering-type
classification, an `ipo` type was added, and the exhibit parser moved to lxml.

---

## 2. The API surface to consume

All via `filing.obj()` → `Prospectus424B`, then `.deal` / `.offering_type` /
`.filing_fees`.

| Field | What it now does | Source priority |
|---|---|---|
| `deal.gross_proceeds` | Total offering amount (gross) | cover (if ≥ $100k) → **`ffd:TtlOfferingAmt`** → pricing table → shares×price |
| `offering_type` | `OfferingType` enum, now incl. `IPO` | text cascade → **XBRL security-type fallback** before `unknown` |
| `filing_fees.total_offering_amount` | Authoritative `ffd:TtlOfferingAmt` (str) | parsed iXBRL |
| `filing_fees.offering_rows[].security_type` | `ffd:OfferingSctyTp` (Debt/Equity/Other/…) | parsed iXBRL |

`OfferingType` members now: `firm_commitment, ipo, atm, best_efforts,
pipe_resale, rights_offering, exchange_offer, structured_note, debt_offering,
base_prospectus_update, unknown`.

---

## 3. Coverage ceilings — measured, not aspirational

The EX-FILING-FEES exhibit is the authoritative source, but it **only exists
for a minority of filings**. Measured over a 3-year sample (424B* excl 424B2):

- **Universe:** ~50,577 filings (2023–2025).
- **iXBRL exhibit present:** ~16.5% (~8,300). Post-2022 only (SEC Rule 408);
  ~0% for 424B1/424B4; none for ATMs (no fixed amount exists by nature).
- **`deal.gross_proceeds` realistic ceiling: ~40–50% non-null**, up from a
  measured ~23.5% baseline. The remainder is structural: ATMs, pre-2022
  takedowns, and 424B1/B4 IPOs that carry no exhibit. **Do not expect the null
  tail to disappear — it is SEC filing behavior, not a library gap.**

**Build the dataset to tolerate nulls as a first-class state, not an error.**

---

## 4. Confidence tiering — DO NOT treat all values as equal

Tag every consumed value by provenance; the new signals are deliberately
tiered:

- **High trust** — anything sourced from `filing_fees` (`ffd:TtlOfferingAmt`,
  `ffd:OfferingSctyTp`). Machine-readable, regex-free, effectively ground truth.
  `deal.gross_proceeds` that came from XBRL is high trust.
- **Medium** — `debt_offering` derived from XBRL security type (`Debt` is
  unambiguous); the text cascade's `high`-confidence classifications.
- **Low — handle with care:**
  - `offering_type == firm_commitment` with confidence `low` and signal
    `xbrl_security_type:equity`. This is a **weak prior**: an unlabelled resale
    (issuer receives *no* proceeds) can land here. **If you sum
    `gross_proceeds` as issuer capital raised, exclude or separately bucket
    low-confidence firm_commitment rows**, or you will double-count resales.
  - `rights_offering` with signal `xbrl_security_type:rights`.

**Where to read the provenance (public API, no private access needed):**

| Accessor | Type | Notes |
|---|---|---|
| `prospectus.offering_type_confidence` / `deal.offering_type_confidence` | `str` | `'high' \| 'medium' \| 'low'` |
| `prospectus.offering_type_signals` / `deal.offering_type_signals` | `list[str]` | incl. `xbrl_security_type:*` markers |
| `prospectus.offering_type_sub_type` | `str \| None` | e.g. `'equity_resale'` |

`deal.to_dict()` emits `offering_type_confidence` and `offering_type_signals`
(the latter omitted when empty) — wire these straight into the schema 1.2
provenance columns. Signals prefixed `xbrl_security_type:` mark that the
structural fallback fired. The §4 exclusion rule is then a one-liner:
`if confidence == 'low' and 'xbrl_security_type:equity' in signals: don't sum as
issuer proceeds`.

---

## 5. Deal-size artifact handling (the $1,000 problem)

The cover-page regex used to grab a per-note **denomination** ($1,000) as the
deal size. Calibration (`scripts/offerings_bench/calibrate_floor.py`):

- ~5% of 424B2 had a cover deal size of **exactly $1,000** (artifact).
- The `(1k, 100k]` band is empty; legitimate deals are all ≥ $100k.
- A `$100k` plausibility floor (`_MIN_PLAUSIBLE_DEAL_SIZE`) now **nulls** these,
  except the ~10% that carry a fee exhibit, where the XBRL total **recovers the
  real value** (e.g. one $1,000 artifact → its true $500k).

Consequence for the backfill: deal sizes below $100k no longer appear; an old
extract with `$1,000`/`$2,000` deal sizes should be **re-run**, not reconciled.

---

## 6. The `ipo` dimension (net-new)

- `OfferingType.IPO` is emitted only for 424B1/424B4 whose cover **asserts**
  "this is an initial public offering" (not a follow-on referencing a past IPO).
- Precision is the priority; **recall is partial** — the S-1/F-1 base-form
  linkage that would catch IPOs with non-standard phrasing was deferred (it
  needs a related-filings lookup). An IPO tape built on this will be clean but
  not exhaustive.
- Sample check (40× 424B4, 2025Q2): 10 `ipo`, 11 `firm_commitment` (the
  follow-ons), 19 other.

---

## 7. Performance / cost notes for a backfill

- **Parser:** EX-FILING-FEES parsing moved to lxml — ~15× faster per exhibit
  (0.32 ms). But parse is **not** the backfill bottleneck; ~8,300 exhibits parse
  in ~3 s total. **Network/download dominates** — use a local edgar-storage
  mirror and download concurrency, not parser tuning, to cut wall-clock.
- **`deal.gross_proceeds` and `deal.shares` are no longer network-free** — they
  reach `filing_fees` (an exhibit download) when the cover is missing/implausible
  (ATMs, debt notes). Budget for it when iterating deals in bulk.
- The fee exhibit is fetched **at most once** per filing (classification reuses
  it for the `filing_fees` cache), so accessing both costs one download.

---

## 8. What is NOT fixed (so you don't wait for it)

- The `unknown` offering-type tail is reduced, not eliminated — only the slice
  of unknowns that *also* carry a fee exhibit is rescued.
- `equity → firm_commitment` does not distinguish resales (see §4).
- No backfill of pre-2022 filings' deal size — no exhibit exists.
- The exhibit parser itself (`_424b_xbrl.py`) is lxml now, but the other
  offerings parsers (`drs.py`, `formd.py`, `formc.py`, `_fee_table.py`) remain
  BeautifulSoup — out of scope here.
