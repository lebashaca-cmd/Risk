---
title: Lookups
date: 2026-11-05
tags: [risk, lookups]
---

# Lookups

The `Nerve` cog (`cogs/nerve.py`) calls `https://api.nerve.wtf` with the `x-api-key` header from `NERVE_API_KEY`.

## What exists

| Command | Endpoint |
|---|---|
| `!tiktok <user>` | `/v1/tiktok/profile` |
| `!github <user or owner/repo>` | `/v1/github/user`, `/v1/github/repository` |
| `!spotify <link or search>` | `/v1/spotify/track`, `album`, `artist`, `playlist`, `search` |
| `!youtube <link or search>` | `/v1/youtube/video`, `playlist`, `channel`, `search` |

Responses are read defensively: `find()` searches nested keys by normalised name, so small shape changes do not break the embeds.

## What is waiting

More lookups were asked for. The nerve.wtf site blocks automated readers and no public docs turned up, so the endpoint names and parameters have to come from you (paste the docs page or endpoint list). Each new lookup is then a small addition to `cogs/nerve.py` following the existing pattern. See [Open items](Open-Items.md).

Related: [Setup and environment variables](Setup-and-Env-Vars.md), [Open items](Open-Items.md)
