---
title: utility_more.py
date: 2026-11-05
tags: [risk, cog]
---

# utility_more.py

Cog file `cogs/utility_more.py` (610 lines).

- File: `discord-bot-python/cogs/utility_more.py` (610 lines)
- Classes: `UtilityMore`
- Data files: none of its own
- Environment variables: none
- Background loops: none
- Event listeners: none

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `addemoji` |  | Adds a custom emoji from an image link or attachment. Usage: !addemoji party https://example.com/party.png | Manage Expressions |
| `admins` |  | Lists the members with Administrator permission. Usage: !admins | guild_only |
| `age` |  | Works out an age and the next birthday from a date. Usage: !age 2000-05-17 |  |
| `average` | `mean` | Gives the mean, median, mode, range and sum of some numbers. Usage: !average 4 8 15 16 23 42 |  |
| `bmi` |  | Works out body mass index from kg and cm, or lb and inches. Usage: !bmi 70 175 or !bmi 154 69 imperial |  |
| `boosters` |  | Lists the members boosting the server. Usage: !boosters | guild_only |
| `bots` |  | Lists the bots in this server. Usage: !bots | guild_only |
| `caesar` |  | Shifts the letters of some text, a Caesar cipher. Usage: !caesar 3 hello |  |
| `charinfo` |  | Shows the Unicode name and code of each character. Usage: !charinfo é |  |
| `convert` |  | Converts length, mass, volume, speed and temperature units. Usage: !convert 10 km to mi |  |
| `countdown` |  | Counts down to a UTC date and time. Usage: !countdown 2026-12-25 18:00 |  |
| `crypto` |  | Shows a cryptocurrency price in US dollars. Usage: !crypto eth |  |
| `daysuntil` |  | Tells you how many days are left until a date. Usage: !daysuntil 2026-12-25 |  |
| `emojiinfo` |  | Shows details about a custom emoji. Usage: !emojiinfo :name: |  |
| `epoch` | `unix` | Converts between Unix time and a UTC date. Usage: !epoch 1798221600 or !epoch 2026-12-25 18:00 |  |
| `joined` |  | Shows when someone joined and their join position. Usage: !joined @user | guild_only |
| `leetspeak` | `leet` | Writes text in leetspeak. Usage: !leetspeak elite hacker |  |
| `lowercase` | `lower` | Turns text into lowercase. Usage: !lowercase HELLO |  |
| `newest` |  | Lists the members who joined most recently. Usage: !newest | guild_only |
| `oldest` |  | Lists the members who joined first. Usage: !oldest 2 | guild_only |
| `palette` |  | Builds a five-colour palette from one hex colour. Usage: !palette #5865F2 |  |
| `percent` |  | Works out percentages between two numbers. Usage: !percent 20 150 |  |
| `pypi` |  | Looks up a Python package on PyPI. Usage: !pypi requests |  |
| `removeemoji` |  | Deletes a custom emoji from this server. Usage: !removeemoji :party: | Manage Expressions |
| `roman` |  | Converts a number to a Roman numeral, or back. Usage: !roman 2026 |  |
| `slugify` | `slug` | Turns text into a url-friendly slug. Usage: !slugify My Great Post! |  |
| `titlecase` |  | Turns text Into Title Case. Usage: !titlecase the quick brown fox |  |
| `uppercase` | `upper` | Turns text into UPPERCASE. Usage: !uppercase hello |  |
| `urlencode` |  | Encodes or decodes text for use in a link. Usage: !urlencode encode hello world |  |
| `uuid` |  | Generates random UUIDs. Usage: !uuid 3 |  |
| `whohas` |  | Lists the members that have a role. Usage: !whohas @Moderators | guild_only |
| `wordcount` | `wc` | Counts the words, characters and sentences in some text. Usage: !wordcount some text here |  |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
