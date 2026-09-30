## What this changes

<!-- The user-visible behaviour before and after, in a sentence or two. -->

Fixes #

## Verification

<!-- Check what applies and delete what does not. -->

- [ ] **Ground truth**: at least one assertion checks a specific value against a real SEC filing I verified by hand. Filing and accession:
- [ ] **Regression test** for a bug is in `tests/issues/regression/`, and its docstring links the issue or bead
- [ ] **Cassettes** were recorded from live SEC and not edited afterwards (see CONTRIBUTING.md). Recorded on:
- [ ] **Silence check**: bad or missing input produces a useful error, not `None`
- [ ] **Docs**: any documented example this touches still runs
- [ ] **Changelog**: a `changelog.d/<id>.<section>.md` fragment, not an edit to `CHANGELOG.md`

## 6.0

- [ ] This PR adds a deprecation, a 6.0 warning, or a "removed in 6.0" note, and `docs/upgrade/6.0.md` says what users see now and what to do instead

CI fails a PR that stages a 6.0 change without touching the upgrade guide. If it flags something that isn't a 6.0 change, add the `no-upgrade-guide` label, say why here, and re-run the job.

## Working context (optional)

<!--
If you worked with an AI assistant, paste its plan and the evidence it
checked: commands run, values compared, what it ruled out. This isn't a
disclosure requirement. It's the fastest way to get a review, because the
reviewer can start from what you already know.
-->
