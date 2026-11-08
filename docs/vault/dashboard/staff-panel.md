---
title: Staff panel
date: 2026-11-08
tags: [risk, dashboard, staff]
---

# Staff panel

A private page at `/staff` (on the dashboard address when one is set) for the Risk team. A button called Staff sits under the footer links on every page.

It is only for people in **your own Risk server**. Servers that have Risk installed never get access, whoever runs them.

## Who gets in

The bot decides, not the website. A person has a role if they are:

1. A bot owner: the Discord application's owner or team, or a user ID in `OWNER_IDS`. Owners always get in, even if `STAFF_GUILD_ID` isn't set.
2. A member of the server in `STAFF_GUILD_ID` who has a role. A role comes from a Discord role listed in `STAFF_ROLE_IDS` (staff) or `DEV_ROLE_IDS` (developer), or from an assignment made in the panel.

| Role | Sees |
|---|---|
| Staff | Totals: servers, members, VIP servers and banned servers |
| Developer | The totals and the owner panel |
| Owner | The same as developer, and can also give the developer and owner roles |

## Owner panel

- **Servers:** every server Risk is in, biggest first, with search. Give VIP (plan, days, note), take VIP, or ban.
- **Prices:** the price and checkout link for each plan. The VIP page shows them within about a minute.
- **Banned servers:** ban by server ID with a reason, or unban. A banned server loses its VIP, Risk leaves it, and Risk leaves again if someone adds it back.
- **Roles:** assign staff (developers and owners), developer or owner (owners only). The person must be in the staff server.
- **Recent changes:** the last 50 things done in the panel and who did them.

## How it works

1. The person signs in with Discord (the same sign-in as the dashboard).
2. The page asks the site, the site asks the bot with the person's user ID, and the bot checks their role on every request. The site never decides.
3. Changes are saved on the bot in `data/staff.json`. Prices and bans survive restarts.

Code: `cogs/staff.py`, `route_staff` in `cogs/dashboard.py`, `staff` in `website/dashboard.py`, `website/src/staff.ts`.

Related: [Dashboard index](INDEX.md), [VIP](../VIP.md), [Setup and env vars](../Setup-and-Env-Vars.md)
