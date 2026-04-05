# S&P 100 Financial Database Expansion

## Overview
Scale from 56 companies to full S&P 100 coverage (~44 new companies) using the automated onboarding pipeline.

## Stage 1: GAAP Expansion Regression Validation
**Goal**: Confirm GAAP expansion (already wired in `config_loader.py:138-244`) causes no regressions.
**Status**: Not Started
**Action**: Run full 56-company E2E suite with `snapshot_mode=True`, compare against golden masters.
**Success**: 0 new regressions.

## Stage 2: Canary Onboarding — 3 Companies
**Goal**: Manually onboard HD, V, ABBV using the new pipeline to validate the workflow.
**Status**: Not Started
**Action**:
```bash
python -m edgar.xbrl.standardization.tools.onboard_company --tickers HD,V,ABBV
```
**Success**: 3 companies onboarded with documented pass/fail per metric.

## Stage 3: Build Automated Onboarding Pipeline
**Goal**: CLI tool that takes a ticker and produces draft YAML + validation report.
**Status**: Complete
**Files Created**:
- `edgar/xbrl/standardization/tools/onboard_company.py`
**Verified**: CLI help, dry-run, archetype detection (11/11 SIC codes), YAML generation.

## Stage 4: S&P 100 Batch Onboarding
**Goal**: Onboard all ~44 remaining S&P 100 companies in waves.
**Status**: Not Started
**Waves**:
- Wave 1: Archetype A (Standard Industrial) — ~13 companies
- Wave 2: Archetype C (Tech/SaaS/Pharma) — ~15 companies
- Wave 3: Archetype B/E (Financial/Insurance) — ~5 companies
**Success**: 95%+ pass rate across all S&P 100.

## Stage 5: CI Regression Gate
**Goal**: pytest-based golden master regression checking.
**Status**: Complete (pre-existing)
**Files**: `tests/regression/test_golden_masters.py`
