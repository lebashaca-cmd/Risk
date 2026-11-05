---
title: Testing
date: 2026-11-05
tags: [risk, testing]
---

# Testing

Nothing was tested against live Discord, Twitch, TikTok or Render. Tests use fake guilds, channels and members, and a headless Chromium for the website.

| Script | What it proves |
|---|---|
| `loadtest.py` | Every cog loads |
| `dashtest.py` | 36 checks of the dashboard API: sections, validation, rollback, permissions |
| `viptest.py` | 58 checks: limits, rules, auto-replies, announcements, expiry, bot profile |
| `sitetest.py` | The website server: sign-in, CSRF, proxying |
| `fullstack.py` | Browser end to end: sign-in, every tab, profile, saving |
| `streamtest.py` | 35 checks: alerts, roles, Twitch and TikTok parsing, test commands |
| `staletest.py` | Old host files produce a clear message, not a crash |

The scripts were kept in a scratch folder and are not in the repo. Lessons from writing them:

- Pass real types in tests. A giveaway crash hid because tests passed ints where a `timedelta` arrives.
- Stale data files from an earlier run can make a browser test fail. Clear `data/*.json` first.
- Extensions loaded through `load_extension` produce a new module, so fetch classes like `ApiError` from `sys.modules`.

Related: [Troubleshooting](Troubleshooting.md), [Changelog](Changelog.md)
