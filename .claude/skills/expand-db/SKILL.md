---
name: expand-db
description: "Expand the Financial Database by onboarding new companies through the automated pipeline. Use when the user says 'expand database', 'onboard companies', or 'add companies to financial database'."
---

# Expand Financial Database

## Overview

This skill orchestrates the expansion of the `FinancialDatabase` by adding new companies through an automated pipeline. It handles onboarding, gap resolution, validation, golden master promotion, and database population.

## When to Use

- User says "expand database to include HD, LOW, MCD"
- User says "onboard SBUX into the financial database"
- User says "add S&P 500 companies to the database"
- User says "check pipeline status" or "show database dashboard"

## How to Use

### 1. Add and Run Companies

```bash
# Add companies to the pipeline
python -m edgar.xbrl.standardization.tools.pipeline_orchestrator add --tickers HD,LOW,MCD

# Run the pipeline (advances each company one step)
python -m edgar.xbrl.standardization.tools.pipeline_orchestrator run --batch HD,LOW,MCD

# Check status
python -m edgar.xbrl.standardization.tools.pipeline_orchestrator status

# Repeat `run` until all companies are COMPLETE or FAILED
```

### 2. Handle Failures

For FAILED companies:
- Check the error with `pipeline status --ticker TICKER`
- If pass_rate >= 50%, use the `concept-mapping-resolver` agent to resolve gaps
- If pass_rate < 50%, report structural issues to the user
- Use `pipeline reset --ticker TICKER` to retry after fixing issues

### 3. View Dashboard

```bash
python -m edgar.xbrl.standardization.tools.pipeline_orchestrator dashboard
```

### 4. Populate Database

```bash
# Populate all COMPLETE companies into FinancialDatabase
python -m edgar.xbrl.standardization.tools.pipeline_orchestrator populate-all
```

## Batch Processing

For large ticker lists, process in batches of 10:

1. Split tickers into groups of 10
2. Add and run each batch
3. Report results after each batch
4. Ask user before continuing to next batch

## Pipeline States

| State | Description |
|-------|-------------|
| PENDING | Added, awaiting processing |
| ONBOARDING | Running onboard_company() |
| ANALYZING | Classifying pass rate and gaps |
| RESOLVING | Running resolve_all_gaps() |
| VALIDATING | Running E2E validation |
| PROMOTING | Promoting golden masters |
| POPULATING | Writing to FinancialDatabase |
| COMPLETE | Done |
| FAILED | Error or max retries exceeded |
