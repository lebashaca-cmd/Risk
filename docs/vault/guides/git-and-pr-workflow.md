---
title: Guide: git and pull request workflow
date: 2026-11-05
tags: [risk, guide, dev]
---

# Guide: git and pull request workflow

- Repo: `lebashaca-cmd/Risk`, default branch `main`. Work on a branch, open a pull request, merge, and Render redeploys the site.
- Branches so far: one per feature (`dashboard`, `dashboard-oauth-via-bot`, `dashboard-json-errors`, `dashboard-vip`).
- Check a push really happened with `git ls-remote --heads origin <branch>` and compare with `git rev-parse HEAD`. A "no remote branch" hook warning has been wrong every time.
- After changing TypeScript run `npx tsc -p .` and commit the compiled `web/assets/js`.
- After changing commands run the exporter and commit `website/data/bot.json`.
- Secrets never go in git: `.env` and `data/` are ignored.

Related: [Changelog](../Changelog.md), [Regenerating the command list](regenerate-command-list.md)
