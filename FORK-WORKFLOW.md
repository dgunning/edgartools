# EdgarTools fork workflow

This copy of [EdgarTools](https://github.com/dgunning/edgartools) is set up as a **fork** so you can add private features and keep merging from upstream.

## Remotes

| Remote    | URL                              | Use |
|-----------|-----------------------------------|-----|
| `upstream` | https://github.com/dgunning/edgartools.git | Pull/merge main development |
| `origin`  | *(you add this)*                  | Your fork (private repo) for your changes |

`main` tracks `upstream/main`. There is no `origin` until you create your fork.

## 1. Create your fork (one-time)

1. On GitHub: **Fork** [dgunning/edgartools](https://github.com/dgunning/edgartools) into your account (e.g. `https://github.com/YOUR_USER/edgartools`), or create a new **private** repo and push this clone to it (no “fork” button needed for a private copy).
2. Add your fork as `origin`:

   ```bash
   cd edgartools
   git remote add origin https://github.com/YOUR_USER/edgartools.git
   # or: git remote add origin git@github.com:YOUR_USER/edgartools.git
   ```

3. Push your current branch and set upstream for future pushes:

   ```bash
   git push -u origin main
   ```

After this, `origin` = your repo, `upstream` = dgunning/edgartools.

## 2. Merge latest from upstream

To bring in changes from the main EdgarTools repo:

```bash
cd edgartools
git fetch upstream
git merge upstream/main
# fix conflicts if any, then:
git push origin main   # if you use origin
```

## 3. Add your private features

Work on a branch (recommended) or on `main`:

```bash
git checkout -b feature/my-feature
# edit code, commit
git push -u origin feature/my-feature
```

Merge to your `main` when ready, then keep pulling from `upstream` as above.

## 4. Develop inside claude-docker

The **claude-docker** setup mounts this repo at `/mnt/edgartools`. To run the MCP server from your fork (with your changes) inside the container:

```bash
# Inside the container
pip3 install -e "/mnt/edgartools[ai]"
python3 -m edgar.ai --test   # verify
```

Then use Claude Code with the edgartools MCP as usual. See `../claude-docker/README.md` for full MCP setup.

## Quick reference

| Task              | Command |
|-------------------|---------|
| Fetch upstream    | `git fetch upstream` |
| Merge upstream    | `git merge upstream/main` |
| Push your fork    | `git push origin main` |
| Use fork in Docker| In container: `pip3 install -e "/mnt/edgartools[ai]"` |
