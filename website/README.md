# Risk website

A small site for the Risk Discord bot: home page with a live status strip, a searchable command list, the Terms of Service and the Privacy Policy.

- **Frontend:** TypeScript in `src/`, compiled to plain JavaScript in `web/assets/js/`. The compiled files are included, so you don't need Node to run the site.
- **Backend:** Python (`server.py`, aiohttp). It serves the pages and five small JSON routes: `/api/config`, `/api/status`, `/api/commands`, `/api/tos`, `/api/privacy`.
- **Data:** `data/bot.json` holds the command list and the terms. A script builds it from your bot's files.

## Run it

```
pip install -r requirements.txt
cp .env.example .env        # then edit the values
python server.py
```

Open http://localhost:8080.

## Settings (`.env`)

| Name | What it does |
| --- | --- |
| `PORT` | Port the site listens on. Hosts like Render set this for you. |
| `BOT_STATUS_URL` | The bot's public status page, for the live badge. Without it the badge says "Status unavailable". |
| `CLIENT_ID` | The bot's application ID. Builds the "Add Risk to your server" link. Without it the button is hidden. |
| `INVITE_URL` | Use your own invite link instead of building one. |
| `INVITE_PERMISSIONS` | Override the permissions number in the invite link. |
| `SUPPORT_URL` | Optional support server link. |
| `TRUST_PROXY` | Set to `1` behind a proxy so rate limits see real visitor IPs. |

Nothing secret goes in this site. The application ID is public, and the site never sees your bot token.

## Keep the command list up to date

When you add or change commands in the bot, regenerate the data and restart the site:

```
python tools/export_bot_data.py /path/to/your/bot
```

The folder you point it at has `main.py` and `cogs/` inside. It reads the files without running them. It leaves off `dusklogs` and `duskreset` because they are private admin tools. To change that, pass `--hide name1,name2`.

## Change the frontend

```
npm install
npm run build      # or: npm run watch
```

Edit files in `src/` and `web/assets/css/site.css`. The compiled output goes to `web/assets/js/`.

## Show the server count (optional)

The bot's `main.py` status handler should include `"guilds": len(bot.guilds)` so the badge can show how many servers Risk is in. Without it the badge still works and just leaves the count out.

## Deploy on Render

`render.yaml` is a Render Blueprint, so Render sets the service up for you.

1. Put the contents of this folder at the root of a GitHub repository (`render.yaml`, `server.py` and `web/` should be at the top level, not inside a subfolder).
2. In Render, choose New, then Blueprint, and pick the repository.
3. Render reads `render.yaml`, installs `requirements.txt` and starts `python server.py`. Visit the `onrender.com` address it gives you.

The blueprint already has your bot's status address and application ID. To change them later, edit the environment variables on the service in the Render dashboard.

Notes:
- Render's free plan puts the site to sleep after about 15 minutes without visits, so the first visit afterwards can take up to a minute to load. A paid plan keeps it awake.
- Render sets `PORT` itself and the server reads it, so you don't need to set it.
- `/healthz` is the health check Render uses.

The bot's own host only gives the bot one port, and the bot's status page already uses it, so the website has to run somewhere else. Render, Railway, Fly.io or any small VPS all work: the start command is `python server.py` and the install command is `pip install -r requirements.txt`.

## Dashboard

Server owners and people with Manage Server sign in with Discord and change Risk's settings for their server. It lives at `dashboard.<your domain>/<server id>`.

How it fits together: the site (this folder) handles the Discord sign-in and forwards settings changes to the bot's web port with a shared key. The bot checks the person's permissions in that server again and validates every value before saving.

### Turn it on

1. **Pick a key.** Make up a long random string (at least 16 characters, 32+ is better).
2. **Bot host** (bot-hosting.cloud, in the bot's `.env` or Startup variables):
   - `DASHBOARD_KEY` = the key
   - `DASHBOARD_URL` = `https://dashboard.<your domain>` (shown by the `!dashboard` command)
   Upload the updated bot files and restart.
3. **Render** (service, Environment tab):
   - `DASHBOARD_KEY` = the same key
   - `DISCORD_CLIENT_SECRET` = the application's client secret (Discord Developer Portal, your app, OAuth2)
   - `DASHBOARD_HOST` = `dashboard.<your domain>` (no `https://`)
4. **Custom domain.** In Render, Settings, Custom Domains, add `dashboard.<your domain>` and create the DNS record Render shows. Add your main domain too if you want the site there. Render's `onrender.com` address can't have subdomains, so this step needs a domain you own.
5. **Discord redirect.** In the Developer Portal, OAuth2, Redirects, add `https://dashboard.<your domain>/api/auth/callback`.

Without `DASHBOARD_HOST` the dashboard still works on the main address at `/dashboard/<server id>`. If `DASHBOARD_HOST` is set, `/dashboard/...` on the main site redirects to the subdomain.

### Notes

- Sign-ins are kept in the site's memory, so a Render restart or sleep signs everyone out. They sign back in with one click.
- The sign-in asks Discord for the `identify` and `guilds` scopes only, and the token is revoked right after the server list is read.
- Each save is recorded in the server's logs as "Dashboard Updated" with who made it.
