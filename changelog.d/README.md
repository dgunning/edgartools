# Changelog fragments

Do not edit `CHANGELOG.md` in a pull request. Add one file here instead:

```
changelog.d/<id>.<section>.md
```

- `<id>`: the bead ID (`xn1u`), issue number (`1244`), or a short slug.
- `<section>`: `added`, `changed`, `deprecated`, `removed`, `fixed`, `security`, or `performance`.
- Body: the bullet text exactly as it should appear in the changelog, e.g.
  `**A statement whose columns are not dates lost every column.** A column was kept only if ...`
  The leading `- ` is optional.

At release time `python scripts/release/assemble_changelog.py` folds every fragment into
`[Unreleased]` and deletes it. `--check` validates and previews without changing anything.

Why: every PR used to insert a bullet at the same line of `CHANGELOG.md`, so any two open
PRs conflicted and each merge forced a conflict fix plus another CI run on every other PR.
A new file per PR never conflicts, and a fragment can only ever land in the *next* release,
which also removes the stale-branch trap where a bullet merged into an already-shipped section.
