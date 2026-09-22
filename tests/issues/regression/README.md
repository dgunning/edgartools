# Regression Tests

Regression tests for specific bugs, so that once we fix one it stays fixed.
251 files live here.

The rules below are enforced by CI, not by convention. Each one exists because
this directory previously failed in that exact way.

## The one rule

**A regression test either runs or it fails.** Everything else follows from it.

A test that skips, xpasses, or asserts something that cannot be false is not
covering the bug it names — and it reads, from the directory listing, as though
it is. That is worse than having no test, because it stops anyone from writing
a real one.

## Automatic marking

Tests here are marked `regression` automatically by `tests/conftest.py`. Do not
add `@pytest.mark.regression` yourself.

The same hook also assigns the marker that decides **where your test runs**, and
this is the part worth reading:

| Your test | Marker | Where it runs |
|---|---|---|
| Runs offline (default) | `fast` | **Every pull request** |
| Needs SEC | `network` | Post-merge and weekly only |

**Unlisted means `fast`, deliberately.** A new test that needs the network and
does not say so fails the pull-request gate on its first run — loud, and one
entry from fixed. Defaulting the other way would file it silently into the
post-merge-only tree, which is the defect this classification exists to close.

If your test genuinely needs SEC, add it to `REGRESSION_NETWORK_FILES` (whole
file) or `REGRESSION_NETWORK_TESTS` (single test) in `tests/conftest.py`. Prefer
the per-test set when only some tests in a file need the network — it keeps the
offline ones gating pull requests.

To find out which you have, measure rather than guess:

```bash
hatch run test-offline-audit tests/issues/regression/test_issue_XXX.py
```

That blocks outbound sockets, clears the functools caches and pops local
storage, so a pass means the test really is offline. A warm HTTP cache will
otherwise make a network-dependent test look fast.

## CI

Regression tests are **not** excluded from the main pipeline. They were until
`edgartools-07lk.21`, and this README said so for a long time after it stopped
being true.

- **Pull requests** — `test-fast` runs `-m 'fast'`, with no regression
  exclusion. Every `fast` test here gates every PR.
- **`network` / `slow`** — still held out of the PR lanes
  (`-m 'network and not slow and not regression'`).
- **Regression Tests workflow** — the whole tree, on pushes to `main` touching
  `edgar/**` or this directory, weekly on Sundays, and on demand. When it goes
  red it opens a tracking issue.

## Naming

```
test_issue_<issue_number>_<short_description>.py
```

For bugs with no GitHub number, the beads ID stands in
(`test_issue_v3ec_two_up_maturity_rows.py`).

## Provenance — enforced

Every file here names its origin **in the module docstring**, as one of:

```
GitHub Issue: https://github.com/dgunning/edgartools/issues/<n>
GitHub PR:    https://github.com/dgunning/edgartools/pull/<n>
Bead:         edgartools-<id>
```

`scripts/check_regression_provenance.py` runs as a step in `test-fast` and fails
the build otherwise. A bare `#819` in prose does **not** satisfy it, deliberately:
109 files named their issue that way and nothing else, in four different shapes
(`GH #812`, `GitHub issue #488`, `issue #762`, `#819`), which no tool could
follow. One canonical form makes "which of these bugs are still open?" a script
instead of a reading exercise.

The filename is not accepted as the answer either. It usually carries the number,
but 67 files here are named after a beads slug and 9 are free-form, so it answers
for part of the tree and silently not the rest.

If you cannot find the origin of an existing file, `git log --reverse -- <file>`
names the commit that added it, and its pull request or bead ID is the answer —
that is how the last four in this tree were traced.

## Writing one

