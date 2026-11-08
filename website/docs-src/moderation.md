# Moderation and auto-mod

Risk has 60+ moderation commands plus automatic filters. Every moderation command checks the permission of the person using it, and Risk also needs the matching permission itself and a role above the member it acts on.

## Warnings, timeouts, kicks and bans

| Goal | Command |
|---|---|
| Warn and record it | `!warn @user reason` |
| See or remove warnings | `!warnings @user`, `!delwarn`, `!clearwarnings @user` |
| Stop someone talking for a while | `!timeout @user 10m reason`, undo with `!untimeout @user` |
| Remove someone | `!kick @user reason` |
| Ban | `!ban @user reason`, `!softban @user` (ban then unban to wipe messages), `!idban <id>` for people who left |
| Ban for a set time | `!tempban @user 3d reason`, list with `!tempbans` |
| Undo | `!unban <id>`, `!unbanall`, list with `!banlist` |

Durations use `s`, `m`, `h` and `d`, like `30m`, `12h` or `3d`.

## Cleaning up

- `!clear 10` deletes the last ten messages.
- `!purgeuser @user 50` deletes one member's recent messages in the channel.
- `!purgebots` removes recent bot messages.
- `!nuke` clones and replaces a channel to wipe it completely.
- `!snipe` and `!editsnipe` show the last deleted or edited message (Manage Messages).

## Locking things down

- `!lock` and `!unlock` stop or allow @everyone from sending in a channel.
- `!hide` and `!unhide` hide a channel from @everyone.
- `!slowmode 10s` sets slowmode, `!slowmode off` removes it.
- `!lockdown raid` locks every text channel at once, and `!unlockdown` undoes it. Use it during a raid.

## Roles and channels

`!addrole`, `!removerole`, `!roleall @Member` (give everyone a role), `!unroleall`, `!createrole`, `!deleterole`, `!rolecolor`, `!rolename`, `!createchannel`, `!deletechannel`, `!renamechannel`, `!clonechannel`, `!settopic`, `!nick` and `!resetnick`.

## Voice moderation

`!vckick`, `!vcmove`, `!vcmute`, `!vcunmute`, `!vcdeafen`, `!vcundeafen`, `!vcmuteall`, `!vcdisconnectall`.

## Auto-mod

Auto-mod watches messages and deletes the ones that break your rules. Members who can manage messages are never filtered. `!automod` shows what is on.

| Filter | What it does |
|---|---|
| `!antilink on` | Deletes messages with links |
| `!antiinvite on` | Deletes Discord invite links |
| `!antispam on` | Deletes message floods (six messages in five seconds) and times the sender out for five minutes |
| `!maxmentions 5` | Deletes messages that mention more than that many people or roles. `0` turns it off |
| `!badwords add word` | Blocks a word or short phrase. Your command message is deleted so the word isn't shown |

Manage the blocked words with `!badwords list`, `!badwords remove word`, `!badwords clear` and `!badwords import` (attach a `.txt` or `.env` file with one word per line or separated by commas). The list can hold 10,000 words, and matching stays fast because Risk compiles the list into one pattern.

Use `!automodignore #channel` or `!automodignore @role` to leave a channel or role alone. Run it again to remove the exception.

Every one of these settings is also in the dashboard under Auto-moderation.

## Good to know

- Joins, leaves, bans and message edits and deletes can be recorded with [server logs](logs).
- If a command says Discord denied permission, Risk's role is probably below the member's top role, or it lacks the needed permission.
- Members with Manage Server can run commands that a [command rule](command-rules) would otherwise block, so don't rely on rules to restrict staff.
