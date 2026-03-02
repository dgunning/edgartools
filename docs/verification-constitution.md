# EdgarTools Verification Constitution

A set of principles governing how we verify that EdgarTools delivers on its promises — to humans and agents alike.

## Why "verification" and not "testing"

**Testing** is inward-facing — "does my code work?" **Verification** is outward-facing — "does this library deliver what we promised?" EdgarTools is a data provider. When verification fails, it means someone downstream got wrong financial data. The stakes are categorically different from typical software testing.

---

## The Principles

### I. Documentation is the specification

Every documented behavior is a verifiable claim. The verification suite and the documentation are two expressions of the same truth. If we can't verify it, we don't promise it. If it's in the docs, it must be verified continuously.

### II. Data correctness is existential

We are a data provider first. A verified API that returns wrong numbers is a failure. Verification must assert not just that code runs, but that the *data is right* — against known ground truths from SEC filings.

### III. The user's experience is the unit of verification

We don't verify internal implementation details. We verify what the user sees: the objects they get back, the values in those objects, the errors they encounter. Refactoring internals should never require rewriting verifications.

### IV. The SEC is the upstream we can't control

Filings change format. Taxonomies evolve. EDGAR goes down. Our verification must distinguish between "our code is broken" and "the upstream data changed." Both matter, but they require different responses.

### V. Verification is continuous, not a gate

Verification isn't something that happens before a release. It's a living system that tells us, at any moment, whether our promises still hold. A verification that only runs in CI is a verification that lies to you between pushes.

### VI. Silence is the worst failure mode

Returning `None` where a user expected data, or silently dropping a filing, is worse than raising an error. Verification must catch silent failures — the cases where code "succeeds" but the user gets nothing useful.

### VII. Coverage means breadth of the SEC, not lines of code

100% line coverage with one company's filings is weaker than 60% line coverage across diverse filers, form types, and edge cases. We verify across the *problem space*, not the *code space*.

### VIII. The API must be solvable

Given a real-world question about a public company, a user — human or agent — should be able to go from question to answer using EdgarTools without needing to read the source code. If they can't, that's a design bug, not a user error.

### IX. Spend verification resources where they buy the most confidence

Not all verification is equal in cost or value. Structure verification in tiers so that cheap verification runs constantly, expensive verification runs deliberately, and the boundary between them is a conscious design choice — not an accident of history.

### X. Recorded verification must have an expiry

Every cassette/fixture represents a frozen assumption about upstream data. These assumptions must be periodically re-validated against live sources. A cassette that hasn't been refreshed is a verification that's slowly becoming a lie.

### XI. A feature without verification is incomplete

Every new capability ships with verification proportional to the breadth of its promise. At minimum: one ground-truth assertion, one verified documented example, one silence check. User-facing features additionally require solvability verification — if a human or agent can't find it and use it, it doesn't exist yet.

---

## Verification Tiers

Each tier exists to protect the tier above it from running too often.

| Tier | Cost | Frequency | What it covers |
|------|------|-----------|----------------|
| **0: Static** | Zero | Every keystroke | Types, imports, syntax, object shapes |
| **1: Recorded** | Milliseconds | Every commit | Cassette-based. Known inputs, known outputs. The bulk of contract + data verification |
| **2: Live** | SEC rate limit + time | PR / nightly | Real network calls. Catches upstream drift. Validates cassettes haven't gone stale |
| **3: Evaluation** | LLM API cost | Weekly / milestone | Agent solvability. Can an LLM produce working code for task scenarios? |

## Verification Layers

| Layer | What it verifies | Principles |
|-------|-----------------|------------|
| **Contract** | Documented examples work | I, III |
| **Data** | Values match SEC ground truth | II, IV |
| **Resilience** | Edge cases handled gracefully | IV, VI |
| **Regression** | Fixed issues stay fixed | V |
| **Solvability** | Users and agents can accomplish goals | VIII |

## Definition of Done

For any new user-facing feature:

1. **One ground-truth assertion** — an actual value from a real filing, confirmed by hand
2. **One verified documented example** — the doc example is itself a runnable verification
3. **One silence check** — bad input produces a useful error, not `None`
4. **Solvability** — skills/docs updated so agents can discover and use the feature
