---
title: Risk project notes
date: 2026-11-05
tags: [risk, index]
---

# Risk project notes

Notes on the Risk Discord bot and its website and dashboard, written 2026-11-05 as a stand-in for a connected Obsidian vault. Open this folder as a vault in Obsidian (File, Open folder as vault) or read it on GitHub: every link is a relative markdown link.

## Start here

- [Architecture](Architecture.md): how the bot, the website and the dashboard talk to each other
- [Setup and environment variables](Setup-and-Env-Vars.md): every setting, where it goes, and what happens without it
- [Deploy guide](Deploy-Guide.md): uploading the bot, Render, and the dashboard subdomain on Namecheap
- [Troubleshooting](Troubleshooting.md): every error we hit and how it was fixed

## Features

- [Dashboard](Dashboard.md): server picker, sections, bot profile, how saving and security work
- [VIP](VIP.md): what VIP unlocks, how to grant it, the limits that were removed
- [Stream alerts](Streams.md): Go Live, Discord status, Twitch and TikTok alerts
- [Message templates](Message-Templates.md): `{embed}`, `{user}`, `{level}`, `New_user`
- [Lookups](Lookups.md): the Nerve API commands and what is still to add
- [Commands by category](commands/INDEX.md): all 343 commands, generated from the bot

## More sections

- [Cogs](cogs/INDEX.md): one note per bot file with its commands, data files, loops and listeners
- [Dashboard sections](dashboard/INDEX.md): one note per tab, the API, validation rules, sign-in flow, frontend
- [Website](website/file-map.md): file map and server behaviour
- [Guides](guides/developer-portal-setup.md): Developer Portal, Twitch app, upload to the host, add a command, add a dashboard section, git workflow, backups, writing tests, regenerating the command list
- [Reference](reference/Command-Index-A-Z.md): command index, permissions index, environment variables, data files, security model, intents, Discord limits, glossary, FAQ, runbooks, roadmap

## Working on it

- [Testing](Testing.md): the test scripts and what each one proves
- [Changelog](Changelog.md): every pull request, in order
- [Decisions](Decisions.md): why things are built the way they are
- [Open items](Open-Items.md): what is waiting on you or on later work

Related: [Open items](Open-Items.md)
- [website/](website/INDEX.md)
- [guides/](guides/INDEX.md)
- [reference/](reference/INDEX.md)
