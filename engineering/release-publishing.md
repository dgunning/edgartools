# Release Publishing & Credentials

EdgarTools publishing is **maintainer-only and manual today** (Posture A). A hardened
GitHub Actions Trusted-Publishing workflow exists but is **inert** until activated (Posture B).

The `release-specialist` agent is configured to **never publish** — it builds artifacts,
pushes the tag, and creates the GitHub release, then hands the `dist/` files back to you.

---

## Posture A — Manual publish (current)

Build and publish from your workstation:

```bash
hatch build                       # produces dist/*.whl and dist/*.tar.gz
twine check dist/*                # sanity-check metadata
twine upload dist/*               # publishes to PyPI
```

### Credential hardening (do this once)

The PyPI token must **not** live in plaintext `~/.pypirc`. Use the macOS Keychain
(the active `keyring` backend), and use a **project-scoped** token.

1. **Create a fresh project-scoped token** at <https://pypi.org/manage/account/token/>
   — scope it to the `edgartools` project only, not "Entire account".
   (Rotating is worth it: the previous token sat in plaintext and was used by an agent.)

2. **Store it in the Keychain** (the secret never touches disk):
   ```bash
   keyring set https://upload.pypi.org/legacy/ __token__
   # paste the pypi-… token at the prompt
   ```

3. **Reduce `~/.pypirc` to keyring-only** — keep the structure but drop the password
   so twine falls back to the Keychain:
   ```ini
   [distutils]
   index-servers = pypi

   [pypi]
   repository = https://upload.pypi.org/legacy/
   username = __token__
   ```

4. **Delete the old token** on PyPI once the Keychain path is verified
   (`twine upload` succeeds on the next release).

`hatch publish` routes through keyring too, but has shown a 403/keyring quirk on this
machine (see edgartools-vunl); `twine upload` is the reliable manual path.

---

## Posture B — Trusted Publishing (hardened, inert until activated)

Workflow: `.github/workflows/release-publish.yml`. Eliminates the on-disk token entirely
(short-lived OIDC token, <15 min) and produces PEP 740 Sigstore attestations automatically.

### Why it's hardened against the known breach classes
- **Every action pinned to a full commit SHA** — mutable tags can't be repointed under us
  (this is what broke tj-actions/changed-files victims; SHA-pinned users were safe).
- **`permissions: {}` at top level**; `id-token: write` granted only to the isolated publish job.
- **Build and publish are separate jobs** — the publish job runs only download-artifact +
  gh-action-pypi-publish, so a hijacked build-time action can't reach the OIDC token.
- **`pypi` environment gate** requires a human approval click before publish runs.
- **Manual `workflow_dispatch` trigger** — publishing is always a deliberate action.

### Activation steps (when you're ready to adopt B)
1. **Register the Trusted Publisher** at <https://pypi.org/manage/project/edgartools/settings/publishing/>:
   - Owner: `dgunning`  ·  Repository: `edgartools`
   - Workflow filename: `release-publish.yml`
   - Environment name: `pypi`
2. **Create the `pypi` GitHub Environment** (repo Settings → Environments):
   - Add yourself as a **required reviewer** (forces manual approval per publish).
   - Optionally restrict to `v*` tags.
3. **Add `zizmor` as a blocking lint** to catch workflow misconfig before it ships:
   ```bash
   pipx run zizmor .github/workflows/
   ```
4. Run the workflow from the Actions tab (`Publish to PyPI` → Run workflow → enter the tag),
   approve the environment gate, and confirm the upload + attestations on PyPI.
5. Once trusted, **revoke the manual token** and remove the Keychain entry — there is then
   no long-lived PyPI credential anywhere.

### Keeping the pins fresh
SHA pins don't auto-update. Enable Dependabot or Renovate for `github-actions` so PRs bump
the pinned SHAs (with the human-readable version in the trailing comment) as new releases ship.
