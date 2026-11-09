# Risk Control Panel

A private Windows app for the bot's owner. From it you can see the bot's status, shut it down or restart it, turn commands off in every server, block users, switch maintenance mode on, change the bot's status, ban servers, give or take VIP, post a message in any server, change prices and staff roles, read the bot's console and reload parts of the bot.

It is for **you only**. It can't do anything unless it has your secret key, and only your bot accepts that key.

## Set up (once)

1. Make a key. Any long random text works, at least 32 characters. For example, in a terminal:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`
2. On the bot's host, set the environment variable `OWNER_PANEL_KEY` to that key. Also set `OWNER_IDS` to your Discord user ID. Upload the new `cogs/owner_control.py` and the updated `main.py`, then restart the bot.
3. Open `RiskPanel.exe`. Enter the bot's address (the host's address with the bot's web port, like `http://12.34.56.78:25239`, the `SERVER_PORT`) and the key, then press Connect. It saves them in `RiskPanel.config.json` next to the program.

## How it works

- The app runs a tiny web page that only your own computer can reach (`127.0.0.1`), and shows it in an Edge or Chrome app window. Closing the window closes the program.
- Your key never leaves the program, and the window never sees it. Each request to the bot is signed with the key instead (an HMAC of the request, the time and a one-time number), so a stranger watching the network can't copy or replay a request, and requests older than 30 seconds are refused.
- If the bot's address starts with `http://` the requests can't be forged, but what the bot answers can be read by someone on the same network path. Put the bot behind https if that matters to you.
- Without `OWNER_PANEL_KEY` on the bot, the owner API is switched off completely.

## Keep it safe

- Don't share `RiskPanel.exe` together with `RiskPanel.config.json`, and never upload the config file anywhere. Whoever has the key controls your bot. If it leaks, change `OWNER_PANEL_KEY` on the bot and reconnect.
- Windows may say the app is from an unknown publisher the first time, because it isn't code-signed. You built it from this folder, so choose More info, then Run anyway.

## Build it yourself

You need Go 1.22 or newer.

- Windows: double-click `build.bat`, or run `go build -ldflags "-H=windowsgui -s -w" -o RiskPanel.exe .`
- Any system: `./build.sh` builds `RiskPanel.exe` for Windows and a native copy for testing.

The page's files are in `ui/` and are built into the program. There are no outside packages.
