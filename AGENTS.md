# AGENTS.md

## Cursor Cloud specific instructions

`foothold-lab` is a **documentation / research hub** (Korean) for the FOOTHOLD
quadruped-locomotion RL project. It is **not a software product**: there is no
application server, database, build system, test suite, or dependency manifest.
The runnable RL/sim code lives in the sibling `foothold-rl` repo (needs GPU +
Isaac Sim) and is **not** in this workspace.

### Runtime / dependencies
- Only runtime needed is **Python 3** (stdlib only). No `requirements.txt`,
  `package.json`, lockfiles, or install step exists — nothing to install.

### The only locally-runnable logic: the inbox → docs promotion pipeline
- Contributors drop Markdown under `inbox/<name>/`; the team lead curates it into
  `docs/research/` (which is what gets published to the public site).
- `.github/scripts/review_inbox.py` is the **promotion gate**. It scores a
  submission against 4 criteria (h1 title, evidence tags, source link, no
  web-forbidden elements) and prints JSON. Run it directly, e.g.:
  `python3 .github/scripts/review_inbox.py inbox/meang/*.md`
- `.github/workflows/promote.yml` performs the actual copy into
  `docs/research/` (prepending a credit header). It is triggered by a GitHub
  issue comment (`/승격`) from the lead and needs GitHub context + secrets
  (`PROJECT_TOKEN`, `DISCORD_*`); it does **not** run standalone locally.

### Not runnable in this environment (don't expect them to work as-is)
- `tools/robogauge/*.py` — import `torch`/`numpy` and reference hardcoded
  Windows checkpoint paths (`C:\isaac\...`). Analysis-only, not runnable here.
- `docs/meetings/print/render.sh` — PDF render via headless `google-chrome` +
  NanumGothic fonts. Optional utility, not part of any core flow.

### Repo policy gotchas
- `main` is protected (`.github/workflows/main-guard.yml`): only the team lead
  commits directly. Everyone else uses a branch + PR.
- `_raw`/copyrighted source material and secrets must never be committed here.
