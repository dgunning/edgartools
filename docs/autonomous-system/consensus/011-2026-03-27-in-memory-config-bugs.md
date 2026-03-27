# Consensus Session 011: In-Memory Config Application Bugs

**Date:** 2026-03-27
**Pattern:** Exploratory
**Models:** GPT-5.4 (neutral), Gemini 3.1 Pro (neutral), Claude Opus 4.6 (moderator)
**Continuation ID:** `ba2f82ae-e8f2-4d1c-bd01-29e40d721c42`
**Trigger:** Run 010 showed 100% semantically correct AI proposals but 0% KEEP — root cause traced to broken in-memory config application layer.

## Context

The autonomous XBRL extraction system has a split mutation architecture: `apply_config_change()` writes changes to YAML files on disk (works correctly), while `apply_change_to_config()` applies changes to an in-memory MappingConfig deepcopy for fast pre-screening (broken). Three bugs in the in-memory path cause ALL AI proposals to have zero effect on extraction, producing identical CQS before and after.

This was the final missing link: O1-O6 fixed the pipeline, O7-O9 added value-grounded search, O10-O11 added caching, O12-O14 fixed the compiler, O15-O20 fixed prompt quality. The AI now proposes semantically correct concepts, but the evaluation layer never sees them because the config mutations are silently corrupted.

## GPT-5.4 (Neutral — Practical)

- Confirms all 3 bugs with 9/10 confidence
- Root cause is dual mutation engines (YAML-path disk vs ad-hoc typed in-memory) that drifted
- Bug 1: Use `target_metric` as canonical key — matches `TreeParser.map_metric()` at line 131
- Bug 2: Fix producer (`compile_action`) to emit dict format; also add consumer tolerance for list payloads as defense-in-depth
- Bug 3: Add `known_divergences: Dict` to `CompanyConfig` — don't store in `metric_overrides`
- Review of all 8 change types found: ADD_KNOWN_VARIANCE silently no-ops on missing ticker; REMOVE_PATTERN/MODIFY_VALUE are explicit no-ops in memory
- Recommends `normalize_change()` helper to canonicalize payloads and prevent future drift
- Notes potential latent issue in `evaluate_experiment_in_memory` with `target_tickers` vs `target_tickers_list`
- Recommends round-trip consumption tests

## Gemini 3.1 (Neutral — Robust)

- Confirms all 3 bugs with 9/10 confidence
- **Critical edge case for Bug 1**: Simple assignment (`metric_overrides[metric] = value`) would clobber existing keys like `sign_negate`. Must use `setdefault().update()` instead
- **Widened blast radius**: `FIX_SIGN_CONVENTION` compiles to `ADD_COMPANY_OVERRIDE`, so sign fixes are ALSO silently broken by Bug 1
- Strongly agrees `compile_action` is the strict contract boundary — no polymorphic type-guessing in writers
- Agrees on `known_divergences` as separate CompanyConfig field
- Agrees on `target_metric`/`target_companies` as canonical keys — don't parse `yaml_path` strings
- Recommends parity check: `serialize(apply_in_memory(change)) == apply_on_disk(change)`

## Our Diagnosis

### Agreements (unanimous)

1. **All 3 bugs confirmed** — root cause is dual mutation engines that drifted
2. **Use `target_metric` as canonical key** — both models agree, matches TreeParser consumption
3. **`compile_action` is the contract boundary** — it must produce well-formed payloads, don't add polymorphism to consumers
4. **Add `known_divergences` to CompanyConfig** — separation of concerns between extraction hints and evaluation bypasses
5. **Round-trip consumption tests** — essential to prevent future drift
6. **`FIX_SIGN_CONVENTION` is also broken** — wider blast radius than initially thought (Gemini catch)

### Disagreement + Resolution

**GPT says**: Add consumer tolerance for list payloads (defense-in-depth for Bug 2).
**Gemini says**: No polymorphism in writers — strict contract at compile_action.
**Our resolution**: Side with Gemini. Strict contract at compile_action is cleaner and catches bugs at the source. Adding list tolerance masks the real issue.

**GPT says**: Simple `metric_overrides[target_metric] = change.new_value` for Bug 1.
**Gemini says**: `setdefault().update()` to preserve existing keys like `sign_negate`.
**Our resolution**: Side with Gemini. The `setdefault().update()` pattern is robust against partial overrides and matches how the disk-write path works (merge, not replace).

### What We Learned

The dual-codepath pattern (preview vs commit using different logic) is an anti-pattern that should be avoided in future systems. The root cause was not the specific bugs but the architectural decision to implement in-memory application as a separate set of ad-hoc handlers instead of sharing logic with the disk-write path. Adding new action types will always risk re-introducing this class of bug unless we add contract tests.

## Key Decisions

32. **In-memory config mutations must use `target_metric` as canonical key, not `yaml_path` parsing** — matches TreeParser consumption (Session 011)
33. **`compile_action` is the strict contract boundary** — all action types must emit well-formed dict payloads; consumers are dumb writers (Session 011)
34. **`setdefault().update()` for metric_overrides** — preserves existing keys (sign_negate, etc.) when adding new override properties (Session 011)
35. **Divergences get their own CompanyConfig field** — `known_divergences: Dict[str, Dict]` separates extraction hints from evaluation bypasses (Session 011)
36. **Round-trip consumption tests are mandatory for config mutation code** — prevents future drift between in-memory and disk paths (Session 011)

## Action Items

- [ ] **O21**: Fix Bug 1 — `apply_change_to_config` ADD_COMPANY_OVERRIDE: use `setdefault(target_metric, {}).update(new_value)`
- [ ] **O22**: Fix Bug 2 — `compile_action` ADD_FORMULA: emit `{"scope": scope, "components": components}` not raw list
- [ ] **O23**: Fix Bug 3 — Add `known_divergences: Dict` to CompanyConfig, route ADD_DIVERGENCE there in-memory
- [ ] **O24**: Add warning for ADD_KNOWN_VARIANCE when ticker is missing in new_value
- [ ] **O25**: Raise explicit error for REMOVE_PATTERN/MODIFY_VALUE in-memory (not silent warning)
- [ ] **O26**: Add round-trip consumption tests (apply in-memory → verify config consumed by extraction)
- [ ] **O27**: Invalidate manifest cache (stale `current_concept=None` from pre-O16 cache)
