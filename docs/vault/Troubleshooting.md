---
title: Troubleshooting
date: 2026-11-05
tags: [risk, troubleshooting]
---

# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "Discord didn't complete the sign-in" | Discord's Cloudflare answered Render's IP with an HTML 429 | The code exchange now runs on the bot. Set `DISCORD_CLIENT_SECRET` on the bot host |
| `AttributeError: 'dict' object has no attribute 'data'` in the Welcome cog | An old `welcome.py` on the host next to the new dashboard | Upload the whole folder. The dashboard now reports a stale section instead of crashing |
| "The bot sent an unexpected answer" | An uncaught error produced a plain-text 500 | A JSON catch-all now returns a readable message. Check the bot log for the traceback |
| Giveaway `TypeError` comparing int and timedelta | `launch()` got a timedelta | Fixed by converting with `total_seconds()` |
| "The request wasn't valid JSON" when changing avatar or banner | The bot read only the first chunk of a large upload | The bot now reads the whole body. Upload `cogs/dashboard.py` |
| A new command does nothing | The new cog file is not on the host (unknown commands are ignored silently) | Upload the whole folder, restart, run `!cogstatus` |
| Alerts for the Discord "Streaming" status never fire | Presence intent off | Enable it in the Developer Portal and set `STREAM_PRESENCE=1` |
| Role is not pinged | Role not mentionable and no Mention Everyone permission | Allow mentions for the role |
| TikTok alerts silent | TikTok blocked the host or changed its data | `!tiktoktest @name` while the account is live |
| Hook says "unpushed commits, no remote branch" | A false report from the hook | Check with `git ls-remote --heads origin <branch>` against `git rev-parse HEAD` |

Related: [Deploy guide](Deploy-Guide.md), [Architecture](Architecture.md)
