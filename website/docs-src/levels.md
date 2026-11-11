# Levels and XP

Members earn XP by chatting. XP adds up to a level, and levels can hand out roles.

## How XP works

- Each message earns 15 to 25 XP, multiplied by your server's multiplier.
- A member can earn XP at most once per cooldown (60 seconds by default), so spamming doesn't help.
- The level for a total is the whole number part of the square root of XP divided by 100. In other words, reaching level **n** takes `100 × n × n` XP in total: level 1 is 100, level 5 is 2,500 and level 10 is 10,000.
- Channels and roles you list as no-XP earn nothing.

## Commands for members

- `!rank` (or `!level`) shows a level card picture: your level with a progress bar, XP earned over 1, 7 and 30 days, your daily average, the top members and the busiest channels of the last 30 days. If the host can't draw pictures it shows the same facts as an embed. `!rank @user` shows someone else. The card needs the Pillow library on the bot host (`pip install -r requirements.txt`). Channel and XP history starts counting from when this version is installed.
- `!profile` shows every stat Risk keeps for you with your rank in each, and `!profile` shows every stat Risk keeps for you with your rank in each.
- `!leaderboard` shows the top members as a picture, 8 per page with avatars, sorted by coins, level, messages and more (`!leaderboard level 2`). `!levels` does the same for XP. Both fall back to an embed if Pillow is missing.
- `!nextlevel` shows how much XP is left for the next level, `!xpneeded 20` the total XP for a level, and `!levelinfo` how levels are set up in this server.
- `!levelstats` shows server-wide numbers.

## Settings for staff

| Goal | Command |
|---|---|
| Choose where level-ups appear | `!levelchannel #levels` (or `here`, or `off`) |
| Write the level-up message | `!levelmessage {embed} Nice one {user}, level {level}! {embed}` |
| Change XP speed | `!xpmultiplier 2` (from 0.1 to 100) |
| Change the cooldown | `!xpcooldown 45` |
| Stop XP in a channel or for a role | `!noxp #bot-spam` or `!noxp @Muted` (run again to undo) |
| Give a role at a level | `!levelreward 10 @Regular` |
| Remove a reward | `!delreward 10` |
| List rewards | `!levelrewards` |
| Stack rewards or keep only the newest | `!rewardmode stack` or `!rewardmode replace` |
| Give reward roles to members who already qualify | `!rewardsync` |

Staff can also adjust people directly with `!addxp`, `!removexp`, `!setxp`, `!setlevel`, `!resetxp` and `!resetlevels`.

## The level-up message

The default message is `🎉 {user} reached level **{level}**!`. You can use these in it, along with every [variable](variables):

- `{user}` mentions the member and `{name}` is their name.
- `{level}` is the new level, `{nextlevel}` the one after, `{xp}` their total XP and `{messages}` how many messages they have sent.
- Put `{embed}` at the start and the end to send it as an embed with their picture.

## Good to know

- Reward roles must sit below Risk's top role, and can't be managed roles or @everyone.
- `!levelmessage reset` goes back to the default.
- All of this is under **Levels** in the [dashboard](dashboard) too.
