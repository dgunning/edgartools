---
description: Catch the right thing when SEC data is missing, unreachable, or unparseable. The edgartools exception hierarchy, and what None means.
---

# Handling Errors

There are only two questions you ever need to ask about a failed edgartools call, and the exception tree is shaped around them:

**Did we get an answer from SEC, or not?** An outage is not an empty result. If you cannot tell those apart, a maintenance window looks exactly like a company that has never filed.

**Was the problem your input, or the data?** A typo'd ticker and a filing we could not parse need different fixes from you.

## The tree

```text
EdgarError                  everything below is one of these
├── TransportError          we could not get an answer from SEC
├── NotFoundError           you named a thing and it does not exist
├── ParsingError            we got the bytes and could not build the object
└── ValidationError         your input was wrong before we ever asked
```

```python
from edgar import Company
from edgar.exceptions import EdgarError, NotFoundError, TransportError

try:
    company = Company("AAPL")
    financials = company.get_financials()
except TransportError as e:
    # We never got an answer. Retry later — the data may be fine.
    print(f"SEC unreachable: {e}")
except NotFoundError as e:
    # SEC answered, and there is no such thing. Retrying will not help.
    print(f"No such company: {e}")
except EdgarError as e:
    # The outer net. Anything edgartools raises is one of these.
    print(f"Unexpected: {e}")
```

Catch the branch, not the leaf. `except NotFoundError` covers a missing company, filing, statement, section and attachment; you rarely need `CompanyNotFoundError` specifically, and naming the branch means new leaf types do not slip past your handler.

### Do not catch httpx types

You may have written `except httpx.ReadTimeout` around an edgartools call, because that is what used to come out. It worked by accident: a dependency's exception was reaching you through our public surface, which meant any change to how we make HTTP requests was a breaking change for your code.

`TransportError` is ours, and it is what you should catch:

```python
from edgar.exceptions import TransportError

try:
    filings = company.get_filings(form="10-K")
except TransportError as e:
    if e.status_code is None:
        print("Never reached SEC — connection, DNS or timeout")
    elif e.status_code == 429:
        print("Rate limited. Wait ~10 minutes; do not retry immediately")
    else:
        print(f"SEC answered {e.status_code} for {e.url}")
```

`status_code is None` is the meaningful distinction: it means we never got an HTTP answer at all. The original httpx exception is still on `e.__cause__` if you need it while debugging.

`TransportError` also covers the rate limiter (`TooManyRequestsError`), TLS problems (`SSLVerificationError`) and a missing identity (`IdentityNotSetError`) — all of which mean "no answer from SEC", however different their causes.

## What `None` means

**`None` never means a failure.** Where a call can legitimately answer "there is no such thing", it returns `None` and its docstring names the exact condition that produces it. Everything else raises.

```python
# A probe. None means this filing genuinely has no XBRL — many do not.
xbrl = filing.xbrl()
if xbrl is None:
    print("no XBRL in this filing")

# The same call during an SEC outage does NOT return None. It raises
# TransportError, so you can tell "no XBRL" from "we could not look".
```

The rule, if you are reading our source or writing a handler:

| You asked | Absence is | Failure is |
|---|---|---|
| for a specific named thing (`filing["Item 7A"]`, `Company("AAPL")`) | a `NotFoundError` | a raise |
| whether something exists (`filing.xbrl()`, `company.get_financials()`) | `None`, documented | a raise |

## Migrating before 6.0

A few calls still return `None` for something that is really a failure. Each of them now emits a `FutureWarning` naming what it will raise in 6.0:

| Call | Today | edgartools 6.0 |
|---|---|---|
| `tenk["Item 99"]` (no such item) | warns, returns `None` | raises `SectionNotFoundError` |
| `find("123456-99")` (malformed accession) | warns, returns `None` | raises `ValidationError` |
| `filing.obj()` on a modelled form with unreadable data | warns, returns `None` | raises `DataObjectError` |
| `tenk.document` when the parser fails | warns, returns `None` | raises the parser's `ParsingError` |
| any httpx failure out of the network layer | propagates as an httpx type | raises `TransportError` |

Where the raising form is the only form, there is now a non-raising one beside it. `report.get(item, default)` is to `report[item]` what `dict.get` is to `dict[...]`, and it never warns:

```python
tenk = filing.obj()

tenk["Item 7"]                      # the item you expect; raises in 6.0 if absent
tenk.get("Item 16", "")             # the item that may not be there
```

### If you process filings in bulk

Each of these warns **once per line of your code, not once per filing** — Python suppresses the repeats. A loop over ten thousand 10-Ks where some omit the item you asked for produces one warning, not ten thousand. The detail about *which* filing (and what items it does have) is on the exception rather than in the warning, so you see it when you turn strict mode on:

```bash
EDGARTOOLS_STRICT_ERRORS=1 python your_script.py   # raises, with the accession named
```

If an absent item is a normal outcome for your corpus rather than a problem, `report.get(item, default)` is the call you want — it is silent by design, today and in 6.0.

### Get the 6.0 behaviour now

Set `EDGARTOOLS_STRICT_ERRORS=1` and every row of that table raises today. Run your test suite with it to find out what breaks while there is still a 5.x release to fix it in:

```bash
EDGARTOOLS_STRICT_ERRORS=1 pytest
```

```python
from edgar.exceptions import strict_errors_enabled

strict_errors_enabled()   # True when the variable is set
```

We run our own suite this way in CI, for exactly the same reason.

## Writing errors that help

Every `EdgarError` carries optional structured detail, and `str(exc)` renders it:

```python
from edgar.exceptions import SectionNotFoundError

try:
    tenk["Item 99"]
except SectionNotFoundError as e:
    print(e.message)        # the one-line statement of what went wrong
    print(e.context)        # {'requested': 'Item 99', 'available': [...]}
    print(e.suggestions)    # what to do about it
```

## Deprecated names

Older exception names still resolve to the same objects, so `except StatementNotFound:` keeps working. They emit a `DeprecationWarning` and are removed in 6.0.

| Old | New |
|---|---|
| `StatementNotFound` | `StatementNotFoundError` |
| `NoCompanyFactsFound` | `CompanyFactsNotFoundError` |
| `SECFilingNotFoundError` | `FilingNotFoundError` |
| `InvalidDateException` | `InvalidDateError` |
| `IdentityNotSetException` | `IdentityNotSetError` |
| `TooManyRequestsException` | `TooManyRequestsError` |
| `DataObjectException` | `DataObjectError` |

## See also

- [Common Pitfalls](../common-pitfalls.md)
- [Upgrading to 6.0](../upgrade/6.0.md)
