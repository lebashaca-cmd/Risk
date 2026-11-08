# Command rules

Command rules let staff decide who can run commands, where, and how often. They live in the dashboard under **Commands**, and they have two layers: **basic rules** for every command and **command rules** for one command at a time.

Members with the **Manage Server** permission (or Administrator) ignore every rule, so staff can never lock themselves out. `!help` and `!dashboard` are never blocked by basic rules either.

## Basic rules

These apply to all commands in the server.

| Rule | What it does |
|---|---|
| Commands are off in these channels | Risk answers nothing there, such as in a chat-only channel |
| Commands only work in these channels | The opposite: pick a bot channel and commands only work there. Leave empty to allow every channel |
| These roles can't use commands | Members with any of these roles are blocked everywhere |
| Wait between a member's commands | A pause of 0 to 60 seconds between any two commands from the same member |
| Delete the command message | After a command runs, Risk deletes what the member typed. Needs the Manage Messages permission |

A member who breaks a basic rule gets a short message saying why, instead of silence.

## Rules for one command

Press **Add a rule**, pick a command, and set any of these:

| Setting | What it does |
|---|---|
| Only these roles can use it | Everyone else is blocked. Leave empty to allow everyone |
| Only works in these channels | Leave empty to allow every channel |
| These roles can't use it | Blocked roles win over the allowed list |
| Turned off in these channels | The command is blocked in those channels only |
| Managers only | Only people with Manage Server can use it |
| Cooldown per member | 0 to 3,600 seconds before the same member can use that command again |

You can have up to 500 rules. A rule on a command also covers its subcommands, so a rule on `giveaway` covers `giveaway start`.

## How the checks are ordered

Risk checks things from the widest to the narrowest and stops at the first one that blocks:

1. Is the member a manager? If so, everything is allowed.
2. Is the command switched off in **General**?
3. Basic rules: blocked channel, only-these channels, blocked roles, wait between commands.
4. The command's own rule: managers only, blocked channels, blocked roles, allowed channels, allowed roles, cooldown.

## Examples

- **Keep commands in one place.** Set "Commands only work in these channels" to `#bot-commands`.
- **Quiet the economy.** Add a rule on `slots` with "Turned off in these channels" set to `#general`.
- **Staff-only note tool.** Add a rule on `note` with "Managers only" on.
- **Slow a heavy command.** Add a rule on `heist` with a 600 second cooldown.
- **Mute a troublemaker's commands.** Put them in a role and add it to "These roles can't use commands".

## Good to know

- Rules only affect Risk commands. They don't change Discord permissions.
- Commands that already need a Discord permission still need it. Rules only make things stricter.
- You can switch a whole command off in **General** without writing a rule.
