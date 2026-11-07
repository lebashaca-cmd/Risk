---
title: Guide: add a dashboard section
date: 2026-11-05
tags: [risk, guide, dev, dashboard]
---

# Guide: add a dashboard section

**Bot (`cogs/dashboard.py`)**
1. Add the name to `SECTIONS`.
2. Write `read_<name>(guild)` and `write_<name>(guild, body)` using the validators in [Validation rules](../dashboard/validation-rules.md).
3. Add an entry to `REQUIREMENTS` listing the cog, file and attributes it needs, so a stale host file disables only this tab.
4. Add it to `stores_for(section)` so a failed save rolls back.

**Website**
5. Add the name to `SECTIONS` in `website/dashboard.py` (the PUT allowlist).

**Frontend**
6. Add the types in `dash-types.ts`.
7. Write a renderer (see `dash-extra.ts`) and add it to the renderers and `SECTION_META` in `dashboard.ts`.
8. Compile with `npx tsc -p .` and commit the output.

**Finish**
9. Extend the tests, write a note under `docs/vault/dashboard/`, and mention it in the changelog.

Related: [Dashboard sections](../dashboard/INDEX.md), [Frontend structure](../dashboard/frontend-structure.md), [Add a command](add-a-command.md)
