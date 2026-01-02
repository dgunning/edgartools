# End-to-end plan: sector-aware learning → virtual trees → standardized `map.json`

This plan produces:

* **Global canonical** + **industry canonical trees** (with per-industry occurrence)
* A **core** `map.json` that standardizes concepts across **any SEC filer**
* Optional **industry overlays** for sector-specific lines (banks, insurance, utilities, etc.)

---

## Step 0 — Expand industries and cohorts (configuration)

### File: `__init__.py`

**Goal:** expand and refine `INDUSTRIES` so you don’t dilute bank concepts.

**Changes**

1. **Add more financial cohorts** instead of one big “Banks”:

   * `commercial_banks` (keep 6020–6029)
   * `thrifts_savings` (6030–6036-ish)
   * `consumer_finance` (6141, etc.)
   * `broker_dealers` / `securities` (62xx)
   * `insurance` (63xx)
2. Add/adjust `default_threshold` per cohort (banks typically lower than industrials):

   * global default can remain higher (e.g., 0.30)
   * cohort default can be lower (e.g., 0.10–0.15)
3. Keep SIC ranges as a list, not a single tuple, to support **multi-range cohorts** cleanly.

**Outcome**

* You can run learning per cohort and get strong bank-specific concept coverage without global dilution.

---

## Step 1 — Make “industry learning” produce full canonical trees (no dependency)

### File: `run_industry_learning.py`  *(modify and/or replace with `run_industries_learner.py`)*

**Goal:** generate **canonical virtual trees per industry** (not just “extensions”), and do **not depend on `run_learning.py` output**.

**Changes**

1. **Remove dependency on** `load_virtual_trees()` and “canonical exclusion” logic.

   * Instead, each industry run builds its own canonical tree from scratch.
2. **Compute occurrence within the cohort**:

   * `occurrence_rate_industry = companies_with_concept / successful_companies_in_cohort`
3. **Build hierarchy properly**:

   * Populate `children` by inverting `parent` relationships after concept selection.
4. **Output file naming**:

   * `virtual_trees_<industry>.json`
   * `learned_mappings_<industry>.json`
   * `learning_summary_<industry>.json`

**Outcome**

* You get a clean, complete industry tree (banks look like banks).

---

## Step 2 — Keep a global canonical run (but integrate it into the new workflow)

### File: `run_learning.py`  *(modify)*

**Goal:** run **global learning** across exchanges, and optionally run for a specific industry or SIC range.

**Changes**

1. **Support multiple exchanges**:

   * Add CLI: `--exchanges NYSE,Nasdaq`
   * Implement: loop exchanges → merge tickers → sample from combined pool.
2. **Support industry sampling directly**:

   * Add CLI:

     * `--industry banking` *(uses SIC ranges from `INDUSTRIES`)*
     * and/or `--sic-range 2834,2836`
   * Implement selection with:

     ```python
     CompanySubset(use_comprehensive=True).from_industry(sic_range=(...)).sample(n).get()
     ```
3. **Support curated lists (critical for banks)**:

   * Add CLI:

     * `--tickers`
     * `--tickers-file`
4. **Output tagging**:

   * Add CLI: `--tag global` / `--tag banks`
   * Writes `virtual_trees_<tag>.json` etc.

**Outcome**

* One command can generate a strong global canonical baseline.
* You can also run “global-but-financials-only” if needed.

---

## Step 3 — Add sector-level occurrence (global + industry in one unified dataset)

### New file: `merge_virtual_trees.py`

**Goal:** merge global + industry trees so each concept node can carry:

* `occurrence_rate_global`
* `occurrence_rate_by_industry: { banking: 0.72, ... }`

**What it does**

1. Load `virtual_trees_global.json`
2. Load all `virtual_trees_<industry>.json`
3. Merge nodes by `concept` (local name), preserve:

   * label (prefer global unless missing)
   * parent/children (prefer industry structure for industry file)
4. Emit:

   * `virtual_trees_merged.json` (global tree + per-industry occurrence metadata)
   * also keep the per-industry JSONs intact

**Outcome**

* Your mapping builder can use a single “truth file” for concept frequency everywhere.

---

## Step 4 — Build standardized `map.json` from learned trees

### New file: `build_map_schema.py`

**Goal:** generate/maintain a **comprehensive** `map.json` for SEC filers.

**Inputs**

* `virtual_trees_merged.json` (or global + industry trees)
* an internal “field spec” definition for your standardized labels:

  * `revenue, cogs, grossIncome, opex, sga, r&d, interestExpense, pretax, taxes, netIncome, ebit`

**Logic**

1. For each standardized field:

   * Rank candidate concepts by:

     * `occurrence_rate_global`
     * and if industry context is provided, boost by `occurrence_rate_by_industry[industry]`
2. Use tree metadata to avoid wrong mappings:

   * Prefer `is_total=true` for subtotals (pretax, netIncome, operating income)
   * Avoid `is_abstract=true` for numeric fields
3. Add sector rules where needed:

   * Banks:

     * `revenue = InterestIncomeExpenseNet + NoninterestIncome` (fallback)
     * `totalOperatingExpense = NoninterestExpense`
     * `ebit = pretaxIncome`
   * Insurance/REIT/Utilities: prefer their known revenue/expense patterns
4. Emit:

   * `map_core.json` (us-gaap + ifrs-full only)
   * `map_overlays/<industry>.json` (optional; adds industry-specific concepts/compute)

**Outcome**

* A data-driven, self-updating mapping that improves as your learning corpus grows.

---

## Step 5 — Apply mapping to filings (standardization pipeline)

### File: `is_coremap.py` *(already provided earlier; keep using)*

**Goal:** extract statement facts via EdgarTools, then apply `map_core.json`.

**Changes (if needed)**

1. Add optional overlay loading:

   * `--industry banking` → auto-load `map_overlays/banking.json` if present
2. Ensure concept normalization remains robust:

   * store both `us-gaap:Revenues` and `us-gaap_Revenues` variants in `facts`

**Outcome**

* Your standardized output works for AAPL, BAC, and most SEC filers with minimal per-company hacks.

---

# Execution order (recommended)

1. **Global canonical**

   * `python run_learning.py --exchanges NYSE,Nasdaq --companies 500 --min-occurrence 0.10 --tag global`
2. **Industry canonicals**

   * `python run_industries_learner.py --industry banking --companies 200 --min-occurrence 0.10`
   * repeat for other cohorts
3. **Merge**

   * `python merge_virtual_trees.py --global virtual_trees_global.json --industries ./industries/*`
4. **Build mapping**

   * `python build_map_schema.py --trees virtual_trees_merged.json --out map_core.json`
5. **Standardize any filing**

   * `python is_coremap.py --symbol bac --mapping map_core.json --industry banking --identity "Name email"`

---

# Summary of files you will modify / add

## Modify

* `__init__.py` — expand `INDUSTRIES`, add financial cohorts, adjust thresholds
* `run_learning.py` — multi-exchange, industry/sic selection, tickers-file, tagging
* `run_industry_learning.py` (or rename to `run_industries_learner.py`) — generate full industry canonical trees (not extensions), build children, output per-industry trees

## Add

* `merge_virtual_trees.py` — merge global + industry trees; attach per-industry occurrence
* `build_map_schema.py` — generate `map_core.json` + optional overlays from merged trees

