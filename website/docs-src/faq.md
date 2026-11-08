# Troubleshooting

## Risk doesn't answer a command

1. Check the prefix. The defaults `!`, `?` and `,` always work. If staff set another prefix, that works too.
2. Check that Risk can **see and send messages** in that channel.
3. The command may be switched off or restricted. Ask staff to look at **General** and **Commands** in the [dashboard](dashboard) and the [command rules](command-rules). Risk tells you when a rule blocks you.
4. Wait a moment and try again. Commands have cooldowns, and Risk says how long.
5. Type `!ping`. If that works, only the one command is the problem.

## "Discord says I don't have permission"

Risk's role is below the member or role it is trying to change, or it is missing the permission. Move Risk's role higher in the role list and check the [permissions](permissions) it needs.

## The dashboard doesn't show my server

- You need **Manage Server** or Administrator on that server.
- Risk must be in the server. Add it first if not.
- Sign out and in again after changing your roles.

## A dashboard section says it isn't available

The bot is running an older copy of that feature. Update the bot's files and restart it. The other sections keep working.

## Level rewards or autorole don't work

The role must sit **below** Risk's top role, can't be a managed (integration) role and can't be @everyone. Then run `!rewardsync` to hand out rewards to members who already qualify.

## Welcome messages don't appear

Run `!welcome` again with the channel, and check that Risk can send messages there. `!welcomeoff` removes the channel and text, so set it up again afterwards.

## My variable shows up as text

Risk leaves a variable alone when it doesn't recognise it. Check the spelling against the [variables](variables) list and use `!testvars` to try the message. Some only work in some places: `{level}` and `{xp}` only in level-up messages.

## Stream alerts don't post

- Run `!streamtest`. If that doesn't post, the alert channel or Risk's permissions are the problem.
- Twitch needs keys on the bot's host, and TikTok is unofficial and can fail. `!twitchtest` and `!tiktoktest` tell you what Risk sees.

## VIP doesn't show up

`!vip` shows the plan for the server you run it in. VIP belongs to one server, so check you are in the right one, then ask in the support server with the server ID.

## Still stuck

Ask in the support server and mention the command you ran and what Risk answered.
