---
title: Deploy guide
date: 2026-11-05
tags: [risk, deploy]
---

# Deploy guide

## The bot

1. Upload the **whole** `discord-bot-python` folder to the host, not just changed files. New files (`cogs/vip.py`, `cogs/streams.py`) are easy to miss, and a stale file next to a new one causes crashes.
2. Install requirements if `requirements.txt` changed.
3. Restart.
4. Run `!cogstatus` (owner only). It should say every cog loaded.

## The website

Render redeploys by itself when a pull request is merged into `main`. The TypeScript is compiled with `npx tsc -p .` and the output in `website/web/assets/js/` is committed, so Render does not need a build step.

## The dashboard subdomain (Namecheap)

1. In Render, open the web service, Settings, Custom Domains, add `dashboard.yourdomain.com`.
2. In Namecheap, Domain List, Manage, Advanced DNS, add a **CNAME** record: Host `dashboard`, Value the `onrender.com` address Render shows.
3. Wait for Render to verify and issue the certificate.
4. Set `DASHBOARD_HOST` on Render and add the OAuth redirect in the Developer Portal.
5. Dashboard links become `dashboard.yourdomain.com/<server id>`. The path form `/dashboard/<id>` also works.

Related: [Setup and environment variables](Setup-and-Env-Vars.md), [Troubleshooting](Troubleshooting.md)
