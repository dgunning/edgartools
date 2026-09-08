# Changelog fragments

Do not edit `CHANGELOG.md` in a pull request. Add one file here instead:

```
changelog.d/<id>.<section>.md
```

- `<id>`: the bead ID (`xn1u`), issue number (`1244`), or a short slug.
- `<section>`: `added`, `changed`, `deprecated`, `removed`, `fixed`, `security`, or `performance`.
- Body: the bullet text exactly as it should appear in the changelog — a bold headline
  naming the user-visible defect, then one or two sentences with **one measured value**,
  then the reference. **At most 500 characters**; the assembler rejects longer ones. The
  root-cause narrative belongs in the commit message and the PR, not here. The leading
  `- ` is optional. Example:

  `**`get_revenue()` returned a component of revenue instead of the filed total.** Contract revenue was tried before `Revenues`, understating Cato's FY2023 top line by $7.7M of other income. The order now matches `Statement.REVENUE_CONCEPTS`. (GH #1294, bead edgartools-y4yp.2)`

At release time `python scripts/release/assemble_changelog.py` folds every fragment into
`[Unreleased]` and deletes it. `--check` validates and previews without changing anything.

Why: every PR used to insert a bullet at the same line of `CHANGELOG.md`, so any two open
PRs conflicted and each merge forced a conflict fix plus another CI run on every other PR.
A new file per PR never conflicts, and a fragment can only ever land in the *next* release,
which also removes the stale-branch trap where a bullet merged into an already-shipped section.