```python
"""
Regression test for GitHub issue #XXX: Brief description

<What broke, and what the user saw. Name the company, form and period.>

GitHub Issue: https://github.com/dgunning/edgartools/issues/XXX
"""

from tests._offline_filings import offline_filing

# AAPL FY2024 10-K, filed 2024-11-01. Read off the filing by hand, once:
# this is the figure the bug got wrong.
AAPL_FY2024_10K = "0000320193-24-000123"
EXPECTED_REVENUE = 391_035_000_000


def test_revenue_matches_filed_figure():
    xbrl = offline_filing(AAPL_FY2024_10K).xbrl()
    df = xbrl.statements.income_statement().to_dataframe()

    row = df[df["concept"] == "us-gaap_RevenueFromContractWithCustomerExcludingAssessedTax"]
    assert not row.empty, f"revenue concept missing; got {sorted(df['concept'].unique())[:20]}"

    # Note the " (FY)" suffix — period columns are not bare dates.
    revenue = row.iloc[0]["2024-09-28 (FY)"]
    assert revenue == EXPECTED_REVENUE, (
        f"AAPL FY2024 revenue should be {EXPECTED_REVENUE:,}, got {revenue:,}"
    )
```

That example is a passing test, not a sketch — including the `(FY)` suffix,
which is not guessable and which cost a debugging session once already. Dump
`list(df.columns)` before you write a column name.

**Assert the value, not its existence.** `assert revenue is not None` passes
against a wrong number, which is the failure mode most of these bugs actually
had. There are 463 such assertions across 125 files here, and they are the
standing cleanup job for this tree.

That number went up, not down, when the `pytest.skip()` calls were converted —
a skip became `assert x is not None` plus the reason it should hold. That was
the right trade (a skip cannot fail; a weak assertion can) but it is a rung on
the ladder, not the top of it. When you touch one of these files, replace the
existence check with the figure from the filing.

**Pin the filing.** `Company("AAPL").get_financials()` follows whichever 10-K is
newest, so a hand-checked value silently stops being the right answer when the
company files again. `tests/_offline_filings.py` builds a `Filing` from a frozen
accession without downloading the 30 MB quarterly index.

**Say why the test exists.** A year from now the assertion is the only record of
what the bug was.

### Three things CI will reject

**`pytest.skip()` — never, anywhere in this tree.** Enforced by
`scripts/check_regression_skips.py`, which runs as a step in `test-fast`. A skip
here converts "the bug is back" into a green run. The two shapes that look like
exceptions are not: a missing committed fixture means a broken checkout, which
belongs in the failure report, and a missing *dependency* is what
`@pytest.mark.skipif` is for — the gate ignores that by design.

If the data you need is absent, that absence is usually the bug. Assert on it:

```python
assert income_stmt is not None, (
    "DNUT should have an annual income statement covering FY2023"
)
```

**Stale `xfail`.** `xfail_strict = true`, so an `xfail` that starts passing
fails the build. When you fix the bug, delete the marker.

**A test with no assertion.** A `pass` body, a bare `print()`, or `return True`
instead of `assert`. `tests/issues/reproductions/` accumulated 137 files
yielding 54 tests this way before it was pruned.

## Running them

```bash
hatch run test-regression                      # the whole tree
hatch run pytest tests/issues/regression -m fast   # just the PR-gating subset
python scripts/check_regression_skips.py       # the no-skip gate
python scripts/check_regression_provenance.py  # the provenance gate
```

## Before you delete one

"This file has zero unique coverage" is a measurement, not a hunch, and
`scripts/coverage_attribution.py` is how you make it:

```bash
COVERAGE_FILE=/tmp/attrib.coverage \
  hatch run pytest -m fast -n auto --cov=edgar --cov-context=test --cov-report=
hatch run python scripts/coverage_attribution.py /tmp/attrib.coverage
```

Read its docstring before acting on the output. Two things it will not tell
you:

- **Zero unique coverage does not mean worthless.** A regression test's job is
  pinning a specific value on specific data, not reaching new lines. It marks a
  file as a candidate for *consolidation*, never for silent deletion.
- **It says nothing about runtime.** The eight largest zero-unique files were
  once read as the ones re-parsing the same big filings; measured, they shared
  0.59s of redundant parsing between them. Measure parse cost separately.

---
*Once we fix a bug, it stays fixed — and the test that proves it actually runs.*
