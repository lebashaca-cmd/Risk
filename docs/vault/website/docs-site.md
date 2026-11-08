---
title: Docs site
date: 2026-11-08
tags: [risk, website, docs]
---

# Docs site

A documentation site that explains everything Risk does: guides for each feature, a page for every command, the variables, VIP plans, permissions and troubleshooting. It is static HTML in `website/web/docs/`, generated, so there is nothing to run for it.

## Where it is served

- `docs.<your domain>` when the site's `DOCS_HOST` is set (add the subdomain as a custom domain on Render, the same way as the dashboard one).
- `/docs/` on the main address, always. `/docs` redirects to `/docs/`.

All pages sit in one folder and link with relative links, so the same files work in both places. Links back to the main site carry `data-main`, and `docs.js` points them at the main domain when it runs on the docs host.

## How it is built

`python tools/build_docs.py [bot folder]` (from `website/`) reads three things:

| Source | Becomes |
|---|---|
| `docs-src/*.md` | The written guides. Small markdown: headings, lists, tables, code blocks, links, `{{directive}}` lines |
| `data/bot.json` | One page per command category, the permissions page, search entries. Regenerate it first with `tools/export_bot_data.py` |
| `discord-bot-python/utils/variables.py` | The variables table |
| `discord-bot-python/cogs/vip.py` | The plan table and VIP command groups (read as text) |

Directives: `{{categories}}`, `{{stats}}`, `{{variables}}`, `{{vipplans}}`, `{{vipcommands}}`, `{{permissions}}`, `{{commands:Category}}` and `{{count}}` inside text.

The output (`*.html`, `search.json`) is committed, like the compiled TypeScript. Rebuild after changing a command or a guide. `docs.css` and `docs.js` are handwritten, with no inline script or style so the site's strict CSP is kept. Search runs in the browser over `search.json`.

The staff panel is deliberately not documented there.

Related: [Server](server.md), [Message templates](../Message-Templates.md)
