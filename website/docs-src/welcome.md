# Welcome and leave

Risk can greet people when they join and say goodbye when they leave.

## Set up a welcome message

```
!welcome #welcome {embed} Welcome New_user to {server}! You are the {ordinal} member. {embed}
```

- Write `New_user` where the new member should appear. In a normal message it becomes a mention. Inside an embed it shows their bold name and a normal mention is sent above the embed, so they still get notified.
- Put `{embed}` at the very start and the very end to send the message as an embed with their profile picture. The embed uses your VIP accent colour if you have one.
- Any [variable](variables) works too, like `{server.members}` or `{user.age}`.

Turn it off with `!welcomeoff`. Your leave settings are kept.

## Leave messages

Set the leave message and channel in the dashboard under **Welcome and leave**. Write `New_user` where the member's name should go. Leave messages never ping anyone.

## Test a message first

Run `!testvars Welcome {user.mention}, you are the {ordinal} member!` to see how variables turn out, using yourself as the member.

## VIP welcome DM

VIP White servers can also send each new member a private welcome message with `!welcomedm set <text>`. See [VIP commands](vip-commands).

## Good to know

- Risk needs permission to send messages in the welcome channel.
- The dashboard shows the same fields, so you can edit the text there and see the limits as you type.
