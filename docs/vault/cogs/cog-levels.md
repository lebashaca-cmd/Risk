---
title: levels.py
date: 2026-11-05
tags: [risk, cog]
---

# levels.py

Cog file `cogs/levels.py` (451 lines).

- File: `discord-bot-python/cogs/levels.py` (451 lines)
- Classes: `Levels`
- Data files: `data/level_settings.json`, `data/levels.json`
- Environment variables: none
- Background loops: `flush` (every(seconds=30))
- Event listeners: `on_message`

## Commands

| Command | Aliases | What it does | Needs |
|---|---|---|---|
| `addxp` |  | Gives someone extra XP. Usage: !addxp @user 500 | Manage Server |
| `delreward` |  | Removes the reward for a level. Usage: !delreward 10 | Manage Roles |
| `levelchannel` |  | Chooses where level-ups are announced: a #channel, here, or off. Usage: !levelchannel #levels | Manage Server |
| `levelinfo` |  | Shows how levels are set up in this server. Usage: !levelinfo |  |
| `levelmessage` |  | Sets the level-up message using {user}, {name} and {level}, or reset. Put {embed} at the start and the end to send it as an embed. Usage: !levelmessage {embed} Nice one {user}, level {level}! {embed} | Manage Server |
| `levelreward` |  | Gives a role when members reach a level. Usage: !levelreward 10 @Regular | Manage Roles |
| `levelrewards` | `levelroles` | Lists the roles given at each level. Usage: !levelrewards |  |
| `levels` | `xpboard` | Shows the most active members by XP, 10 per page. Usage: !levels 2 |  |
| `levelstats` |  | Shows level statistics for the server. Usage: !levelstats |  |
| `nextlevel` |  | Shows how much XP is left for the next level. Usage: !nextlevel @user |  |
| `noxp` |  | Toggles a channel or role that earns no XP. Usage: !noxp #bot-spam | Manage Server |
| `rank` | `level` | Shows someone's level and XP. Usage: !rank @user |  |
| `removexp` |  | Takes XP away from someone. Usage: !removexp @user 500 | Manage Server |
| `resetlevels` |  | Resets everyone's XP in this server. Usage: !resetlevels confirm | Administrator |
| `resetxp` |  | Resets one person's XP and message count. Usage: !resetxp @user | Manage Server |
| `rewardmode` |  | Chooses whether reward roles stack or only the newest is kept. Usage: !rewardmode replace | Manage Roles |
| `rewardsync` |  | Gives reward roles to members who already qualify. Usage: !rewardsync | Manage Roles |
| `setlevel` |  | Sets someone to the start of a level. Usage: !setlevel @user 10 | Manage Server |
| `setxp` |  | Sets someone's XP. Usage: !setxp @user 2500 | Manage Server |
| `xpcooldown` |  | Sets how many seconds a member waits between XP gains. Usage: !xpcooldown 45 | Manage Server |
| `xpmultiplier` |  | Sets how much XP each message earns, from 0.1 to 100. Usage: !xpmultiplier 2 | Manage Server |
| `xpneeded` |  | Shows the total XP needed to reach a level. Usage: !xpneeded 25 |  |

Related: [Cogs index](INDEX.md), [Architecture](../Architecture.md), [Commands by category](../commands/INDEX.md)
