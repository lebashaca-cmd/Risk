# Permissions

Risk checks Discord permissions every time you run a command. This page lists which permission each command asks of you, and what Risk needs for itself.

## What Risk needs

When you add Risk, keep the default permissions ticked. These are the ones features rely on:

- **Send Messages, Embed Links, Attach Files and Add Reactions** for nearly everything.
- **Manage Messages** for `!clear`, auto-mod and deleting command messages.
- **Manage Roles** for level rewards, autorole, verify and reaction roles. Risk's role must sit **above** the roles it hands out.
- **Manage Channels** for tickets, locks, `!slowmode` and channel tools.
- **Kick Members, Ban Members and Moderate Members** for the moderation commands.
- **View Audit Log** for the log lookup commands.

If a command fails with a permission message, the fix is nearly always one of these two: tick the permission, or move Risk's role higher in the role list.

## What you need

Commands list the permission they need on their reference entry. Members with **Manage Server** also have extra reach: they ignore [command rules](command-rules) and disabled commands.

{{permissions}}

## Good to know

- Discord's **Administrator** permission counts as every permission.
- Risk never lets someone do more than their own permissions allow. It also cannot act on members whose top role is above its own.
- Commands not listed here need no permission.
